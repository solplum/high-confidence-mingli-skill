"""Compare reachable BaZi structures when the civil birth time is incomplete."""
import argparse
from datetime import date, datetime, time, timedelta
import json

import bazi_core_reading as core
import bazi_primary_spouse
import bazi_qiong_xin_zi
import pai_pan_bazi as engine
from bazi_period_facts import period_facts
from time_scenarios import (
    MAX_YEAR, MIN_YEAR, TICK, UTC, UnsupportedUtcInterval, check_recorded_scenario_bounds, check_timezone_source,
    civil_clock_band_shichen_spans, civil_date_spans, civil_shichen_spans, dayun_age_segments,
    enumerate_scenarios, fixed_utc_offset, iana_zone, parse_birth_date, parse_civil_clock_band, parse_query_point,
    recorded_scenario_bounds, resolve_civil, scenario_clock_at, scenario_witnesses,
    snapshot_apparent_correction, snapshot_dut1_seconds, solar_clock, timezone_provenance,
)

VERSION = 'bazi-scenario-comparison-v1'
UNKNOWN_HOUR = 'birth_date_unknown_hour'
KNOWN_SHICHEN = 'birth_date_known_shichen'
KNOWN_CLOCK_BAND = 'birth_date_known_clock_band'
LABELS = {'day_master': '日主参照', 'season': '月令与季节', 'roots': '同五行根气',
          'relations': '冲合刑害配对', 'month_exposure': '月支藏干透出',
          'support': '生扶线索', 'opposing': '克泄耗线索'}


def canonical_pillars(fields, keys=core.KEYS):
    """The enumerator retains only stems/branches; derive annotations by engine."""
    day = fields['bazi.day'][0]
    return {key: (fields['bazi.' + key][0], fields['bazi.' + key][1],
                  '—' if key == 'day' else engine.shishen_of(
                      engine.GAN.index(day), engine.GAN.index(fields['bazi.' + key][0])),
                  engine.format_canggan(fields['bazi.' + key][1])) for key in keys}


def analyze_birth_date(day, sex, *, utc_offset=None, zone=None, shichen=None, clock_band=None):
    """Analyze a civil date, optionally narrowed to a branch or a clock band."""
    if clock_band is not None:
        if shichen is not None:
            raise ValueError('请选择民用时辰或出生钟面区间')
        if (zone is None) == (utc_offset is None):
            raise ValueError('出生钟面区间须明确提供出生时区或固定 UTC 偏移')
        if sex not in ('男', '女'):
            raise ValueError('出生钟面区间的大运核查需要确认性别为男或女')
        if (not isinstance(clock_band, (list, tuple)) or len(clock_band) != 2 or
                not all(isinstance(bound, str) for bound in clock_band)):
            raise ValueError('出生钟面区间须提供原民用钟面的起止')
        start_text, end_text = clock_band
        start_minutes, end_minutes = parse_civil_clock_band(start_text, end_text)
        civil_spans = civil_clock_band_shichen_spans(day, start_minutes, end_minutes,
                                                     utc_offset=utc_offset, zone=zone)
        spans = ((start, end, engine.ZHI_LIST[index]) for start, end, index in civil_spans)
        prefix = 'birth-band'
    else:
        if utc_offset is None and zone is None:
            utc_offset = 8
        civil_spans = (civil_date_spans(day, utc_offset, zone) if shichen is None else
                       civil_shichen_spans(day, shichen, utc_offset, zone))
        spans = ((start, end, shichen) for start, end in civil_spans)
        prefix = 'birth-day' if shichen is None else 'birth-shichen'

    has_hour = shichen is not None or clock_band is not None
    keys = core.KEYS if has_hour else core.KEYS[:3]
    candidates = {}
    windows = []
    age_segments = []
    for start, end, branch in spans:
        if has_hour and (start.astimezone(UTC).year < MIN_YEAR or
                         (end.astimezone(UTC) - TICK).year > MAX_YEAR):
            raise UnsupportedUtcInterval('时辰候选仅支持可达 UTC 区间落在 1901–2099 年内')
        for segment in period_facts(start, end, 'day')['segments']:
            if has_hour:
                day_fact = segment['facts'][-1]
                hour_pillar = engine.resolve_hour_pillar(engine.GAN.index(day_fact['pillar'][0]), branch)
                segment['facts'].append(dict(layer='hour', pillar=''.join(hour_pillar),
                                             source='scripts/pai_pan_bazi.py:resolve_hour_pillar',
                                             window=day_fact['window']))
            identity = tuple(fact['pillar'] for fact in segment['facts'])
            if identity not in candidates:
                candidate_id = f'{prefix}-candidate-{len(candidates) + 1}'
                fields = {'bazi.' + key: value for key, value in zip(keys, identity)}
                pillars = canonical_pillars(fields, keys)
                if not has_hour:
                    pillars['hour'] = ('未知',) * 4
                analysis = core.analyze(dict(pillars=pillars, sex=sex, scenario_id=candidate_id),
                                        candidate_temporal_uncertainty=True)
                candidates[identity] = dict(id=candidate_id, pillars=dict(zip(keys, identity)),
                                            analysis=analysis)
            candidate_id = candidates[identity]['id']
            windows.append(dict(segment, candidate_id=candidate_id))
            if has_hour:
                left = datetime.fromisoformat(segment['start']).astimezone(UTC)
                right = datetime.fromisoformat(segment['end']).astimezone(UTC)
                # period_facts already split this reachable span at every jie
                # and 23:00. Any age cuts inside it share this four-pillar ID.
                for _, _, record, _ in dayun_age_segments(left, right, (), sex, end_inclusive=False):
                    age_segments.append(dict(record, birth_witnesses=[
                        dict(scenario_id=candidate_id, witness_utc=record['start_utc'])]))
    rows = list(candidates.values())
    stable = {key: rows[0]['pillars'][key] for key in keys
              if all(row['pillars'][key] == rows[0]['pillars'][key] for row in rows)}
    result = dict(kind=UNKNOWN_HOUR, solar_date=day.isoformat(), sex=sex,
                  time_basis='civil', timezone=zone, utc_offset=utc_offset,
                  timezone_source=timezone_provenance(zone),
                  coverage='complete_for_reachable_civil_date_and_modeled_three_pillars',
                  interval_semantics='start_inclusive_end_exclusive',
                  windows=windows, candidates=rows, stable_pillars=stable,
                  excluded=['hour_pillar', 'qiyun', 'dayun_ages', 'ziwei', 'qizheng', 'ephemeris_error'])
    if has_hour:
        if clock_band is None:
            result.update(kind=KNOWN_SHICHEN, shichen=shichen,
                          coverage='complete_for_reachable_civil_shichen_and_modeled_four_pillars')
        else:
            result.update(kind=KNOWN_CLOCK_BAND,
                          clock_band=dict(start_inclusive=start_text, end_exclusive=end_text),
                          coverage='complete_for_reachable_civil_clock_band_and_modeled_four_pillars')
        result['excluded'] = ['ziwei', 'qizheng', 'ephemeris_error']
        result['dayun_age_comparison'] = dict(
            scope='rounded_bazi_dayun_ages_at_physical_birth_instants',
            coverage='complete_for_rounded_model_not_ephemeris_error',
            natal_candidate_coverage=result['coverage'], segments=age_segments)
    return result


def _civil_candidates_with_segments(replayed):
    candidates = replayed['candidates']
    segments = {row['id']: [] for row in candidates}
    for window in replayed['windows']:
        start, end = (datetime.fromisoformat(window[key]).astimezone(UTC) for key in ('start', 'end'))
        segments[window['candidate_id']].append(dict(
            start_utc=start.isoformat(), end_utc=end.isoformat(), end_inclusive=False))
    return [dict(row, birth_segments=segments[row['id']]) for row in candidates]


def verified_date_candidates(snapshot):
    """Replay a date-only civil snapshot and return its canonical natal candidates."""
    if snapshot.get('kind') != UNKNOWN_HOUR or snapshot.get('time_basis') != 'civil':
        raise ValueError('六字候选复核需要原民用生日快照')
    sex, zone, offset = (snapshot.get(key) for key in ('sex', 'timezone', 'utc_offset'))
    if sex not in ('男', '女') or (zone is None) == (offset is None):
        raise ValueError('六字候选复核需要原性别及民用时区或固定偏移')
    if 'timezone_source' in snapshot:
        check_timezone_source(snapshot['timezone_source'], zone)
    expected = analyze_birth_date(parse_birth_date(snapshot['solar_date']), sex,
                                  utc_offset=offset, zone=zone)
    keys = ('coverage', 'interval_semantics', 'windows', 'stable_pillars')
    saved = [(row['id'], row['pillars']) for row in snapshot['candidates']]
    actual = [(row['id'], row['pillars']) for row in expected['candidates']]
    if any(snapshot.get(key) != expected[key] for key in keys) or saved != actual:
        raise ValueError('六字候选或实际区间与原民用生日重算不一致')

    return _civil_candidates_with_segments(expected)


def _verify_native_luck(analysis, windows, point, sex, source):
    spouse_sex = (analysis.get('primary_spouse') or {}).get('sex')
    if sex not in ('男', '女') or spouse_sex not in (None, sex):
        raise ValueError('八字出生性别无效或与已存核心不一致：' + source)
    instant = point.astimezone(UTC)
    _, _, native, _ = dayun_age_segments(instant, instant, (), sex)[0]
    if windows != native['age_windows'] or any(
            analysis['facts'][layer]['pillar'] != native[layer + '_pillar']
            for layer in ('year', 'month')):
        raise ValueError('大运表与出生见证的原生折月不一致：' + source)
    return native


def _verify_birth_clock(analysis, clock, source):
    day_stem, day_branch, *_ = engine.resolve_day_pillar(clock.date(), clock.hour, clock.minute)
    shichen = engine.hour_to_shichen(clock.hour, clock.minute)
    hour = engine.resolve_hour_pillar(engine.GAN.index(day_stem), shichen)
    if (analysis['facts']['day']['pillar'] != day_stem + day_branch or
            analysis['facts']['hour']['pillar'] != ''.join(hour)):
        raise ValueError('出生候选的日柱或时柱与见证钟面不一致，须按原参数重建快照：' + source)
    return shichen


def _verify_model_birth_scope(analysis, scenario_id, source, *, uncertain=None):
    if uncertain is None:
        uncertain = scenario_id is not None
    for name in ('qiong_xin_zi_model', 'primary_spouse'):
        if name not in analysis and (not uncertain or name == 'primary_spouse'):
            continue
        panel = analysis.get(name)
        if (not isinstance(panel, dict) or 'scenario_id' not in panel or
                panel['scenario_id'] != scenario_id or panel.get('temporal_uncertainty') is not uncertain):
            raise ValueError('八字模型的出生时间场景与原出生范围不一致，须重建快照：' + source)


def _verified_civil_point(snapshot):
    """Resolve the original wall time and check the saved physical instant."""
    inputs = snapshot['input']
    saved = snapshot.get('time', {})
    if not isinstance(saved, dict):
        raise ValueError('保存的民用出生时间记录须为对象')
    if not all(isinstance(inputs.get(key), str) for key in ('solar', 'hour')):
        raise ValueError('大运核对需要原民用出生日期与时分')
    hour, minute = (int(part) for part in inputs['hour'].split(':'))
    local = datetime.combine(parse_birth_date(inputs['solar']), time(hour, minute))
    zone, offset = inputs.get('timezone'), inputs.get('utc_offset')
    if zone is None and offset is None:
        raise ValueError('大运核对需要原固定UTC偏移或IANA时区')
    provenance = snapshot.get('provenance')
    if isinstance(provenance, dict) and 'timezone' in inputs and 'timezone_source' in provenance:
        check_timezone_source(provenance['timezone_source'], zone)
    civil = resolve_civil(local, offset, zone, inputs.get('fold'))
    if 'civil' in saved and civil.isoformat() != datetime.fromisoformat(saved['civil']).isoformat():
        raise ValueError('保存的民用出生钟面或UTC偏移与原出生输入不一致')
    if ('iana_zone' in saved and saved['iana_zone'] != zone) or ('fold' in saved and saved['fold'] != civil.fold):
        raise ValueError('保存的时区或fold与原出生输入不一致')
    if 'instant_bj' in saved and datetime.fromisoformat(saved['instant_bj']) != civil.astimezone(UTC):
        raise ValueError('保存的北京时间与原民用出生瞬间不一致')
    native = snapshot.get('bazi')
    if isinstance(native, dict) and 'birth_dt' in native:
        table = native.get('dayun_age_windows')
        reference = native.get('hour_unknown')
        if isinstance(table, dict):
            reference = table.get('birth_time_is_reference', reference)
        instant = native['birth_dt']
        if reference is not True and (
                not isinstance(instant, str) or datetime.fromisoformat(instant) != civil.astimezone(UTC)):
            raise ValueError('保存的八字出生瞬间与原民用出生输入不一致')
    return civil


def _original_chart_clock(snapshot, point, *, allow_missing_record=False):
    inputs = snapshot['input']
    basis = inputs.get('time_basis')
    if basis == 'civil':
        expected = point.replace(tzinfo=None)
    elif basis in ('mean-solar', 'apparent-solar'):
        if allow_missing_record and inputs.get('lon') is None:
            return None
        eot = snapshot_apparent_correction(point, inputs, snapshot.get('qizheng')) if basis == 'apparent-solar' else 0
        if eot is None:
            return None
        expected = solar_clock(point, inputs['lon'], eot)
    elif allow_missing_record and basis is None:
        return None
    else:
        raise ValueError('大运核对需要明确的出生钟面口径')
    saved = snapshot.get('time', {})
    fields = ['chart_clock'] if not allow_missing_record or 'chart_clock' in saved else []
    if basis in ('mean-solar', 'apparent-solar'):
        selected = basis.replace('-', '_')
        if saved.get(selected) is not None:
            fields.append(selected)
    for field in fields:
        try:
            clock = datetime.fromisoformat(saved[field])
        except (TypeError, ValueError) as exc:
            raise ValueError('保存的出生钟面格式无效：time.' + field) from exc
        if clock.replace(second=0, microsecond=0) != expected.replace(second=0, microsecond=0):
            raise ValueError('所选口径的出生钟面与原出生瞬间不一致：time.' + field)
    return expected


def _birth_pillars(snapshot, point):
    clock = _original_chart_clock(snapshot, point, allow_missing_record=True)
    physical = point.astimezone(engine.BJ)
    _, yg, yz, _ = engine.resolve_year_pillar(physical)
    month = engine.resolve_month_pillar(physical, engine.GAN.index(yg))[:2]
    expected = dict(year=yg + yz, month=''.join(month))
    if clock is not None:
        day = engine.resolve_day_pillar(clock.date(), clock.hour, clock.minute)[:2]
        hour = engine.resolve_hour_pillar(engine.GAN.index(day[0]), engine.hour_to_shichen(clock.hour, clock.minute))
        expected.update(day=''.join(day), hour=''.join(hour))
    return expected


def _verify_fallback_cores(inputs, expected, cores, uncertain):
    """Check known natal pillars without claiming an unavailable luck table."""
    bound = 'hour' in expected
    for analysis in cores:
        model = analysis.get('qiong_xin_zi_model') or {}
        candidate = model.get('scenario_id') if uncertain else None
        source = '独立核对的本命核心'
        _verify_model_birth_scope(analysis, candidate, source, uncertain=uncertain)
        sex = inputs.get('sex')
        if sex is not None and (analysis.get('primary_spouse') or {}).get('sex') not in (None, sex):
            raise ValueError('八字出生性别与已存核心不一致：' + source)
        if candidate is not None:
            if not isinstance(candidate, str) or not candidate.strip():
                raise ValueError('独立核对的本命核心须使用有效的出生候选ID')
            # The supplied core has no UTC witness to tie it to the original range.
            bound = False
        elif any(row['pillar'] != expected[key] for key, row in analysis['facts'].items() if key in expected):
            raise ValueError('本命核心的已知四柱与原出生输入重排不一致')
    return bound


def _check_saved_scenario_bounds(snapshot, point, delta):
    inputs = snapshot['input']
    scenarios = snapshot.get('scenarios')
    comparison = snapshot.get('bazi_scenario_comparison')
    # A complete comparison also declares an enumeration in older snapshots
    # that did not retain the separate command-line flag.
    if not delta and (isinstance(comparison, dict) or 'enumerate_scenarios' not in inputs
                      or 'uncertainty_minutes' not in inputs):
        ranges = [scenarios]
        if isinstance(comparison, dict):
            ranges.append(comparison.get('context'))
        if isinstance(scenarios, dict) and isinstance(scenarios.get('dayun_age_comparison'), dict):
            segments = scenarios['dayun_age_comparison'].get('segments')
            if isinstance(segments, list):
                ranges.extend(segments)
        for row in ranges:
            if not isinstance(row, dict):
                continue
            try:
                start, end = (parse_query_point(row[key]) for key in ('start_utc', 'end_utc'))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if start.utcoffset() is None or end.utcoffset() is None or start >= end:
                continue
            if 'uncertainty_minutes' not in inputs:
                raise ValueError('原出生误差分钟缺失，存档仍有非零枚举范围，请核对原出生误差')
            raise ValueError('出生误差枚举范围与原输入的误差分钟不一致')
    check_recorded_scenario_bounds(inputs, recorded_scenario_bounds(inputs, scenarios), point, delta)


def _original_birth_range(snapshot):
    inputs = snapshot.get('input')
    if (not isinstance(inputs, dict) or not all(isinstance(inputs.get(key), str) for key in ('solar', 'hour')) or
            (inputs.get('timezone') is None and inputs.get('utc_offset') is None)):
        return None, False
    minutes = inputs.get('uncertainty_minutes', 0)
    if type(minutes) not in (int, float) or not 0 <= minutes < float('inf'):
        raise ValueError('原出生误差须为有限非负分钟数')
    point = _verified_civil_point(snapshot)
    center = point.astimezone(UTC)
    try:
        delta = timedelta(minutes=minutes)
        _check_saved_scenario_bounds(snapshot, center, delta)
        bounds = (center - delta, center + delta)
    except OverflowError as exc:
        raise ValueError('原出生误差范围超出可表示日期') from exc
    return point, bounds


def recorded_birth_context(snapshot, *, verified_natal_cores=()):
    """Return the physical birth range and whether fallback cores are bound to it."""
    point, bounds = _original_birth_range(snapshot)
    if point is None:
        return None, False
    if not verified_natal_cores:
        return bounds, True
    expected = _birth_pillars(snapshot, point)
    inputs = snapshot['input']
    return bounds, _verify_fallback_cores(inputs, expected, verified_natal_cores,
                                          bool(inputs.get('uncertainty_minutes', 0)))


def _verify_candidate_coverage(snapshot, ages, candidate_ids, *, civil, dut1_seconds=0.0, verify_ages=True):
    """Return the replay after checking intervals and witness associations."""
    kind = snapshot.get('kind')
    if kind in (KNOWN_SHICHEN, KNOWN_CLOCK_BAND):
        scope = '出生时辰' if kind == KNOWN_SHICHEN else '出生钟面区间'
        if snapshot.get('time_basis') != 'civil':
            raise ValueError(scope + '须采用原民用钟面')
        if 'timezone_source' in snapshot:
            check_timezone_source(snapshot['timezone_source'], snapshot.get('timezone'))
        if kind == KNOWN_SHICHEN:
            precision = dict(shichen=snapshot['shichen'])
        else:
            band = snapshot.get('clock_band')
            if not isinstance(band, dict) or not all(isinstance(band.get(key), str)
                                                     for key in ('start_inclusive', 'end_exclusive')):
                raise ValueError('缺少原出生钟面区间的起止')
            precision = dict(clock_band=(band['start_inclusive'], band['end_exclusive']))
        expected = analyze_birth_date(parse_birth_date(snapshot['solar_date']), snapshot['sex'],
                                      utc_offset=snapshot['utc_offset'], zone=snapshot['timezone'], **precision)
        expected_ids = {candidate['id'] for candidate in expected['candidates']}
        if any(snapshot.get(key) != expected[key] for key in ('coverage', 'windows')):
            raise ValueError('时辰候选区间与原出生输入重算不一致')
        saved_pillars = {row['id']: row.get('pillars') for row in snapshot['candidates']}
        expected_pillars = {row['id']: row['pillars'] for row in expected['candidates']}
        if snapshot.get('stable_pillars') != expected['stable_pillars'] or saved_pillars != expected_pillars:
            raise ValueError(scope + '的四柱摘要与原出生输入重算不一致')
    else:
        inputs, scenarios = snapshot['input'], snapshot['scenarios']
        expected = enumerate_scenarios(civil, inputs['uncertainty_minutes'], inputs['time_basis'],
                                       inputs.get('lon'), inputs['sex'], dut1_seconds=dut1_seconds)
        expected_ids = {f'candidate-{i}' for i in range(1, len(expected['variants']) + 1)}
        if inputs.get('enumerate_scenarios', True) is not True:
            raise ValueError('原出生输入的误差枚举标记与存档候选不一致')
        if scenarios.get('interval_semantics') != expected['interval_semantics']:
            raise ValueError('原出生误差枚举的区间口径与原输入重算不一致')
        if 'scope' in scenarios and scenarios['scope'] != expected['scope']:
            raise ValueError('原出生误差枚举的范围声明与原输入重算不一致')
        if any(scenarios.get(key) != expected[key] for key in ('start_utc', 'end_utc', 'coverage')):
            raise ValueError('出生误差枚举范围与原出生输入重算不一致')
        # Warnings may reference the original analysis year. Coverage depends
        # on the reachable chart fields, witnesses and intervals.
        if scenario_witnesses(scenarios) != scenario_witnesses(expected):
            raise ValueError('出生误差枚举候选与原出生输入重算不一致，须按原参数重建快照')
    if ((verify_ages and ages != expected['dayun_age_comparison']) or
            (candidate_ids is not None and candidate_ids != expected_ids)):
        raise ValueError('折月段、出生候选或见证与原出生输入重算不一致，须按原参数重建快照')
    return expected


def _birth_segment_intersections(left, right, end_inclusive, candidate_intervals):
    """Clip a physical age segment to the same candidate's ordered intervals."""
    intersections = []
    for interval in candidate_intervals:
        candidate_left = datetime.fromisoformat(interval['start_utc'])
        candidate_right = datetime.fromisoformat(interval['end_utc'])
        start = max(left, candidate_left)
        end = min(right, candidate_right)
        includes_end = ((end < right or end_inclusive) and
                        (end < candidate_right or interval['end_inclusive']))
        if start > end or (start == end and not includes_end):
            continue
        if intersections and intersections[-1]['end_utc'] == start.isoformat():
            intersections[-1].update(end_utc=end.isoformat(), end_inclusive=includes_end)
        else:
            intersections.append(dict(start_utc=start.isoformat(), end_utc=end.isoformat(),
                                      end_inclusive=includes_end))
    return intersections


def _core_from_pillars(pillars, sex, scenario_id=None):
    if (not isinstance(pillars, dict) or set(pillars) != set(core.KEYS) or
            any(not isinstance(value, str) or len(value) != 2 or
                value[0] not in engine.GAN or value[1] not in engine.ZHI for value in pillars.values())):
        raise ValueError('本命核心复核须保留完整的原四柱')
    fields = {'bazi.' + key: pillars[key] for key in core.KEYS}
    return core.analyze(dict(pillars=canonical_pillars(fields), sex=sex, scenario_id=scenario_id),
                        candidate_temporal_uncertainty=scenario_id is not None)


def _replay_luck_core(analysis, sex, scenario_id=None):
    """Rebuild derived modules from the four pillars checked against this witness."""
    return _core_from_pillars({key: analysis['facts'][key]['pillar'] for key in core.KEYS}, sex, scenario_id)


def _verify_enumerated_candidate(row, variant, scenario_id):
    if variant is not None:
        pillars = {key: ''.join(variant['fields']['bazi.' + key]) for key in core.KEYS}
        if (row['id'] == scenario_id and row.get('pillars') == pillars and
                all(row.get(key) == variant[key] for key in ('witness_utc', 'chart_clock', 'intervals'))):
            return pillars
    raise ValueError('存档八字候选与原出生输入重算不一致：' + scenario_id)


def _check_saved_candidate_context(comparison, replayed):
    context = comparison.get('context')
    if (comparison.get('coverage') != replayed['coverage'] or not isinstance(context, dict) or
            any(context.get(key) != replayed[key] for key in ('start_utc', 'end_utc', 'interval_semantics'))):
        raise ValueError('存档八字候选的覆盖口径或实际范围与原出生输入重算不一致')


def _enumerated_natal_without_ages(snapshot, candidates, civil, dut1_seconds, *, replayed=None):
    """Recover verified natal candidates when the derived age table is absent."""
    error = '出生误差已枚举但缺少折月段或八字候选'
    if (not isinstance(candidates, list) or not candidates or
            any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in candidates)):
        raise ValueError(error)
    ids = {row['id'] for row in candidates}
    if len(ids) != len(candidates):
        raise ValueError('出生候选 ID 重复')
    if replayed is None:
        replayed = _verify_candidate_coverage(snapshot, None, ids, civil=civil,
                                              dut1_seconds=dut1_seconds, verify_ages=False)
    _check_saved_candidate_context(snapshot['bazi_scenario_comparison'], replayed)
    sex = snapshot['input']['sex']
    result = []
    for i, (row, variant) in enumerate(zip(candidates, replayed['variants']), 1):
        scenario_id = f'candidate-{i}'
        pillars = _verify_enumerated_candidate(row, variant, scenario_id)
        if 'analysis' in row:
            analysis = row['analysis']
            facts = analysis.get('facts') if isinstance(analysis, dict) else None
            if (not isinstance(facts, dict) or any(not isinstance(facts.get(key), dict) or
                                                   facts[key].get('pillar') != pillar for key, pillar in pillars.items())):
                raise ValueError('存档本命核心的四柱与原出生输入重算不一致：' + scenario_id)
            _verify_model_birth_scope(analysis, scenario_id, scenario_id)
            if (analysis.get('primary_spouse') or {}).get('sex') not in (None, sex):
                raise ValueError('八字出生性别与已存核心不一致：' + scenario_id)
        result.append(dict(id=scenario_id, pillars=pillars, analysis=_core_from_pillars(pillars, sex, scenario_id),
                           witness_utc=variant['witness_utc'], birth_segments=variant['intervals']))
    return dict(coverage=replayed['coverage'], tables=[], natal_candidates=result)


def _exact_natal_without_age_table(snapshot, native):
    inputs = snapshot['input']
    sex = inputs.get('sex')
    if native.get('hour_unknown', False) is not False or sex not in ('男', '女'):
        return None
    if native.get('sex') not in (None, sex):
        raise ValueError('八字出生性别与原盘不一致：bazi.pillars')
    pillars = native.get('pillars', {})
    if not isinstance(pillars, dict):
        raise ValueError('八字原四柱须为对象')
    hour = pillars.get('hour')
    if isinstance(hour, (list, tuple)) and tuple(hour) == ('未知',) * 4:
        return None
    point, bounds = _original_birth_range(snapshot)
    if point is None or bounds[0] != bounds[1]:
        return None
    expected = _birth_pillars(snapshot, point)
    if 'hour' not in expected:
        return None
    canonical = _replayed_exact_pillars(pillars, expected)
    if 'bazi_core_reading' in snapshot:
        saved = snapshot['bazi_core_reading']
        if not isinstance(saved, dict) or not isinstance(saved.get('facts'), dict):
            raise ValueError('存档本命核心缺少可核四柱：bazi_core_reading')
        _verify_fallback_cores(inputs, expected, [saved], False)
    return core.analyze(dict(pillars=canonical, sex=sex))


def _replayed_exact_pillars(pillars, expected):
    canonical = canonical_pillars({'bazi.' + key: value for key, value in expected.items()})
    for key in core.KEYS:
        if key in pillars and (not isinstance(pillars[key], (list, tuple)) or tuple(pillars[key]) != canonical[key]):
            raise ValueError('八字原四柱与原出生输入重排不一致：' + key)
    return canonical


def birth_luck_tables(snapshot):
    """Read native age tables with replayed birth cores and their witnesses."""
    kind = snapshot.get('kind')
    dut1_seconds = 0.0
    civil = None
    variants = None
    replayed_scenarios = None
    if kind in (KNOWN_SHICHEN, KNOWN_CLOCK_BAND):
        if 'dayun_age_comparison' not in snapshot:
            # Keep canonical birth coverage without treating the reconstructed
            # age rows as a table retained in the original snapshot.
            candidates = snapshot.get('candidates')
            if (snapshot.get('interval_semantics') != 'start_inclusive_end_exclusive' or
                    not isinstance(candidates, list) or not candidates or
                    any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in candidates)):
                raise ValueError('旧档缺折月表时须保留可核出生候选和民用半开区间')
            candidate_ids = {row['id'] for row in candidates}
            if len(candidate_ids) != len(candidates):
                raise ValueError('出生候选 ID 重复')
            replayed = _verify_candidate_coverage(snapshot, None, candidate_ids, civil=None, verify_ages=False)
            return dict(coverage='birth_luck_unverified', tables=[],
                        natal_candidates=_civil_candidates_with_segments(replayed))
        ages = snapshot['dayun_age_comparison']
        if not isinstance(ages, dict) or not isinstance(ages.get('segments'), list) or not ages['segments']:
            raise ValueError('存档折月表无有效运段，须按原出生输入重建')
        candidates = snapshot['candidates']
        sex = snapshot['sex']
        zone = (iana_zone(snapshot['timezone']) if snapshot['timezone'] else
                fixed_utc_offset(snapshot['utc_offset']))
        basis, lon = 'civil', None
        source = 'dayun_age_comparison.segments'
    elif kind == UNKNOWN_HOUR:
        return dict(coverage=snapshot['coverage'], tables=[])
    elif snapshot['input'].get('uncertainty_minutes'):
        scenarios = snapshot.get('scenarios') or {}
        if not scenarios:
            return dict(coverage='uncertainty_not_enumerated', tables=[])
        ages = scenarios.get('dayun_age_comparison')
        has_age_table = 'dayun_age_comparison' in scenarios
        missing_comparison = 'bazi_scenario_comparison' not in snapshot
        source = 'scenarios.dayun_age_comparison.segments'
        if has_age_table and (not isinstance(ages, dict) or not isinstance(ages.get('segments'), list) or
                              not ages['segments']):
            raise ValueError('出生误差已枚举但缺少折月段或八字候选')
        inputs = snapshot['input']
        sex, basis, lon = inputs['sex'], inputs['time_basis'], inputs.get('lon')
        if basis == 'apparent-solar':
            recorded_dut1 = snapshot_dut1_seconds(inputs, snapshot.get('qizheng'))
            dut1_seconds = recorded_dut1 or 0.0
        civil = _verified_civil_point(snapshot)
        clock_snapshot = snapshot
        if basis == 'apparent-solar' and recorded_dut1 is None:
            # The old enumeration contract permits zero only when the original witnesses replay.
            clock_snapshot = dict(snapshot, input=dict(inputs, dut1_seconds=dut1_seconds))
        _original_chart_clock(clock_snapshot, civil, allow_missing_record=True)
        if missing_comparison:
            replayed_scenarios = _verify_candidate_coverage(
                snapshot, ages, None, civil=civil, dut1_seconds=dut1_seconds, verify_ages=has_age_table)
            snapshot = dict(snapshot, bazi_scenario_comparison=analyze(replayed_scenarios, sex=sex))
        comparison = snapshot['bazi_scenario_comparison']
        candidates = comparison.get('candidates') if isinstance(comparison, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise ValueError('出生误差已枚举但缺少折月段或八字候选')
        if not has_age_table:
            return _enumerated_natal_without_ages(snapshot, candidates, civil, dut1_seconds,
                                                  replayed=replayed_scenarios)
        zone = civil.tzinfo
        variants = {f'candidate-{index}': row for index, row in enumerate(scenarios['variants'], 1)}
    else:
        inputs = snapshot['input']
        bounds = recorded_scenario_bounds(inputs, snapshot.get('scenarios'))
        point = _verified_civil_point(snapshot) if bounds is not None else None
        _check_saved_scenario_bounds(snapshot, point.astimezone(UTC) if point is not None else None, timedelta())
        raw = snapshot.get('bazi', {})
        if not isinstance(raw, dict):
            raise ValueError('保存的八字原盘须为对象')
        table = raw.get('dayun_age_windows')
        if table is not None and not isinstance(table, dict):
            raise ValueError('八字原折月大运表须为对象')
        if not table:
            result = dict(coverage='birth_luck_unverified', tables=[])
            natal_core = _exact_natal_without_age_table(snapshot, raw)
            if natal_core is not None:
                result['natal_core'] = natal_core
            return result
        if (('hour_unknown' in raw and type(raw['hour_unknown']) is not bool) or
                ('birth_time_is_reference' in table and type(table['birth_time_is_reference']) is not bool)):
            raise ValueError('八字原时柱和折月大运表的参考时间标记须为布尔值')
        hour_unknown = raw.get('hour_unknown')
        reference = table.get('birth_time_is_reference')
        if reference is False and hour_unknown is True:
            raise ValueError('八字原时柱未知与原折月大运表的精确时间标记冲突')
        pillars = raw.get('pillars')
        full_native_pillars = isinstance(pillars, dict) and all(key in pillars for key in core.KEYS)
        if reference is True or (reference is None and hour_unknown is not False):
            return dict(coverage='birth_luck_unverified', tables=[])
        windows = table.get('windows')
        if not isinstance(windows, list) or not windows:
            raise ValueError('八字原折月大运表缺少有效运段')
        point = point or _verified_civil_point(snapshot)
        expected_clock = _original_chart_clock(snapshot, point, allow_missing_record=True)
        if expected_clock is None:
            return dict(coverage='birth_luck_unverified', tables=[])
        source = 'bazi.dayun_age_windows.windows'
        if raw.get('sex') not in (None, inputs['sex']):
            raise ValueError('八字出生性别与原盘不一致：' + source)
        if 'bazi_core_reading' in snapshot:
            analysis = snapshot['bazi_core_reading']
        elif full_native_pillars:
            analysis = core.analyze(raw)
        else:
            saved_pillars = raw.get('pillars', {})
            if not isinstance(saved_pillars, dict):
                raise ValueError('八字原四柱须为对象')
            expected_pillars = _birth_pillars(snapshot, point)
            analysis = core.analyze(dict(pillars=_replayed_exact_pillars(saved_pillars, expected_pillars),
                                         sex=inputs['sex']))
        _verify_native_luck(analysis, windows, point, inputs['sex'], source)
        _verify_birth_clock(analysis, expected_clock, source)
        _verify_model_birth_scope(analysis, None, source)
        if 'pillars' in raw:
            if not isinstance(pillars, dict):
                raise ValueError('八字原四柱须为对象')
            for key in core.KEYS:
                if key not in pillars:
                    continue
                pair = pillars[key]
                if (not isinstance(pair, (list, tuple)) or len(pair) < 2 or
                        any(not isinstance(value, str) for value in pair[:2]) or
                        ''.join(pair[:2]) != analysis['facts'][key]['pillar']):
                    raise ValueError('八字原四柱与已核本命核心不一致：' + key)
        return dict(coverage='single_birth_input', tables=[
            dict(analysis=_replay_luck_core(analysis, inputs['sex']), windows=windows, source=source, witness=None,
                 birth_segments=[], birth_segment=None)
        ])

    by_id = {}
    for candidate in candidates:
        identity = candidate['id']
        if 'analysis' in candidate:
            analysis = candidate['analysis']
        else:
            pillars = candidate.get('pillars')
            if variants is not None:
                pillars = _verify_enumerated_candidate(candidate, variants.get(identity), identity)
            analysis = _core_from_pillars(pillars, sex, identity)
        by_id[identity] = analysis
    if len(by_id) != len(candidates):
        raise ValueError('出生候选 ID 重复')
    tables = []
    for index, segment in enumerate(ages['segments']):
        segment_source = f'{source}[{index}]'
        left, right = (datetime.fromisoformat(segment[key]) for key in ('start_utc', 'end_utc'))
        age_birth_segment = {key: segment[key] for key in ('start_utc', 'end_utc', 'end_inclusive')}
        if not segment['birth_witnesses']:
            raise ValueError('折月段缺少出生见证：' + segment_source)
        for witness in segment['birth_witnesses']:
            scenario_id = witness['scenario_id']
            analysis = by_id.get(scenario_id)
            if (analysis is None or any(analysis['facts'][layer]['pillar'] != segment[layer + '_pillar']
                        for layer in ('year', 'month'))):
                raise ValueError('折月段与出生候选不匹配：' + segment_source)
            point = datetime.fromisoformat(witness['witness_utc'])
            if (not all(t.utcoffset() is not None for t in (left, right, point)) or point < left or
                    point > right or (point == right and not segment['end_inclusive'])):
                raise ValueError('折月见证不在对应出生区间：' + segment_source)
            native = _verify_native_luck(analysis, segment['age_windows'], point, sex, segment_source)
            if any(segment[key] != native[key] for key in ('start_age_months', 'forward')):
                raise ValueError('折月段起运或顺逆与出生见证不一致：' + segment_source)
            clock = scenario_clock_at(point, zone, basis, lon, dut1_seconds=dut1_seconds)
            shichen = _verify_birth_clock(analysis, clock, segment_source)
            _verify_model_birth_scope(analysis, scenario_id, segment_source)
            if kind in (KNOWN_SHICHEN, KNOWN_CLOCK_BAND):
                if (clock.date().isoformat() != snapshot['solar_date'] or
                        (kind == KNOWN_SHICHEN and shichen != snapshot['shichen'])):
                    raise ValueError('折月见证超出原民用生日或时辰：' + segment_source)
                birth_segments = [age_birth_segment]
            else:
                variant = variants.get(scenario_id, {})
                raw = variant.get('fields', {})
                if (raw.get('ziwei.solar_date'), raw.get('ziwei.shichen_index'), raw.get('ziwei.birth_year')) != (
                        clock.date().isoformat(), engine.ZHI_LIST.index(shichen), point.astimezone(zone).year):
                    raise ValueError('出生见证与原枚举候选的日期或时辰不一致，须按原参数重建快照：' +
                                     segment_source)
                birth_segments = _birth_segment_intersections(
                    left, right, segment['end_inclusive'], variant['intervals'])
            tables.append(dict(windows=segment['age_windows'], source=segment_source + '.age_windows',
                               witness=dict(witness),
                               birth_segments=birth_segments,
                               birth_segment=birth_segments[0] if len(birth_segments) == 1 else None))
    if replayed_scenarios is None:
        replayed_scenarios = _verify_candidate_coverage(
            snapshot, ages, by_id.keys(), civil=civil, dut1_seconds=dut1_seconds)
    if variants is not None:
        _check_saved_candidate_context(comparison, replayed_scenarios)
        for row in candidates:
            _verify_enumerated_candidate(row, variants.get(row['id']), row['id'])
    replayed = {scenario_id: _replay_luck_core(analysis, sex, scenario_id)
                for scenario_id, analysis in by_id.items()}
    for table in tables:
        table['analysis'] = replayed[table['witness']['scenario_id']]
    return dict(coverage=ages['natal_candidate_coverage'], tables=tables)


def luck_contexts_at_age(snapshot, folded_age_months):
    """Select each source-linked luck row at a caller-verified model age."""
    if folded_age_months is not None and (type(folded_age_months) is not int or folded_age_months < 0):
        raise ValueError('折月年龄须为非负整数，未知时用 None')
    result = birth_luck_tables(snapshot)
    contexts = []
    for table in result['tables']:
        active = [(index, row) for index, row in enumerate(table['windows'])
                  if folded_age_months is not None and
                  row['start_months_inclusive'] <= folded_age_months < row['end_months_exclusive']]
        if len(active) > 1:
            raise ValueError('同一出生候选的大运年龄窗重叠：' + table['source'])
        source = table['source']
        pillar = None
        age_window = None
        if active:
            index, age_window = active[0]
            source += f'[{index}]'
            start, end = age_window['start_months_inclusive'], age_window['end_months_exclusive']
            window = f'原折月年龄 [{start}, {end}) 个月'
            status = 'before_major_luck' if age_window['sequence'] == '起运前' else 'active'
            if status == 'active':
                pillar = age_window['pillar']
        elif folded_age_months is None:
            window = '本次折月年龄未知'
            status = 'age_unknown'
        else:
            window = f'原折月年龄 {folded_age_months} 个月未落入已排运窗'
            status = 'outside_luck_windows'
        age_table_range = dict(
            start_months_inclusive=table['windows'][0]['start_months_inclusive'],
            end_months_exclusive=table['windows'][-1]['end_months_exclusive'])
        contexts.append(dict(analysis=table['analysis'], witness=table['witness'],
                             birth_segment=table['birth_segment'], birth_segments=table['birth_segments'],
                             age_window=age_window, status=status,
                             age_table_range=age_table_range,
                             luck=dict(layer='luck', pillar=pillar, source=source, window=window)))
    bound = dict(coverage=result['coverage'], folded_age_months=folded_age_months, contexts=contexts)
    if 'natal_candidates' in result:
        bound['natal_candidates'] = result['natal_candidates']
    if 'natal_core' in result:
        bound['natal_core'] = result['natal_core']
    return bound


def luck_windows_in_range(snapshot, start_months, end_months):
    """Clip replayed native tables to a caller-verified half-open folded-age range."""
    if (type(start_months) is not int or type(end_months) is not int or
            not 0 <= start_months < end_months):
        raise ValueError('所问折月年龄范围须为非空的非负整数半开区间')
    result = birth_luck_tables(snapshot)

    def clip(start, end):
        return dict(start_months_inclusive=start, end_months_exclusive=end)

    tables = []
    for table in result['tables']:
        intersections = []
        for index, row in enumerate(table['windows']):
            left = max(start_months, row['start_months_inclusive'])
            right = min(end_months, row['end_months_exclusive'])
            if left < right:
                intersections.append(dict(age_range=clip(left, right), native_window=dict(row),
                                          source=f"{table['source']}[{index}]"))
        first = table['windows'][0]['start_months_inclusive']
        last = table['windows'][-1]['end_months_exclusive']
        outside = [clip(left, right) for left, right in (
            (start_months, min(end_months, first)), (max(start_months, last), end_months)) if left < right]
        tables.append(dict(table, intersections=intersections, outside_table=outside))
    return dict(result, requested_age_range=clip(start_months, end_months), tables=tables)


def _parse_date_only(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return parse_birth_date(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description='分段核查已知民用生日、时辰或钟面区间的八字候选')
    parser.add_argument('--birth-date', required=True, type=_parse_date_only, help='公历出生日期 YYYY-MM-DD')
    parser.add_argument('--sex', required=True, choices=('男', '女'))
    parser.add_argument('--shichen', choices=engine.ZHI_LIST, help='已确认的民用时辰，分钟未知')
    parser.add_argument('--start', help='已确认出生钟面区间起点 HH:MM，含起点')
    parser.add_argument('--end', help='已确认出生钟面区间终点 HH:MM，不含终点')
    zone = parser.add_mutually_exclusive_group()
    zone.add_argument('--utc-offset', type=float, help='民用 UTC 偏移，只知生日或时辰时默认 +08')
    zone.add_argument('--timezone', help='民用 IANA 时区')
    args = parser.parse_args(argv)
    clock_band = None
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None:
            parser.error('出生钟面区间须同时提供 --start 与 --end')
        clock_band = (args.start, args.end)
    try:
        result = analyze_birth_date(args.birth_date, args.sex, utc_offset=args.utc_offset,
                                    zone=args.timezone, shichen=args.shichen, clock_band=clock_band)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def evidence(analysis):
    facts = analysis['facts']
    month = facts['month']['branch']
    season = next(s for chars, s in [('寅卯辰', '春'), ('巳午未', '夏'),
                                    ('申酉戌', '秋'), ('亥子丑', '冬')] if month in chars)
    relations = [core.describe([core.LABELS[k] + '柱' for k in r['positions']]) +
                 r['symbols'] + r['kind'] for r in analysis['relations'] + analysis['groups']]
    exposure = [r['stem'] + '（' + r['ten_god'] + '）' +
                ('透于' + core.describe([core.LABELS[k] + '干' for k in r['exposed_at']])
                 if r['exposed_at'] else '未透于年/月/时干') +
                ('，与日干相同' if r['same_as_day'] else '') for r in analysis['month_exposure']]
    return {'day_master': facts['day']['stem'] + core.element(facts['day']['stem']),
            'season': month + '月，节气划分的' + season + '季',
            'roots': core.describe(analysis['roots']), 'relations': core.describe(relations),
            'month_exposure': '；'.join(exposure),
            'support': core.describe(analysis['support']),
            'opposing': core.describe(analysis['opposing'])}


def analyze(scenarios, sex=None):
    time_uncertain = scenarios['start_utc'] != scenarios['end_utc']
    rows = []
    for i, variant in enumerate(scenarios['variants'], 1):
        analysis = core.analyze(
            {'pillars': canonical_pillars(variant['fields']),
             'scenario_id': 'candidate-' + str(i), 'sex': sex},
            candidate_temporal_uncertainty=time_uncertain)
        facts = evidence(analysis)
        # Newer rule versions may expose a conditional pattern decision. Keep
        # the comparison valid with the original structural-only analyzer too.
        if 'pattern_reasoning' in analysis:
            facts['pattern'] = analysis['pattern_reasoning']['text']
        facts['strength'] = analysis['strength_reasoning']['text']
        rows.append({'id': 'candidate-' + str(i), 'witness_utc': variant['witness_utc'],
                     'chart_clock': variant['chart_clock'], 'intervals': variant['intervals'],
                     'pillars': {k: analysis['facts'][k]['pillar'] for k in core.KEYS},
                     'evidence': facts, 'analysis': analysis})
    if not rows:
        raise ValueError('候选比较至少需要一个可达候选')
    constant = {k: v for k, v in rows[0]['evidence'].items()
                if all(row['evidence'][k] == v for row in rows)}
    changed = [k for k in rows[0]['evidence'] if k not in constant]
    complete = scenarios['coverage'] == 'complete_for_modeled_boundaries_not_astronomical_error'
    labels = dict(LABELS, pattern='格局条件判断', strength='强弱条件比较')
    for row in rows:
        row['text'] = '；'.join(labels[k] + '：' + row['evidence'][k] for k in changed) if changed else '所列结构证据与其他候选相同。'
    return {'schema_version': 1, 'rule_version': VERSION, 'coverage': scenarios['coverage'],
            'scope': '仅比较枚举器返回的八字四柱结构；不代表完整紫微、七政、起运或人生预测',
            'reviewed_panel_scope': '新增卡片逐候选解释，仅对相应见证输入成立；未将卡片结论纳入区间稳定性判定。',
            'context': {k: scenarios[k] for k in ('start_utc', 'end_utc', 'interval_semantics', 'excluded')},
            'stable_evidence': constant if complete else {},
            'observed_constant_evidence': {} if complete else constant,
            'changing_evidence': changed, 'labels': labels, 'candidates': rows,
            'warnings': ['差别来自出生时刻输入的不确定性，不是多个未来结果的概率；没有给候选分配可信度。',
                         '根气仅指藏干有日主同五行；配对不等于合化或事件。共同线索也不直接推出强弱、喜忌。'] +
                        ([] if complete else ['真太阳时仅比较已找到的数值样本，不能声称覆盖全部候选或保证结构稳定。'])}


def render(comparison):
    lines = ['', '### 出生时刻候选的八字对照', '', comparison['scope'] + '。']
    constant = comparison['stable_evidence'] or comparison['observed_constant_evidence']
    heading = ('区间内共同证据（仅当前模型）'
               if comparison['coverage'] == 'complete_for_modeled_boundaries_not_astronomical_error'
               else '已找到样本的共同证据（不保证区间稳定）')
    lines.append(heading + '：')
    lines.extend('- ' + comparison['labels'][k] + '：' + value for k, value in constant.items())
    if not constant:
        lines.append('- 所列证据没有共同项。')
    for i, row in enumerate(comparison['candidates'], 1):
        lines += ['', '**候选 %d**：' % i + '、'.join(core.LABELS[k] + '柱' + v for k, v in row['pillars'].items()) +
                  '；可达样本 UTC ' + row['witness_utc'] + '。']
        analysis = row['analysis']
        for name, render_panel in (('qiong_xin_zi_model', bazi_qiong_xin_zi.render),
                                   ('primary_spouse', bazi_primary_spouse.render)):
            if name in analysis:
                lines += render_panel(analysis[name], nested=True)
        lines += ['', row['text']]
    if 'day_master' in comparison['changing_evidence']:
        lines.append('日主改变后，十神和根气都必须按各自日干重算，不能把中心盘的身份或生扶判断搬到另一候选。')
    if 'season' in comparison['changing_evidence']:
        lines.append('跨节气改变月令和季节背景，取格与调候的前提随之改变；不能共用中心盘的月令判断。')
    lines.extend('注意：' + w for w in comparison['warnings'])
    sources = {(r['analysis']['source']['path'], r['analysis']['source']['version']) for r in comparison['candidates']}
    lines.append('依据：' + '；'.join(path + '，' + version for path, version in sorted(sources)) + '；候选保留原枚举器的 UTC 见证与区间。')
    pattern_sources = []
    for row in comparison['candidates']:
        pattern = row['analysis'].get('pattern_reasoning')
        if pattern and pattern['attribution'] not in pattern_sources:
            pattern_sources.append(pattern['attribution'])
    for source in pattern_sources:
        lines += core.render_pattern_attribution(source, scope='上述候选对照中的格局候选解释')
    lines += core.strength_reasoning.render_attribution(comparison['candidates'][0]['analysis']['strength_reasoning']['attribution'])
    return lines


if __name__ == '__main__':
    main()
