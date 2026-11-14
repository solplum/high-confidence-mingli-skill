"""Approved Xin/zi ordinary-condition matcher; no efficacy or time calculator.

The caller supplies canonical natal facts and, for temporal adaptation, facts
already derived by the existing engine. Matching never completes the separate
manual review of source applicability and supported defeating effects.
"""
from bisect import bisect_right
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pai_pan_bazi as engine
from bazi_primary_spouse import PROFILE as PRIMARY_SPOUSE_PROFILE
from bazi_reviewed_structure import KEYS, _nodes, relations_from_facts
from time_scenarios import check_timezone_source, parse_query_point

VERSION = 'bazi-qiong-xin-zi-v1'
PROFILE = VERSION
RECORD_IDS = tuple('bazi-qiong-QX%02d' % i for i in range(1, 4))
LEVELS = ('luck', 'year', 'month', 'day')
ADAPTATIONS = dict(zip(LEVELS, ('BJ06', 'BJ07', 'BJ08', 'BJ08')))


def _records(root):
    from reviewed_knowledge import load_profile
    return {r['rule_id']: r for r in load_profile('bazi', PROFILE, RECORD_IDS, root=root)}


def _window_bounds(label):
    """Read an explicit half-open window while retaining legacy prose labels."""
    label = label.strip()
    if not (label.startswith('[') and label.endswith(')')):
        return None
    endpoints = [part.strip() for part in label[1:-1].split(',')]
    if len(endpoints) != 2:
        return None
    try:
        points = [parse_query_point(part) for part in endpoints]
    except ValueError:
        return None
    return points if all(point.utcoffset() is not None for point in points) else None


def _query_window_bounds(window):
    bounds = _window_bounds(window) if isinstance(window, str) else None
    if bounds is None or bounds[0] >= bounds[1] or bounds[0].utcoffset() != bounds[1].utcoffset():
        raise ValueError('本次查询须为正长度、同一固定偏移的 ISO 半开窗口')
    return bounds


def _period_rows(rows, expected_window):
    if not isinstance(rows, (list, tuple)) or len(rows) > len(LEVELS):
        raise ValueError('时间层须为运、年、月、日的连续前缀')
    expected = _query_window_bounds(expected_window) if expected_window is not None else None
    result, windows = [], []
    valid_pillars = {''.join(engine.gz_from_index(i)) for i in range(60)}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get('layer') != LEVELS[index]:
            raise ValueError('时间层须依次提供运、年、月、日，不能跳过或重复')
        if 'pillar' not in row or (row['pillar'] is not None and
                                   (not isinstance(row['pillar'], str) or row['pillar'] not in valid_pillars)):
            raise ValueError('非规范时间干支：' + row['layer'])
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('source', 'window')):
            raise ValueError('时间层须保留事实来源及有效窗口：' + row['layer'])
        bounds = _window_bounds(row['window'])
        if bounds is not None:
            windows.append(bounds)
        if expected is not None:
            if bounds is not None and (bounds[0] > expected[0] or bounds[1] < expected[1]):
                raise ValueError('时间层窗口不覆盖本次查询分段：' + row['layer'])
            if row['pillar'] is not None and row['layer'] != 'luck':
                if bounds is None:
                    raise ValueError('绑定查询时，已知年月日层须提供可核的 ISO 窗口：' + row['layer'])
                if row['layer'] == 'day' and any(point.utcoffset() != expected[0].utcoffset()
                                                for point in bounds):
                    raise ValueError('日层须使用本次查询的固定民用偏移')
        result.append({k: deepcopy(row[k]) for k in ('layer', 'pillar', 'source', 'window')})
    if windows and max(start for start, _ in windows) >= min(end for _, end in windows):
        raise ValueError('可核对的时间层窗口没有共同有效时段，须用同一查询区间的事实')
    known_calendar = [row for row in result[1:] if row['pillar'] is not None] if expected is not None else []
    if known_calendar:
        from bazi_period_facts import period_facts

        segments = period_facts(*expected, known_calendar[-1]['layer'])['segments']
        for row in known_calendar:
            layer = row['layer']
            actual = {fact['pillar'] for segment in segments for fact in segment['facts'] if fact['layer'] == layer}
            if len(actual) > 1:
                raise ValueError('本次查询分段跨越原引擎干支换界：' + layer)
            if actual != {row['pillar']}:
                raise ValueError('本次查询分段干支与原引擎不一致：' + layer)
    return result


def _temporal_nodes(rows, day_stem):
    nodes = []
    for row in rows:
        if row['pillar'] is None:
            continue
        stem, branch = row['pillar']
        position = 'temporal.' + row['layer']
        nodes.append(dict(id=position + '.stem', position=position, layer='visible',
                          stem=stem, element=engine.GAN_WUXING[engine.GAN.index(stem)],
                          ten_god=engine.shishen_of(engine.GAN.index(day_stem), engine.GAN.index(stem))))
        for hidden, element in engine.CANGGAN[branch]:
            nodes.append(dict(id=position + '.hidden.' + hidden, position=position,
                              layer='hidden', stem=hidden, element=element,
                              ten_god=engine.shishen_of(engine.GAN.index(day_stem), engine.GAN.index(hidden))))
    return nodes


def _evaluate(facts, relations, groups, missing, uncertain, scenario_id, rows, records, errors):
    scope = rows[-1]['layer'] if rows else 'natal'
    panel = dict(rule_version=VERSION, profile=PROFILE, reading_use='conditional_module_only',
                 status='withheld', temporal_scope=scope, scenario_id=scenario_id,
                 temporal_uncertainty=bool(uncertain), missing_pillars=list(missing),
                 temporal_facts=deepcopy(rows), source_errors=list(errors), cards=[],
                 facts_origin='canonical_core_facts_and_caller_supplied_engine_period_facts',
                 natal_pillars={k: v['pillar'] for k, v in facts.items()},
                 full_interval_coverage=False, predictive_validity='unvalidated',
                 prediction_guarantee=False,
                 result_scope='single_input_candidate', interval_stability_assessed=False,
                 unique_input_result=not bool(uncertain or missing),
                 conditional_model_direction='withheld', matched_branch=None,
                 manual_review_completed=False,
                 effect_assessment='not_automatically_adjudicated',
                 scope='辛日出生子月的普通整体／发展条件模型；机械匹配不代替人工作用与适配复审')
    if errors:
        return panel
    panel['cards'] = [dict(id=r['rule_id'], source_summary=r['summary'],
                           source_conditions=deepcopy(r['conditions']),
                           source_exclusions=deepcopy(r['exclusions']),
                           direction_branches=deepcopy(r['direction_branches']),
                           citation=deepcopy(r['citation'])) for r in records.values()]
    nodes = deepcopy(_nodes(facts)) + _temporal_nodes(rows, facts['day']['stem'])
    visible = lambda stem: [n['id'] for n in nodes if n['layer'] == 'visible' and n['stem'] == stem]
    hidden = lambda stem: [n['id'] for n in nodes if n['layer'] == 'hidden' and n['stem'] == stem]
    fire_roots = [n['id'] for n in nodes if n['layer'] == 'hidden' and n['element'] == '火']
    unknown_layers = [r['layer'] for r in rows if r['pillar'] is None]
    unbound_uncertainty = bool(uncertain and not (isinstance(scenario_id, str) and scenario_id.strip()))
    incomplete = bool(missing or unbound_uncertainty or unknown_layers)
    observed = dict(bing_visible_ids=visible('丙'), ren_visible_ids=visible('壬'),
                    ren_hidden_ids=hidden('壬'), wu_visible_ids=visible('戊'),
                    gui_visible_ids=visible('癸'), direct_bing_hidden_root_ids=hidden('丙'),
                    same_element_fire_root_ids=fire_roots)
    panel.update(nodes=nodes, observed=observed, unknown_temporal_layers=unknown_layers,
                 unique_input_result=not bool(uncertain or missing or unknown_layers),
                 natal_relations=deepcopy(relations + groups),
                 root_definition='current_project_same_element_hidden_stem_structure_not_source_complete_root_theory',
                 source_model_identity='selected_B_reading_and_author_M0',
                 temporal_adaptations=[dict(layer=r['layer'], author_rule=ADAPTATIONS[r['layer']]) for r in rows])
    subject = facts['day']['stem'] == '辛' and facts['month']['branch'] == '子'
    evidence = [dict(id='xin_day_birth_zi_month', status='met' if subject else 'not_met',
                     fact_ids=['day.stem', 'month.branch'])]
    for key in ('bing_visible_ids', 'ren_visible_ids', 'ren_hidden_ids', 'wu_visible_ids',
                'gui_visible_ids', 'same_element_fire_root_ids'):
        evidence.append(dict(id=key, status='present' if observed[key] else
                             ('unknown_in_full_set' if incomplete else 'not_observed_in_evaluated_set'),
                             fact_ids=list(observed[key])))
    panel['condition_facts'] = evidence
    panel['required_manual_review'] = [
        dict(id='source_and_temporal_applicability', rule_ids=['BZ-QX01', 'BZ-QX02'],
             status='required', source_conditions=deepcopy(records['BZ-QX01']['conditions'])),
        dict(id='supported_necessary_use_defeaters_and_same_scope_counterevidence', rule_ids=['BZ-QX03'],
             status='required', source_conditions=deepcopy(records['BZ-QX03']['conditions'])),
    ]
    panel['robustness'] = dict(
        status='not_established', general_interaction_effects='unresolved_not_zero',
        temporal_interactions_review='required' if rows else 'not_applicable',
        interpretation_alternative=deepcopy(records['BZ-QX02']['direction_branches'][1]['counterconditions']),
        positive_exit_conditions=deepcopy(records['BZ-QX03']['direction_branches'][0]['counterconditions']),
        empirical_validity='unknown_without_corresponding_frozen_outcome_data')
    panel['alternative_conservative_reading'] = dict(
        ordinary_positive='not_established', reason='未匹配所选B或所评集合不完整')
    if not subject:
        panel.update(status='outside_scope', conditional_model_direction='outside_scope')
        return panel
    has_bing_root = bool(observed['bing_visible_ids'] and fire_roots)
    gui_counter = has_bing_root and bool(observed['gui_visible_ids'])
    panel['specific_gui_countercondition'] = dict(
        status='present' if gui_counter else ('unknown' if incomplete else 'not_observed'),
        fact_ids=observed['bing_visible_ids'] + fire_roots + observed['gui_visible_ids'],
        source_rule='BZ-QX03', rescue_assessment='not_established_by_pairing_or_presence')
    # Unknown hour or a missing upper layer can hide Ren/Gui exposure. It cannot
    # be treated as an empty layer to enter B or prove the ordinary gate clear.
    if incomplete:
        panel['incomplete_reasons'] = (['时柱未知'] if missing else []) + (
            ['出生时间场景未决且未标明具体候选，本结果不能推广到区间'] if unbound_uncertainty else []) + [
            '时间层未知：' + layer for layer in unknown_layers]
        return panel
    panel['status'] = 'conditional_candidate_requires_manual_review' if uncertain else 'conditional_requires_manual_review'
    if gui_counter:
        branch = records['BZ-QX03']['direction_branches'][0]
        panel.update(conditional_model_direction='development_support_restricted',
                     matched_branch=branch['key'], source_direction=branch['direction'])
        return panel
    a = has_bing_root and bool(observed['ren_visible_ids']) and not observed['wu_visible_ids']
    b = has_bing_root and bool(observed['ren_hidden_ids']) and not observed['ren_visible_ids']
    if a or b:
        branch = records['BZ-QX02']['direction_branches'][0 if a else 1]
        panel.update(conditional_model_direction='development_configuration_relatively_favorable',
                     matched_branch=branch['key'], source_direction=branch['direction'])
        if b:
            panel['alternative_conservative_reading'] = dict(
                ordinary_positive='not_established' if observed['wu_visible_ids'] else 'same_factual_gate_met',
                reason='保守继承无戊字面门：戊透退出普通正支；退出不自动等于负评' if observed['wu_visible_ids']
                else '未见戊癸透，保守字面门亦不因该项退出；作用性否定仍需独立核查')
    else:
        panel['conditional_model_direction'] = 'ordinary_positive_not_established'
    return panel


def evaluate(facts, relations, groups, missing, temporal_uncertainty=False, scenario_id=None, root=None):
    """Match one canonical natal input; never alter the supplied core evidence."""
    try:
        records, errors = _records(root), []
    except (ValueError, OSError, KeyError, ImportError) as exc:
        records, errors = {}, [str(exc)]
    return _evaluate(facts, relations, groups, missing, temporal_uncertainty,
                     scenario_id, [], records, errors)


def _validated_natal_pillars(facts, missing):
    if (not isinstance(facts, dict) or missing not in ([], ['hour']) or
            set(facts) != set(KEYS).difference(missing)):
        raise ValueError('需要当前core的原局四柱事实及缺柱记录')
    pillars = {}
    for position, row in facts.items():
        value = row.get('pillar') if isinstance(row, dict) else None
        if not isinstance(value, str) or len(value) != 2 or value[0] not in engine.GAN or value[1] not in engine.ZHI:
            raise ValueError('原局干支字段无效：' + position)
        pillars[position] = value
    day_index = engine.GAN.index(pillars['day'][0])
    for position, (stem, branch) in pillars.items():
        fact = facts[position]
        expected = engine.pillar_fact(stem, branch, day_index, is_day=position == 'day')
        hidden = fact.get('hidden')
        if (any(fact.get(key) != expected[key] for key in ('stem', 'branch', 'ten_god')) or
                not isinstance(hidden, (list, tuple)) or len(hidden) != len(expected['hidden']) or
                any(not isinstance(row, dict) or any(row.get(key) != value for key, value in native.items())
                    for row, native in zip(hidden, expected['hidden']))):
            raise ValueError('原局干支分解、十神或藏干与引擎不一致，须用同一出生候选：' + position)
    return pillars


def evaluate_periods(core_analysis, temporal_pillars, root=None, *, expected_window=None):
    """Return separate natal and cumulative period panels, without computing time.

    Each row supplies ``layer, pillar, source, window``. Layers are a continuous
    luck/year/month/day prefix; ``pillar=None`` retains an unknown layer. A month
    panel cannot see the day row, while a day panel cannot discard its uppers.
    Explicit aware half-open windows must share time. If expected_window is
    supplied from the current query segment, dated rows must cover that segment.
    Known year/month/day rows need dated windows and must match native calendar
    facts throughout that segment. Known day rows must use the query's civil
    offset. Legacy prose labels remain annotations otherwise.
    Callers must derive and review every modeled boundary window.
    """
    rows = _period_rows(temporal_pillars, expected_window)
    natal = core_analysis.get('qiong_xin_zi_model') if isinstance(core_analysis, dict) else None
    if (not isinstance(natal, dict) or natal.get('rule_version') != VERSION or
            natal.get('profile') != PROFILE or natal.get('temporal_scope') != 'natal' or
            type(natal.get('temporal_uncertainty')) is not bool or 'scenario_id' not in natal):
        raise ValueError('需要当前core的独立模型及明确出生时间场景元数据')
    facts = core_analysis.get('facts')
    missing = core_analysis.get('missing_pillars')
    pillars = _validated_natal_pillars(facts, missing)
    # Cached natal metadata must belong to these facts before it can label a
    # period result as a candidate or as a unique input.
    if natal.get('natal_pillars') != pillars or natal.get('missing_pillars') != missing:
        raise ValueError('原局模型与当前core的四柱事实或缺柱记录冲突，须用同一出生候选')
    sibling = core_analysis.get('primary_spouse')
    scene_fields = ('scenario_id', 'temporal_uncertainty')
    if (isinstance(sibling, dict) and sibling.get('profile') == PRIMARY_SPOUSE_PROFILE and
            all(key in sibling for key in scene_fields) and
            any(sibling[key] != natal[key] for key in scene_fields)):
        raise ValueError('原局模型与当前core的出生时间场景冲突，须用同一出生候选')
    try:
        records, errors = _records(root), []
    except (ValueError, OSError, KeyError, ImportError) as exc:
        records, errors = {}, [str(exc)]
    uncertainty = natal['temporal_uncertainty']
    scenario_id = natal['scenario_id']
    relations, groups = relations_from_facts(facts)
    result = {}
    for count in range(len(rows) + 1):
        context = rows[:count]
        result[context[-1]['layer'] if context else 'natal'] = _evaluate(
            facts, relations, groups, missing, uncertainty, scenario_id, context, records, errors)
    return result


def _read_civil_candidates(candidates, requested_cores):
    if not requested_cores:
        return candidates
    by_id = {row['id']: row['analysis'] for row in candidates}
    selected = set()
    for core in requested_cores:
        model = core.get('qiong_xin_zi_model') if isinstance(core, dict) else None
        identity = model.get('scenario_id') if isinstance(model, dict) else None
        if (not isinstance(identity, str) or identity not in by_id or
                core.get('missing_pillars') != by_id[identity]['missing_pillars'] or
                core.get('facts') != by_id[identity]['facts']):
            raise ValueError('指定本命核心不属于本次原民用生日候选')
        selected.add(identity)
    return [row for row in candidates if row['id'] in selected]


def _require_post_birth_window(snapshot, contexts, window, *, fallback_cores=()):
    """Check post-birth bounds and return status and any verified exact instant."""
    core_bound = True
    birth_instant = None
    if all(context['birth_segments'] for context in contexts):
        birth_segments = [segment for context in contexts for segment in context['birth_segments']]
        first = min(datetime.fromisoformat(row['start_utc']) for row in birth_segments)
        last = max(datetime.fromisoformat(row['end_utc']) for row in birth_segments)
    else:
        from bazi_scenario_reading import recorded_birth_context

        bounds, core_bound = recorded_birth_context(snapshot, verified_natal_cores=fallback_cores)
        if bounds is None:
            return 'birth_time_unverified', None
        first, last = bounds
        if core_bound and first == last:
            birth_instant = first.astimezone(timezone.utc).isoformat()
    start, end = _query_window_bounds(window)
    if end <= first:
        raise ValueError('查询时段早于原出生范围')
    if start < last:
        raise ValueError('查询时段与原出生范围相交，须另核出生后的查询段')
    if not core_bound:
        return 'birth_core_unverified', None
    return None, birth_instant


def _birth_witness_key(witness):
    if (not isinstance(witness, dict) or set(witness) != {'scenario_id', 'witness_utc'} or
            any(not isinstance(value, str) or not value.strip() for value in witness.values())):
        raise ValueError('须同时指定原快照出生见证的 scenario_id 与 witness_utc')
    return witness['scenario_id'], witness['witness_utc']


def evaluate_query_segment(snapshot, request_segment, folded_age_months, *, expected_window=None,
                           expected_layer=None, expected_birth_witness=None,
                           verified_natal_cores=(), root=None):
    """Apply the verified age and report which original birth witnesses were read."""
    from bazi_scenario_reading import UNKNOWN_HOUR, luck_contexts_at_age, verified_date_candidates

    facts = request_segment['facts']
    if not isinstance(facts, (list, tuple)) or not facts:
        raise ValueError('本次查询分段缺少年月日历法事实')
    layer = facts[-1].get('layer') if isinstance(facts[-1], dict) else None
    if expected_layer is not None:
        if expected_layer not in LEVELS[1:]:
            raise ValueError('预期查询层须为 year、month 或 day')
        if layer != expected_layer:
            raise ValueError('历法事实层与本次独立确认的查询层不一致')
    window = f"[{request_segment['start']}, {request_segment['end']})"
    if expected_window is not None:
        actual = _query_window_bounds(window)
        expected = _query_window_bounds(expected_window)
        if actual != expected:
            raise ValueError('历法事实分段与本次独立确认的查询起止不一致')
        if layer == 'day' and actual[0].utcoffset() != expected[0].utcoffset():
            raise ValueError('日层须使用本次查询的固定民用偏移')
        window = expected_window
    if expected_birth_witness is not None:
        _birth_witness_key(expected_birth_witness)
    bound = luck_contexts_at_age(snapshot, folded_age_months)
    contexts = bound['contexts']
    fallback_cores = ()
    natal_candidate_coverage = None
    available_witnesses = [context['witness'] for context in contexts if context['witness'] is not None]
    witness_scope = 'all_available_witnesses' if available_witnesses else 'no_candidate_witnesses'
    if expected_birth_witness is not None:
        if not contexts:
            raise ValueError('原快照没有指定出生见证的可核大运来源：' + bound['coverage'])
        contexts = [context for context in contexts if context['witness'] == expected_birth_witness]
        if len(contexts) != 1:
            raise ValueError('指定出生见证不存在或不唯一，须按同一原快照核对候选及 UTC 瞬间')
        witness_scope = 'selected_birth_witness'
    elif not contexts:
        candidates = bound.get('natal_candidates')
        if snapshot.get('kind') == UNKNOWN_HOUR:
            candidates = verified_date_candidates(snapshot)
        if candidates is not None:
            natal_candidates = _read_civil_candidates(candidates, tuple(verified_natal_cores))
            read_ids = [row['id'] for row in natal_candidates]
            natal_candidate_coverage = dict(read=read_ids, unread=[row['id'] for row in candidates
                                                                  if row['id'] not in read_ids])
        else:
            fallback_cores = tuple(verified_natal_cores)
            natal_inputs = fallback_cores
            if not natal_inputs and 'natal_core' in bound:
                natal_inputs = (bound['natal_core'],)
            natal_candidates = [dict(analysis=natal, birth_segments=[]) for natal in natal_inputs]
        contexts = [
            dict(analysis=row['analysis'], witness=None, birth_segment=None, birth_segments=row['birth_segments'],
                 age_window=None, age_table_range=None, status='birth_luck_unverified',
                 luck=dict(layer='luck', pillar=None, source=bound['coverage'], window=window))
            for row in natal_candidates
        ]
    birth_status, birth_instant = (
        _require_post_birth_window(snapshot, contexts, window, fallback_cores=fallback_cores)
        if contexts else (None, None)
    )
    readings = []
    for context in contexts:
        panels = evaluate_periods(context['analysis'], [context['luck'], *facts], root, expected_window=window)
        readings.append(dict(witness=context['witness'], birth_segment=context['birth_segment'],
                             birth_segments=context['birth_segments'],
                             age_window=context['age_window'], age_table_range=context['age_table_range'],
                             luck_status=context['status'], panels=panels))
    read_witnesses = [row['witness'] for row in readings if row['witness'] is not None]
    witness_coverage = dict(scope=witness_scope, read=read_witnesses,
                            unread=[witness for witness in available_witnesses if witness not in read_witnesses])
    result = dict(window=window, coverage=bound['coverage'], witness_coverage=witness_coverage,
                  folded_age_months=folded_age_months, readings=readings)
    if birth_instant is not None:
        result['birth_instant_utc'] = birth_instant
    if birth_status is not None:
        result['birth_time_status'] = birth_status
    if natal_candidate_coverage is not None:
        result['natal_candidate_coverage'] = natal_candidate_coverage
    return result


def _replay_query_evaluation(snapshot, evaluation, layer, start, end, verified_natal_cores, root):
    coverage = evaluation['witness_coverage']
    witness = None
    if coverage['scope'] == 'selected_birth_witness':
        if len(coverage['read']) != 1:
            raise ValueError('选定出生见证的续算结果须明确记录一条已读见证')
        witness, = coverage['read']
    # The outer audit already checked this calendar prefix against the original plan.
    calendar_rows = evaluation['readings'][0]['panels'][layer]['temporal_facts'][1:]
    segment = dict(start=start.isoformat(), end=end.isoformat(), facts=calendar_rows)
    try:
        # Each archived window may have read a different subset of the
        # independently checked natal candidates. Replay that window's scope.
        if verified_natal_cores and 'natal_candidate_coverage' in evaluation:
            candidate_coverage = evaluation['natal_candidate_coverage']
            read = candidate_coverage.get('read') if isinstance(candidate_coverage, dict) else None
            if not isinstance(read, list) or not read or not all(isinstance(identity, str) for identity in read):
                raise ValueError('已读面板缺少有效的本命候选范围')
            verified_natal_cores = tuple(core for core in verified_natal_cores
                                         if core['qiong_xin_zi_model']['scenario_id'] in read)
            if {core['qiong_xin_zi_model']['scenario_id'] for core in verified_natal_cores} != set(read):
                raise ValueError('已读面板含本次未独立核对的本命候选')
        current = evaluate_query_segment(
            snapshot, segment, evaluation['folded_age_months'], expected_window=evaluation['window'],
            expected_layer=layer, expected_birth_witness=witness,
            verified_natal_cores=verified_natal_cores, root=root)
    except ValueError as error:
        raise ValueError('已读面板无法按本次原出生快照复核。' + str(error)) from error
    if 'birth_instant_utc' in evaluation:
        if evaluation['birth_instant_utc'] != current.get('birth_instant_utc'):
            raise ValueError('已读面板与本次原出生快照的精确出生时刻不一致，须按本次出生输入续算')
    elif 'birth_instant_utc' in current:
        # Old panels cannot establish which exact minute was used to choose a luck window.
        if current['coverage'] == 'single_birth_input' and evaluation['folded_age_months'] is not None:
            raise ValueError('旧面板缺少精确出生时刻，须按本次出生输入及独立核实的折月年龄续算')
        current.pop('birth_instant_utc')
    if current != evaluation:
        raise ValueError('已读面板与本次原出生快照或该见证的大运事实不一致')


def _audited_birth_keys(snapshot, verified_natal_cores):
    from bazi_scenario_reading import UNKNOWN_HOUR, birth_luck_tables, verified_date_candidates

    if snapshot.get('kind') == UNKNOWN_HOUR:
        candidates = verified_date_candidates(snapshot)
    else:
        result = birth_luck_tables(snapshot)
        if 'natal_candidates' not in result:
            witnesses = (row['witness'] for row in result['tables'])
            return [(row['scenario_id'], row['witness_utc']) for row in witnesses if row is not None]
        candidates = result['natal_candidates']
    _read_civil_candidates(candidates, verified_natal_cores)
    return [(row['id'], None) for row in candidates]


def _unread_windows(planned, covered):
    unread = []
    for (start, end), subwindows in zip(planned, covered):
        cursor = start
        for left, right in sorted(subwindows):
            if left > cursor:
                unread.append(f"[{cursor.isoformat()}, {left.astimezone(start.tzinfo).isoformat()})")
            cursor = max(cursor, right).astimezone(start.tzinfo)
        if cursor < end:
            unread.append(f"[{cursor.isoformat()}, {end.isoformat()})")
    return unread


def _boundaries_of_kind(plan, kind):
    boundaries = plan.get('boundaries')
    if not isinstance(boundaries, (list, tuple)):
        return []
    return [row for row in boundaries if isinstance(row, Mapping) and
            isinstance(row.get('reasons'), (list, tuple)) and any(
                isinstance(reason, Mapping) and reason.get('kind') == kind for reason in row['reasons'])]


def _verified_saved_query_zone(plan):
    zone = plan.get('timezone')
    if (zone is not None and (not isinstance(zone, str) or not zone.strip())) or (
            zone is None and 'civil_dates' in plan):
        raise ValueError('原查询计划的民用时区无法复核')
    if 'timezone_source' in plan:
        check_timezone_source(plan['timezone_source'], zone)
    return zone


def _retained_boundaries_match(plan, native):
    boundaries = plan.get('boundaries', ())
    return isinstance(boundaries, (list, tuple)) and all(row in native['boundaries'] for row in boundaries)


def _retained_segments_match(plan, native):
    bounds = {(row['start'], row['end']) for row in native['segments']}
    saved_segments = plan.get('segments', ())
    return isinstance(saved_segments, (list, tuple)) and all(
        isinstance(row, Mapping) and all(isinstance(row.get(key), str) for key in ('start', 'end')) and
        (row['start'], row['end']) in bounds for row in saved_segments)


def _restored_date_segments(plan, native, *, require_recorded_gaps=False):
    _verified_saved_query_zone(plan)
    gap_kind = 'civil_date_membership_gap'
    if ('civil_dates' not in native or any(plan.get(key) != native[key] for key in ('start', 'end')) or
            ('civil_dates' in plan and plan['civil_dates'] != native['civil_dates']) or
            not _retained_boundaries_match(plan, native) or (require_recorded_gaps and
                _boundaries_of_kind(plan, gap_kind) != _boundaries_of_kind(native, gap_kind))):
        raise ValueError('存档日期起止或日期成员间隙与原查询重算不一致，须按原日期请求重建')
    if not _retained_segments_match(plan, native):
        raise ValueError('存档分段与重算的日期成员范围不一致')
    return native['segments']


def _iana_clock_segments(plan, native, *, scope_verified=False):
    from bazi_period_facts import regional_date_facts

    _verified_saved_query_zone(plan)
    start, end = (parse_query_point(native[key]).date() for key in ('start', 'end'))
    if start >= end:
        return native['segments']
    # The same physical endpoints can cover two different sets of civil dates after a rollback.
    shifts = _boundaries_of_kind(native, 'iana_utc_offset_change')
    if not any(parse_query_point(reason['previous_clock']).date() > parse_query_point(row['at']).date()
               for row in shifts for reason in row['reasons'] if reason['kind'] == 'iana_utc_offset_change'):
        return native['segments']
    try:
        date_plan = regional_date_facts(start, end, native['layer'], native['timezone'])
    except (ValueError, OverflowError):
        return native['segments']
    if (any(native[key] != date_plan[key] for key in ('start', 'end')) or
            not _boundaries_of_kind(date_plan, 'civil_date_membership_gap')):
        return native['segments']
    if not (_retained_boundaries_match(plan, native) and _retained_segments_match(plan, native)):
        raise ValueError('存档分段或边界与连续钟面范围不一致，须按原请求重建')
    if not scope_verified and _retained_boundaries_match(plan, date_plan) and _retained_segments_match(plan, date_plan):
        raise ValueError('原查询无法区分日期成员范围与连续钟面范围，须独立核实原请求')
    return native['segments']


def _query_plan_segments(plan, expected_request):
    from bazi_period_facts import period_facts, query_period_facts, regional_date_facts, regional_period_facts
    basis = plan.get('time_basis')
    if 'time_basis' not in plan and any(key in plan for key in ('start', 'end', 'timezone', 'civil_dates',
                                                               'timezone_source')):
        if not all(isinstance(plan.get(key), str) for key in ('start', 'end')):
            raise ValueError('原查询计划缺少可复核的起止，须按原请求重建')
        zone = _verified_saved_query_zone(plan)
        basis = 'civil_fixed_offset' if zone is None else 'civil_iana'
    if 'civil_dates' in plan and basis != 'civil_iana':
        raise ValueError('存档民用日期范围须使用原 IANA 时区口径')
    saved_gaps = (_boundaries_of_kind(plan, 'civil_date_membership_gap')
                  if basis == 'civil_iana' and 'civil_dates' not in plan else [])
    expected = None
    if expected_request is not None:
        if not isinstance(expected_request, Mapping):
            raise ValueError('须独立提供原查询请求的起止、时间层及时区')
        try:
            expected = query_period_facts(expected_request.get('start'), expected_request.get('end'),
                                          expected_request.get('layer'), expected_request.get('timezone'),
                                          start_fold=expected_request.get('start_fold'),
                                          end_fold=expected_request.get('end_fold'))
        except (ValueError, OverflowError) as exc:
            raise ValueError('无法按原查询请求重建八字计划。' + str(exc)) from exc
        recover_dates = 'civil_dates' not in plan and 'civil_dates' in expected
        request_fields = ('start', 'end', 'layer', 'timezone')
        if not (saved_gaps or recover_dates):
            request_fields += ('civil_dates',)
        if basis != expected['time_basis'] or any(plan.get(key) != expected.get(key) for key in request_fields):
            raise ValueError('保存的八字计划与独立确认的原查询请求不一致')
    if basis == 'civil_fixed_offset':
        if _verified_saved_query_zone(plan) is not None:
            raise ValueError('固定偏移查询计划与保存的 IANA 时区不一致')
        if expected is not None:
            return expected['segments']
        start, end = (parse_query_point(plan[key]) for key in ('start', 'end'))
        return period_facts(start, end, plan['layer'])['segments']
    if expected is not None:
        if saved_gaps or 'civil_dates' in expected:
            return _restored_date_segments(plan, expected)
        return _iana_clock_segments(plan, expected, scope_verified=True)
    if basis is None and 'time_basis' not in plan:
        return plan['segments']
    layer = plan['layer']
    if 'civil_dates' in plan:
        dates = plan['civil_dates']
        if not isinstance(dates, Mapping):
            raise ValueError('存档民用日期范围无法复核，须按原日期请求重建')
        native = query_period_facts(dates.get('start_inclusive'), dates.get('end_exclusive'), layer,
                                   plan.get('timezone'))
        return _restored_date_segments(plan, native)
    start, end = (parse_query_point(plan[key]) for key in ('start', 'end'))
    if basis == 'civil_iana':
        if saved_gaps:
            native = regional_date_facts(start.date(), end.date(), layer, plan['timezone'])
            return _restored_date_segments(plan, native, require_recorded_gaps=True)
        return _iana_clock_segments(plan, regional_period_facts(start, end, layer, plan['timezone']))
    raise ValueError('原查询计划的民用时间口径无法复核')


def _verified_folded_age_windows(ages):
    if not isinstance(ages, Mapping):
        raise ValueError('本次独立核对的折月年龄须按实际时窗和出生见证提供')
    normalized = {}
    for key, age in ages.items():
        if (not isinstance(key, tuple) or len(key) != 4 or
                any(not isinstance(point, datetime) or point.utcoffset() is None for point in key[:2])):
            raise ValueError('本次独立核对的折月年龄须提供带偏移的实际起止及出生见证')
        if age is not None and (type(age) is not int or age < 0):
            raise ValueError('折月年龄须为非负整数，未核时用 None')
        start, end = (point.astimezone(timezone.utc) for point in key[:2])
        actual = (start, end, *key[2:])
        if start >= end:
            raise ValueError('本次折月年龄的窗口起点须早于终点')
        if actual in normalized and normalized[actual] != age:
            raise ValueError('同一实际窗口和出生见证有冲突的独立折月年龄')
        normalized[actual] = age
    _check_folded_age_sequence(normalized.items(), '独立折月年龄')
    by_witness = {}
    for (start, end, scenario_id, witness), age in sorted(normalized.items(), key=lambda item: item[0][:2]):
        windows = by_witness.setdefault((scenario_id, witness), [])
        if windows and windows[-1][2] == age and start <= windows[-1][1]:
            left, right, _ = windows[-1]
            windows[-1] = left, max(end, right), age
        else:
            windows.append((start, end, age))
    return by_witness


def _check_folded_age_sequence(entries, age_label):
    by_witness = {}
    for (start, end, scenario_id, witness_utc), age in entries:
        by_witness.setdefault((scenario_id, witness_utc), []).append((start, end, age))
    for windows in by_witness.values():
        latest_end, previous_age = None, None
        latest_known_end, latest_known_age, preceding_age_end = None, None, None
        for start, end, age in sorted(windows, key=lambda window: window[:2]):
            if latest_end is not None and start < latest_end:
                if age != previous_age:
                    raise ValueError('同一出生见证的重叠实际窗口有冲突的' + age_label)
                latest_end = max(latest_end, end)
            else:
                latest_end, previous_age = end, age
            if age is None:
                continue
            if age == latest_known_age:
                latest_known_end = max(latest_known_end, end)
                continue
            if latest_known_age is not None:
                if age < latest_known_age:
                    raise ValueError('同一出生见证的' + age_label + '随实际时间倒退')
                # Two single-month increases can be split over several nearby panels.
                earlier_end = latest_known_end if age > latest_known_age + 1 else preceding_age_end
                if earlier_end is not None:
                    gap = start - earlier_end
                    if gap < timedelta(days=1):
                        boundary = '相邻实际窗口之间，' if not gap else '实际窗口相隔不足一天，'
                        raise ValueError('同一出生见证的' + boundary + age_label + '一次跳过超过一个月')
            preceding_age_end = latest_known_end
            latest_known_age, latest_known_end = age, end


def _check_folded_ages(evaluation, readings, start, end, verified_folded_ages, *, query_timezone):
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    for reading in readings:
        witness = reading['witness'] or {}
        key = (reading['panels']['natal']['scenario_id'], witness.get('witness_utc'))
        windows = verified_folded_ages.get(key, ())
        for left, right, age in windows:
            if left <= start and end <= right:
                break
        else:
            cuts = [right.astimezone(query_timezone).isoformat()
                    for (_, right, earlier_age), (left, _, later_age) in zip(windows, windows[1:])
                    if start < right == left < end and earlier_age is not None
                    and later_age is not None and earlier_age != later_age]
            detail = '，已跨折月年龄切点，须分段重读：' + '、'.join(cuts) if cuts else ''
            raise ValueError('已读窗口及出生见证缺少本次独立核对的折月年龄' + detail)
        cached_age = evaluation['folded_age_months']
        if type(age) is not type(cached_age) or age != cached_age:
            raise ValueError('已读窗口的折月年龄与本次独立核对的年龄不一致')


def audit_query_range(calendar_plan, segment_evaluations, *, snapshot=None, expected_request=None,
                      expected_birth_witness=None, verified_natal_cores=(),
                      verified_folded_ages=None, root=None):
    """Compare inspected windows against the independently generated calendar plan.

    Pass the current original snapshot to replay each counted result and list
    missing windows for each available birth candidate. Coverage records reading
    of the supplied evidence, not completeness of a numerical birth sample or
    adjudication of any model direction. Native plans are replayed from their
    request bounds before counting any covered windows. An independent
    expected_request can bind the stored plan to the user's current request.
    With an independently selected expected_birth_witness, only its readings
    and ages count towards coverage, including when reusing a wider result.
    Replayed readings must agree on overlapping ages for each birth witness.
    Cached exact readings with an age used for luck selection must carry the
    original exact birth instant. Regenerate legacy panels without it.
    Supply independently checked ages keyed by (aware start, aware end,
    scenario ID, witness UTC). The evidence must cover the entire read window
    with one age for that witness. The returned check flag describes the
    evidence used for windows that were read, including explicit unknown ages.
    """
    if verified_folded_ages is not None:
        if snapshot is None:
            raise ValueError('核对本次折月年龄时须提供原出生快照')
        verified_folded_ages = _verified_folded_age_windows(verified_folded_ages)
    layer = calendar_plan['layer']
    if layer not in LEVELS[1:]:
        raise ValueError('原查询计划须为 year、month 或 day')
    segments = _query_plan_segments(calendar_plan, expected_request)
    planned = [_query_window_bounds(f"[{row['start']}, {row['end']})") for row in segments]
    if not planned:
        raise ValueError('原查询计划没有可读的历法分段')
    starts = [start for start, _ in planned]
    covered = [[] for _ in planned]
    verified_natal_cores = tuple(verified_natal_cores)
    birth_keys = _audited_birth_keys(snapshot, verified_natal_cores) if snapshot is not None else []
    if expected_birth_witness is not None:
        if snapshot is None:
            raise ValueError('指定本次出生见证时须提供原出生快照')
        selected_key = _birth_witness_key(expected_birth_witness)
        if selected_key not in birth_keys:
            raise ValueError('指定出生见证不存在，须按同一原快照核对候选及 UTC 瞬间')
        birth_keys = [selected_key]
    covered_by_birth = {key: [[] for _ in planned] for key in birth_keys}
    replayed_ages = [] if snapshot is not None and verified_folded_ages is None else None
    required_panels = {'natal', *LEVELS[:LEVELS.index(layer) + 1]}
    for evaluation in segment_evaluations:
        all_readings = evaluation['readings']
        readings = all_readings
        if expected_birth_witness is not None:
            readings = [row for row in all_readings if row['witness'] == expected_birth_witness]
            if not readings:
                continue
        start, end = _query_window_bounds(evaluation['window'])
        index = bisect_right(starts, start) - 1
        if index < 0 or end > planned[index][1]:
            raise ValueError('已读窗口不属于原查询的单个历法分段')
        if layer == 'day' and start.utcoffset() != starts[index].utcoffset():
            raise ValueError('已读日层窗口未使用原查询的固定民用偏移')
        planned_facts = segments[index]['facts']
        expected_pillars = [(row['layer'], row['pillar']) for row in planned_facts]
        for reading in all_readings:
            panels = reading['panels']
            if set(panels) != required_panels:
                raise ValueError('已读窗口的模型层与原查询层不一致')
            calendar_rows = panels[layer]['temporal_facts'][1:]
            if [(row['layer'], row['pillar']) for row in calendar_rows] != expected_pillars:
                raise ValueError('已读面板的年月日干支与原查询分段不一致')
            for row in calendar_rows:
                bounds = _window_bounds(row['window'])
                if (bounds is None or bounds[0] > start or bounds[1] < end or
                        (row['layer'] == 'day' and any(point.utcoffset() != start.utcoffset() for point in bounds))):
                    raise ValueError('已读面板的历法事实窗口不覆盖本次读取范围')
        if readings:
            if snapshot is not None:
                _replay_query_evaluation(snapshot, evaluation, layer, start, end, verified_natal_cores, root)
            if evaluation.get('birth_time_status') is not None:
                continue
            if verified_folded_ages is not None:
                _check_folded_ages(evaluation, readings, start, end, verified_folded_ages,
                                   query_timezone=starts[index].tzinfo)
            covered[index].append((start, end))
            if replayed_ages is not None:
                physical_window = (start.astimezone(timezone.utc), end.astimezone(timezone.utc))
            for reading in readings:
                witness = reading['witness'] or {}
                key = (reading['panels']['natal']['scenario_id'], witness.get('witness_utc'))
                if key in covered_by_birth:
                    covered_by_birth[key][index].append((start, end))
                if replayed_ages is not None:
                    replayed_ages.append(((*physical_window, *key), evaluation['folded_age_months']))

    if replayed_ages is not None:
        _check_folded_age_sequence(replayed_ages, '已读面板折月年龄')
    result = dict(layer=layer, planned_segments=len(planned), unread_windows=_unread_windows(planned, covered),
                  folded_age_evidence_checked=verified_folded_ages is not None and any(covered))
    if covered_by_birth:
        result['unread_by_birth'] = [
            dict(scenario_id=identity, witness_utc=witness, unread_windows=_unread_windows(planned, windows))
            for (identity, witness), windows in covered_by_birth.items()
        ]
    return result


def render(panel, *, nested=False):
    if panel['status'] == 'outside_scope':
        return []
    title = '十一月辛完整条件模型'
    lines = ['', '**' + title + '**' if nested else '### ' + title, '']
    if panel['source_errors']:
        return lines + ['来源检查失败，新增模型不作判断：' + '；'.join(panel['source_errors'])]
    if panel['status'] == 'withheld':
        lines.append('完整模型结果暂缓。')
        lines.extend(reason + '。' for reason in panel.get('incomplete_reasons', []))
        if panel['specific_gui_countercondition']['status'] == 'present':
            lines.append('当前所核事实中，丙透有结构根且癸透，已观察到 QX03 反条的事实条件。')
    elif panel['matched_branch'] == 'B_selected_graded_positive':
        lines.append('所选 B 的普通正支已匹配，传统模型内发展配置相对有利，评价低于 A。')
        lines.append(panel['alternative_conservative_reading']['reason'] + '。')
    else:
        lines.append(panel.get('source_direction', '普通正支未完整匹配；不能据此自动判差。'))
    lines += ['以上为机械条件匹配，仍须先核适用性、有据的必要用途否定和竞争反证，才能形成交付结论。',
              '同五行藏干根为项目结构口径；通根事实不证明作用有效。一般交互未决不等于零影响。',
              '有据阻断须撤评，现实不符不能倒推隐藏根失效免责。']
    lines.extend('依据：' + c['citation']['record_id'] + '，' + c['citation']['locator'] for c in panel['cards'])
    return lines
