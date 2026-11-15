"""`ditx` with no arguments: an interactive command builder.

Not a second implementation of anything: you pick a command and its options,
the equivalent `ditx ...` line is shown live at the bottom, and `r` runs exactly
that line. New members learn the CLI by watching it being written for them.

Python stdlib curses only (no pip). The model (what is selected, which argv it
produces, whether it is runnable) is plain Python and unit-tested without a
terminal; everything curses lives in the View.
"""

import curses
import json
import locale
import os
import re
import shlex
import subprocess
import sys
import tempfile

from . import ui
from .commands import COMMANDS, GROUPS, plugin_cmd, resolve_values
from .workspace import native_arch

STATE_FILE = os.path.join(
    os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'), 'ditx', 'last.json'
)

# options that must be set before a command can run
REQUIRED = {
    ('deploy', 'domains'),
    ('new', 'domain'),
    ('new', 'package'),
    ('ci', 'stage'),
    ('completion', 'shell'),
}
VIEW_GROUPS = GROUPS + [('plugins', 'Plugins')]
DEFAULT = object()  # picker result: "back to the default value"


# ════════════════════════════════════════════════════════════════════════════
# model
# ════════════════════════════════════════════════════════════════════════════


class Model:
    def __init__(self, ws, state=None):
        self.ws = ws
        builtin = [c for g, _ in GROUPS for c in COMMANDS if c.group == g and c.tui]
        try:
            plugins = ws.plugins()
        except Exception:  # noqa: BLE001 - a broken PATH entry must not kill the TUI
            plugins = {}
        self.commands = builtin + [
            plugin_cmd(name, path, summary) for name, (path, summary) in sorted(plugins.items())
        ]
        self.index = 0
        self.values = {}  # {command: {dest: value}}
        self.dry_run = False
        self.verbose = False
        self.mouse = True  # m toggles; off lets the terminal select text normally
        self.focus = 'cmds'  # remembered across runs
        self.opt_i = 0
        if state:
            self.load(state)

    # ── selection ──
    @property
    def cmd(self):
        return self.commands[self.index]

    def options(self):
        return [o for o in self.cmd.opts if o.tui]

    def select(self, name):
        for i, c in enumerate(self.commands):
            if c.name == name:
                self.index = i
                return True
        return False

    # ── values ──
    def value(self, opt):
        v = self.values.get(self.cmd.name, {}).get(opt.dest)
        if v is None:
            return [] if opt.kind == 'multi' else (False if opt.kind == 'flag' else opt.default)
        return v

    def set_value(self, opt, v):
        self.values.setdefault(self.cmd.name, {})[opt.dest] = v

    def reset(self, opt):
        """Back to the option's default (Del / Backspace / x)."""
        self.values.get(self.cmd.name, {}).pop(opt.dest, None)

    def is_set(self, opt):
        return self.values.get(self.cmd.name, {}).get(opt.dest) is not None

    def selected_domains(self):
        """Domains picked in this command's --domain (empty = all)."""
        o = self.opt('domains')
        return list(self.value(o)) if o else []

    def choices(self, opt):
        if opt.values == 'packages':  # only what the selected domains contain
            try:
                return self.ws.packages(self.selected_domains() or None)
            except Exception:  # noqa: BLE001 - pickers must never crash
                return []
        vals = resolve_values(opt.values, self.ws)
        if opt.dest == 'robot' and not vals:
            vals = [self.ws.default_robot()]
        return vals

    def cycle(self, opt, step=1):
        """Flags toggle; choices step through their values (None = default)."""
        if opt.kind == 'flag':
            self.set_value(opt, not self.value(opt))
        elif opt.kind == 'choice':
            vals = self.choices(opt)
            if not vals:
                return
            ring = vals if opt.default in vals else [None] + vals
            cur = self.value(opt)
            i = ring.index(cur) if cur in ring else 0
            self.set_value(opt, ring[(i + step) % len(ring)])

    @staticmethod
    def value_problem(cmd_name, opt, v):
        """Why `v` is not a valid value for `opt` (None = fine). Shared by edit and load."""
        if v in (None, '', []):
            return None
        if opt.dest in ('jobs', 'workers') and v != 'auto':
            if not (str(v).isdigit() and int(v) > 0):
                flag = '-j' if opt.dest == 'jobs' else '--workers'
                return f'{flag} must be auto or a positive number'
        if opt.kind == 'choice' and isinstance(opt.values, tuple) and v not in opt.values:
            name = opt.flags[-1] if opt.flags else opt.dest
            return f'{name} must be one of {", ".join(opt.values)}'
        if cmd_name == 'new' and opt.dest == 'package' and not re.fullmatch(r'[a-z][a-z0-9_]*', v):
            return 'package names are snake_case: lowercase letters, digits, underscores'
        return None

    # ── output ──
    def argv(self):
        """The command line this selection stands for (what `r` runs)."""
        c = self.cmd
        out = [c.name]
        mode = ['--dry-run'] * self.dry_run + ['--verbose'] * self.verbose
        if c.group == 'plugins':
            out = mode + out  # global flags go before a plugin: it parses the rest itself
        else:
            out += mode
        for o in [o for o in c.opts if not o.flags] + [o for o in c.opts if o.flags]:
            v = self.value(o)
            flag = o.flags[-1] if o.flags else None  # long form, the same as the labels
            if o.kind == 'flag':
                if v:
                    out.append(flag)
            elif o.kind == 'multi':
                if v:
                    out += ([flag] if flag else []) + list(v)
            elif v not in (None, '') and (v != o.default or not o.flags and o.default is None):
                if flag:
                    out += [flag, str(v)]
                elif v != o.default:
                    out.append(str(v))
        return out

    def command_line(self):
        return 'ditx ' + shlex.join(self.argv())

    def problem(self):
        """Why the current selection cannot run yet (None = runnable)."""
        if self.cmd.name == 'robot':
            action = self.value(self.opt('action')) or 'list'
            if action in ('add', 'remove') and not self.value(self.opt('name')):
                return f'set NAME first: which robot to {action}'
            if action == 'add' and not self.value(self.opt('host')):
                return 'set --host first: the robot hostname, e.g. DIT-2026-11'
        for o in self.cmd.opts:
            if (self.cmd.name, o.dest) in REQUIRED or o.dest in self.cmd.required:
                v = self.value(o)
                if not v:
                    return f'set {opt_label(o)} first: {o.help}'
        pkgs, doms = self.opt('packages'), self.selected_domains()
        if pkgs and doms and self.value(pkgs):
            try:
                known = set(self.ws.packages(doms))
            except Exception:  # noqa: BLE001
                known = set()
            stray = [p for p in self.value(pkgs) if p not in known]
            if stray:
                which = 'is' if len(stray) == 1 else 'are'
                return f'{", ".join(stray)} {which} not in the selected domains ({", ".join(doms)})'
        if self.cmd.name == 'new':
            pkg, dom = self.value(self.opt('package')), self.value(self.opt('domain'))
            if pkg and dom and not pkg.startswith(dom + '_'):
                return f'package names start with their domain, e.g. {dom}_{pkg}'
        for o in self.cmd.opts:
            p = self.value_problem(self.cmd.name, o, self.value(o))
            if p:
                return p
        return None

    def opt(self, dest):
        return next((o for o in self.cmd.opts if o.dest == dest), None)

    # ── persistence: last command, its options, focus and cursor ──
    def to_dict(self):
        return {
            'command': self.cmd.name,
            'values': self.values,
            'focus': self.focus,
            'opt': self.opt_i,
            'mouse': self.mouse,
        }

    def load(self, state):
        if not isinstance(state, dict):
            return
        values = state.get('values')
        if isinstance(values, dict):
            for c in self.commands:
                saved = values.get(c.name)
                if not isinstance(saved, dict):
                    continue
                for o in c.opts:
                    v = saved.get(o.dest)
                    if v is None or o.kind == 'text' and o.dest == 'cmd':
                        continue
                    typed = (
                        o.kind == 'flag'
                        and isinstance(v, bool)
                        or o.kind == 'multi'
                        and isinstance(v, list)
                        and all(isinstance(x, str) for x in v)
                        or o.kind in ('choice', 'text')
                        and isinstance(v, str)
                    )
                    if typed and not self.value_problem(c.name, o, v):
                        self.values.setdefault(c.name, {})[o.dest] = v
        if isinstance(state.get('command'), str):
            self.select(state['command'])
        if isinstance(state.get('mouse'), bool):
            self.mouse = state['mouse']
        if state.get('focus') in ('cmds', 'opts'):
            self.focus = state['focus']
        if isinstance(state.get('opt'), int) and state['opt'] >= 0:
            self.opt_i = state['opt']
        if not self.options():
            self.focus, self.opt_i = 'cmds', 0
        self.opt_i = min(self.opt_i, max(0, len(self.options()) - 1))


def opt_label(o):
    """--flag for options, UPPERCASE for positionals, as usage lines write them."""
    return o.flags[-1] if o.flags else o.dest.upper()


def toggle_all(chosen, shown):
    """Ctrl+A in a multi picker: select every visible entry, or none if all already are."""
    return chosen - set(shown) if set(shown) <= chosen else chosen | set(shown)


def load_state():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_state(model):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE))
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(model.to_dict(), f)
        os.replace(tmp, STATE_FILE)  # atomic: a crash never leaves half a file
    except OSError:
        pass


# ════════════════════════════════════════════════════════════════════════════
# view
# ════════════════════════════════════════════════════════════════════════════

# key hint bar; the ones listed in DROP_ORDER disappear first when the terminal is narrow
HELP_KEYS = [
    ('↑↓', 'move'),
    ('Tab', 'pane'),
    ('⏎', 'edit'),
    ('/', 'filter'),
    ('r', 'run'),
    ('n', 'dry-run'),
    ('v', 'verbose'),
    ('m', 'mouse'),
    ('?', 'help'),
    ('q', 'quit'),
]
DROP_ORDER = ['m', 'n', 'v', '/', '⏎', 'Tab', '↑↓']
HELP_TEXT = [
    ('Keys', None),
    ('↑ ↓  j k', 'move in the focused pane'),
    ('Tab  ← →  h l', 'switch between commands and options (← → change a choice value)'),
    ('⏎  Space', 'edit the option: toggle a flag, open a picker, type a value'),
    ('Del  ⌫  x', 'reset the option to its default'),
    ('g G  Home End', 'first / last'),
    ('PgUp PgDn  Ctrl+U/D', 'page up / down'),
    ('/', 'filter the commands (Esc clears)'),
    ('r', 'run the command line shown at the bottom'),
    ('n  v', 'toggle --dry-run / --verbose'),
    ('m', 'mouse capture on / off (off: the terminal selects and copies text normally)'),
    ('?', 'this help'),
    ('q  Ctrl+C', 'quit (Esc only steps back)'),
    ('', ''),
    ('Mouse', None),
    ('click', 'select; click a selected option again to edit it'),
    ('wheel', 'scroll the pane under the pointer'),
    ('Shift+drag', 'selects text to copy even with the mouse on'),
    ('', ''),
    ('Legend', None),
    ('!', 'asks for confirmation before it runs'),
    ('required', 'set this option before r'),
    ('DRY-RUN', 'commands are printed, nothing changes'),
    ('MOUSE OFF', 'mouse capture is off (m turns it back on)'),
    ('', ''),
    ('', 'The bottom line is exactly what runs; type it yourself next time.'),
]

C_ACCENT, C_DIM, C_OK, C_ERR, C_KEY, C_RULE, C_TEXT, C_VALUE, C_SEL, C_WARN, C_SEL_DIM = range(
    1, 12
)


class View:
    MIN_W, MIN_H = 64, 20

    def __init__(self, scr, model):
        self.scr, self.m = scr, model
        self.message = ''  # last error (red); standing problems come from the model (yellow)
        self.filter = None  # None = no filter; '' or text = filtering the command list
        self.typing = False  # keystrokes go into the filter
        self.colors = False
        self.hits = []
        self.panes = {}
        self._init_colors()

    @property
    def focus(self):
        return self.m.focus

    @focus.setter
    def focus(self, v):
        self.m.focus = v

    @property
    def opt_i(self):
        return self.m.opt_i

    @opt_i.setter
    def opt_i(self, v):
        self.m.opt_i = v

    def _init_colors(self):
        if os.environ.get('NO_COLOR') or not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()  # keep the terminal's own background
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        rich = curses.COLORS >= 256
        pal = {
            # brand accent for focus, semantic colors for state (see ui.py)
            C_ACCENT: (ui.ACCENT, curses.COLOR_CYAN),
            C_DIM: (ui.GRAY, curses.COLOR_WHITE),
            C_OK: (ui.OK, curses.COLOR_GREEN),
            C_ERR: (ui.ERR, curses.COLOR_RED),
            C_WARN: (ui.WARN, curses.COLOR_YELLOW),
            C_KEY: (ui.ACCENT, curses.COLOR_CYAN),
            C_RULE: (ui.RULE, curses.COLOR_WHITE),
            C_TEXT: (-1, -1),
            C_VALUE: (ui.WHITE, curses.COLOR_WHITE),
        }
        for pair, (c256, c8) in pal.items():
            curses.init_pair(pair, c256 if rich else c8, bg)
        curses.init_pair(
            C_SEL, 231 if rich else curses.COLOR_WHITE, ui.SEL_BG if rich else curses.COLOR_BLUE
        )
        # the cursor of the pane without focus: a quiet gray bar (lazygit style)
        curses.init_pair(
            C_SEL_DIM, 252 if rich else curses.COLOR_WHITE, 237 if rich else curses.COLOR_BLACK
        )
        self.colors = True

    def gradient_attr(self, color):
        """Bold + one 256-color foreground (pairs allocated on demand, 20+)."""
        attr = curses.A_BOLD
        if self.colors and curses.COLORS >= 256:
            pair = 20 + color % 200
            try:
                curses.init_pair(pair, color, -1)
                attr |= curses.color_pair(pair)
            except curses.error:
                attr |= curses.color_pair(C_ACCENT)
        elif self.colors:
            attr |= curses.color_pair(C_ACCENT)
        return attr

    def attr(self, pair, bold=False):
        a = curses.color_pair(pair) if self.colors else 0
        if pair == C_SEL and not self.colors:
            a = curses.A_REVERSE
        if pair == C_SEL_DIM and not self.colors:
            a = curses.A_UNDERLINE
        return a | (curses.A_BOLD if bold else 0)

    def put(self, y, x, text, attr=0, maxw=None):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w or x < 0:
            return
        room = (w - x - (1 if y == h - 1 else 0)) if maxw is None else min(maxw, w - x)
        out, used = '', 0
        for ch in text:
            cw = ui.width(ch)
            if used + cw > room:
                break
            out += ch
            used += cw
        try:
            self.scr.addstr(y, x, out, attr)
        except curses.error:
            pass

    def box(self, y, x, h, w, title, focused):
        a = self.attr(C_ACCENT if focused else C_RULE, bold=focused)
        self.put(y, x, '╭' + '─' * (w - 2) + '╮', a)
        for i in range(1, h - 1):
            self.put(y + i, x, '│', a)
            self.put(y + i, x + w - 1, '│', a)
        self.put(y + h - 1, x, '╰' + '─' * (w - 2) + '╯', a)
        self.put(y, x + 2, f' {title} ', self.attr(C_ACCENT if focused else C_DIM, bold=True))

    @staticmethod
    def scroll_first(cur, count, visible):
        """First visible row so that `cur` stays on screen (one row of context)."""
        if count <= visible or cur < visible - 1:
            return 0
        return min(cur - visible + 2, count - visible)

    # ── command list (with / filter) ──
    def visible_commands(self):
        flt = (self.filter or '').lower()
        return [i for i, c in enumerate(self.m.commands) if flt in c.name.lower()]

    def move_command(self, to=None, step=0):
        idx = self.visible_commands()
        if not idx:
            return
        pos = idx.index(self.m.index) if self.m.index in idx else 0
        pos = to if to is not None else pos + step
        self.m.index = idx[max(0, min(len(idx) - 1, pos))]
        self.opt_i = 0

    def move_option(self, to=None, step=0):
        n = len(self.m.options())
        if n:
            self.opt_i = max(0, min(n - 1, to if to is not None else self.opt_i + step))

    # ── frame ──
    def layout(self):
        h, w = self.scr.getmaxyx()
        compact = h < 30  # fewer blank rows on small terminals
        top = 3 if compact else 4
        bottom = 5 if compact else 7  # preview box + hints + status (+ blank rows)
        return h, w, compact, top, h - top - bottom

    def draw(self):
        s, m = self.scr, self.m
        s.erase()
        self.hits = []  # (y, x0, x1, target) of clickable rows, rebuilt every frame
        self.panes = {}
        h, w, compact, top, body_h = self.layout()
        if w < self.MIN_W or h < self.MIN_H:
            msg = f'terminal too small: need {self.MIN_W}x{self.MIN_H}, have {w}x{h}'
            self.put(0, 0, msg, self.attr(C_ERR))
            s.refresh()
            return
        hy = 0 if compact else 1
        if not hasattr(self, '_branch'):
            self._branch = m.ws.git(m.ws.root, 'rev-parse', '--abbrev-ref', 'HEAD')
        where = f'{self._branch or "-"} · {m.ws.distro} · robot {m.ws.default_robot()}'
        # two-row wordmark (the big figlet logo is for install / init / doctor only)
        art = ui.WORDMARK
        for i, line in enumerate(art):
            for j, ch in enumerate(line):
                if ch != ' ':
                    self.put(hy + i, 2 + j, ch, self.gradient_attr(ui.logo_color(i, j, art)))
        x = 2 + len(art[0]) + 3
        self.put(hy, x, 'DIT-X  Eurobot workspace', self.attr(C_DIM))
        self.put(hy + 1, x, where, self.attr(C_TEXT))
        badges = [
            b
            for b, on in (
                (' DRY-RUN ', m.dry_run),
                (' VERBOSE ', m.verbose),
                (' MOUSE OFF ', not m.mouse),
            )
            if on
        ]
        self.put(hy + 1, x + ui.width(where) + 2, ' '.join(badges), self.attr(C_WARN, bold=True))

        # left: commands grouped; right: options
        left_w = 24
        self.draw_commands(top, left_w, body_h)
        rx, rw = left_w + 2, w - left_w - 3
        self.draw_options(top, rx, rw, body_h)

        # command preview: exactly what `r` runs
        cy = top + body_h
        self.box(cy, 1, 3, w - 2, 'command line', False)
        problem = m.problem()
        self.put(cy + 1, 3, '$ ', self.attr(C_DIM))
        line = ui.clip(m.command_line(), w - 8)
        self.put(cy + 1, 5, line, self.attr(C_WARN if problem else C_VALUE, bold=True))

        # key hints (least important dropped first when narrow) + status line
        hints = list(HELP_KEYS)
        drop = list(DROP_ORDER)
        while sum(ui.width(k) + ui.width(d) + 3 for k, d in hints) > w - 4 and drop:
            gone = drop.pop(0)
            hints = [kd for kd in hints if kd[0] != gone]
        hint_y = h - 2 if compact else h - 3
        x = 2
        for k, d in hints:
            self.put(hint_y, x, k, self.attr(C_KEY, bold=True))
            x += ui.width(k) + 1
            self.put(hint_y, x, d, self.attr(C_DIM))
            x += ui.width(d) + 2
        if self.message:
            status, color = self.message, C_ERR
        elif problem:
            status, color = problem, C_WARN
        else:
            status, color = self.status_hint(), C_DIM
        self.put(hint_y + 1, 2, ui.clip(status, w - 4), self.attr(color))
        s.refresh()

    def draw_commands(self, top, left_w, body_h):
        m = self.m
        flt = self.filter
        title = f'commands /{flt}' if flt is not None else 'commands'
        self.box(top, 1, body_h, left_w, title, self.focus == 'cmds')
        self.panes['cmds'] = (top, top + body_h, 1, left_w + 1)
        shown = set(self.visible_commands())
        if shown and m.index not in shown:
            self.move_command(to=0)
        rows = []  # (text, command index or None for a group heading)
        for g, label in VIEW_GROUPS:
            idx = [i for i, c in enumerate(m.commands) if c.group == g and i in shown]
            if idx:
                rows.append((label, None))
                rows += [(m.commands[i].name, i) for i in idx]
        inner = left_w - 2
        visible = body_h - 2
        if not rows:
            self.put(top + 1, 3, 'no matches', self.attr(C_DIM))
            return
        sel_row = next((r for r, (_, i) in enumerate(rows) if i == m.index), 0)
        first = self.scroll_first(sel_row, len(rows), visible)
        for r, (text, i) in enumerate(rows[first : first + visible]):
            y = top + 1 + r
            if i is None:
                self.put(y, 3, text, self.attr(C_DIM))
                continue
            c = m.commands[i]
            sel = i == m.index
            mark = '!' if c.confirm else ' '
            row = ' ' + ui.pad(f' {text}', inner - 3) + mark + ' '  # exactly `inner` cells
            if sel:
                pair = C_SEL if self.focus == 'cmds' else C_SEL_DIM
                self.put(y, 2, row, self.attr(pair, bold=True))
            else:
                self.put(y, 2, row, self.attr(C_TEXT))
                if c.confirm:
                    self.put(y, 2 + inner - 2, '!', self.attr(C_ERR))
            self.hits.append((y, 1, left_w + 1, ('cmd', i)))
        if first > 0:
            self.put(top, left_w - 3, '▲', self.attr(C_DIM))
        if first + visible < len(rows):
            self.put(top + body_h - 1, left_w - 3, '▼', self.attr(C_DIM))

    def draw_options(self, top, rx, rw, body_h):
        m = self.m
        self.box(top, rx, body_h, rw, f'{m.cmd.name} options', self.focus == 'opts')
        self.panes['opts'] = (top, top + body_h, rx, rx + rw)
        self.put(top + 1, rx + 2, ui.clip(m.cmd.help, rw - 4), self.attr(C_DIM))
        opts = m.options()
        self.opt_i = min(self.opt_i, max(0, len(opts) - 1))
        if not opts:
            hint = (
                f'plugin: runs `ditx {m.cmd.name}`; press r'
                if m.cmd.group == 'plugins'
                else 'no options: press r to run'
            )
            self.put(top + 3, rx + 2, hint, self.attr(C_DIM))
            return
        inner = rw - 2
        label_w = min(22, max([ui.width(self.opt_label(o)) for o in opts] + [8]) + 1)
        visible = body_h - 4  # help line + blank line + borders
        first = self.scroll_first(self.opt_i, len(opts), visible)
        for r, o in enumerate(opts[first : first + visible]):
            i = first + r
            y = top + 3 + r
            label = f'  {ui.pad(self.opt_label(o), label_w)}  '
            value = self.opt_value_text(o)
            if i == self.opt_i:
                pair = C_SEL if self.focus == 'opts' else C_SEL_DIM
                row = ui.pad(ui.clip(label + value, inner), inner)
                self.put(y, rx + 1, row, self.attr(pair, bold=self.focus == 'opts'))
            else:
                self.put(y, rx + 1, label, self.attr(C_TEXT))
                vx = rx + 1 + ui.width(label)
                self.put(y, vx, ui.clip(value, inner - ui.width(label)), self.value_attr(o))
            self.hits.append((y, rx, rx + rw, ('opt', i)))
        if first > 0:
            self.put(top + 2, rx + rw - 3, '▲', self.attr(C_DIM))
        if first + visible < len(opts):
            self.put(top + body_h - 1, rx + rw - 3, '▼', self.attr(C_DIM))

    def status_hint(self):
        if self.typing:
            return 'type to filter · ⏎ done · Esc clear'
        opts = self.m.options()
        if self.focus == 'opts' and opts:
            o = opts[self.opt_i]
            reset = ' · Del reset' if self.m.is_set(o) else ''
            about = getattr(o, 'choice_help', None) or {}
            v = self.m.value(o)
            what = f' — {v}: {about[v]}' if isinstance(v, str) and v in about else ''
            return f'{o.help}{what}  (⏎ edit{reset})'
        if self.m.cmd.group == 'plugins' and not opts:
            return 'r run the plugin · ? help'
        return 'Tab/→ options · r run · / filter · ? help'

    def opt_label(self, o):
        return opt_label(o)

    def is_required(self, o):
        required = (self.m.cmd.name, o.dest) in REQUIRED or o.dest in self.m.cmd.required
        return required and not self.m.value(o)

    def opt_value_text(self, o):
        v = self.m.value(o)
        if self.is_required(o):
            return 'required · ⏎ to set'
        if o.kind == 'flag':
            return '● on' if v else '○ off'
        if o.kind == 'multi':
            return ' '.join(v) if v else ('all' if o.dest == 'domains' else 'none')
        if v in (None, ''):
            return self.default_text(o) or 'not set'
        return str(v)

    def default_text(self, o):
        if o.dest == 'robot':
            return f'default: {self.m.ws.default_robot()}'
        if o.dest == 'arch':
            return f'default: native ({native_arch()})'
        if o.default not in (None, ''):
            return f'default: {o.default}'
        return ''

    def value_attr(self, o):
        v = self.m.value(o)
        if self.is_required(o):
            return self.attr(C_WARN, bold=True)
        if o.kind == 'flag':
            return self.attr(C_OK if v else C_DIM, bold=bool(v))
        if v in (None, '', []) or (o.kind != 'multi' and v == o.default):
            return self.attr(C_DIM)
        return self.attr(C_VALUE, bold=True)

    # ── popups ──
    def too_small(self):
        h, w = self.scr.getmaxyx()
        return w < self.MIN_W or h < self.MIN_H

    def popup_frame(self, title, rows_h, width_hint):
        """A centered box with a 1-row margin to the panes; returns (y, x, height, width)."""
        h, w = self.scr.getmaxyx()
        pw = min(w - 4, max(30, width_hint + 6), max(30, int(w * 0.8)))
        ph = min(h - 4, rows_h + 2)
        py, px = (h - ph) // 2, (w - pw) // 2
        for yy in range(py, py + ph):
            self.put(yy, px, ' ' * pw)
        self.box(py, px, ph, pw, title, True)
        return py, px, ph, pw

    def wait_too_small(self):
        """While the terminal is too small, only show that; True = the user pressed Esc."""
        return self.scr.get_wch() == '\x1b'

    def outside(self, ev, frame):
        py, px, ph, pw = frame
        return isinstance(ev, tuple) and not (py <= ev[0] < py + ph and px <= ev[1] < px + pw)

    def picker(self, opt, multi):
        """List picker with a filter line. Returns the new value, DEFAULT, or None (cancel)."""
        values = self.m.choices(opt)
        if not values:
            self.message = f'{self.opt_label(opt)} has nothing to choose from'
            return None
        current = self.m.value(opt)
        entries = list(values)
        default_entry = not multi and opt.default not in values
        if default_entry:
            label = self.default_text(opt) or 'not set'
            entries = [f'({label})'] + entries
        chosen = set(current or []) if multi else set()
        if not multi and current in values:
            cur = entries.index(current)
        else:
            cur = 0
        flt = ''
        hint = (
            'Space toggle · Ctrl+A all · ⏎ ok · type to filter · Esc cancel'
            if multi
            else '⏎ choose · type to filter · Esc cancel'
        )
        about = {} if multi else (getattr(opt, 'choice_help', None) or {})
        name_w = max(ui.width(v) for v in entries)
        list_h = min(len(entries), 14)  # fixed frame: sized from all entries, not the matches
        width = max(
            [ui.width(v) + 4 + (ui.width(about[v]) + 3 if v in about else 0) for v in entries]
            + [ui.width(hint), 30]
        )
        while True:
            shown = [e for e in entries if flt.lower() in e.lower()]
            cur = min(cur, max(0, len(shown) - 1))
            self.draw()
            if self.too_small():
                if self.wait_too_small():
                    return None
                continue
            frame = self.popup_frame(self.opt_label(opt), list_h + 2, width)
            py, px, ph, pw = frame
            rows_h = ph - 4
            count = f'{len(shown)}/{len(entries)}'
            self.put(py + 1, px + 2, '/ ' + flt, self.attr(C_TEXT, bold=True), maxw=pw - 10)
            self.put(py + 1, px + pw - 2 - len(count), count, self.attr(C_DIM))
            first = self.scroll_first(cur, len(shown), rows_h)
            rows = {}
            for i, v in enumerate(shown[first : first + rows_h]):
                idx = first + i
                rows[py + 2 + i] = idx
                box = ('[x] ' if v in chosen else '[ ] ') if multi else ''
                sel = idx == cur
                self.put(
                    py + 2 + i,
                    px + 2,
                    ui.pad(f'{box}{v}', pw - 4),
                    self.attr(C_SEL, bold=True) if sel else self.attr(C_TEXT),
                )
                if v in about:  # what each choice means, dimmed to the right (fzf preview style)
                    dx = px + 2 + ui.width(box) + name_w + 3
                    self.put(
                        py + 2 + i,
                        dx,
                        ui.clip(about[v], max(0, px + pw - 2 - dx)),
                        self.attr(C_SEL) if sel else self.attr(C_DIM),
                    )
            if not shown:
                self.put(py + 2, px + 2, 'no matches', self.attr(C_DIM))
            if first > 0:
                self.put(py + 2, px + pw - 2, '▲', self.attr(C_DIM))
            if first + rows_h < len(shown):
                self.put(py + ph - 3, px + pw - 2, '▼', self.attr(C_DIM))
            self.put(py + ph - 2, px + 2, hint, self.attr(C_DIM), maxw=pw - 4)
            self.scr.refresh()
            k = self.scr.get_wch()
            if k == '\x1b':
                return None
            if k == curses.KEY_MOUSE:
                ev = self.mouse()
                if ev == 'up':
                    cur = max(0, cur - 1)
                elif ev == 'down':
                    cur = min(len(shown) - 1, cur + 1)
                elif self.outside(ev, frame):
                    return None  # click outside closes, like a menu
                elif ev and ev[0] in rows:
                    cur = rows[ev[0]]
                    if not multi:
                        return self.picked(shown[cur], default_entry, entries)
                    chosen ^= {shown[cur]}
                continue
            if k == curses.KEY_UP:  # arrows only: letters (also j/k) go into the filter
                cur = max(0, cur - 1)
            elif k == curses.KEY_DOWN:
                cur = min(len(shown) - 1, cur + 1)
            elif k in (curses.KEY_PPAGE, curses.KEY_HOME):
                cur = 0 if k == curses.KEY_HOME else max(0, cur - rows_h)
            elif k in (curses.KEY_NPAGE, curses.KEY_END):
                cur = len(shown) - 1 if k == curses.KEY_END else min(len(shown) - 1, cur + rows_h)
            elif k in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                flt = flt[:-1]
            elif k == '\x15':  # ^u clears the filter
                flt = ''
            elif k == ' ' and multi and shown:
                chosen ^= {shown[cur]}
            elif k == '\x01' and multi and shown:  # Ctrl+A: all visible, or none if all are set
                chosen = toggle_all(chosen, shown)
            elif k in ('\n', '\r', curses.KEY_ENTER):
                if multi:
                    return [v for v in values if v in chosen]
                if shown:
                    return self.picked(shown[cur], default_entry, entries)
            elif isinstance(k, str) and k.isprintable() and k != ' ':
                flt += k

    @staticmethod
    def picked(entry, default_entry, entries):
        return DEFAULT if default_entry and entry == entries[0] else entry

    def text_input(self, opt):
        """One-line editor: placeholder = default, readline keys, validated before ⏎ closes."""
        current = self.m.values.get(self.m.cmd.name, {}).get(opt.dest)
        buf = ' '.join(current) if isinstance(current, list) else str(current or '')
        pos = len(buf)
        error = ''
        placeholder = self.default_text(opt) or 'empty = default'
        curses.curs_set(1)
        try:
            while True:
                self.draw()
                if self.too_small():
                    if self.wait_too_small():
                        return None
                    continue
                width = max(40, ui.width(opt.help), ui.width(buf) + 4)
                frame = self.popup_frame(self.opt_label(opt), 3, width)
                py, px, ph, pw = frame
                self.put(py + 1, px + 2, opt.help, self.attr(C_DIM), maxw=pw - 4)
                self.put(py + 2, px + 2, '> ', self.attr(C_ACCENT, bold=True))
                if buf:
                    self.put(py + 2, px + 4, buf, self.attr(C_TEXT, bold=True), maxw=pw - 6)
                else:
                    self.put(py + 2, px + 4, placeholder, self.attr(C_DIM), maxw=pw - 6)
                if error:
                    self.put(py + 3, px + 2, error, self.attr(C_ERR), maxw=pw - 4)
                else:
                    keys = '⏎ ok · Esc cancel · Ctrl+U clear · empty = default'
                    self.put(py + 3, px + 2, keys, self.attr(C_DIM), maxw=pw - 4)
                self.scr.move(py + 2, min(px + 4 + ui.width(buf[:pos]), px + pw - 2))
                self.scr.refresh()
                k = self.scr.get_wch()
                error = ''
                if k == '\x1b':
                    return None
                if k == curses.KEY_MOUSE:
                    if self.outside(self.mouse(), frame):
                        return None
                    continue
                if k in ('\n', '\r', curses.KEY_ENTER):
                    v = buf.strip()
                    check = v.split() if opt.kind == 'multi' else v
                    problem = None
                    if opt.kind != 'multi':
                        problem = self.m.value_problem(self.m.cmd.name, opt, check)
                    if problem:
                        error = problem
                        continue
                    return v
                if k in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                    if pos:
                        buf, pos = buf[: pos - 1] + buf[pos:], pos - 1
                elif k == curses.KEY_DC:
                    buf = buf[:pos] + buf[pos + 1 :]
                elif k == curses.KEY_LEFT:
                    pos = max(0, pos - 1)
                elif k == curses.KEY_RIGHT:
                    pos = min(len(buf), pos + 1)
                elif k in (curses.KEY_HOME, '\x01'):
                    pos = 0
                elif k in (curses.KEY_END, '\x05'):
                    pos = len(buf)
                elif k == '\x15':  # ^u: delete to the start
                    buf, pos = buf[pos:], 0
                elif k == '\x0b':  # ^k: delete to the end
                    buf = buf[:pos]
                elif k == '\x17':  # ^w: delete the word before the cursor
                    left = buf[:pos].rstrip()
                    cut = left.rfind(' ') + 1
                    buf, pos = buf[:cut] + buf[pos:], cut
                elif isinstance(k, str) and k.isprintable():
                    buf, pos = buf[:pos] + k + buf[pos:], pos + 1
        finally:
            curses.curs_set(0)

    def confirm(self, text):
        robot = self.m.opt('robot')
        if robot is not None:
            text += f' (robot {self.m.value(robot) or self.m.ws.default_robot()})'
        self.draw()
        line = '$ ' + self.m.command_line()
        frame = self.popup_frame('confirm', 3, max(ui.width(text), ui.width(line)))
        py, px, ph, pw = frame
        self.put(py + 1, px + 2, text, self.attr(C_ERR, bold=True), maxw=pw - 4)
        self.put(py + 2, px + 2, ui.clip(line, pw - 4), self.attr(C_TEXT))
        self.put(py + 3, px + 2, 'y run · any other key cancels', self.attr(C_DIM))
        self.scr.refresh()
        return self.scr.get_wch() in ('y', 'Y')

    def show_help(self):
        """Keys, mouse, legend, then the options of the current command; scrollable."""
        lines = []
        for k, d in HELP_TEXT:
            if d is None:
                lines.append(('head', k))
            else:
                lines.append(('row', f'  {ui.pad(k, 18)} {d}' if k else (f'  {d}' if d else '')))
        lines.append(('row', ''))
        lines.append(('head', f'Options of ditx {self.m.cmd.name}'))
        for o in self.m.cmd.opts:
            lines.append(('row', f'  {ui.pad(self.opt_label(o), 18)} {o.help}'))
        if not self.m.cmd.opts:
            lines.append(('row', '  (none)'))
        top = 0
        while True:
            self.draw()
            if self.too_small():
                if self.wait_too_small():
                    return
                continue
            width = max(ui.width(t) for _, t in lines)
            frame = self.popup_frame('help · ↑↓ scroll · any key closes', len(lines), width)
            py, px, ph, pw = frame
            rows = ph - 2
            top = max(0, min(top, len(lines) - rows))
            for i, (kind, text) in enumerate(lines[top : top + rows]):
                a = self.attr(C_ACCENT, bold=True) if kind == 'head' else self.attr(C_TEXT)
                self.put(py + 1 + i, px + 2, text, a, maxw=pw - 4)
            if top > 0:
                self.put(py + 1, px + pw - 2, '▲', self.attr(C_DIM))
            if top + rows < len(lines):
                self.put(py + ph - 2, px + pw - 2, '▼', self.attr(C_DIM))
            self.scr.refresh()
            k = self.scr.get_wch()
            if k == curses.KEY_MOUSE:
                ev = self.mouse()  # wheel scrolls; clicks are ignored (no accidental close)
                if ev in ('up', 'down'):
                    top += -1 if ev == 'up' else 1
                continue
            if k in (curses.KEY_UP, 'k'):
                top -= 1
            elif k in (curses.KEY_DOWN, 'j'):
                top += 1
            elif k == curses.KEY_PPAGE:
                top -= rows
            elif k == curses.KEY_NPAGE:
                top += rows
            else:
                return

    # ── event loop ──
    def edit_option(self, o, key):
        if o.kind == 'flag':
            self.m.cycle(o)
        elif o.kind == 'choice':
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                self.m.cycle(o, -1 if key == curses.KEY_LEFT else 1)
            else:
                v = self.picker(o, multi=False)
                if v is DEFAULT:
                    self.m.reset(o)
                elif v is not None:
                    self.m.set_value(o, v)
        elif o.kind == 'multi':
            v = self.picker(o, multi=True) if self.m.choices(o) else self.text_input(o)
            if v is not None:
                v = v if isinstance(v, list) else v.split()
                self.m.set_value(o, v) if v else self.m.reset(o)
        elif o.kind == 'text':
            v = self.text_input(o)
            if v is not None:
                self.m.set_value(o, v) if v else self.m.reset(o)

    def mouse(self):
        """'up' / 'down' for the wheel, (y, x) for a click, None for anything else."""
        try:
            _, x, y, _, b = curses.getmouse()
        except curses.error:
            return None
        self.last_mouse = (y, x)
        if b & curses.BUTTON4_PRESSED:
            return 'up'
        if b & getattr(curses, 'BUTTON5_PRESSED', 0x200000):
            return 'down'
        if b & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED):
            return (y, x)
        return None  # releases, drags: ignore so one click acts once

    def pane_at(self, y, x):
        for name, (y0, y1, x0, x1) in self.panes.items():
            if y0 <= y < y1 and x0 <= x < x1:
                return name
        return None

    def on_mouse(self):
        ev = self.mouse()
        if ev in ('up', 'down'):
            # the wheel scrolls the pane under the pointer, clamped at the ends
            step = -1 if ev == 'up' else 1
            pane = self.pane_at(*self.last_mouse) or self.focus
            if pane == 'opts':
                self.move_option(step=step)
            else:
                self.move_command(step=step)
            return
        if not ev:
            return
        y, x = ev
        for hy, x0, x1, (kind, i) in self.hits:
            if hy == y and x0 <= x < x1:
                if kind == 'cmd':
                    self.m.index, self.opt_i, self.focus = i, 0, 'cmds'
                elif self.focus == 'opts' and self.opt_i == i:
                    self.edit_option(self.m.options()[i], '\n')  # second click edits
                else:
                    self.focus, self.opt_i = 'opts', i
                return

    def page(self):
        _, _, _, _, body_h = self.layout()
        return max(1, body_h - 4)

    def on_filter_key(self, k):
        """Keys while typing a / filter."""
        if k == '\x1b':
            self.filter, self.typing = None, False
        elif k in ('\n', '\r', curses.KEY_ENTER, curses.KEY_DOWN, '\t'):
            self.typing = False
            if not self.filter:
                self.filter = None
        elif k in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            if self.filter:
                self.filter = self.filter[:-1]
            else:
                self.filter, self.typing = None, False
        elif isinstance(k, str) and k.isprintable():
            self.filter += k
        self.move_command(step=0)

    def apply_mouse(self):
        """Capture the mouse, or hand it back to the terminal (plain text selection)."""
        curses.mousemask(curses.ALL_MOUSE_EVENTS if self.m.mouse else 0)

    def loop(self):
        curses.curs_set(0)
        self.scr.keypad(True)
        self.apply_mouse()
        curses.mouseinterval(0)  # no click delay
        while True:
            self.draw()
            k = self.scr.get_wch()
            if k == curses.KEY_RESIZE:
                continue
            self.message = ''
            opts = self.m.options()
            if k == curses.KEY_MOUSE:
                self.on_mouse()
                continue
            if self.typing:
                self.on_filter_key(k)
                continue
            if k == 'q':
                return None
            if k == '\x1b':  # Esc steps back: clear the filter, then leave the options pane
                if self.filter is not None:
                    self.filter = None
                else:
                    self.focus = 'cmds'
                continue
            if k == '?':
                self.show_help()
            elif k == '/':
                self.filter, self.typing, self.focus = self.filter or '', True, 'cmds'
            elif k == 'n':
                self.m.dry_run = not self.m.dry_run
            elif k == 'm':
                self.m.mouse = not self.m.mouse
                self.apply_mouse()  # the MOUSE OFF badge in the header shows the state
            elif k == 'v':
                self.m.verbose = not self.m.verbose
            elif k == 'r':
                problem = self.m.problem()
                if problem:
                    self.message = problem
                    continue
                if (
                    self.m.cmd.confirm
                    and not self.m.dry_run
                    and not self.confirm(self.m.cmd.confirm)
                ):
                    continue
                return self.m.argv()
            elif k == '\t':
                self.focus = 'opts' if self.focus == 'cmds' and opts else 'cmds'
            elif k in ('g', curses.KEY_HOME):
                self.move_option(to=0) if self.focus == 'opts' else self.move_command(to=0)
            elif k in ('G', curses.KEY_END):
                last = 10**6
                self.move_option(to=last) if self.focus == 'opts' else self.move_command(to=last)
            elif k in (curses.KEY_NPAGE, curses.KEY_PPAGE, '\x04', '\x15'):
                step = self.page() if k == curses.KEY_NPAGE else -self.page()
                if k in ('\x04', '\x15'):  # ^d / ^u: half a page
                    step = (self.page() // 2 or 1) * (1 if k == '\x04' else -1)
                if self.focus == 'opts':
                    self.move_option(step=step)
                else:
                    self.move_command(step=step)
            elif self.focus == 'cmds':
                if k in (curses.KEY_UP, 'k'):
                    self.move_command(step=-1)
                elif k in (curses.KEY_DOWN, 'j'):
                    self.move_command(step=1)
                elif k in (curses.KEY_RIGHT, '\n', '\r', curses.KEY_ENTER, 'l') and opts:
                    self.focus = 'opts'
            elif opts:
                o = opts[self.opt_i]
                if k in (curses.KEY_UP, 'k'):
                    self.move_option(step=-1)
                elif k in (curses.KEY_DOWN, 'j'):
                    self.move_option(step=1)
                elif k in (curses.KEY_DC, curses.KEY_BACKSPACE, '\x7f', '\b', 'x'):
                    self.m.reset(o)
                elif (k == curses.KEY_LEFT and o.kind != 'choice') or k == 'h':
                    self.focus = 'cmds'
                elif k in ('\n', '\r', curses.KEY_ENTER, ' ', curses.KEY_LEFT, curses.KEY_RIGHT):
                    self.edit_option(o, k)


def _read_key():
    """One key from the terminal without waiting for Enter (stdlib termios)."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_tui(ws, dry_run=False, verbose=False, mouse=None):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        ui.error('the interactive builder needs a terminal; see `ditx --help` for the commands')
        return 2
    if os.environ.get('TERM', 'dumb') == 'dumb':
        ui.error('TERM is "dumb"; set TERM=xterm-256color or use `ditx --help`')
        return 2
    locale.setlocale(locale.LC_ALL, '')
    os.environ.setdefault('ESCDELAY', '25')  # Esc closes popups without a 1 s lag
    model = Model(ws, load_state())
    model.dry_run = model.dry_run or dry_run
    model.verbose = model.verbose or verbose
    if mouse is not None:
        model.mouse = bool(mouse)
    if os.environ.get('DITX_NO_MOUSE', '').lower() not in ('', '0', 'false', 'no'):
        model.mouse = False
    exe = os.path.join(ws.root, 'bin', 'ditx')
    rc = 0
    while True:
        try:
            argv = curses.wrapper(lambda scr: View(scr, model).loop())
        except KeyboardInterrupt:  # ^c quits quietly, like q
            save_state(model)
            return 130
        save_state(model)  # also on quit: the next start comes back to the same place
        if argv is None:
            return rc
        line = 'ditx ' + shlex.join(argv)
        print(ui.paint('$ ', ui.GRAY) + ui.paint(line, ui.WHITE, bold=True), file=sys.stderr)
        try:
            # destructive commands were already confirmed in the builder's popup
            env = {**os.environ, 'DITX_CONFIRMED': '1'} if model.cmd.confirm else None
            rc = subprocess.call([sys.executable, exe, *argv], env=env)
        except KeyboardInterrupt:
            rc = 130
        mark = ui.paint('✓', ui.OK, bold=True) if rc == 0 else ui.paint(f'✗ {rc}', ui.ERR, True)
        print(
            f'\n{mark}  {ui.paint("⏎", ui.ACCENT, bold=True)} back to the builder · '
            f'{ui.paint("q", ui.ACCENT, bold=True)} quit',
            file=sys.stderr,
            flush=True,
        )
        try:
            key = _read_key()
        except (OSError, KeyboardInterrupt):
            key = 'q'
        if key in ('q', 'Q', '\x03', '\x04'):
            return rc
