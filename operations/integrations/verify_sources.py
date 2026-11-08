#!/usr/bin/env python3
"""Verify explicit upstream source provenance without fetching or reading credentials."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--sentinel-root',type=Path);p.add_argument('--pki-root',type=Path);a=p.parse_args()
pins=json.loads((Path(__file__).parent/'upstream-sources.json').read_text(encoding='utf-8'))['sources']
if not(a.sentinel_root or a.pki_root):p.error('provide at least one source root')
for name,root in [('sentinel',a.sentinel_root),('pki',a.pki_root)]:
 if root is None:continue
 def git(*args):
  r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True)
  if r.returncode:raise SystemExit(name+': SOURCE_VERIFICATION_FAILED')
  return r.stdout.strip()
 if git('remote','get-url','origin')!=pins[name]['origin'] or git('rev-parse','HEAD')!=pins[name]['commit']:raise SystemExit(name+': PIN_MISMATCH')
 if git('status','--porcelain','--untracked-files=no'):raise SystemExit(name+': TRACKED_SOURCE_DIRTY')
 print(json.dumps({'source':name,'path':str(root.resolve()),**pins[name],'verified':True}))
