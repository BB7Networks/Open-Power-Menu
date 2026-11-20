#!/usr/bin/env python3
"""Check local documentation links; optionally audit the Phase 2 maintenance boundary."""
import argparse
import csv
import hashlib
import html
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def files():
    result = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    return sorted({n for n in result if n and (ROOT/n).is_file()})


def markdown(text):
    return re.sub(r'(?ms)^(`{3,}|~{3,}).*?^\1[^\n]*$', '', text)


def anchors(text):
    result, counts = set(), {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', markdown(text), flags=re.M):
        heading = re.sub(r'!?\[([^]]+)\]\([^)]*\)',r'\1',heading)
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        number=counts.get(slug,0);counts[slug]=number+1
        result.add(slug+('-'+str(number) if number else ''))
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)',text))
    return result


def audit_links(names):
    errors, links, external = [], 0, set()
    for name in names:
        if not name.endswith('.md'): continue
        path=ROOT/name;text=markdown(path.read_text())
        references = re.findall(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\)',text)
        references += re.findall(r'(?:href|src)=["\']([^"\']+)["\']',text)
        for ref in references:
            ref=html.unescape(ref.strip('<>'));parts=urlsplit(ref)
            if parts.scheme or parts.netloc:
                external.add(ref);continue
            target=(path.parent/unquote(parts.path)).resolve() if parts.path else path
            links+=1
            if not target.exists():
                errors.append(name+': missing '+ref)
            elif parts.fragment and target.suffix=='.md' and unquote(parts.fragment) not in anchors(target.read_text()):
                errors.append(name+': missing anchor '+ref)
    return errors,links,external


def audit_inventory(names):
    errors=[]
    with (ROOT/'docs/maintenance/phase2-inventory.csv').open() as stream:
        rows=list(csv.DictReader(stream))
    with (ROOT/'docs/maintenance/phase2-added-files.csv').open() as stream:
        added=list(csv.DictReader(stream))
    if len(rows)!=279 or len({r['source'] for r in rows})!=279:
        errors.append('Baseline inventory must classify all 279 approved files exactly once')
    expected={r['destination'] for r in rows if r['decision']!='delete'}|{r['path'] for r in added}
    if set(names)!=expected:
        errors.append('Inventory mismatch: missing='+str(sorted(expected-set(names)))+' unclassified='+str(sorted(set(names)-expected)))
    protected=0
    for row in rows:
        path=ROOT/row['destination']
        source=row['source']
        runtime=(row['category'] in {'native runtime and shared resources','legacy Python compatibility'}
                 or source.endswith(('.png','.svg'))
                 or source.startswith('native/packaging/') and source.endswith(('.cpp','.hpp','install.sh.in')))
        if runtime:
            protected+=1
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['approved_sha256']:
                errors.append('Protected runtime/gallery changed: '+source)
    return errors,protected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase2',action='store_true',help='Also check the approved maintenance inventory and runtime/gallery hashes')
    args=parser.parse_args()
    names=files();errors,count,external=audit_links(names)
    print(f'Checked {count} local documentation links; {len(external)} external URLs inventoried (not network-validated).')
    if args.phase2:
        failures,protected=audit_inventory(names);errors+=failures
        print(f'Classified {len(names)} current files; verified {protected} protected runtime/gallery files against approved Phase 1.')
    if errors:
        print('\n'.join(errors));raise SystemExit(1)
    print('Repository audit passed.')


if __name__=='__main__': main()
