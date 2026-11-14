"""MIT: four approved, bounded reviews of observed BaZi structure.

This module consumes canonical core facts. It neither chooses a pattern nor
changes strength, stem/branch facts, combination effects, or ledger permissions.
"""
from copy import deepcopy
from itertools import combinations, product
import json

import pai_pan_bazi as engine

VERSION = 'bazi-reviewed-structure-v1'
PROFILE = VERSION
RULE_IDS = ('BZ-K01', 'BZ-K02', 'BZ-K03', 'BZ-K04')
RECORD_IDS = tuple('bazi-reviewed-' + rule for rule in RULE_IDS)
KEYS = ('year', 'month', 'day', 'hour')
LABELS = dict(zip(KEYS, ('年', '月', '日', '时')))
ELEMENTS = '木火土金水'
PAIR_RULES = {
    '六冲': ('子午', '丑未', '寅申', '卯酉', '辰戌', '巳亥'),
    '六合配对': ('子丑', '寅亥', '卯戌', '辰酉', '巳申', '午未'),
    '相害': ('子未', '丑午', '寅巳', '卯辰', '申亥', '酉戌'),
    '子卯刑': ('子卯',),
    '自刑配对': ('辰辰', '午午', '酉酉', '亥亥'),
}
GROUP_RULES = {'三合齐字': ('申子辰', '亥卯未', '寅午戌', '巳酉丑'),
               '三会齐字': ('寅卯辰', '巳午未', '申酉戌', '亥子丑'),
               '三刑齐字': ('寅巳申', '丑戌未')}
RESOURCE = ('正印', '偏印')
WEALTH = ('正财', '偏财')
TITLES = dict(zip(RULE_IDS, ('官、伤、印的候选分支', '食、杀、印、财的反向作用链',
                              '五合的自身、他干、隔位与共享角色', '月令用神、相神与扶抑的语义对象')))


def relations_from_facts(facts):
    """Derive the original pair and group observations in fixed pillar order."""
    known = {key: facts[key] for key in KEYS if key in facts}
    pairs = []
    for left, right in combinations(known, 2):
        branches = known[left]['branch'] + known[right]['branch']
        stems = known[left]['stem'] + known[right]['stem']
        adjacent = abs(KEYS.index(left) - KEYS.index(right)) == 1
        for kind, patterns in PAIR_RULES.items():
            if any(sorted(branches) == sorted(pattern) for pattern in patterns):
                pairs.append(dict(kind=kind, positions=[left, right], symbols=branches, adjacent=adjacent))
        if any(sorted(stems) == sorted(pattern) for pattern in ('甲己', '乙庚', '丙辛', '丁壬', '戊癸')):
            pairs.append(dict(kind='天干五合配对', positions=[left, right], symbols=stems, adjacent=adjacent))
    groups = []
    branches = {row['branch'] for row in known.values()}
    for kind, patterns in GROUP_RULES.items():
        for pattern in patterns:
            if set(pattern) <= branches:
                groups.append(dict(kind=kind, symbols=pattern,
                                   positions=[key for key, row in known.items() if row['branch'] in pattern]))
    return pairs, groups


def _element(stem):
    return engine.GAN_WUXING[engine.GAN.index(stem)]


def _nodes(facts):
    rows = []
    for pos in KEYS:
        if pos not in facts:
            continue
        f = facts[pos]
        rows.append(dict(id=pos + '.stem', position=pos, layer='visible',
                         stem=f['stem'], element=_element(f['stem']), ten_god=f['ten_god'],
                         text=LABELS[pos] + '干' + f['stem'] + '（' + f['ten_god'] + '）'))
        for h in f['hidden']:
            rows.append(dict(id=pos + '.hidden.' + h['stem'], position=pos, layer='hidden',
                             stem=h['stem'], element=h['element'], ten_god=h['ten_god'],
                             text=LABELS[pos] + '支' + f['branch'] + '藏' + h['stem'] + '（' + h['ten_god'] + '）'))
    for node in rows:
        node['same_element_root_ids'] = [n['id'] for n in rows
                                         if n['layer'] == 'hidden' and n['element'] == node['element']]
    return rows


def _edges(left, right, kind, relation):
    expected = 1 if relation == '生' else 2
    edges = []
    for a, b in product(left, right):
        if (ELEMENTS.index(b['element']) - ELEMENTS.index(a['element'])) % 5 != expected:
            continue
        edges.append(dict(id=kind + ':' + a['id'] + '>' + b['id'], kind=kind,
                          from_id=a['id'], to_id=b['id'], relation=relation,
                          layers=[a['layer'], b['layer']],
                          adjacent=abs(KEYS.index(a['position']) - KEYS.index(b['position'])) == 1,
                          position_distance=abs(KEYS.index(a['position']) - KEYS.index(b['position'])),
                          text=a['text'] + relation + b['text'], efficacy='withheld'))
    return edges


def _check(id_, nodes, uncertain, text):
    return dict(id=id_, status='present' if nodes else ('unknown' if uncertain else 'not_observed_known_pillars'),
                fact_ids=[n['id'] for n in nodes], text=text)


def _candidate(c, facts):
    return dict(id='month.' + c['stem'] + '.' + c['ten_god'], stem=c['stem'], ten_god=c['ten_god'],
                name=c['name'], exposed_at=list(c['exposed_at']),
                fact_ids=['month.hidden.' + c['stem']] + [k + '.stem' for k in c['exposed_at']],
                month_branch=facts['month']['branch'])


def _card(rule, record, uncertain, missing_reasons):
    citation = deepcopy(record['citation'])
    citation.update(record_id=record['id'], source_span=deepcopy(record['source_span']))
    return dict(id=rule, title=TITLES[rule], status='withheld' if uncertain else 'conditional',
                candidates=[], nodes=[], paths=[], conditions=[], exclusions=[], counterevidence=[],
                unresolved=list(missing_reasons), citation=citation,
                reading_use='conditional_module_only', scope='事实与方向审查；独立保存不扩展个人ledger权限',
                source_summary=deepcopy(record['summary']),
                source_conditions=deepcopy(record['conditions']), source_exclusions=deepcopy(record['exclusions']),
                effect_assessment='withheld', predictive_validity='unvalidated', prediction_guarantee=False)


def evaluate(facts, month_exposure, relations, groups, pattern, strength, missing,
             temporal_uncertainty=False, scenario_id=None, root=None):
    """Review one already-validated input candidate; never mutate the input."""
    uncertainty = bool(missing or temporal_uncertainty)
    reasons = []
    if missing:
        reasons.append('时柱未知：未见只限已知柱，候选名单、透藏和争合仍可能改变')
    if temporal_uncertainty:
        reasons.append('出生时间有非零误差或未决场景：当前事实仅属单一输入，须逐可达场景重算')
    panel = dict(rule_version=VERSION, profile=PROFILE, status='withheld' if uncertainty else 'conditional',
                 temporal_scope='single_input_candidate', scenario_id=scenario_id,
                 temporal_uncertainty=bool(temporal_uncertainty), missing_pillars=list(missing),
                 source_errors=[], cards=[], predictive_validity='unvalidated', prediction_guarantee=False,
                 reading_use='conditional_module_only',
                 scope='获批四项的事实、方向与角色审查；不判断效力、成格或喜忌，不扩展个人ledger权限')
    try:
        from reviewed_knowledge import load_profile
        records = load_profile('bazi', PROFILE, RECORD_IDS, root=root)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        panel.update(status='withheld', source_errors=[str(exc)])
        panel['cards'] = [dict(id=r, title=TITLES[r], status='withheld', nodes=[], paths=[],
                               conditions=[], exclusions=[], counterevidence=[], candidates=[],
                               unresolved=['来源检查失败：' + str(exc)], citation=None)
                          for r in RULE_IDS]
        return panel
    by_rule = {r['rule_id']: r for r in records}
    nodes = _nodes(facts)
    panel['nodes'] = deepcopy(nodes)
    by_id = {n['id']: n for n in nodes}
    find = lambda gods: [n for n in nodes if n['ten_god'] in gods]
    resources, wealth = find(RESOURCE), find(WEALTH)
    hurt, food, killers = find(('伤官',)), find(('食神',)), find(('偏官',))
    eligible = [_candidate(c, facts) for c in pattern['candidates'] if c['verdict'] == 'eligible']
    officers = [c for c in eligible if c['ten_god'] == '正官']
    killing = [c for c in eligible if c['ten_god'] == '偏官']
    candidate_nodes = lambda candidates: [by_id[p + '.stem'] for c in candidates for p in c['exposed_at']]
    candidate_centers = lambda candidates: [by_id[f] for c in candidates for f in c['fact_ids']]
    month_relations = [deepcopy(r) for r in relations + groups
                       if 'month' in r['positions'] and r['kind'] != '天干五合配对']
    common = dict(day_stem=facts['day']['stem'], month_branch=facts['month']['branch'],
                  month_exposure=deepcopy(month_exposure), candidate_route=pattern['rule_version'],
                  candidate_decision=pattern['decision'], candidates=deepcopy(eligible),
                  month_branch_relations=month_relations,
                  source_model_conflicts=deepcopy(strength['source_model_conflicts']),
                  contested_effects=deepcopy(strength['contested_effects']),
                  unassessed_interactions=deepcopy(strength['unassessed_interactions']),
                  strength_supporting_fact_ids=list(strength['supporting_fact_ids']),
                  strength_counterevidence_fact_ids=list(strength['counterevidence_fact_ids']),
                  strength_decision=strength['decision'])
    panel['context'] = common

    k1 = _card('BZ-K01', by_rule['BZ-K01'], uncertainty, reasons)
    officer_nodes = candidate_nodes(officers)
    challenge = _edges(hurt, officer_nodes, 'hurting_officer_controls_officer', '克')
    rescue = _edges(resources, hurt, 'resource_controls_hurting_officer', '克') if officers else []
    wealth_resource = _edges(wealth, resources, 'wealth_controls_resource', '克')
    k1['candidates'] = deepcopy(officers)
    k1['nodes'] = [deepcopy(n) for n in nodes if n in candidate_centers(officers) + hurt + resources + wealth] if officers else []
    k1['paths'] = challenge + rescue
    k1['conditions'] = [
        _check('officer_candidate_on_existing_route', officer_nodes, uncertainty, '仅审现有月藏同干透出的正官候选'),
        _check('hurting_officer_positions', hurt, uncertainty, '伤官的透干与藏干逐位置区分'),
        _check('resource_visible', [n for n in resources if n['layer'] == 'visible'], uncertainty, '透印可以进入透印救应候选审查，出现不等于有效'),
        _check('resource_hidden', [n for n in resources if n['layer'] == 'hidden'], uncertainty, '藏印保留为藏干事实，不能替代透印')]
    k1['branches'] = []
    if challenge:
        k1['branches'].append(dict(id='officer_challenged', path_ids=[e['id'] for e in challenge], status=k1['status']))
    if rescue:
        visible_rescue = [e for e in rescue if by_id[e['from_id']]['layer'] == 'visible']
        hidden_rescue = [e for e in rescue if by_id[e['from_id']]['layer'] == 'hidden']
        if visible_rescue:
            k1['branches'].append(dict(id='resource_rescue_candidate', path_ids=[e['id'] for e in visible_rescue], status=k1['status'],
                                       visible_resource_ids=[n['id'] for n in resources if n['layer'] == 'visible']))
        if hidden_rescue:
            k1['branches'].append(dict(id='hidden_resource_direction_only', path_ids=[e['id'] for e in hidden_rescue], status='withheld'))
        k1['branches'].append(dict(id='rescue_efficacy_unresolved', fact_ids=[n['id'] for n in resources], status='withheld'))
    visible_officers = [n for n in find(('正官',)) if n['layer'] == 'visible']
    visible_killers = [n for n in killers if n['layer'] == 'visible']
    resource_combinations = [deepcopy(r) for r in relations if r['kind'] == '天干五合配对'
                             and any(n['layer'] == 'visible' and n['position'] in r['positions'] for n in resources)]
    k1['conditions'] += [
        dict(id='resource_root_locations_checked', status='checked_known_pillars',
             nodes=[dict(node_id=n['id'], root_ids=list(n['same_element_root_ids'])) for n in resources], efficacy='withheld'),
        dict(id='wealth_constraints_on_resource_checked', status='checked_known_pillars',
             path_ids=[p['id'] for p in wealth_resource], efficacy='withheld'),
        dict(id='resource_stem_combinations_checked', status='checked_known_pillars',
             relations=deepcopy(resource_combinations), efficacy='withheld'),
        dict(id='month_branch_interactions_checked', status='checked_known_pillars',
             relations=deepcopy(month_relations), efficacy='withheld'),
        dict(id='officer_killer_visible_positions_checked', status='checked_known_pillars',
             officer_ids=[n['id'] for n in visible_officers], killer_ids=[n['id'] for n in visible_killers]),
        dict(id='strength_not_pattern_capacity_proof', status='withheld',
             supporting_fact_ids=list(strength['supporting_fact_ids']), counterevidence_fact_ids=list(strength['counterevidence_fact_ids']),
             source_model_conflicts=deepcopy(strength['source_model_conflicts']),
             contested_effects=deepcopy(strength['contested_effects']), unassessed_interactions=deepcopy(strength['unassessed_interactions']))]
    k1['counterevidence'] = (wealth_resource if officers else []) + resource_combinations + month_relations
    if visible_officers and visible_killers:
        k1['counterevidence'].append(dict(kind='officer_killer_both_visible',
                                           fact_ids=[n['id'] for n in visible_officers + visible_killers]))
    k1['exclusions'] = [dict(id='other_candidates_retained', candidates=deepcopy([c for c in eligible if c not in officers])),
                         dict(id='no_absence_of_other_rescue_claim', status='withheld', text='未覆盖其他救应路径，不能称无救')]
    k1['unresolved'] += ['印的同五行根、财制印、印干合和月支关系须连同核心冲合与强弱支持/反证逐项审查，均未裁决效力',
                         '偏强或偏弱趋势不证明官格承受条件；救应、成格及破格均未决']
    if not officers:
        k1['status'] = 'withheld'
        k1['unresolved'].append('本路线当前没有入选正官候选，不启用官伤印分支')

    k2 = _card('BZ-K02', by_rule['BZ-K02'], uncertainty, reasons)
    killer_nodes = candidate_nodes(killing)
    food_killer = _edges(food, killer_nodes, 'food_controls_killer', '克')
    resource_food = _edges(resources, food, 'resource_controls_food', '克') if killing else []
    wealth_killer = _edges(wealth, killer_nodes, 'wealth_generates_killer', '生')
    k2['candidates'] = deepcopy(killing)
    k2['nodes'] = [deepcopy(n) for n in nodes if n in candidate_centers(killing) + food + resources + wealth + [by_id['day.stem']]] if killing else []
    k2['paths'] = food_killer + resource_food + (wealth_resource if killing else []) + wealth_killer
    k2['conditions'] = [
        _check('killer_candidate_on_existing_route', killer_nodes, uncertainty, '偏官候选可与其他月令候选并列'),
        _check('food_not_hurting_officer', food, uncertainty, '此项只用食神，不把伤官代替食神'),
        _check('resource_visible', [n for n in resources if n['layer'] == 'visible'], uncertainty, '印克食须保留透干位置'),
        _check('resource_hidden', [n for n in resources if n['layer'] == 'hidden'], uncertainty, '藏印不能写成全无印或等同透印'),
        _check('wealth_visible', [n for n in wealth if n['layer'] == 'visible'], uncertainty, '财透与藏财分开'),
        _check('wealth_hidden', [n for n in wealth if n['layer'] == 'hidden'], uncertainty, '藏财不等于财已有效去印')]
    k2['reversal_chains'] = []
    for fedge, redge in product(food_killer, resource_food):
        if fedge['from_id'] != redge['to_id']:
            continue
        k2['reversal_chains'].append(dict(node_ids=[redge['from_id'], redge['to_id'], fedge['to_id']],
                                           path_ids=[redge['id'], fedge['id']], efficacy='withheld'))
    k2['shared_wealth_roles'] = [dict(node_id=n['id'],
                                      controls_resource_path_ids=[p['id'] for p in wealth_resource if p['from_id'] == n['id']],
                                      generates_killer_path_ids=[p['id'] for p in wealth_killer if p['from_id'] == n['id']])
                               for n in wealth if killing and any(p['from_id'] == n['id'] for p in wealth_killer)]
    k2['alternative_paths'] = _edges(resources, [by_id['day.stem']], 'resource_generates_day', '生') if killing else []
    food_combinations = [deepcopy(r) for r in relations if r['kind'] == '天干五合配对'
                         and any(n['layer'] == 'visible' and n['position'] in r['positions'] for n in food)]
    k2['conditions'] += [
        dict(id='food_root_locations_checked', status='checked_known_pillars',
             nodes=[dict(node_id=n['id'], root_ids=list(n['same_element_root_ids'])) for n in food], efficacy='withheld'),
        dict(id='food_stem_combinations_checked', status='checked_known_pillars', relations=deepcopy(food_combinations), efficacy='withheld'),
        dict(id='officer_killer_visible_positions_checked', status='checked_known_pillars',
             officer_ids=[n['id'] for n in visible_officers], killer_ids=[n['id'] for n in visible_killers]),
        dict(id='day_capacity_for_food_control', status='withheld',
             supporting_fact_ids=list(strength['supporting_fact_ids']), counterevidence_fact_ids=list(strength['counterevidence_fact_ids']),
             source_model_conflicts=deepcopy(strength['source_model_conflicts']),
             contested_effects=deepcopy(strength['contested_effects']), unassessed_interactions=deepcopy(strength['unassessed_interactions'])),
        dict(id='manual_efficacy_basis', status='withheld',
             text='当前输入只有盘面方向；没有提供足以裁决制杀、反制或救应效力的额外人工依据')]
    k2['counterevidence'] = wealth_killer + food_combinations + month_relations
    if visible_officers and visible_killers:
        k2['counterevidence'].append(dict(kind='officer_killer_both_visible',
                                           fact_ids=[n['id'] for n in visible_officers + visible_killers]))
    k2['exclusions'] = [dict(id='other_candidates_retained', candidates=deepcopy([c for c in eligible if c not in killing])),
                         dict(id='hurting_officer_not_substituted', fact_ids=[n['id'] for n in hurt])]
    k2['unresolved'] += ['食神自身根气、干合、日主承受与所有刑害效力未决，方向不等于有效制杀',
                         '印亦可生日主；同一财可制印并生杀，不据此固定喜忌或裁决哪条主导']
    if not killing:
        k2['status'] = 'withheld'
        k2['unresolved'].append('本路线当前没有入选偏官候选，不启用食杀印财链')

    k3 = _card('BZ-K03', by_rule['BZ-K03'], uncertainty, reasons)
    combinations = [r for r in relations if r['kind'] == '天干五合配对']
    k3['pairs'] = []
    for index, r in enumerate(combinations):
        a, b = r['positions']
        left, right = sorted((KEYS.index(a), KEYS.index(b)))
        endpoints = [deepcopy(by_id[a + '.stem']), deepcopy(by_id[b + '.stem'])]
        shared = []
        for other_index, other in enumerate(combinations):
            overlap = [p for p in r['positions'] if p in other['positions']]
            if index != other_index and overlap:
                shared.append(dict(pair_positions=list(other['positions']), symbols=other['symbols'], shared_positions=overlap))
        k3['pairs'].append(dict(positions=list(r['positions']), symbols=r['symbols'], adjacent=r['adjacent'],
                                role='self' if 'day' in r['positions'] else 'other', endpoints=endpoints,
                                intervening_stems=[deepcopy(by_id[p + '.stem']) for p in KEYS[left + 1:right] if p in facts],
                                shared_endpoint_pairs=shared, shared_pair_check='unknown_hour' if missing else 'checked_known_pillars',
                                efficacy='withheld'))
    k3['nodes'] = [deepcopy(n) for n in nodes if n['layer'] == 'visible']
    k3['conditions'] = [dict(id='known_stem_order', status='present', fact_ids=[n['id'] for n in k3['nodes']],
                             text='按年、月、日、时的实际位置检查，重复字保留不同位置'),
                         dict(id='shared_pair_completeness', status='unknown' if uncertainty else 'checked_known_pillars',
                              fact_ids=[n['id'] for n in k3['nodes']], text='共享同一干位置列为争合待审，不先判任何一对无效')]
    k3['exclusions'] = [dict(id='no_combination_effect_rule', status='withheld',
                              text='自身之合不能仅据配对称十神被外部合去；他干配对、相邻或隔位也不证明合去、合绊或合化'),
                         dict(id='stems_only', text='只解释天干五合，不向地支六合、三合或半合扩展')]
    k3['counterevidence'] = [dict(kind='shared_endpoint_pairs', positions=p['positions'], pairs=p['shared_endpoint_pairs'])
                              for p in k3['pairs'] if p['shared_endpoint_pairs']]
    k3['unresolved'] += ['中间干、共享位置、根气和月令只是待审条件；不删除任何原干或裁决合化效力']

    k4 = _card('BZ-K04', by_rule['BZ-K04'], uncertainty, reasons)
    k4['candidates'] = deepcopy(eligible)
    k4['semantic_objects'] = []
    finance_officer = _edges(wealth, officer_nodes, 'wealth_generates_officer', '生')
    finance_other_killers = _edges(wealth, killers, 'wealth_generates_killer', '生') if officers or killing else []
    for c in eligible:
        targets = {p + '.stem' for p in c['exposed_at']}
        assisting = []
        if c['ten_god'] == '正官':
            assisting = [dict(node_id=p['from_id'], path_ids=[p['id']], role='财生官的相神候选', efficacy='withheld')
                         for p in finance_officer if p['to_id'] in targets]
            if challenge:
                assisting += [dict(node_id=p['from_id'], path_ids=[p['id']] + [q['id'] for q in challenge if q['from_id'] == p['to_id'] and q['to_id'] in targets],
                                   role='透印制伤以护官的相神候选', efficacy='withheld')
                              for p in rescue if by_id[p['from_id']]['layer'] == 'visible']
        elif c['ten_god'] == '偏官':
            assisting = [dict(node_id=p['from_id'], path_ids=[p['id']], role='食神制杀的相神候选', efficacy='withheld')
                         for p in food_killer if p['to_id'] in targets]
        for helper in assisting:
            helper['opposing_path_ids'] = [p['id'] for p in wealth_resource + resource_food + finance_other_killers
                                           if helper['node_id'] in (p['from_id'], p['to_id'])]
        k4['semantic_objects'].append(dict(candidate_id=c['id'], status=k4['status'],
                                            month_observation_center=dict(term='月令取格用神（本路线观察中心）', fact_ids=list(c['fact_ids'])),
                                            assisting_candidates=assisting,
                                            balancing_need=dict(term='扶抑所需假设', status='withheld',
                                                                strength_decision=strength['decision'],
                                                                text='不由月令观察中心或相神候选自动生成扶抑喜忌')))
    k4['nodes'] = deepcopy(nodes) if eligible else []
    k4['paths'] = finance_officer + challenge + rescue + food_killer + resource_food + (wealth_resource if officers or killing else []) + finance_other_killers
    k4['conditions'] = [dict(id='candidate_route_binding', status='present' if eligible else ('unknown' if uncertainty else 'not_observed_known_pillars'),
                             candidate_ids=[c['id'] for c in eligible],
                             fact_ids=list(dict.fromkeys(f for c in eligible for f in c['fact_ids'])),
                             text='每个候选单列月令观察中心，辅助者必须绑定具体方向与对象')]
    k4['counterevidence'] = (wealth_resource if officers else []) + resource_food + finance_other_killers + month_relations
    k4['exclusions'] = [dict(id='no_route_expansion', text='本路线无候选时，不补入其他不透干取格法'),
                         dict(id='no_unique_favorable_element', status='withheld', text='三种语义不合并为全局唯一喜用，也不推人生结果')]
    k4['unresolved'] += ['相神候选有位置和方向仍不证明有力；其他格的辅助者未由这四项补造',
                         '相反路径和时间变化均可改变角色解释，扶抑证据仍由原模块独立给出']
    if not eligible:
        k4['status'] = 'withheld'
        k4['unresolved'].append('本路线当前没有入选候选，月令用神及相神对象暂缓绑定')
    panel['cards'] = [k1, k2, k3, k4]
    return panel


def _show(nodes):
    return '、'.join(n['text'] for n in nodes) or '已知柱未见（不推广到未知柱或其他时间场景）'


def render(panel):
    lines = ['', '### 八字获批受限结构审查', '', panel['scope'] + '。']
    if panel['source_errors']:
        lines.append('四项审查均 withheld；来源检查失败：' + '；'.join(panel['source_errors']) + '。')
        return lines
    node_text = {n['id']: n['text'] for n in panel['nodes']}
    for card in panel['cards']:
        rule = card['id']
        lines += ['', '**' + rule + ' ' + card['title'] + '【' + card['status'] + '】**']
        if rule in ('BZ-K01', 'BZ-K02'):
            lines.append('本路线观察对象：' + ('、'.join(c['name'] + '（' + '、'.join(LABELS[p] + '干' + c['stem'] for p in c['exposed_at']) + '透）' for c in card['candidates']) or '当前没有入选的相应候选') + '。')
            if card['nodes']:
                lines.append('位置与层级：' + _show(card['nodes']) + '。')
            if card['paths']:
                lines.append('可复核方向：' + '；'.join(p['text'] for p in card['paths']) + '；各边效力未决。')
            rooting = [n for n in card['nodes'] if n['layer'] == 'visible' and
                       n['ten_god'] in (RESOURCE if rule == 'BZ-K01' else RESOURCE + WEALTH + ('食神',))]
            if rooting:
                lines.append('同五行藏干根位置：' + '；'.join(n['text'] + '→' +
                             ('、'.join(node_text[i] for i in n['same_element_root_ids']) or '已知支未见')
                             for n in rooting) + '；有根仍不证明有效。')
            if rule == 'BZ-K01' and card['branches']:
                names = dict(officer_challenged='官受伤挑战', resource_rescue_candidate='透印制伤的救应候选',
                             hidden_resource_direction_only='藏印制伤方向（不替代透印救应）', rescue_efficacy_unresolved='印的救应效力仍未决')
                lines.append('并列分支：' + '；'.join(names[b['id']] for b in card['branches']) + '。')
            if rule == 'BZ-K02' and card['alternative_paths']:
                lines.append('替代解释：' + '；'.join(p['text'] for p in card['alternative_paths']) + '，不能仅按印克食给印定好坏。')
        elif rule == 'BZ-K03':
            for pair in card['pairs']:
                text = '、'.join(n['text'] for n in pair['endpoints']) + '：' + ('日干自身之合语境' if pair['role'] == 'self' else '他干之合语境')
                text += '；' + ('相邻' if pair['adjacent'] else '隔位，中间为' + _show(pair['intervening_stems']))
                if pair['role'] == 'self':
                    text += '；不能仅据自身配对称该十神被外部合去'
                if pair['shared_endpoint_pairs']:
                    text += '；共享端点的其他配对：' + '、'.join(''.join(LABELS[p] for p in q['pair_positions']) + q['symbols'] for q in pair['shared_endpoint_pairs'])
                lines.append(text + '；仅标角色，合的效力未决。')
            if not card['pairs']:
                lines.append('已知柱未检出天干五合配对；未知柱或其他时间场景仍须另查。')
        else:
            for obj in card['semantic_objects']:
                c = next(c for c in card['candidates'] if c['id'] == obj['candidate_id'])
                text = c['name'] + '：月令取格用神只指' + c['stem'] + '的观察中心'
                assisting = obj['assisting_candidates']
                text += '；相神审查为' + ('、'.join(a['role'] + '（' + node_text[a['node_id']] + '）' for a in assisting) if assisting else '本四项未建立具体辅助路径')
                lines.append(text + '；扶抑所需仍未决。')
            if not card['semantic_objects']:
                lines.append('当前没有可绑定的月令候选与相神对象；不从仍在的藏干补造本路线候选。')
        if card['counterevidence']:
            notes = [c.get('text') or c.get('kind', '') + '（' + '、'.join(LABELS[p] for p in c.get('positions', [])) + '）' for c in card['counterevidence']]
            lines.append('反向或争议事实：' + '；'.join(notes) + '。')
        lines.append('未决/限制：' + '；'.join(card['unresolved']) + '。')
        cite = card['citation']
        label = cite.get('source_label', cite.get('label', '项目原创条件释义'))
        lines.append('依据：' + label + '；' + cite['record_id'] + '；' + cite['path'] + '；范围 ' + json.dumps(cite['source_span'], ensure_ascii=False, sort_keys=True) +
                     '；固定版本 ' + str(cite.get('revision', '未标')) + '；SHA256 ' + cite['sha256'] +
                     '；许可 ' + str(cite.get('license_scope', '见登记')) + '（' + cite.get('license_path', '') + '）。')
        if cite.get('primary_sources'):
            lines.append('本卡底本定位：' + '；'.join(p['locator'] for p in cite['primary_sources']) + '。')
    primary = panel['cards'][0]['citation'].get('primary_sources', [])
    if primary:
        lines.append('共同底本：' + '；'.join(p['edition'] + '；书目固定版本 ' + str(p['revision']) +
                     '；扫描 SHA256 ' + p['artifact_sha256'] for p in primary) +
                     '；' + panel['cards'][0]['citation']['upstream_url'] + '；四项共享同一底本，不能算四份独立证据。')
    lines.append('以上为项目原创条件释义，非古籍逐字引用或预测验证；各节点的透藏、根与关系均保留，不据此确认救应、成格、合化或唯一喜忌。')
    return lines
