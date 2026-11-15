#!/usr/bin/env python3
"""ANSI terminal output -> SVG terminal window (text stays text: selectable, searchable).

    ditx --help | FORCE_COLOR=1 ... > out.ansi
    python3 tools/docs/termshot.py out.ansi --cmd 'ditx --help' --cols 100 -o help.svg

What it does:
  - replays the output on a fixed grid of `cols` cells (like a terminal: \\r, \\b, \\t,
    erase-in-line, cursor left/right/column, autowrap), so spinners that redraw a line
    end up as their final state
  - renders SGR: 16 / 256 / truecolor fore- and background, bold, dim, italic, underline,
    strikethrough, reverse; every other escape sequence (OSC, cursor show/hide, ...) is dropped
  - every text run gets an exact x and textLength, so columns line up with any monospace
    font (wide CJK characters take two cells)
  - box-drawing lines and block elements are drawn as shapes that fill the whole cell,
    like a terminal does, so borders and block logos join up across rows (a font glyph
    is shorter than the line height and would leave gaps)
  - a window frame: rounded corners, title bar with three dots and a title, the brand's
    dark theme, and a first line with the prompt and the command

Standard library only.
"""

import argparse
from dataclasses import dataclass, replace
import hashlib
import re
import sys
import unicodedata

# ── theme ────────────────────────────────────────────────────────────────────

# 16 ANSI colors of the DIT neon theme (what a terminal with this theme would show);
# indices 16-255 are the fixed xterm values, which is what ditx itself uses.
PALETTE16 = [
    '#1c1d33',  # 0 black
    '#ff4d6d',  # 1 red
    '#5fd787',  # 2 green
    '#ffd75f',  # 3 yellow
    '#5f87ff',  # 4 blue
    '#ff3fbf',  # 5 magenta
    '#00d7ff',  # 6 cyan (accent)
    '#c9cbe0',  # 7 white
    '#5c6085',  # 8 bright black
    '#ff7a93',  # 9 bright red
    '#87ffaf',  # 10 bright green
    '#ffe58a',  # 11 bright yellow
    '#87afff',  # 12 bright blue
    '#ff7fdf',  # 13 bright magenta
    '#5fffff',  # 14 bright cyan
    '#ffffff',  # 15 bright white
]
FG = '#dcdeef'
BG = '#0e0f1d'
CHROME = '#171829'  # title bar
BORDER = '#2b2d48'
TITLE_FG = '#8a8db0'
DOTS = ['#ff5f57', '#febc2e', '#28c840']
# brand ramp under the title bar: DIT red -> magenta -> violet -> cyan
BRAND_RAMP = ['#d70000', '#ff005f', '#ff00af', '#af5fff', '#5f5fff', '#00afff', '#00d7ff']
ACCENT_SGR = '1;38;5;45'  # prompt `$`

FONT_FAMILY = "'JetBrains Mono', 'Cascadia Code', 'DejaVu Sans Mono', monospace"
FONT_SIZE = 14
CELL_W = FONT_SIZE * 0.6  # advance width of the fonts above
LINE_H = round(FONT_SIZE * 1.3, 2)
PAD_X, PAD_Y = 18, 14
TITLE_H = 36
RADIUS = 10


def xterm256(n):
    """Hex color of xterm-256 index n (16-231: 6x6x6 cube, 232-255: grays)."""
    if n < 16:
        return PALETTE16[n]
    if n < 232:
        n -= 16
        levels = [0, 95, 135, 175, 215, 255]
        r, g, b = levels[n // 36], levels[n // 6 % 6], levels[n % 6]
        return f'#{r:02x}{g:02x}{b:02x}'
    v = 8 + 10 * (n - 232)
    return f'#{v:02x}{v:02x}{v:02x}'


# ── terminal model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Style:
    fg: str | None = None  # hex color, None = default
    bg: str | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    reverse: bool = False

    def colors(self):
        """(fg, bg) as drawn; bg None = window background."""
        fg, bg = self.fg or FG, self.bg
        if self.reverse:
            fg, bg = bg or BG, fg
        return fg, bg


PLAIN = Style()


def _color(params, i):
    """Parse an extended color at params[i] (after 38/48). Returns (hex or None, next i)."""
    if i < len(params) and params[i] == 5 and i + 1 < len(params):
        return xterm256(max(0, min(255, params[i + 1]))), i + 2
    if i < len(params) and params[i] == 2 and i + 3 < len(params):
        r, g, b = (max(0, min(255, v)) for v in params[i + 1 : i + 4])
        return f'#{r:02x}{g:02x}{b:02x}', i + 4
    return None, len(params)


def apply_sgr(style, params):
    """New Style after `ESC [ params m`."""
    if not params:
        params = [0]
    i = 0
    s = style
    while i < len(params):
        p = params[i]
        i += 1
        if p == 0:
            s = PLAIN
        elif p == 1:
            s = replace(s, bold=True)
        elif p == 2:
            s = replace(s, dim=True)
        elif p == 3:
            s = replace(s, italic=True)
        elif p in (4, 21):
            s = replace(s, underline=True)
        elif p == 7:
            s = replace(s, reverse=True)
        elif p == 9:
            s = replace(s, strike=True)
        elif p == 22:
            s = replace(s, bold=False, dim=False)
        elif p == 23:
            s = replace(s, italic=False)
        elif p == 24:
            s = replace(s, underline=False)
        elif p == 27:
            s = replace(s, reverse=False)
        elif p == 29:
            s = replace(s, strike=False)
        elif 30 <= p <= 37:
            s = replace(s, fg=PALETTE16[p - 30])
        elif 90 <= p <= 97:
            s = replace(s, fg=PALETTE16[p - 90 + 8])
        elif p == 39:
            s = replace(s, fg=None)
        elif 40 <= p <= 47:
            s = replace(s, bg=PALETTE16[p - 40])
        elif 100 <= p <= 107:
            s = replace(s, bg=PALETTE16[p - 100 + 8])
        elif p == 49:
            s = replace(s, bg=None)
        elif p in (38, 48):
            color, i = _color(params, i)
            if color:
                s = replace(s, fg=color) if p == 38 else replace(s, bg=color)
    return s


def char_width(ch):
    if unicodedata.combining(ch) or ch in '​‌‍︎️':
        return 0
    return 2 if unicodedata.east_asian_width(ch) in 'WF' else 1


# ESC [ params final | ESC ] ... (BEL | ESC \) | ESC P/X/^/_ ... ESC \ | ESC (charset) x | ESC x
_ESCAPE = re.compile(
    r'\x1b\[(?P<csi>[0-?]*)[ -/]*(?P<final>[@-~])'
    r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?'
    r'|\x1b[PX^_][^\x1b]*(?:\x1b\\)?'
    r'|\x1b[()*+#%][\x20-\x7e]?'
    r'|\x1b[\x20-\x7e]?'
)

WIDE_TAIL = ''  # cell taken by the right half of a wide character


class Screen:
    """A grid of `cols` cells per row that grows downwards (no scrolling off the top)."""

    def __init__(self, cols):
        self.cols = cols
        self.rows = [[]]
        self.row = self.col = 0
        self.style = PLAIN

    def _line(self):
        while len(self.rows) <= self.row:
            self.rows.append([])
        line = self.rows[self.row]
        while len(line) < self.col:
            line.append((' ', PLAIN))
        return line

    def _put(self, ch, w):
        if w == 0:  # combining mark / joiner: attach to the previous cell
            line = self._line()
            k = min(self.col, len(line)) - 1
            while k >= 0 and line[k][0] == WIDE_TAIL:
                k -= 1
            if k >= 0:
                line[k] = (line[k][0] + ch, line[k][1])
            return
        if self.col + w > self.cols:  # autowrap
            self.row += 1
            self.col = 0
        line = self._line()
        cells = [(ch, self.style)] + [(WIDE_TAIL, self.style)] * (w - 1)
        for k, cell in enumerate(cells):
            pos = self.col + k
            if pos < len(line):
                line[pos] = cell
            else:
                line.append(cell)
        self.col += w

    def _csi(self, params_text, final):
        if params_text.startswith(('?', '>', '<', '=')):
            return  # private modes (cursor show/hide, bracketed paste, ...)
        nums = [int(x) if x.isdigit() else 0 for x in params_text.replace(':', ';').split(';')]
        if params_text == '':
            nums = []
        n = nums[0] if nums else 0
        if final == 'm':
            self.style = apply_sgr(self.style, nums)
        elif final == 'K':
            line = self._line()
            if n == 0:
                del line[self.col :]
            elif n == 1:
                line[: self.col + 1] = [(' ', PLAIN)] * min(len(line), self.col + 1)
            else:
                line.clear()
        elif final == 'G':
            self.col = max(0, min(self.cols - 1, (n or 1) - 1))
        elif final == 'C':
            self.col = min(self.cols - 1, self.col + (n or 1))
        elif final == 'D':
            self.col = max(0, self.col - (n or 1))
        elif final == 'A':
            self.row = max(0, self.row - (n or 1))
        elif final in 'BE':
            self.row += n or 1
            if final == 'E':
                self.col = 0
        elif final == 'F':
            self.row, self.col = max(0, self.row - (n or 1)), 0
        # everything else (scroll regions, screen clears, ...) is ignored

    def feed(self, text):
        pos = 0
        for m in _ESCAPE.finditer(text):
            self._text(text[pos : m.start()])
            if m.group('final'):
                self._csi(m.group('csi'), m.group('final'))
            pos = m.end()
        self._text(text[pos:])

    def _text(self, text):
        for ch in text:
            if ch == '\n':
                self.row += 1
                self.col = 0
            elif ch == '\r':
                self.col = 0
            elif ch == '\b':
                self.col = max(0, self.col - 1)
            elif ch == '\t':
                self.col = min(self.cols - 1, (self.col // 8 + 1) * 8)
            elif ch < ' ' or ch == '\x7f' or 0x80 <= ord(ch) < 0xA0:
                continue  # other control characters
            else:
                self._put(ch, char_width(ch))

    def lines(self):
        """Rows without trailing blanks (and without trailing empty rows)."""
        out = []
        for line in self.rows:
            line = list(line)
            while line and line[-1][0] == ' ' and line[-1][1].colors()[1] is None:
                line.pop()
            out.append(line)
        while out and not out[-1]:
            out.pop()
        return out


# ── SVG ──────────────────────────────────────────────────────────────────────


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _num(v):
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def _runs(line):
    """Split a row into (start cell, n cells, text, style, wide) runs of one style.

    Wide characters get a run of their own so each one sits exactly on its two cells.
    """
    runs = []
    for col, (ch, st) in enumerate(line):
        if ch == WIDE_TAIL:
            continue
        wide = col + 1 < len(line) and line[col + 1][0] == WIDE_TAIL
        last = runs[-1] if runs else None
        if last and not wide and not last[4] and last[3] == st and last[0] + last[1] == col:
            runs[-1] = (last[0], last[1] + 1, last[2] + ch, st, False)
        else:
            runs.append((col, 2 if wide else 1, ch, st, wide))
    return runs


# ── cell shapes ──────────────────────────────────────────────────────────────

# box drawing -> arms (up, right, down, left): 0 none, 1 light, 2 heavy
_ARMS = {}
for _chars, _weight in (('─│┌┐└┘├┤┬┴┼╴╵╶╷', 1), ('━┃┏┓┗┛┣┫┳┻╋╸╹╺╻', 2)):
    for _ch, _dirs in zip(
        _chars,
        'rl ud rd dl ur ul urd udl rdl url urdl l u r d'.split(),
        strict=True,
    ):
        _ARMS[_ch] = tuple(_weight if d in _dirs else 0 for d in 'urdl')
ROUND = {'╭': 'rd', '╮': 'ld', '╯': 'lu', '╰': 'ru'}  # (horizontal, vertical) arm
# block elements -> filled part of the cell (x0, y0, x1, y1 as fractions) and opacity
BLOCKS = {
    '█': (0, 0, 1, 1), '▀': (0, 0, 1, 0.5), '▄': (0, 0.5, 1, 1), '▌': (0, 0, 0.5, 1),
    '▐': (0.5, 0, 1, 1), '▔': (0, 0, 1, 0.125), '▕': (0.875, 0, 1, 1),
}  # fmt: skip
BLOCKS.update({chr(0x2581 + i): (0, 1 - (i + 1) / 8, 1, 1) for i in range(7)})  # ▁..▇
BLOCKS.update({chr(0x2589 + i): (0, 0, (7 - i) / 8, 1) for i in range(7)})  # ▉..▏
QUADS = {  # upper left, upper right, lower left, lower right
    '▖': '0010', '▗': '0001', '▘': '1000', '▙': '1011', '▚': '1001', '▛': '1110',
    '▜': '1101', '▝': '0100', '▞': '0110', '▟': '0111',
}  # fmt: skip
SHADES = {'░': 0.25, '▒': 0.5, '▓': 0.75}
LIGHT_W, HEAVY_W = 1.25, 2.5


def is_shape(ch):
    return ch in _ARMS or ch in ROUND or ch in BLOCKS or ch in QUADS or ch in SHADES


def _shape(ch, n, x, top):
    """(kind, payload) for `n` copies of shape `ch` from cell x: kind 'rect' -> list of
    (x, y, w, h, opacity), kind 1 / 2 (light / heavy) -> SVG path data."""
    w, h = n * CELL_W, LINE_H
    if ch in SHADES:
        return 'rect', [(x, top, w, h, SHADES[ch])]
    if ch in BLOCKS:
        x0, y0, x1, y1 = BLOCKS[ch]
        if x1 - x0 < 1:  # partial width: one piece per cell
            return 'rect', [
                (x + i * CELL_W + x0 * CELL_W, top + y0 * h, (x1 - x0) * CELL_W, (y1 - y0) * h, 1)
                for i in range(n)
            ]
        return 'rect', [(x, top + y0 * h, w, (y1 - y0) * h, 1)]
    if ch in QUADS:
        hw, hh = CELL_W / 2, h / 2
        return 'rect', [
            (x + i * CELL_W + q % 2 * hw, top + q // 2 * hh, hw, hh, 1)
            for i in range(n)
            for q in range(4)
            if QUADS[ch][q] == '1'
        ]
    cy = top + h / 2
    if ch in ROUND:  # quarter curve from the cell center to two edges
        hx, vy = ROUND[ch]
        r = CELL_W / 2
        sx, sy = (1 if hx == 'r' else -1), (1 if vy == 'd' else -1)
        cx = x + r
        return 1, (
            f'M{_num(cx + sx * r)} {_num(cy)}Q{_num(cx)} {_num(cy)} {_num(cx)} {_num(cy + sy * r)}'
            f'V{_num(top + h if sy > 0 else top)}'
        )
    arms = _ARMS[ch]  # one weight per character in the tables above
    if arms in ((0, 1, 0, 1), (0, 2, 0, 2)):  # horizontal run: one line
        return max(arms), f'M{_num(x)} {_num(cy)}H{_num(x + w)}'
    segs = []
    for i in range(n):
        cx = x + i * CELL_W + CELL_W / 2
        ends = ('V', top), ('H', cx + CELL_W / 2), ('V', top + h), ('H', cx - CELL_W / 2)
        segs += [
            f'M{_num(cx)} {_num(cy)}{axis}{_num(v)}'
            for arm, (axis, v) in zip(arms, ends, strict=True)
            if arm
        ]
    return max(arms), ''.join(segs)


def _shape_runs(chars):
    """(offset, n, ch) for each run of one shape character in `chars`."""
    out = []
    for i, ch in enumerate(chars):
        if not is_shape(ch):
            continue
        if out and out[-1][2] == ch and out[-1][0] + out[-1][1] == i:
            out[-1] = (out[-1][0], out[-1][1] + 1, ch)
        else:
            out.append((i, 1, ch))
    return out


def render_svg(text, cols=100, title='', cmd=None, prompt='$'):
    """SVG document (str) for ANSI `text` on a `cols` wide terminal."""
    screen = Screen(cols)
    if cmd is not None:
        screen.feed(f'\x1b[{ACCENT_SGR}m{prompt}\x1b[0m {cmd}\n')
    screen.feed(text.replace('\r\n', '\n'))
    lines = screen.lines() or [[]]

    uid = 't' + hashlib.sha1(f'{cols}\0{title}\0{cmd}\0{text}'.encode()).hexdigest()[:6]
    width = PAD_X * 2 + cols * CELL_W
    body_h = PAD_Y * 2 + len(lines) * LINE_H
    height = TITLE_H + body_h
    classes = {}

    def cls(style):
        fg, _ = style.colors()
        decl = [f'fill:{fg}']
        if style.bold:
            decl.append('font-weight:700')
        if style.italic:
            decl.append('font-style:italic')
        if style.dim:
            decl.append('opacity:0.6')
        deco = [
            d for d, on in (('underline', style.underline), ('line-through', style.strike)) if on
        ]
        if deco:
            decl.append('text-decoration:' + ' '.join(deco))
        key = ';'.join(decl)
        if key not in classes:
            classes[key] = f'{uid}-{len(classes)}'
        return classes[key]

    rects, blocks, lines_, texts = [], [], [], []
    for row, line in enumerate(lines):
        top = TITLE_H + PAD_Y + row * LINE_H
        baseline = top + (LINE_H - FONT_SIZE) / 2 + FONT_SIZE * 0.8
        for col, n, chars, style, wide in _runs(line):
            x = PAD_X + col * CELL_W
            _, bg = style.colors()
            if bg:
                rects.append(
                    f'<rect x="{_num(x)}" y="{_num(top)}" width="{_num(n * CELL_W)}" '
                    f'height="{_num(LINE_H)}" fill="{bg}"/>'
                )
            fg, _ = style.colors()
            for off, k, ch in [] if wide else _shape_runs(chars):
                kind, payload = _shape(ch, k, x + off * CELL_W, top)
                if kind == 'rect':
                    for rx, ry, rw, rh, op in payload:
                        op *= 0.6 if style.dim else 1
                        alpha = f' opacity="{_num(op)}"' if op < 1 else ''
                        blocks.append(
                            f'<rect x="{_num(rx)}" y="{_num(ry)}" width="{_num(rw)}" '
                            f'height="{_num(rh)}" fill="{fg}"{alpha}/>'
                        )
                else:
                    alpha = ' opacity="0.6"' if style.dim else ''
                    lines_.append(
                        f'<path d="{payload}" stroke="{fg}" '
                        f'stroke-width="{LIGHT_W if kind == 1 else HEAVY_W}"{alpha}/>'
                    )
            if not wide:
                chars = ''.join(' ' if is_shape(c) else c for c in chars)
            if not chars.strip(' ') and not (style.underline or style.strike):
                continue
            texts.append(
                f'<text x="{_num(x)}" y="{_num(baseline)}" textLength="{_num(n * CELL_W)}" '
                f'lengthAdjust="spacingAndGlyphs" class="{cls(style)}">{_esc(chars)}</text>'
            )

    stops = ''.join(
        f'<stop offset="{_num(i / (len(BRAND_RAMP) - 1))}" stop-color="{c}"/>'
        for i, c in enumerate(BRAND_RAMP)
    )
    css = ''.join(f'.{name}{{{decl}}}' for decl, name in classes.items())
    dots = ''.join(
        f'<circle cx="{PAD_X + 2 + i * 20}" cy="{TITLE_H / 2}" r="6" fill="{c}"/>'
        for i, c in enumerate(DOTS)
    )
    title_svg = (
        f'<text x="{_num(width / 2)}" y="{_num(TITLE_H / 2 + 4.5)}" text-anchor="middle" '
        f'fill="{TITLE_FG}" font-size="13">{_esc(title)}</text>'
        if title
        else ''
    )
    w, h = _num(width), _num(height)
    label = _esc(f'$ {cmd}' if cmd else title or 'terminal').replace('"', '&quot;')
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" xml:space="preserve" role="img" aria-label="{label}">',
        f'<style>.{uid} text{{font-family:{FONT_FAMILY};font-size:{FONT_SIZE}px;'
        f'white-space:pre;font-variant-ligatures:none}}{css}</style>',
        f'<defs><linearGradient id="{uid}-ramp" x1="0" x2="1" y1="0" y2="0">{stops}'
        f'</linearGradient><clipPath id="{uid}-clip"><rect width="{w}" height="{h}" '
        f'rx="{RADIUS}"/></clipPath></defs>',
        f'<g class="{uid}" clip-path="url(#{uid}-clip)">',
        f'<rect width="{w}" height="{h}" fill="{BG}"/>',
        f'<rect width="{w}" height="{TITLE_H}" fill="{CHROME}"/>',
        f'<rect y="{TITLE_H - 2}" width="{w}" height="2" fill="url(#{uid}-ramp)" opacity="0.85"/>',
        dots,
        title_svg,
        *rects,
        # blocks tile without hairline seams; lines keep antialiasing for the round corners
        f'<g shape-rendering="crispEdges">{"".join(blocks)}</g>' if blocks else '',
        f'<g fill="none" stroke-linecap="square">{"".join(lines_)}</g>' if lines_ else '',
        *texts,
        '</g>',
        f'<rect x="0.5" y="0.5" width="{_num(width - 1)}" height="{_num(height - 1)}" '
        f'rx="{RADIUS - 0.5}" fill="none" stroke="{BORDER}"/>',
        '</svg>',
    ]
    return '\n'.join(x for x in out if x) + '\n'


def substitute(text, subs=(), regex_subs=()):
    """Literal OLD=NEW replacements, then (pattern, repl) regex replacements."""
    for old, new in subs:
        text = text.replace(old, new)
    for pattern, repl in regex_subs:
        text = re.sub(pattern, repl, text)
    return text


def _pair(value):
    old, sep, new = value.partition('=')
    if not sep or not old:
        raise argparse.ArgumentTypeError(f'expected OLD=NEW, got {value!r}')
    return old, new


def main(argv=None):
    p = argparse.ArgumentParser(
        prog='termshot', description='ANSI terminal output -> SVG terminal window'
    )
    p.add_argument('input', nargs='?', default='-', help='ANSI text file (default: stdin)')
    p.add_argument('--title', default='', help='window title')
    p.add_argument('--cmd', help='command shown on the first line after the prompt')
    p.add_argument('--cols', type=int, default=100, help='terminal width in cells')
    p.add_argument('--sub', type=_pair, action='append', default=[], metavar='OLD=NEW')
    p.add_argument('--sub-re', type=_pair, action='append', default=[], metavar='REGEX=NEW')
    p.add_argument('-o', '--output', default='-', help='SVG file (default: stdout)')
    a = p.parse_args(argv)
    if a.input == '-':
        text = sys.stdin.buffer.read().decode('utf-8', errors='replace')
    else:
        with open(a.input, 'rb') as f:
            text = f.read().decode('utf-8', errors='replace')
    text = substitute(text, a.sub, a.sub_re)
    cmd = substitute(a.cmd, a.sub, a.sub_re) if a.cmd is not None else None
    svg = render_svg(text, cols=a.cols, title=a.title, cmd=cmd)
    if a.output == '-':
        sys.stdout.write(svg)
    else:
        with open(a.output, 'w', encoding='utf-8', newline='\n') as f:
            f.write(svg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
