"""Bounded time resolution and discrete scenario enumeration, not predictions.

ZoneInfo requires Python 3.9+ only when an IANA zone is requested.
TZif transitions are integer POSIX seconds (RFC 8536); inspect each second
within the deliberately small interval, not coarse sampling of chart outputs.
"""
from datetime import datetime, timedelta, timezone
import math
import hashlib
from pathlib import Path

import pai_pan_bazi as bazi
import pai_pan_qizheng as qz

UTC = timezone.utc
MAX_UNCERTAINTY_MINUTES = 120
MIN_YEAR, MAX_YEAR = 1901, 2099


def resolve_civil(local, offset=8, zone=None, fold=None):
    if local.tzinfo is not None:
        raise ValueError("出生民用钟面应不带时区")
    if zone is None:
        if fold is not None:
            raise ValueError("--fold 仅用于 --timezone")
        return local.replace(tzinfo=timezone(timedelta(hours=offset)))
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:
        raise ValueError("IANA 时区需要 Python 3.9+ 与系统时区数据库") from exc
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("未知或不可用 IANA 时区：" + zone) from exc
    candidates = {}
    for f in (0, 1):
        aware = local.replace(tzinfo=tz, fold=f)
        back = aware.astimezone(UTC).astimezone(tz)
        if back.replace(tzinfo=None) == local and back.fold == f:
            candidates[f] = aware
    if not candidates:
        raise ValueError("此民用时间不存在（时区跳时 gap）；请核实出生记录，不自动平移")
    if len(candidates) > 1 and fold is None:
        raise ValueError("此民用时间重复（fold）；请明确 --fold 0（较早）或 1（较晚）")
    if fold is not None and fold not in candidates:
        raise ValueError("所选 --fold 不适用于此民用时间")
    return candidates[fold if fold is not None else 0]


def timezone_provenance(zone):
    """Hash the host TZif source when readable; never claim data is bundled/pinned."""
    if zone is None:
        return {"kind": "fixed_offset", "tzif_sha256": None}
    from zoneinfo import TZPATH
    # resolve_civil has already validated this key through ZoneInfo.
    for root in TZPATH:
        source = Path(root) / zone
        if source.is_file():
            return {"kind": "host_iana_tzif", "zone": zone,
                    "tzif_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    try:
        import importlib.resources as resources
        package = "tzdata.zoneinfo." + ".".join(zone.split("/")[:-1])
        data = resources.read_binary(package.rstrip("."), zone.split("/")[-1])
        return {"kind": "tzdata_package", "zone": zone,
                "tzif_sha256": hashlib.sha256(data).hexdigest()}
    except (ImportError, FileNotFoundError, OSError):
        return {"kind": "unverified_iana_source", "zone": zone, "tzif_sha256": None}


def enumerate_scenarios(civil, minutes, basis, lon, sex="男", now=None):
    """Civil/mean: discrete partition; apparent: non-exhaustive numeric witnesses.

    Interval is elapsed UTC time around an already resolved center, inclusive.
    Scope: four pillars, Ziwei calendar date/shichen/birth-year inputs only.
    Planetary coordinates, qiyun and full Ziwei output are NOT enumerated.
    """
    if not math.isfinite(minutes) or not 0 <= minutes <= MAX_UNCERTAINTY_MINUTES:
        raise ValueError("候选枚举误差须在 0 至 120 分钟之间")
    if basis not in ("civil", "mean-solar", "apparent-solar"):
        raise ValueError("未知时间口径")
    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise ValueError("经度超出范围")
    if civil.utcoffset() is None:
        raise ValueError("候选枚举需要明确的出生瞬间")
    center = civil.astimezone(UTC)
    start, end = center - timedelta(minutes=minutes), center + timedelta(minutes=minutes)
    if start.year < MIN_YEAR or end.year > MAX_YEAR:
        raise ValueError("候选枚举仅支持完整 UTC 区间落在 1901–2099 年内")
    tz = civil.tzinfo
    def clock(t):
        if basis == "civil":
            return t.astimezone(tz).replace(tzinfo=None)
        eot = qz.equation_of_time_minutes(qz.jd_from_utc(t)) if basis == "apparent-solar" else 0
        return t.replace(tzinfo=None) + timedelta(minutes=lon * 4 + eot)
    points = {start, end}
    # Read every TZif transition second. No chart-output sampling assumption.
    offsets = {start.astimezone(tz).utcoffset()}
    t = start.replace(microsecond=0) + timedelta(seconds=1)
    prior = start.astimezone(tz).utcoffset()
    while t <= end:
        current = t.astimezone(tz).utcoffset()
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
    for year in range(start.year, end.year + 1):
        for event, _name, _zhi, _lon, _year in bazi.jie_events_around(year):
            point = event.astimezone(UTC)
            if start <= point <= end:
                points.add(point)
    variants = {}
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
            variants[key] = {"fields": fields, "witness_utc": t.isoformat(),
                             "chart_clock": c.isoformat(), "intervals": [],
                             "warnings": result["warnings"]}
        if basis != "apparent-solar":
            variants[key]["intervals"].append(segment)
    rows = list(variants.values())
    stable = {k: v for k, v in rows[0]["fields"].items()
              if all(row["fields"][k] == v for row in rows)}
    return {"scope": "bazi_four_pillars_and_ziwei_discrete_inputs_only",
            "coverage": ("numerical_witnesses_not_exhaustive" if basis == "apparent-solar" else
                         "complete_for_modeled_boundaries_not_astronomical_error"),
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
                         "ephemeris_error", "alternative_late_zi_conventions"]}
