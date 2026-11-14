#!/usr/bin/env python3
"""Read Ziwei candidates for a confirmed clock interval on one civil birth date."""
import argparse
import json
from copy import deepcopy

from time_scenarios import (
    MAX_YEAR, MIN_YEAR, TICK, UTC, check_timezone_source, civil_clock_band_shichen_spans,
    iana_zone, parse_birth_date, parse_civil_clock_band, timezone_provenance,
)
from ziwei_life_reading import BIRTH_BAND_SCHEMA, BRANCHES, _chart, _fill_missing_chart_annotations, _same_identity, analyze
from ziwei_native import run_ziwei


BAND_INTERVAL = 'confirmed_civil_clock_membership_start_inclusive_end_exclusive'
BAND_COVERAGE = 'reachable_discrete_shichen_in_confirmed_civil_band'


def civil_span_record(left, right, tz):
    """Keep the actual offset-bearing and UTC bounds of a civil span."""
    return dict(
        start_inclusive=left.isoformat(), end_exclusive=right.isoformat(),
        start_utc=left.astimezone(UTC).isoformat(), end_exclusive_utc=right.astimezone(UTC).isoformat(),
        fold_at_start=left.astimezone(tz).fold if tz else 0,
        fold_at_last_included=(right - TICK).astimezone(tz).fold if tz else 0,
    )


def _reachable_shichen(day, start, end, zone, utc_offset):
    spans = civil_clock_band_shichen_spans(day, start, end, utc_offset=utc_offset, zone=zone)
    tz = iana_zone(zone) if zone is not None else None
    reachable = {}
    for left, right, index in spans:
        reachable.setdefault(index, []).append(civil_span_record(left, right, tz))
    return reachable


def _band_candidate_inputs(day, start, end, sex, analysis_year, zone, utc_offset):
    if not MIN_YEAR <= day.year <= MAX_YEAR:
        raise ValueError('紫微出生区间仅支持 1901–2099 年的民用日期')
    if (zone is None) == (utc_offset is None):
        raise ValueError('须明确提供出生时区或固定 UTC 偏移')
    if ((zone is not None and not isinstance(zone, str)) or
            (utc_offset is not None and type(utc_offset) not in (int, float))):
        raise ValueError('出生时区或固定 UTC 偏移无效')
    if sex not in ('男', '女'):
        raise ValueError('性别须为男或女')
    if type(analysis_year) is not int or not day.year <= analysis_year <= 9999:
        raise ValueError('分析年须为不早于原民用出生年的有效年份')
    start_minutes, end_minutes = parse_civil_clock_band(start, end)
    reachable = _reachable_shichen(day, start_minutes, end_minutes, zone, utc_offset)
    return [dict(id='ziwei-band-' + str(index),
                 input=dict(solar_date=day.isoformat(), birth_year=day.year, shichen_index=index,
                            shichen=BRANCHES[index], sex=sex),
                 civil_spans=spans)
            for index, spans in sorted(reachable.items(), key=lambda item: item[1][0]['start_utc'])]


def native_shichen_chart(day, identity, analysis_year):
    """Invoke the native chart using the confirmed discrete shichen."""
    sex = identity['sex']
    raw, error = run_ziwei(day.year, day.month, day.day, None, None, sex, None, None,
                           age_year=analysis_year, birth_year=day.year, output_format='json',
                           shichen=identity['shichen'])
    if error:
        return None, error
    native = json.loads(raw)
    expected = dict(solar=identity['solar_date'], birthYear=day.year, shichenIndex=identity['shichen_index'],
                    gender={'男': 'male', '女': 'female'}[sex], ageYear=analysis_year)
    if any(native['input'].get(key) != value for key, value in expected.items()):
        return None, '原生紫微输入与可达的民用日期、时辰或年份不一致'
    return native, None


def _candidate_context(candidate, index):
    return dict(id=candidate['id'], input=deepcopy(candidate['input']),
                civil_spans=deepcopy(candidate['civil_spans']), coverage=BAND_COVERAGE,
                chart_path=f'candidates[{index}].native.chart',
                scope='selected_reachable_civil_band_candidate_only', birth_time_confirmed=False)


def _matches_replayed_chart(chart, native):
    """Compare using known optional omissions while preserving the source chart."""
    compared = deepcopy(chart)
    observed = deepcopy(native)
    _fill_missing_chart_annotations(compared, native)
    # A query year may reconstruct these duplicates after the raw table matches.
    for field in ('currentAge', 'currentDaXianIndex'):
        if field not in compared:
            compared[field] = native[field]
    # A missing stage table limits T02 without invalidating natal evidence.
    # Any saved table still has to match the native replay.
    if compared.get('daXians') is None:
        compared.pop('daXians', None)
        observed.pop('daXians', None)
    # T02 checks the saved numeric bureau against the verified first stage age.
    compared.pop('wuxingJu', None)
    observed.pop('wuxingJu', None)
    try:
        palaces, _ = _chart(compared)
    except ValueError:
        return False
    # Align only the comparison copies. The returned chart retains its
    # saved order for palace and star evidence paths.
    palaces.sort(key=lambda palace: palace['branch'])
    observed['palaces'].sort(key=lambda palace: palace['branch'])
    for saved, source in zip(palaces, observed['palaces']):
        # T02 checks these optional mirrors against the verified native table.
        # A stale mirror limits stage use without invalidating this natal chart.
        for field in ('daXianAge', 'isCurrentDaXian'):
            saved.pop(field, None)
            source.pop(field, None)
        # The life panel derives empty-palace facts from actual placements.
        # Check any saved display annotations, without requiring them.
        for field in ('oppositeBranch', 'isEmpty', 'borrowedFromBranch', 'borrowedFromName', 'borrowedStars'):
            if field not in saved:
                source.pop(field, None)
        for palace in (saved, source):
            palace['stars'].sort(key=lambda star: (star['name'], star['type']))
        for star, native_star in zip(saved['stars'], source['stars']):
            for field in ('brightness', 'brightnessRaw', 'siHua'):
                saved_value = star.get(field)
                if saved_value is None or (field == 'siHua' and saved_value == ''):
                    if field in native_star:
                        star[field] = native_star[field]
                    else:
                        star.pop(field, None)
    return _same_identity(compared, observed)


def birth_time_candidates(day, start, end, sex, analysis_year, *, zone=None, utc_offset=None):
    """Return native chart evidence and conditional panels for reachable branches."""
    candidates = _band_candidate_inputs(day, start, end, sex, analysis_year, zone, utc_offset)
    for index, candidate in enumerate(candidates):
        native, error = native_shichen_chart(day, candidate['input'], analysis_year)
        candidate.update(native=native, life_reading=None, error=error)
        if error:
            continue
        panel = analyze(native['chart'], day.year, analysis_year, replayed_natal=native['chart'])
        panel['birth_scenario'] = _candidate_context(candidate, index)
        candidate['life_reading'] = panel
    statuses = {c['life_reading']['status'] if c['life_reading'] else 'withheld' for c in candidates}
    status = statuses.pop() if len(statuses) == 1 else 'partial'
    return dict(
        schema_version=BIRTH_BAND_SCHEMA, status=status,
        input=dict(birth_date=day.isoformat(), start_inclusive=start, end_exclusive=end, sex=sex,
                   analysis_year=analysis_year, time_basis='civil', timezone=zone, utc_offset_hours=utc_offset),
        interval_semantics=BAND_INTERVAL, birth_candidate_coverage=BAND_COVERAGE,
        birth_time_confirmed=False, timezone_source=timezone_provenance(zone), candidates=candidates,
    )


def select_birth_band_candidate(snapshot, candidate_id):
    """Recheck the full physical band and replay its selected native chart."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError('民用出生钟面区间续算须指定紫微候选 ID')
    inputs = snapshot.get('input')
    if (not isinstance(inputs, dict) or inputs.get('time_basis') != 'civil' or
            not all(isinstance(inputs.get(key), str) for key in ('birth_date', 'start_inclusive', 'end_exclusive')) or
            snapshot.get('birth_time_confirmed') is not False or
            snapshot.get('interval_semantics') != BAND_INTERVAL or snapshot.get('birth_candidate_coverage') != BAND_COVERAGE):
        raise ValueError('缺少可核的原民用出生钟面区间或区间口径')
    day = parse_birth_date(inputs['birth_date'])
    analysis_year = inputs.get('analysis_year')
    if 'timezone_source' in snapshot:
        check_timezone_source(snapshot['timezone_source'], inputs.get('timezone'))
    expected = {candidate['id']: candidate for candidate in _band_candidate_inputs(
        day, inputs['start_inclusive'], inputs['end_exclusive'], inputs.get('sex'), analysis_year,
        inputs.get('timezone'), inputs.get('utc_offset_hours'))}
    candidates = snapshot.get('candidates')
    if (not isinstance(candidates, list) or len(candidates) != len(expected) or
            any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in candidates)):
        raise ValueError('紫微候选集合未覆盖原民用出生钟面区间')
    by_id = {row['id']: (index, row) for index, row in enumerate(candidates)}
    if by_id.keys() != expected.keys():
        raise ValueError('紫微候选编号与原民用出生钟面区间不一致')
    for identity, reachable in expected.items():
        saved = by_id[identity][1]
        if any(saved.get(key) != reachable[key] for key in ('input', 'civil_spans')):
            raise ValueError('紫微候选出生身份或实际可达区间与原输入不一致：' + identity)
    if candidate_id not in by_id:
        raise ValueError('本快照未找到紫微候选 ID：' + candidate_id)
    index, selected = by_id[candidate_id]
    native = selected.get('native')
    if not isinstance(native, dict) or selected.get('error'):
        raise ValueError('所选紫微候选缺少有效原盘，请按原民用出生区间重排')
    reachable = expected[candidate_id]
    replayed, error = native_shichen_chart(day, reachable['input'], analysis_year)
    if error:
        raise ValueError('无法用内置紫微引擎复盘所选候选：' + error)
    chart = native.get('chart')
    if not isinstance(chart, dict) or not _same_identity(native.get('input'), replayed['input']):
        raise ValueError('所选紫微候选的原生输入或原盘与出生区间复盘不一致')
    if not _matches_replayed_chart(chart, replayed['chart']):
        raise ValueError('所选紫微候选的原生输入或原盘与出生区间复盘不一致')
    return chart, replayed['chart'], day.year, analysis_year, _candidate_context(reachable, index)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--birth-date', required=True, help='已确认的公历民用出生日期')
    parser.add_argument('--start', required=True, help='出生钟面区间起点 HH:MM，含起点')
    parser.add_argument('--end', required=True, help='出生钟面区间终点 HH:MM，不含终点')
    parser.add_argument('--sex', required=True, choices=('男', '女'))
    parser.add_argument('--analysis-year', required=True, type=int)
    zone = parser.add_mutually_exclusive_group(required=True)
    zone.add_argument('--timezone', help='出生地的 IANA 民用时区')
    zone.add_argument('--utc-offset', type=float, help='原民用钟面的明确固定 UTC 偏移小时')
    args = parser.parse_args(argv)
    try:
        result = birth_time_candidates(parse_birth_date(args.birth_date), args.start, args.end,
                                       args.sex, args.analysis_year, zone=args.timezone, utc_offset=args.utc_offset)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result['status'] == 'withheld' else 0


if __name__ == '__main__':
    raise SystemExit(main())
