"""
Reads analysis/engagement_analysis.json and writes docs/index.html.
Run after analyze_engagement.py. The docs/ folder is served via GitHub Pages.
"""
import json
import os
from datetime import datetime, timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(__file__)
JSON_FILE = os.path.join(BASE, 'analysis', 'engagement_analysis.json')
OUT_FILE  = os.path.join(BASE, 'docs', 'index.html')

os.makedirs(os.path.join(BASE, 'docs'), exist_ok=True)

with open(JSON_FILE, encoding='utf-8') as f:
    data = json.load(f)

FOLLOWER_HISTORY_FILE = os.path.join(BASE, 'follower_history.json')
follower_history = {}
if os.path.exists(FOLLOWER_HISTORY_FILE):
    with open(FOLLOWER_HISTORY_FILE, encoding='utf-8') as f:
        follower_history = json.load(f)

now_tw = datetime.now(TAIWAN_TZ).strftime('%B %d, %Y %H:%M Taiwan Time')

def js(val):
    return json.dumps(val, ensure_ascii=False)

def account_data(key):
    d = data[key]
    return dict(
        handle       = d['handle'],
        tweet_count  = d['tweet_count'],
        summary      = d['summary'],
        all_hours    = sorted(
                           sorted(d.get('all_hours', []), key=lambda x: x.get('tweet_count',0), reverse=True)[:12],
                           key=lambda x: x.get('hour', 0)
                       ),
        best_days    = sorted(d.get('best_days', []), key=lambda x: ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].index(x['day']) if x['day'] in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'] else 7),
        images       = d.get('images', {}),
        top_keywords = d.get('top_keywords', [])[:10],
        best_image_keywords = d.get('best_image_keywords', []),
        top_hashtags_by_interaction = d.get('top_hashtags_by_interaction', [])[:10],
        top_hashtags_by_usage       = d.get('top_hashtags_by_usage', [])[:10],
        top_tweets   = d.get('top_tweets', [])[:10],
        top_tweets_by_views = d.get('top_tweets_by_views', [])[:10],
        daily_top_tweets = d.get('daily_top_tweets', {}),
        language     = d.get('language'),
    )

# Ordered list of accounts to show — skip 'combined' key
ACCOUNT_ORDER = ['TrendForce', 'technews_tw', 'dylan522p', 'jukan05', 'QQ_Timmy', 'SemiAnalysis_']
accounts = [(k, account_data(k)) for k in ACCOUNT_ORDER if k in data]
# fallback: add any extra accounts in JSON not in the order list
for k in data:
    if k != 'combined' and k not in ACCOUNT_ORDER and isinstance(data[k], dict) and 'handle' in data[k]:
        accounts.append((k, account_data(k)))

def kpi_row(d):
    s = d['summary']
    return f"""
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Total Tweets</div><div class="kpi-value blue">{d['tweet_count']:,}</div></div>
      <div class="kpi"><div class="kpi-label">Avg Interaction</div><div class="kpi-value gold">{s['avg_interaction']}</div></div>
      <div class="kpi"><div class="kpi-label">Median Interaction</div><div class="kpi-value">{s['median_interaction']}</div></div>
      <div class="kpi"><div class="kpi-label">Max Interaction</div><div class="kpi-value green">{s['max_interaction']:,}</div></div>
      <div class="kpi"><div class="kpi-label">Avg Views</div><div class="kpi-value teal">{int(s.get('avg_views',0)):,}</div></div>
      <div class="kpi"><div class="kpi-label">Max Views</div><div class="kpi-value">{int(s.get('max_views',0)):,}</div></div>
    </div>"""

def mini_tweets(tweets):
    cards = []
    for t in tweets:
        original = str(t.get('text','')).replace('<','&lt;').replace('>','&gt;')
        short = original[:120] + ('...' if len(original) > 120 else '')
        cards.append(f'<div class="lang-tweet"><span class="num">{t["interaction"]:,}</span> &middot; {short}</div>')
    return '\n'.join(cards)

def lang_bars(pid, suffix, items, color, val_key, label_key, count_key=None):
    return f'<div id="{pid}-{suffix}" class="lang-bar-container" data-pid="{pid}" data-suffix="{suffix}"></div>'

def language_section(d, pid):
    lang = d.get('language')
    if not lang:
        return ''
    zh = lang.get('chinese', {})
    en = lang.get('english', {})
    zh_color = 'var(--gold)' if zh.get('avg_interaction',0) >= en.get('avg_interaction',0) else 'var(--muted)'
    en_color = 'var(--teal)' if en.get('avg_interaction',0) > zh.get('avg_interaction',0) else 'var(--muted)'

    zh_img_w = zh.get('img_with', {})
    zh_img_wo = zh.get('img_without', {})
    en_img_w = en.get('img_with', {})
    en_img_wo = en.get('img_without', {})

    return f"""
  <div class="section">
    <div class="section-title">Chinese vs English &mdash; Overview</div>
    <div class="img-compare">
      <div class="img-card">
        <div class="img-card-label">Chinese</div>
        <div class="img-card-val" style="color:{zh_color}">{zh.get('avg_interaction','')}</div>
        <div class="img-card-sub">avg interaction &middot; {zh.get('tweet_count','')} tweets</div>
        <div class="img-card-sub">avg views {int(zh.get('avg_views',0)):,}</div>
      </div>
      <div class="img-card">
        <div class="img-card-label">English</div>
        <div class="img-card-val" style="color:{en_color}">{en.get('avg_interaction','')}</div>
        <div class="img-card-sub">avg interaction &middot; {en.get('tweet_count','')} tweets</div>
        <div class="img-card-sub">avg views {int(en.get('avg_views',0)):,}</div>
      </div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Chinese &mdash; Best Hours</div>
      <div id="{pid}-zh-hours"></div>
    </div>
    <div class="section">
      <div class="section-title">English &mdash; Best Hours</div>
      <div id="{pid}-en-hours"></div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Chinese &mdash; Best Days</div>
      <div id="{pid}-zh-days"></div>
    </div>
    <div class="section">
      <div class="section-title">English &mdash; Best Days</div>
      <div id="{pid}-en-days"></div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Chinese &mdash; Images vs No Images</div>
      <div class="img-compare">
        <div class="img-card">
          <div class="img-card-label">With Image</div>
          <div class="img-card-val" style="color:var(--green)">{zh_img_w.get('avg','')}</div>
          <div class="img-card-sub">{zh_img_w.get('count','')} tweets</div>
        </div>
        <div class="img-card">
          <div class="img-card-label">No Image</div>
          <div class="img-card-val" style="color:var(--muted)">{zh_img_wo.get('avg','')}</div>
          <div class="img-card-sub">{zh_img_wo.get('count','')} tweets</div>
        </div>
      </div>
    </div>
    <div class="section">
      <div class="section-title">English &mdash; Images vs No Images</div>
      <div class="img-compare">
        <div class="img-card">
          <div class="img-card-label">With Image</div>
          <div class="img-card-val" style="color:var(--green)">{en_img_w.get('avg','')}</div>
          <div class="img-card-sub">{en_img_w.get('count','')} tweets</div>
        </div>
        <div class="img-card">
          <div class="img-card-label">No Image</div>
          <div class="img-card-val" style="color:var(--muted)">{en_img_wo.get('avg','')}</div>
          <div class="img-card-sub">{en_img_wo.get('count','')} tweets</div>
        </div>
      </div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Chinese &mdash; Top Hashtags</div>
      <div id="{pid}-zh-ht"></div>
    </div>
    <div class="section">
      <div class="section-title">English &mdash; Top Hashtags</div>
      <div id="{pid}-en-ht"></div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">Top Chinese Tweets</div>
      <div class="lang-tweets">{mini_tweets(zh.get('top_tweets',[]))}</div>
    </div>
    <div class="section">
      <div class="section-title">Top English Tweets</div>
      <div class="lang-tweets">{mini_tweets(en.get('top_tweets',[]))}</div>
    </div>
  </div>"""

def images_section(d):
    img = d['images']
    wi  = img.get('with_image', {})
    wo  = img.get('without_image', {})
    return f"""
      <div class="section">
        <div class="section-title">Images vs No Images</div>
        <div class="img-row">
          <div class="img-stat">
            <div class="img-stat-label">With Image</div>
            <div class="img-stat-val" style="color:var(--green)">{wi.get('avg_interaction','')}</div>
            <div class="img-stat-sub">{wi.get('count','')} tweets</div>
          </div>
          <div class="img-stat">
            <div class="img-stat-label">No Image</div>
            <div class="img-stat-val" style="color:var(--muted)">{wo.get('avg_interaction','')}</div>
            <div class="img-stat-sub">{wo.get('count','')} tweets</div>
          </div>
          <div class="img-stat">
            <div class="img-stat-label">Winner</div>
            <div class="img-stat-val" style="color:var(--blue);font-size:14px">{img.get('winner','').capitalize()}</div>
            <div class="img-stat-sub">{img.get('pct_difference','')}% better</div>
          </div>
        </div>
      </div>"""

def tweet_cards(tweets):
    cards = []
    for t in tweets:
        text = str(t.get('text','')).replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')[:200]
        if len(str(t.get('text',''))) > 200:
            text += '...'
        url = t.get('url','')
        cards.append(f"""
      <div class="tweet-card">
        <div class="tweet-rank">#{t['rank']}</div>
        <div class="tweet-stats">
          <div class="tweet-stat"><span class="num">{t['interaction']:,}</span><span class="lbl">total</span></div>
          <div class="tweet-stat"><span class="num">{t['likes']:,}</span><span class="lbl">likes</span></div>
          <div class="tweet-stat"><span class="num">{t['retweets']:,}</span><span class="lbl">retweets</span></div>
          <div class="tweet-stat"><span class="num">{t['replies']:,}</span><span class="lbl">replies</span></div>
          {'<div class="tweet-stat"><span class="num">' + f"{int(t.get('views',0)):,}" + '</span><span class="lbl">views</span></div>' if t.get('views') else ''}
        </div>
        <div class="tweet-text">{text}</div>
        <a class="tweet-link" href="{url}" target="_blank" rel="noopener">{url}</a>
      </div>""")
    return '\n'.join(cards)

def page(pid, d, active=''):
    handle = d['handle']
    hours  = d['all_hours']
    days   = d['best_days']
    kws    = d['top_keywords']
    hti    = d['top_hashtags_by_interaction']
    htu    = d['top_hashtags_by_usage']

    lang = d.get('language') or {}
    zh = lang.get('chinese', {})
    en = lang.get('english', {})

    no_hashtags = handle in ('dylan522p', 'jukan05', 'QQ_Timmy', 'SemiAnalysis_')
    hashtag_section_html = '' if no_hashtags else f"""<div class="two-col">
    <div class="section">
      <div class="section-title">Top Hashtags by Avg Interaction</div>
      <div id="{pid}-hti"></div>
    </div>
    <div class="section">
      <div class="section-title">Most Used Hashtags</div>
      <div id="{pid}-htu"></div>
    </div>
  </div>"""

    # Embed data as JS variables to avoid HTML attribute quoting issues
    data_script = f"""<script>
window._data = window._data || {{}};
window._data['{pid}'] = {{
  hours:    {js(hours)},
  days:     {js(days)},
  kws:      {js(kws)},
  kws_views: {js(sorted(kws, key=lambda x: x.get('avg_views', 0), reverse=True))},
  hti:      {js(hti)},
  htu:      {js(htu)},
  zh_hours: {js(zh.get('best_hours',[]))},
  en_hours: {js(en.get('best_hours',[]))},
  zh_days:  {js(zh.get('best_days',[]))},
  en_days:  {js(en.get('best_days',[]))},
  zh_ht:    {js(zh.get('top_hashtags',[]))},
  en_ht:    {js(en.get('top_hashtags',[]))},
  follower_history: {js(follower_history.get(handle, []))},
  daily_top_tweets: {js(d.get('daily_top_tweets', {}))}
}};
</script>"""

    return f"""
{data_script}
<div class="page {'active' if active else ''}" id="page-{pid}">
  <p class="updated">Based on {d['tweet_count']:,} tweets scraped from @{handle} &middot; Updated {now_tw}</p>
  {kpi_row(d)}
  <div class="section">
    <div class="section-title">Follower Growth</div>
    <canvas id="{pid}-followers" height="80" style="width:100%;max-width:100%"></canvas>
    <div id="{pid}-followers-note" style="font-size:10px;color:var(--muted);margin-top:4px"></div>
  </div>
  <div class="bar-legend"><span><span class="dot" style="background:var(--gold)"></span>Interaction</span><span><span class="dot" style="background:var(--blue)"></span>Views</span></div>
  <div class="two-col">
    <div class="section">
      <div class="section-title">Best Hours to Post (Taiwan Time)</div>
      <div id="{pid}-hours"></div>
    </div>
    <div class="section">
      <div class="section-title">Avg Interaction &amp; Views by Day</div>
      <div id="{pid}-days"></div>
    </div>
  </div>
  {images_section(d)}
  <div class="two-col">
    <div class="section">
      <div class="section-title">Top Topics by Avg Interaction</div>
      <div id="{pid}-kws"></div>
    </div>
    <div class="section">
      <div class="section-title">Top Topics by Avg Views</div>
      <div id="{pid}-kws-views"></div>
    </div>
  </div>
  {hashtag_section_html}
  {language_section(d, pid) if d.get('language') and d['handle'] == 'technews_tw' else ''}
  <div class="section">
    <div class="section-title">Top 3 Tweets by Day</div>
    <select class="day-picker" id="{pid}-daypicker" onchange="renderDailyTop('{pid}')"></select>
    <div id="{pid}-daily-tweets" style="margin-top:14px"></div>
  </div>
  <div class="two-col">
    <div class="section">
      <div class="section-title">Top 10 Tweets by Interaction</div>
      {tweet_cards(d['top_tweets'])}
    </div>
    <div class="section">
      <div class="section-title">Top 10 Tweets by Views</div>
      {tweet_cards(d['top_tweets_by_views']) if d['top_tweets_by_views'] else '<div style="color:var(--muted);font-size:12px;padding:8px">No view data available yet</div>'}
    </div>
  </div>
</div>"""

def pid_for(key):
    return key.lower().replace('_', '')

tabs_html = ''.join([
    f'<div class="tab{" active" if i==0 else ""}" onclick="switchTab(\'{pid_for(k)}\',this)">@{d["handle"]}</div>'
    for i, (k, d) in enumerate(accounts)
])
pages_html = ''.join([
    page(pid_for(k), d, active='active' if i == 0 else '')
    for i, (k, d) in enumerate(accounts)
])

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X Analytics Dashboard &mdash; TrendForce Research</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0d1117;--surface:#161b22;--border:#21262d;--muted:#8b949e;
  --text:#e6edf3;--blue:#3b9eff;--teal:#26c6da;--gold:#f0b429;
  --green:#3fb950;--red:#f85149;
  --mono:'SF Mono','Fira Code','Cascadia Code',monospace;
  --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;min-height:100vh}}
.header{{border-bottom:1px solid var(--border);padding:20px 32px 0;display:flex;align-items:flex-end;gap:32px;position:sticky;top:0;background:rgba(13,17,23,.92);backdrop-filter:blur(8px);z-index:10}}
.logo{{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding-bottom:18px;white-space:nowrap}}
.logo span{{color:var(--blue)}}
.tabs{{display:flex;gap:0}}
.tab{{padding:10px 22px 14px;font-size:13px;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;white-space:nowrap;user-select:none}}
.tab:hover{{color:var(--text)}}
.tab.active{{color:var(--text);border-color:var(--blue)}}
.page{{display:none;padding:32px;max-width:1200px;margin:0 auto}}
.page.active{{display:block}}
.kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px 18px}}
.kpi-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}}
.kpi-value{{font-family:var(--mono);font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--text)}}
.kpi-value.blue{{color:var(--blue)}}.kpi-value.gold{{color:var(--gold)}}.kpi-value.green{{color:var(--green)}}.kpi-value.teal{{color:var(--teal)}}
.section{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px 22px;margin-bottom:16px}}
.section-title{{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:16px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
@media(max-width:700px){{.two-col{{grid-template-columns:1fr}}}}
.bar-row{{display:flex;align-items:center;gap:10px;margin-bottom:4px;font-size:12px}}
.bar-label{{width:110px;color:var(--muted);text-align:right;flex-shrink:0;font-family:var(--mono);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-label.left{{text-align:left;width:200px}}
.bar-track{{flex:1;height:4px;background:var(--border);border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px;background:var(--blue);transition:width .4s ease}}
.bar-fill.gold{{background:var(--gold)}}.bar-fill.teal{{background:var(--teal)}}.bar-fill.green{{background:var(--green)}}.bar-fill.blue{{background:#1a6fd4}}
.bar-val{{font-family:var(--mono);font-size:11px;color:var(--text);min-width:42px;font-variant-numeric:tabular-nums}}
.bar-count{{font-family:var(--mono);font-size:10px;color:var(--muted);min-width:60px}}
.bar-group{{margin-bottom:5px}}
.bar-group-highlight{{background:rgba(255,255,255,0.04);border-radius:5px;padding:3px 6px;margin-left:-6px}}
.bar-row-views{{margin-top:2px;opacity:.65}}
.bar-row-best-interact{{opacity:1}}
.bar-row-best-views{{opacity:1}}
.bar-fill-best{{filter:brightness(1.25)}}
.best-badge{{font-size:9px;font-weight:700;color:var(--gold);margin-left:4px;letter-spacing:0.03em}}
.best-badge-views{{color:#5baeff}}
.views-val{{font-family:var(--mono);font-size:10px;color:var(--blue);min-width:42px}}
.bar-metric{{font-size:9px;color:var(--muted);min-width:44px;font-family:var(--mono);opacity:.7}}
.bar-legend{{display:flex;gap:16px;margin-bottom:10px;font-size:11px;color:var(--muted)}}
.bar-legend span{{display:flex;align-items:center;gap:5px}}
.dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.img-compare{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.img-card{{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:14px;text-align:center}}
.img-card-label{{font-size:11px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.07em}}
.img-card-val{{font-family:var(--mono);font-size:26px;font-weight:700}}
.img-card-sub{{font-size:11px;color:var(--muted);margin-top:4px}}
.img-winner{{margin-top:12px;font-size:12px;color:var(--green);text-align:center}}
.img-row{{display:flex;gap:16px;align-items:flex-start}}
.img-stat{{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 12px;text-align:center}}
.img-stat-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px}}
.img-stat-val{{font-family:var(--mono);font-size:20px;font-weight:700}}
.img-stat-sub{{font-size:10px;color:var(--muted);margin-top:3px}}
.tweet-card{{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:14px 16px;margin-bottom:10px}}
.tweet-rank{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:6px}}
.tweet-stats{{display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap}}
.tweet-stat{{font-family:var(--mono);font-size:12px}}
.tweet-stat .num{{color:var(--blue);font-weight:600}}
.tweet-stat .lbl{{color:var(--muted);font-size:10px;margin-left:2px}}
.tweet-text{{font-size:13px;color:var(--text);line-height:1.5;margin-bottom:8px}}
.tweet-link{{font-size:11px;color:var(--blue);text-decoration:none;word-break:break-all}}
.tweet-link:hover{{text-decoration:underline}}
.updated{{font-size:11px;color:var(--muted);margin-bottom:24px}}
.lang-tweet{{font-size:12px;color:var(--text);padding:6px 0;border-bottom:1px solid var(--border);line-height:1.5}}
.lang-tweet:last-child{{border-bottom:none}}
.lang-tweet .num{{color:var(--blue);font-family:var(--mono);font-weight:600}}
.lang-translated{{font-size:11px;color:var(--muted);margin-top:2px;font-style:italic}}
.day-picker{{background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-family:var(--mono);font-size:13px;cursor:pointer;min-width:160px}}
.day-picker:focus{{outline:1px solid var(--blue)}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">X Analytics &middot; <span>TrendForce Research</span></div>
  <div class="tabs">
    {tabs_html}
  </div>
</div>

{pages_html}

<script>
function switchTab(id, el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-' + id).classList.add('active');
}}

function renderBars(pid, key, color, valKey, labelKey, opts) {{
  opts = opts || {{}};
  const el = document.getElementById(pid + '-' + key);
  if (!el) return;
  const dataKey = key.replace(/-/g, '_');
  const items = (window._data[pid] || {{}})[dataKey] || [];
  const viewKey = opts.viewKey || 'avg_views';
  const isLeft = labelKey === 'hashtag' || labelKey === 'keyword';

  const maxI = Math.max(...items.map(i => +i[valKey] || 0), 1);
  const maxV = Math.max(...items.map(i => +i[viewKey] || 0), 1);
  const isTimeDayChart = key === 'hours' || key === 'days' || key.endsWith('-hours') || key.endsWith('-days');
  const bestIVal = isTimeDayChart ? maxI : null;
  const bestVVal = isTimeDayChart ? maxV : null;

  items.forEach(item => {{
    const label = labelKey === 'hour'
      ? String(item.hour).padStart(2,'0') + ':00'
      : String(item[labelKey] || '');
    const val  = +item[valKey]  || 0;
    const views = +item[viewKey] || 0;
    const pctI = (val   / maxI * 100).toFixed(1);
    const pctV = (views / maxV * 100).toFixed(1);
    const countStr = opts.countKey
      ? `<div class="bar-count">${{item[opts.countKey] != null ? item[opts.countKey] + ' tweets' : ''}}</div>`
      : '';

    const isBestI = isTimeDayChart && val === bestIVal;
    const isBestV = isTimeDayChart && views === bestVVal;

    const div = document.createElement('div');
    div.className = 'bar-group';
    if (isBestI || isBestV) div.classList.add('bar-group-highlight');
    const viewsStr = views >= 1000 ? (views/1000).toFixed(1)+'K' : views;
    const bestIBadge = isBestI ? ' <span class="best-badge">★ interactions</span>' : '';
    const bestVBadge = isBestV ? ' <span class="best-badge best-badge-views">★ views</span>' : '';
    const secondRow = opts.dualBar !== false ? `
      <div class="bar-row bar-row-views${{isBestV?' bar-row-best-views':''}}">
        <div class="bar-label ${{isLeft?'left':''}}"></div>
        <div class="bar-track"><div class="bar-fill blue${{isBestV?' bar-fill-best':''}}" style="width:${{pctV}}%"></div></div>
        <div class="bar-val views-val">${{viewsStr}}${{bestVBadge}}</div>
        <div class="bar-metric">views</div>
      </div>` : '';
    div.innerHTML = `
      <div class="bar-row${{isBestI?' bar-row-best-interact':''}}">
        <div class="bar-label ${{isLeft?'left':''}}">${{label}}</div>
        <div class="bar-track"><div class="bar-fill ${{color}}${{isBestI?' bar-fill-best':''}}" style="width:${{pctI}}%"></div></div>
        <div class="bar-val">${{val}}${{bestIBadge}}</div>
        <div class="bar-metric">${{valKey==='avg_views'?'views':'interact'}}</div>
        ${{countStr}}
      </div>
      ${{secondRow}}`;
    el.appendChild(div);
  }});
}}

function renderFollowerChart(pid) {{
  const data = ((window._data[pid] || {{}}).follower_history || []);
  const canvas = document.getElementById(pid + '-followers');
  const note = document.getElementById(pid + '-followers-note');
  if (!canvas) return;
  if (data.length < 2) {{
    canvas.style.display = 'none';
    if (note) note.textContent = data.length === 1
      ? 'Tracking started ' + data[0].date + ' — check back tomorrow for a trend line.'
      : 'No follower data yet — will appear after the first daily scrape.';
    return;
  }}
  const W = canvas.offsetWidth || 800, H = canvas.height;
  canvas.width = W;
  const ctx = canvas.getContext('2d');
  const counts = data.map(d => d.followers);
  const minC = Math.min(...counts), maxC = Math.max(...counts);
  const pad = {{ l: 60, r: 16, t: 12, b: 28 }};
  const gw = W - pad.l - pad.r, gh = H - pad.t - pad.b;
  const range = maxC - minC || 1;

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1;
  [0, 0.25, 0.5, 0.75, 1].forEach(f => {{
    const y = pad.t + gh * (1 - f);
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + gw, y); ctx.stroke();
    const val = Math.round(minC + range * f);
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.font = '10px monospace'; ctx.textAlign = 'right';
    ctx.fillText(val >= 1000 ? (val/1000).toFixed(1)+'K' : val, pad.l - 4, y + 3);
  }});

  // Line + fill
  const pts = data.map((d, i) => ({{
    x: pad.l + (i / (data.length - 1)) * gw,
    y: pad.t + gh * (1 - (d.followers - minC) / range)
  }}));
  ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
  pts.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = '#5baeff'; ctx.lineWidth = 2; ctx.stroke();

  // Fill under line
  ctx.lineTo(pts[pts.length-1].x, pad.t + gh);
  ctx.lineTo(pts[0].x, pad.t + gh);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + gh);
  grad.addColorStop(0, 'rgba(91,174,255,0.25)'); grad.addColorStop(1, 'rgba(91,174,255,0)');
  ctx.fillStyle = grad; ctx.fill();

  // Dots + date labels
  ctx.fillStyle = '#5baeff';
  const step = Math.max(1, Math.floor(data.length / 8));
  pts.forEach((p, i) => {{
    ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI*2); ctx.fill();
    if (i % step === 0 || i === data.length - 1) {{
      ctx.fillStyle = 'rgba(255,255,255,0.4)'; ctx.font = '9px monospace'; ctx.textAlign = 'center';
      ctx.fillText(data[i].date.slice(5), p.x, pad.t + gh + 14);
      ctx.fillStyle = '#5baeff';
    }}
  }});

  // Latest count label
  const last = pts[pts.length - 1];
  ctx.fillStyle = '#fff'; ctx.font = 'bold 11px monospace'; ctx.textAlign = 'left';
  ctx.fillText(counts[counts.length-1].toLocaleString(), last.x + 6, last.y + 4);
}}

function tweetCardHtml(t) {{
  const esc = s => String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  let text = esc(t.text).slice(0, 200);
  if (String(t.text || '').length > 200) text += '...';
  const viewsStat = t.views ? `<div class="tweet-stat"><span class="num">${{Number(t.views).toLocaleString()}}</span><span class="lbl">views</span></div>` : '';
  return `
      <div class="tweet-card">
        <div class="tweet-rank">#${{t.rank}}</div>
        <div class="tweet-stats">
          <div class="tweet-stat"><span class="num">${{Number(t.interaction).toLocaleString()}}</span><span class="lbl">total</span></div>
          <div class="tweet-stat"><span class="num">${{Number(t.likes).toLocaleString()}}</span><span class="lbl">likes</span></div>
          <div class="tweet-stat"><span class="num">${{Number(t.retweets).toLocaleString()}}</span><span class="lbl">retweets</span></div>
          <div class="tweet-stat"><span class="num">${{Number(t.replies).toLocaleString()}}</span><span class="lbl">replies</span></div>
          ${{viewsStat}}
        </div>
        <div class="tweet-text">${{text}}</div>
        <a class="tweet-link" href="${{t.url}}" target="_blank" rel="noopener">${{t.url}}</a>
      </div>`;
}}

function populateDayPicker(pid) {{
  const sel = document.getElementById(pid + '-daypicker');
  if (!sel) return;
  const daily = (window._data[pid] || {{}}).daily_top_tweets || {{}};
  const days = Object.keys(daily).sort().reverse();
  if (!days.length) {{
    sel.innerHTML = '<option>No data yet</option>';
    sel.disabled = true;
    return;
  }}
  sel.innerHTML = days.map(d => `<option value="${{d}}">${{d}}</option>`).join('');
  renderDailyTop(pid);
}}

function renderDailyTop(pid) {{
  const sel = document.getElementById(pid + '-daypicker');
  const container = document.getElementById(pid + '-daily-tweets');
  if (!sel || !container) return;
  const daily = (window._data[pid] || {{}}).daily_top_tweets || {{}};
  const tweets = daily[sel.value] || [];
  container.innerHTML = tweets.length
    ? tweets.map(tweetCardHtml).join('')
    : '<div style="color:var(--muted);font-size:12px;padding:8px">No tweets for this day.</div>';
}}

{js([pid_for(k) for k, _ in accounts])}.forEach(pid => {{
  renderFollowerChart(pid);
  populateDayPicker(pid);
  renderBars(pid, 'hours',    'gold',  'avg_interaction', 'hour',    {{countKey:'tweet_count'}});
  renderBars(pid, 'days',     '',      'avg_interaction', 'day',     {{}});
  renderBars(pid, 'kws',       'teal',  'avg_interaction', 'keyword', {{countKey:'tweet_count', dualBar:false}});
  renderBars(pid, 'kws-views', 'blue',  'avg_views',       'keyword', {{countKey:'tweet_count', dualBar:false}});
  renderBars(pid, 'hti',      '',      'avg_interaction', 'hashtag', {{countKey:'tweet_count'}});
  renderBars(pid, 'htu',      'green', 'tweet_count',     'hashtag', {{}});
  renderBars(pid, 'zh-hours', 'gold',  'avg_interaction', 'hour',    {{countKey:'tweet_count'}});
  renderBars(pid, 'en-hours', 'teal',  'avg_interaction', 'hour',    {{countKey:'tweet_count'}});
  renderBars(pid, 'zh-days',  'gold',  'avg_interaction', 'day',     {{}});
  renderBars(pid, 'en-days',  'teal',  'avg_interaction', 'day',     {{}});
  renderBars(pid, 'zh-ht',    'gold',  'avg_interaction', 'hashtag', {{countKey:'tweet_count'}});
  renderBars(pid, 'en-ht',    'teal',  'avg_interaction', 'hashtag', {{countKey:'tweet_count'}});
}});
</script>
</body>
</html>"""

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Dashboard written to docs/index.html  ({len(html):,} bytes)')
print(f'Updated: {now_tw}')
