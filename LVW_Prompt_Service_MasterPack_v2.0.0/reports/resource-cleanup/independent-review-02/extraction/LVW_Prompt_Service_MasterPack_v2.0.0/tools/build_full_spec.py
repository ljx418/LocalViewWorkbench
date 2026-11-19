#!/usr/bin/env python3
"""Deterministic docs assembly. No product imports, services or dependencies."""
from pathlib import Path
import argparse
import posixpath
import re

ROOT = Path(__file__).resolve().parents[1]

def render():
    files = sorted((ROOT / 'docs').glob('*.md')) + sorted((ROOT / 'docs/adr').glob('*.md'))
    sections = []
    for path in files:
        def relocate(match):
            target = match.group(1)
            if target.startswith(('#', 'http:', 'https:', 'mailto:')):
                return match.group(0)
            name, sep, fragment = target.partition('#')
            relative = posixpath.normpath(str(path.parent.relative_to(ROOT)) + '/' + name)
            return '](' + relative + (sep + fragment if sep else '') + ')'
        text = re.sub(r'\]\(([^)]+)\)', relocate, path.read_text(encoding='utf-8'))
        text = '\n'.join(line.rstrip() + ('<br>' if line.endswith('  ') else '') for line in text.splitlines())
        sections.append('<!-- source: ' + str(path.relative_to(ROOT)) + ' -->\n\n' + text.rstrip())
    return '# LVW · V0–V3 当前设计汇编\n\n由 tools/build_full_spec.py 从 docs 生成；单一产品坐标读取 plans/execution-control.json。设计与候选不代表产品已验收。\n\n' + '\n\n---\n\n'.join(sections) + '\n'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'FULL_SPEC.md'
    content = render()
    if args.check:
        good = target.exists() and target.read_text(encoding='utf-8') == content
        print('FULL_SPEC_CURRENT' if good else 'FULL_SPEC_STALE')
        return 0 if good else 1
    target.write_text(content, encoding='utf-8')
    print('FULL_SPEC_GENERATED_FROM_DOCS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
