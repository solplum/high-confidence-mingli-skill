"""Opt-in chart-linked traditional comparison. Original adapter code: MIT.

Rendered study expressions retain the registry's CC-BY-SA-4.0 attribution.
No personal-event claim or new ledger authorization is created.
"""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pai_pan_qizheng as engine
import qizheng_rule_profiles as profiles
import qizheng_traditional_study as study

SCHEME = 'qianyuan-palace-v1'
BODIES = ('日', '月', '水', '金', '火', '木', '土')
ROOT = Path(__file__).resolve().parents[1]


def analyze(chart, scheme=None, other_body='金', temporal_uncertainty=False, birth_instant=None):
    out = dict(status='withheld', scope='chart_linked_conditional_structure',
               predictive_validity='unvalidated', personal_ledger_authorized=False,
               classical_quote_authorized=False, scheme=scheme, claims=[],
               unimplemented=['QZT02庙乐评定', 'QZT03相会判断', 'QZT05实际行限', '四余取主', '人生事件预测'])
    try:
        if scheme != SCHEME:
            raise ValueError('须明确选择 qianyuan-palace-v1；不自动把度主法切换为宫主法。')
        if other_body not in BODIES:
            raise ValueError('本轮只比较日月五星；不启用四余规则。')
        if not isinstance(chart, dict) or chart.get('calculation_profile') != 'physical-v2':
            raise ValueError('本入口只接受 corrected physical-v2 引擎盘；旧版只供复现。')
        if chart.get('star_frame_contract', {}).get('within_validated_range') is not True:
            raise ValueError('缺少已检查日期范围的坐标契约。')
        # Reuse the existing source lock and conservative chart evidence gate.
        base = profiles.analyze(chart, temporal_uncertainty=temporal_uncertainty)
        if base['status'] == 'withheld':
            raise ValueError(base['reason'] + ''.join(profiles.palace_guard_reasons(chart)))
        palace_claim = next((c for c in base['claims'] if c['rule_id'] == 'QZ02'), {})
        if palace_claim.get('status') != 'conditional':
            raise ValueError(palace_claim.get('reason', '立命宫证据不足。'))
        for item in (chart.get('ming_du'), chart.get('bodies', {}).get('日')):
            if not isinstance(item, dict) or item.get('classification_quality', {}).get('near_boundary') is not False:
                raise ValueError('缺少明确的宿宫边界检查，或处于边界。')
        contract = chart.get('horizon_contract')
        if not isinstance(contract, dict) or contract.get('ming_gong_clock') != 'Beijing civil hour, independent traditional rule':
            raise ValueError('缺少北京时间安命契约。')
        jd = chart.get('jd_utc')
        if type(jd) not in (float, int) or not math.isfinite(jd):
            raise ValueError('缺少有效UTC瞬间。')
        # Engine CLI inputs have minute precision; round floating JD noise to
        # milliseconds before recovering the civil clock for a consistency check.
        civil = (datetime(2000, 1, 1, tzinfo=timezone.utc) +
                 timedelta(seconds=round((jd - 2451544.5) * 86400, 3))).astimezone(engine.BJ)
        if birth_instant is not None:
            if not isinstance(birth_instant, datetime) or birth_instant.utcoffset() is None:
                raise ValueError('候选瞬间须带明确时区。')
            recovered = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=(jd - 2451544.5) * 86400)
            if abs((birth_instant - recovered).total_seconds()) > 0.0001:
                raise ValueError('候选瞬间与引擎UTC儒略日不一致。')
            # Keep exact subsecond witness side of a civil-hour boundary;
            # 0.1 ms only bounds floating-JD conversion, not physical accuracy.
            civil = birth_instant.astimezone(engine.BJ)
        mg = chart.get('ming_gong', {})
        if mg.get('hour_zhi') != engine._hour_to_shichen(civil.hour, civil.minute):
            raise ValueError('安命时辰与UTC瞬间转换的北京时间不一致。')
        sun_branch = chart.get('sun_palace_zhi')
        if sun_branch not in profiles.LORDS or mg.get('sun_palace') != sun_branch or mg.get('hour_zhi') not in profiles.LORDS:
            raise ValueError('立命宫时辰/太阳宫链缺失或不一致。')
        if engine.ming_gong_zhi(sun_branch, mg['hour_zhi']) != mg.get('zhi'):
            raise ValueError('立命宫与引擎安命法不一致。')
        body = chart.get('bodies', {}).get(other_body)
        if not isinstance(body, dict) or not body:
            raise ValueError('缺少待比较曜的引擎字段。')
        for key in ('tropical', 'sidereal'):
            value = body.get(key)
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value < 360:
                raise ValueError('待比较曜缺少有效黄经字段。')
        facts = dict(context='natal', reference_basis='palace_lord', branch=mg['zhi'],
                     other_element=engine.LUMINARIES_WUXING[other_body])
        claim = study.evaluate('QZT04', facts)
        if claim['status'] != 'conditional_study':
            raise ValueError(claim.get('reason', '传统资料来源门未通过。'))
        claim.update(status='conditional', input_facts=facts, other_body=other_body,
                     chart_pointers=['/ming_gong/zhi', '/ming_gong/hour_zhi', '/sun_palace_zhi', '/bodies/' + other_body],
                     element_basis='engine.LUMINARIES_WUXING, not the occupied mansion lord')
        claim['application'] = ('若采用本盘近似宿宫与北京时间安命，并选择乾元本命宫主参照，则%s宫主%s折%s，%s曜按项目映射属%s，相对于宫主为“%s”。这是传统结构比较，不据此断性格、贵贱、病寿、婚财或应期。' %
                                (mg['zhi'], claim['calculation']['palace_lord'], claim['calculation']['reference_element'],
                                 other_body, facts['other_element'], claim['calculation']['relation']))
        claim['alternative'] = '既有QZ01以命度宿主为参照；其恩用难仇标签不搬到本宫主法，两个基准不可合并投票。'
        raw = json.dumps(chart, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        out.update(status='conditional', claims=[claim], chart_sha256=hashlib.sha256(raw).hexdigest(),
                   registry_sha256=study.REGISTRY_SHA256,
                   adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   calculation_profile='physical-v2', horizon_contract=chart.get('horizon_contract'),
                   source_gate='review-locked study registry + existing qizheng source/field gate')
    except (ValueError, TypeError, KeyError, OSError, AttributeError, OverflowError) as exc:
        out['reason'] = str(exc)
    return out


def render(result):
    lines = ['### 七政传统参照比较（条件式，非人生预测）']
    if result['status'] == 'withheld':
        lines.append('暂不判：' + result['reason'])
    for claim in result['claims']:
        lines += [claim['application'], claim['alternative'], study.format_reading(claim)]
    lines.append('未启用：' + '；'.join(result['unimplemented']))
    return '\n'.join(lines)


def main(argv=None):
    parser = engine.build_parser()
    parser.add_argument('--tradition', choices=(SCHEME,))
    parser.add_argument('--other-body', choices=BODIES, default='金')
    parser.add_argument('--uncertain-time', action='store_true')
    parser.add_argument('--format', choices=('json', 'text'), default='text')
    args = parser.parse_args(argv)
    try:
        date = tuple(int(n) for n in args.solar.split('-'))
        if len(date) != 3:
            raise ValueError('--solar requires YYYY-MM-DD')
        hour, minute = (int(n) for n in args.hour.split(':'))
        chart, warnings = engine.compute(date, hour, minute, args.lat, args.lon, args.place,
                                         profile=args.profile, dut1_seconds=args.dut1_seconds)
        reading = analyze(chart, args.tradition, args.other_body, args.uncertain_time)
        result = {'input': vars(args), 'chart': chart, 'warnings': warnings, 'traditional_reading': reading}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) if args.format == 'json' else render(reading) + '\n' + '\n'.join('引擎提示：' + w for w in warnings))
        return 1 if reading['status'] == 'withheld' else 0
    except (ValueError, TypeError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
