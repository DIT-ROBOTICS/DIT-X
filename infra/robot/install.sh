#!/bin/bash
# Prepare a robot for `ditx deploy` / `ditx up`. Run ON the robot, from a checkout
# of the shell repo, as the desktop account:
#   sudo infra/robot/install.sh [--user ditrobotics] [--dry-run] [--uninstall]
#
# Idempotent: running it again only fixes what drifted. Everything lives in one
# folder next to DIT-Scripts' /home/share/{data,scripts}, owned by the desktop account
# and the docker group (setgid), so every DIT-Scripts account (main and one per
# team: navigation, localization, vision) can deploy and prune what another pushed:
#   /home/share/eurobot/
#     compose.yaml .env   written by ditx
#     overlays/           builds pushed by `ditx deploy`
#     active/             overlay choice kept across reboots (`ditx deploy --persist`)
#     run/active/         overlay choice until the next boot (emptied at every boot)
#                         → a rebooted robot always runs its stable image
#     logs/               every container's log + system/ (journal, kernel)
#     config/             logging.env (retention, NAS sync)
#     state/              bookkeeping of the timers
#   systemd timers        log retention (hourly), NAS sync (nightly), syslog export (10 min)
#   udev rules            /dev/dit-* stable device names (edit the placeholders first)
set -euo pipefail

here=infra/robot   # paths in the printed commands stay short
cd "$(dirname "$0")/../.."
user="${SUDO_USER:-ditrobotics}"   # owner: the account that ran sudo (the desktop account)
# DIT-Scripts creates these; whoever exists gets the groups ditx needs
accounts=(ditrobotics main navigation localization vision)
dry=0
uninstall=0
while (($#)); do
  case "$1" in
    --user) user="${2:?--user needs a name}"; shift 2 ;;
    -n | --dry-run) dry=1; shift ;;
    --uninstall) uninstall=1; shift ;;
    -h | --help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

# ── output: the same marks and colors as ditx ─────────────────────────────
# Each step prints the commands it really runs (dim), then one result line:
#   ✓ done / already in place   – would change (dry run)   ! needs attention
if [[ -z "${NO_COLOR:-}" && (-t 1 || -n "${FORCE_COLOR:-}") ]]; then
  bold=$'\e[1m' dim=$'\e[2m' green=$'\e[32m' yellow=$'\e[33m' red=$'\e[31m' cyan=$'\e[36m' off=$'\e[0m'
else
  bold='' dim='' green='' yellow='' red='' cyan='' off=''
fi
changes=0
say() { printf '  %s%s %s%s\n' "$dim" "$( ((dry)) && echo would || echo +)" "$*" "$off"; }
run() {   # run CMD...: show it, count it, and stop the install if it fails
  changes=$((changes + 1))
  say "$*"
  ((dry)) || "$@" || die "failed: $*"
}
write() {   # write FILE (content on stdin) if it differs; returns 1 when it was already right
  local f="$1" tmp
  tmp="$(mktemp)"
  cat > "$tmp"
  if [[ -f "$f" ]] && cmp -s "$tmp" "$f"; then
    rm -f "$tmp"
    return 1
  fi
  changes=$((changes + 1))
  say "write $f"
  ((dry)) || install -D -m 0644 "$tmp" "$f" || die "failed: write $f"
  rm -f "$tmp"
}
ensure_dir() {   # ensure_dir PATH OWNER GROUP MODE
  [[ -d "$1" && "$(stat -c %U:%G:%a "$1")" == "$2:$3:$4" ]] ||
    run install -d -o "$2" -g "$3" -m "$4" "$1"
}
runsh() {   # runsh 'CMD': like run, for a command line with a glob (shown as written)
  changes=$((changes + 1))
  say "$1"
  ((dry)) || eval "$1" || die "failed: $1"
}
same_file() {   # same_file SRC DST MODE: DST has the content of SRC and MODE
  [[ -f "$2" && "$(stat -c %a "$2")" == "$3" ]] && cmp -s "$1" "$2"
}
step() {   # step LABEL DETAIL: result line of the commands run since the last step
  if ((changes && dry)); then
    printf '%s–%s %-13s %s %s(%d to change)%s\n' "$dim" "$off" "$1" "$2" "$dim" "$changes" "$off"
  elif ((changes)); then
    printf '%s✓%s %-13s %s\n' "$green" "$off" "$1" "$2"
  else
    printf '%s✓%s %-13s %s %s(no change)%s\n' "$green" "$off" "$1" "$2" "$dim" "$off"
  fi
  changes=0
}
warn() { printf '%s!%s %-13s %s\n' "$yellow" "$off" "$1" "$2"; }
die() { printf '%s✗%s %s\n' "$red" "$off" "$*" >&2; exit 1; }

((dry)) || [[ $EUID -eq 0 ]] || die "run with sudo (or --dry-run to see what it would do)"

units=(eurobot-log-retention eurobot-log-sync eurobot-syslog-export)
root=/home/share/eurobot

if ((uninstall)); then
  printf '%s▸ uninstall%s  timers and scripts; %s stays\n' "$bold$cyan" "$off" "$root"
  for u in "${units[@]}"; do
    run systemctl disable --now "$u.timer" || true
    run rm -f "/etc/systemd/system/$u.service" "/etc/systemd/system/$u.timer"
  done
  run rm -rf /usr/local/lib/eurobot
  run rm -f /etc/tmpfiles.d/eurobot.conf /etc/udev/rules.d/99-dit-devices.rules
  run systemctl daemon-reload
  step removed "timers, scripts, tmpfiles and udev rules"
  exit 0
fi

if id "$user" > /dev/null 2>&1; then
  group="$(id -gn "$user")"
else
  ((dry)) || die "user $user does not exist (use --user)"
  warn account "no $user here (not a robot?): showing the plan only"
  group="$user"
fi
getent group docker > /dev/null && group=docker   # shared with the team (DIT-Scripts does the same)
printf '%s▸ install%s  %s:%s → %s%s\n' \
  "$bold$cyan" "$off" "$user" "$group" "$root" "$( ((dry)) && echo "  (dry run)")"

# ── folders ───────────────────────────────────────────────────────────────
# /home/share comes from DIT-Scripts on team machines; keep its permissions if it exists
[[ -d /home/share ]] || run install -d -m 0755 /home/share
for d in "$root" "$root"/{overlays,active,logs,config,state}; do
  ensure_dir "$d" "$user" "$group" 2775
done
if write /etc/tmpfiles.d/eurobot.conf <<CONF || [[ ! -d "$root/run/active" ]]; then
# run/ is emptied at every boot: an overlay activated without --persist is forgotten
D $root/run        2775 $user $group -
d $root/run/active 2775 $user $group -
CONF
  run systemd-tmpfiles --create /etc/tmpfiles.d/eurobot.conf
fi
step folders "$root"

# ── accounts: docker (ditx, /home/share), dialout (serial devices) ────────
found=()
for u in $(printf '%s\n' "$user" "${accounts[@]}" | sort -u); do
  id "$u" > /dev/null 2>&1 || continue
  found+=("$u")
  for g in docker dialout; do
    if getent group "$g" > /dev/null && ! id -nG "$u" | tr ' ' '\n' | grep -qx "$g"; then
      run usermod -aG "$g" "$u"
    fi
  done
done
step accounts "docker + dialout: ${found[*]:-none here}"

# ── log timers ────────────────────────────────────────────────────────────
[[ -d /usr/local/lib/eurobot ]] || run install -d -m 0755 /usr/local/lib/eurobot
stale=0
for s in "$here"/eurobot-*.sh; do
  same_file "$s" "/usr/local/lib/eurobot/${s##*/}" 755 || stale=1
done
((stale)) && runsh "install -m 755 -t /usr/local/lib/eurobot $here/eurobot-*.sh"
if [[ ! -f "$root/config/logging.env" ]]; then   # once: edited on the robot afterwards
  write "$root/config/logging.env" < "$here/logging.env.example"
  run chown "$user:$group" "$root/config/logging.env"
fi
reload=0
for u in "${units[@]}"; do
  sed "s/@USER@/$user/g" "$here/systemd/$u.service" | write "/etc/systemd/system/$u.service" && reload=1
  write "/etc/systemd/system/$u.timer" < "$here/systemd/$u.timer" && reload=1
done
((reload)) && run systemctl daemon-reload
for u in "${units[@]}"; do
  if ! { systemctl is-enabled --quiet "$u.timer" && systemctl is-active --quiet "$u.timer"; } 2> /dev/null; then
    run systemctl enable --now "$u.timer"
  fi
done
step "log timers" "retention, NAS sync, syslog export"

# ── udev: stable /dev/dit-* names ─────────────────────────────────────────
if write /etc/udev/rules.d/99-dit-devices.rules < "$here/udev/99-dit-devices.rules"; then
  run udevadm control --reload
fi
step "udev rules" "/dev/dit-* (fill in infra/robot/udev/ first)"

# ── docker: rotate container logs (only if the admin has no config yet) ───
if [[ -f /etc/docker/daemon.json ]]; then
  step "docker logs" "kept the existing daemon.json"
else
  write /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "local",
  "log-opts": { "max-size": "50m", "max-file": "5" }
}
JSON
  step "docker logs" "rotated: 5 × 50 MB per container"
  warn docker "applies after: sudo systemctl restart docker"
fi

# ── checks ────────────────────────────────────────────────────────────────
if ! systemctl is-active --quiet chrony 2> /dev/null; then
  warn chrony "not running: logs of different machines will not line up"
  printf '  %s→ sudo apt install chrony, all machines on one time server%s\n' "$dim" "$off"
fi
if ((dry)); then
  printf '%s–%s %-13s %s\n' "$dim" "$off" "dry run" "nothing changed (run without -n to apply)"
else
  printf '%s✓%s %-13s %s\n' "$green" "$off" "ready" "next, on your laptop: ditx doctor -r <robot>"
fi
