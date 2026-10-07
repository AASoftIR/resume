#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs=[]; self.canonical=[]; self.descriptions=[]; self.jsonld=[]; self._jsonld=False; self._buf=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag in {'a','link'} and d.get('href'): self.refs.append(d['href'])
        if tag in {'script','img','source','iframe','object'} and (d.get('src') or d.get('data')): self.refs.append(d.get('src') or d.get('data'))
        if tag=='link' and d.get('rel')=='canonical' and d.get('href'): self.canonical.append(d['href'])
        if tag=='meta' and d.get('name')=='description' and d.get('content'): self.descriptions.append(d['content'])
        if tag=='script' and d.get('type')=='application/ld+json': self._jsonld=True; self._buf=[]
    def handle_data(self,data):
        if self._jsonld: self._buf.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self._jsonld:
            self.jsonld.append(''.join(self._buf)); self._jsonld=False; self._buf=[]

def local_target(page: Path, ref: str) -> Path | None:
    parsed=urlparse(ref)
    if parsed.scheme or parsed.netloc or ref.startswith(('mailto:','tel:','data:','#')):
        return None
    path=unquote(parsed.path)
    if not path:
        return page
    if path.startswith('/'):
        # Project Pages is mounted under /resume; root-absolute links are intentionally avoided.
        return None
    target=(page.parent / path).resolve()
    if target.is_dir(): target=target/'index.html'
    return target

def main() -> int:
    errors=[]; html_files=sorted(DIST.rglob('*.html'))
    if not html_files: errors.append('no generated HTML files')
    for page in html_files:
        parser=Parser(); parser.feed(page.read_text(encoding='utf-8'))
        if page.name!='404.html':
            if len(parser.canonical)!=1: errors.append(f'{page.relative_to(DIST)}: expected one canonical URL')
            if not parser.descriptions or not parser.descriptions[0].strip(): errors.append(f'{page.relative_to(DIST)}: missing meta description')
        for raw in parser.jsonld:
            try: json.loads(raw)
            except Exception as exc: errors.append(f'{page.relative_to(DIST)}: invalid JSON-LD: {exc}')
        for ref in parser.refs:
            target=local_target(page,ref)
            if target is not None and DIST.resolve() in (target, *target.parents) and not target.exists():
                errors.append(f'{page.relative_to(DIST)}: broken local ref {ref} -> {target.relative_to(DIST)}')

    required=['index.html','resume.pdf','robots.txt','sitemap.xml','site.webmanifest','assets/og-card.png','assets/icon-192.png','assets/icon-512.png','about/index.html','projects/index.html','experience/index.html','skills/index.html','education/index.html','contact/index.html','cv/index.html']
    for rel in required:
        if not (DIST/rel).is_file(): errors.append(f'missing required build output: {rel}')

    sitemap=(DIST/'sitemap.xml').read_text(encoding='utf-8') if (DIST/'sitemap.xml').exists() else ''
    try:
        ET.fromstring(sitemap)
    except Exception as exc:
        errors.append(f'invalid sitemap.xml: {exc}')
    try:
        json.loads((DIST/'site.webmanifest').read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'invalid site.webmanifest: {exc}')
    for page in html_files:
        if page.name=='404.html': continue
        rel=page.relative_to(DIST).as_posix()
        if rel=='index.html': suffix='/'
        else: suffix='/' + rel.removesuffix('index.html')
        if suffix not in sitemap: errors.append(f'sitemap missing page path: {suffix}')

    robots=(DIST/'robots.txt').read_text(encoding='utf-8') if (DIST/'robots.txt').exists() else ''
    if 'Sitemap:' not in robots: errors.append('robots.txt missing Sitemap directive')

    if errors:
        print('SEO/site validation failed:', file=sys.stderr)
        for err in errors: print(f'- {err}', file=sys.stderr)
        return 1
    print(f'Validated {len(html_files)} HTML pages, structured data, sitemap, robots, and local links.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
