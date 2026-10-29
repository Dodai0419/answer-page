"""Time a full render (parse + lint + diagrams + HTML) and a cold CLI run. usage: python bench/bench.py [RUNS]"""
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import answer_page as ap  # noqa: E402

runs = int(sys.argv[1]) if len(sys.argv) > 1 else 50
for name in ('tcp.md', 'merge-vs-rebase.md'):
    src = open(os.path.join(ROOT, 'examples', name), encoding='utf-8').read()
    t = time.perf_counter()
    for _ in range(runs):
        doc = ap.parse(src)
        ap.lint_doc(doc)
        page = ap.render(doc)
    print('%-20s in-process render %.2f ms  page %.1f KB' % (name, (time.perf_counter() - t) / runs * 1000, len(page.encode()) / 1024))
with tempfile.TemporaryDirectory() as d:
    t = time.perf_counter()
    subprocess.run([sys.executable, os.path.join(ROOT, 'answer_page.py'), os.path.join(ROOT, 'examples', 'tcp.md'),
                    '-o', os.path.join(d, 'x.html')], capture_output=True, check=True)
    print('cold CLI run (tcp.md): %.0f ms' % ((time.perf_counter() - t) * 1000))
