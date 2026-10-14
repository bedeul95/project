#!/usr/bin/env python3
"""Build a self-contained offline HTML deliverable from local source files."""
from pathlib import Path
import json
root = Path(__file__).resolve().parent
css = (root / 'src/style.css').read_text()
engine = (root / 'src/engine.js').read_text()
app = (root / 'src/read-ui.js').read_text() + '\n' + (root / 'src/app.js').read_text()
for value in (engine, app):
    if '</script' in value.lower():
        raise ValueError('Source contains a script closing tag; escape it before bundling.')
html = '''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#183d2d"><meta name="description" content="ATLAS Mac 퀀트 기업평가·거래량 분석·모의운용"><title>ATLAS · Mac Quant Studio</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23183d2d'/%3E%3Cpath d='M16 48L32 14L48 48M23 36H41' fill='none' stroke='%23d2e8c9' stroke-width='5'/%3E%3C/svg%3E"><style>''' + css + '''</style></head>
<body><div id="app"></div><div id="toast" role="status" aria-live="polite"></div><input id="import-file" type="file" accept=".json,application/json" hidden><noscript>ATLAS를 실행하려면 브라우저의 JavaScript를 허용해주세요.</noscript><script>''' + engine + '''</script><script>''' + app + '''</script></body></html>'''
(root / '시작.html').write_text(html, encoding='utf-8')
print(json.dumps({'file': str(root / '시작.html'), 'bytes': len(html.encode())}, ensure_ascii=False))
