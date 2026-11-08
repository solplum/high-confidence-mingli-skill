"""MIT generator; generated adapted study text/JSON: CC-BY-SA-4.0."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
base = [sys.executable, str(ROOT/'scripts/qizheng_traditional_reading.py'),
        '--solar', '2000-01-01', '--hour', '12:00', '--tradition', 'qianyuan-palace-v1']
cases = {'valid': (['--lat','35','--lon','120'], 0),
         'absent-location': ([], 1),
         'uncertain-time': (['--lat','35','--lon','120','--uncertain-time'], 1)}
manifest = {}
for name, (args, code) in cases.items():
    for fmt, ext in (('json','json'), ('text','txt')):
        proc = subprocess.run(base + args + ['--format',fmt], capture_output=True, text=True)
        if proc.returncode != code:
            raise RuntimeError(proc.stderr or proc.stdout)
        path = DEST / (name + '.' + ext)
        path.write_text(proc.stdout, encoding='utf-8')
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
(DEST/'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
