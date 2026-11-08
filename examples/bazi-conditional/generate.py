#!/usr/bin/env python3
"""Produce a restricted structural explanation from the existing fictional snapshot.

The generated ledger includes a CC BY-SA 4.0 card adaptation; not MIT.
Run from any cwd. Validator --root must be the repository root.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
LABEL = '未校勘数字转录的传统规则释义（项目整理，非预测验证）'
USE = 'conditional_traditional_interpretation'


def build():
    catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())
    card = next(r for r in catalog['records'] if r['id'] == 'bazi-dts-interpret-geju')
    src = next(s for s in catalog['sources'] if s['id'] == card['source_id'])
    chart_path = 'examples/engine-reading/summer.json'
    chart = json.loads((ROOT / chart_path).read_text())
    facts = [dict(id=name, system='bazi', scenario_id='fictional', source_id='chart',
                  pointer='/bazi/pillars/' + name, value=chart['bazi']['pillars'][name])
             for name in ['year', 'month', 'day', 'hour']]
    bound = [f['id'] for f in facts]
    rule = dict(id='geju', system='bazi', source_id='card', school='滴天髓辑要数字转录的项目释义，未校勘',
                locator=src['path']+':'+str(card['source_span']['start_line']),
                quote=card['summary'], attribution_kind='registered_source_excerpt', source_label=src['citation_label'],
                reading_use=USE, catalog_record_id=card['id'], interpretation_label=LABEL,
                predictive_status='unvalidated', authenticity_status='uncollated_digital_transcription',
                guaranteed_prediction=False, **card['source_span'])
    rule['redistribution'] = {key: src[key] for key in ['license_id','license_url','attribution','contributors_url','change_notice','upstream_url','revision']}
    rule['redistribution']['license_notice'] = (ROOT / src['license_path']).read_text()
    assessments = [
        '快照月柱辛巳，月支藏丙、庚、戊；年干庚、时干戊可与月藏对应，日干癸。这里只核对结构，不判身强弱。',
        '暂按该卡先月令后透干的观察顺序；月藏庚与戊均透，保留印与官两条候选，不直接定一个格名。',
        '时干戊与午中己的显隐不同，不能据共存认定官杀混杂；盘中也没有以伤官见官成立为前提的结论。']
    exclusions = ['未由官印或官杀共现推断吉凶，只描述月藏与透干关系。',
                  '此盘月支巳，并非四季土月；不外推该页四季月的争议取格说法。']
    checks = dict(rule_id='geju',
        conditions=[dict(criterion=t,result='met',assessment=a,fact_ids=bound) for t,a in zip(card['conditions'],assessments)],
        exclusions=[dict(criterion=t,result='reviewed',assessment=a,fact_ids=bound) for t,a in zip(card['exclusions'],exclusions)])
    claim = dict(id='structure',system='bazi',domain='传统结构解释',time_scope='虚构本命结构',
        statement='月支巳藏丙、庚、戊，年干庚与时干戊透出，因此先保留月令取格中的印、官两个候选解释；不足以确定成格或人生结果。',
        status='conditional',boundary='unassessed',fact_ids=bound,rule_ids=['geju'],depends_on=[],scenario_ids=['fictional'],
        conditions='仅按固定数字转录的项目释义分析；未完成旺衰、救应、其他学派与时间候选比较。',
        counterevidence='月藏丙未透，庚戊同时透，不能只选一个字就排除其他路径；日主承受与合绊未作充分判断。',
        alternatives='可以分别保留印与官的候选，也可在另一取格口径下重做；当前不判完整成格。',
        limitations='传统术语解释不是已校勘古籍引文、预测验证或人生保证。结构校验不能自动判断释义是否正确。',
        explanation=dict(plain='先解释为什么关注官与印，而不是凭书名直接下断语。',technical='将巳月藏干与四柱透干逐项对应，保留两个路径及尚缺的判断。',action='接着检查旺衰、救应与反证；资料不足就停留在候选解释，不用于重大决定。'),
        reading_use=USE,interpretation_label=LABEL,predictive_status='unvalidated',authenticity_status='uncollated_digital_transcription',guaranteed_prediction=False,application_checks=[checks])
    return dict(schema_version=1,purpose='synthetic_test',
        sources=[dict(id='chart',kind='chart',path=chart_path,sha256=hashlib.sha256((ROOT/chart_path).read_bytes()).hexdigest(),system='bazi',scenario_id='fictional',pointer_prefix='/bazi'),
                 dict(id='card',kind='reference',path=src['path'],sha256=src['sha256'])],
        scenarios=[dict(id='fictional',label='既有虚构引擎样例',time_basis='旧示例固定民用时间',assumptions='非真实用户；复用summer.json，无新排盘或历史天文真实性主张。')],
        facts=facts,rules=[rule],claims=[claim],syntheses=[])


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/bazi-conditional-ledger.json')
    out.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
    print(str(out))
