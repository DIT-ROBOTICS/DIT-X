#!/bin/bash
# Append new system journal and kernel messages to the eurobot log folder, so
# USB disconnects, network-manager events, OOM kills etc. sit next to the
# container logs with the same retention and NAS sync.
#   /home/share/eurobot/logs/system/journal_<date>.log
#   /home/share/eurobot/logs/system/kernel_<date>.log
# journalctl cursor files make every run continue exactly where the last stopped.
set -euo pipefail

conf="${EUROBOT_LOGGING_ENV:-/home/share/eurobot/config/logging.env}"
# shellcheck disable=SC1090
[[ -r "$conf" ]] && source "$conf"
LOG_ROOT="${LOG_ROOT:-/home/share/eurobot/logs}"
STATE_DIR="${STATE_DIR:-/home/share/eurobot/state/syslog-export}"

out="$LOG_ROOT/system"
mkdir -p "$out" "$STATE_DIR"
day="$(date +%F)"

export_journal() {   # name, extra journalctl args...
  local name="$1"; shift
  local cursor="$STATE_DIR/$name.cursor" since=()
  [[ -s "$cursor" ]] || since=(--since "-15min")   # first run: don't dump the whole journal
  journalctl --no-pager -o short-iso-precise --cursor-file="$cursor" "${since[@]}" "$@" \
    >> "$out/${name}_${day}.log"
}

export_journal journal
export_journal kernel -k   # = dmesg, but incremental and with wall-clock timestamps
