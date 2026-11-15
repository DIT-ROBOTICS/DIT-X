"""Tab completion backend: `ditx __complete [--describe|--describe-tab] <words…>`.

The shell scripts in tools/completion only forward to this, so completion
always knows exactly the commands, flags and values the CLI accepts.
  plain           one candidate per line (bash)
  --describe      `value:description`, colons in values escaped (zsh _describe)
  --describe-tab  `value<TAB>description` (fish)
"""

from .commands import BY_NAME, COMMANDS, plugin_cmd, resolve_values

GLOBAL = [
    ('-n', '--dry-run', 'print what would run, change nothing'),
    ('-v', '--verbose', 'show the full output of every tool'),
    ('-q', '--quiet', 'print only warnings and errors'),
    ('-h', '--help', 'show help'),
]
TOP_ONLY = [('-V', '--version', 'print the version')]


def _global_words():
    return {w for s, lng, _ in GLOBAL + TOP_ONLY for w in (s, lng)}


def _line_domains(before):
    """Domains given with -d/--domain on the line so far (packages are filtered by them)."""
    out, take = [], False
    for w in before[1:]:
        if w.startswith('--domain='):
            out.append(w.split('=', 1)[1])
            take = True
        elif w in ('-d', '--domain'):
            take = True
        elif w.startswith('-'):
            take = False
        elif take:
            out.append(w)
    return out


def _described(o, values):
    """(value, its own one-line meaning if the option has one, else the option's help)."""
    return [(v, o.choice_help.get(v, o.help)) for v in values]


def _candidates(ws, words):
    """[(value, description)] for the last word of `words` (everything after `ditx`)."""
    words = words or ['']
    cur, before = words[-1], list(words[:-1])
    while before and before[0] in _global_words():  # `ditx -n build ...`
        before.pop(0)
    if not before:  # the command (or a global flag) is being typed
        if cur.startswith('-'):
            return [(f, h) for s, lng, h in GLOBAL + TOP_ONLY for f in (lng, s)]
        out = [(c.name, c.help) for c in COMMANDS]
        if ws:
            out += [(n, s or 'plugin') for n, (_, s) in sorted(ws.plugins().items())]
        return out + [('help', 'show help for a command')]
    if before[0] == 'help':
        return [(c.name, c.help) for c in COMMANDS] if len(before) == 1 else []
    cmd = BY_NAME.get(before[0])
    if not cmd and ws:  # a plugin: complete what it declares with `# ditx-arg:`
        found = ws.plugins().get(before[0])
        cmd = plugin_cmd(before[0], *found) if found else None
    if not cmd:
        return []
    flag_opt = {f: o for o in cmd.opts for f in o.flags}
    used = set(before)
    doms = _line_domains(before)

    def values(o):
        return resolve_values(o.values, ws, doms)

    if cur.startswith('--') and '=' in cur:  # --build-type=Rel<Tab>
        flag = cur.split('=', 1)[0]
        o = flag_opt.get(flag)
        if not o or o.kind == 'flag':
            return []
        return [(f'{flag}={v}', h) for v, h in _described(o, values(o))]

    # a value for the option before the cursor? (single-value options take exactly one)
    for i in range(len(before) - 1, 0, -1):
        w = before[i]
        if not w.startswith('-'):
            continue
        o = flag_opt.get(w)
        n_values = len(before) - 1 - i
        if (
            o
            and not cur.startswith('-')
            and ((o.kind == 'multi') or (o.kind in ('choice', 'text') and n_values == 0))
        ):
            given = set(before[i + 1 :])
            return [(v, h) for v, h in _described(o, values(o)) if v not in given]
        break

    flags = []
    for o in cmd.opts:
        if o.flags and not (set(o.flags) & used):
            flags += [(f, o.help) for f in sorted(o.flags, key=len, reverse=True)]
    if cmd.group != 'plugins':  # a plugin parses its own flags; globals go before its name
        flags += [(f, h) for s, lng, h in GLOBAL for f in (lng, s) if f not in used]
    if cur.startswith('-'):
        return flags
    positionals = [o for o in cmd.opts if not o.flags]
    n_pos = sum(1 for w in before[1:] if not w.startswith('-'))
    if positionals:
        o = positionals[min(n_pos, len(positionals) - 1)]
        if o.kind == 'multi' or n_pos < len(positionals):
            return [(v, h) for v, h in _described(o, values(o)) if v not in used]
    return [f for f in flags if f[0].startswith('--')]  # nothing positional left: options


def complete(ws, words, describe=None):
    """Lines for the shell script; filtered by the prefix under the cursor."""
    cur = (words or [''])[-1]
    seen, out = set(), []
    for value, desc in _candidates(ws, words):
        if not value.startswith(cur) or value in seen:
            continue
        seen.add(value)
        if describe == '--describe':
            out.append(f'{value.replace(":", chr(92) + ":")}:{desc}')
        elif describe == '--describe-tab':
            out.append(f'{value}\t{desc}')
        else:
            out.append(value)
    return out
