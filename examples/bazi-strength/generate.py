#!/usr/bin/env python3
"""Reproducible synthetic dates, not personal data or accuracy evidence. MIT."""
from datetime import date
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import pai_pan_bazi as engine
import bazi_core_reading as core

CASES = [('strong', '1987-07-07', 10, 'strong_tendency'),
         ('weak', '1978-09-09', 12, 'weak_tendency'),
         ('competing', '1980-01-01', 10, 'competing_evidence'),
         ('unresolved', '1980-01-08', 10, 'conditions_unresolved')]

def generate():
    rows = []
    for name, solar, hour, expected in CASES:
        result = engine.compute(date.fromisoformat(solar), hour=hour, minute=0, now=date(2026,1,1))
        analysis = core.analyze(result)['strength_reasoning']
        assert analysis['decision'] == expected, (name, analysis['decision'])
        rows.append(dict(id=name, synthetic=True, input=dict(solar=solar, hour=hour, minute=0,
                         clock='引擎默认北京时间钟面，非个人出生信息'),
                         pillars={k:v[0]+v[1] for k,v in result['pillars'].items()}, strength_reasoning=analysis))
    here = Path(__file__).resolve().parent
    (here/'cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    text = ['# 日主承受证据：四个合成日期的真实引擎输出', '',
            '以下只是为覆盖规则选择的日期，不对应任何人的命盘，也不是预测验证。原创强弱释义 MIT；此文件未包含格局候选 CC BY-SA 改编段。', '']
    for row in rows:
        a=row['strength_reasoning']
        text += ['## '+row['id']+'：'+row['input']['solar']+' '+str(row['input']['hour'])+':00',
                 '四柱：'+'、'.join(row['pillars'].values()),a['text'],
                 '尚未确定：'+'；'.join(a['missing_conditions']+a['unresolved_effects']),
                 '反转条件：'+'；'.join(a['changing_conditions'])]+core.strength_reasoning.render_attribution(a['attribution'])+['']
    (here/'cases.md').write_text('\n'.join(text)+'\n')

if __name__ == '__main__':
    generate()
