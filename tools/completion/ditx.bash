# bash completion for ditx; installed by ./install.sh. All logic lives in
# `ditx __complete` so completion can never disagree with the CLI.
_ditx() {
  # rebuild the words ourselves: bash splits `--flag=value` at '=' (COMP_WORDBREAKS)
  local line="${COMP_LINE:0:COMP_POINT}" cur prefix
  local -a words
  IFS=' ' read -r -a words <<< "$line"
  [[ "$line" == *' ' ]] && words+=('')
  cur="${words[${#words[@]}-1]}"
  local IFS=$'\n'
  # shellcheck disable=SC2207
  COMPREPLY=($(command ditx __complete "${words[@]:1}" 2>/dev/null))
  if [[ "$cur" == --*=* ]]; then  # bash only replaces the part after '='
    prefix="${cur%%=*}="
    COMPREPLY=("${COMPREPLY[@]#"$prefix"}")
  fi
}
complete -F _ditx ditx

# `ditx cd <domain|package>` has to change *this* shell's directory, so it is a function
ditx() {
  if [ "${1:-}" = cd ]; then
    local dir
    dir="$(DITX_SHELL_FUNCTION=1 command ditx cd "${@:2}")" && cd "$dir" || return
  else
    command ditx "$@"
  fi
}
