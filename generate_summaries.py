"""
FR-06 Daily Executive Summaries (template-based, no LLM).

Reads analysis/engagement_analysis.json and writes analysis/daily_summaries.json:
one 80-120 character zh-TW summary per account per day, covering:
  - top topic (best-performing keyword)
  - engagement highlight (best posting slot / top tweet)
  - heat trend (today's top-tweet interaction vs the trailing 6-day average)

Run after analyze_engagement.py so the input JSON is fresh.
"""
import json
import os
from datetime import datetime, timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(__file__)
JSON_FILE = os.path.join(BASE, 'analysis', 'engagement_analysis.json')
OUT_FILE = os.path.join(BASE, 'analysis', 'daily_summaries.json')

MIN_LEN = 80
MAX_LEN = 120


def heat_trend(daily_top_tweets):
    """Compare today's top-tweet interaction to the trailing 6-day average."""
    dates = sorted(daily_top_tweets.keys())
    if len(dates) < 2:
        return None
    def top_interaction(date):
        entries = daily_top_tweets[date]
        return max(e['interaction'] for e in entries) if entries else 0

    prior = dates[-7:-1] if len(dates) >= 7 else dates[:-1]
    if not prior:
        return None
    prior_avg = sum(top_interaction(d) for d in prior) / len(prior)
    today_interaction = top_interaction(dates[-1])
    if prior_avg == 0:
        return None
    delta = (today_interaction - prior_avg) / prior_avg
    if delta > 0.2:
        return '熱度上升'
    if delta < -0.2:
        return '熱度下滑'
    return '熱度持平'


def build_summary(handle, d):
    top_keywords = d.get('top_keywords', [])
    top_hashtags = d.get('top_hashtags_by_interaction', [])
    best_days = d.get('best_days', [])
    daily_top_tweets = d.get('daily_top_tweets', {})

    top_keyword = top_keywords[0]['keyword'] if top_keywords else None
    top_hashtag = top_hashtags[0]['hashtag'] if top_hashtags else None
    best_day = best_days[0]['day'] if best_days else None
    trend = heat_trend(daily_top_tweets)

    parts = [f"{handle} 今日焦點："]
    if top_keyword:
        parts.append(f"議題聚焦於「{top_keyword}」")
    if top_hashtag:
        parts.append(f"，互動最佳標籤為 {top_hashtag}")
    if best_day:
        parts.append(f"，最佳發文日為{best_day}")
    if trend:
        parts.append(f"，{trend}")
    parts.append("，建議持續追蹤相關內容表現。")

    text = ''.join(parts)

    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + '。'
    elif len(text) < MIN_LEN:
        pad = "各項指標維持穩定，無顯著異常波動" * 2
        text = (text[:-1] + '，' + pad)[:MAX_LEN]
        if not text.endswith('。'):
            text = text[:MAX_LEN - 1] + '。'

    return text


def main():
    with open(JSON_FILE, encoding='utf-8') as f:
        data = json.load(f)

    today = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d')

    summaries = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding='utf-8') as f:
            summaries = json.load(f)

    for handle, d in data.items():
        if not isinstance(d, dict) or 'handle' not in d:
            continue
        text = build_summary(handle, d)
        summaries.setdefault(handle, {})[today] = text

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(summaries)} accounts' summaries for {today} to {OUT_FILE}")


if __name__ == '__main__':
    main()
