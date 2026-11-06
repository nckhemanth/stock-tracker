#!/bin/bash
# Stock Tracker auto-refresh cron script
# Runs the pipeline and pushes to GitHub Pages

set -e

PROJECT="/Users/hemanth/Learn/Trading/my-patterns/stock-tracker"
PYTHON="/Users/hemanth/.pyenv/versions/3.10.13/bin/python3"
LOG="$PROJECT/data/cron.log"

cd "$PROJECT"

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting refresh..." >> "$LOG"

# Run the pipeline
$PYTHON -u run.py --force >> "$LOG" 2>&1

# Push to GitHub
/usr/bin/git -C "$PROJECT" add docs/ data/ >> "$LOG" 2>&1
/usr/bin/git -C "$PROJECT" diff --cached --quiet && echo "$(date) No changes" >> "$LOG" || {
  /usr/bin/git -C "$PROJECT" commit -m "Refresh $(date -u '+%Y-%m-%dT%H:%M')" >> "$LOG" 2>&1
  /usr/bin/git -C "$PROJECT" push >> "$LOG" 2>&1
}

echo "$(date '+%Y-%m-%d %H:%M:%S') Done." >> "$LOG"
echo "---" >> "$LOG"
