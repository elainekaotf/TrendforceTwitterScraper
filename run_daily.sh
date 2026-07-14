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

# TrendForceDash runs on its own independent schedule (0/4/6/8/12/16/18/20),
# not this repo's :30-past-the-hour schedule - a fresh scrape here could sit
# unsynced for hours until TrendForceDash's own next scheduled run. Sync and
# push it immediately after every run here instead of waiting.
#
# Backgrounded (not awaited): trendforce-daily is a single launchd Label with
# a fixed StartCalendarInterval (0:30/4:30/8:30/...) - launchd does NOT queue
# a missed firing while the previous instance of the same Label is still
# running, it just skips it. This chained sync occasionally took several
# hours (observed 2026-07-14: a run starting 00:44 didn't finish until
# ~09:32), which silently ate the 4:30 AND 8:30 firings entirely - nothing
# re-scraped tphuang (or anyone else) for ~9 hours, purely because this
# script itself hadn't returned yet. Running it detached lets run_daily.sh
# (and therefore the next scheduled scrape) finish on time regardless of how
# long the sync takes. run_pipeline.sh has its own independent
# FAILURES/alert.sh handling and logs to TrendForceDash/pipeline.log, so
# nothing here needs to wait for or re-check its result.
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing TrendForceDash (backgrounded)..."
nohup bash -c '
  bash /Users/elainekao/TrendForceDash/run_pipeline.sh core
  bash /Users/elainekao/TrendForceDash/run_pipeline.sh accounts
' >> /Users/elainekao/TrendForceDash/pipeline.log 2>&1 &
disown

if [ ${#FAILURES[@]} -gt 0 ]; then
  JOINED=$(IFS=', '; echo "${FAILURES[*]}")
  bash alert.sh "TrendForce Daily Run — Issues" "Steps that failed: ${JOINED}. Check cron.log."
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily run complete."
