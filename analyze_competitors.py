import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))
CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'analysis')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_followers(val):
    if not val or val.strip() in ('', 'unknown'):
        return 0
    val = val.strip().replace(',', '')
    try:
        if val.endswith('K'):
            return int(float(val[:-1]) * 1000)
        if val.endswith('M'):
            return int(float(val[:-1]) * 1_000_000)
        return int(float(val))
    except ValueError:
        return 0


def parse_count(val):
    if not val or val.strip() == '':
        return 0
    val = val.strip().replace(',', '')
    try:
        if val.endswith('K'):
            return int(float(val[:-1]) * 1000)
        if val.endswith('M'):
            return int(float(val[:-1]) * 1_000_000)
        return int(float(val))
    except ValueError:
        return 0


def load_tf_mentions():
    rows = []
    for f in sorted(os.listdir(CSV_DIR)):
        if not re.match(r'\d{4}-\d{2}-\d{2}\.csv', f):
            continue
        with open(os.path.join(CSV_DIR, f), newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                rows.append({
                    'source': 'trendforce',
                    'handle': row.get('handle', '').strip().lower().lstrip('@'),
                    'displayName': row.get('displayName', ''),
                    'followers': parse_followers(row.get('followers', '0')),
                    'likes': parse_count(row.get('likes', '0')),
                    'retweets': parse_count(row.get('retweets', '0')),
                    'replies': parse_count(row.get('replies', '0')),
                    'sentiment': row.get('sentiment', ''),
                    'sentimentScore': float(row.get('sentimentScore', 0) or 0),
                    'tweetUrl': row.get('tweetUrl', ''),
                    'text': row.get('text', ''),
                    'timestamp': row.get('timestamp', ''),
                })
    return rows


def load_competitor_mentions():
    rows = []
    for f in sorted(os.listdir(CSV_DIR)):
        if not f.startswith('competitors_') or not f.endswith('.csv'):
            continue
        with open(os.path.join(CSV_DIR, f), newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                rows.append({
                    'source': 'competitor',
                    'competitorMentioned': row.get('competitorMentioned', ''),
                    'handle': row.get('handle', '').strip().lower().lstrip('@'),
                    'displayName': row.get('displayName', ''),
                    'followers': parse_followers(row.get('followers', '0')),
                    'likes': parse_count(row.get('likes', '0')),
                    'retweets': parse_count(row.get('retweets', '0')),
                    'replies': parse_count(row.get('replies', '0')),
                    'sentiment': row.get('sentiment', ''),
                    'sentimentScore': float(row.get('sentimentScore', 0) or 0),
                    'tweetUrl': row.get('tweetUrl', ''),
                    'text': row.get('text', ''),
                    'timestamp': row.get('timestamp', ''),
                })
    return rows


def avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else 0


def bar(val, max_val, width=20):
    if max_val == 0:
        return ''
    return '█' * min(int(val / max_val * width), width)


tf_tweets = load_tf_mentions()
comp_tweets = load_competitor_mentions()

print(f'\n{"="*60}')
print(f'  TRENDFORCE vs COMPETITOR MENTION ANALYSIS')
print(f'{"="*60}')
print(f'  TrendForce mention tweets loaded : {len(tf_tweets)}')
print(f'  Competitor mention tweets loaded : {len(comp_tweets)}')


# ── 1. Top accounts by follower count ────────────────────────
print(f'\n{"─"*60}')
print('  TOP 15 ACCOUNTS BY FOLLOWER COUNT (mentioning TrendForce)')
print(f'{"─"*60}')
tf_by_handle = {}
for t in tf_tweets:
    h = t['handle']
    if h not in tf_by_handle or t['followers'] > tf_by_handle[h]['followers']:
        tf_by_handle[h] = t

top_tf = sorted(tf_by_handle.values(), key=lambda x: x['followers'], reverse=True)[:15]
max_f = top_tf[0]['followers'] if top_tf else 1
for t in top_tf:
    b = bar(t['followers'], max_f)
    followers_str = f"{t['followers']:,}"
    print(f"  {t['displayName'][:25]:<26} @{t['handle']:<22} {followers_str:>10} followers  {b}")

print(f'\n{"─"*60}')
print('  TOP 15 ACCOUNTS BY FOLLOWER COUNT (mentioning Competitors)')
print(f'{"─"*60}')
comp_by_handle = {}
for t in comp_tweets:
    h = t['handle']
    if h not in comp_by_handle or t['followers'] > comp_by_handle[h]['followers']:
        comp_by_handle[h] = t

top_comp = sorted(comp_by_handle.values(), key=lambda x: x['followers'], reverse=True)[:15]
max_f2 = top_comp[0]['followers'] if top_comp else 1
for t in top_comp:
    b = bar(t['followers'], max_f2)
    followers_str = f"{t['followers']:,}"
    print(f"  {t['displayName'][:25]:<26} @{t['handle']:<22} {followers_str:>10} followers  {b}  [{t['competitorMentioned']}]")


# ── 2. Accounts that mention BOTH TrendForce and competitors ──
print(f'\n{"─"*60}')
print('  ACCOUNTS THAT MENTION BOTH TRENDFORCE AND COMPETITORS')
print(f'{"─"*60}')
tf_handles = set(t['handle'] for t in tf_tweets)
comp_handles = set(t['handle'] for t in comp_tweets)
overlap = tf_handles & comp_handles

if overlap:
    overlap_info = []
    for h in overlap:
        tf_count = sum(1 for t in tf_tweets if t['handle'] == h)
        comp_count = sum(1 for t in comp_tweets if t['handle'] == h)
        comp_names = list(set(t['competitorMentioned'] for t in comp_tweets if t['handle'] == h))
        followers = tf_by_handle.get(h, comp_by_handle.get(h, {})).get('followers', 0)
        display = tf_by_handle.get(h, comp_by_handle.get(h, {})).get('displayName', h)
        overlap_info.append({
            'handle': h, 'displayName': display, 'followers': followers,
            'tf_count': tf_count, 'comp_count': comp_count, 'comp_names': comp_names,
        })
    overlap_info.sort(key=lambda x: x['followers'], reverse=True)
    print(f'  Found {len(overlap_info)} overlapping accounts:\n')
    for o in overlap_info:
        print(f"  @{o['handle']:<25} {o['displayName'][:20]:<21} {o['followers']:>10,} followers")
        print(f"    TrendForce mentions: {o['tf_count']}  |  Competitor mentions: {o['comp_count']}  ({', '.join(o['comp_names'])})")
else:
    print('  No overlapping accounts found yet (more data needed across days).')


# ── 3. Competitor mention breakdown ──────────────────────────
print(f'\n{"─"*60}')
print('  COMPETITOR MENTION BREAKDOWN')
print(f'{"─"*60}')
comp_counts = defaultdict(int)
for t in comp_tweets:
    comp_counts[t['competitorMentioned']] += 1

tf_total = len(tf_tweets)
max_c = max(comp_counts.values()) if comp_counts else 1
print(f'  TrendForce mentions total: {tf_total}')
print()
for name, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True):
    b = bar(count, max_c)
    print(f"  {name:<30} {count:>4} mentions  {b}")


# ── 4. Sentiment comparison ───────────────────────────────────
print(f'\n{"─"*60}')
print('  SENTIMENT COMPARISON')
print(f'{"─"*60}')

def sentiment_breakdown(tweets, label):
    counts = defaultdict(int)
    scores = defaultdict(list)
    for t in tweets:
        counts[t['sentiment']] += 1
        scores[t['sentiment']].append(t['sentimentScore'])
    total = len(tweets)
    print(f'\n  {label} ({total} tweets):')
    for s in ['positive', 'neutral', 'negative']:
        c = counts.get(s, 0)
        pct = round(c / total * 100, 1) if total else 0
        avg_score = avg(scores.get(s, []))
        b = bar(c, total)
        print(f"    {s:<10} {c:>4} ({pct:>5}%)  {b}  avg score: {avg_score}")

sentiment_breakdown(tf_tweets, 'TrendForce mentions')
sentiment_breakdown(comp_tweets, 'Competitor mentions')

avg_tf = avg([t['sentimentScore'] for t in tf_tweets])
avg_comp = avg([t['sentimentScore'] for t in comp_tweets])
print(f'\n  Overall avg sentiment score — TrendForce: {avg_tf}  |  Competitors: {avg_comp}')
winner = 'TrendForce' if avg_tf > avg_comp else 'Competitors'
print(f'  → {winner} receives more positive sentiment overall')


# ── 5. Engagement comparison ──────────────────────────────────
print(f'\n{"─"*60}')
print('  ENGAGEMENT COMPARISON (avg per tweet)')
print(f'{"─"*60}')

def eng_stats(tweets, label):
    likes = [t['likes'] for t in tweets]
    rts = [t['retweets'] for t in tweets]
    reps = [t['replies'] for t in tweets]
    total = [t['likes'] + t['retweets'] + t['replies'] for t in tweets]
    print(f'  {label}:')
    print(f'    Avg likes:     {avg(likes)}')
    print(f'    Avg retweets:  {avg(rts)}')
    print(f'    Avg replies:   {avg(reps)}')
    print(f'    Avg total:     {avg(total)}')

eng_stats(tf_tweets, 'TrendForce mention tweets')
print()
eng_stats(comp_tweets, 'Competitor mention tweets')


# ── 6. Top high-follower accounts NOT yet mentioning TF ───────
print(f'\n{"─"*60}')
print('  HIGH-FOLLOWER ACCOUNTS MENTIONING COMPETITORS BUT NOT TRENDFORCE')
print('  (potential accounts to target/engage)')
print(f'{"─"*60}')
comp_only = {h: comp_by_handle[h] for h in comp_handles - tf_handles}
top_comp_only = sorted(comp_only.values(), key=lambda x: x['followers'], reverse=True)[:10]
if top_comp_only:
    for t in top_comp_only:
        comp_names = list(set(tw['competitorMentioned'] for tw in comp_tweets if tw['handle'] == t['handle']))
        print(f"  @{t['handle']:<25} {t['displayName'][:20]:<21} {t['followers']:>10,} followers  [{', '.join(comp_names)}]")
else:
    print('  None found yet.')


# ── 7. Save CSV report ────────────────────────────────────────
report_path = os.path.join(OUTPUT_DIR, 'competitor_analysis.csv')
with open(report_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)

    w.writerow(['TRENDFORCE vs COMPETITOR MENTION ANALYSIS'])
    w.writerow([])

    w.writerow(['TOP ACCOUNTS BY FOLLOWERS - TRENDFORCE MENTIONS'])
    w.writerow(['handle', 'displayName', 'followers', 'tweet_count'])
    for t in top_tf:
        tc = sum(1 for tw in tf_tweets if tw['handle'] == t['handle'])
        w.writerow([t['handle'], t['displayName'], t['followers'], tc])
    w.writerow([])

    w.writerow(['TOP ACCOUNTS BY FOLLOWERS - COMPETITOR MENTIONS'])
    w.writerow(['handle', 'displayName', 'followers', 'competitor_mentioned', 'tweet_count'])
    for t in top_comp:
        tc = sum(1 for tw in comp_tweets if tw['handle'] == t['handle'])
        w.writerow([t['handle'], t['displayName'], t['followers'], t['competitorMentioned'], tc])
    w.writerow([])

    w.writerow(['ACCOUNTS MENTIONING BOTH TRENDFORCE AND COMPETITORS'])
    w.writerow(['handle', 'displayName', 'followers', 'tf_mentions', 'comp_mentions', 'competitors'])
    for o in (overlap_info if overlap else []):
        w.writerow([o['handle'], o['displayName'], o['followers'], o['tf_count'], o['comp_count'], '; '.join(o['comp_names'])])
    w.writerow([])

    w.writerow(['COMPETITOR MENTION COUNTS'])
    w.writerow(['competitor', 'mention_count'])
    for name, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True):
        w.writerow([name, count])
    w.writerow([])

    w.writerow(['HIGH-FOLLOWER ACCOUNTS MENTIONING COMPETITORS ONLY'])
    w.writerow(['handle', 'displayName', 'followers', 'competitors'])
    for t in top_comp_only:
        comp_names = list(set(tw['competitorMentioned'] for tw in comp_tweets if tw['handle'] == t['handle']))
        w.writerow([t['handle'], t['displayName'], t['followers'], '; '.join(comp_names)])

print(f'\nSaved analysis/competitor_analysis.csv')
print(f'{"="*60}\n')
