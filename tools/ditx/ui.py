"""Terminal output shared by every ditx command.

Rules (https://clig.dev):
  - color only on a TTY, never when NO_COLOR is set (FORCE_COLOR / CI forces it on)
  - messages to stderr, machine-readable data to stdout
  - one line per step; tool noise (colcon, buildx, git, compose) goes to a log file
    and is shown only on failure or with -v (CI shows everything)
  - no box drawing in log output: it breaks with CJK/emoji widths and in CI logs
"""

import atexit
import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import unicodedata

# Colors in xterm-256 (fixed indices: the 16 ANSI colors follow the terminal theme
# and can end up invisible against its background).
# Semantic colors follow the usual CLI convention; the brand only colors the logo,
# focus and the spinner, so red always means "error".
OK = 78  # ✓ green
ERR = 203  # ✗ red
WARN = 220  # ! yellow
WHITE = 255  # values
GRAY = 245  # secondary text
RULE = 237  # borders
# Brand ("neon", synthwave): logo gradient DIT red -> magenta -> violet -> cyan
# (bottom-left -> top-right), accent for focus/keys/spinner, selection background.
LOGO_RAMP = [160, 197, 199, 171, 135, 99, 63, 39, 45]
ACCENT = ACCENT_HI = 45
SEL_BG = 24

# -v / CI: stream every line of every tool instead of one line per step
VERBOSE = os.environ.get('CI', '').lower() not in ('', '0', 'false', 'no')
# GitHub Actions folds `::group::` blocks; GitLab uses section markers
GITHUB = bool(os.environ.get('GITHUB_ACTIONS'))
# -n: steps end with a gray `–` and "(dry run)", never ✓; -q: only warnings and errors
DRY_RUN = False
QUIET = False


def _color_enabled(stream):
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('CLICOLOR_FORCE', '0') != '0':
        return True
    # CI web logs render colors; a plain CI=1 piped into a file stays plain
    if any(os.environ.get(k) for k in ('FORCE_COLOR', 'GITHUB_ACTIONS', 'GITLAB_CI')):
        return True
    return hasattr(stream, 'isatty') and stream.isatty() and os.environ.get('TERM') != 'dumb'


COLOR_ERR = _color_enabled(sys.stderr)
COLOR_OUT = _color_enabled(sys.stdout)
LIVE = sys.stderr.isatty() and os.environ.get('TERM') != 'dumb'


def paint(text, color, bold=False, stream=None):
    on = COLOR_OUT if stream is sys.stdout else COLOR_ERR
    if not on or color is None:
        return text
    return f'\033[{"1;" if bold else ""}38;5;{color}m{text}\033[0m'


def term_width():
    return max(40, min(shutil.get_terminal_size((100, 24)).columns, 120))


def layout(msg, room):
    """Fit a message into `room` columns, the way flutter/brew doctor do: a long
    `what  → fix` puts the fix on its own indented line, and whatever is still too
    long wraps with a hanging indent. Short messages stay one line. Lines after an
    explicit newline are kept as they are (commands to copy must not be broken)."""
    out = []
    first, *rest = msg.split('\n')
    for line in [first]:
        if width(line) <= room:
            out.append(line)
            continue
        head, sep, fix = line.partition('  → ')
        kw = dict(width=room, break_long_words=False, break_on_hyphens=False)
        out += textwrap.wrap(head, subsequent_indent='  ', **kw) or [head]
        if sep:
            out += textwrap.wrap('→ ' + fix, initial_indent='  ', subsequent_indent='    ', **kw)
    return out + rest


def _emit(mark, color, msg, always=False, dim=False):
    if QUIET and not always:
        return
    lines = layout(msg, term_width() - 2)
    for i, line in enumerate(lines):
        lead = paint(mark, color, bold=True) if i == 0 else ' ' * width(mark)
        print(f'{lead} {paint(line, GRAY) if dim else line}', file=sys.stderr, flush=True)


def done(msg):
    """Closing line of a multi-step command: `  ── 4 domains · 36s`."""
    if not QUIET:
        print(paint(f'  ── {msg}', GRAY), file=sys.stderr, flush=True)


def step(msg):
    _emit('▸', ACCENT, msg)


def info(msg):
    _emit(' ', None, msg, dim=True)


def ok(msg):
    _emit('✓', OK, msg)


def warn(msg):
    _emit('!', WARN, msg, always=True)


def error(msg):
    _emit('✗', ERR, msg, always=True)


def command(argv_text, force=False):
    """Echo a command before running it (only with -v / --dry-run, or in CI)."""
    if VERBOSE or force:
        if ROOT and not VERBOSE:  # dry-run lines stay short: paths relative to the workspace
            argv_text = argv_text.replace(ROOT + '/', '').replace(ROOT, '.')
        print(paint(f'$ {argv_text}', GRAY), file=sys.stderr, flush=True)


def planned(label, text):
    """One line of a dry-run plan: what a step would do, without the raw command."""
    print(paint(f'– {pad(label, LABEL_W)} {text}  (dry run)', GRAY), file=sys.stderr, flush=True)


def width(s):
    """Display width; CJK characters take two cells."""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def pad(s, n):
    return s + ' ' * max(0, n - width(s))


def clip(s, n):
    out, used = '', 0
    for ch in s:
        if used + width(ch) > n:
            return out[:-1] + '…' if out else ''
        out += ch
        used += width(ch)
    return out


def table(rows, header=None, stream=sys.stdout):
    """Plain aligned columns (greppable; no borders). On a terminal the last column is
    cut with … to fit its width, like `gh pr list`; piped output keeps every character."""
    rows = [[str(c) for c in r] for r in rows]
    if not rows:  # empty: the caller prints its empty-state line, no lonely header
        return
    allrows = ([header] if header else []) + rows
    widths = [max(width(r[i]) for r in allrows) for i in range(len(allrows[0]))]
    if stream.isatty():
        room = term_width() - sum(w + 2 for w in widths[:-1])
        if room >= 12 and widths[-1] > room:
            widths[-1] = room
            rows = [r[:-1] + [clip(r[-1], room)] for r in rows]
    if header:
        print(
            paint(
                '  '.join(pad(h, w) for h, w in zip(header, widths, strict=False)).rstrip(),
                GRAY,
                stream=stream,
            ),
            file=stream,
        )
    for r in rows:
        print('  '.join(pad(c, w) for c, w in zip(r, widths, strict=False)).rstrip(), file=stream)


# ── one line per step ───────────────────────────────────────────────────────

# braille dots on UTF-8 terminals, plain ASCII elsewhere (old SSH sessions, LANG=C)
_UTF8 = 'utf' in (getattr(sys.stderr, 'encoding', '') or '').lower()
SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' if _UTF8 else '|/-\\'
LABEL_W = 14
_cursor_hidden = False


def _hide_cursor(hide):
    """Hide the terminal cursor while a spinner runs; always restored (atexit, errors)."""
    global _cursor_hidden
    if hide == _cursor_hidden or not LIVE:
        return
    _cursor_hidden = hide
    sys.stderr.write('\033[?25l' if hide else '\033[?25h')
    sys.stderr.flush()


atexit.register(_hide_cursor, False)


class Task:
    """A step shown as one line: a spinner + live status while it runs (on a TTY),
    then `✓ label  summary  12s` or `✗ label  summary`.

        with ui.Task('build main') as t:
            t.status('main_startup')
            ...
            t.done('3 packages')
    """

    def __init__(self, label):
        self.label, self.text, self.result = label, '', None
        self.start = time.monotonic()  # steady clock for durations
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        if LIVE and not VERBOSE and not QUIET:
            _hide_cursor(True)
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()

    def _line(self, mark, mark_color, text, show_time, text_color=None, bold=True):
        secs = time.monotonic() - self.start
        t = paint(f'  {secs:.0f}s', GRAY) if show_time and secs >= 1 else ''
        try:
            cols = os.get_terminal_size(sys.stderr.fileno()).columns
        except OSError:
            cols = 100
        cols = cols if cols >= 40 else 100  # ptys without a size report 0
        room = max(10, cols - LABEL_W - 12)
        head = f'{paint(mark, mark_color, bold=bold)} {pad(self.label, LABEL_W)}'
        return f'{head} {paint(clip(text, room), text_color)}{t}'

    def _spin(self):
        i = 0
        while not self._stop.wait(0.1):
            with self._lock:
                frame = SPINNER[i % len(SPINNER)]
                line = self._line(frame, ACCENT, self.text, True, GRAY, bold=False)
                sys.stderr.write('\r\033[K' + line)
                sys.stderr.flush()
            i += 1

    def status(self, text):
        self.text = text

    def print(self, text):
        """A permanent line above the spinner (e.g. a warning while the task runs)."""
        with self._lock:
            if self._thread:
                sys.stderr.write('\r\033[K')
            print(text, file=sys.stderr, flush=True)

    def _finish(self, mark, color, summary):
        if self.result is not None:
            return
        self.result = mark
        self._stop.set()
        if self._thread:
            self._thread.join()
            sys.stderr.write('\r\033[K')
            _hide_cursor(False)
        if QUIET and mark != '✗':
            return
        print(self._line(mark, color, summary, True), file=sys.stderr, flush=True)

    def done(self, summary=''):
        if DRY_RUN:  # nothing ran: never claim success
            summary = summary.replace(' · verified', '').replace('  verified', '')
            self._finish('–', GRAY, f'{summary}  (dry run)'.strip())
            return
        self._finish('✓', OK, summary)

    def fail(self, summary=''):
        self._finish('✗', ERR, summary)

    def skip(self, summary=''):
        self._finish('–', GRAY, summary)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.fail('interrupted' if exc_type is KeyboardInterrupt else self.text)
        else:
            self.done(self.text)
        return False


def run_logged(cmd, log_path, on_line=None, **popen):
    """Run cmd (list or shell string), all output -> log_path; returns (rc, lines).

    on_line(line) is called for every output line (to update a Task); with -v the
    lines are also printed as they come.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    lines = []
    with open(log_path, 'a', encoding='utf-8', errors='replace') as log:
        log.write(f'$ {cmd if isinstance(cmd, str) else " ".join(cmd)}\n')
        log.flush()
        p = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors='replace',
            bufsize=1,
            **popen,
        )
        for line in p.stdout:
            line = line.rstrip('\n')
            log.write(line + '\n')
            lines.append(line)
            if VERBOSE:
                _print_verbose(line)
            if on_line:
                on_line(line)
        rc = p.wait()
    return rc, lines


def _print_verbose(line):
    """Full-output mode: tool lines as they come; our @@ section markers become CI folds."""
    if line.startswith('@@begin '):
        name = line[8:].strip()
        print(
            f'::group::{name}' if GITHUB else paint(f'── {name}', ACCENT, bold=True),
            file=sys.stderr,
            flush=True,
        )
    elif line.startswith('@@end '):
        if GITHUB:
            print('::endgroup::', file=sys.stderr, flush=True)
    elif line.startswith('@@note '):
        print(line[7:], file=sys.stderr, flush=True)
    elif not line.startswith('@@'):
        print(line, file=sys.stderr, flush=True)


ROOT = ''  # workspace root, stripped from paths in failure output (set by cli.main)


def show_tail(lines, n=25, title=''):
    """Print the last n meaningful lines of a failed step, indented, with relative paths."""
    noise = ('gmake', 'make[', 'make:', '---')
    keep = [x for x in lines if x.strip() and not x.lstrip().startswith(noise)][-n:]
    if ROOT:
        keep = [x.replace(ROOT + '/', '') for x in keep]
    if title:
        print(paint(f'  {title}', GRAY), file=sys.stderr)
    for x in keep:
        print(paint('  │ ', RULE) + x, file=sys.stderr)


# ── brand ───────────────────────────────────────────────────────────────────

# Two-row half-block wordmark for headers that must stay small (TUI).
WORDMARK = [
    '█▀▄ ▀█▀ ▀█▀',
    '█▄▀ ▄█▄  █ ',
]

# The DIT ROBOTICS MOTD from DIT-Scripts (figlet "slant"), with the brand gradient.
LOGO = [
    r'    ____  __________   ____        __          __  _          ',
    r'   / __ \/  _/_  __/  / __ \____  / /_  ____  / /_(_)_________',
    r'  / / / // /  / /    / /_/ / __ \/ __ \/ __ \/ __/ / ___/ ___/',
    r' / /_/ // /  / /    / _, _/ /_/ / /_/ / /_/ / /_/ / /__(__  ) ',
    r'/_____/___/ /_/    /_/ |_|\____/_.___/\____/\__/_/\___/____/  ',
]


def logo_color(row, col, lines):
    """256-color index for one character of `lines` (diagonal gradient)."""
    w = max(len(x) for x in lines)
    t = (col + 2 * (len(lines) - 1 - row)) / (w + 2 * len(lines))
    return LOGO_RAMP[min(int(t * len(LOGO_RAMP)), len(LOGO_RAMP) - 1)]


def banner(subtitle=''):
    """The DIT ROBOTICS logo with its gradient; for install / init / doctor only."""
    for i, line in enumerate(LOGO):
        out, run, color = '', '', None
        for j, ch in enumerate(line.rstrip()):  # one escape per color run, not per char
            c = logo_color(i, j, LOGO)
            if c != color and run:
                out += paint(run, color, bold=True)
                run = ''
            run, color = run + ch, c
        print(out + paint(run, color, bold=True), file=sys.stderr)
    if subtitle:
        print(paint(f'  {subtitle}', GRAY), file=sys.stderr)
    print(file=sys.stderr)


def gradient(text):
    """Text with the brand ramp from left to right (one-line headers)."""
    n = max(1, len(text))
    return ''.join(
        paint(ch, LOGO_RAMP[min(i * len(LOGO_RAMP) // n, len(LOGO_RAMP) - 1)], bold=True)
        for i, ch in enumerate(text)
    )
