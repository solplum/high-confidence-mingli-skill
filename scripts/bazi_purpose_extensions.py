"""MIT: independent approved candidate and purpose-condition research panel.

Consumes canonical core facts; does not choose efficacy, balance, or fortune.
"""
from copy import deepcopy

from bazi_reviewed_structure import _nodes, _edges

VERSION = 'bazi-purpose-extensions-v1'
PROFILE = VERSION
RULE_IDS = ('BZ-M01', 'BZ-M02', 'BZ-M03')
RECORD_IDS = tuple('bazi-purpose-' + rule for rule in RULE_IDS)
ROUTE = 'single-hidden-ordinary-month-v1'
ORDINARY = {'正官', '偏官', '正财', '偏财', '正印', '偏印', '食神', '伤官'}
RESOURCE = ('正印', '偏印')
WEALTH = ('正财', '偏财')
TITLES = dict(zip(RULE_IDS, ('单藏月的独立普通候选', '食神具体用法的条件核查', '夏木食神的有限印水季节用途')))


def _presence(id_, rows, missing, text):
    return dict(id=id_, status='present' if rows else ('unknown' if missing else 'not_observed_known_pillars'),
                fact_ids=[n['id'] for n in rows], text=text)


def _manual(id_, text):
    return dict(id=id_, status='withheld', text=text)


def evaluate(facts, relations, groups, pattern, strength, missing,
             temporal_uncertainty=False, scenario_id=None, root=None):
    """Return a detached panel for this input candidate, preserving old decisions."""
    uncertain = bool(missing or temporal_uncertainty)
    reasons = []
    if missing:
        reasons.append('时柱未知：未见只限已知柱，不确认全盘未透或完整竞争')
    if temporal_uncertainty:
        reasons.append('时间场景未决：本面板只属当前候选，须逐可达场景重算')
    panel = dict(rule_version=VERSION, profile=PROFILE, reading_use='conditional_module_only',
                 status='withheld' if uncertain else 'conditional', scenario_id=scenario_id,
                 temporal_scope='single_input_candidate', temporal_uncertainty=bool(temporal_uncertainty),
                 missing_pillars=list(missing), source_errors=[], cards=[],
                 predictive_validity='unvalidated', prediction_guarantee=False,
                 scope='独立候选与人工条件核查；不改旧状态，不裁效力、轻重、调候强度或净运势')
    try:
        from reviewed_knowledge import load_profile
        records = load_profile('bazi', PROFILE, RECORD_IDS, root=root)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        panel.update(status='withheld', source_errors=[str(exc)])
        panel['cards'] = [dict(id=r, title=TITLES[r], status='withheld', candidates=[], paths=[],
                               conditions=[], citation=None, unresolved=['来源检查失败：' + str(exc)])
                          for r in RULE_IDS]
        return panel

    records = {r['rule_id']: r for r in records}
    nodes = _nodes(facts)
    by_id = {n['id']: n for n in nodes}
    day = by_id['day.stem']
    resources = [n for n in nodes if n['ten_god'] in RESOURCE]
    wealth = [n for n in nodes if n['ten_god'] in WEALTH]
    food = [n for n in nodes if n['ten_god'] == '食神']
    visible_wealth = [n for n in wealth if n['layer'] == 'visible']
    all_relations = deepcopy(relations + groups)
    panel['nodes'] = deepcopy(nodes)
    panel['context'] = dict(day_stem=facts['day']['stem'], month_branch=facts['month']['branch'],
                            original_candidate_route=pattern['rule_version'],
                            original_candidate_decision=pattern['decision'],
                            original_strength_decision=strength['decision'],
                            relations=all_relations,
                            contested_effects=deepcopy(strength['contested_effects']),
                            unassessed_interactions=deepcopy(strength['unassessed_interactions']),
                            source_model_conflicts=deepcopy(strength['source_model_conflicts']))

    def card(rule):
        record = records[rule]
        return dict(id=rule, title=TITLES[rule], status='withheld' if uncertain else 'conditional',
                    reading_use='conditional_module_only', candidates=[], paths=[], conditions=[],
                    source_summary=record['summary'], source_conditions=deepcopy(record['conditions']),
                    source_exclusions=deepcopy(record['exclusions']), citation=deepcopy(record['citation']),
                    unresolved=list(reasons), effect_assessment='withheld',
                    predictive_validity='unvalidated', prediction_guarantee=False)

    m1 = card('BZ-M01')
    month = facts['month']
    hidden = month['hidden']
    m1['route'] = ROUTE
    m1['decision'] = 'outside_route'
    m1['conditions'] = [dict(id='single_hidden_month', status='met' if month['branch'] in '子卯酉' and len(hidden) == 1 else 'not_met',
                              fact_ids=['month.hidden.' + h['stem'] for h in hidden],
                              text='仅子卯酉且当前模型唯一藏干；午藏丁己及其他多藏月不适用')]
    if month['branch'] in '子卯酉' and len(hidden) == 1:
        center = hidden[0]
        if center['ten_god'] not in ORDINARY:
            m1['decision'] = 'outside_ordinary'
            m1['unresolved'].append('月令为比劫，不借此启用建禄、月刃或特殊格')
        else:
            exposed = [pos for pos, f in facts.items() if pos != 'day' and f['stem'] == center['stem']]
            exposure = 'exposed_known_pillars' if exposed else ('unknown_full_chart_exposure' if missing else 'unexposed_in_current_candidate')
            m1['decision'] = 'exposed_record' if exposed else ('incomplete_hour' if missing else 'unexposed_candidate')
            m1['candidates'] = [dict(id='month.' + center['stem'] + '.' + center['ten_god'], route=ROUTE,
                                      stem=center['stem'], ten_god=center['ten_god'],
                                      name=center['ten_god'] + '月令观察候选', month_branch=month['branch'],
                                      exposed_at=exposed, exposure_status=exposure,
                                      fact_ids=['month.hidden.' + center['stem']] + [p + '.stem' for p in exposed],
                                      full_chart_exposure_checked=not bool(missing),
                                      status='withheld' if uncertain else 'conditional')]
    if not m1['candidates']:
        m1['status'] = 'withheld'
    m1['month_branch_relations'] = [r for r in all_relations if 'month' in r['positions'] and r['kind'] != '天干五合配对']
    m1['unresolved'].append('新候选不等于成格或喜用，不接入旧BJ01-A/BZ-K消费者；合冲不自动删候选')

    candidates = {}
    for c in pattern['candidates']:
        if c['verdict'] == 'eligible' and c['ten_god'] == '食神':
            id_ = 'month.' + c['stem'] + '.食神'
            candidates[id_] = dict(id=id_, stem=c['stem'], ten_god='食神',
                                    route_ids=[pattern['rule_version']], exposed_at=list(c['exposed_at']),
                                    fact_ids=['month.hidden.' + c['stem']] + [p + '.stem' for p in c['exposed_at']])
    for c in m1['candidates']:
        if c['ten_god'] != '食神':
            continue
        if c['id'] in candidates:
            candidates[c['id']]['route_ids'].append(ROUTE)
        else:
            candidates[c['id']] = dict(id=c['id'], stem=c['stem'], ten_god='食神', route_ids=[ROUTE],
                                       exposed_at=list(c['exposed_at']), fact_ids=list(c['fact_ids']))

    m2 = card('BZ-M02')
    m2['candidates'] = list(candidates.values())
    m2['conditions'] = [dict(id='food_candidate_for_condition_review', status='present' if candidates else 'not_established_on_approved_routes',
                              fact_ids=list(dict.fromkeys(i for c in candidates.values() for i in c['fact_ids'])),
                              text='M1候选只进入条件核查，不证明食神生财或解印已成用法'),
                        _presence('wealth_visible', visible_wealth, missing, '透财与藏财分开，财透不等于解印'),
                        _presence('wealth_hidden', [n for n in wealth if n['layer'] == 'hidden'], missing, '藏财不能充当透财'),
                        _presence('resource_observed', resources, missing, '印的位置与透藏逐个保留，不由偏印名称判夺食')]
    m2['manual_checks'] = [_manual('food_generates_wealth_efficacy', '先核食神生财路线与节点作用基础'),
                            _manual('food_wealth_light_heavy', '按BJ02/BJ04独立比较财食轻重，候选不附送轻重'),
                            _manual('resource_control_and_wealth_relief', '须证明印制食制约及透财限制此制约的实际作用'),
                            _manual('capacity_and_reverse_costs', '同目标比较承受、印制食/减印、生官杀等反向成本')]
    m2['branches'] = [dict(id='food_generates_wealth', status='withheld',
                            required_manual_checks=['food_generates_wealth_efficacy', 'food_wealth_light_heavy', 'capacity_and_reverse_costs'],
                            source_options=['财食轻且用法成立时研究补财食', '财食重且用法成立时研究帮身；不等于任何印比皆宜']),
                      dict(id='effective_wealth_relief_of_resource', status='withheld',
                           required_manual_checks=['resource_control_and_wealth_relief', 'capacity_and_reverse_costs'],
                           visible_wealth_fact_ids=[n['id'] for n in visible_wealth],
                           source_options=['已有效解印的既定用法才参考财旺/食伤与印/官杀的相反取运方向'])]
    if candidates:
        m2['paths'] = (_edges(food, wealth, 'food_generates_wealth', '生') +
                       _edges(resources, food, 'resource_controls_food', '克') +
                       _edges(wealth, resources, 'wealth_controls_resource', '克') +
                       _edges(resources, [day], 'resource_generates_day', '生') +
                       _edges(wealth, [n for n in nodes if n['ten_god'] in ('正官', '偏官')], 'wealth_generates_officer_or_killer', '生'))
    else:
        m2['status'] = 'withheld'
    m2['unresolved'] += ['一般印压食/财护食已获BJ04许可；本卡新增具体用法的取运条件，不重设计七杀门槛',
                         '两条来源分支不合成普遍排序；本模块不接收预置轻重或效力答案，净首选留人工论证',
                         '大运程序沿BJ06，年/月/日投射仍为BJ07/BJ08作者外推，非本来源的短期算法']

    m3 = card('BZ-M03')
    in_domain = day['element'] == '木' and month['branch'] in '巳午未'
    water_resources = [n for n in resources if n['element'] == '水']
    m3['domain_status'] = 'summer_wood' if in_domain else 'outside_summer_wood_scope'
    m3['candidates'] = deepcopy(m2['candidates']) if in_domain else []
    m3['conditions'] = [dict(id='summer_wood_domain', status='met' if in_domain else 'not_met',
                              fact_ids=['day.stem', 'month.branch'], text='仅木日主巳午未月，冬金不适用'),
                        _presence('water_resource_observed', water_resources, missing, '只列印水事实，不把土印移作水印'),
                        dict(id='food_candidate_for_seasonal_review', status='present' if in_domain and candidates else 'not_established_on_approved_routes',
                             fact_ids=list(dict.fromkeys(i for c in m3['candidates'] for i in c['fact_ids'])))]
    m3['manual_checks'] = [_manual('fire_intensity_and_wood_dryness', '火炎木焦须独立比较，夏月或火的位置不证明强度'),
                            _manual('water_resource_efficacy', '印水须能实际作用，不以存在推有效调候'),
                            _manual('source_structure_and_output_cost', '核来源结构相容、印制食成本、财制印与承受反向路径')]
    if in_domain and candidates:
        m3['paths'] = (_edges(water_resources, [day], 'water_resource_generates_wood', '生') +
                       _edges(water_resources, food, 'water_resource_controls_food', '克') +
                       _edges(wealth, water_resources, 'wealth_controls_water_resource', '克'))
    else:
        m3['status'] = 'withheld'
    m3['unresolved'] += ['前提未独立成立时不裁季节用途；即使成立仍保留印制食成本，不推出印越多越好',
                         '不用于冬金，不启用同页其他官杀分支或全面调候、合冲效力、喜忌及净运势']
    panel['cards'] = [m1, m2, m3]
    return panel


def render(panel):
    lines = ['', '### 八字分目的受限增补（独立面板）', '', panel['scope'] + '。']
    if panel['source_errors']:
        return lines + ['来源未通过：' + '；'.join(panel['source_errors']) + '。']
    node_names = {n['id']: n['text'] for n in panel['nodes']}
    for c in panel['cards']:
        lines += ['', '**' + c['id'] + ' ' + c['title'] + '【' + c['status'] + '】**']
        if c['id'] == 'BZ-M01':
            lines.append('独立路线状态：' + c['decision'] + '。')
            for candidate in c['candidates']:
                exposure = candidate['exposure_status']
                label = {'exposed_known_pillars': '已知柱同干已透', 'unknown_full_chart_exposure': '已知柱未见同干，缺时不能确认全盘未透',
                         'unexposed_in_current_candidate': '当前完整输入候选未透同干'}[exposure]
                lines.append(candidate['name'] + '：月支' + candidate['month_branch'] + '藏' + candidate['stem'] + '；' + label + '；不等于成格或喜用。')
        else:
            if c['candidates']:
                lines.append('进入条件核查：' + '、'.join(x['stem'] + '食神（' + '、'.join(x['route_ids']) + '）' for x in c['candidates']) + '；尚未成立具体用法。')
            if c['paths']:
                lines.append('实际方向：' + '；'.join(p['text'] for p in c['paths']) + '；各边效力仍未决。')
            lines.append('人工待审：' + '；'.join(x['text'] for x in c['manual_checks']) + '。')
        used = list(dict.fromkeys(i for p in c['paths'] for i in (p['from_id'], p['to_id'])))
        if used:
            lines.append('同五行根位置：' + '；'.join(node_names[i] + '→' +
                         ('、'.join(node_names[r] for r in next(n for n in panel['nodes'] if n['id'] == i)['same_element_root_ids']) or '已知支未见')
                         for i in used) + '；有根不等于有效。')
        lines.append('限制：' + '；'.join(c['unresolved']) + '。')
        cite = c['citation']
        lines.append('依据：' + cite['source_label'] + '；' + cite['record_id'] + '；' + cite['path'] + ':' +
                     str(cite['source_span']['start_line']) + '；' + '；'.join(p['locator'] for p in cite['primary_sources']) + '。')
    return lines
