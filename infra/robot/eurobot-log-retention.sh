#!/bin/bash
# Keep /home/share/eurobot/logs bounded: drop files older than RETENTION_DAYS, then the
# oldest files until the total is below MAX_GB. Files written in the last
# KEEP_RECENT_MIN minutes are never touched (a running container appends there).
set -euo pipefail

conf="${EUROBOT_LOGGING_ENV:-/home/share/eurobot/config/logging.env}"
# shellcheck disable=SC1090
[[ -r "$conf" ]] && source "$conf"
LOG_ROOT="${LOG_ROOT:-/home/share/eurobot/logs}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
MAX_GB="${MAX_GB:-100}"
KEEP_RECENT_MIN="${KEEP_RECENT_MIN:-60}"
max_bytes="${MAX_BYTES:-$((MAX_GB * 1024 * 1024 * 1024))}"

[[ -d "$LOG_ROOT" ]] || { echo "no $LOG_ROOT, nothing to do"; exit 0; }

old=$(find "$LOG_ROOT" -type f -mmin +$((RETENTION_DAYS * 1440)) -print -delete | wc -l)

total=$(du -sb "$LOG_ROOT" | cut -f1)
removed=0
if (( total > max_bytes )); then
  while IFS=' ' read -r _mtime size path; do
    (( total <= max_bytes )) && break
    rm -f -- "$path"
    total=$((total - size))
    removed=$((removed + 1))
  done < <(find "$LOG_ROOT" -type f -mmin +"$KEEP_RECENT_MIN" -printf '%T@ %s %p\n' | sort -n)
fi
find "$LOG_ROOT" -mindepth 1 -type d -empty -delete

echo "retention: removed $old file(s) older than ${RETENTION_DAYS}d, $removed more for size;" \
  "now $((total / 1024 / 1024)) MiB (limit $((max_bytes / 1024 / 1024)) MiB)"
if (( total > max_bytes )); then
  echo "WARN: still above the limit; only recent files are left" >&2
fi
