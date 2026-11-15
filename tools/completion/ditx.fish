# fish completion + `ditx cd` for ditx; ./install.sh links it into
# ~/.config/fish/conf.d/ when fish is set up. Same backend as bash/zsh.
contains -- $HOME/.local/bin $PATH; or set -gx PATH $HOME/.local/bin $PATH

function __ditx_complete
    set -l words (commandline -opc) (commandline -ct)
    command ditx __complete --describe-tab $words[2..-1] 2>/dev/null
end
complete -c ditx -f -a '(__ditx_complete)'

# `ditx cd <domain|package>` has to change *this* shell's directory, so it is a function
function ditx --wraps ditx
    if test "$argv[1]" = cd
        set -l dir (env DITX_SHELL_FUNCTION=1 command ditx cd $argv[2..-1]); and cd $dir
    else
        command ditx $argv
    end
end
