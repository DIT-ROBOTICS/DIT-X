#!/bin/bash
# Copy /home/share/eurobot/logs to the lab NAS (incremental). Quietly does nothing when
# NAS_TARGET is empty or the NAS is unreachable (competition venue, no uplink),
# so the timer never fails and the next run catches up.
set -euo pipefail

conf="${EUROBOT_LOGGING_ENV:-/home/share/eurobot/config/logging.env}"
# shellcheck disable=SC1090
[[ -r "$conf" ]] && source "$conf"
LOG_ROOT="${LOG_ROOT:-/home/share/eurobot/logs}"
NAS_TARGET="${NAS_TARGET:-}"

if [[ -z "$NAS_TARGET" ]]; then
  echo "log sync disabled (NAS_TARGET empty)"
  exit 0
fi
dest="${NAS_TARGET%/}/$(hostname)/"

if [[ "$NAS_TARGET" == *:* ]]; then
  host="${NAS_TARGET%%:*}"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null; then
    echo "NAS $host unreachable, skipping (next run will catch up)"
    exit 0
  fi
  ssh -o BatchMode=yes "$host" mkdir -p "${dest#*:}"
else
  mkdir -p "$dest"
fi

rsync -a --partial --timeout=60 "$LOG_ROOT/" "$dest"
echo "synced $LOG_ROOT → $dest"
