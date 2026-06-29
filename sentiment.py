import sys
import json
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from langdetect import detect, LangDetectException

LANGUAGE_NAMES = {
    'en': 'English', 'zh-cn': 'Chinese (Simplified)', 'zh-tw': 'Chinese (Traditional)',
    'ja': 'Japanese', 'ko': 'Korean', 'de': 'German', 'fr': 'French',
    'es': 'Spanish', 'pt': 'Portuguese', 'ar': 'Arabic', 'hi': 'Hindi',
    'ru': 'Russian', 'it': 'Italian', 'nl': 'Dutch', 'tr': 'Turkish',
    'vi': 'Vietnamese', 'th': 'Thai', 'id': 'Indonesian', 'pl': 'Polish',
}

# Language code -> definitive single country (only when unambiguous)
LANGUAGE_TO_COUNTRY = {
    'ja': 'Japan',
    'ko': 'South Korea',
    'th': 'Thailand',
    'vi': 'Vietnam',
    'id': 'Indonesia',
    'tr': 'Turkey',
    'pl': 'Poland',
    'it': 'Italy',
    'ru': 'Russia',
    'hi': 'India',
    'ar': None,  # ambiguous — handled via timezone in guess_country
    'zh-cn': None,  # could be China, Singapore, Malaysia
    'zh-tw': None,  # could be Taiwan or Hong Kong
    'de': None,  # Germany, Austria, Switzerland
    'fr': None,  # France, Belgium, many African countries
    'es': None,  # many countries
    'pt': None,  # Brazil vs Portugal
    'nl': None,  # Netherlands, Belgium
    'en': None,  # too ambiguous
}

# Timezone UTC hour ranges -> candidate countries/regions
TIMEZONE_TO_REGIONS = {
    'asia_pacific': set(['Japan', 'South Korea', 'China', 'Taiwan', 'Hong Kong',
                         'Singapore', 'Vietnam', 'Thailand', 'Indonesia', 'Malaysia',
                         'Philippines', 'Australia']),
    'europe_mideast': set(['United Kingdom', 'Germany', 'France', 'Italy', 'Netherlands',
                           'Poland', 'Russia', 'Turkey', 'United Arab Emirates', 'Saudi Arabia',
                           'Israel', 'India']),  # India overlaps
    'americas':       set(['United States', 'Canada', 'Brazil', 'Mexico', 'Argentina']),
    'overlap':        set(['Japan', 'South Korea', 'China', 'Australia',  # late Asia / early EU
                           'United Kingdom', 'Germany', 'France']),
}

# City / region / common text -> country
LOCATION_TEXT_MAP = {
    # Asia
    'tokyo': 'Japan', 'osaka': 'Japan', 'kyoto': 'Japan', 'japan': 'Japan',
    'seoul': 'South Korea', 'busan': 'South Korea', 'korea': 'South Korea', 'south korea': 'South Korea',
    'beijing': 'China', 'shanghai': 'China', 'shenzhen': 'China', 'guangzhou': 'China',
    'china': 'China', 'prc': 'China',
    'taipei': 'Taiwan', 'taiwan': 'Taiwan',
    'hong kong': 'Hong Kong', 'hk': 'Hong Kong',
    'singapore': 'Singapore', 'sg': 'Singapore',
    'bangkok': 'Thailand', 'thailand': 'Thailand',
    'jakarta': 'Indonesia', 'indonesia': 'Indonesia',
    'kuala lumpur': 'Malaysia', 'kl': 'Malaysia', 'malaysia': 'Malaysia',
    'manila': 'Philippines', 'philippines': 'Philippines',
    'ho chi minh': 'Vietnam', 'hanoi': 'Vietnam', 'vietnam': 'Vietnam',
    'mumbai': 'India', 'delhi': 'India', 'bangalore': 'India', 'bengaluru': 'India',
    'hyderabad': 'India', 'chennai': 'India', 'india': 'India',
    # Americas
    'new york': 'United States', 'nyc': 'United States', 'los angeles': 'United States',
    'la': 'United States', 'san francisco': 'United States', 'sf': 'United States',
    'silicon valley': 'United States', 'bay area': 'United States', 'seattle': 'United States',
    'chicago': 'United States', 'boston': 'United States', 'austin': 'United States',
    'washington': 'United States', 'dc': 'United States', 'usa': 'United States',
    'united states': 'United States', 'u.s.': 'United States', 'us': 'United States',
    'toronto': 'Canada', 'vancouver': 'Canada', 'canada': 'Canada',
    'sao paulo': 'Brazil', 'brazil': 'Brazil', 'brasil': 'Brazil',
    'mexico city': 'Mexico', 'mexico': 'Mexico',
    # Europe
    'london': 'United Kingdom', 'manchester': 'United Kingdom', 'uk': 'United Kingdom',
    'united kingdom': 'United Kingdom', 'england': 'United Kingdom',
    'berlin': 'Germany', 'munich': 'Germany', 'frankfurt': 'Germany', 'germany': 'Germany',
    'paris': 'France', 'france': 'France',
    'amsterdam': 'Netherlands', 'netherlands': 'Netherlands',
    'zurich': 'Switzerland', 'switzerland': 'Switzerland',
    'stockholm': 'Sweden', 'sweden': 'Sweden',
    'madrid': 'Spain', 'barcelona': 'Spain', 'spain': 'Spain',
    'moscow': 'Russia', 'russia': 'Russia',
    'dubai': 'United Arab Emirates', 'uae': 'United Arab Emirates',
    'abu dhabi': 'United Arab Emirates',
    'riyadh': 'Saudi Arabia', 'jeddah': 'Saudi Arabia', 'saudi arabia': 'Saudi Arabia',
    'saudi': 'Saudi Arabia', 'ksa': 'Saudi Arabia',
    'tel aviv': 'Israel', 'israel': 'Israel',
    'cairo': 'Egypt', 'egypt': 'Egypt',
    'kuwait': 'Kuwait', 'qatar': 'Qatar', 'doha': 'Qatar',
    'bahrain': 'Bahrain', 'oman': 'Oman', 'muscat': 'Oman',
    # Oceania
    'sydney': 'Australia', 'melbourne': 'Australia', 'australia': 'Australia',
}

def parse_location_text(raw):
    """Map a raw profile location string to a country. Returns None if unmappable."""
    if not raw or raw.strip().lower() in ('', 'unknown', 'earth', 'worldwide', 'global',
                                           'internet', 'everywhere', 'the internet', 'remote'):
        return None
    text = raw.lower().strip()
    # Try longest match first
    for key in sorted(LOCATION_TEXT_MAP, key=len, reverse=True):
        if key in text:
            return LOCATION_TEXT_MAP[key]
    return None

def utc_hour_to_zone(utc_hour):
    if utc_hour is None:
        return None
    if 0 <= utc_hour < 6:
        return 'asia_pacific'
    elif 6 <= utc_hour < 12:
        return 'europe_mideast'
    elif 12 <= utc_hour < 18:
        return 'americas'
    else:
        return 'overlap'

def guess_country(profile_location, lang_code, utc_hour):
    """
    Weighted location guess:
      1. Profile location (highest weight) — if parseable, trust it
      2. Language -> country (only when unambiguous single country)
      3. Language + timezone agreement as tiebreaker
      4. Unknown if signals conflict or insufficient
    """
    loc_country = parse_location_text(profile_location)

    # --- Weight 1: profile location is set and mappable -> trust it ---
    if loc_country:
        return loc_country

    # --- Weight 2: language maps to a single unambiguous country ---
    lang_country = LANGUAGE_TO_COUNTRY.get(lang_code)  # None if ambiguous
    if lang_country:
        # Sanity check: does timezone agree?
        tz_zone = utc_hour_to_zone(utc_hour)
        if tz_zone and lang_country in TIMEZONE_TO_REGIONS.get(tz_zone, set()):
            return lang_country
        elif tz_zone is None:
            return lang_country  # no timezone data, still trust language
        else:
            # Language says one region, timezone says another — flag unknown
            return 'Unknown'

    # --- Weight 3: ambiguous language — need timezone to narrow down ---
    # E.g. zh-cn during Asia-Pacific hours -> likely China/Taiwan/Singapore
    # But English during Asian hours with no location -> unknown
    if lang_code == 'en':
        # English is too global — timezone alone is not enough
        return 'Unknown'

    tz_zone = utc_hour_to_zone(utc_hour)
    if not tz_zone:
        return 'Unknown'

    # For ambiguous languages, check if tz agrees with the language's possible regions
    lang_region_hint = {
        'zh-cn': TIMEZONE_TO_REGIONS['asia_pacific'],
        'zh-tw': TIMEZONE_TO_REGIONS['asia_pacific'],
        'de':    {'Germany', 'Austria', 'Switzerland'},
        'fr':    {'France', 'Belgium'},
        'es':    TIMEZONE_TO_REGIONS['americas'] | {'Spain'},
        'pt':    {'Brazil', 'Portugal'},
        'nl':    {'Netherlands', 'Belgium'},
        'ar':    {'Saudi Arabia', 'United Arab Emirates', 'Egypt', 'Kuwait', 'Qatar', 'Bahrain', 'Oman', 'Jordan', 'Iraq', 'Lebanon'},
    }.get(lang_code, set())

    tz_countries = TIMEZONE_TO_REGIONS.get(tz_zone, set())
    overlapping = lang_region_hint & tz_countries

    if len(overlapping) == 1:
        return next(iter(overlapping))
    # Multiple or zero matches — not confident enough
    return 'Unknown'


def infer_timezone_hint(timestamp_str):
    if not timestamp_str:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        utc_hour = dt.hour
        if 0 <= utc_hour < 6:
            hint = 'Asia-Pacific active hours (UTC 0-6)'
        elif 6 <= utc_hour < 12:
            hint = 'Europe / Middle East active hours (UTC 6-12)'
        elif 12 <= utc_hour < 18:
            hint = 'Americas active hours (UTC 12-18)'
        else:
            hint = 'Asia-Pacific / Europe overlap (UTC 18-24)'
        return {'utcHour': utc_hour, 'activeRegionHint': hint}
    except Exception:
        return None


analyzer = SentimentIntensityAnalyzer()
tweets = json.loads(sys.stdin.read())

for tweet in tweets:
    text = tweet.get('text', '')

    # Sentiment
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']
    if compound >= 0.05:
        label = 'positive'
    elif compound <= -0.05:
        label = 'negative'
    else:
        label = 'neutral'
    tweet['sentiment'] = label
    tweet['sentimentScore'] = round(compound * 10, 4)
    tweet.pop('matchedPositive', None)
    tweet.pop('matchedNegative', None)

    # Language detection
    try:
        lang_code = detect(text) if len(text.strip()) > 10 else 'unknown'
    except LangDetectException:
        lang_code = 'unknown'
    tweet['language'] = lang_code
    tweet['languageName'] = LANGUAGE_NAMES.get(lang_code, lang_code)

    # Timezone hint
    tz = infer_timezone_hint(tweet.get('timestamp'))
    tweet['timezoneHint'] = tz
    utc_hour = tz['utcHour'] if tz else None

    # Weighted country guess
    tweet['guessedCountry'] = guess_country(
        tweet.get('profileLocation', ''),
        lang_code,
        utc_hour,
    )

print(json.dumps(tweets))
