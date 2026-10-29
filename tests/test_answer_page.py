import os
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import answer_page as ap  # noqa: E402

TCP = open(os.path.join(ROOT, 'examples', 'tcp.md'), encoding='utf-8').read()


class Parse(unittest.TestCase):
    def test_frontmatter_intro_and_panels(self):
        doc = ap.parse(TCP)
        self.assertEqual(doc['meta']['title'], 'TCP three-way handshake')
        self.assertEqual(doc['meta']['cols'], '3')
        self.assertTrue(doc['intro'].startswith('TCP opens a connection'))
        self.assertEqual([p['title'] for p in doc['panels']],
                         ['Three-way handshake', 'Why three messages', 'State changes', 'Flags'])
        self.assertEqual([p['tag'] for p in doc['panels']], ['A', 'B', 'C', 'D'])
        self.assertEqual(doc['panels'][0]['span'], 2)
        self.assertEqual(doc['panels'][0]['meta'], 'open')


class Diagrams(unittest.TestCase):
    def test_sequence(self):
        svg = ap.sequence_svg('participants: Client, Server\nnote Server: LISTEN\nClient -> Server: SYN, seq=x\n'
                              'Server --> Client: SYN+ACK\nnote Client, Server: ESTABLISHED')
        root = ET.fromstring(svg)
        self.assertEqual(len([e for e in root.iter() if e.get('class') == 'msg']), 1)
        self.assertEqual(len([e for e in root.iter() if e.get('class') == 'msg dash']), 1)
        self.assertIn('ESTABLISHED', svg)

    def test_flow_nodes_shapes_and_layers(self):
        g = ap.flow_graph('(CLOSED) -> LISTEN: passive open\nLISTEN -> SYN_RCVD\n(CLOSED) --> SYN_SENT\n'
                          'SYN_SENT -> *ESTABLISHED\nSYN_RCVD -> *ESTABLISHED\nA & B -> {Valid?}\nX -> [(DB)]')
        n = g['nodes']
        self.assertEqual(n['CLOSED']['shape'], 'round')
        self.assertTrue(n['ESTABLISHED']['hot'])
        self.assertEqual(n['Valid?']['shape'], 'diamond')
        self.assertEqual(n['DB']['shape'], 'cylinder')
        self.assertEqual(n['CLOSED']['layer'], 0)
        self.assertEqual(n['ESTABLISHED']['layer'], 3)
        self.assertIn(('CLOSED', 'SYN_SENT', '', True), g['edges'])
        ET.fromstring(ap.flow_svg('A -> B\nB -> C', 'LR'))

    def test_flow_cycle_does_not_hang(self):
        g = ap.flow_graph('A -> B\nB -> A')
        self.assertEqual(sorted(v['layer'] for v in g['nodes'].values()), [0, 1])


class Lint(unittest.TestCase):
    def test_rules(self):
        text = ('We utilize a cache in order to go fast. ' +
                'This sentence has far too many words in it because it keeps going on and on about nothing at all here and then it goes on for a while more.\n\n'
                '1. The file is deleted by the script.')
        rules = [w['rule'] for w in ap.lint(text)]
        self.assertIn('word', rules)
        self.assertIn('sentence-length', rules)
        self.assertIn('passive-step', rules)

    def test_code_and_no_rows_are_skipped(self):
        self.assertEqual(ap.lint('Use `utilize_everything()` here.\n| FIN | no utilize it |'), [])

    def test_tcp_example_is_clean(self):
        self.assertEqual(ap.lint_doc(ap.parse(TCP)), [])


class Render(unittest.TestCase):
    def test_single_file_page(self):
        page = ap.render(ap.parse(TCP))
        self.assertTrue(page.startswith('<!doctype html>'))
        self.assertNotRegex(page, r'(?:src|href)="https?://')
        self.assertEqual(page.count('<svg'), 2)
        self.assertIn('class="chip ok"', page)
        self.assertIn('class="callout warn"', page)
        self.assertIn('grid-column:span 2', page)
        self.assertIn('<ol>', page)

    def test_ladder_picks_text_for_small_answers(self):
        self.assertEqual(ap.pick_rung(ap.parse('Short answer. It is fine.')), 'text')
        self.assertEqual(ap.pick_rung(ap.parse(TCP)), 'page')

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'tcp.html')
            p = subprocess.run([sys.executable, os.path.join(ROOT, 'answer_page.py'), os.path.join(ROOT, 'examples', 'tcp.md'),
                                '-o', out], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('0 style warnings', p.stdout)
            self.assertTrue(os.path.getsize(out) > 3000)


if __name__ == '__main__':
    unittest.main()
