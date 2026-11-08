"""Generate public synthetic fixtures only. No real-person data."""
from datetime import date
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import pai_pan_bazi as engine
import bazi_core_reading as core

CASES = [('S1', '1988-03-18', 10, 20), ('S2', '2001-08-22', 16, 40),
         ('S3', '1975-12-11', 6, 30), ('S4-before', '1998-06-30', 22, 58),
         ('S4-after', '1998-06-30', 23, 2), ('S5-before', '1992-02-04', 21, 46),
         ('S5-after', '1992-02-04', 21, 50)]

def generate():
    output = ['# 合成案例结构解读', '', '全部为测试输入，不代表任何真实人物。固定分析年2026。', '',
              '旧版382ce416：每例五栏均为 agent 注释。新版：每例五栏均给出本盘证据与未决项。',
              '这不是完整人生详批，也没有检验预测准确率。', '']
    data = []
    for id_, solar, hour, minute in CASES:
        r = engine.compute(date.fromisoformat(solar), hour=hour, minute=minute, now=date(2026, 1, 1))
        a = core.analyze(r)
        output += ['## ' + id_ + ' ' + solar + ' %02d:%02d' % (hour, minute),
                   '四柱：' + '、'.join(r['pillars'][k][0] + r['pillars'][k][1] for k in core.KEYS)] + core.render(a)
        data.append({'case_id': id_, 'synthetic': True, 'analysis': a})
    here = Path(__file__).resolve().parent
    (here / 'readings.md').write_text('\n'.join(output) + '\n')
    (here / 'readings.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    generate()
