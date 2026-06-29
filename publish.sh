#!/bin/bash
# Run weekly: generates docs/index.html from latest analysis, then pushes to GitHub Pages.
# Cron example (every Monday 9:30 AM Taiwan = 01:30 UTC):
#   30 1 * * 1 /Users/elainekao/TrendforceTwitterScraper/publish.sh >> /tmp/publish.log 2>&1

set -e
cd "$(dirname "$0")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting publish..."

# 1. Re-run engagement analysis so the JSON is fresh
python3 analyze_engagement.py

# 2. Generate docs/index.html from the JSON
python3 generate_dashboard.py

# 3. Stage and commit only the dashboard HTML
git add docs/index.html
if git diff --cached --quiet; then
  echo "Nothing changed in docs/index.html, skipping push."
  exit 0
fi

git commit -m "Weekly dashboard update $(date '+%Y-%m-%d')"
git push

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. Dashboard pushed to GitHub Pages."
