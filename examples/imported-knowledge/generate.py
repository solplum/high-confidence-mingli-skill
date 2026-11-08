#!/usr/bin/env python3
"""Run the actual CLI and join a pinned modern source to fictional chart facts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    args = ['scripts/build_chart.py', '--solar', '2000-05-15', '--hour', '12:00',
            '--sex', '男', '--lat', '31.23', '--lon', '121.47',
            '--timezone', 'Asia/Shanghai', '--analysis-year', '2026', '--format', 'json']
    result = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True, check=True)
    chart = json.loads(result.stdout)
    assert chart['ziwei'] is not None, chart['degradation']
    save(OUT / 'snapshot.json', chart)
    save(OUT / 'command.json', ['python3'] + args)
    catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text(encoding='utf-8'))
    source = next(s for s in catalog['sources'] if s['id'] == 'iztro-docs-palace')
    lines = (ROOT / source['path']).read_text(encoding='utf-8').splitlines()
    line = next(i for i, text in enumerate(lines, 1) if text.startswith('三方四正不是'))
    palaces = chart['ziwei']['chart']['palaces']
    base = next(p['branch'] for p in palaces if p['isMingGong'])
    branches = {(base + shift) % 12 for shift in (0, 4, 6, 8)}
    facts = [dict(id='palace-' + str(i), system='ziwei', scenario_id='fictional', source_id='chart',
                  pointer='/ziwei/chart/palaces/' + str(i), value=p)
             for i, p in enumerate(palaces) if p['branch'] in branches]
    assert len(facts) == 4
    ledger = dict(schema_version=1, purpose='synthetic_test',
        scenarios=[dict(id='fictional', label='虚构输入：导入知识示例', time_basis='civil',
                        assumptions='上海附近公共坐标；Asia/Shanghai；显式分析年2026；无现实经历或预测检验。')],
        sources=[dict(id='chart', kind='chart', path='examples/imported-knowledge/snapshot.json',
                      sha256=hashlib.sha256((OUT / 'snapshot.json').read_bytes()).hexdigest(),
                      system='ziwei', scenario_id='fictional', pointer_prefix='/ziwei'),
                 dict(id='palace-source', kind='reference', path=source['path'], sha256=source['sha256'])],
        facts=facts,
        rules=[dict(id='three-four', system='ziwei', source_id='palace-source', school='固定本命盘关系；不启用宫干飞化',
                    locator=source['path'] + ':' + str(line), start_line=line, end_line=line, quote=lines[line-1],
                    attribution_kind='registered_source_excerpt', source_label=source['citation_label'])],
        claims=[dict(id='bounded-relation', system='ziwei', domain='宫位关系', time_scope='本命',
            statement='本例命宫三方四正的四宫已列出实际星曜，仅确认分析范围，不作吉凶或人生事件判断。',
            status='conditional', boundary='unassessed', fact_ids=[f['id'] for f in facts], rule_ids=['three-four'],
            depends_on=[], scenario_ids=['fictional'], conditions='只适用于这一虚构本命快照和固定关系定义。',
            counterevidence='星曜组合、四化、庙旺、成格破格与运限未综合评估。',
            alternatives='其他学派需另列定义和适用条件，不直接混用。',
            limitations='来源是现代数字说明，不是核验古籍原文；文件与结构一致不能证明预测能力。',
            explanation=dict(plain='这里只圈出要一起看的四个位置，不能由此得出你的未来。',
                technical='以命宫地支为基准，取本宫、+6对宫及+4/+8三合宫；下列facts保留四宫真实字段。',
                action='若进一步解释，先逐项核对组合条件、例外和不同学派。'))], syntheses=[])
    save(OUT / 'ledger.json', ledger)
    result = subprocess.run([sys.executable, 'scripts/validate_claim_ledger.py',
        'examples/imported-knowledge/ledger.json', '--root', '.'], cwd=ROOT, capture_output=True, text=True, check=True)
    (OUT / 'validation.json').write_text(result.stdout, encoding='utf-8')
    print('Actual three-engine CLI snapshot and imported-source ledger passed (4 palace facts).')

if __name__ == '__main__':
    main()
