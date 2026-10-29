#!/usr/bin/env python3
"""answer-page: turn a short Markdown draft into a one-page HTML answer with diagrams, and check the writing.

Draft format and the STE writing rules follow QingYunA/answer-me-with-html (MIT); the "pick the lowest rung that
works" step follows ChangWenC/understanding-ladder (MIT) and undefined-ui/explain-skill (MIT).
"""
import argparse
import html
import re
import sys

E = html.escape

# ---------- parse ----------

PANEL_RE = re.compile(r'^##\s+(?:([A-Z])\s+)?(.*?)\s*(?:\{([^}]*)\})?\s*$')


def parse(text):
    meta, body = {}, text.replace('\r\n', '\n')
    if body.startswith('---\n'):
        head, _, body = body[4:].partition('\n---\n')
        for line in head.splitlines():
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip()
    intro, panels, cur = [], [], None
    for line in body.split('\n'):
        m = PANEL_RE.match(line)
        if m:
            attrs = dict(re.findall(r'(\w+)="?([^"\s]*)"?', m.group(3) or ''))
            cur = {'tag': m.group(1) or '', 'title': m.group(2), 'span': int(attrs.get('span', 1)),
                   'meta': attrs.get('meta', ''), 'lines': []}
            panels.append(cur)
        else:
            (cur['lines'] if cur else intro).append(line)
    for p in panels:
        p['blocks'] = blocks('\n'.join(p.pop('lines')))
    return {'meta': meta, 'intro': '\n'.join(intro).strip(), 'panels': panels}


def blocks(text):
    """Split into ('md', text) and (lang, args, body) fenced blocks."""
    out, md, fence = [], [], None
    for line in text.split('\n'):
        if fence is None and line.startswith('```'):
            if md:
                out.append(('md', '\n'.join(md).strip(), ''))
                md = []
            head = line[3:].strip().split(None, 1)
            fence = [head[0] if head else '', head[1] if len(head) > 1 else '', []]
        elif fence is not None and line.startswith('```'):
            out.append((fence[0], fence[1], '\n'.join(fence[2])))
            fence = None
        elif fence is not None:
            fence[2].append(line)
        else:
            md.append(line)
    if md and '\n'.join(md).strip():
        out.append(('md', '\n'.join(md).strip(), ''))
    return out

# ---------- markdown ----------

STATUS = re.compile(r'^(ok|no|warn|✓|✗|⚠)\s+')
CHIP = {'ok': 'ok', '✓': 'ok', 'no': 'no', '✗': 'no', 'warn': 'warn', '⚠': 'warn'}


def inline(s):
    s = E(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', s)
    return re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)


def cell(c):
    m = STATUS.match(c)
    return '<span class="chip %s">%s</span> %s' % (CHIP[m.group(1)], m.group(1), inline(c[m.end():])) if m else inline(c)


def markdown(text):
    out, lines, i = [], text.split('\n'), 0
    while i < len(lines):
        t = lines[i].strip()
        if not t:
            i += 1
        elif t.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            body = [r for r in rows[1:] if not all(re.fullmatch(r':?-+:?', c) for c in r)]
            out.append('<table><tr>%s</tr>%s</table>' % (''.join('<th>%s</th>' % inline(c) for c in rows[0]),
                       ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % cell(c) for c in r) for r in body)))
        elif re.match(r'^(\d+[.)]|[-*+])\s', t):
            tag = 'ol' if t[0].isdigit() else 'ul'
            items = []
            while i < len(lines) and re.match(r'^\s*(\d+[.)]|[-*+])\s', lines[i]):
                items.append(re.sub(r'^\s*(\d+[.)]|[-*+])\s+', '', lines[i]))
                i += 1
            out.append('<%s>%s</%s>' % (tag, ''.join('<li>%s</li>' % inline(x) for x in items), tag))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r'^\s*(\||\d+[.)]\s|[-*+]\s)', lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append('<p>%s</p>' % inline(' '.join(para)))
    return ''.join(out)

# ---------- flow diagram ----------

EDGE_RE = re.compile(r'^(.+?)\s*(-->|->)\s*(.+?)(?:\s*:\s*(.*))?$')
SHAPES = [('[(', ')]', 'cylinder'), ('(', ')', 'round'), ('{', '}', 'diamond'), ('[', ']', 'rect')]


def node(raw, nodes):
    s = raw.strip()
    hot = s.startswith('*')
    s = s.lstrip('*').strip()
    shape = 'rect'
    for o, c, name in SHAPES:
        if s.startswith(o) and s.endswith(c):
            s, shape = s[len(o):-len(c)].strip(), name
            break
    n = nodes.setdefault(s, {'shape': 'rect', 'hot': False, 'layer': 0})
    n['shape'] = shape if shape != 'rect' else n['shape']
    n['hot'] = n['hot'] or hot
    return s


def flow_graph(src):
    nodes, edges = {}, []
    for line in src.split('\n'):
        line = line.strip()
        if not line or line.startswith('group ') or line.startswith('%%'):
            continue
        m = EDGE_RE.match(line)
        if not m:
            node(line, nodes)
            continue
        dst = node(m.group(3), nodes)
        for src_name in m.group(1).split('&'):
            edges.append((node(src_name, nodes), dst, (m.group(4) or '').strip(), m.group(2) == '-->'))
    # longest-path layering; edges that close a cycle are ignored for layout
    order, state = [], {}

    def visit(v):
        state[v] = 1
        for a, b, _, _ in edges:
            if a == v and state.get(b) is None:
                visit(b)
        state[v] = 2
        order.append(v)
    for v in nodes:
        if state.get(v) is None and not any(b == v for _, b, _, _ in edges):
            visit(v)
    for v in nodes:
        if state.get(v) is None:
            visit(v)
    rank = {v: i for i, v in enumerate(reversed(order))}
    for v in reversed(order):
        for a, b, _, _ in edges:
            if a == v and rank[b] > rank[a]:
                nodes[b]['layer'] = max(nodes[b]['layer'], nodes[a]['layer'] + 1)
    return {'nodes': nodes, 'edges': edges}


def text_w(s, size=13):
    return sum(size * (1.0 if ord(ch) > 0x2E80 else 0.6) for ch in s)


def flow_svg(src, direction='LR'):
    g = flow_graph(src)
    nodes, lr = g['nodes'], direction.upper() in ('LR', 'RL')
    layers = {}
    for name, n in nodes.items():
        layers.setdefault(n['layer'], []).append(name)
        n['w'], n['h'] = max(70, text_w(name) + 28), 38
    gap_main, gap_cross = 70, 26
    pos, main = {}, 20
    for layer in sorted(layers):
        names = layers[layer]
        thick = max((nodes[v]['w'] if lr else nodes[v]['h']) for v in names)
        cross = 20
        for v in names:
            n = nodes[v]
            pos[v] = (main + (thick - n['w']) / 2, cross) if lr else (cross, main + (thick - n['h']) / 2)
            cross += (n['h'] if lr else n['w']) + gap_cross
        labels = [text_w(lb, 12) for a, b, lb, _ in g['edges'] if nodes[a]['layer'] == layer and lb]
        main += thick + max([gap_main] + [w + 24 for w in labels] if lr else [gap_main])
    for v, (x, y) in pos.items():
        nodes[v]['x'], nodes[v]['y'] = x, y
    W = max(n['x'] + n['w'] for n in nodes.values()) + 20
    H = max(n['y'] + n['h'] for n in nodes.values()) + 20
    out = ['<svg xmlns="http://www.w3.org/2000/svg" class="dia" viewBox="0 0 %d %d" width="%d">' % (W, H, W),
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           '<path d="M0,0 L10,5 L0,10 z" class="ah"/></marker></defs>']
    for a, b, label, dash in g['edges']:
        A, B = nodes[a], nodes[b]
        if lr:
            x1, y1, x2, y2 = A['x'] + A['w'], A['y'] + A['h'] / 2, B['x'], B['y'] + B['h'] / 2
            if B['x'] <= A['x']:  # back edge: route below
                x1, x2 = A['x'] + A['w'] / 2, B['x'] + B['w'] / 2
                y1, y2 = A['y'] + A['h'], B['y'] + B['h']
        else:
            x1, y1, x2, y2 = A['x'] + A['w'] / 2, A['y'] + A['h'], B['x'] + B['w'] / 2, B['y']
        out.append('<line class="edge%s" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" marker-end="url(#ah)"/>'
                   % (' dash' if dash else '', x1, y1, x2, y2))
        if label:
            out.append('<text class="elabel" x="%.1f" y="%.1f">%s</text>' % ((x1 + x2) / 2, (y1 + y2) / 2 - 6, E(label)))
    for name, n in nodes.items():
        x, y, w, h = n['x'], n['y'], n['w'], n['h']
        cls = 'node' + (' hot' if n['hot'] else '')
        if n['shape'] == 'diamond':
            out.append('<polygon class="%s" points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f"/>'
                       % (cls, x + w / 2, y - 6, x + w + 8, y + h / 2, x + w / 2, y + h + 6, x - 8, y + h / 2))
        elif n['shape'] == 'cylinder':
            out.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" ry="9"/>' % (cls, x, y, w, h, w / 2))
        else:
            out.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d"/>'
                       % (cls, x, y, w, h, 19 if n['shape'] == 'round' else 6))
        out.append('<text class="ntext" x="%.1f" y="%.1f">%s</text>' % (x + w / 2, y + h / 2 + 4.5, E(name)))
    return '\n'.join(out + ['</svg>'])

# ---------- sequence diagram ----------

def sequence_svg(src):
    parts, rows = [], []
    for line in src.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('participants:'):
            parts += [p.strip() for p in line[13:].split(',') if p.strip() not in parts]
        elif line.startswith('note '):
            who, _, msg = line[5:].partition(':')
            rows.append(('note', [w.strip() for w in who.split(',')], msg.strip()))
        else:
            m = re.match(r'^(.+?)\s*(-->|->)\s*(.+?)\s*:\s*(.*)$', line)
            if m:
                rows.append(('msg', [m.group(1).strip(), m.group(3).strip()], m.group(4), m.group(2) == '-->'))
    for r in rows:
        parts += [p for p in r[1] if p not in parts]
    colw = max(170, max([text_w(r[2]) + 40 for r in rows] or [0]))
    X = {p: 20 + colw * (i + 0.5) for i, p in enumerate(parts)}
    W, H = int(colw * len(parts) + 40), 70 + 46 * len(rows) + 20
    out = ['<svg xmlns="http://www.w3.org/2000/svg" class="dia" viewBox="0 0 %d %d" width="%d">' % (W, H, W),
           '<defs><marker id="sh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           '<path d="M0,0 L10,5 L0,10 z" class="ah"/></marker></defs>']
    for p, x in X.items():
        out.append('<line class="life" x1="%.1f" y1="44" x2="%.1f" y2="%d"/>' % (x, x, H - 10))
        out.append('<rect class="node" x="%.1f" y="10" width="%.1f" height="34" rx="6"/>' % (x - (text_w(p) + 28) / 2, text_w(p) + 28))
        out.append('<text class="ntext" x="%.1f" y="32">%s</text>' % (x, E(p)))
    for i, r in enumerate(rows):
        y = 80 + 46 * i
        if r[0] == 'note':
            xs = [X[w] for w in r[1]]
            w = max(text_w(r[2]) + 24, max(xs) - min(xs) + 60)
            cx = (min(xs) + max(xs)) / 2
            out.append('<rect class="note" x="%.1f" y="%d" width="%.1f" height="28" rx="4"/>' % (cx - w / 2, y - 18, w))
            out.append('<text class="ntext" x="%.1f" y="%d">%s</text>' % (cx, y + 1, E(r[2])))
        else:
            a, b = X[r[1][0]], X[r[1][1]]
            out.append('<line class="msg%s" x1="%.1f" y1="%d" x2="%.1f" y2="%d" marker-end="url(#sh)"/>'
                       % (' dash' if r[3] else '', a, y, b + (-4 if b > a else 4), y))
            out.append('<text class="elabel" x="%.1f" y="%d">%s</text>' % ((a + b) / 2, y - 7, E(r[2])))
    return '\n'.join(out + ['</svg>'])

# ---------- STE writing check ----------

LIMITS = {'procedural': 20, 'descriptive': 25}
MAX_SENTENCES = 6
WORDS = {'utilize': 'use', 'utilise': 'use', 'utilization': 'use', 'commence': 'start', 'commenced': 'started',
         'prior to': 'before', 'in order to': 'to', 'approximately': 'about', 'ensure': 'make sure',
         'replenish': 'fill', 'terminate': 'stop', 'facilitate': 'help', 'leverage': 'use', 'numerous': 'many',
         'subsequently': 'then', 'endeavor': 'try', 'ascertain': 'find', 'sufficient': 'enough',
         'demonstrate': 'show', 'assist': 'help', 'obtain': 'get', 'initiate': 'start', 'modify': 'change',
         'possess': 'have', 'purchase': 'buy', 'in the event that': 'if', 'due to the fact that': 'because',
         'at this point in time': 'now', 'a number of': 'some', 'with regard to': 'about', 'in addition': 'also'}
WORD_RE = [(re.compile(r'\b%s\b' % w.replace(' ', r'\s+'), re.I), w, s) for w, s in sorted(WORDS.items(), key=lambda x: -len(x[0]))]
PASSIVE = re.compile(r'\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(\w+ed|known|done|made|given|taken|seen|written|'
                     r'built|shown|sent|kept|held|found|set|put|run|begun|chosen|driven|broken)\b', re.I)
ABBR = re.compile(r'\b(e\.g|i\.e|etc|vs|cf|approx|Fig|No)\.', re.I)


def clean(t):
    t = re.sub(r'~~[^~]*~~|`[^`]*`|"[^"\n]*"|“[^”\n]*”', '', t)
    return re.sub(r'[*_]{1,3}', '', re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', t))


def sentences(t):
    t = ABBR.sub(lambda m: m.group(0).replace('.', '\0'), t)
    return [s.replace('\0', '.').strip() for s in re.findall(r'[^.!?;]+(?:[.!?;]+|$)', t) if s.strip()]


def check(unit, line, kind, out):
    ss = sentences(unit)
    for s in ss:
        n = len(re.findall(r"[A-Za-z0-9][\w'’-]*", s))
        if n > LIMITS[kind]:
            out.append({'line': line, 'rule': 'sentence-length', 'message': '%s sentence has %d words (max %d)' % (kind, n, LIMITS[kind])})
        for rx, w, sug in WORD_RE:
            if rx.search(s):
                out.append({'line': line, 'rule': 'word', 'message': '"%s"' % w, 'suggestion': sug})
        if kind == 'procedural' and PASSIVE.search(s):
            out.append({'line': line, 'rule': 'passive-step', 'message': 'passive voice in a step: "%s"' % PASSIVE.search(s).group(0),
                        'suggestion': 'say who does it'})
    return len(ss)


def lint(text, start=1):
    out, para = [], None
    for i, raw in enumerate(text.split('\n')):
        t, line = raw.strip(), start + i
        if not t or t.startswith('#') or t.startswith('```'):
            if para and para[1] > MAX_SENTENCES:
                out.append({'line': para[0], 'rule': 'paragraph-length', 'message': 'paragraph has %d sentences (max %d)' % (para[1], MAX_SENTENCES)})
            para = None
            continue
        if t.startswith('|'):
            cells = [c.strip() for c in t.strip('|').split('|')]
            if not re.fullmatch(r'[\s:|-]+', t) and not any(re.match(r'^(no|✗)(\s|$)', c) for c in cells):
                for c in cells:
                    check(clean(STATUS.sub('', c)), line, 'descriptive', out)
            continue
        m = re.match(r'^(?:([-*+])|(\d+)[.)])\s+(.*)$', t)
        if m:
            check(clean(m.group(3)), line, 'procedural' if m.group(2) else 'descriptive', out)
            continue
        n = check(clean(t.lstrip('> ')), line, 'descriptive', out)
        para = [para[0], para[1] + n] if para else [line, n]
    if para and para[1] > MAX_SENTENCES:
        out.append({'line': para[0], 'rule': 'paragraph-length', 'message': 'paragraph has %d sentences (max %d)' % (para[1], MAX_SENTENCES)})
    return out


def lint_doc(doc):
    out = lint(doc['intro'])
    for p in doc['panels']:
        for lang, args, body in p['blocks']:
            if lang == 'md' or lang == 'callout':
                out += [dict(w, panel=p['tag'] or p['title']) for w in lint(args if lang == 'md' else body)]
    return out

# ---------- ladder + render ----------

def pick_rung(doc):
    """Lowest rung that works: plain text unless the answer has structure a page shows better."""
    langs = [b[0] for p in doc['panels'] for b in p['blocks']]
    has_table = any('|' in b[1] for p in doc['panels'] for b in p['blocks'] if b[0] == 'md')
    words = len(re.findall(r'\w+', doc['intro'] + ' '.join(b[1] + b[2] for p in doc['panels'] for b in p['blocks'])))
    return 'page' if {'flow', 'sequence'} & set(langs) or has_table or len(doc['panels']) > 2 or words > 180 else 'text'


def block_html(lang, args, body):
    if lang == 'md':
        return markdown(args)
    if lang == 'flow':
        return '<div class="fig">%s</div>' % flow_svg(body, (args.split() or ['LR'])[0])
    if lang == 'sequence':
        return '<div class="fig">%s</div>' % sequence_svg(body)
    if lang == 'callout':
        kind, _, title = args.partition(' ')
        return '<div class="callout %s"><b>%s</b>%s</div>' % (E(kind or 'info'), E(title), markdown(body))
    return '<pre><code>%s</code></pre>' % E(body)


CSS = """:root{--bg:#f6f7f9;--card:#fff;--fg:#1f2328;--mute:#59636e;--line:#d1d9e0;--acc:#0969da;--hot:#ddf4ff;--ok:#1a7f37;--no:#cf222e;--warn:#9a6700}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#151b23;--fg:#e6edf3;--mute:#9198a1;--line:#3d444d;--acc:#4493f8;--hot:#0c2d6b;--ok:#3fb950;--no:#f85149;--warn:#d29922}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:32px 20px}h1{margin:0;font-size:30px}.sub{color:var(--mute);margin:4px 0 14px}
.lead{font-size:17px;max-width:80ch}.grid{display:grid;gap:16px;grid-template-columns:repeat(var(--cols),minmax(0,1fr));margin-top:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;min-width:0}
.card h2{font-size:16px;margin:0 0 10px;display:flex;gap:8px;align-items:center}.tag{background:var(--acc);color:#fff;border-radius:6px;padding:0 7px;font-size:13px}
.meta{margin-left:auto;color:var(--mute);font-weight:400;font-size:12px}.fig{overflow-x:auto}.dia{max-width:100%;height:auto;font:13px system-ui,sans-serif}
.node{fill:var(--card);stroke:var(--fg);stroke-width:1.3}.node.hot{fill:var(--hot);stroke:var(--acc);stroke-width:2}.note{fill:var(--hot);stroke:none}
.ntext{fill:var(--fg);text-anchor:middle}.elabel{fill:var(--mute);text-anchor:middle;font-size:12px}.ah{fill:var(--fg)}
.edge,.msg{stroke:var(--fg);stroke-width:1.3}.dash{stroke-dasharray:5 4}.life{stroke:var(--line);stroke-dasharray:3 4}
table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}
.chip{font-size:11px;font-weight:700;border-radius:9px;padding:1px 7px;color:#fff;text-transform:uppercase}.chip.ok{background:var(--ok)}.chip.no{background:var(--no)}.chip.warn{background:var(--warn)}
.callout{border-left:4px solid var(--acc);background:var(--bg);border-radius:6px;padding:10px 14px;margin:10px 0}.callout.warn{border-color:var(--warn)}.callout.ok{border-color:var(--ok)}.callout.no{border-color:var(--no)}
.callout p{margin:4px 0 0}code{background:var(--bg);border-radius:4px;padding:0 4px}pre{background:var(--bg);padding:10px;border-radius:8px;overflow:auto}
footer{color:var(--mute);font-size:13px;margin-top:20px}@media(max-width:760px){.grid{grid-template-columns:1fr}.card{grid-column:auto!important}}"""


def render(doc):
    m = doc['meta']
    cards = []
    for p in doc['panels']:
        head = ('<span class="tag">%s</span>' % E(p['tag']) if p['tag'] else '') + E(p['title']) + \
               ('<span class="meta">%s</span>' % E(p['meta']) if p['meta'] else '')
        cards.append('<section class="card" style="grid-column:span %d"><h2>%s</h2>%s</section>'
                     % (p['span'], head, ''.join(block_html(*b) for b in p['blocks'])))
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><style>%s</style></head>\n<body><main><h1>%s</h1>%s%s<div class="grid" style="--cols:%s">%s</div>%s</main></body></html>\n'
            % (E(m.get('title', 'Answer')), CSS, E(m.get('title', 'Answer')),
               '<p class="sub">%s</p>' % E(m['subtitle']) if m.get('subtitle') else '',
               '<div class="lead">%s</div>' % markdown(doc['intro']) if doc['intro'] else '',
               E(m.get('cols', '2')), '\n'.join(cards),
               '<footer>Source: %s</footer>' % E(m['source']) if m.get('source') else ''))


def as_text(doc):
    parts = [doc['meta'].get('title', ''), doc['intro']]
    for p in doc['panels']:
        parts.append(p['title'])
        parts += [b[1] if b[0] == 'md' else b[2] for b in p['blocks']]
    return '\n\n'.join(x for x in parts if x).strip() + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('draft', nargs='?', help='Markdown draft (see examples/)')
    ap.add_argument('-o', '--out', help='HTML file to write (default: draft name with .html)')
    ap.add_argument('--rung', choices=['auto', 'text', 'page'], default='page',
                    help='auto: print plain text when a page would not help (understanding ladder)')
    ap.add_argument('--strict', action='store_true', help='exit 1 when there are style warnings')
    ap.add_argument('--demo', action='store_true', help='render every file in examples/ into docs/')
    a = ap.parse_args(argv)
    if a.demo:
        import glob
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        for path in sorted(glob.glob(os.path.join(here, 'examples', '*.md'))):
            out = os.path.join(here, 'docs', os.path.basename(path)[:-3] + '.html')
            main([path, '-o', out, '--rung', 'auto'])
        return 0
    if not a.draft:
        ap.error('give a draft file, e.g. answer_page.py examples/tcp.md')
    with open(a.draft, encoding='utf-8') as f:
        doc = parse(f.read())
    warnings = lint_doc(doc)
    for w in warnings:
        print('%s L%d [%s] %s%s' % (w.get('panel', 'intro'), w['line'], w['rule'], w['message'],
                                    ' -> ' + w['suggestion'] if w.get('suggestion') else ''))
    rung = pick_rung(doc) if a.rung == 'auto' else a.rung
    if rung == 'text':
        sys.stdout.write(as_text(doc))
        print('(rung: text - a page would not add anything here)')
    else:
        out = a.out or re.sub(r'\.md$', '', a.draft) + '.html'
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(render(doc))
        figs = sum(b[0] in ('flow', 'sequence') for p in doc['panels'] for b in p['blocks'])
        print('wrote %s: %d panels, %d diagrams, %d style warnings' % (out, len(doc['panels']), figs, len(warnings)))
    return 1 if a.strict and warnings else 0


if __name__ == '__main__':
    sys.exit(main())
