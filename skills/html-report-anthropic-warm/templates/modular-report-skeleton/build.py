#!/usr/bin/env python3
"""Build skills-report.html from modular sections.

Usage:
  cd ~/<report-dir>
  python3 build.py            # full build
  python3 build.py memory     # rebuild only memory section into existing file
  python3 build.py persona    # rebuild only persona section
  python3 build.py s01        # rebuild only performance section (alias supported)

When you partial-rebuild, build.py replaces JUST that section in the output HTML
and leaves everything else intact. Full build is also fast (<1s).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'sections'))

# Section order + module map + HTML marker. Add new section by appending here
# and creating sections/<module_name>.py with a render() function.
SECTIONS = [
    ('hero',    'hero',            'HERO'),
    ('s00',     's00_memory',      'SECTION-00'),
    ('s00b',    's00b_persona',    'SECTION-00B'),
    ('s01',     's01_performance', 'SECTION-01'),
    ('s02',     's02_code_changes','SECTION-02'),
    ('s03',     's03_coverage',    'SECTION-03'),
    ('footer',  'footer',          'FOOTER'),
]

# Friendly aliases so `python3 build.py memory` works as well as `s00`
ALIASES = {
    'memory': 's00',
    'persona': 's00b',
    'performance': 's01', 'perf': 's01',
    'code': 's02',
    'coverage': 's03', 'cats': 's03',
}

# === Output path — change to where the final HTML should live ===
OUT_PATH = ROOT.parent / 'skills-report-claude-design.html'

def render_section(alias):
    mod_name = next((m for a, m, _ in SECTIONS if a == alias), None)
    if not mod_name:
        raise ValueError(f"Unknown section alias: {alias}")
    marker = next((mk for a, _, mk in SECTIONS if a == alias), alias.upper())
    mod = __import__(mod_name)
    import importlib; importlib.reload(mod)  # pick up edits in same Python session
    html = mod.render()
    return f'<!-- BEGIN: {marker} -->\n{html}\n<!-- END: {marker} -->'

def build_full():
    css = (ROOT / 'styles' / 'main.css').read_text()
    body_parts = [render_section(alias) for alias, _, _ in SECTIONS]
    # Footer renders OUTSIDE <div class="wrap"> so it spans full width
    wrap_inner = '\n'.join(body_parts[:-1])
    footer_html = body_parts[-1]
    html = f'''<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1620, initial-scale=1">
<title>Report (modular)</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
<div class="wrap">
{wrap_inner}
</div>
{footer_html}
</body>
</html>
'''
    OUT_PATH.write_text(html)
    return OUT_PATH, len(html)

def rebuild_section(alias):
    canonical = ALIASES.get(alias, alias)
    if not OUT_PATH.exists():
        print("No existing HTML — running full build")
        return build_full()
    html = OUT_PATH.read_text()
    marker = next((mk for a, _, mk in SECTIONS if a == canonical), None)
    if not marker:
        print(f"Unknown alias '{alias}' — running full build")
        return build_full()
    new_block = render_section(canonical)
    import re
    pattern = re.compile(
        rf'<!-- BEGIN: {re.escape(marker)} -->.*?<!-- END: {re.escape(marker)} -->',
        re.DOTALL
    )
    m = pattern.search(html)
    if not m:
        print(f"Marker {marker} not found in HTML — running full build")
        return build_full()
    html = html[:m.start()] + new_block + html[m.end():]
    OUT_PATH.write_text(html)
    return OUT_PATH, len(html)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        path, size = rebuild_section(target)
        print(f"✅ Rebuilt section: {target}")
    else:
        path, size = build_full()
        print(f"✅ Full build")
    print(f"   → {path}")
    print(f"   → {size:,} chars")
