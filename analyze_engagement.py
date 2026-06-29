import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))

CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'analysis')
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALL_ACCOUNTS = ['QQ_Timmy', 'jukan05', 'TrendForce', 'dylan522p', 'SemiAnalysis_']

# Allow passing account names as CLI args: python3 analyze_engagement.py QQ_Timmy dylan522p
ACCOUNTS = sys.argv[1:] if len(sys.argv) > 1 else ALL_ACCOUNTS


def parse_count(val):
    """Convert Twitter stat strings like '1.2K', '3M' to int."""
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


def load_csv(handle):
    filepath = os.path.join(CSV_DIR, f'{handle}.csv')
    if not os.path.exists(filepath):
        print(f'  [!] csv/{handle}.csv not found — skipping')
        return []
    rows = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            likes    = parse_count(row.get('likes', '0'))
            retweets = parse_count(row.get('retweets', '0'))
            replies  = parse_count(row.get('replies', '0'))
            views    = parse_count(row.get('views', '0'))
            interaction = likes + retweets + replies

            ts = row.get('timestamp', '')
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(TAIWAN_TZ)
                hour    = dt.hour
                weekday = dt.strftime('%A')  # Monday, Tuesday...
            except Exception:
                hour    = None
                weekday = None

            keywords = [k.strip() for k in row.get('keywords', '').split(';') if k.strip()]
            has_images = row.get('hasImages', 'no').strip().lower() == 'yes'
            text = row.get('text', '')
            hashtags = [h.lower() for h in re.findall(r'#\w+', text)]

            rows.append({
                'timestamp':   ts,
                'hour':        hour,
                'weekday':     weekday,
                'likes':       likes,
                'retweets':    retweets,
                'replies':     replies,
                'views':       views,
                'interaction': interaction,
                'keywords':    keywords,
                'hashtags':    hashtags,
                'has_images':  has_images,
                'text':        text,
                'tweetUrl':    row.get('tweetUrl', ''),
            })
    return rows


def avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else 0


def top_n(d, n=10):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]


def analyze(handle, tweets):
    print(f'\n{"="*50}')
    print(f'  {handle}  ({len(tweets)} tweets)')
    print(f'{"="*50}')

    results = {'handle': handle, 'tweet_count': len(tweets)}

    # ── 1. Best hour to post ──────────────────────────────
    hour_interactions = defaultdict(list)
    for t in tweets:
        if t['hour'] is not None:
            hour_interactions[t['hour']].append(t['interaction'])

    hour_avg = {h: avg(v) for h, v in hour_interactions.items()}
    best_hours = sorted(hour_avg.items(), key=lambda x: x[1], reverse=True)[:5]

    print('\n📅 Best hours to post (Taiwan Time, avg total interaction):')
    for hour, score in best_hours:
        bar = '█' * min(int(score / max(hour_avg.values()) * 20), 20)
        print(f'  {hour:02d}:00  {bar}  {score}')

    results['best_hours'] = [{'hour': h, 'avg_interaction': s} for h, s in best_hours]
    results['all_hours']  = [{'hour': h, 'avg_interaction': avg(v), 'tweet_count': len(v)}
                              for h, v in sorted(hour_interactions.items())]

    # ── 2. Best day of week ───────────────────────────────
    day_interactions = defaultdict(list)
    for t in tweets:
        if t['weekday']:
            day_interactions[t['weekday']].append(t['interaction'])

    day_avg = {d: avg(v) for d, v in day_interactions.items()}
    day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    print('\n📆 Avg interaction by day of week:')
    for day in day_order:
        if day in day_avg:
            bar = '█' * min(int(day_avg[day] / max(day_avg.values()) * 20), 20)
            print(f'  {day:<10}  {bar}  {day_avg[day]}')

    results['best_days'] = sorted([{'day': d, 'avg_interaction': s} for d, s in day_avg.items()],
                                   key=lambda x: x['avg_interaction'], reverse=True)

    # ── 3. Images vs no images ────────────────────────────
    img_yes = [t['interaction'] for t in tweets if t['has_images']]
    img_no  = [t['interaction'] for t in tweets if not t['has_images']]
    avg_img    = avg(img_yes)
    avg_no_img = avg(img_no)
    print(f'\n🖼  Images vs no images:')
    print(f'  With image:    avg {avg_img}  ({len(img_yes)} tweets)')
    print(f'  Without image: avg {avg_no_img}  ({len(img_no)} tweets)')
    winner = 'images' if avg_img > avg_no_img else 'no images'
    diff = abs(round(((avg_img - avg_no_img) / avg_no_img * 100) if avg_no_img else 0, 1))
    print(f'  → {winner} perform {diff}% better')

    results['images'] = {
        'with_image':    {'avg_interaction': avg_img,    'count': len(img_yes)},
        'without_image': {'avg_interaction': avg_no_img, 'count': len(img_no)},
        'winner': winner, 'pct_difference': diff,
    }

    # ── 4. Top keywords by avg interaction ───────────────
    keyword_interactions = defaultdict(list)
    for t in tweets:
        for kw in t['keywords']:
            keyword_interactions[kw].append(t['interaction'])

    # Filter keywords with at least 3 appearances for statistical relevance
    kw_avg = {kw: avg(v) for kw, v in keyword_interactions.items() if len(v) >= 3}
    kw_count = {kw: len(v) for kw, v in keyword_interactions.items()}
    top_kws = sorted(kw_avg.items(), key=lambda x: x[1], reverse=True)[:15]

    print(f'\n🔑 Top keywords by avg interaction (min 3 tweets):')
    for kw, score in top_kws:
        print(f'  {kw:<30} avg {score:<8} ({kw_count[kw]} tweets)')

    results['top_keywords'] = [{'keyword': kw, 'avg_interaction': s, 'tweet_count': kw_count[kw]}
                                for kw, s in top_kws]

    # ── 5. Top performing tweets ──────────────────────────
    top_tweets = sorted(tweets, key=lambda x: x['interaction'], reverse=True)[:10]
    print(f'\n🏆 Top 10 tweets by interaction:')
    for i, t in enumerate(top_tweets, 1):
        print(f'  {i}. [{t["interaction"]} total | {t["likes"]}♥ {t["retweets"]}🔁 {t["replies"]}💬]')
        print(f'     {t["text"][:100]}{"..." if len(t["text"]) > 100 else ""}')
        print(f'     {t["tweetUrl"]}')

    results['top_tweets'] = [{
        'rank': i+1, 'interaction': t['interaction'],
        'likes': t['likes'], 'retweets': t['retweets'], 'replies': t['replies'],
        'views': t['views'],
        'text': t['text'], 'url': t['tweetUrl'], 'timestamp': t['timestamp'],
        'keywords': t['keywords'], 'has_images': t['has_images'],
    } for i, t in enumerate(top_tweets)]

    # ── 6. Keyword + image combo ──────────────────────────
    img_kw_interactions = defaultdict(list)
    for t in tweets:
        if t['has_images']:
            for kw in t['keywords']:
                img_kw_interactions[kw].append(t['interaction'])

    img_kw_avg = {kw: avg(v) for kw, v in img_kw_interactions.items() if len(v) >= 2}
    top_img_kws = sorted(img_kw_avg.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_img_kws:
        print(f'\n📸 Best keyword + image combos:')
        for kw, score in top_img_kws:
            print(f'  {kw:<30} avg {score}')
        results['best_image_keywords'] = [{'keyword': kw, 'avg_interaction': s} for kw, s in top_img_kws]

    # ── 7. Hashtag analysis ───────────────────────────────
    hashtag_interactions = defaultdict(list)
    hashtag_views = defaultdict(list)
    for t in tweets:
        for ht in t['hashtags']:
            hashtag_interactions[ht].append(t['interaction'])
            if t['views']:
                hashtag_views[ht].append(t['views'])

    ht_avg = {ht: avg(v) for ht, v in hashtag_interactions.items() if len(v) >= 2}
    ht_count = {ht: len(v) for ht, v in hashtag_interactions.items()}
    ht_view_avg = {ht: avg(hashtag_views[ht]) for ht in ht_avg if hashtag_views[ht]}
    top_hts_by_interaction = sorted(ht_avg.items(), key=lambda x: x[1], reverse=True)[:15]
    top_hts_by_count = sorted(ht_count.items(), key=lambda x: x[1], reverse=True)[:15]

    if top_hts_by_interaction:
        print(f'\n#️⃣  Top hashtags by avg interaction (min 2 tweets):')
        max_ht = top_hts_by_interaction[0][1] if top_hts_by_interaction else 1
        for ht, score in top_hts_by_interaction:
            bar = '█' * min(int(score / max_ht * 20), 20)
            views_str = f'  views avg: {ht_view_avg[ht]}' if ht in ht_view_avg else ''
            print(f'  {ht:<25} avg {score:<8} ({ht_count[ht]} tweets)  {bar}{views_str}')

        print(f'\n#️⃣  Most used hashtags:')
        max_hc = top_hts_by_count[0][1] if top_hts_by_count else 1
        for ht, count in top_hts_by_count:
            bar = '█' * min(int(count / max_hc * 20), 20)
            print(f'  {ht:<25} {count:>4} tweets  {bar}  avg interaction: {ht_avg.get(ht, 0)}')

    results['top_hashtags_by_interaction'] = [
        {'hashtag': ht, 'avg_interaction': s, 'tweet_count': ht_count[ht],
         'avg_views': ht_view_avg.get(ht, 0)}
        for ht, s in top_hts_by_interaction
    ]
    results['top_hashtags_by_usage'] = [
        {'hashtag': ht, 'tweet_count': c, 'avg_interaction': ht_avg.get(ht, 0)}
        for ht, c in top_hts_by_count
    ]

    # ── 9. Summary stats ─────────────────────────────────
    all_interactions = [t['interaction'] for t in tweets]
    print(f'\n📊 Summary:')
    print(f'  Total tweets:      {len(tweets)}')
    print(f'  Avg interaction:   {avg(all_interactions)}')
    print(f'  Median interaction:{sorted(all_interactions)[len(all_interactions)//2]}')
    print(f'  Max interaction:   {max(all_interactions) if all_interactions else 0}')

    all_views = [t['views'] for t in tweets]
    print(f'  Avg views:         {avg(all_views)}')
    print(f'  Max views:         {max(all_views) if all_views else 0}')

    results['summary'] = {
        'avg_interaction':    avg(all_interactions),
        'median_interaction': sorted(all_interactions)[len(all_interactions)//2] if all_interactions else 0,
        'max_interaction':    max(all_interactions) if all_interactions else 0,
        'avg_views':          avg(all_views),
        'max_views':          max(all_views) if all_views else 0,
    }

    return results


def make_bar(value, max_value, width=20):
    filled = int(value / max_value * width) if max_value else 0
    return '█' * filled


def save_csv_report(handle, results):
    """Write analysis CSV formatted like terminal output — no emojis to avoid crashes."""
    filepath = os.path.join(OUTPUT_DIR, f'{handle}_analysis.csv')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)

        def row(line=''):
            w.writerow([line])

        row(f'SUMMARY -- @{handle}')
        row(f'  Total tweets:       {results["tweet_count"]}')
        row(f'  Avg interaction:    {results["summary"]["avg_interaction"]}')
        row(f'  Median interaction: {results["summary"]["median_interaction"]}')
        row(f'  Max interaction:    {results["summary"]["max_interaction"]}')
        row(f'  Avg views:          {results["summary"].get("avg_views", "")}')
        row(f'  Max views:          {results["summary"].get("max_views", "")}')
        row()

        row('BEST HOURS TO POST (Taiwan Time, avg total interaction):')
        all_hours = results.get('all_hours', [])
        max_val = max((r['avg_interaction'] for r in all_hours), default=1)
        for r in sorted(all_hours, key=lambda x: x['hour']):
            bar = make_bar(r['avg_interaction'], max_val)
            row(f'  {r["hour"]:02d}:00  {bar}  {r["avg_interaction"]}  ({r["tweet_count"]} tweets)')
        row()

        row('AVG INTERACTION BY DAY OF WEEK:')
        day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        best_days = sorted(results.get('best_days', []),
                           key=lambda x: day_order.index(x['day']) if x['day'] in day_order else 99)
        max_val = max((r['avg_interaction'] for r in best_days), default=1)
        for r in best_days:
            bar = make_bar(r['avg_interaction'], max_val)
            row(f'  {r["day"]:<10}  {bar}  {r["avg_interaction"]}')
        row()

        row('IMAGES VS NO IMAGES:')
        img = results.get('images', {})
        row(f'  With image:    avg {img.get("with_image", {}).get("avg_interaction", "")}  ({img.get("with_image", {}).get("count", "")} tweets)')
        row(f'  Without image: avg {img.get("without_image", {}).get("avg_interaction", "")}  ({img.get("without_image", {}).get("count", "")} tweets)')
        row(f'  -> {img.get("winner", "")} perform {img.get("pct_difference", "")}% better')
        row()

        row('TOP KEYWORDS BY AVG INTERACTION (min 3 tweets):')
        top_kws = results.get('top_keywords', [])
        for r in top_kws:
            row(f'  {r["keyword"]:<30} avg {r["avg_interaction"]:<8} ({r["tweet_count"]} tweets)')
        row()

        row('BEST KEYWORD + IMAGE COMBOS:')
        for r in results.get('best_image_keywords', []):
            row(f'  {r["keyword"]:<30} avg {r["avg_interaction"]}')
        row()

        row('TOP HASHTAGS BY AVG INTERACTION (min 2 tweets):')
        top_hts = results.get('top_hashtags_by_interaction', [])
        max_val = max((r['avg_interaction'] for r in top_hts), default=1)
        for r in top_hts:
            bar = make_bar(r['avg_interaction'], max_val)
            views_str = f'  views avg: {r["avg_views"]}' if r.get('avg_views') else ''
            row(f'  {r["hashtag"]:<25} avg {r["avg_interaction"]:<8} ({r["tweet_count"]} tweets)  {bar}{views_str}')
        row()

        row('MOST USED HASHTAGS:')
        top_hts_usage = results.get('top_hashtags_by_usage', [])
        max_val = max((r['tweet_count'] for r in top_hts_usage), default=1)
        for r in top_hts_usage:
            bar = make_bar(r['tweet_count'], max_val)
            row(f'  {r["hashtag"]:<25} {r["tweet_count"]:>4} tweets  {bar}  avg interaction: {r["avg_interaction"]}')
        row()

        row('TOP 10 TWEETS BY INTERACTION:')
        for t in results.get('top_tweets', []):
            row(f'  {t["rank"]}. [{t["interaction"]} total | {t["likes"]} likes  {t["retweets"]} retweets  {t["replies"]} replies  views: {t.get("views", 0)}]')
            row(f'     {t["text"][:120]}{"..." if len(t["text"]) > 120 else ""}')
            row(f'     {t["url"]}')

    print(f'\n  Saved analysis/{handle}_analysis.csv')


all_results = {}
all_tweets_combined = []

for account in ACCOUNTS:
    tweets = load_csv(account)
    if not tweets:
        continue
    results = analyze(account, tweets)
    all_results[account] = results
    all_results[account]['tweets'] = tweets
    all_tweets_combined.extend(tweets)
    save_csv_report(account, results)

    # Standalone hashtag CSV
    ht_path = os.path.join(OUTPUT_DIR, f'{account}_hashtags.csv')
    with open(ht_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['hashtag', 'tweet_count', 'avg_interaction', 'avg_views'])
        seen_hts = set()
        usage = {r['hashtag']: r for r in results.get('top_hashtags_by_usage', [])}
        inter = {r['hashtag']: r for r in results.get('top_hashtags_by_interaction', [])}
        all_hts = list(usage.keys()) + [h for h in inter if h not in usage]
        for ht in all_hts:
            if ht in seen_hts:
                continue
            seen_hts.add(ht)
            u = usage.get(ht, {})
            i = inter.get(ht, {})
            w.writerow([ht, u.get('tweet_count', i.get('tweet_count', '')),
                        i.get('avg_interaction', u.get('avg_interaction', '')),
                        i.get('avg_views', '')])
    print(f'  Saved analysis/{account}_hashtags.csv')

# Combined analysis
if all_tweets_combined:
    print(f'\n{"="*50}')
    print(f'  COMBINED ({", ".join(ACCOUNTS)})  ({len(all_tweets_combined)} tweets total)')
    print(f'{"="*50}')
    combined_results = analyze('combined', all_tweets_combined)
    save_csv_report('combined', combined_results)
    all_results['combined'] = combined_results

# Master summary spreadsheet — all accounts side by side
summary_file = os.path.join(OUTPUT_DIR, 'summary.csv')
with open(summary_file, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    accounts_with_results = [k for k in all_results if k != 'combined']
    all_keys = accounts_with_results + (['combined'] if 'combined' in all_results else [])

    # Header
    w.writerow([''] + all_keys)

    # Overview
    w.writerow(['OVERVIEW'])
    w.writerow(['Tweet count']    + [all_results[k]['tweet_count']                        for k in all_keys])
    w.writerow(['Avg interaction'] + [all_results[k]['summary']['avg_interaction']         for k in all_keys])
    w.writerow(['Median interaction'] + [all_results[k]['summary']['median_interaction']   for k in all_keys])
    w.writerow(['Max interaction'] + [all_results[k]['summary']['max_interaction']         for k in all_keys])
    w.writerow([])

    # Best hours — full 24h table with bar per account
    w.writerow(['BEST HOURS TO POST (Taiwan Time)'])
    hour_header = ['Hour']
    for k in all_keys:
        hour_header += [f'{k} avg interaction', f'{k} chart']
    w.writerow(hour_header)
    all_hour_avgs = {k: {r['hour']: r['avg_interaction'] for r in all_results[k].get('all_hours', [])} for k in all_keys}
    max_hour_val  = {k: max(all_hour_avgs[k].values(), default=1) for k in all_keys}
    for hour in range(24):
        row = [f'{hour:02d}:00']
        for k in all_keys:
            val = all_hour_avgs[k].get(hour, 0)
            row += [val, make_bar(val, max_hour_val[k])]
        w.writerow(row)
    w.writerow([])

    # Best days — full week table with bar per account
    w.writerow(['BEST DAYS TO POST'])
    day_header = ['Day']
    for k in all_keys:
        day_header += [f'{k} avg interaction', f'{k} chart']
    w.writerow(day_header)
    day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    all_day_avgs = {k: {r['day']: r['avg_interaction'] for r in all_results[k].get('best_days', [])} for k in all_keys}
    max_day_val  = {k: max(all_day_avgs[k].values(), default=1) for k in all_keys}
    for day in day_order:
        row = [day]
        for k in all_keys:
            val = all_day_avgs[k].get(day, 0)
            row += [val, make_bar(val, max_day_val[k])]
        w.writerow(row)
    w.writerow([])

    # Images
    w.writerow(['IMAGES VS NO IMAGES'])
    img_header = ['']
    for k in all_keys:
        img_header += [f'{k} avg interaction', f'{k} chart']
    w.writerow(img_header)
    max_img_val = {k: max(
        all_results[k]['images']['with_image']['avg_interaction'],
        all_results[k]['images']['without_image']['avg_interaction'],
    ) or 1 for k in all_keys}
    for label, field in [('With image', 'with_image'), ('Without image', 'without_image')]:
        row = [label]
        for k in all_keys:
            val = all_results[k]['images'][field]['avg_interaction']
            row += [val, make_bar(val, max_img_val[k])]
        w.writerow(row)
    w.writerow(['Winner'] + [v for k in all_keys for v in [all_results[k]['images']['winner'], f"{all_results[k]['images']['pct_difference']}% better"]])
    w.writerow([])

    # Top keywords — ranked table with bar per account
    w.writerow(['TOP KEYWORDS BY AVG INTERACTION'])
    kw_header = ['Rank']
    for k in all_keys:
        kw_header += [f'{k} keyword', f'{k} avg', f'{k} chart']
    w.writerow(kw_header)
    max_kw_val = {k: max((r['avg_interaction'] for r in all_results[k].get('top_keywords', [])), default=1) for k in all_keys}
    max_rows = max(len(all_results[k].get('top_keywords', [])) for k in all_keys)
    for i in range(max_rows):
        row = [f'#{i+1}']
        for k in all_keys:
            kws = all_results[k].get('top_keywords', [])
            if i < len(kws):
                row += [kws[i]['keyword'], kws[i]['avg_interaction'], make_bar(kws[i]['avg_interaction'], max_kw_val[k])]
            else:
                row += ['', '', '']
        w.writerow(row)
    w.writerow([])

    # Top tweets per account
    w.writerow(['TOP 10 TWEETS PER ACCOUNT'])
    w.writerow(['Rank', 'Account', 'Interaction', 'Views', 'Likes', 'Retweets', 'Replies', 'Has Images', 'Keywords', 'Timestamp', 'URL', 'Text'])
    for k in all_keys:
        for t in all_results[k].get('top_tweets', []):
            w.writerow([f"#{t['rank']}", k, t['interaction'], t.get('views', ''), t['likes'], t['retweets'], t['replies'],
                        'yes' if t['has_images'] else 'no',
                        '; '.join(t['keywords']), t['timestamp'], t['url'], t['text']])
        w.writerow([])

print(f'\nMaster summary saved to analysis/summary.csv')

# Save combined JSON
json_out = os.path.join(OUTPUT_DIR, 'engagement_analysis.json')
with open(json_out, 'w') as f:
    # Remove raw tweets from JSON to keep it small
    for k in all_results:
        all_results[k].pop('tweets', None)
    json.dump(all_results, f, indent=2)
print(f'\nFull JSON saved to analysis/engagement_analysis.json')
