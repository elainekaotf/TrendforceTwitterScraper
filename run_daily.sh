#!/bin/bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Library/Frameworks/Python.framework/Versions/3.10/bin:$PATH"
cd /Users/elainekao/TrendforceTwitterScraper

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily run..."

FAILURES=()

# Clear mention scraper cache so it does a fresh scrape each day
rm -f raw_tweets.json tf_reference.json

npm run scrape || { echo "[WARN] scrape failed"; FAILURES+=("mention scrape"); }
npm run scrape:accounts || { echo "[WARN] scrape:accounts failed"; FAILURES+=("account scrape"); }
npm run scrape:watchlist || { echo "[WARN] scrape:watchlist failed"; FAILURES+=("watchlist scrape"); }
npm run scrape:competitors || { echo "[WARN] scrape:competitors failed"; FAILURES+=("competitor scrape"); }

# Update and publish the dashboard to GitHub Pages
# (publish.sh sends its own alert on CSV-validation/push/deploy failures)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running publish..."
bash /Users/elainekao/TrendforceTwitterScraper/publish.sh || { echo "[ERROR] publish failed"; FAILURES+=("publish"); }

if [ ${#FAILURES[@]} -gt 0 ]; then
  JOINED=$(IFS=', '; echo "${FAILURES[*]}")
  bash alert.sh "TrendForce Daily Run — Issues" "Steps that failed: ${JOINED}. Check cron.log."
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily run complete."
