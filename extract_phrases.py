"""
Extracts distinctive search phrases from TrendForce reference posts.
Prioritizes numerical stats and specific claims — these are the most
distinctive and least likely to appear coincidentally.
"""
import sys
import json
import re

def extract_phrases(text, max_phrases=2):
    phrases = []

    # 1. Sentences/clauses containing numbers — most distinctive
    sentences = re.split(r'[.!?\n]+', text)
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 15 or len(sent) > 120:
            continue
        # Must contain a number (stat, %, $, units)
        if not re.search(r'\d', sent):
            continue
        # Strip leading bullets/emoji
        sent = re.sub(r'^[\s\-•▪▶►*#🔹🔸📊📈📉⚡]+', '', sent).strip()
        if len(sent) < 15:
            continue
        phrases.append(sent)

    # 2. Extract specific numeric patterns with context (5-10 word windows)
    # e.g. "DRAM contract prices to rise 8-13%" -> search for that exact stat
    number_patterns = re.finditer(
        r'(?:[A-Za-z][A-Za-z0-9\s\-]{3,30}?)\s*(?:of\s+)?(?:US\$|USD|\$)?\d[\d,\.]*\s*(?:%|billion|million|thousand|units?|GB|TB|nm|W|x|X)?',
        text
    )
    for m in number_patterns:
        phrase = m.group(0).strip()
        if 8 <= len(phrase) <= 80 and re.search(r'\d', phrase):
            phrases.append(phrase)

    # Deduplicate, prefer longer phrases, limit to max_phrases
    seen = set()
    result = []
    for p in sorted(phrases, key=len, reverse=True):
        # Use first 30 chars as dedup key
        key = p[:30].lower()
        if key not in seen:
            seen.add(key)
            result.append(p)
        if len(result) >= max_phrases:
            break

    return result


posts = json.loads(sys.stdin.read())
output = []
for post in posts:
    text = post.get('text', '')
    if not text:
        continue
    phrases = extract_phrases(text)
    if phrases:
        output.append({ 'text': text[:200], 'phrases': phrases })

print(json.dumps(output))
