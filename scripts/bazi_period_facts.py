#!/usr/bin/env python3
"""Partition a civil query into native BaZi fact windows."""

import argparse
from datetime import datetime, timedelta, timezone
import json

import pai_pan_bazi as engine
from time_scenarios import (
    civil_date_range_spans, fixed_offset_spans, iana_query_zone, parse_query_point,
    resolve_query_endpoint, timezone_provenance,
)


LAYERS = ('year', 'month', 'day')


def _fact(layer, stem, branch, window):
    return dict(layer=layer, pillar=stem + branch,
                source='scripts/pai_pan_bazi.py:resolve_' + layer + '_pillar', window=window)


def _segment(start, end, layer):
    instant_bj = start.astimezone(engine.BJ)
    window = '[' + start.isoformat() + ', ' + end.isoformat() + ')'
    _, year_stem, year_branch, _ = engine.resolve_year_pillar(instant_bj)
    facts = [_fact('year', year_stem, year_branch, window)]
    if layer in ('month', 'day'):
        stem, branch, *_ = engine.resolve_month_pillar(instant_bj, engine.GAN.index(year_stem))
        facts.append(_fact('month', stem, branch, window))
    if layer == 'day':
        stem, branch, *_ = engine.resolve_day_pillar(start.date(), start.hour, start.minute)
        facts.append(_fact('day', stem, branch, window))
    return dict(start=start.isoformat(), end=end.isoformat(), facts=facts)


def period_facts(start, end, layer):
    """Enumerate half-open windows for the caller's explicitly fixed civil clock."""
    if layer not in LAYERS:
        raise ValueError('layer 须为 year、month 或 day')
    if not all(isinstance(point, datetime) and isinstance(point.tzinfo, timezone)
               for point in (start, end)):
        raise ValueError('查询起止须明确带固定 UTC 偏移')
    if start.utcoffset() != end.utcoffset():
        raise ValueError('查询起止须采用同一固定 UTC 偏移，变偏移区间应另行解析')
    if start >= end:
        raise ValueError('查询起点须早于终点')

    start_bj, end_bj = (point.astimezone(engine.BJ) for point in (start, end))
    # Adjacent calls can return the same jie. Use the model instant once, then
    # display it on the query clock without changing its physical instant.
    jie = {event for year in range(start_bj.year, end_bj.year + 1)
           for event in engine.jie_events_around(year)
           if start_bj < event[0] < end_bj and (layer != 'year' or event[3] == 315)}
    cuts = {}
    for instant, name, _, _, _ in sorted(jie):
        cut = instant.astimezone(start.tzinfo)
        cuts[cut] = [dict(kind='jie', name=name, time_bj=instant.isoformat())]
    if layer == 'day':
        first = start.replace(hour=23, minute=0, second=0, microsecond=0)
        for i in range((end.date() - start.date()).days + 1):
            cut = first + timedelta(days=i)
            if start < cut < end:
                cuts.setdefault(cut, []).append(dict(kind='civil_23h_day_boundary'))

    points = [start, *sorted(cuts), end]
    return dict(
        layer=layer, time_basis='civil_fixed_offset', interval_semantics='start_inclusive_end_exclusive',
        start=start.isoformat(), end=end.isoformat(),
        coverage='complete_for_requested_layers_under_existing_engine_boundaries',
        boundaries=[dict(at=cut.isoformat(), reasons=cuts[cut]) for cut in points[1:-1]],
        segments=[_segment(left, right, layer) for left, right in zip(points, points[1:])],
        limitations=[
            '仅输出所选时间层及其上层干支事实。大运及交运窗口、时柱与解读另核。',
            '年、月使用原引擎按真实瞬间计算的立春及十二节。节气时标及临界误差沿用原引擎限制。',
            '日柱使用查询民用钟面的 23:00 换日。固定偏移须覆盖整段，工具不识别地区夏令时或太阳钟面。',
        ],
    )


def _regional_facts_from_spans(spans, layer, zone, tz):
    segments, boundaries = [], []
    previous_right = None
    for left, right in spans:
        piece = period_facts(left, right, layer)
        if previous_right is not None:
            kind = ('iana_utc_offset_change' if previous_right == left else 'civil_date_membership_gap')
            boundaries.append(dict(at=piece['start'], reasons=[
                dict(kind=kind, previous_clock=segments[-1]['end']),
            ]))
        boundaries.extend(piece['boundaries'])
        segments.extend(piece['segments'])
        previous_right = right
    return dict(piece, time_basis='civil_iana', timezone=zone, timezone_source=timezone_provenance(zone, resolved_zone=tz),
                start=segments[0]['start'], end=segments[-1]['end'], boundaries=boundaries, segments=segments,
                limitations=[*piece['limitations'][:-1],
                             '日柱使用指定民用时区的钟面于 23:00 换日，时区跳变按实际前后钟面处理。'])


def regional_period_facts(start, end, layer, zone, *, start_fold=None, end_fold=None):
    """Resolve the region's actual civil clock on every segment."""
    tz = iana_query_zone(zone)
    start = resolve_query_endpoint(start, zone, tz, start_fold, '--start')
    end = resolve_query_endpoint(end, zone, tz, end_fold, '--end')
    if start.astimezone(timezone.utc) >= end.astimezone(timezone.utc):
        raise ValueError('查询起点须早于终点')
    facts = _regional_facts_from_spans(fixed_offset_spans(start, end, tz), layer, zone, tz)
    return dict(facts, start=start.isoformat(), end=end.isoformat())


def regional_date_facts(start_date, end_date, layer, zone):
    """Cover every reachable instant with a local date in the half-open range."""
    tz = iana_query_zone(zone)
    spans = civil_date_range_spans(start_date, end_date, zone=zone, resolved_zone=tz)
    if not spans:
        raise ValueError('所给民用日期范围无可达查询时刻')
    return dict(_regional_facts_from_spans(spans, layer, zone, tz),
                civil_dates=dict(start_inclusive=start_date.isoformat(), end_exclusive=end_date.isoformat()))


def query_period_facts(start_text, end_text, layer, zone=None, *, start_fold=None, end_fold=None):
    """Resolve the original request using the same rules as the command line."""
    if not all(isinstance(point, str) for point in (start_text, end_text)):
        raise ValueError('查询起止须为 ISO 日期或民用日期时间')
    if any(fold is not None and (type(fold) is not int or fold not in (0, 1))
           for fold in (start_fold, end_fold)):
        raise ValueError('查询端点 fold 须为 0 或 1')
    start, end = parse_query_point(start_text), parse_query_point(end_text)
    if zone is not None:
        if not isinstance(zone, str):
            raise ValueError('查询时区须为 IANA 时区名称')
        if (start_text == start.date().isoformat() and end_text == end.date().isoformat() and
                start_fold is None and end_fold is None):
            return regional_date_facts(start.date(), end.date(), layer, zone)
        return regional_period_facts(start, end, layer, zone, start_fold=start_fold, end_fold=end_fold)
    if start_fold is not None or end_fold is not None:
        raise ValueError('--start-fold 和 --end-fold 仅用于 --timezone')
    return period_facts(start, end, layer)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, help='区间起点，ISO 民用日期时间；IANA 查询两端也可都用纯日期')
    parser.add_argument('--end', required=True, help='区间终点，不包含终点')
    parser.add_argument('--layer', choices=LAYERS, required=True, help='所需时间层，自动附上层事实')
    parser.add_argument('--timezone', help='IANA 民用时区。未提供时两端须使用相同固定 UTC 偏移')
    parser.add_argument('--start-fold', type=int, choices=(0, 1), help='无偏移的重复起点，0 较早，1 较晚')
    parser.add_argument('--end-fold', type=int, choices=(0, 1), help='无偏移的重复终点，0 较早，1 较晚')
    args = parser.parse_args(argv)
    try:
        result = query_period_facts(args.start, args.end, args.layer, args.timezone,
                                    start_fold=args.start_fold, end_fold=args.end_fold)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
