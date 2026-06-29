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

now_tw = datetime.now(TAIWAN_TZ).strftime('%B %d, %Y %H:%M Taiwan Time')

def js(val):
    return json.dumps(val, ensure_ascii=False)

def account_data(key):
    d = data[key]
    return dict(
        handle       = d['handle'],
        tweet_count  = d['tweet_count'],
        summary      = d['summary'],
        all_hours    = d.get('all_hours', []),
        best_days    = d.get('best_days', []),
        images       = d.get('images', {}),
        top_keywords = d.get('top_keywords', [])[:10],
        best_image_keywords = d.get('best_image_keywords', []),
        top_hashtags_by_interaction = d.get('top_hashtags_by_interaction', [])[:10],
        top_hashtags_by_usage       = d.get('top_hashtags_by_usage', [])[:10],
        top_tweets   = d.get('top_tweets', [])[:10],
    )

tf = account_data('TrendForce')
tn = account_data('technews_tw')

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

def images_section(d):
    img = d['images']
    wi  = img.get('with_image', {})
    wo  = img.get('without_image', {})
    return f"""
      <div class="section">
        <div class="section-title">Images vs No Images</div>
        <div class="img-compare">
          <div class="img-card">
            <div class="img-card-label">With Image</div>
            <div class="img-card-val" style="color:var(--green)">{wi.get('avg_interaction','')}</div>
            <div class="img-card-sub">avg interaction &middot; {wi.get('count','')} tweets</div>
          </div>
          <div class="img-card">
            <div class="img-card-label">Without Image</div>
            <div class="img-card-val" style="color:var(--muted)">{wo.get('avg_interaction','')}</div>
            <div class="img-card-sub">avg interaction &middot; {wo.get('count','')} tweets</div>
          </div>
        </div>
        <div class="img-winner">{img.get('winner','').capitalize()} perform {img.get('pct_difference','')}% better</div>
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
          <div class="tweet-stat"><span class="num">{int(t.get('views',0)):,}</span><span class="lbl">views</span></div>
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

    return f"""
<div class="page {'active' if active else ''}" id="page-{pid}">
  <p class="updated">Based on {d['tweet_count']:,} tweets scraped from @{handle} &middot; Updated {now_tw}</p>
  {kpi_row(d)}
  <div class="two-col">
    <div class="section">
      <div class="section-title">Best Hours to Post (Taiwan Time)</div>
      <div id="{pid}-hours" data-items='{js(hours)}' data-color="gold" data-val="avg_interaction" data-count="tweet_count" data-label="hour_label"></div>
    </div>
    <div class="section">
      <div class="section-title">Avg Interaction by Day</div>
      <div id="{pid}-days" data-items='{js(days)}' data-color="" data-val="avg_interaction" data-label="day"></div>
    </div>
  </div>
  <div class="two-col">
    {images_section(d)}
    <div class="section">
      <div class="section-title">Top Keywords by Avg Interaction</div>
      <div id="{pid}-kws" data-items='{js(kws)}' data-color="teal" data-val="avg_interaction" data-count="tweet_count" data-label="keyword"></div>
    </div>
  </div>
  <div class="two-col">
    <div class="section">
      <div class="section-title">Top Hashtags by Avg Interaction</div>
      <div id="{pid}-hti" data-items='{js(hti)}' data-color="" data-val="avg_interaction" data-count="tweet_count" data-label="hashtag"></div>
    </div>
    <div class="section">
      <div class="section-title">Most Used Hashtags</div>
      <div id="{pid}-htu" data-items='{js(htu)}' data-color="green" data-val="tweet_count" data-count2="avg_interaction" data-label="hashtag"></div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Top 10 Tweets by Interaction</div>
    {tweet_cards(d['top_tweets'])}
  </div>
</div>"""

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
.bar-row{{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:12px}}
.bar-label{{width:110px;color:var(--muted);text-align:right;flex-shrink:0;font-family:var(--mono);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-label.left{{text-align:left;width:140px}}
.bar-track{{flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px;background:var(--blue);transition:width .4s ease}}
.bar-fill.gold{{background:var(--gold)}}.bar-fill.teal{{background:var(--teal)}}.bar-fill.green{{background:var(--green)}}
.bar-val{{font-family:var(--mono);font-size:11px;color:var(--text);min-width:42px;font-variant-numeric:tabular-nums}}
.bar-count{{font-family:var(--mono);font-size:10px;color:var(--muted);min-width:60px}}
.img-compare{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.img-card{{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:14px;text-align:center}}
.img-card-label{{font-size:11px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.07em}}
.img-card-val{{font-family:var(--mono);font-size:26px;font-weight:700}}
.img-card-sub{{font-size:11px;color:var(--muted);margin-top:4px}}
.img-winner{{margin-top:12px;font-size:12px;color:var(--green);text-align:center}}
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
</style>
</head>
<body>

<div class="header">
  <div class="logo">X Analytics &middot; <span>TrendForce Research</span></div>
  <div class="tabs">
    <div class="tab active" onclick="switchTab('tf',this)">@TrendForce</div>
    <div class="tab" onclick="switchTab('tn',this)">@technews_tw</div>
  </div>
</div>

{page('tf', tf, active='active')}
{page('tn', tn)}

<script>
function switchTab(id, el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-' + id).classList.add('active');
}}

function renderBars(containerId) {{
  const el = document.getElementById(containerId);
  if (!el) return;
  const items   = JSON.parse(el.dataset.items || '[]');
  const color   = el.dataset.color || '';
  const valKey  = el.dataset.val;
  const countKey= el.dataset.count;
  const count2  = el.dataset.count2;
  const labelKey= el.dataset.label;
  const max = Math.max(...items.map(i => +i[valKey] || 0)) || 1;

  items.forEach(item => {{
    const label = labelKey === 'hour_label'
      ? String(item.hour).padStart(2,'0') + ':00'
      : (item[labelKey] || '');
    const val = +item[valKey] || 0;
    const pct = (val / max * 100).toFixed(1);
    const countStr = countKey
      ? `<div class="bar-count">${{item[countKey] ? item[countKey] + (countKey==='tweet_count'?' tweets':'') : ''}}</div>`
      : (count2 ? `<div class="bar-count">avg ${{item[count2]}}</div>` : '');

    const div = document.createElement('div');
    div.className = 'bar-row';
    div.innerHTML = `
      <div class="bar-label ${{labelKey==='hashtag'||labelKey==='keyword'?'left':''}}">${{label}}</div>
      <div class="bar-track"><div class="bar-fill ${{color}}" style="width:${{pct}}%"></div></div>
      <div class="bar-val">${{val}}</div>
      ${{countStr}}
    `;
    el.appendChild(div);
  }});
}}

['tf-hours','tf-days','tf-kws','tf-hti','tf-htu',
 'tn-hours','tn-days','tn-kws','tn-hti','tn-htu'].forEach(renderBars);
</script>
</body>
</html>"""

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Dashboard written to docs/index.html  ({len(html):,} bytes)')
print(f'Updated: {now_tw}')
