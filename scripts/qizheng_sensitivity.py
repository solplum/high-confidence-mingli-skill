"""Bounded empirical time sensitivity, never an exhaustive partition/proof.

Refine categorical differences between adjacent grid witnesses, not a claim
of monotonicity or a physical event-time solver. Equal endpoint signatures
can hide excursions, tangent crossings and multiple roots, especially near
polar ascendant singularities. Every retained candidate is actually evaluated.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math

import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules
import qizheng_traditional_reading as tradition
from time_scenarios import (
    MAX_YEAR, MIN_YEAR, TICK, UnsupportedUtcInterval, civil_clock_band_shichen_spans,
    civil_shichen_spans, fixed_offset_spans, iana_zone, parse_birth_date, parse_civil_clock_band,
    timezone_provenance,
)

VERSION = 'qizheng-time-sensitivity-v1'
GRID_SECONDS = 60
BRACKET_SECONDS = 0.1
MAX_EVALUATIONS = 4096


def fields(chart, reading):
    """Only discrete outputs; continuous coordinates remain in witness charts."""
    out = {}
    for name, body in chart['bodies'].items():
        for key in ('mansion', 'mansion_wx', 'star'):
            out['bodies.' + name + '.' + key] = body[key]
        out['bodies.' + name + '.palace'] = engine.palace_of(body['sidereal'])
        out['bodies.' + name + '.near_boundary'] = body.get('classification_quality', {}).get('near_boundary')
    md = chart.get('ming_du')
    out['ascendant.defined'] = md is not None
    for key in ('mansion', 'wuxing', 'star'):
        out['ascendant.' + key] = md.get(key) if md else None
    out['ascendant.palace'] = engine.palace_of(md['sidereal']) if md else None
    out['ascendant.near_boundary'] = md.get('classification_quality', {}).get('near_boundary') if md else None
    out['ming_gong'] = chart.get('ming_gong')
    out['day_night'] = (chart.get('day_night') or {}).get('type')
    out['en_yong'] = chart.get('en_yong')
    out['rule_output'] = {key: reading.get(key) for key in ('status', 'reason', 'claims')}
    return out


def _validate_sampling_inputs(lat, lon, dut1_seconds):
    if (type(lat) not in (int, float) or type(lon) not in (int, float)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
            or not all(math.isfinite(x) for x in (lat, lon))):
        raise ValueError('七政敏感性经纬度超出范围')
    if (type(dut1_seconds) not in (int, float)
            or not -0.9 <= dut1_seconds <= 0.9
            or not math.isfinite(dut1_seconds)):
        raise ValueError('dut1_seconds must be finite and within +/-0.9 s (modern UTC)')


def _verify_utc_interval(start, end):
    if start.year < MIN_YEAR or end.year > MAX_YEAR:
        raise UnsupportedUtcInterval('七政敏感性完整 UTC 区间须在 1901–2099 年内')


def _grid_points(start, end, center=None):
    points = {start, end}
    if center is not None:
        points.add(center)
    t = start
    while t < end:
        points.add(t)
        t += timedelta(seconds=GRID_SECONDS)
    return sorted(points)


def compare(civil, minutes, lat, lon, profile='physical-v2', dut1_seconds=0.0, traditional_scheme=None, other_body='金'):
    if not isinstance(civil, datetime):
        raise ValueError('七政敏感性需要明确的出生瞬间')
    if (type(minutes) not in (int, float) or not 0 <= minutes <= 120
            or not math.isfinite(minutes)):
        raise ValueError('七政敏感性误差须在 0 至 120 分钟之间')
    _validate_sampling_inputs(lat, lon, dut1_seconds)
    try:
        if civil.utcoffset() is None:
            raise ValueError('七政敏感性需要明确的出生瞬间')
        center = civil.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('七政敏感性需要可转换为 UTC 的明确出生瞬间') from exc
    # Reject datetime extrema before interval arithmetic can overflow. Check
    # UTC, not the civil year: offsets can cross a supported-year boundary.
    _verify_utc_interval(center, center)
    start, end = center - timedelta(minutes=minutes), center + timedelta(minutes=minutes)
    _verify_utc_interval(start, end)
    return _sample(_grid_points(start, end, center), civil.tzinfo, lat, lon, profile, dut1_seconds,
                   traditional_scheme, other_body, max_evaluations=MAX_EVALUATIONS, center=center,
                   uncertain_birth=bool(minutes))


def _sample(points, local_timezone, lat, lon, profile, dut1_seconds, traditional_scheme, other_body,
            *, max_evaluations, center=None, uncertain_birth=True):
    """Sample inclusive UTC witness bounds. Only the old entry has a center."""
    start, end = points[0], points[-1]
    if len(points) > max_evaluations:
        raise ValueError('计算上限不足以保留七政区间的基础采样')
    cache = {}
    def evaluate(t):
        if t not in cache:
            if len(cache) >= max_evaluations:
                return None
            bj = t.astimezone(engine.BJ)
            chart, warnings = engine.compute((bj.year, bj.month, bj.day), bj.hour, bj.minute,
                lat, lon, birth_instant=t, profile=profile, dut1_seconds=dut1_seconds)
            # Pointwise evidence, not a grant to use this as the uncertain birth chart.
            reading = rules.analyze(chart, withhold_on_source_error=True)
            traditional = tradition.analyze(chart, traditional_scheme, other_body, False, birth_instant=t) if traditional_scheme else None
            discrete = fields(chart, reading)
            if traditional is not None:
                discrete['traditional_rule_output'] = {k: traditional.get(k) for k in ('status', 'reason', 'claims')}
            local = t.astimezone(local_timezone)
            cache[t] = {'witness_utc': t.isoformat(), 'witness_civil': local.isoformat(),
                        'fold': local.fold, 'chart': chart, 'rule_reading': reading,
                        'traditional_reading': traditional, 'warnings': warnings, 'fields': discrete}
        return cache[t]
    for t in points:
        evaluate(t)
    brackets = []
    pending = list(zip(points, points[1:]))
    budget_exhausted = False
    while pending:
        left, right = pending.pop()
        a, b = evaluate(left), evaluate(right)
        if a['fields'] == b['fields']:
            continue
        width = (right-left).total_seconds()
        if width <= BRACKET_SECONDS:
            brackets.append({'left_utc': left.isoformat(), 'right_utc': right.isoformat(),
                'width_seconds': width, 'changed_fields': sorted(k for k in a['fields'] if a['fields'][k] != b['fields'][k])})
            continue
        mid = left + (right-left)/2
        if evaluate(mid) is None:
            budget_exhausted = True
            brackets.append({'left_utc': left.isoformat(), 'right_utc': right.isoformat(),
                'width_seconds': width, 'unrefined': True,
                'changed_fields': sorted(k for k in a['fields'] if a['fields'][k] != b['fields'][k])})
            continue
        pending.extend(((left, mid), (mid, right)))
    # Keep one witness per observed signature plus both sides of every bracket
    # and start/centre/end. Nothing is a hypothetical combination of field values.
    keep = {start, end}
    if center is not None:
        keep.add(center)
    seen = set()
    for t, row in sorted(cache.items()):
        signature = json.dumps(row['fields'], ensure_ascii=False, sort_keys=True)
        if signature not in seen:
            seen.add(signature)
            keep.add(t)
    bracket_times = {b[k] for b in brackets for k in ('left_utc', 'right_utc')}
    keep.update(t for t in cache if t.isoformat() in bracket_times)
    first = cache[start]['fields']
    changed = sorted(k for k in first if any(row['fields'][k] != first[k] for row in cache.values()))
    limitations = [
        '有限采样及分类差异二分包围；未证明单调、连续或根数，可能遗漏同端点间短暂变化、相切及多次过界。',
        '未观察到变化不等于稳定；不输出稳定字段保证或完整候选集。',
        '0.1 秒是数值包围目标，不是天文精度、真实过界时间精度或出生时间精度。',
        '宿表未校准、误差未知；时间比较不消除宿界、星历、UT1/Delta T、大气/地形误差。',
        '紫气为未独立校准的模型点；physical-v2 是近似物理模型，不是精密星历或预测验证。',
        '此比较使用原始物理瞬间，不比较真太阳时选择本身；均时差及真太阳时误差仍未校准。',
        '每个候选的规则仅为该瞬间的条件证据；整段出生时间不确定时仍暂缓中心规则结论。',
        '高纬上升交点可退化或不连续；空命度保留，不假设单调或插值补齐。',
        ('区间为已解析中心前后实际经过 UTC 时间；不自动合并未选择的 fold。' if center is not None
         else '本段采样终点是排除端点前的最后一个可表示时刻；无中心出生盘。'),
    ]
    if profile == 'legacy-v1':
        limitations.append('legacy-v1 仅复现已知错误模型，不因比较而恢复可信度。')
    interval = {'start_utc': start.isoformat()}
    if center is not None:
        interval['center_utc'] = center.isoformat()
    interval.update(end_utc=end.isoformat(), endpoints_included=True, basis='elapsed_utc')
    # This block may be saved independently from its enclosing chart.
    inputs = dict(lat=lat, lon=lon, profile=profile, dut1_seconds=dut1_seconds)
    zone_name = getattr(local_timezone, 'key', None)
    if isinstance(zone_name, str):
        inputs['timezone'] = zone_name
    elif isinstance(local_timezone, timezone):
        seconds = local_timezone.utcoffset(None).total_seconds()
        if seconds % 60 == 0 and abs(seconds) <= 14 * 3600:
            inputs['utc_offset_hours'] = seconds / 3600
    return {'version': VERSION, 'status': 'sampled_conditional', 'coverage_complete': False,
        'input': inputs,
        'stable_fields': {}, 'observed_changing_fields': changed,
        'not_observed_changing_fields': sorted(set(first)-set(changed)),
        'interval': interval,
        'calculation_profile': profile, 'rule_profile': rules.PROFILE,
        'traditional_scheme': traditional_scheme, 'traditional_other_body': other_body if traditional_scheme else None,
        'method': {'grid_seconds': GRID_SECONDS, 'bracket_target_seconds': BRACKET_SECONDS,
                   'max_evaluations': max_evaluations, 'evaluation_count': len(cache),
                   'budget_exhausted': budget_exhausted, 'root_completeness_proven': False,
                   'search': 'bisect observed discrete signature differences; not continuous root isolation'},
        'high_latitude_caution': abs(lat) >= 66,
        'uncertain_birth_rule_status': 'withheld' if uncertain_birth else cache[center]['rule_reading']['status'],
        'boundaries': sorted(brackets, key=lambda b: b['left_utc']),
        'candidates': [cache[t] for t in sorted(keep)], 'limitations': limitations}


def compare_civil_band(day, start, end, lat, lon, *, zone=None, utc_offset=None,
                       profile='physical-v2', dut1_seconds=0.0, traditional_scheme=None, other_body='金'):
    """Sample each actual piece of a confirmed civil clock band independently."""
    return _compare_civil_birth(
        day, lat, lon, start=start, end=end, zone=zone, utc_offset=utc_offset, profile=profile,
        dut1_seconds=dut1_seconds, traditional_scheme=traditional_scheme, other_body=other_body,
    )


def _compare_civil_birth(day, lat, lon, *, start=None, end=None, shichen=None, zone=None, utc_offset=None,
                         profile='physical-v2', dut1_seconds=0.0, traditional_scheme=None, other_body='金'):
    if (zone is None) == (utc_offset is None):
        raise ValueError('须明确提供出生时区或固定 UTC 偏移')
    _validate_sampling_inputs(lat, lon, dut1_seconds)
    if shichen is None:
        if start is None or end is None:
            raise ValueError('须提供 --shichen 或一对 --start 与 --end')
        start_minutes, end_minutes = parse_civil_clock_band(start, end)
        spans = [(left, right) for left, right, _ in civil_clock_band_shichen_spans(
            day, start_minutes, end_minutes, zone=zone, utc_offset=utc_offset)]
        version = 'qizheng-civil-band-sensitivity-v1'
        semantics = 'confirmed_civil_clock_membership_start_inclusive_end_exclusive'
        birth_scope = dict(start_inclusive=start, end_exclusive=end)
    else:
        if start is not None or end is not None:
            raise ValueError('--shichen 与 --start、--end 须择一组')
        spans = civil_shichen_spans(day, shichen, utc_offset=utc_offset, zone=zone)
        version = 'qizheng-civil-shichen-sensitivity-v1'
        semantics = 'confirmed_civil_shichen_membership_start_inclusive_end_exclusive'
        birth_scope = dict(shichen=shichen)
    local_zone = iana_zone(zone) if zone is not None else None
    grids = []
    for left, right in spans:
        first, last = (left.astimezone(timezone.utc), right.astimezone(timezone.utc) - TICK)
        _verify_utc_interval(first, last)
        grids.append(_grid_points(first, last))
    future_grid_count = sum(map(len, grids))
    if future_grid_count > MAX_EVALUATIONS:
        raise ValueError('计算上限不足以保留七政出生钟面区间的全部基础采样')

    sections = []
    changed = set()
    first_fields = None
    remaining = MAX_EVALUATIONS
    for points, (local_start, local_end) in zip(grids, spans):
        future_grid_count -= len(points)
        # Keep enough budget to sample all later reachable sections.
        sample = _sample(points, local_zone or local_start.tzinfo, lat, lon, profile, dut1_seconds,
                         traditional_scheme, other_body, max_evaluations=remaining - future_grid_count)
        remaining -= sample['method']['evaluation_count']
        anchor = sample['candidates'][0]['fields']
        if first_fields is None:
            first_fields = anchor
        changed.update(sample['observed_changing_fields'])
        changed.update(key for key in anchor if anchor[key] != first_fields[key])
        sections.append(dict(start_utc=points[0].isoformat(), end_exclusive_utc=(points[-1] + TICK).isoformat(),
                             start_local=local_start.isoformat(), end_exclusive_local=local_end.isoformat(),
                             sample=sample))
    return dict(
        version=version, status='sampled_conditional',
        input=dict(birth_date=day.isoformat(), **birth_scope,
                   timezone=zone, utc_offset_hours=utc_offset, lat=lat, lon=lon,
                   profile=profile, dut1_seconds=dut1_seconds, traditional_scheme=traditional_scheme,
                   traditional_other_body=other_body if traditional_scheme else None),
        timezone_source=timezone_provenance(zone),
        interval_semantics=semantics,
        coverage_complete=False, stable_fields={}, uncertain_birth_rule_status='withheld',
        method=dict(max_evaluations=MAX_EVALUATIONS, evaluation_count=MAX_EVALUATIONS - remaining,
                    budget_exhausted=any(section['sample']['method']['budget_exhausted'] for section in sections)),
        observed_changing_fields=sorted(changed), sampled_sections=sections,
    )


SUMMARY_MAX_CHANGES = 6
RULE_FIELDS = ('rule_output', 'traditional_rule_output')
SUMMARY_PRIORITIES = (
    *RULE_FIELDS, 'ascendant.defined', 'day_night', 'ascendant.mansion', 'ming_gong',
    'ascendant.palace',
) + tuple('bodies.' + body + '.' + field for body in engine.LUMINARIES for field in ('mansion', 'palace'))


def _label(key):
    labels = {'day_night': '昼夜划分', 'ascendant.defined': '上升交点能否计算',
              'ascendant.mansion': '命度所属宿', 'ascendant.palace': '命度所在宫',
              'ming_gong': '传统立命宫', 'rule_output': '条件规则解释', 'traditional_rule_output': '乾元宫主条件参照'}
    if key in labels:
        return labels[key]
    if key.startswith('bodies.'):
        _, body, field = key.split('.')
        return body + {'mansion': '所在宿', 'palace': '所在宫'}.get(field, '的分类')
    return '其他分类或靠界筛查'


def _value(key, value):
    if key == 'ascendant.defined':
        return '可计算' if value else '未定义（不补造命度）'
    if key == 'ming_gong':
        return value.get('zhi', '未提供') + '宫' if value else '未提供'
    if key in RULE_FIELDS:
        if value['status'] == 'withheld':
            return '暂缓解释（' + value['reason'].rstrip('。') + '）'
        partial = next((claim['reason'] for claim in value['claims'] if claim['status'] == 'withheld'), None)
        return '有条件解释' if partial is None else '部分可解释（' + partial.rstrip('。') + '）'
    return str(value) if value is not None else '未定义'


def _conditional_claim_text(rule_output):
    """Use only the structure already interpreted at the sampled instant."""
    details = {}
    for claim in rule_output['claims']:
        if claim['status'] != 'conditional':
            continue
        rule_id = claim['rule_id']
        if rule_id == 'QZ01':
            facts = claim['facts']
            details[rule_id] = '%s宿取%s为度主' % (facts['mansion'], facts['reference_element'])
        elif rule_id == 'QZ02':
            facts = claim['facts']
            details[rule_id] = '%s宫主折%s，对度主为%s' % (
                facts['zhi'], facts['palace_lord_element'], claim['relation_to_degree_lord'])
        elif rule_id == 'QZT04':
            calculation = claim['calculation']
            details[rule_id] = '%s曜相对%s宫主%s为%s' % (
                claim['other_body'], calculation['zhi'], calculation['reference_element'],
                calculation['relation'])
    return details


def _change_text(key, a, b, separator):
    before, after = (row['fields'][key] for row in (a, b))
    left, right = _value(key, before), _value(key, after)
    change = left + separator + right
    if key in RULE_FIELDS:
        early, late = (_conditional_claim_text(value) for value in (before, after))
        details = []
        for rule_id in dict.fromkeys((*early, *late)):
            first, last = early.get(rule_id), late.get(rule_id)
            if first == last:
                comparison = '两点均' + first
            elif first is not None and last is not None:
                comparison = first + separator + last
            else:
                comparison = ('前一见证 ' + first) if first is not None else ('后一见证 ' + last)
            details.append(rule_id + ' ' + comparison)
        if details:
            change += '（' + '。'.join(details) + '）'
        elif left == right:
            change += '（具体条件或解释内容不同）'
    return change


def _shared_observation_line(fields, changed):
    """Name the main classifications that agree across the actual samples."""
    observations = [
        _label(key) + '为' + _value(key, fields[key])
        for key in ('day_night', 'ascendant.mansion', 'ming_gong')
        if key not in changed and fields.get(key) is not None
    ]
    if observations:
        return '- 已采样时点均观测到' + '、'.join(observations) + '。'
    return None


def _shared_rule_observations(fields, changed):
    for key in RULE_FIELDS:
        if key in fields and key not in changed:
            rule_output = fields[key]
            details = _conditional_claim_text(rule_output)
            status, claims = _rule_availability(rule_output)
            if details or status == 'withheld' or 'withheld' in claims.values():
                value = _value(key, rule_output)
                if value == '有条件解释':
                    line = '- 实测见证的共同结果（%s）' % _label(key)
                else:
                    line = '- 已采样时点的%s均为%s' % (_label(key), value)
                if details:
                    line += '。' + '。'.join(rule_id + ' ' + description for rule_id, description in details.items())
                yield line + '。'


def _bracket_line(key, bracket, by_time):
    a, b = (by_time[bracket[k]] for k in ('left_utc', 'right_utc'))
    low = datetime.fromisoformat(bracket['left_utc']).replace(second=0, microsecond=0)
    high = datetime.fromisoformat(bracket['right_utc'])
    rounded_high = high.replace(second=0, microsecond=0)
    if rounded_high < high:
        rounded_high += timedelta(minutes=1)
    return '- %s：%s；一次观察差异位于 UTC %s 至 %s 范围内。' % (
        _label(key), _change_text(key, a, b, ' → '),
        low.strftime('%Y-%m-%d %H:%M'), rounded_high.strftime('%Y-%m-%d %H:%M'))


def _rule_availability(fields):
    return fields['status'], {claim['rule_id']: claim['status'] for claim in fields['claims']}


def _changes_rule_availability(key, witnesses):
    before, after = (_rule_availability(row['fields'][key]) for row in witnesses)
    return before != after


def _summary_witness(key, adjacent, boundaries, by_time):
    pairs = [pair for pair in adjacent if pair[0]['fields'][key] != pair[1]['fields'][key]]
    brackets = [row for row in boundaries if key in row['changed_fields']]
    if key in RULE_FIELDS:
        for pair in pairs:
            if _changes_rule_availability(key, pair):
                return pair, None
        for bracket in brackets:
            if _changes_rule_availability(key, (by_time[bracket['left_utc']], by_time[bracket['right_utc']])):
                return None, bracket
    return (pairs[0], None) if pairs else (None, next(iter(brackets), None))


def _later_rule_observation(key, before, after, candidates):
    """Keep a later usable witness when the displayed pair shows withdrawal."""
    if key not in RULE_FIELDS:
        return None
    lost = (_conditional_claim_text(before['fields'][key]).keys() -
            _conditional_claim_text(after['fields'][key]).keys())
    if not lost:
        return None
    for row in candidates:
        if row['witness_utc'] <= after['witness_utc']:
            continue
        available = _conditional_claim_text(row['fields'][key])
        restored = [rule_id + ' ' + text for rule_id, text in available.items() if rule_id in lost]
        if restored:
            return '- %s在后续已计算见证 UTC %s 又可作条件解释。%s。' % (
                _label(key), row['witness_utc'], '。'.join(restored))
    return None


def _has_clock_disambiguation(candidates, interval, local_timezone):
    offsets = set()
    for row in candidates:
        clock = datetime.fromisoformat(row['witness_civil'])
        offsets.add(clock.utcoffset())
        if len(offsets) > 1 or (local_timezone is None and row['fold']):
            return True
        if local_timezone is not None:
            instant = datetime.fromisoformat(row['witness_utc'])
            local = instant.astimezone(local_timezone)
            alternate = local.replace(fold=1 - local.fold)
            # A second offset only counts if both occurrences are reachable.
            if alternate.utcoffset() != local.utcoffset() and local.astimezone(timezone.utc) == instant:
                other = alternate.astimezone(timezone.utc).astimezone(local_timezone)
                if other.fold == alternate.fold and other.replace(tzinfo=None) == local.replace(tzinfo=None):
                    return True
    if local_timezone is None or isinstance(local_timezone, timezone):
        return False
    # Civil offsets can change between retained sky samples. Include the
    # final instant because this comparison uses closed UTC bounds.
    start, end = (datetime.fromisoformat(interval[key]) for key in ('start_utc', 'end_utc'))
    return len(fixed_offset_spans(start, end + TICK, local_timezone)) > 1


def render(result, full_evidence=False, *, local_timezone=None):
    """Bounded plain-language overview; complete evidence is explicitly opt-in.

    Selection is presentation only. JSON candidates and observed changes remain
    unchanged; a displayed bracket never asserts that all changes were found.
    """
    by_time = {row['witness_utc']: row for row in result['candidates']}
    interval = result['interval']
    first, last = (by_time[interval[k]] for k in ('start_utc', 'end_utc'))
    lines = ['## 七政时间敏感性（有限采样，不是完整枚举）',
        '- 比较时段（输入时区，含端点）：' + first['witness_civil'] + ' 至 ' + last['witness_civil'] + '。',
        '- 共实际计算 %d 个时刻，找到 %d 组前后不同的结果。以下最多列 %d 项重要差异（时间范围向外取整到分钟）。' %
        (result['method']['evaluation_count'], len(result['boundaries']), SUMMARY_MAX_CHANGES)]
    changed = set(result['observed_changing_fields'])
    selected = [key for key in SUMMARY_PRIORITIES if key in changed][:SUMMARY_MAX_CHANGES]
    for key in selected:
        _, bracket = _summary_witness(key, (), result['boundaries'], by_time)
        if bracket is not None:
            lines.append(_bracket_line(key, bracket, by_time))
            before, after = (by_time[bracket[side]] for side in ('left_utc', 'right_utc'))
            later = _later_rule_observation(key, before, after, result['candidates'])
            if later:
                lines.append(later)
    if not changed:
        lines.append('- 本次采样未观察到分类变化，但不能据此说整个时段稳定。')
    elif not selected:
        lines.append('- 观察到其他分类或靠界筛查变化；详细字段见完整证据。')
    else:
        lines.append('- 每项列一处主要差异。暂缓后另有可解释见证时列一处后续点，其他过界请查看完整证据。')
    common = _shared_observation_line(first['fields'], changed)
    if common:
        lines.append(common)
    lines.extend(_shared_rule_observations(first['fields'], changed))
    if any(row['chart'].get('ming_du') is None for row in result['candidates']):
        lines.append('- 部分或全部见证的上升交点未定义；这些时刻不补造命度或相关规则。')
    if result['high_latitude_caution']:
        lines.append('- 高纬度可能出现上升交点退化或跳变，采样尤其不能保证找全。')
    if _has_clock_disambiguation(result['candidates'], interval, local_timezone):
        lines.append('- 时段涉及时区偏移变化或重复民用时刻；以 UTC 区分瞬间，不自动加入另一个出生时刻选择。')
        lines.append('- 本次比较的 UTC 时段（含端点）：' + interval['start_utc'] + ' 至 ' + interval['end_utc'] + '。')
    if result['method']['budget_exhausted']:
        lines.append('- 已达到计算上限；部分差异包围未细化，详见完整证据。')
    if result['calculation_profile'] == 'legacy-v1':
        lines.append('- 当前为旧版错误模型复现，比较结果不代表模型已获验证。')
    lines += ['- 可能漏掉短暂变化、多次过界或相切；未观察到不等于稳定，边界时刻也不是实际天文精度。',
              '- 宿界尚未校准；采样候选的解释仅在各自条件下成立，不能代替整段出生时间的确定结论。',
              '- 紫气为未独立校准的模型点；物理星历、均时差与真太阳时误差不因本比较消除。',
              '- 完整证据：使用 --format json，或在文本模式加 --qizheng-sensitivity-evidence。']
    if full_evidence:
        lines += ['### 完整七政敏感性证据', '```json',
                  json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), '```']
    return lines


def render_civil_birth(result):
    """Summarize actual witnesses, keeping cross-section differences distinct."""
    sections = result['sampled_sections']
    samples = [section['sample'] for section in sections]
    by_time = {row['witness_utc']: row for sample in samples for row in sample['candidates']}
    adjacent = [(earlier['candidates'][-1], later['candidates'][0])
                for earlier, later in zip(samples, samples[1:])]
    boundaries = [row for sample in samples for row in sample['boundaries']]
    lines = ['## 七政出生时间采样（有限见证）',
             '- 出生时刻尚未唯一确定，整段出生规则暂缓。',
             '- 共计算 %d 个时刻，可达时段 %d 段。各段起点包含，终点排除。' %
             (result['method']['evaluation_count'], len(sections))]
    for section in sections:
        lines.append('- 民用 %s 至 %s。对应 UTC %s 至 %s。' % (
            section['start_local'], section['end_exclusive_local'],
            section['start_utc'], section['end_exclusive_utc']))
    changed = set(result['observed_changing_fields'])
    selected = [key for key in SUMMARY_PRIORITIES if key in changed][:SUMMARY_MAX_CHANGES]
    for key in selected:
        witnesses, bracket = _summary_witness(key, adjacent, boundaries, by_time)
        if witnesses is not None:
            a, b = witnesses
            lines.append('- %s分别为%s。两段的实际见证为 UTC %s 和 %s，仅说明两点有别。' % (
                _label(key), _change_text(key, a, b, '／'), a['witness_utc'], b['witness_utc']))
        elif bracket is not None:
            lines.append(_bracket_line(key, bracket, by_time))
            witnesses = tuple(by_time[bracket[side]] for side in ('left_utc', 'right_utc'))
        if witnesses is not None:
            later = _later_rule_observation(key, *witnesses, by_time.values())
            if later:
                lines.append(later)
    if not changed:
        lines.append('- 本次采样未观察到分类变化，整个出生范围仍未穷尽。')
    elif not selected:
        lines.append('- 观察到其他分类或靠界筛查变化，详见完整证据。')
    first_fields = samples[0]['candidates'][0]['fields']
    common = _shared_observation_line(first_fields, changed)
    if common:
        lines.append(common)
    lines.extend(_shared_rule_observations(first_fields, changed))
    if any(row['chart']['ming_du'] is None for row in by_time.values()):
        lines.append('- 部分或全部见证的上升交点未定义，相关规则暂缓。')
    if any(sample['high_latitude_caution'] for sample in samples):
        lines.append('- 高纬上升交点可能退化或跳变，有限采样可能遗漏这些变化。')
    if result['method']['budget_exhausted']:
        lines.append('- 已达到计算上限，部分差异包围未细化。')
    if result['input']['profile'] == 'legacy-v1':
        lines.append('- 当前为已知错误的旧版模型复现。')
    lines += ['- 每项列一处主要差异。暂缓后另有可解释见证时列一处后续点。段内包围向外取整到分钟，宿界及近似星历的误差仍在。',
              '- 采样可能漏掉变化。使用 --format json 读取完整见证、规则条件和未覆盖范围。']
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description='按实际可达的民用出生时辰或钟面区间采样七政')
    parser.add_argument('--birth-date', required=True, type=parse_birth_date)
    parser.add_argument('--start', help='出生钟面起点 HH:MM，包含')
    parser.add_argument('--end', help='出生钟面终点 HH:MM，不包含')
    parser.add_argument('--shichen', help='只确认原民用出生时辰，分钟未知')
    parser.add_argument('--lat', required=True, type=float)
    parser.add_argument('--lon', required=True, type=float)
    zone = parser.add_mutually_exclusive_group(required=True)
    zone.add_argument('--timezone')
    zone.add_argument('--utc-offset', type=float)
    parser.add_argument('--qizheng-profile', choices=('physical-v2', 'legacy-v1'), default='physical-v2')
    parser.add_argument('--dut1-seconds', type=float, default=0.0)
    parser.add_argument('--qizheng-tradition', choices=(tradition.SCHEME,))
    parser.add_argument('--qizheng-other-body', choices=tradition.BODIES, default='金')
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    args = parser.parse_args(argv)
    try:
        result = _compare_civil_birth(
            args.birth_date, args.lat, args.lon, start=args.start, end=args.end, shichen=args.shichen,
            zone=args.timezone, utc_offset=args.utc_offset, profile=args.qizheng_profile,
            dut1_seconds=args.dut1_seconds, traditional_scheme=args.qizheng_tradition, other_body=args.qizheng_other_body,
        )
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    if args.format == 'text':
        print('\n'.join(render_civil_birth(result)))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
