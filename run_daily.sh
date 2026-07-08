#!/bin/bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Library/Frameworks/Python.framework/Versions/3.10/bin:$PATH"
cd /Users/elainekao/TrendforceTwitterScraper

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily run..."

FAILURES=()

# Clear mention scraper cache so it does a fresh scrape each day
rm -f raw_tweets.json tf_reference.json

npm run scrape || { echo "[WARN] scrape failed"; FAILURES+=("mention scrape"); }

# Capture scrape:accounts output (while still streaming it to cron.log as
# before) so we can verify @TrendForce was actually attempted — checking
# "did the CSV change" isn't reliable, since a run with genuinely nothing
# new/updated for TrendForce in that window won't touch the file at all
# even though it scraped successfully.
ACCOUNTS_LOG=$(mktemp)
npm run scrape:accounts 2>&1 | tee "$ACCOUNTS_LOG"
ACCOUNTS_EXIT=${PIPESTATUS[0]:-$?}
if [ "$ACCOUNTS_EXIT" -ne 0 ]; then
  echo "[WARN] scrape:accounts failed"
  FAILURES+=("account scrape")
fi

if ! grep -q "@TrendForce: scraping recent tweets" "$ACCOUNTS_LOG" || grep -q "\[!\] @TrendForce failed" "$ACCOUNTS_LOG"; then
  echo "[WARN] @TrendForce wasn't successfully scraped this run — retrying it specifically..."
  node scrape_accounts.js @TrendForce
  if [ $? -ne 0 ]; then
    echo "[WARN] @TrendForce retry failed"
    FAILURES+=("TrendForce not scraped")
  fi
fi
rm -f "$ACCOUNTS_LOG"

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
