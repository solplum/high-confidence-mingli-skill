#!/usr/bin/env python3
"""Match approved Ziwei models against the canonical natal and legacy stage facts."""
from copy import deepcopy

import reviewed_knowledge as knowledge
from ziwei_case_judgments import LIFE_PROFILE, RAW_BRIGHTNESS, _name, _surrounding, _transforms

PROFILE = 'ziwei-stage-relationship-v1'
STAGE_RULES = tuple('ZW-ST%02d' % i for i in range(1, 10))
RELATIONSHIP_RULE = 'ZW-RL01'
RULE_IDS = (*STAGE_RULES, RELATIONSHIP_RULE)
RECORD_IDS = tuple('ziwei-stage-relationship-' + rule for rule in RULE_IDS)
BRANCHES = dict(zip(RULE_IDS, (
    ('tianfu_progress',), ('taiyang_mao_support', 'taiyang_zi_fire_ji'),
    ('taiyin_chou_support', 'taiyin_si_counter'), ('wuqu_quan_progress',),
    ('tianxiang_pursuit', 'tianxiang_yang_restriction'), ('tianliang_progress',),
    ('tiantong_zi_progress', 'tiantong_hai_progress', 'tiantong_wu_opposite_fire'),
    ('tanlang_coordination',), ('pojun_resource_support',),
    ('sun_giant_gate_stability',),
)))
FOUR_MALEFICS = {'擎羊', '陀罗', '火星', '铃星'}
SIX_MALEFICS = FOUR_MALEFICS | {'地空', '地劫'}
MALEFIC_PREDICATES = {'clear_four', 'clear_six', 'same_palace_fire', 'same_palace_qingyang', 'opposite_fire'}
# Approved source/native compatibility in Zi-to-Hai branch order. A missing
# value is an excluded position, not a substitute brightness or direction.
WUQU_COMPATIBILITY = '旺庙得利庙平旺庙得利庙平'
TIANXIANG_COMPATIBILITY = '庙庙庙陷得得庙得庙陷得得'
TIANLIANG_COMPATIBILITY = ('庙', None, '庙', '庙', '庙', None,
                           '庙', None, '陷', '得', '庙', None)


def _load_cards(root):
    records = knowledge.load_profile('ziwei', PROFILE, RECORD_IDS, root=root)
    cards = {row['rule_id']: row for row in records}
    if set(cards) != set(RULE_IDS) or len(records) != len(cards):
        raise ValueError('阶段及关系卡的规则身份不完整')
    for rule, row in cards.items():
        keys = [item['key'] for item in row['direction_branches']]
        if len(keys) != len(set(keys)) or set(keys) != set(BRANCHES[rule]):
            raise ValueError(rule + '的已批准分支缺失或多出未批准分支')
    return cards


def _match(card, alternatives, seats, observation=None):
    selected = next((key for key, tests in alternatives.items() if all(tests.values())), None)
    observed = observation is not None and all(observation[1].values())
    tests_by_branch = list(alternatives.values())
    if observation is not None:
        tests_by_branch.append(observation[1])
    missing = {key for tests in tests_by_branch if all(value is not False for value in tests.values())
               for key, value in tests.items() if value is None}
    pending = not selected and bool(missing)
    row = dict(
        record_id=card['id'], status='conditional' if selected else 'facts_only' if observed else 'withheld' if pending else 'not_triggered',
        fact_match=None if pending else selected is not None, selected_branch=selected, checks=alternatives,
        actual_major_facts=deepcopy([fact for fact in seats if fact is not None]),
        direction_branches=[deepcopy(branch) for branch in card['direction_branches'] if branch['key'] == selected],
        counter_observations=[deepcopy(branch) for branch in card['direction_branches']
                              if observed and branch['key'] == observation[0]],
        overall_direction='withheld',
    )
    if pending:
        row['reasons'] = []
        if any('natal' in key for key in missing):
            row['reasons'].append('本命年干或所需固定本命四化未核')
        if missing & MALEFIC_PREDICATES:
            row['reasons'].append('所需原生煞曜位置缺失或不唯一')
        if any('raw' in key or key.startswith('compatible_actual_') for key in missing):
            row['reasons'].append('所需实坐主星原始亮度未核')
    return row


def _context(domains, anchor):
    surrounding = _surrounding(domains, anchor)
    malefics = [fact for domain in surrounding for fact in domain['facts'] if fact['name'] in SIX_MALEFICS]
    # iztro 2.6.1 getMinorStar places each of these origin stars once;
    # a truncated or duplicate snapshot cannot certify an empty position.
    occurrences = {name: [] for name in sorted(SIX_MALEFICS)}
    for domain in domains:
        for fact in domain['facts']:
            if fact['name'] in occurrences:
                occurrences[fact['name']].append(fact)
    positions = {name: facts[0]['branch'] if len(facts) == 1 and facts[0]['type'] == 'sha' else None
                 for name, facts in occurrences.items()}
    return dict(anchor=anchor['branch'], surrounding=[dict(branch=row['branch'], domain=row['domain'],
                                                           fact_paths=[fact['path'] for fact in row['facts']])
                                                     for row in surrounding],
                selected_malefic_facts=malefics, verified_malefic_positions=positions)


def _located_in(context, name, branches):
    position = context['verified_malefic_positions'][name]
    return position in branches if position is not None else None


def _clear(context, names):
    surrounding = {row['branch'] for row in context['surrounding']}
    observed = [_located_in(context, name, surrounding) for name in names]
    if True in observed:
        return False
    return None if None in observed else True


def _stage_modules(anchor, context, natal, cards, natal_year_stem):
    branch = anchor['branch']
    actual = {fact['name']: fact for fact in anchor['facts'] if fact['type'] == 'major'}

    def seat_level(name, expected):
        if expected is None or name not in actual:
            return False
        if actual[name].get('brightness_conflict'):
            return None
        raw = actual[name].get('brightness_raw')
        return raw == expected if raw in RAW_BRIGHTNESS else None

    natal = natal or {}
    obstacle, power = natal.get('忌'), natal.get('权')
    clear_four = _clear(context, FOUR_MALEFICS)
    no_natal_ji_here = obstacle['fact']['branch'] != branch if obstacle is not None else None
    stem_known = natal_year_stem is not None
    opposite_fire = _located_in(context, '火星', {(branch + 6) % 12})
    same_palace_fire = _located_in(context, '火星', {branch})
    liang_brightness = TIANLIANG_COMPATIBILITY[branch]

    # Each branch is its own object and reading. No branch cancels a different
    # one or uses votes to produce a stage or lifelong result.
    return {
        'ZW-ST01': _match(cards['ZW-ST01'], {'tianfu_progress': dict(actual_tianfu='天府' in actual)},
                          [actual.get('天府')]),
        'ZW-ST02': _match(cards['ZW-ST02'], {
            'taiyang_mao_support': dict(mao_actual_taiyang_raw_temple=branch == 3 and seat_level('太阳', '庙'),
                                       clear_four=clear_four, no_natal_ji_in_seat=no_natal_ji_here),
            'taiyang_zi_fire_ji': dict(zi_actual_taiyang_raw_fallen=branch == 0 and seat_level('太阳', '陷'),
                                       same_palace_fire=same_palace_fire,
                                       compatible_natal_jia=natal_year_stem == 0 if stem_known else None,
                                       natal_taiyang_ji=actual.get('太阳') == obstacle['fact'] if obstacle is not None else None),
        }, [actual.get('太阳')]),
        'ZW-ST03': _match(cards['ZW-ST03'], {
            'taiyin_chou_support': dict(chou_actual_taiyin_raw_temple=branch == 1 and seat_level('太阴', '庙'),
                                       clear_four=clear_four, no_natal_ji_in_seat=no_natal_ji_here),
        }, [actual.get('太阴')], observation=('taiyin_si_counter', dict(
            si_actual_taiyin_raw_fallen=branch == 5 and seat_level('太阴', '陷'),
            same_palace_fire=same_palace_fire))),
        'ZW-ST04': _match(cards['ZW-ST04'], {'wuqu_quan_progress': dict(
            compatible_actual_wuqu=seat_level('武曲', WUQU_COMPATIBILITY[branch]),
            compatible_natal_geng=natal_year_stem == 6 if stem_known else None,
            natal_wuqu_quan=actual.get('武曲') == power['fact'] if power is not None else None,
        )}, [actual.get('武曲')]),
        'ZW-ST05': _match(cards['ZW-ST05'], {
            'tianxiang_pursuit': dict(compatible_actual_tianxiang=seat_level('天相', TIANXIANG_COMPATIBILITY[branch]),
                                     clear_six=_clear(context, SIX_MALEFICS)),
            'tianxiang_yang_restriction': dict(
                compatible_actual_tianxiang=seat_level('天相', TIANXIANG_COMPATIBILITY[branch]),
                same_palace_qingyang=_located_in(context, '擎羊', {branch})),
        }, [actual.get('天相')]),
        'ZW-ST06': _match(cards['ZW-ST06'], {'tianliang_progress': dict(
            compatible_actual_tianliang=seat_level('天梁', liang_brightness),
            clear_four=clear_four,
        )}, [actual.get('天梁')]),
        'ZW-ST07': _match(cards['ZW-ST07'], {
            'tiantong_zi_progress': dict(zi_actual_tiantong_raw_prosperous=branch == 0 and seat_level('天同', '旺'),
                                         clear_four=clear_four),
            'tiantong_hai_progress': dict(hai_actual_tiantong_raw_temple=branch == 11 and seat_level('天同', '庙'),
                                          clear_four=clear_four),
            'tiantong_wu_opposite_fire': dict(wu_actual_tiantong_raw_fallen=branch == 6 and seat_level('天同', '陷'),
                                              opposite_fire=opposite_fire),
        }, [actual.get('天同')]),
        'ZW-ST08': _match(cards['ZW-ST08'], {'tanlang_coordination': dict(
            compatible_actual_tanlang_raw_temple=branch in (1, 4, 7, 10) and seat_level('贪狼', '庙'),
        )}, [actual.get('贪狼')]),
        'ZW-ST09': _match(cards['ZW-ST09'], {'pojun_resource_support': dict(
            compatible_actual_pojun_raw_temple=branch in (0, 6) and seat_level('破军', '庙'),
            clear_four=clear_four,
        )}, [actual.get('破军')]),
    }


def _status(statuses):
    if 'withheld' in statuses:
        return 'withheld' if statuses == {'withheld'} else 'partial'
    for status in ('conditional', 'facts_only'):
        if status in statuses:
            return status
    return 'not_triggered'


def _validated_domains(panel):
    if not isinstance(panel, dict) or panel.get('profile') != LIFE_PROFILE or panel.get('version') != LIFE_PROFILE:
        raise ValueError('必须提供已核ziwei-life-domains-v1面板')
    domains = panel['domains']
    if (len(domains) != 12 or {row['branch'] for row in domains} != set(range(12)) or
            len({_name(row['domain']) for row in domains}) != 12 or
            any(not isinstance(row['facts'], list) for row in domains)):
        raise ValueError('缺少已核十二宫完整实际星表')
    actual = [fact for domain in domains for fact in domain['facts']]
    if sorted(fact['name'] for fact in actual if fact['type'] == 'major') != sorted(knowledge.STARS):
        raise ValueError('十四实际主星缺失或重复')
    return domains


def _stages(panel, domains, cards, natal_year_stem, natal_transform_error):
    card = panel['modules'].get('ZW-T02', {})
    rows = card.get('rows', [])
    if card.get('status') != 'conditional' or len(rows) != 1 or rows[0]['status'] != 'conditional' or rows[0]['errors']:
        raise ValueError('旧T02年度窗未核或暂缓，不另行计算年龄或取其他时间层')
    contract = rows[0]
    natal = _transforms(panel, 'natal', allow_partial=natal_transform_error is not None)
    facts = [fact for domain in domains for fact in domain['facts']]
    if any(transform['fact'] not in facts for transform in natal.values()):
        raise ValueError('已核固定本命四化未附着于实际星表')
    stages = []
    by_branch = {domain['branch']: domain for domain in domains}
    for stage in contract['rows']:
        anchor = by_branch[stage['native']['palaceBranch']]
        if _name(anchor['domain']) != _name(stage['domain']):
            raise ValueError('旧T02实坐宫位与本命星表冲突')
        context = _context(domains, anchor)
        modules = _stage_modules(anchor, context, natal, cards, natal_year_stem)
        stages.append(dict(legacy_stage=deepcopy(stage), context=context, modules=modules,
                           status=_status({module['status'] for module in modules.values()}),
                           overall_direction='withheld'))
    return ({key: deepcopy(value) for key, value in contract.items() if key != 'rows'}, stages)


def _relationship(domains, card):
    anchor = next(row for row in domains if _name(row['domain']) == '夫妻')
    context = _context(domains, anchor)
    seats = [fact for fact in anchor['facts'] if fact['type'] == 'major' and fact['name'] in ('太阳', '巨门')]
    result = _match(card, {'sun_giant_gate_stability': dict(sun_and_giant_gate_actual_copresence=len(seats) == 2,
                                                           clear_six=_clear(context, SIX_MALEFICS))}, seats)
    result['context'] = context
    return result


def evaluate(existing_canonical_life_panel, root=None, input_errors=None, *,
             natal_year_stem=None, natal_transform_error=None):
    """Return model branches with fact paths, without calculating or combining time layers."""
    stem = natal_year_stem if type(natal_year_stem) is int and 0 <= natal_year_stem < 10 else None
    result = dict(profile=PROFILE, version=PROFILE, reading_use='conditional_module_only', status='withheld',
                  predictive_validity='unvalidated', prediction_guarantee=False,
                  overall_direction='withheld', full_interval_coverage=False,
                  natal_year_stem=dict(value=stem, path='chart.lunarInfo.yearStem'),
                  source_errors=[], input_errors=[], stage_errors=[], stage_status='withheld',
                  stages=[], stage_contract=None, cards={},
                  relationship=dict(record_id=RECORD_IDS[-1], status='withheld', fact_match=None, selected_branch=None,
                                    direction_branches=[], overall_direction='withheld'))
    try:
        cards = _load_cards(root)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        result['source_errors'] = [str(exc)]
        return result
    result['cards'] = cards
    panel = existing_canonical_life_panel
    try:
        domains = _validated_domains(panel)
        panel_errors = list(panel.get('input_errors', []))
        if isinstance(natal_transform_error, str) and natal_transform_error in panel_errors:
            panel_errors.remove(natal_transform_error)
            result['natal_transform_error'] = natal_transform_error
        else:
            natal_transform_error = None
        errors = [*panel.get('source_errors', []), *panel_errors, *(input_errors or [])]
        if panel.get('temporal_uncertainty'):
            errors.append('出生时间不确定，阶段和夫妻模型暂缓个人化')
        if errors:
            result['input_errors'] = errors
            return result
        result['relationship'] = _relationship(domains, cards[RELATIONSHIP_RULE])
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, StopIteration) as exc:
        result['input_errors'] = [str(exc)]
        return result
    try:
        contract, stages = _stages(panel, domains, cards, stem, natal_transform_error)
        result.update(stage_contract=contract, stages=stages, stage_status=_status({stage['status'] for stage in stages}))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, StopIteration) as exc:
        result['stage_errors'] = [str(exc)]
    result['status'] = _status({result['stage_status'], result['relationship']['status']})
    return result
