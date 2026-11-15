"""tools/docs/termshot.py: ANSI parsing, the cell grid and the SVG it writes.

python3 -m unittest discover -s tools/tests -v
"""

import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'docs'))

import termshot  # noqa: E402
from termshot import PLAIN, Screen, Style, apply_sgr, render_svg, xterm256  # noqa: E402

SVG = '{http://www.w3.org/2000/svg}'


def screen(text, cols=40):
    s = Screen(cols)
    s.feed(text)
    return s


def row_text(s, i=0):
    return ''.join(ch for ch, _ in s.lines()[i])


def texts(svg):
    """[(x, y, text, class)] of every <text> in an SVG string."""
    root = ET.fromstring(svg)
    return [
        (float(t.get('x')), float(t.get('y')), t.text or '', t.get('class'))
        for t in root.iter(SVG + 'text')
    ]


class Sgr(unittest.TestCase):
    def test_reset_and_attributes(self):
        s = apply_sgr(PLAIN, [1, 2, 3, 4, 7, 9])
        self.assertTrue(s.bold and s.dim and s.italic and s.underline and s.reverse and s.strike)
        self.assertEqual(apply_sgr(s, [0]), PLAIN)
        self.assertEqual(apply_sgr(s, []), PLAIN)  # ESC[m == ESC[0m
        s = apply_sgr(s, [22, 23, 24, 27, 29])
        self.assertEqual(s, PLAIN)

    def test_16_colors_use_the_theme(self):
        self.assertEqual(apply_sgr(PLAIN, [31]).fg, termshot.PALETTE16[1])
        self.assertEqual(apply_sgr(PLAIN, [96]).fg, termshot.PALETTE16[14])
        self.assertEqual(apply_sgr(PLAIN, [44]).bg, termshot.PALETTE16[4])
        self.assertEqual(apply_sgr(PLAIN, [101]).bg, termshot.PALETTE16[9])
        self.assertIsNone(apply_sgr(apply_sgr(PLAIN, [31, 41]), [39, 49]).fg)

    def test_256_colors(self):
        self.assertEqual(apply_sgr(PLAIN, [38, 5, 45]).fg, '#00d7ff')  # ditx accent
        self.assertEqual(apply_sgr(PLAIN, [38, 5, 160]).fg, '#d70000')  # DIT red
        self.assertEqual(apply_sgr(PLAIN, [48, 5, 24]).bg, '#005f87')  # selection
        self.assertEqual(xterm256(232), '#080808')
        self.assertEqual(xterm256(255), '#eeeeee')
        self.assertEqual(xterm256(3), termshot.PALETTE16[3])

    def test_truecolor_and_combined(self):
        s = apply_sgr(PLAIN, [1, 38, 2, 255, 0, 175, 48, 2, 1, 2, 3])
        self.assertEqual((s.fg, s.bg, s.bold), ('#ff00af', '#010203', True))

    def test_colon_subparameters(self):
        s = screen('\x1b[38:5:203mx')
        self.assertEqual(s.lines()[0][0][1].fg, xterm256(203))

    def test_truncated_extended_color_is_ignored(self):
        self.assertEqual(apply_sgr(PLAIN, [38, 5]), PLAIN)

    def test_reverse_swaps_default_colors(self):
        fg, bg = Style(reverse=True).colors()
        self.assertEqual((fg, bg), (termshot.BG, termshot.FG))


class Grid(unittest.TestCase):
    def test_plain_text_and_newlines(self):
        s = screen('ab\ncd\n\n')
        self.assertEqual([row_text(s, i) for i in range(2)], ['ab', 'cd'])
        self.assertEqual(len(s.lines()), 2)  # trailing empty rows dropped

    def test_carriage_return_and_erase_line_keep_the_final_spinner_state(self):
        s = screen('⠋ build  main\r\x1b[K⠙ build  main\r\x1b[K✓ build  3 packages\n')
        self.assertEqual(row_text(s), '✓ build  3 packages')

    def test_carriage_return_overwrites_in_place(self):
        self.assertEqual(row_text(screen('hello\rJ')), 'Jello')

    def test_other_escapes_are_stripped(self):
        s = screen('\x1b[?25la\x1b]8;;https://x.y\x07link\x1b]8;;\x07\x1b(Bb\x1b[?25h\x1b7c')
        self.assertEqual(row_text(s), 'alinkbc')

    def test_cursor_movement(self):
        self.assertEqual(row_text(screen('abcdef\x1b[3Dx')), 'abcxef')
        self.assertEqual(row_text(screen('abc\x1b[6Gx')), 'abc  x')
        self.assertEqual(row_text(screen('ab\x08c')), 'ac')
        self.assertEqual(row_text(screen('a\tb')), 'a       b')

    def test_wide_characters_take_two_cells(self):
        s = screen('\u4e2da')
        line = s.lines()[0]
        self.assertEqual(len(line), 3)
        self.assertEqual(line[1][0], termshot.WIDE_TAIL)

    def test_combining_marks_join_the_previous_cell(self):
        line = screen('éx').lines()[0]
        self.assertEqual([c for c, _ in line], ['é', 'x'])

    def test_autowrap_at_cols(self):
        s = screen('abcdefgh', cols=5)
        self.assertEqual([row_text(s, 0), row_text(s, 1)], ['abcde', 'fgh'])

    def test_wide_char_does_not_split_across_the_edge(self):
        s = screen('abcd\u4e2d', cols=5)
        self.assertEqual([row_text(s, 0), row_text(s, 1)], ['abcd', '\u4e2d'])

    def test_control_characters_dropped(self):
        self.assertEqual(row_text(screen('a\x07\x00b')), 'ab')

    def test_trailing_blanks_trimmed_unless_colored(self):
        self.assertEqual(len(screen('ab   ').lines()[0]), 2)
        self.assertEqual(len(screen('ab\x1b[44m  \x1b[0m').lines()[0]), 4)


class Svg(unittest.TestCase):
    def test_well_formed_with_frame_and_prompt(self):
        svg = render_svg('\x1b[1;38;5;78m✓\x1b[0m ok\n', cols=30, title='~/DIT-X', cmd='ditx x')
        root = ET.fromstring(svg)
        self.assertEqual(root.get('{http://www.w3.org/XML/1998/namespace}space'), 'preserve')
        self.assertEqual(len(list(root.iter(SVG + 'circle'))), 3)  # window dots
        t = texts(svg)
        self.assertEqual(t[0][2], '~/DIT-X')  # title
        self.assertEqual(t[1][2], '$')  # prompt, then the command on the same row
        self.assertEqual(t[2][2], ' ditx x')
        self.assertEqual(t[1][1], t[2][1])
        self.assertIn('✓', [x[2] for x in t])

    def test_cells_are_positioned_on_a_fixed_grid(self):
        svg = render_svg('ab\x1b[31mcd\x1b[0m  \x1b[32me\n', cols=20)
        runs = [x for x in texts(svg)]
        xs = {text.strip(): x for x, _, text, _ in runs}
        cw = termshot.CELL_W
        self.assertAlmostEqual(xs['cd'] - xs['ab'], 2 * cw, places=1)
        self.assertAlmostEqual(xs['e'] - xs['ab'], 6 * cw, places=1)
        for el in ET.fromstring(svg).iter(SVG + 'text'):
            if el.get('textLength'):
                cells = len(el.text)
                self.assertAlmostEqual(float(el.get('textLength')), cells * cw, places=1)

    def test_wide_char_gets_two_cells(self):
        svg = render_svg('\u4e2dx', cols=10)
        el = [e for e in ET.fromstring(svg).iter(SVG + 'text') if e.text == '\u4e2d'][0]
        self.assertAlmostEqual(float(el.get('textLength')), 2 * termshot.CELL_W, places=1)

    def test_escapes_xml_special_characters(self):
        svg = render_svg('<a & b>\n', cols=20)
        self.assertIn('&lt;a &amp; b&gt;', svg)
        ET.fromstring(svg)

    def test_styles_become_classes(self):
        svg = render_svg('\x1b[1;3;4;38;5;45mx\x1b[0m\x1b[2my\n', cols=10)
        style = re.search(r'<style>(.*?)</style>', svg, re.S)[1]
        self.assertIn(
            'fill:#00d7ff;font-weight:700;font-style:italic;text-decoration:underline', style
        )
        self.assertIn('opacity:0.6', style)

    def test_background_rects(self):
        svg = render_svg('\x1b[48;5;24m sel \x1b[0m\n', cols=10)
        self.assertIn('fill="#005f87"', svg)

    def test_width_follows_cols_and_height_the_lines(self):
        a = ET.fromstring(render_svg('x\n', cols=80))
        b = ET.fromstring(render_svg('x\ny\n', cols=100))
        self.assertLess(float(a.get('width')), float(b.get('width')))
        self.assertLess(float(a.get('height')), float(b.get('height')))

    def test_deterministic(self):
        self.assertEqual(render_svg('a\n', cmd='x'), render_svg('a\n', cmd='x'))


class Cli(unittest.TestCase):
    def test_file_to_file_with_substitutions(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, 'in.ansi'), os.path.join(d, 'out.svg')
            with open(src, 'w', encoding='utf-8') as f:
                f.write('/home/alice/ws ok 20261115-123456\n')
            rc = termshot.main(
                [
                    src,
                    '--cmd',
                    'ls /home/alice/ws',
                    '--cols',
                    '50',
                    '--title',
                    't',
                    '--sub',
                    '/home/alice/ws=~/DIT-X',
                    '--sub-re',
                    r'\d{8}-\d{6}=TIME',
                    '-o',
                    dst,
                ]
            )
            self.assertEqual(rc, 0)
            with open(dst, encoding='utf-8') as f:
                svg = f.read()
        self.assertNotIn('alice', svg)
        self.assertIn('~/DIT-X ok TIME', svg)

    def test_stdin_to_stdout(self):
        stdin = mock.Mock(buffer=io.BytesIO(b'\x1b[32mhi\x1b[0m\n'))
        out = io.StringIO()
        with mock.patch.object(sys, 'stdin', stdin), mock.patch.object(sys, 'stdout', out):
            self.assertEqual(termshot.main(['--cols', '20']), 0)
        self.assertIn('>hi</text>', out.getvalue())

    def test_bad_sub_is_a_usage_error(self):
        with self.assertRaises(SystemExit), mock.patch.object(sys, 'stderr', io.StringIO()):
            termshot.main(['--sub', 'novalue'])


if __name__ == '__main__':
    unittest.main()
