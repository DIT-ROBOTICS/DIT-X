#!/bin/bash
# Put `ditx` on your PATH and enable Tab completion. Idempotent; safe to re-run.
#   ./install.sh              install (symlink ~/.local/bin/ditx + rc block)
#   ./install.sh --dry-run    show what would change
#   ./install.sh --uninstall  undo both
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${HOME}/.local/bin"
link="${bin_dir}/ditx"
begin='# >>> ditx (DIT-X) >>>'
end='# <<< ditx (DIT-X) <<<'
dry=0
mode=install
for a in "$@"; do
  case "$a" in
    -n|--dry-run) dry=1 ;;
    --uninstall) mode=uninstall ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

do_() { if (( dry )); then echo "would: $*"; else "$@"; fi; }

strip_block() {   # remove our marked block from an rc file
  local rc="$1"
  [[ -f "$rc" ]] && grep -qF "$begin" "$rc" || return 0
  if (( dry )); then echo "would: remove ditx block from $rc"; return 0; fi
  sed -i "/^${begin//\//\\/}\$/,/^${end//\//\\/}\$/d" "$rc"
}

rc_files=()
[[ -f "$HOME/.bashrc" ]] && rc_files+=("$HOME/.bashrc")
[[ -f "$HOME/.zshrc" ]] && rc_files+=("$HOME/.zshrc")

fish_conf="$HOME/.config/fish/conf.d/ditx.fish"

if [[ "$mode" == uninstall ]]; then
  if [[ -L "$link" && "$(readlink -f "$link")" == "$root/bin/ditx" ]]; then do_ rm "$link"; fi
  if [[ -L "$fish_conf" && "$(readlink -f "$fish_conf")" == "$root/tools/completion/ditx.fish" ]]; then
    do_ rm "$fish_conf"
  fi
  for rc in "${rc_files[@]}"; do strip_block "$rc"; done
  echo "ditx uninstalled"
  exit 0
fi

if [[ -e "$link" && ! -L "$link" ]]; then
  echo "refusing to overwrite $link (not a symlink we made)" >&2
  exit 1
fi
do_ mkdir -p "$bin_dir"
do_ ln -sfn "$root/bin/ditx" "$link"

for rc in "${rc_files[@]}"; do
  shell=bash; [[ "$rc" == *zshrc ]] && shell=zsh
  strip_block "$rc"
  block="$begin
case \":\$PATH:\" in *\":$bin_dir:\"*) ;; *) export PATH=\"$bin_dir:\$PATH\" ;; esac
[ -f \"$root/tools/completion/ditx.$shell\" ] && source \"$root/tools/completion/ditx.$shell\"
$end"
  if (( dry )); then
    echo "would: append to $rc:"; echo "$block"
  else
    # end the file with exactly one newline, then the block (re-installs don't pile up blank lines)
    [[ -s "$rc" && -n "$(tail -c1 "$rc")" ]] && echo >> "$rc"
    printf '%s\n' "$block" >> "$rc"
  fi
done

# fish reads ~/.config/fish/conf.d/*.fish itself: link ours there when fish is set up
if [[ -d "$HOME/.config/fish" ]]; then
  if [[ -e "$fish_conf" && ! -L "$fish_conf" ]]; then
    echo "not touching $fish_conf (not a link we made)" >&2
  else
    do_ mkdir -p "$(dirname "$fish_conf")"
    do_ ln -sfn "$root/tools/completion/ditx.fish" "$fish_conf"
  fi
fi

if (( dry )); then
  echo "dry run: nothing changed"
  exit 0
fi
PYTHONPATH="$root/tools" python3 -c 'from ditx import ui; ui.banner("DIT-X · Eurobot workspace · installed")' || true
echo "ditx installed → $link (open a new shell, then: ditx doctor)"
