import sys
import json
import os
from rapidfuzz import fuzz

try:
    import imagehash
    from PIL import Image, ImageEnhance
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print('[analyze_credit] imagehash/Pillow not installed — image matching disabled', file=sys.stderr)

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print('[analyze_credit] pytesseract not installed — OCR disabled', file=sys.stderr)

CREDIT_KEYWORDS = [
    'trendforce', 'trendforce.com', '@trendforce', 'via tf', 'source: tf',
    'source:tf', 'via trendforce', 'source: trendforce', 'per trendforce',
    'according to trendforce', 'data from trendforce',
]

PHASH_THRESHOLD = 12  # hamming distance; lower = stricter match


def check_citation(text):
    lower = text.lower()
    return any(kw in lower for kw in CREDIT_KEYWORDS)


def compute_text_similarity(tweet_text, tf_texts):
    if not tf_texts or not tweet_text.strip():
        return 0.0
    best = max(fuzz.token_set_ratio(tweet_text, tf) for tf in tf_texts)
    return round(best / 100.0, 4)


def compute_image_match(tweet_paths, tf_paths):
    if not IMAGEHASH_AVAILABLE or not tweet_paths or not tf_paths:
        return False
    tf_hashes = []
    for p in tf_paths:
        if not os.path.exists(p):
            continue
        try:
            tf_hashes.append(imagehash.phash(Image.open(p)))
        except Exception:
            pass
    if not tf_hashes:
        return False
    for p in tweet_paths:
        if not os.path.exists(p):
            continue
        try:
            h = imagehash.phash(Image.open(p))
            if any(abs(h - tfh) <= PHASH_THRESHOLD for tfh in tf_hashes):
                return True
        except Exception:
            pass
    return False


def ocr_detect_tf(image_paths):
    if not OCR_AVAILABLE or not IMAGEHASH_AVAILABLE or not image_paths:
        return False
    for p in image_paths:
        if not os.path.exists(p):
            continue
        try:
            img = Image.open(p).convert('L')  # grayscale
            img = ImageEnhance.Contrast(img).enhance(2.0)
            text = pytesseract.image_to_string(img, lang='eng').lower()
            if any(kw in text for kw in CREDIT_KEYWORDS):
                return True
        except Exception:
            pass
    return False


def classify_credit(cited, text_sim, image_match, ocr_found):
    # text_sim is on 0-10 scale here (raw, before rounding)
    if cited:
        return 'credited'
    has_tf_signal = text_sim >= 5.5 or image_match or ocr_found
    if not has_tf_signal:
        return 'no_tf_content'
    if text_sim >= 7.0 or image_match or ocr_found:
        return 'uncredited'
    return 'possible_uncredited'


data = json.loads(sys.stdin.read())
tweets = data['tweets']
tf_reference = data['tfReference']

tf_texts = [t.get('text', '') for t in tf_reference if t.get('text')]
tf_image_paths = [p for t in tf_reference for p in t.get('localImagePaths', [])]

for tweet in tweets:
    text = tweet.get('text', '')
    tweet_paths = tweet.get('localImagePaths', [])

    cited = check_citation(text)
    text_sim = compute_text_similarity(text, tf_texts)  # 0.0-1.0
    image_match = compute_image_match(tweet_paths, tf_image_paths)
    ocr_found = ocr_detect_tf(tweet_paths)

    text_sim_scaled = text_sim * 10  # 0.0-10.0
    tweet['cited'] = cited
    tweet['textSimilarity'] = round(text_sim_scaled, 2)
    tweet['imageMatch'] = image_match
    tweet['ocrFoundTF'] = ocr_found
    tweet['creditFlag'] = classify_credit(cited, text_sim_scaled, image_match, ocr_found)

print(json.dumps(tweets))
