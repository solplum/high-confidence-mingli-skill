#!/usr/bin/env python3
"""Evaluate three approved Ziwei cases against an existing canonical life panel."""
from copy import deepcopy

import reviewed_knowledge as knowledge

PROFILE = 'ziwei-judgment-cases-v1'
RULE_IDS = ('ZW-RC01', 'ZW-RC02', 'ZW-RC03')
RECORD_IDS = tuple('ziwei-cases-' + rule for rule in RULE_IDS)
LIFE_PROFILE = 'ziwei-life-domains-v1'
DYNAMIC_PROFILE = 'iztro-2.6.1-lunar-year-month-v1'
KINDS = '禄权科忌'
RAW_BRIGHTNESS = ('庙', '旺', '得', '利', '平', '不', '陷')


def _name(value):
    return value[:-1] if isinstance(value, str) and value.endswith('宫') else value


def _module(rule):
    return dict(rule_id=rule, record_id='ziwei-cases-' + rule, status='withheld',
                fact_match=None, reading_use='conditional_module_only', reasons=[], checks=[],
                reality_status='not_observed_or_inferred', overall_direction='withheld',
                identity='retractable_traditional_working_hypothesis',
                direction_branches=[], selected_branch=None, counterexamples=[])


def _withhold(module, reasons):
    module.update(status='withheld', fact_match=None, reasons=list(reasons),
                  direction_branches=[], selected_branch=None)


def _actual_major(transform, domains):
    fact = transform.get('fact', {})
    return (fact.get('type') == 'major' and transform.get('star') in knowledge.STARS and
            fact.get('name') == transform.get('star') and
            any(fact == actual for domain in domains for actual in domain['facts']))


def _annual_career_placement(transform, domains):
    return _actual_major(transform, domains) and _name(transform['fact']['domain']) in ('官禄', '迁移')


def _transforms(panel, layer, *, allow_partial=False):
    rows = [row for row in panel['transformations'] if row.get('layer') == layer]
    kinds = {row.get('kind') for row in rows}
    if (len(rows) != len(kinds) or not kinds <= set(KINDS) or
            ((layer != 'natal' or not allow_partial) and len(kinds) != len(KINDS))):
        raise ValueError('缺少完整已核' + layer + '四化，不能由原始星表或其他时间层补齐')
    if any(row.get('status') not in ('conditional', 'facts_only') for row in rows):
        raise ValueError(layer + '四化未获准用于条件研究')
    if layer == 'natal':
        actual = [fact for domain in panel['domains'] for fact in domain['facts']]
        for row in rows:
            fact = row['fact']
            if ([item for item in actual if item.get('natal_transform') == row['kind']] != [fact] or
                    sum(item.get('name') == row['star'] for item in actual) != 1 or
                    fact.get('name') != row['star'] or row.get('source_path') != fact['path'] + '.siHua'):
                raise ValueError('已核本命化' + row['kind'] + '与唯一实星标记或来源路径不一致')
    return {row['kind']: row for row in rows}


def _finish(module, matched, branch=None):
    module.update(status='conditional' if matched else 'not_triggered', fact_match=bool(matched),
                  selected_branch=branch if matched else None)
    if not matched:
        module['direction_branches'] = []
        module['reasons'] = ['事实谓词不满足；不触发不能倒推出同一目标更顺、平稳或不利']


def _finish_spouse(module, branch, supporting_stars, missing_kinds):
    states = [check['matched'] for check in module['checks']]
    if False in states:
        _finish(module, False)
        return
    if None in states:
        _withhold(module, ['缺少已核固定本命四化：' + '、'.join(missing_kinds)])
        return
    unresolved = [star['name'] for star in supporting_stars
                  if star.get('brightness_conflict') or star.get('brightness_raw') not in RAW_BRIGHTNESS]
    if unresolved:
        _withhold(module, ['相关实坐主星原始亮度缺失或未知：' + '、'.join(unresolved)])
        return
    _finish(module, True, branch)


def _spouse_cases(panel, modules, *, allow_partial_natal=False):
    spouse = next(row for row in panel['domains'] if _name(row['domain']) == '夫妻')
    natal = _transforms(panel, 'natal', allow_partial=allow_partial_natal)
    majors = [fact for fact in spouse['facts'] if fact['type'] == 'major']
    power, obstacle = natal.get('权'), natal.get('忌')
    power_here = _actual_major(power, [spouse]) if power is not None else None
    obstacle_here = _actual_major(obstacle, [spouse]) if obstacle is not None else None
    separate = False
    if power_here is not False and obstacle_here is not False:
        separate = power['star'] != obstacle['star'] if power is not None and obstacle is not None else None
    rc01 = modules['ZW-RC01']
    rc01['context'] = dict(domain=deepcopy(spouse), transformations=deepcopy(list(natal.values())))
    rc01['checks'] = [dict(predicate='two_actual_spouse_major_stars', matched=len(majors) == 2),
                      dict(predicate='separate_natal_power_and_obstacle_actual_major_stars', matched=separate)]
    _finish_spouse(rc01, 'negotiation_friction', majors, [kind for kind in '权忌' if kind not in natal])
    rc02 = modules['ZW-RC02']
    jumen = False
    if any(fact['name'] == '巨门' for fact in majors):
        jumen = None if obstacle is None else obstacle_here and obstacle['star'] == '巨门'
    tiantong = any(fact['name'] == '天同' for fact in majors)
    rc02['context'] = dict(domain=deepcopy(spouse), transformations=deepcopy(list(natal.values())),
                           tiantong_actual_copresence=tiantong)
    rc02['checks'] = [dict(predicate='actual_spouse_jumen_with_natal_obstacle', matched=jumen)]
    supporting_stars = [fact for fact in majors if fact['name'] in ('巨门', '天同')]
    _finish_spouse(rc02, 'tiantong_copresent' if tiantong else 'tiantong_absent',
                   supporting_stars, ['忌'] if obstacle is None else [])
    if rc02['selected_branch'] is not None:
        rc02['direction_branches'] = [branch for branch in rc02['direction_branches']
                                      if branch.get('key') == rc02['selected_branch']]


def _surrounding(domains, anchor):
    branches = [(anchor['branch'] + offset) % 12 for offset in (0, 4, 8, 6)]
    return [deepcopy(next(row for row in domains if row['branch'] == branch)) for branch in branches]


def _annual_case(panel, module):
    card = panel['modules'].get('ZW-T02', {})
    stages = card.get('rows', [])
    if (card.get('status') != 'conditional' or len(stages) != 1 or
            stages[0].get('status') != 'conditional' or stages[0].get('errors')):
        raise ValueError('旧T02阶段未核或暂缓，不能重推年龄或借用未来大限')
    stages = stages[0]
    current = [row for row in stages.get('rows', []) if row.get('current') is True]
    no_current = not current and stages.get('current_index') == -1
    if not no_current and (len(current) != 1 or current[0].get('index') != stages.get('current_index')):
        raise ValueError('旧T02没有唯一已核当前大限')
    dynamic = panel['dynamic']
    yearly = dynamic.get('layers', {}).get('yearly', {})
    if (dynamic.get('profile') != DYNAMIC_PROFILE or dynamic.get('status') not in ('admitted', 'partial') or
            yearly.get('status') != 'admitted'):
        raise ValueError('同一查询点的准入年层缺失或暂缓；月层不能替代年层')
    query = dynamic.get('query_point')
    if (not isinstance(query, dict) or not isinstance(query.get('solar_date'), str) or
            query['solar_date'][:4] != str(stages.get('analysis_year'))):
        raise ValueError('查询点与旧T02分析年度或当前年度窗不一致，不拼接不同年度')
    stage_contract = {key: deepcopy(stages[key]) for key in (
        'age_contract', 'birth_year', 'analysis_year', 'current_age', 'current_index', 'identity', 'precision')}
    transforms = _transforms(panel, 'yearly')
    if no_current:
        covered = stages.get('covered_window')
        status = stages.get('current_status')
        if isinstance(covered, dict):
            module['context'] = dict(query_point=deepcopy(query), full_interval_coverage=False,
                                     current_stage=None, stage_contract=stage_contract,
                                     current_status=status, covered_window=deepcopy(covered))
            if status == 'before_first_stage' and query['solar_date'] < covered['start_inclusive']:
                module['checks'] = [dict(predicate='actual_current_legacy_stage_is_natal_career', matched=False)]
                _finish(module, False)
                module['reasons'] = ['查询点尚未进入首个旧大限。已排范围从 ' + covered['start_inclusive'] + ' 开始。']
                return
            if status == 'after_last_stage' and query['solar_date'] >= covered['end_exclusive']:
                raise ValueError('查询点超出已排大限。最后一个年度窗于 ' + covered['end_exclusive'] + ' 结束。')
        raise ValueError('旧T02没有唯一已核当前大限')
    current = current[0]
    if not current['window']['start_inclusive'] <= query['solar_date'] < current['window']['end_exclusive']:
        raise ValueError('查询点与旧T02分析年度或当前年度窗不一致，不拼接不同年度')
    domains = panel['domains']
    career = next(row for row in domains if _name(row['domain']) == '官禄')
    ming = next(row for row in domains if _name(row['domain']) == '命')
    module['context'] = dict(query_point=deepcopy(query), full_interval_coverage=False,
                            admitted_yearly=dict(profile=dynamic.get('profile'), layer=deepcopy(yearly)),
                            current_stage=deepcopy(current), stage_contract=stage_contract,
                            natal_ming_surrounding=_surrounding(domains, ming),
                            career_stage_surrounding=_surrounding(domains, career),
                            transformations=deepcopy(panel['transformations']),
                            nonmajor_policy='facts_only_no_new_nature_or_weight',
                            unresolved_modifiers='保留本命及年/月全部四化和实际星表；未核交互不相加、抵消或自动取消本例')
    module['checks'] = [dict(predicate='actual_current_legacy_stage_is_natal_career',
                             matched=_name(current['domain']) == '官禄')]
    for kind in ('禄', '权'):
        transform = transforms[kind]
        module['checks'].append(dict(predicate='yearly_' + kind + '_direct_actual_major_in_natal_career_or_travel',
                                     matched=_annual_career_placement(transform, domains),
                                     evidence=deepcopy(transform)))
    _finish(module, all(check['matched'] for check in module['checks']), 'proactive_application_fit')


def evaluate(existing_canonical_life_panel, root=None, input_errors=None, *, natal_transform_error=None):
    """Return detached case research; never load charts, infer ages, or read raw layers."""
    result = dict(version=PROFILE, profile=PROFILE, reading_use='conditional_module_only', status='withheld',
                  predictive_validity='unvalidated', prediction_guarantee=False,
                  source_errors=[], input_errors=[], modules={rule: _module(rule) for rule in RULE_IDS},
                  scope='两条本命夫妻协商局部假说与一条查询点年度行动适配；不输出整体吉凶或事件',
                  overall_direction='withheld', full_interval_coverage=False)
    modules = result['modules']
    try:
        records = knowledge.load_profile('ziwei', PROFILE, RECORD_IDS, root=root)
        if {row['rule_id'] for row in records} != set(RULE_IDS):
            raise ValueError('三项判例卡身份不完整')
        for record in records:
            module = modules[record['rule_id']]
            module.update(title=record['title'], summary=record['summary'],
                          source_conditions=deepcopy(record['conditions']),
                          source_exclusions=deepcopy(record['exclusions']), citation=deepcopy(record['citation']),
                          direction_branches=deepcopy(record['direction_branches']),
                          counterexamples=deepcopy(record['counterexamples']),
                          author_adaptations=deepcopy(record.get('author_adaptations', [])),
                          time_boundaries=deepcopy(record['time_boundaries']),
                          source_identity=record['source_identity'])
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        result['source_errors'] = [str(exc)]
        for module in modules.values():
            _withhold(module, result['source_errors'])
        return result
    try:
        panel = existing_canonical_life_panel
        if (not isinstance(panel, dict) or panel.get('profile') != LIFE_PROFILE or
                panel.get('version') != LIFE_PROFILE):
            raise ValueError('必须提供已核ziwei-life-domains-v1面板')
        domains = panel.get('domains')
        if (not isinstance(domains, list) or len(domains) != 12 or
                len({_name(row['domain']) for row in domains}) != 12 or
                any(not isinstance(row.get('facts'), list) for row in domains)):
            raise ValueError('缺少已核十二宫完整实际星表')
        result['facts'] = dict(domains=deepcopy(domains), transformations=deepcopy(panel['transformations']))
        panel_errors = list(panel.get('input_errors', []))
        if isinstance(natal_transform_error, str) and natal_transform_error in panel_errors:
            panel_errors.remove(natal_transform_error)
            result['natal_transform_error'] = natal_transform_error
        else:
            natal_transform_error = None
        errors = list(panel.get('source_errors', [])) + panel_errors + list(input_errors or [])
        if panel.get('temporal_uncertainty'):
            errors.append('出生时间不确定：保留候选事实，暂缓判例个人化')
        if errors:
            raise ValueError('；'.join(errors))
        try:
            _spouse_cases(panel, modules, allow_partial_natal=natal_transform_error is not None)
        except (ValueError, KeyError, TypeError, IndexError, StopIteration, AttributeError) as exc:
            for rule in RULE_IDS[:2]:
                _withhold(modules[rule], [str(exc)])
        if natal_transform_error is not None:
            _withhold(modules['ZW-RC03'], [natal_transform_error])
        else:
            try:
                _annual_case(panel, modules['ZW-RC03'])
            except (ValueError, KeyError, TypeError, IndexError, StopIteration, AttributeError) as exc:
                _withhold(modules['ZW-RC03'], [str(exc)])
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        result['input_errors'] = [str(exc)]
        for module in modules.values():
            _withhold(module, result['input_errors'])
        return result
    statuses = {module['status'] for module in modules.values()}
    result['status'] = ('partial' if 'withheld' in statuses and len(statuses) > 1 else
                        'conditional' if 'conditional' in statuses else
                        'withheld' if statuses == {'withheld'} else 'not_triggered')
    return result
