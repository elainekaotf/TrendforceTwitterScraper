#!/bin/bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Library/Frameworks/Python.framework/Versions/3.10/bin:$PATH"
cd /Users/elainekao/TrendforceTwitterScraper

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily run..."

npm run scrape || echo "[WARN] scrape failed"
npm run scrape:accounts || echo "[WARN] scrape:accounts failed"
npm run scrape:watchlist || echo "[WARN] scrape:watchlist failed"
npm run scrape:competitors || echo "[WARN] scrape:competitors failed"

# RSS citation crawler — no browser needed, runs fast
node /Users/elainekao/google-citations/rss-crawler.js || echo "[WARN] rss-crawler failed"

# Update and publish the dashboard to GitHub Pages
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running publish..."
bash /Users/elainekao/TrendforceTwitterScraper/publish.sh || echo "[ERROR] publish failed"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily run complete."
