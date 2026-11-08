"""Bounded empirical time sensitivity, never an exhaustive partition/proof.

Refine categorical differences between adjacent grid witnesses, not a claim
of monotonicity or a physical event-time solver. Equal endpoint signatures
can hide excursions, tangent crossings and multiple roots, especially near
polar ascendant singularities. Every retained candidate is actually evaluated.
"""
from datetime import datetime, timedelta, timezone
import json
import math

import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules
import qizheng_traditional_reading as tradition

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


def compare(civil, minutes, lat, lon, profile='physical-v2', dut1_seconds=0.0, traditional_scheme=None, other_body='金'):
    if not isinstance(civil, datetime):
        raise ValueError('七政敏感性需要明确的出生瞬间')
    if (type(minutes) not in (int, float) or not 0 <= minutes <= 120
            or not math.isfinite(minutes)):
        raise ValueError('七政敏感性误差须在 0 至 120 分钟之间')
    if (type(lat) not in (int, float) or type(lon) not in (int, float)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
            or not all(math.isfinite(x) for x in (lat, lon))):
        raise ValueError('七政敏感性经纬度超出范围')
    if (type(dut1_seconds) not in (int, float)
            or not -0.9 <= dut1_seconds <= 0.9
            or not math.isfinite(dut1_seconds)):
        raise ValueError('dut1_seconds must be finite and within +/-0.9 s (modern UTC)')
    try:
        if civil.utcoffset() is None:
            raise ValueError('七政敏感性需要明确的出生瞬间')
        center = civil.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('七政敏感性需要可转换为 UTC 的明确出生瞬间') from exc
    # Reject datetime extrema before interval arithmetic can overflow. Check
    # UTC, not the civil year: offsets can cross a supported-year boundary.
    if not 1901 <= center.year <= 2099:
        raise ValueError('七政敏感性完整 UTC 区间须在 1901–2099 年内')
    start, end = center - timedelta(minutes=minutes), center + timedelta(minutes=minutes)
    if start.year < 1901 or end.year > 2099:
        raise ValueError('七政敏感性完整 UTC 区间须在 1901–2099 年内')
    cache = {}
    def evaluate(t):
        if t not in cache:
            if len(cache) >= MAX_EVALUATIONS:
                return None
            bj = t.astimezone(engine.BJ)
            chart, warnings = engine.compute((bj.year, bj.month, bj.day), bj.hour, bj.minute,
                lat, lon, birth_instant=t, profile=profile, dut1_seconds=dut1_seconds)
            # Pointwise evidence, not a grant to use this as the uncertain birth chart.
            reading = rules.analyze(chart, temporal_uncertainty=False)
            traditional = tradition.analyze(chart, traditional_scheme, other_body, False, birth_instant=t) if traditional_scheme else None
            discrete = fields(chart, reading)
            if traditional is not None:
                discrete['traditional_rule_output'] = {k: traditional.get(k) for k in ('status', 'reason', 'claims')}
            local = t.astimezone(civil.tzinfo)
            cache[t] = {'witness_utc': t.isoformat(), 'witness_civil': local.isoformat(),
                        'fold': local.fold, 'chart': chart, 'rule_reading': reading,
                        'traditional_reading': traditional, 'warnings': warnings, 'fields': discrete}
        return cache[t]
    points = {start, center, end}
    t = start
    while t < end:
        points.add(t)
        t += timedelta(seconds=GRID_SECONDS)
    points = sorted(points)
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
    keep = {start, center, end}
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
        '区间为已解析中心前后实际经过 UTC 时间；不自动合并未选择的 fold。',
    ]
    if profile == 'legacy-v1':
        limitations.append('legacy-v1 仅复现已知错误模型，不因比较而恢复可信度。')
    return {'version': VERSION, 'status': 'sampled_conditional', 'coverage_complete': False,
        'stable_fields': {}, 'observed_changing_fields': changed,
        'not_observed_changing_fields': sorted(set(first)-set(changed)),
        'interval': {'start_utc': start.isoformat(), 'center_utc': center.isoformat(), 'end_utc': end.isoformat(), 'endpoints_included': True, 'basis': 'elapsed_utc'},
        'calculation_profile': profile, 'rule_profile': rules.PROFILE,
        'traditional_scheme': traditional_scheme, 'traditional_other_body': other_body if traditional_scheme else None,
        'method': {'grid_seconds': GRID_SECONDS, 'bracket_target_seconds': BRACKET_SECONDS,
                   'max_evaluations': MAX_EVALUATIONS, 'evaluation_count': len(cache),
                   'budget_exhausted': budget_exhausted, 'root_completeness_proven': False,
                   'search': 'bisect observed discrete signature differences; not continuous root isolation'},
        'high_latitude_caution': abs(lat) >= 66,
        'uncertain_birth_rule_status': 'withheld' if minutes else cache[center]['rule_reading']['status'],
        'boundaries': sorted(brackets, key=lambda b: b['left_utc']),
        'candidates': [cache[t] for t in sorted(keep)], 'limitations': limitations}


SUMMARY_MAX_CHANGES = 6


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
    if key in ('rule_output', 'traditional_rule_output'):
        return '暂缓解释' if value.get('status') == 'withheld' else '有条件解释'
    return str(value) if value is not None else '未定义'


def render(result, full_evidence=False):
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
    priorities = ['ascendant.defined', 'day_night', 'ascendant.mansion',
                  'ascendant.palace', 'ming_gong', 'traditional_rule_output', 'rule_output']
    priorities += ['bodies.' + body + '.' + field for body in engine.LUMINARIES
                   for field in ('mansion', 'palace')]
    changed = set(result['observed_changing_fields'])
    selected = [key for key in priorities if key in changed][:SUMMARY_MAX_CHANGES]
    for key in selected:
        bracket = next((b for b in result['boundaries'] if key in b['changed_fields']), None)
        if bracket is None:
            continue
        a, b = (by_time[bracket[k]] for k in ('left_utc', 'right_utc'))
        left, right = (_value(key, row['fields'][key]) for row in (a, b))
        change = left + ' → ' + right
        if key in ('rule_output', 'traditional_rule_output') and left == right:
            change += '（具体条件或解释内容不同）'
        low = datetime.fromisoformat(bracket['left_utc'])
        high = datetime.fromisoformat(bracket['right_utc'])
        low = low.replace(second=0, microsecond=0)
        rounded_high = high.replace(second=0, microsecond=0)
        if rounded_high < high:
            rounded_high += timedelta(minutes=1)
        lines.append('- %s：%s；一次观察差异位于 UTC %s 至 %s 范围内。' %
                     (_label(key), change, low.strftime('%Y-%m-%d %H:%M'), rounded_high.strftime('%Y-%m-%d %H:%M')))
    if not changed:
        lines.append('- 本次采样未观察到分类变化，但不能据此说整个时段稳定。')
    elif not selected:
        lines.append('- 观察到其他分类或靠界筛查变化；详细字段见完整证据。')
    else:
        lines.append('- 这里只列每项的一处见证，未列出的字段及其他过界请查看完整证据。')
    if any(row['chart'].get('ming_du') is None for row in result['candidates']):
        lines.append('- 部分或全部见证的上升交点未定义；这些时刻不补造命度或相关规则。')
    if result['high_latitude_caution']:
        lines.append('- 高纬度可能出现上升交点退化或跳变，采样尤其不能保证找全。')
    if first['fold'] or last['fold'] or first['witness_civil'][-6:] != last['witness_civil'][-6:]:
        lines.append('- 时段涉及时区偏移变化或重复民用时刻；以 UTC 区分瞬间，不自动加入另一个出生时刻选择。')
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
