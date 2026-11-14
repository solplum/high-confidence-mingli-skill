"""Approved natal structure and spouse-role checks using canonical BaZi core facts."""
from copy import deepcopy

from bazi_pattern_reasoning import VERSION as EXPOSED_MONTH_ROUTE
from bazi_reviewed_structure import _nodes
from reviewed_knowledge import load_profile


PROFILE = 'bazi-primary-spouse-v1'
RULE_IDS = ('BZ-P01', 'BZ-R01')
RECORD_IDS = tuple('bazi-primary-spouse-' + rule for rule in RULE_IDS)
TITLES = dict(zip(RULE_IDS, ('乙申壬戊的局部官主印兼', '普通官用下的局部配偶支持')))
PRIMARY_BRANCH = 'officer_primary_resource_secondary'
SPOUSE_BRANCH = 'ordinary_officer_spouse_support'


def _check(id_, status, fact_ids=()):
    return dict(id=id_, status=status, fact_ids=list(fact_ids))


def _observed_status(found, incomplete):
    if found:
        return 'met'
    return 'unknown' if incomplete else 'not_met'


def _ids(nodes, *gods, layer=None):
    return [n['id'] for n in nodes if n['ten_god'] in gods and (layer is None or n['layer'] == layer)]


def _manual_checks(**checks):
    return [dict(id=id_, status='required', text=text) for id_, text in checks.items()]


def _card(rule):
    return dict(id=rule, title=TITLES[rule], status='withheld', conditions=[],
                conditional_model_result=None, citation=None, required_manual_review=[],
                manual_review_completed=False, effect_assessment='not_automatically_adjudicated')


def _primary(card, facts, visible, officer_candidates, incomplete, uncertain):
    day_matches = facts['day']['stem'] == '乙'
    month_matches = facts['month']['branch'] == '申'
    ren = [n['id'] for n in visible if n['stem'] == '壬']
    wu = [n['id'] for n in visible if n['stem'] == '戊']
    geng = [c for c in officer_candidates if c['stem'] == '庚']
    geng_ids = [id_ for candidate in geng for id_ in candidate['fact_ids']]
    card['conditions'] = [
        _check('yi_day', _observed_status(day_matches, False), ['day.stem']),
        _check('birth_shen_month', _observed_status(month_matches, False), ['month.branch']),
        _check('natal_ren_visible', _observed_status(ren, incomplete), ren),
        _check('natal_wu_visible', _observed_status(wu, incomplete), wu),
        _check('existing_eligible_geng_officer', _observed_status(geng, incomplete), geng_ids),
    ]
    if any(c['status'] == 'not_met' for c in card['conditions']):
        card['status'] = 'outside_scope'
        return
    if incomplete:
        return
    card['status'] = ('conditional_candidate_requires_manual_review' if uncertain
                      else 'conditional_requires_manual_review')
    card['conditional_model_result'] = dict(
        branch=PRIMARY_BRANCH, object='ordinary_pattern_local_role_order',
        primary='正官', accompanying='正印',
        wealth_role='正财参与生官配合', robustness='not_established',
        text='在乙日申月、壬戊实透及现行庚官候选的窄例内，官为主线，印保留兼用，财参与生官配合。')
    card['required_manual_review'] = _manual_checks(
        necessary_use_defeaters=(
            '对照实际节点与原候选，核有据的必要用途阻断并据此撤回或分支。一般合冲与生克效力未决，'
            '作为稳健性风险保留。来源给出局部主兼，不另要求预先认证财已生官或已克印。'))


def _spouse(card, nodes, officer_candidates, sex, incomplete):
    direct_wealth = _ids(nodes, '正财', layer='visible')
    indirect_wealth = _ids(nodes, '偏财', layer='visible')
    killers = _ids(nodes, '偏官', layer='visible')
    food_hurting = _ids(nodes, '食神', '伤官')
    sex_status = 'unknown' if sex not in ('男', '女') else _observed_status(sex == '男', False)
    if len(direct_wealth) > 1 or indirect_wealth:
        wealth_status = 'not_met'
    else:
        wealth_status = 'unknown' if incomplete else _observed_status(len(direct_wealth) == 1, False)
    card['conditions'] = [
        _check('traditional_male_scope', sex_status),
        _check('unique_visible_direct_wealth_no_visible_indirect_wealth',
               wealth_status, direct_wealth + indirect_wealth),
        _check('spouse_role_for_named_development_use', 'requires_manual_review'),
        _check('independent_ordinary_officer_hypothesis', 'requires_manual_review'),
    ]
    card['observations'] = dict(
        direct_wealth_visible_ids=direct_wealth, indirect_wealth_visible_ids=indirect_wealth,
        ordinary_officer_candidates=deepcopy(officer_candidates),
        resource_ids=_ids(nodes, '正印', '偏印'),
        visible_killer_ids=killers, food_hurting_ids=food_hurting)
    card['countercondition_checks'] = [
        _check('light_resource_exposed_wealth', 'requires_manual_review',
               card['observations']['resource_ids'] + direct_wealth + indirect_wealth),
        _check('food_or_hurting_with_exposed_killer_and_wealth',
               'requires_manual_review' if killers or incomplete else 'no_visible_killer_observed',
               food_hurting + killers + direct_wealth + indirect_wealth),
        _check('other_necessary_officer_use_defeaters', 'requires_manual_review'),
    ]
    if 'not_met' in (sex_status, wealth_status):
        card['status'] = 'outside_scope'
        return
    if 'unknown' in (sex_status, wealth_status):
        return
    card['status'] = 'requires_manual_review'
    card['required_manual_review'] = _manual_checks(
        actual_question='确认原问确为配偶角色对明确发展用法的支持，记录具体目标。',
        independent_hypothesis=(
            '先用已准方法独立建立可反驳的普通官用H1，记录月令、根、透、承受、配合与同目标竞争解释。'
            '候选列表只报告旧同干透出路线，候选本身不能建立H1。P1匹配可供研究官用身份，不能代替其余核查。'),
        specific_and_necessary_use_defeaters=(
            '检查印轻财露、食神／伤官透杀逢财及其他有据的必要用途阻断。'
            '印轻需独立依据，食神／伤官不额外设外透硬门。日支冲、妻宫用处与整体关系各按实际对象审查。'),
        conditional_result_and_withdrawal=(
            '匹配并审查反条后，可在H1下给既定发展用法的配偶角色支持条件评价，'
            '同时交代稳健性与翻转条件。H1撤回则该评价同步撤回。'))


def evaluate_bazi_primary_spouse(facts, relations, groups, pattern, missing, *, sex=None,
                                 temporal_uncertainty=False, scenario_id=None, root=None):
    """Build the separate natal panel. No caller assertion substitutes for R1 review."""
    cards = [_card(rule) for rule in RULE_IDS]
    uncertain = bool(temporal_uncertainty)
    unbound_uncertainty = uncertain and not (isinstance(scenario_id, str) and scenario_id.strip())
    temporal_scope = 'central_reference_only' if unbound_uncertainty else 'single_natal_input_candidate'
    panel = dict(rule_version=PROFILE, profile=PROFILE, reading_use='conditional_module_only',
                 status='withheld', cards=cards, source_errors=[], sex=sex,
                 temporal_scope=temporal_scope, scenario_id=scenario_id,
                 temporal_uncertainty=uncertain, missing_pillars=list(missing),
                 predictive_validity='unvalidated', prediction_guarantee=False)
    try:
        records = {r['rule_id']: r for r in load_profile('bazi', PROFILE, RECORD_IDS, root=root)}
        for card, branch in zip(cards, (PRIMARY_BRANCH, SPOUSE_BRANCH)):
            record = records[card['id']]
            if sum(row['key'] == branch for row in record['direction_branches']) != 1:
                raise ValueError('已批准条件支缺失或重复：' + card['id'])
            card.update(source_summary=record['summary'], source_conditions=deepcopy(record['conditions']),
                        source_exclusions=deepcopy(record['exclusions']),
                        source_direction_branches=deepcopy(record['direction_branches']),
                        source_counterexamples=deepcopy(record['counterexamples']),
                        author_adaptations=deepcopy(record['author_adaptations']),
                        time_boundaries=deepcopy(record['time_boundaries']),
                        citation=deepcopy(record['citation']))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        panel['source_errors'] = [str(exc)]
        panel['cards'] = [_card(rule) for rule in RULE_IDS]
        return panel

    incomplete = bool(missing or unbound_uncertainty)
    nodes = _nodes(facts)
    visible = [n for n in nodes if n['layer'] == 'visible' and n['position'] != 'day']
    officer_candidates = [
        dict(stem=c['stem'], route=pattern['rule_version'],
             fact_ids=['month.hidden.' + c['stem']] + [pos + '.stem' for pos in c['exposed_at']])
        for c in pattern['candidates'] if pattern['rule_version'] == EXPOSED_MONTH_ROUTE
        and c['verdict'] == 'eligible' and c['ten_god'] == '正官'
    ]
    panel.update(status='withheld' if incomplete else 'available', nodes=nodes,
                 natal_relations=deepcopy(relations + groups),
                 original_candidate_decision=pattern['decision'],
                 original_selected_candidate=pattern['selected_candidate'])
    _primary(cards[0], facts, visible, officer_candidates, incomplete, uncertain)
    _spouse(cards[1], nodes, officer_candidates, sex, incomplete)
    return panel


def render(panel, *, nested=False):
    title = '八字主兼与配偶支持（条件模型）'
    heading = ['', '**' + title + '**' if nested else '### ' + title, '']
    if panel['source_errors']:
        return heading + ['来源检查未通过。' + '。'.join(panel['source_errors'])]
    primary, spouse = panel['cards']
    lines = []
    if primary['conditional_model_result']:
        lines.extend([primary['conditional_model_result']['text'],
                      '需人工核查必要用途的反证与稳健性。依据 ' + primary['citation']['locator'] + '。'])
    if spouse['status'] == 'requires_manual_review':
        lines.extend(['配偶支持的财星事实通过筛查。方向待核具体发展目标、独立官用H1及其反条。依据 '
                      + spouse['citation']['locator'] + '。'])
    return heading + lines if lines else []
