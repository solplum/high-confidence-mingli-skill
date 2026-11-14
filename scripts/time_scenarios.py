"""Bounded time resolution and discrete scenario enumeration, not predictions.

ZoneInfo requires Python 3.9+ only when an IANA zone is requested.
TZif transitions are integer POSIX seconds (RFC 8536); inspect each second
within the deliberately small interval, not coarse sampling of chart outputs.
"""
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
import math
import re

import pai_pan_bazi as bazi
import pai_pan_qizheng as qz

UTC = timezone.utc
TICK = timedelta(microseconds=1)
MAX_UNCERTAINTY_MINUTES = 120
MIN_YEAR, MAX_YEAR = 1901, 2099
QUERY_SECOND_FRACTION = re.compile(r'(:[0-5][0-9])[.,]([0-9]{1,6})(?=[+-]|$)')
QUERY_FRACTIONAL_OFFSET = re.compile(
    r'([+-])([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])\.([0-9]{6})$'
)


class UnsupportedUtcInterval(ValueError):
    """The optional comparison does not support the full UTC interval."""


def parse_birth_date(value):
    """Parse the original numeric birth date, including unpadded fields."""
    if not isinstance(value, str) or value.count('-') != 2:
        raise ValueError('出生日期需要 YYYY-MM-DD')
    return date(*(int(part) for part in value.split('-')))


def iana_zone(zone):
    """Load a region using the same host TZif source as birth resolution."""
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:
        raise ValueError("IANA 时区需要 Python 3.9+ 与系统时区数据库") from exc
    try:
        return ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("未知或不可用 IANA 时区：" + zone) from exc


def iana_query_zone(zone):
    """Resolve a range query and bind exact checkpoint hints to its clock."""
    tz = iana_zone(zone)
    from tzif_transitions import bind_query_zone
    return bind_query_zone(tz)


def fixed_utc_offset(hours):
    """Resolve the documented whole-minute fixed offset from numeric hours."""
    invalid = "固定 UTC 偏移须在 -14 至 +14 小时内，精确到整分钟"
    if type(hours) not in (int, float) or not -14 <= hours <= 14:
        raise ValueError(invalid)
    minutes = hours * 60
    whole_minutes = round(minutes)
    # Float hours can put an exact minute on either side of its integer.
    if not math.isclose(minutes, whole_minutes, rel_tol=0, abs_tol=1e-12):
        raise ValueError(invalid)
    return timezone(timedelta(minutes=whole_minutes))


def resolve_civil(local, offset=8, zone=None, fold=None):
    if local.tzinfo is not None:
        raise ValueError("出生民用钟面应不带时区")
    if zone is None:
        if fold is not None:
            raise ValueError("--fold 仅用于 --timezone")
        return local.replace(tzinfo=fixed_utc_offset(offset))
    return _resolve_regional_clock(local, iana_zone(zone), fold)


def _resolve_regional_clock(local, tz, fold, *, clock_label="出生记录"):
    candidates = {}
    for f in (0, 1):
        aware = local.replace(tzinfo=tz, fold=f)
        back = aware.astimezone(UTC).astimezone(tz)
        if back.replace(tzinfo=None) == local and back.fold == f:
            candidates[f] = aware
    if not candidates:
        raise ValueError(f"此民用时间不存在（时区跳时 gap）；请核实{clock_label}，不自动平移")
    if len(candidates) > 1 and fold is None:
        raise ValueError("此民用时间重复（fold）；请明确 --fold 0（较早）或 1（较晚）")
    if fold is not None and fold not in candidates:
        raise ValueError("所选 --fold 不适用于此民用时间")
    return candidates[fold if fold is not None else 0]


def parse_query_point(value):
    """Preserve the physical query instant across supported Python versions."""
    text = value[:-1] + '+00:00' if value.endswith('Z') else value
    # Older Python accepts only three or six fractional digits. Some
    # versions also discard nonzero fractional offsets smaller than a second.
    text = QUERY_SECOND_FRACTION.sub(lambda part: part[1] + '.' + part[2].ljust(6, '0'), text)
    offset = QUERY_FRACTIONAL_OFFSET.search(text)
    if offset is None or offset.start() <= 10:
        return datetime.fromisoformat(text)
    clock = datetime.fromisoformat(text[:offset.start()])
    if clock.utcoffset() is not None:
        raise ValueError('查询钟面只能包含一个 UTC 偏移')
    hours, minutes, seconds, microseconds = map(int, offset.groups()[1:])
    delta = timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)
    return clock.replace(tzinfo=timezone(delta if offset[1] == '+' else -delta))


def resolve_query_endpoint(value, zone, tz, fold, label):
    """Resolve a local query endpoint or verify its explicit offset."""
    if value.utcoffset() is None:
        try:
            return _resolve_regional_clock(value, tz, fold, clock_label="查询钟面")
        except ValueError as exc:
            raise ValueError(f'{label}：' + str(exc).replace('--fold', label + '-fold')) from exc
    if fold is not None:
        raise ValueError(f'{label} 已有明确偏移，不能另传 {label}-fold')
    local = value.astimezone(tz)
    if local.replace(tzinfo=None) != value.replace(tzinfo=None) or local.utcoffset() != value.utcoffset():
        raise ValueError(f'{label} 的钟面或偏移与指定 IANA 时区不符')
    return local


def _utc_seconds_inside(start, end):
    second = timedelta(seconds=1)
    point = start.replace(microsecond=0) + second
    while point < end:
        yield point
        point += second


def fixed_offset_spans(start, end, tz):
    """Split an already resolved, half-open instant range on TZif offsets."""
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    left = start
    active_offset = left.astimezone(tz).utcoffset()
    spans = []
    checkpoints = getattr(tz, 'offset_checkpoints', _utc_seconds_inside)
    for point in checkpoints(start, end):
        offset = point.astimezone(tz).utcoffset()
        if offset != active_offset:
            fixed = timezone(active_offset)
            spans.append((left.astimezone(fixed), point.astimezone(fixed)))
            left = point
            active_offset = offset
    fixed = timezone(active_offset)
    spans.append((left.astimezone(fixed), end.astimezone(fixed)))
    return spans


def civil_date_range_spans(start_date, end_date, utc_offset=None, zone=None, *, resolved_zone=None):
    """Return half-open, fixed-offset spans whose local dates are in the range."""
    if start_date >= end_date:
        raise ValueError("查询起点日期须早于终点日期")
    midnight = datetime.combine(start_date, datetime.min.time())
    end_midnight = datetime.combine(end_date, datetime.min.time())
    if utc_offset is not None and zone is not None:
        raise ValueError("固定 UTC 偏移与 IANA 时区互斥")
    if zone is None:
        fixed = fixed_utc_offset(8 if utc_offset is None else utc_offset)
        return [(midnight.replace(tzinfo=fixed), end_midnight.replace(tzinfo=fixed))]
    tz = resolved_zone if resolved_zone is not None else iana_zone(zone)
    scan_start = midnight.replace(tzinfo=UTC) - timedelta(days=1)
    scan_end = end_midnight.replace(tzinfo=UTC) + timedelta(days=1)
    spans = []
    for left, right in fixed_offset_spans(scan_start, scan_end, tz):
        begin = max(left, midnight.replace(tzinfo=left.tzinfo))
        end = min(right, end_midnight.replace(tzinfo=left.tzinfo))
        if begin < end:
            spans.append((begin, end))
    return spans


def civil_date_spans(day, utc_offset=None, zone=None):
    """Return the reachable civil date as half-open, fixed-offset spans."""
    spans = civil_date_range_spans(day, day + timedelta(days=1), utc_offset, zone)
    if not spans:
        raise ValueError("该地区的所给民用日期无可达出生时刻")
    return spans


def parse_civil_clock_band(start_text, end_text):
    """Parse the bounds of a confirmed, narrower-than-day civil clock band."""
    def clock_minutes(text):
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', text):
            raise ValueError('出生钟面区间须为 HH:MM，24:00 仅可作终点')
        hour, minute = map(int, text.split(':'))
        return 60 * hour + minute

    start = clock_minutes(start_text)
    end = 1440 if end_text == '24:00' else clock_minutes(end_text)
    if start >= end:
        raise ValueError('须提供同一民用日期内已确认的出生钟面区间，开始须早于结束')
    if (start, end) == (0, 1440):
        raise ValueError('全天范围未缩小出生钟面，继续按时辰未知处理')
    return start, end


def civil_shichen_hours(index):
    """Return civil-clock hour bounds for a discrete branch on one date."""
    return ((0, 1), (23, 24)) if index == 0 else ((2 * index - 1, 2 * index + 1),)


def civil_clock_band_shichen_spans(day, start_minutes, end_minutes, *, utc_offset=None, zone=None):
    """Partition the reachable clock band by UTC offset and civil branch."""
    hours = sorted((start, end, index) for index in range(len(bazi.ZHI_LIST))
                   for start, end in civil_shichen_hours(index))
    spans = []
    for left, right in civil_date_spans(day, utc_offset=utc_offset, zone=zone):
        midnight = datetime.combine(day, datetime.min.time(), tzinfo=left.tzinfo)
        band_start = max(left, midnight + timedelta(minutes=start_minutes))
        band_end = min(right, midnight + timedelta(minutes=end_minutes))
        for start_hour, end_hour, index in hours:
            start = max(band_start, midnight + timedelta(hours=start_hour))
            end = min(band_end, midnight + timedelta(hours=end_hour))
            if start < end:
                spans.append((start, end, index))
    if not spans:
        raise ValueError('所给出生钟面区间无可达时刻')
    return spans


def civil_shichen_spans(day, shichen, utc_offset=None, zone=None):
    """Select the reachable parts of a branch on one confirmed civil date."""
    if shichen not in bazi.ZHI_LIST:
        raise ValueError("时辰须为子丑寅卯辰巳午未申酉戌亥之一")
    index = bazi.ZHI_LIST.index(shichen)
    hours = civil_shichen_hours(index)
    spans = []
    for left, right in civil_date_spans(day, utc_offset, zone):
        midnight = datetime.combine(day, datetime.min.time(), tzinfo=left.tzinfo)
        for start_hour, end_hour in hours:
            begin = max(left, midnight + timedelta(hours=start_hour))
            end = min(right, midnight + timedelta(hours=end_hour))
            if begin < end:
                spans.append((begin, end))
    if not spans:
        raise ValueError("所给民用时辰无可达出生时刻")
    return spans


def timezone_provenance(zone, *, resolved_zone=None):
    """Hash the host TZif source when readable; never claim data is bundled/pinned."""
    if zone is None:
        return {"kind": "fixed_offset", "tzif_sha256": None}
    from tzif_transitions import read_tzif, source_provenance
    if resolved_zone is not None:
        bound = getattr(resolved_zone, 'tzif_source', None)
        return dict(bound) if bound is not None else source_provenance(zone, None)
    # The caller has already validated the name through ZoneInfo.
    return source_provenance(zone, read_tzif(zone))


def check_timezone_source(source, zone):
    """Check saved source identity without requiring identical TZif versions."""
    if (not isinstance(source, Mapping) or ('zone' in source and source['zone'] != zone) or
            (source.get('kind') == 'fixed_offset') != (zone is None)):
        raise ValueError('保存的时区来源与原民用时区不一致')


def solar_clock(civil, lon, eot_minutes):
    """Naive solar clock label, NOT a timezone-aware physical instant."""
    if civil.utcoffset() is None:
        raise ValueError("太阳钟面转换需要明确 UTC 偏移")
    if not math.isfinite(lon) or not -180 <= lon <= 180 or not math.isfinite(eot_minutes):
        raise ValueError("经度或均时差无效")
    return civil.astimezone(UTC).replace(tzinfo=None) + timedelta(minutes=lon * 4 + eot_minutes)


def _check_dut1(dut1_seconds):
    if type(dut1_seconds) not in (int, float) or not -0.9 <= dut1_seconds <= 0.9:
        raise ValueError('出生DUT1与真太阳时原计算口径冲突')


def snapshot_dut1_seconds(inputs, qizheng):
    """Read the original DUT1, falling back to the saved Qizheng horizon."""
    qizheng = qizheng if isinstance(qizheng, dict) else {}
    horizon = qizheng.get('horizon_contract')
    horizon = horizon if isinstance(horizon, dict) else {}
    if 'dut1_seconds' not in inputs and 'dut1_seconds' not in horizon:
        return None
    dut1_seconds = inputs.get('dut1_seconds', horizon.get('dut1_seconds'))
    _check_dut1(dut1_seconds)
    profile = inputs.get('qizheng_profile', qizheng.get('calculation_profile'))
    if profile == 'legacy-v1' and dut1_seconds != 0:
        raise ValueError('出生DUT1与legacy-v1原计算口径冲突')
    return dut1_seconds


def _apparent_eot(instant, dut1_seconds):
    jd_ut = qz.jd_from_utc(instant.astimezone(UTC)) + dut1_seconds / 86400
    return qz.equation_of_time_minutes(jd_ut)


def snapshot_apparent_correction(civil, inputs, qizheng):
    """Use a recorded DUT1 and the native equation of time."""
    dut1_seconds = snapshot_dut1_seconds(inputs, qizheng)
    if dut1_seconds is None:
        return None
    if civil.utcoffset() is None:
        raise ValueError('真太阳时复算需要明确的出生UTC偏移')
    return _apparent_eot(civil, dut1_seconds)


def scenario_clock_at(instant, zone, basis, lon, *, dut1_seconds=0.0):
    """Apply the enumerator's chosen civil or solar clock at one UTC witness."""
    if basis == "civil":
        return instant.astimezone(zone).replace(tzinfo=None)
    eot = _apparent_eot(instant, dut1_seconds) if basis == "apparent-solar" else 0
    return solar_clock(instant, lon, eot)


def scenario_clock_boundaries(start, end, zone, basis, lon):
    """Find civil and mean clock cuts, also used as apparent-solar witness seeds."""
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    points = {start, end}
    # Read every TZif transition second. No chart-output sampling assumption.
    prior = start.astimezone(zone).utcoffset()
    offsets = {prior}
    t = start.replace(microsecond=0) + timedelta(seconds=1)
    while t <= end:
        current = t.astimezone(zone).utcoffset()
        offsets.add(current)
        if current != prior:
            points.add(t)
        prior = current
        t += timedelta(seconds=1)
    # Midnight changes Ziwei's solar date; odd hours change shichen, 23 changes
    # BaZi's day. Civil birth-year changes matter even for a solar chart clock.
    shifts = offsets if basis == "civil" else {timedelta(minutes=lon * 4)}
    for shift in shifts | offsets:
        day = (start.replace(tzinfo=None) + shift).date() - timedelta(days=1)
        last = (end.replace(tzinfo=None) + shift).date() + timedelta(days=1)
        while day <= last:
            for hour in (0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23):
                point = (datetime.combine(day, datetime.min.time()) + timedelta(hours=hour) - shift).replace(tzinfo=UTC)
                if start <= point <= end:
                    points.add(point)
            day += timedelta(days=1)
    return points


def dayun_age_segments(start, end, jie_points, sex, *, end_inclusive=True):
    """Split a bounded UTC range on the existing model's rounded-month changes."""
    stop = end + TICK if end_inclusive else end
    cuts = sorted({start, stop, *jie_points})
    segments = []
    for left, right in zip(cuts, cuts[1:]):
        birth = left.astimezone(bazi.BJ)
        _, year_gan, year_zhi, _ = bazi.resolve_year_pillar(birth)
        month_gan, month_zhi, _, _, prev_jie, next_jie = bazi.resolve_month_pillar(birth, bazi.GAN.index(year_gan))

        def rounded(point):
            return bazi.resolve_qiyun(point.astimezone(bazi.BJ), year_gan, prev_jie, next_jie, sex)

        first, last = rounded(left), rounded(right - TICK)
        # Between jie the reference term is fixed. Rounded thresholds are six
        # hours apart, longer than the entire allowed four-hour birth range.
        parts = [(left, right, first)]
        if first != last:
            low, high = left, right - TICK
            while high - low > TICK:
                mid = low + (high - low) // 2
                if rounded(mid) == first:
                    low = mid
                else:
                    high = mid
            parts = [(left, high, first), (high, right, last)]
        for begin, finish, (forward, years, months) in parts:
            age = years * 12 + months
            rows = bazi.build_dayun(month_gan, month_zhi, forward, years, months)
            record = dict(start_utc=begin.isoformat(),
                          end_utc=(end if finish == stop else finish).isoformat(),
                          end_inclusive=end_inclusive and finish == stop, start_age_months=age,
                          year_pillar=year_gan + year_zhi, month_pillar=month_gan + month_zhi,
                          forward=forward, age_windows=bazi.dayun_age_windows(rows, age, False)["windows"])
            segments.append((begin, finish, record, {}))
    return segments


def recorded_scenario_bounds(inputs, scenarios):
    """Read the bounds of a declared native birth-time enumeration."""
    if inputs.get('enumerate_scenarios') is not True or scenarios is None:
        return None
    if (not isinstance(scenarios, dict) or
            scenarios.get('scope') != 'bazi_four_pillars_and_ziwei_discrete_inputs_only' or
            scenarios.get('interval_semantics') != 'inclusive_elapsed_UTC_minutes_around_resolved_center'):
        return (None, None)
    points = []
    for field in ('start_utc', 'end_utc'):
        value = scenarios.get(field)
        try:
            point = parse_query_point(value) if isinstance(value, str) and len(value) > 10 else None
        except ValueError:
            point = None
        points.append(point)
    return tuple(points)


def check_recorded_scenario_bounds(inputs, bounds, instant, delta):
    """Check saved endpoints against the original resolved clock and error."""
    if bounds is None:
        return
    start, end = bounds
    if (any(point is None or point.utcoffset() is None for point in (start, end)) or
            instant - start != end - instant or start > instant):
        raise ValueError('出生误差枚举范围与原民用出生中心不一致')
    if 'uncertainty_minutes' not in inputs and start < end:
        raise ValueError('原出生误差分钟缺失，存档仍有非零枚举范围，请核对原出生误差')
    if (start, end) != (instant - delta, instant + delta):
        raise ValueError('出生误差枚举范围与原输入的误差分钟不一致')


def scenario_witnesses(scenarios):
    """The ordered candidate identity, clock, and coverage evidence."""
    keys = ('fields', 'witness_utc', 'chart_clock', 'intervals')
    try:
        return [tuple(row[key] for key in keys) for row in scenarios['variants']]
    except (KeyError, TypeError) as exc:
        raise ValueError('出生误差枚举缺少必要的见证字段') from exc


def enumerate_scenarios(civil, minutes, basis, lon, sex="男", now=None, *, dut1_seconds=0.0):
    """Civil/mean: discrete partition; apparent: non-exhaustive numeric witnesses.

    Interval is elapsed UTC time around an already resolved center, inclusive.
    Scope: four pillars, Ziwei calendar date/shichen/birth-year inputs only.
    Rounded qiyun ages use a separate physical-instant partition.
    """
    if not math.isfinite(minutes) or not 0 <= minutes <= MAX_UNCERTAINTY_MINUTES:
        raise ValueError("候选枚举误差须在 0 至 120 分钟之间")
    if basis not in ("civil", "mean-solar", "apparent-solar"):
        raise ValueError("未知时间口径")
    if basis == "apparent-solar":
        _check_dut1(dut1_seconds)
    if lon is None and basis != "civil":
        raise ValueError("太阳时候选枚举需要出生地经度")
    if lon is not None and (not math.isfinite(lon) or not -180 <= lon <= 180):
        raise ValueError("经度超出范围")
    if civil.utcoffset() is None:
        raise ValueError("候选枚举需要明确的出生瞬间")
    center = civil.astimezone(UTC)
    if not MIN_YEAR <= center.year <= MAX_YEAR:
        raise UnsupportedUtcInterval("候选枚举仅支持完整 UTC 区间落在 1901–2099 年内")
    start, end = center - timedelta(minutes=minutes), center + timedelta(minutes=minutes)
    if start.year < MIN_YEAR or end.year > MAX_YEAR:
        raise UnsupportedUtcInterval("候选枚举仅支持完整 UTC 区间落在 1901–2099 年内")
    tz = civil.tzinfo
    def clock(t):
        return scenario_clock_at(t, tz, basis, lon, dut1_seconds=dut1_seconds)
    points = scenario_clock_boundaries(start, end, tz, basis, lon)
    brackets = []
    if basis == "apparent-solar":
        # This numeric pass is explicitly NOT a coverage proof. Do not report
        # stable fields or exact interval attribution for this mode. Both
        # sides of each bracket are evaluated as real, reachable witnesses.
        day = clock(start).date() - timedelta(days=1)
        last = clock(end).date() + timedelta(days=1)
        while day <= last:
            for hour in (0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23):
                target = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
                if clock(start) <= target <= clock(end):
                    low, high = start, end
                    while (high - low).total_seconds() > .001:
                        mid = low + (high - low) / 2
                        if clock(mid) < target:
                            low = mid
                        else:
                            high = mid
                    points.update((low, high))
                    brackets.append({"clock_boundary": target.isoformat(),
                                     "low_utc": low.isoformat(), "high_utc": high.isoformat(),
                                     "max_width_seconds": .001})
            day += timedelta(days=1)
    jie_points = set()
    for year in range(start.year, end.year + 1):
        for event, _name, _zhi, _lon, _year in bazi.jie_events_around(year):
            point = event.astimezone(UTC)
            if start <= point <= end:
                jie_points.add(point)
    points.update(jie_points)
    ages = dayun_age_segments(start, end, jie_points, sex)
    numerical = basis == "apparent-solar"
    if numerical:
        points.update(begin for begin, _, _, _ in ages)
    variants = {}
    variant_ids = {}
    boundaries = sorted(points)
    for i, t in enumerate(boundaries):
        c = clock(t)
        result = bazi.compute(c.date(), c.hour, c.minute, sex=sex,
                              birth_instant=t, **({"now": now} if now else {}))
        fields = {"bazi." + key: list(value[:2]) for key, value in result["pillars"].items()}
        fields.update({"ziwei.solar_date": c.date().isoformat(),
                       "ziwei.shichen_index": ((c.hour + 1) // 2) % 12,
                       "ziwei.birth_year": t.astimezone(tz).year})
        key = repr(fields)
        segment = {"start_utc": t.isoformat(),
                   "end_utc": (boundaries[i + 1] if i + 1 < len(boundaries) else end).isoformat(),
                   "end_inclusive": i + 1 == len(boundaries)}
        if key not in variants:
            variant_ids[key] = "candidate-%d" % (len(variants) + 1)
            variants[key] = {"fields": fields, "witness_utc": t.isoformat(),
                             "chart_clock": c.isoformat(), "intervals": [],
                             "warnings": result["warnings"]}
        if not numerical:
            variants[key]["intervals"].append(segment)
        # Exact clock intervals can be joined by intersection. For apparent
        # solar time bind only chart inputs actually evaluated at this point.
        limit = t + TICK if numerical else (boundaries[i + 1] if i + 1 < len(boundaries) else end + TICK)
        for left, right, _, witnesses in ages:
            shared = max(left, t)
            if shared < min(right, limit):
                witnesses.setdefault(variant_ids[key], shared.isoformat())
    rows = list(variants.values())
    stable = {k: v for k, v in rows[0]["fields"].items()
              if all(row["fields"][k] == v for row in rows)}
    coverage = ("numerical_witnesses_not_exhaustive" if numerical else
                "complete_for_modeled_boundaries_not_astronomical_error")
    return {"scope": "bazi_four_pillars_and_ziwei_discrete_inputs_only",
            "coverage": coverage,
            "boundary_brackets": brackets,
            "numerical_tolerance_is_not_ephemeris_accuracy": True,
            "interval_semantics": "inclusive_elapsed_UTC_minutes_around_resolved_center",
            "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "caps": {"plus_minus_minutes": 120, "utc_years": [1901, 2099]},
            "stable_fields": {} if basis == "apparent-solar" else stable,
            "observed_constant_fields": stable if basis == "apparent-solar" else {},
            "changing_fields": [k for k in rows[0]["fields"] if k not in stable],
            "variants": rows,
            "excluded": ["qiyun", "dayun_ages", "qizheng", "full_ziwei_output",
                         "ephemeris_error", "alternative_late_zi_conventions"],
            "dayun_age_comparison": {
                "scope": "rounded_bazi_dayun_ages_at_physical_birth_instants",
                "coverage": "complete_for_rounded_model_not_ephemeris_error",
                "natal_candidate_coverage": coverage,
                "segments": [dict(record, birth_witnesses=[
                    dict(scenario_id=key, witness_utc=value) for key, value in witnesses.items()])
                    for _, _, record, witnesses in ages],
            }}
