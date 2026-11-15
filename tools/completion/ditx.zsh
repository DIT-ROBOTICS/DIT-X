#compdef ditx
# zsh completion for ditx; installed by ./install.sh (same backend as bash,
# with descriptions shown next to each candidate).
_ditx() {
  local -a out
  out=("${(@f)$(command ditx __complete --describe "${(@)words[2,CURRENT]}" 2>/dev/null)}")
  out=(${out:#})
  (( ${#out} )) && _describe -t ditx 'ditx' out
}
compdef _ditx ditx

# `ditx cd <domain|package>` has to change *this* shell's directory, so it is a function
ditx() {
  if [[ "${1:-}" == cd ]]; then
    local dir
    dir="$(DITX_SHELL_FUNCTION=1 command ditx cd "${@:2}")" && cd "$dir" || return
  else
    command ditx "$@"
  fi
}
