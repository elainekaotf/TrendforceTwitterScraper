import sys
import json
import re

try:
    from langdetect import detect, LangDetectException
    LANGDETECT_OK = True
except ImportError:
    LANGDETECT_OK = False
    print('[enrich_accounts] langdetect not installed', file=sys.stderr)

try:
    from deep_translator import GoogleTranslator
    TRANSLATE_OK = True
except ImportError:
    TRANSLATE_OK = False
    print('[enrich_accounts] deep-translator not installed — run: pip3 install deep-translator', file=sys.stderr)

try:
    from keybert import KeyBERT
    KEYBERT_OK = True
    kw_model = KeyBERT()
except Exception:
    KEYBERT_OK = False
    print('[enrich_accounts] keybert not installed — run: pip3 install keybert', file=sys.stderr)

try:
    import nltk
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    nltk.download('stopwords', quiet=True)
    from nltk.tokenize import word_tokenize
    from nltk import pos_tag
    from nltk.corpus import stopwords
    NLTK_OK = True
    STOPWORDS = set(stopwords.words('english'))
except Exception:
    NLTK_OK = False
    print('[enrich_accounts] nltk not available — noun extraction disabled', file=sys.stderr)

TECH_KEYWORDS = [
    # Memory
    'nand', 'dram', 'hbm', 'hbm2', 'hbm3', 'hbm4', 'ddr5', 'lpddr', 'lpddr5',
    'qlc', 'tlc', 'mlc', 'gddr', 'rdimm', 'dimm',
    # Storage
    'ssd', 'emmc', 'ufs', 'nand flash',
    # Companies
    'tsmc', 'samsung', 'sk hynix', 'hynix', 'micron', 'intel', 'nvidia',
    'amd', 'qualcomm', 'apple', 'mediatek', 'broadcom', 'arm', 'asml',
    'western digital', 'kioxia', 'seagate', 'trendforce', 'semianalysis',
    # Chips & semiconductor
    'semiconductor', 'wafer', 'foundry', 'chip', 'chiplet', 'node',
    'advanced packaging', 'cowos', 'soic', 'packaging', 'fab', 'yield',
    'process node', 'gate-all-around', 'backside power',
    # AI & servers
    'ai server', 'ai accelerator', 'data center', 'datacenter', 'hyperscaler',
    'gpu', 'cpu', 'tpu', 'llm', 'inference', 'training', 'edge ai',
    'on device', 'hpc', 'csp', 'rack', 'capex',
    # Memory types & products
    'memory', 'storage', 'server', 'ai chip', 'supply chain',
    # Display
    'oled', 'amoled', 'lcd', 'mini led', 'micro led', 'display', 'panel',
    # Phones
    'smartphone', 'iphone', 'handset', 'snapdragon',
    # Market terms (specific)
    'contract price', 'spot price', 'oversupply', 'shortage',
    'inventory correction', 'capacity utilization', 'bit shipment',
    'lead time', 'wafer starts',
]

# Keywords to always exclude from analysis (too generic or noisy)
KEYWORD_BLACKLIST = {
    'nm', 'earnings', 'announce', 'announced', 'announces', 'announcement',
    '2024', '2025', '2026', '2027', 'q1', 'q2', 'q3', 'q4',
    'report', 'reports', 'reported', 'share', 'shares', 'stock',
    'said', 'says', 'new', 'first', 'next', 'last', 'still', 'also',
    'guidance', 'margin', 'revenue', 'forecast', 'analyst',
    'company', 'market', 'industry', 'growth', 'increase', 'decrease',
    'quarter', 'year', 'month', 'week', 'day', 'time',
    'price', 'demand', 'capacity', 'shipment', 'billion', 'million',
    'percent', 'strong', 'weak', 'high', 'low', 'good', 'bad',
    'dominate', 'dominates', 'dominating', 'global', 'world', 'worldwide',
    'supply chain', 'supply', 'chain', 'cost', 'costs', 'ai chip', 'ai chips',
}

# Stopwords to exclude from noun fallback
EXTRA_STOPWORDS = {
    'rt', 'via', 'amp', 'would', 'could', 'should', 'also', 'new', 'said',
    'says', 'say', 'one', 'two', 'three', 'get', 'got', 'go', 'going',
    'know', 'think', 'make', 'made', 'good', 'great', 'big', 'lot',
    'many', 'much', 'still', 'even', 'well', 'just', 'need', 'want',
    'http', 'https', 'com', 'www',
}

def extract_keybert(text):
    if not KEYBERT_OK or len(text.strip()) < 10:
        return []
    try:
        results = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),  # single words and two-word phrases
            stop_words='english',
            top_n=5,
            use_mmr=True,   # diversity — avoids near-duplicate phrases
            diversity=0.5,
        )
        filtered = []
        for kw, score in results:
            if score <= 0.2:
                continue
            words = kw.lower().split()
            # skip if any word is blacklisted
            if any(w in KEYWORD_BLACKLIST for w in words):
                continue
            # skip bigrams made of two unrelated company names (e.g. "samsung sk")
            if len(words) == 2:
                companies = {'samsung', 'sk', 'hynix', 'micron', 'tsmc', 'nvidia',
                             'intel', 'amd', 'apple', 'qualcomm', 'mediatek', 'arm'}
                if words[0] in companies and words[1] in companies:
                    continue
            filtered.append(kw)
        return filtered
    except Exception:
        return []

def extract_keywords(text):
    lower = text.lower()
    hashtags = re.findall(r'#\w+', text.lower())
    tech = [kw for kw in TECH_KEYWORDS if kw in lower]
    return list(dict.fromkeys(hashtags + tech))  # dedupe preserving order

def extract_nouns(text):
    if not NLTK_OK:
        return []
    try:
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)
        nouns = [
            word.lower() for word, pos in tagged
            if pos in ('NN', 'NNS', 'NNP', 'NNPS')
            and len(word) > 2
            and word.lower() not in STOPWORDS
            and word.lower() not in EXTRA_STOPWORDS
            and not word.startswith('http')
            and word.isalpha()
        ]
        # Return top 5 most meaningful nouns
        seen = set()
        result = []
        for n in nouns:
            if n not in seen:
                seen.add(n)
                result.append(n)
            if len(result) >= 5:
                break
        return result
    except Exception:
        return []

def detect_lang(text):
    if not LANGDETECT_OK or len(text.strip()) < 10:
        return 'en'
    try:
        return detect(text)
    except LangDetectException:
        return 'en'

def translate_to_english(text, lang):
    if not TRANSLATE_OK or lang == 'en':
        return text
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated or text
    except Exception:
        return text

tweets = json.loads(sys.stdin.read())

for tweet in tweets:
    original_text = tweet.get('text', '')

    # Detect language
    lang = detect_lang(original_text)
    tweet['language'] = lang

    # Translate for keyword extraction only — original text is preserved
    if lang != 'en':
        translated = translate_to_english(original_text, lang)
        tweet['translatedText'] = translated
        working_text = translated
    else:
        tweet['translatedText'] = original_text
        working_text = original_text

    # Hashtags from original text (language-agnostic)
    hashtags = re.findall(r'#\w+', original_text.lower())

    # Tech keyword matches from translated text
    tech = extract_keywords(working_text)

    # Primary: KeyBERT on translated text
    keybert_phrases = extract_keybert(working_text)

    # Combine: hashtags + tech keywords + KeyBERT phrases
    all_keywords = list(dict.fromkeys(hashtags + tech + keybert_phrases))

    # Final fallback: significant nouns
    if not all_keywords:
        all_keywords = extract_nouns(working_text)

    has_images = tweet.get('hasImages', False)

    # Tweet is link-only if it contains a URL and has no other meaningful text
    text_without_urls = re.sub(r'https?://\S+', '', original_text).strip()
    is_link_only = bool(re.search(r'https?://\S+', original_text)) and len(text_without_urls) < 5

    if not all_keywords:
        if is_link_only:
            all_keywords = ['link']
        elif has_images:
            all_keywords = ['image']

    tweet['keywords'] = '; '.join(all_keywords) if all_keywords else ''

print(json.dumps(tweets))
