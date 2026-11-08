"""MIT code; generated traditional interpretation is CC BY-SA 4.0.

A bounded month-hidden-stem exposure route, not a complete 格局判定.
No scoring, seasonal commander substitution, or predictive claims.
"""
import json
from pathlib import Path
import knowledge_catalog
import pai_pan_bazi as engine

VERSION = 'month-exposure-candidates-v1'
LABELS = dict(zip(('year', 'month', 'day', 'hour'), ('年', '月', '日', '时')))
ORDINARY = {'正官', '偏官', '正财', '偏财', '正印', '偏印', '食神', '伤官'}


def evaluate(facts, exposures, pairs, groups, missing):
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / 'knowledge/catalog.json').read_text())
    errors = knowledge_catalog.validate(catalog, root)
    if errors:
        raise ValueError('传统解释来源检查失败：' + '; '.join(errors))
    record = next(r for r in catalog['records'] if r['id'] == 'bazi-dts-interpret-geju')
    if record['status'] != 'usable' or record['profile'] != 'bazi-traditional-conditional' or record['usage_scope'] != 'conditional_traditional_interpretation':
        raise ValueError('月令候选来源不再允许受限传统解释')
    attribution = knowledge_catalog.citation(catalog, root, record['source_id'])
    attribution.update(record_id=record['id'], source_span=record['source_span'],
                       interpretation_label=record['interpretation_label'],
                       adaptation='将月令、透干、关系检查整理为有界候选决策；不是古文逐句算法或成格判据。',
                       output_license='CC-BY-SA-4.0')
    month = facts['month']['branch']
    candidates = []
    for x in exposures:
        basis = ['月支' + month + '藏' + x['stem'] + '，对日干' + facts['day']['stem'] + '为' + x['ten_god']]
        basis += [LABELS[k] + '干' + facts[k]['stem'] + '与该藏干同字，构成透出' for k in x['exposed_at']]
        objections = []
        if x['ten_god'] not in ORDINARY:
            verdict = 'outside_route'
            objections.append(x['ten_god'] + '不进入本模块的八类普通格候选；建禄、月刃及特殊格须另审')
        elif not x['exposed_at']:
            verdict = 'not_established' if not missing else 'unknown_exposure'
            objections.append('已知年、月、时干未见' + x['stem'] + '，这条“月藏同干透出”的入选条件未满足')
        else:
            verdict = 'eligible'
        if x['same_as_day']:
            objections.append('日干本身不算外部透出，不能用自身给自己立格')
        candidates.append({'stem': x['stem'], 'ten_god': x['ten_god'],
                           'name': x['ten_god'] + '格候选', 'verdict': verdict,
                           'supporting_facts': basis, 'opposing_facts': objections,
                           'exposed_at': x['exposed_at']})
    eligible = [c for c in candidates if c['verdict'] == 'eligible']
    selected = eligible[0] if len(eligible) == 1 else None
    if missing:
        decision = 'incomplete_hour'
        conclusion = '时柱未知，不能确定最终候选名单。'
        if selected:
            conclusion += '已知三柱优先保留' + selected['name'] + '，不是全盘定格。'
    elif len(eligible) == 1:
        decision = 'single_candidate'
        conclusion = '按月藏同干透出的有限取格路线，本盘优先取' + selected['name'] + '。'
    elif len(eligible) > 1:
        decision = 'competing_candidates'
        conclusion = '月令有多个藏干透出：' + '、'.join(c['name'] for c in eligible) + '；不能仅按藏干排列顺序挑一个。'
    else:
        decision = 'no_candidate_on_route'
        conclusion = '本盘没有满足这条透干路线的普通格候选；不等于全盘无格，也不否定不透干取格的其他口径。'
    interactions = []
    for r in pairs + groups:
        affected = [c['stem'] for c in eligible if
                    ('month' in r['positions'] and r['kind'] != '天干五合配对') or
                    (r['kind'] == '天干五合配对' and set(c['exposed_at']) & set(r['positions']))]
        if affected:
            text = '、'.join(LABELS[k] + facts[k]['pillar'] for k in r['positions']) + '构成' + r['kind']
            text += '；涉及月令或候选透干，须查作用能否成立，不能据配对直接撤格或宣称合化'
            interactions.append({'kind': r['kind'], 'positions': r['positions'], 'affected_stems': affected, 'text': text})
    visible = {god: [LABELS[k] + '干' + f['stem'] for k, f in facts.items()
                     if k != 'day' and f['ten_god'] == god]
               for god in ORDINARY | {'比肩', '劫财'}}
    checks = []
    # Concrete co-presence is a question to adjudicate, not an automatic success/failure rule.
    for names, label in [(('正官', '偏官'), '官杀并透'), (('正官', '伤官'), '伤官与正官并透')]:
        if all(visible[n] for n in names):
            checks.append(label + '：' + '；'.join(n + '在' + '、'.join(visible[n]) for n in names) +
                          '。这反对直接称格局清纯，但不足以断破格或人生吉凶；尚需查制化与救应')
    paths = []
    elements = '木火土金水'
    for c in eligible:
        cw = engine.GAN_WUXING[engine.GAN.index(c['stem'])]
        for k, f in facts.items():
            if k == 'day' or k in c['exposed_at']:
                continue
            ow = engine.GAN_WUXING[engine.GAN.index(f['stem'])]
            relation = ('同类于', '生', '克', '受克于', '受生于')[(elements.index(ow) - elements.index(cw)) % 5]
            detail = c['stem'] + cw + '（' + c['ten_god'] + '，透于' + '、'.join(LABELS[p] + '干' for p in c['exposed_at']) + '）' + relation + LABELS[k] + '干' + f['stem'] + ow + '（' + f['ten_god'] + '）'
            if c['ten_god'] in ('食神', '伤官') and f['ten_god'] == '偏官':
                detail += '：有食伤制杀的五行方向；尚未证明食伤或七杀有力，也未证明日主能够承受泄耗，不能直接定为有效制杀'
            else:
                detail += '：这是可复核的作用方向，效力仍须结合根气、位置和制化，不按相生即吉或相克即凶处理'
            paths.append({'candidate_stem': c['stem'], 'other_position': k, 'relation': relation, 'text': detail})
    changes = ['补全或改动时柱，可能新增月藏干透出、竞争候选或关系制约，须重新运行',
               '出生时刻跨节令使月柱变化，月藏干名单和全部候选依据随之重算',
               '若要从候选升级为成格，须另证日主承受、透干有效性与成败救应；当前不由候选推出喜忌']
    candidate_text = []
    meanings = {'eligible': '入选', 'outside_route': '不适用本路线',
                'not_established': '本路线不入选', 'unknown_exposure': '缺时待定'}
    for c in candidates:
        candidate_text.append(c['name'] + '【' + meanings[c['verdict']] + '】：' +
                              '；'.join(c['supporting_facts'] + c['opposing_facts']))
    text = conclusion + '这里“取候选”是决定接下来围绕哪种月令关系审查，不是宣告成格。' + '。'.join(candidate_text) + '。'
    if not eligible:
        interaction_check_status = 'not_applicable_no_candidate'
        text += '本路线没有入选候选，未进行候选受制审查；月支关系见核心冲合，不能把未审查写成未检出。'
    else:
        interaction_check_status = 'checked_known_pillars'
        text += ('作用上的保留：' + '；'.join(i['text'] for i in interactions) + '。') if interactions else '已知柱未检出本模块所列的月支/候选透干关系干扰；这不是“毫无破格因素”的证明。'
    if checks:
        text += '；'.join(checks) + '。'
    if paths:
        text += '候选与其他透干的关系：' + '；'.join(p['text'] for p in paths) + '。'
    return {'rule_version': VERSION, 'status': 'conditional' if not missing else 'withheld',
            'decision': decision, 'selected_candidate': selected['name'] if selected else None,
            'candidates': candidates, 'interactions': interactions,
            'interaction_check_status': interaction_check_status, 'purity_checks': checks, 'candidate_paths': paths,
            'changing_conditions': changes, 'text': text, 'attribution': attribution,
            'authenticity_status': 'uncollated_digital_transcription',
            'predictive_validity': 'unvalidated', 'prediction_guarantee': False,
            'scope': '月令透干普通格候选选择；非成格、旺衰、调候或喜忌定案'}
