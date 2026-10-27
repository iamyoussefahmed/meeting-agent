#!/bin/sh
# Runs the calendar watcher and restarts it if it stops, logging to data/watcher.log.
# Used on Windows (inside WSL), where there is no LaunchAgent; see
# infra/install_watcher_windows.ps1. On a Mac, use infra/install_watcher.sh instead.
cd "$(dirname "$0")/.." || exit 1
mkdir -p data

# Only one watcher at a time, or every meeting would get two bots.
if pgrep -f "meeting_agent watch" >/dev/null; then
  echo "Watcher is already running."
  exit 0
fi

while true; do
  .venv/bin/python -m meeting_agent watch >> data/watcher.log 2>&1
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] watcher stopped; restarting in 30s" >> data/watcher.log
  sleep 30
done
