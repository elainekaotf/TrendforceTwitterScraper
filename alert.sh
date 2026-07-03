#!/bin/bash
# Usage: bash alert.sh "Title" "Message body"
# Fires a native macOS notification so failures don't just sit silently in
# cron.log until someone happens to check. Safe to call from any script;
# never fails the caller even if notifications are unavailable (e.g. no GUI
# session attached, which can happen for a cron job on some setups).

TITLE="${1:-TrendForce Scraper}"
MESSAGE="${2:-Something went wrong.}"

osascript -e "display notification \"${MESSAGE//\"/\\\"}\" with title \"${TITLE//\"/\\\"}\" sound name \"Basso\"" 2>/dev/null || true

# Optional secondary channels — uncomment and configure if you want redundancy
# beyond the desktop notification (e.g. so you notice even if the Mac is asleep
# or you're away from it):
#
# Email (requires `mail` configured, e.g. via `brew install msmtp` + a relay):
# echo "$MESSAGE" | mail -s "$TITLE" you@example.com
#
# Slack (requires a webhook URL — store it in an env var, not in this file):
# curl -s -X POST -H 'Content-type: application/json' \
#   --data "{\"text\":\"*$TITLE*\n$MESSAGE\"}" \
#   "$SLACK_WEBHOOK_URL" >/dev/null
