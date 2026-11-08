"""Synthetic-only full workflow evidence. MIT code; study-derived outputs CC BY-SA 4.0.
Run: python3 examples/qizheng-full-round/reproduce.py OUTPUT_DIRECTORY
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
DEST = Path(sys.argv[1]).resolve()
DEST.mkdir(parents=True, exist_ok=True)
base = [sys.executable, str(ROOT/'scripts/build_chart.py'), '--sex','男', '--lat','35','--lon','120', '--qizheng-tradition','qianyuan-palace-v1']
cases = {
 'narrow': ['--solar','2000-01-01','--hour','12:00','--analysis-year','2026','--uncertainty-minutes','0.5','--qizheng-sensitivity'],
 'large': ['--solar','2000-01-01','--hour','08:00','--analysis-year','2026','--uncertainty-minutes','120','--qizheng-sensitivity'],
 'dst': ['--solar','2024-11-03','--hour','01:30','--analysis-year','2026','--timezone','America/New_York','--fold','1','--uncertainty-minutes','120','--qizheng-sensitivity'],
 'pole': ['--solar','2000-01-01','--hour','12:00','--analysis-year','2026','--lat','90','--uncertainty-minutes','2','--qizheng-sensitivity'],
 'lower1901': ['--solar','1901-01-01','--hour','12:00','--analysis-year','2026','--uncertainty-minutes','120','--qizheng-sensitivity'],
 'upper2100': ['--solar','2100-01-01','--hour','12:00','--analysis-year','2100'],
 'no-node': ['--solar','2000-01-01','--hour','12:00','--analysis-year','2026'],
}
manifest = {}
for name, args in cases.items():
 for fmt, ext in [('json','json'),('text','txt')]:
  env = dict(os.environ)
  if name == 'no-node':
   empty=DEST/'empty-path';empty.mkdir(exist_ok=True); env['PATH']=str(empty)
  p=subprocess.run(base+args+['--format',fmt],capture_output=True,text=True,env=env)
  assert p.returncode==0, (name,p.stderr)
  if fmt=='json':
   data=json.loads(p.stdout)
   if '--uncertainty-minutes' in args: assert data['qizheng_traditional_reading']['status']=='withheld'
   if name=='upper2100': assert data['qizheng']['star_frame_contract']['within_validated_range'] is True
   if name=='no-node': assert data['ziwei'] is None and data['degradation']['ziwei']
   else: assert data['ziwei'] is not None
   if name=='pole': assert data['qizheng']['ming_du'] is None
   if data['qizheng_sensitivity']:
    r=data['qizheng_sensitivity']; assert not r['coverage_complete'] and not r['stable_fields']
    assert all(c['traditional_reading'] is not None for c in r['candidates'])
  else:
   if '--qizheng-sensitivity' in args:
    assert '```json' not in p.stdout
    assert '紫气为未独立校准' in p.stdout
  path=DEST/(name+'.'+ext); path.write_text(p.stdout)
  manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
# Reject unsupported intervals instead of quietly clipping them.
for name,args in [('lower-cross',['--solar','1901-01-01','--hour','00:00']),('upper-cross',['--solar','2100-01-01','--hour','12:00'])]:
 p=subprocess.run(base+args+['--uncertainty-minutes','120','--qizheng-sensitivity'],capture_output=True,text=True)
 assert p.returncode==2 and '1901' in p.stderr
 path=DEST/(name+'.stderr');path.write_text(p.stderr);manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
(DEST/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
