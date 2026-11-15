#!/bin/bash
# Entrypoint of every eurobot container. Builds the environment in layers:
#
#   /opt/ros/$ROS_DISTRO                      ROS
#   /opt/eurobot/base/install                 shared interfaces (baked into the image)
#   /opt/eurobot/$EUROBOT_DOMAIN/install      this domain, stable build (baked into the image)
#   /var/lib/eurobot/overlays/<domain>/<id>   overlay pushed by `ditx deploy` (optional)
#
# The active overlay id is read from /run/eurobot/active/<domain> (tmpfs: gone
# after a reboot, so the robot falls back to the stable image) or from
# /var/lib/eurobot/active/<domain> (`ditx deploy --persist`).
#
# With EUROBOT_LOG_DIR set (the long-running service of a container), all output is also
# written to $EUROBOT_LOG_DIR/<container>/<container>_<start time>.log and the entrypoint
# says which build runs. Commands exec'd into a running container (`ditx topics`, `ditx
# contract live`) leave it empty, so they print only their own output.
set -e
umask 002   # logs stay writable for the robot's group, whoever deploys next

say() { [[ -z "${EUROBOT_LOG_DIR:-}" ]] || echo "[entrypoint] $*"; }

# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO}/setup.bash"
# shellcheck disable=SC1091
source /opt/eurobot/base/install/setup.bash

domain="${EUROBOT_DOMAIN:-}"
if [[ -n "$domain" && -f "/opt/eurobot/$domain/install/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/eurobot/$domain/install/setup.bash"
fi

if [[ -n "${EUROBOT_LOG_DIR:-}" ]]; then
  name="${EUROBOT_CONTAINER:-${domain:-$(hostname)}}"
  mkdir -p "$EUROBOT_LOG_DIR/$name/ros"
  logfile="$EUROBOT_LOG_DIR/$name/${name}_$(date +%Y%m%dT%H%M%S).log"
  export ROS_LOG_DIR="$EUROBOT_LOG_DIR/$name/ros"
  exec > >(tee -a "$logfile") 2>&1
  say "log file $logfile"
fi

overlay=""
if [[ -n "$domain" ]]; then
  for f in "/run/eurobot/active/$domain" "/var/lib/eurobot/active/$domain"; do
    [[ -s "$f" ]] && { overlay="$(<"$f")"; break; }
  done
fi
if [[ -n "$overlay" ]]; then
  dir="/var/lib/eurobot/overlays/$domain/$overlay"
  want="$(cat /opt/eurobot/base/FINGERPRINT 2>/dev/null || true)"
  have="$(sed -n 's/.*"base_fingerprint": *"\([^"]*\)".*/\1/p' "$dir/manifest.json" 2>/dev/null || true)"
  if [[ ! -f "$dir/install/setup.bash" ]]; then
    say "WARN overlay $overlay not found in $dir, running the stable image"
  elif [[ "$have" != "$want" && "${EUROBOT_ALLOW_SKEW:-0}" != 1 ]]; then
    say "ERROR overlay $overlay was built against base $have but this image has base $want."
    say "      Interfaces differ, so it would fail at runtime. Running the stable image instead."
    say "      Rebuild against the current base, or deploy with --allow-skew if you know better."
  else
    # shellcheck disable=SC1091
    source "$dir/install/setup.bash"
    export EUROBOT_OVERLAY="$overlay"
    # one short line; `ditx deploy` waits for "overlay <id> active", the full manifest is on disk
    who="$(python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); d=m["domain"]
g=m.get("git",{}).get(d,{}); print(m.get("user","?"), "·", d + "@" + (g.get("describe") or "?"))' \
      "$dir/manifest.json" 2>/dev/null || echo "?")"
    say "overlay $overlay active · by $who"
  fi
fi
[[ -z "${EUROBOT_OVERLAY:-}" && -n "$domain" ]] && say "running stable image (no overlay)"

exec "$@"
