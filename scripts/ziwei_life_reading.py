#!/usr/bin/env python3
"""Approved module-only Ziwei life topics; preserves native and dynamic contracts."""
import argparse
from copy import deepcopy
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import re

import reviewed_knowledge as knowledge
from time_scenarios import (
    UTC, check_recorded_scenario_bounds, check_timezone_source, civil_shichen_hours, civil_shichen_spans, enumerate_scenarios,
    fixed_utc_offset, iana_zone, parse_birth_date, parse_query_point, recorded_scenario_bounds, resolve_civil,
    scenario_clock_at, scenario_clock_boundaries, scenario_witnesses, snapshot_apparent_correction,
    snapshot_dut1_seconds, solar_clock, timezone_provenance,
)
import ziwei_case_judgments as case_judgments
from ziwei_native import lunar_calendar_at, run_ziwei
import ziwei_stage_relationship as stage_relationship

PROFILE = 'ziwei-life-domains-v1'
BIRTH_BAND_SCHEMA = 'ziwei-birth-time-candidates-v1'
DYNAMIC_PROFILE = 'iztro-2.6.1-lunar-year-month-v1'
RULE_IDS = tuple('ZW-D%02d' % i for i in range(1, 9)) + tuple('ZW-E%02d' % i for i in range(1, 6)) + ('ZW-S01', 'ZW-T02')
RECORD_IDS = tuple('ziwei-life-' + rule for rule in RULE_IDS)
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
STEMS = '甲乙丙丁戊己庚辛壬癸'
KINDS = '禄权科忌'
BIRTH_DATE_FIELDS = ('year', 'month', 'day')
BIRTH_HEADER_FIELDS = ('hour', *BIRTH_DATE_FIELDS, 'gender')
NAMES = ('命', '父母', '福德', '田宅', '官禄', '仆役', '迁移', '疾厄', '财帛', '子女', '夫妻', '兄弟')
DOMAIN_RULES = dict(zip(('兄弟', '夫妻', '子女', '疾厄', '仆役', '田宅', '福德', '父母'), RULE_IDS[:8]))
ROLES = {'命': '自身选择与方向', '财帛': '资源分配与使用', '官禄': '做事与落实方式', '迁移': '对外互动',
         '兄弟': '自身与实际手足的相处和互助边界', '夫妻': '自身择偶态度与亲密互动',
         '子女': '实际养育或陪伴角色中的自身投入', '疾厄': '身体管理与劳逸安排的一般生活反思',
         '仆役': '自身择友、沟通与交往边界', '田宅': '家庭边界、居住安排与积累态度',
         '福德': '思考与内在满足的取向', '父母': '自身接受支持与自主边界'}
UNCERTAIN = '出生时间存在非零误差：这里只列本候选事实，不作为唯一输入的个人主题'
MEDICAL_BOUNDARY = '仅一般生活反思；不从星曜或四化推体质、器官、疾病风险、事故、寿命、用药或就医时机'


def _name(value):
    return value[:-1] if isinstance(value, str) and value.endswith('宫') else value


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _chart(chart):
    if not isinstance(chart, dict) or not _integer(chart.get('mingGongBranch'), 0, 11):
        raise ValueError('缺少有效本命命宫地支')
    palaces = chart.get('palaces')
    if not isinstance(palaces, list) or len(palaces) != 12:
        raise ValueError('十二宫不完整')
    if any(not isinstance(p, dict) or not _integer(p.get('branch'), 0, 11) or
           _name(p.get('name')) not in NAMES or not isinstance(p.get('stars'), list) for p in palaces):
        raise ValueError('宫位名称、地支或星表无效')
    if len({p['branch'] for p in palaces}) != 12 or len({_name(p['name']) for p in palaces}) != 12:
        raise ValueError('十二宫名称或地支重复')
    facts = []
    for pi, palace in enumerate(palaces):
        if _name(palace['name']) != NAMES[(palace['branch'] - chart['mingGongBranch']) % 12]:
            raise ValueError('宫名与本命命宫地支关系不符')
        for si, star in enumerate(palace['stars']):
            if (not isinstance(star, dict) or not isinstance(star.get('name'), str) or not star['name'].strip() or
                    star.get('type') not in ('major', 'minor', 'lucky', 'sha') or
                    star.get('siHua') not in (None, '', *KINDS)):
                raise ValueError('原始星表或本命四化标记无效')
            facts.append(dict(name=star['name'], type=star['type'], brightness_raw=star.get('brightnessRaw'),
                              natal_transform=star.get('siHua') or None, domain=palace['name'],
                              branch=palace['branch'], palace_path='chart.palaces[%d]' % pi,
                              path='chart.palaces[%d].stars[%d]' % (pi, si)))
    majors = [f for f in facts if f['type'] == 'major']
    if sorted(f['name'] for f in majors) != sorted(knowledge.STARS):
        raise ValueError('十四实际主星缺失、重复或包含未登记主星')
    return palaces, facts


def _table(root):
    # Read the native fixed table rather than maintain a second astrology table.
    text = (Path(root) / 'scripts/pai_pan_ziwei/vendor/constants.ts').read_text(encoding='utf-8')
    block = text.split('export const SI_HUA_TABLE:', 1)[1].split('};', 1)[0]
    rows = {int(i): re.findall(r"'([^']+)'", values)
            for i, values in re.findall(r'^\s*(\d):\s*\[([^\]]+)\]', block, re.M)}
    if set(rows) != set(range(10)) or any(len(row) != 4 or len(set(row)) != 4 for row in rows.values()):
        raise ValueError('原生固定四化表无法核对')
    return rows


def _effective_lunar_month(calendar):
    return calendar['lunarMonth'] + int(calendar['isLeap'] and calendar['lunarDay'] > 15)


def dynamic_layer_pillar(calendar, layer):
    """Use the locked normal profile's lunar year and half-leap-month rule."""
    year = calendar['lunarYear'] - 4
    if layer == 'yearly':
        return STEMS[year % 10], BRANCHES[year % 12]
    month = _effective_lunar_month(calendar)
    return STEMS[(2 * (year % 10) + month + 1) % 10], BRANCHES[(month + 1) % 12]


def _card(record):
    return dict(rule_id=record['rule_id'], record_id=record['id'], title=record['title'], status='conditional',
                reading_use='conditional_module_only', summary=record['summary'],
                source_conditions=deepcopy(record['conditions']), source_exclusions=deepcopy(record['exclusions']),
                citation=deepcopy(record['citation']), rows=[], unresolved=[], effect_assessment='withheld')


def _brightness(raw):
    if raw in ('庙', '旺'):
        return '按已登记现代说明讨论主动、直接表达；不是效力或结果等级'
    if raw in ('不', '陷'):
        return '同时考虑保留表达与额外斟酌；不是不利结果判定'
    return '中间等级不再强分' if raw in ('得', '利', '平') else '缺少原始亮度，不推定为平或反推压缩等级'


def _domain(palace, facts, themes, card, uncertainty):
    domain = _name(palace['name'])
    actual = [deepcopy(f) for f in facts if f['branch'] == palace['branch']]
    majors = [f for f in actual if f['type'] == 'major']
    row = dict(domain=palace['name'], role=ROLES[domain], branch=palace['branch'],
               source_rule=card['rule_id'] if card else 'ziwei-domain-conditional',
               status='withheld' if uncertainty or not majors else 'conditional', facts=actual,
               major_topics=[], empty_palace=not majors, borrowed_topics=[],
               author_connection='把已登记单星主题作为本领域自身态度或行为的条件研究入口；须另核实际角色与目标',
               missing_conditions=['实际角色、目标、支持与同目标反向尚待人工核查；反证问题不是已经存在的负向特征',
                                   '完整辅杂曜与组合交互未裁决，不推他人心理或事件结果'])
    if card:
        row['citation'] = deepcopy(card['citation'])
    if uncertainty:
        row['missing_conditions'].append(UNCERTAIN)
    for fact in majors:
        theme = themes[fact['name']]
        brightness_discussion = ('保存亮度与复盘不一致，暂缓亮度解释'
                                 if fact.get('brightness_conflict') else _brightness(fact['brightness_raw']))
        row['major_topics'].append(dict(star=fact['name'], fact_path=fact['path'],
                                        theme=theme['theme'], countercheck=theme['question'],
                                        brightness_raw=fact['brightness_raw'], brightness_discussion=brightness_discussion,
                                        identity='conditional_topic_not_measured_trait', citation=deepcopy(theme['citation'])))
    if not majors:
        row['missing_conditions'].append('空宫仅保留完整实际星表，不从对宫借入主题、亮度或四化')
    if domain == '疾厄':
        row['health_scope'] = 'general_life_reflection_only'
        row['medical_boundary'] = MEDICAL_BOUNDARY
    return row


def _natal_transforms(chart, facts, table):
    lunar = chart.get('lunarInfo')
    if not isinstance(lunar, dict):
        raise ValueError('lunarInfo须为对象：暂缓本命四化主题，保留实际宫位星表')
    stem = lunar.get('yearStem')
    if not _integer(stem, 0, 9):
        raise ValueError('缺少已核出生农历年干，暂缓本命四化主题')
    rows, errors = [], {}
    for kind, star in zip(KINDS, table[stem]):
        attached = [fact for fact in facts if fact['natal_transform'] == kind]
        if len(attached) != 1 or attached[0]['name'] != star or sum(fact['name'] == star for fact in facts) != 1:
            errors[kind] = '原生本命化' + kind + '缺失或附着不符合固定表'
            continue
        fact, = attached
        rows.append(dict(id='natal.' + kind, layer='natal', kind=kind, star=star,
                         fact=deepcopy(fact), source_path=fact['path'] + '.siHua'))
    return rows, errors


def _static_identity(chart):
    birth = chart.get('birthInfo')
    if not isinstance(birth, dict):
        birth = {}
    return dict(birthInfo={key: birth.get(key) for key in ('year', 'month', 'day', 'hour', 'gender')}, lunarInfo=chart.get('lunarInfo'),
                mingGongBranch=chart.get('mingGongBranch'), shenGongBranch=chart.get('shenGongBranch'),
                palaces=sorted([dict(branch=p['branch'], name=_name(p['name']),
                                    stars=sorted([(s['name'], s['type'], s.get('brightnessRaw'), s.get('siHua') or None)
                                                  for s in p['stars']], key=lambda row: row[0]))
                                for p in chart['palaces']], key=lambda p: p['branch']))


def _same_identity(left, right):
    # Python equality equates True and 1, but saved JSON identity fields are typed.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _static_placements(chart, *, include_body):
    identity = _static_identity(chart)
    del identity['birthInfo']
    del identity['lunarInfo']
    if not include_body:
        del identity['shenGongBranch']
    for palace in identity['palaces']:
        palace['stars'] = [star[:2] for star in palace['stars']]
    return identity


def _fill_missing_birth_header(saved_chart, observed):
    saved = saved_chart.get('birthInfo')
    if saved is None:
        saved_chart['birthInfo'] = dict(observed)
        return ['chart.birthInfo']
    if not isinstance(saved, dict):
        return []
    fields = [key for key in BIRTH_HEADER_FIELDS if saved.get(key) is None]
    if fields:
        saved_chart['birthInfo'] = {**saved, **{key: observed[key] for key in fields}}
    return ['chart.birthInfo.' + key for key in fields]


def _check_saved_birth_header(saved, observed):
    if saved is None:
        return
    if not isinstance(saved, dict):
        raise ValueError('原盘出生标头格式与原出生资料复盘不一致')
    conflicts = [key for key in BIRTH_HEADER_FIELDS if saved.get(key) is not None and
                 (type(saved[key]) is not type(observed[key]) or saved[key] != observed[key])]
    if any(key in BIRTH_DATE_FIELDS for key in conflicts):
        raise ValueError('已存出生日期分量与原出生资料复盘不一致')
    if conflicts:
        raise ValueError('原盘出生标头的时辰或性别与原出生资料复盘不一致')


def _fill_missing_chart_annotations(saved, observed):
    """Compare through known omissions without changing the stored chart."""
    gaps = _fill_missing_birth_header(saved, observed['birthInfo'])
    if saved.get('shenGongBranch') is None and observed.get('shenGongBranch') is not None:
        saved['shenGongBranch'] = observed['shenGongBranch']
        gaps.append('chart.shenGongBranch')
    lunar, source_lunar = saved.get('lunarInfo'), observed.get('lunarInfo')
    if lunar is None and isinstance(source_lunar, dict):
        saved['lunarInfo'] = source_lunar
        gaps.append('chart.lunarInfo')
    elif isinstance(lunar, dict) and isinstance(source_lunar, dict) and lunar.keys() <= source_lunar.keys():
        missing = source_lunar.keys() - lunar.keys()
        if lunar.get('yearStem') is None and 'yearStem' in source_lunar:
            missing.add('yearStem')
        if missing:
            saved['lunarInfo'] = {**lunar, **{key: source_lunar[key] for key in missing}}
            gaps.extend('chart.lunarInfo.' + key for key in sorted(missing))
    return gaps


def _unverified_static_fields(native, chart, native_facts, facts, table, *,
                              mismatch='动态附带本命星表与实际出生盘不一致', allow_missing_chart_annotations=False):
    """Allow missing saved annotations only after exact birth and star alignment."""
    observed, saved = _static_identity(native), _static_identity(chart)
    if _same_identity(observed, saved):
        return []
    observed_palaces = observed.pop('palaces')
    saved_palaces = saved.pop('palaces')
    gaps = []
    if not _same_identity(observed, saved):
        if not allow_missing_chart_annotations:
            raise ValueError(mismatch)
        gaps = _fill_missing_chart_annotations(saved, observed)
        if not _same_identity(observed, saved):
            raise ValueError(mismatch)
    verified_transforms = None
    for source_palace, saved_palace in zip(observed_palaces, saved_palaces):
        source_stars = source_palace.pop('stars')
        saved_stars = saved_palace.pop('stars')
        if source_palace != saved_palace or [row[:2] for row in source_stars] != [row[:2] for row in saved_stars]:
            raise ValueError(mismatch)
        branch = saved_palace['branch']
        for source, recorded in zip(source_stars, saved_stars):
            if source == recorded:
                continue
            name, star_type, brightness, transform = recorded
            paths = [fact['path'] for fact in facts if
                     (fact['branch'], fact['name'], fact['type']) == (branch, name, star_type)]
            if len(paths) != 1:
                raise ValueError(mismatch)
            path, = paths
            if brightness != source[2]:
                if brightness is not None or source[2] not in case_judgments.RAW_BRIGHTNESS:
                    raise ValueError(mismatch)
                gaps.append(path + '.brightnessRaw')
            if transform != source[3]:
                if transform is not None or source[3] is None:
                    raise ValueError(mismatch)
                if verified_transforms is None:
                    rows, _ = _natal_transforms(native, native_facts, table)
                    verified_transforms = {row['kind']: (row['fact']['branch'], row['star'], row['fact']['type'])
                                           for row in rows}
                if verified_transforms.get(source[3]) != (branch, name, star_type):
                    raise ValueError(mismatch)
                gaps.append(path + '.siHua')
    return gaps


def _dynamic(dynamic, chart, facts, birth_year, table, expected_query_point, replayed_natal,
             verified_target_clock, latest_birth, birth_gaps):
    from ziwei_query_windows import date_index_after_birth

    base = dict(status='not_requested', profile=DYNAMIC_PROFILE, layers={}, transformations=[],
                full_interval_coverage=False, excluded_layers=['daily', 'age', 'decadal', 'hourly'], errors=[])
    if dynamic is None:
        return base
    base['status'] = 'withheld'

    def verify_birth_order(query_point):
        order_date, order_index = query_point
        if (latest_birth is None or
                (verified_target_clock is not None and verified_target_clock < latest_birth) or
                (verified_target_clock is None and
                 not date_index_after_birth(date.fromisoformat(order_date), order_index, latest_birth))):
            base['birth_time_status'] = 'birth_time_unverified'
            raise ValueError('查询可能早于出生范围的最晚边界，须核原出生资料并提供带偏移的本次查询钟面')

    try:
        if expected_query_point is not None:
            verify_birth_order(expected_query_point)
        if not isinstance(dynamic, dict) or dynamic.get('schema_version') != 'ziwei-dynamic-facts-v1':
            raise ValueError('必须提供独立适配器完整输出，不接受raw或裸layers')
        admitted = dynamic.get('admitted_dynamic_facts', {})
        if (admitted.get('profile') != DYNAMIC_PROFILE or admitted.get('full_interval_coverage') is not False or
                admitted.get('native_age_and_decadal_unchanged') is not True):
            raise ValueError('动态profile或单点/原年龄合同标记不符合准入合同')
        layers = admitted.get('layers')
        if not isinstance(layers, dict) or set(layers) - {'yearly', 'monthly', 'daily'}:
            raise ValueError('准入层包含未许可层或缺少layers')
        born = dynamic.get('inputs', {}).get('birth', {})
        b = chart.get('birthInfo', {})
        birth_hour = b.get('hour') if isinstance(b, dict) else None
        sex_by_gender = {'male': '男', 'female': '女'}
        if (not isinstance(b, dict) or b.get('gender') not in sex_by_gender or
                not _integer(b.get('year'), 1, 9999) or not _integer(b.get('month'), 1, 12) or
                not _integer(b.get('day'), 1, 31) or not _integer(birth_hour, 0, 11)):
            raise ValueError('缺少已核本命出生标头，无法核对动态出生身份')
        solar = '%04d-%02d-%02d' % (b['year'], b['month'], b['day'])
        original_year = born.get('original_civil_birth_year')
        if (born.get('solar') != solar or not _integer(born.get('shichen_index'), 0, 11) or
                born['shichen_index'] != birth_hour or born.get('sex') != sex_by_gender[b['gender']] or
                not _integer(original_year, 1, 9999) or abs(original_year - b['year']) > 1 or
                (birth_year is not None and original_year != birth_year)):
            raise ValueError('动态出生身份或原民用出生年与本盘不一致')
        target = dynamic.get('inputs', {}).get('target', {})
        target_date = date.fromisoformat(target['solar_date'])
        if target_date.isoformat() != target['solar_date'] or not _integer(target.get('time_index'), 0, 12):
            raise ValueError('动态查询点无效')
        actual_index = target['time_index']
        actual_query_point = (target['solar_date'], actual_index)
        if expected_query_point is None:
            verify_birth_order(actual_query_point)
        if expected_query_point is not None and actual_query_point != expected_query_point:
            expected_date, expected_index = expected_query_point
            raise ValueError(f'动态查询点与本次请求不一致。实际为 {target_date}（时辰索引 {actual_index}），'
                             f'预期为 {expected_date}（时辰索引 {expected_index}）')
        if (verified_target_clock is not None or 'civil_time' in target or
                target_date < date.fromisoformat(solar) or target_date.year < original_year):
            recorded_clock = _optional_clock(target.get('civil_time'))
            if (verified_target_clock is None or recorded_clock is None or
                    recorded_clock.isoformat() != verified_target_clock.isoformat()):
                raise ValueError('动态资料须与独立核对的带偏移查询钟面一致')
        native = dynamic.get('native_wrapper_snapshot', {}).get('chart')
        _, native_facts = _chart(native)
        if replayed_natal is not None and not _same_identity(_static_identity(native), _static_identity(replayed_natal)):
            raise ValueError('动态附带本命星表与实际出生盘不一致')
        static_gaps = [*birth_gaps, *_unverified_static_fields(
            native, chart, native_facts, facts, table, allow_missing_chart_annotations=replayed_natal is not None)]
        if static_gaps:
            base['unverified_static_fields'] = static_gaps
        native_inputs = dynamic['native_wrapper_snapshot'].get('input')
        if (not isinstance(native_inputs, dict) or not _integer(native_inputs.get('ageYear'), 1, 9999) or
                native_inputs['ageYear'] != max(target_date.year, original_year)):
            raise ValueError('动态目标公历年与适配器原生ageYear参考年不一致')
        expected_birth_inputs = dict(solar=solar, shichenIndex=birth_hour, gender=b['gender'], birthYear=original_year)
        if any(type(native_inputs.get(key)) is not type(value) or native_inputs[key] != value
               for key, value in expected_birth_inputs.items()):
            raise ValueError('动态附带原生输入与本命出生日期、时辰、性别或原民用出生年不一致')
        # These fields audit identity only. No research value supplies a topic or
        # replaces missing admitted data; forbidden raw time layers are not read.
        research = dynamic.get('research_dynamic_iztro')
        raw_horoscope = research.get('raw_horoscope') if isinstance(research, dict) else None
        if not isinstance(raw_horoscope, dict):
            raise ValueError('缺少查询日期审计元数据，不能核实动态查询点')
        source_date = raw_horoscope.get('solarDate')
        try:
            source_date = date(*map(int, source_date.split('-'))) if isinstance(source_date, str) else None
        except (ValueError, TypeError):
            source_date = None
        if source_date != target_date:
            raise ValueError('目标日期与适配器来源solarDate不一致或缺失')
        calendar = research.get('calendar_observation')
        if not isinstance(calendar, dict):
            raise ValueError('缺少查询农历审计元数据，不能核实年/月边界')
        target_lunar = calendar.get('target_lunar')
        if (not isinstance(target_lunar, dict) or not _integer(target_lunar.get('lunarYear'), 1, 9999) or
                target_lunar['lunarYear'] not in (target_date.year-1, target_date.year)):
            raise ValueError('查询农历审计字段缺失或无效，不能核实年/月边界')
        expected_lunar = lunar_calendar_at(target_date)
        source_views = research.get('selected_fact_views')
        source_palaces = native['palaces']

        def coordinate(value):
            if not isinstance(value, dict) or not _integer(value.get('iztro_array_index'), 0, 11):
                raise ValueError('动态宫位坐标缺失或索引无效')
            p = source_palaces[value['iztro_array_index']]
            if (not _integer(value.get('branch_index'), 0, 11) or value.get('branch_index') != p['branch'] or value.get('earthly_branch') != BRANCHES[p['branch']] or
                    _name(value.get('natal_palace')) != _name(p['name'])):
                raise ValueError('动态坐标与实际本命地支/宫名不匹配')
            return p

        base['query_point'] = deepcopy(target)
        base['original_civil_birth_year'] = original_year
        for layer_name in ('yearly', 'monthly'):
            layer_result = dict(status='withheld', errors=[], transformations=[])
            base['layers'][layer_name] = layer_result
            layer = layers.get(layer_name)
            try:
                if not isinstance(layer, dict) or layer.get('status') != 'facts_only' or layer.get('interpretation_status') != 'facts_only_no_effect_verdict':
                    raise ValueError('该动态层未被事实适配器准入')
                if layer_name == 'monthly' and (
                        not _integer(target_lunar.get('lunarMonth'), 1, 12) or
                        not _integer(target_lunar.get('lunarDay'), 1, 30) or
                        type(target_lunar.get('isLeap')) is not bool):
                    raise ValueError('查询农历月、日或闰月标记缺失或无效，不能核实流月边界')
                layer_pointer = '/research_dynamic_iztro/raw_horoscope/' + layer_name
                if layer.get('raw_pointer') != layer_pointer:
                    raise ValueError('动态层raw_pointer与准入层身份不一致')
                source_view = source_views.get(layer_name) if isinstance(source_views, dict) else None
                audit_keys = ('raw_pointer', 'ming_coordinate', 'heavenly_stem', 'earthly_branch', 'domain_coordinates', 'transformations')
                if (not isinstance(source_view, dict) or any(key not in source_view or key not in layer or
                        source_view[key] != layer[key] for key in audit_keys)):
                    raise ValueError('该层来源派生视图缺失或与admitted不一致，不从research补齐')
                ming = coordinate(layer.get('ming_coordinate'))
                coordinates = layer.get('domain_coordinates')
                if not isinstance(coordinates, list) or len(coordinates) != 12:
                    raise ValueError('该层十二领域坐标不完整')
                branches, names = [], []
                for item in coordinates:
                    p = coordinate(item.get('natal_coordinate'))
                    name = _name(item.get('layer_palace_name'))
                    if name != NAMES[(p['branch'] - ming['branch']) % 12]:
                        raise ValueError('动态领域与该层命宫关系不符')
                    branches.append(p['branch']); names.append(name)
                if len(set(branches)) != 12 or len(set(names)) != 12:
                    raise ValueError('动态领域坐标重复')
                stem = layer.get('heavenly_stem')
                if not isinstance(stem, str) or len(stem) != 1 or stem not in STEMS or layer.get('earthly_branch') not in tuple(BRANCHES):
                    raise ValueError('动态干支缺失或无效')
                if layer_name == 'yearly' and layer['earthly_branch'] != BRANCHES[ming['branch']]:
                    raise ValueError('流年地支与该层实际命宫坐标不一致')
                source_year = target_lunar['lunarYear']
                expected_pillar = dynamic_layer_pillar(target_lunar, layer_name)
                if (stem, layer['earthly_branch']) != expected_pillar:
                    reason = ('流年标签与来源查询农历年不一致' if layer_name == 'yearly' else
                              '流月标签或落点与来源农历月/闰月半月边界不一致')
                    raise ValueError(reason)
                if layer_name == 'monthly':
                    birth_lunar = calendar.get('birth_lunar')
                    native_lunar = native.get('lunarInfo')
                    if (not isinstance(birth_lunar, dict) or not isinstance(native_lunar, dict) or
                            not _integer(birth_lunar.get('lunarYear'), 1, 9999) or not _integer(birth_lunar.get('lunarMonth'), 1, 12) or
                            not _integer(birth_lunar.get('lunarDay'), 1, 30) or
                            any(birth_lunar.get(k) != native_lunar.get(k) for k in ('lunarYear','lunarMonth','lunarDay')) or
                            type(birth_lunar.get('isLeap')) is not bool or birth_lunar['isLeap'] != native_lunar.get('isLeapMonth')):
                        raise ValueError('出生农历审计字段与原生本命不一致或缺失')
                    source_month = _effective_lunar_month(target_lunar)
                    birth_month = _effective_lunar_month(birth_lunar)
                    expected_branch = ((source_year-4) % 12 - birth_month + birth_hour + source_month) % 12
                    if ming['branch'] != expected_branch:
                        raise ValueError('流月标签或落点与来源农历月/闰月半月边界不一致')
                transforms = layer.get('transformations')
                if not isinstance(transforms, list) or len(transforms) != 4 or {t.get('kind') for t in transforms} != set(KINDS):
                    raise ValueError('动态四化缺失或重复')
                rows = []
                for t in transforms:
                    kind, star = t['kind'], t.get('star')
                    if t.get('raw_pointer') != layer_pointer + '/mutagen/' + str(KINDS.index(kind)):
                        raise ValueError('动态四化raw_pointer与层身份或化类顺序不一致')
                    if star != table[STEMS.index(stem)][KINDS.index(kind)]:
                        raise ValueError('动态四化星名与准入干固定表不符')
                    matches = [f for f in facts if f['name'] == star]
                    locations = t.get('natal_star_locations')
                    if len(matches) != 1 or not isinstance(locations, list) or len(locations) != 1:
                        raise ValueError('动态四化必须附着到唯一实际本命星')
                    location = locations[0]
                    p = coordinate(location.get('location'))
                    if location.get('name') != star or p['branch'] != matches[0]['branch']:
                        raise ValueError('动态四化附着到错误本命星位')
                    rows.append(dict(id=layer_name + '.' + kind, layer=layer_name, kind=kind, star=star,
                                     fact=deepcopy(matches[0]), source_path='/admitted_dynamic_facts/layers/' + layer_name + '/transformations/' + str(transforms.index(t)),
                                     admitted_attachment=deepcopy(t), query_point=deepcopy(target)))
                # Check the source behind the pointer, not just two copies of its projection.
                raw_layer = raw_horoscope.get(layer_name)
                palace_names = [item['layer_palace_name'] for item in sorted(
                    coordinates, key=lambda item: item['natal_coordinate']['iztro_array_index'])]
                if (not isinstance(raw_layer, dict) or not _integer(raw_layer.get('index'), 0, 11) or
                        raw_layer['index'] != layer['ming_coordinate']['iztro_array_index'] or
                        raw_layer.get('heavenlyStem') != stem or raw_layer.get('earthlyBranch') != layer['earthly_branch'] or
                        raw_layer.get('palaceNames') != palace_names or raw_layer.get('mutagen') != table[STEMS.index(stem)]):
                    raise ValueError('动态年/月来源原生层缺失或与准入事实不一致')
                if source_year != expected_lunar['lunarYear']:
                    raise ValueError('流年或流月来源农历年与实际查询日期不一致')
                if layer_name == 'monthly' and any(target_lunar[key] != expected_lunar[key]
                                                   for key in ('lunarMonth', 'lunarDay', 'isLeap')):
                    raise ValueError('流月与实际查询日期的农历月/闰月半月边界不一致')
                layer_result.update(status='admitted', transformations=rows, heavenly_stem=stem,
                                    earthly_branch=layer['earthly_branch'], ming_coordinate=deepcopy(layer['ming_coordinate']),
                                    domain_coordinates=deepcopy(coordinates))
                base['transformations'].extend(rows)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                layer_result['errors'] = [str(exc)]
        statuses = [r['status'] for r in base['layers'].values()]
        base['status'] = 'admitted' if all(s == 'admitted' for s in statuses) else ('partial' if 'admitted' in statuses else 'withheld')
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        base['errors'] = [str(exc)]
    return base


def _transform_topics(transforms, cards, themes, uncertain):
    rows = []
    for t in transforms:
        row = deepcopy(t)
        fact = row['fact']
        major = fact['type'] == 'major' and row['star'] in themes
        card = cards['ZW-E%02d' % (KINDS.index(row['kind']) + 1)]
        row.update(rule_id=card['rule_id'], status='conditional' if major and not uncertain else ('withheld' if major else 'facts_only'),
                   temporal_scope='long_term_natal_hypothesis' if row['layer'] == 'natal' else 'single_query_point_relative_to_fixed_natal_background',
                   reference='本命为长期假说；年/月相对本命背景，年月彼此分列且不量化比较',
                   topic=card['summary'] if major else None, star_theme=themes[row['star']]['theme'] if major else None,
                   countercheck=themes[row['star']]['question'] if major else None,
                   citation=deepcopy(card['citation']), net_effect='withheld',
                   identity='conditional_topic_not_measured_trait' if major else 'nonmajor_transformation_fact_only')
        row['unresolved'] = ['实际领域/目标、资源/职责及同目标反向需另核；不由主题推外部机会或人生结果',
                             '保留全部本宫星表与多化修饰；分量不相加、不抵消，交互与净效力未裁决']
        if major:
            row['theme_citation'] = deepcopy(themes[row['star']]['citation'])
        else:
            row['unresolved'].append('非十四主星：未登记独立主题，不借辅星分组或邻星补单星性质')
        if uncertain:
            row['unresolved'].append(UNCERTAIN)
        if _name(fact['domain']) == '疾厄':
            row.update(health_scope='general_life_reflection_only', medical_boundary=MEDICAL_BOUNDARY)
        cards[card['rule_id']]['rows'].append(row)
        rows.append(row)
    return rows


def _components(rows):
    groups = []
    for kind, key in (('same_palace', lambda r: r['fact']['branch']), ('same_star', lambda r: r['star'])):
        for value in sorted({key(row) for row in rows}, key=str):
            members = [row for row in rows if key(row) == value]
            if len(members) < 2:
                continue
            cross_layer = len({r['layer'] for r in members}) > 1
            groups.append(dict(kind=kind, key=value, component_ids=[r['id'] for r in members],
                               eligible_component_ids=[r['id'] for r in members if r['status'] == 'conditional'],
                               fact_only_component_ids=[r['id'] for r in members if r['status'] == 'facts_only'],
                               status='conditional' if any(r['status'] == 'conditional' for r in members) else 'withheld',
                               source_identity='author_extension_same_star_or_cross_layer' if cross_layer or kind == 'same_star' else 'modern_source_same_palace_coexistence',
                               interaction='unknown_may_change_component_expression_and_strength', net_effect='withheld',
                               calculation='no_sum_no_cancellation_no_net_auspiciousness'))
    return groups


def _body(chart, domains, uncertain):
    branch = chart.get('shenGongBranch')
    matches = [row for row in domains if row['branch'] == branch] if _integer(branch, 0, 11) else []
    flags = [p for p in chart['palaces'] if p.get('isShenGong')]
    if (len(matches) != 1 or _name(matches[0]['domain']) not in ('命', '迁移', '夫妻', '官禄', '财帛', '福德') or
            (flags and (len(flags) != 1 or flags[0]['branch'] != branch))):
        return dict(status='withheld', reason='身宫地支或六种唯一所在宫未核，不能猜位置')
    row = matches[0]
    return dict(status='withheld' if uncertain else 'conditional', branch=branch, domain=row['domain'],
                fact_path='chart.shenGongBranch', palace_path=row['facts'][0]['palace_path'] if row['facts'] else 'chart.palaces[%d]' % next(i for i,p in enumerate(chart['palaces']) if p['branch'] == branch),
                role=ROLES[_name(row['domain'])], identity='retractable_long_term_attention_hypothesis',
                comparison='与实际命宫主题、现实选择及相反行为比较；不是测得人格或一生唯一目标')


def _native_stage_placement(row):
    """Use the recorded age window and palace for the legacy stage contract."""
    if not isinstance(row, dict):
        return None
    numbers = tuple(row.get(key) for key in ('startAge', 'endAge', 'palaceBranch'))
    if any(type(value) is not int for value in numbers):
        return None
    return (*numbers, _name(row.get('palaceName')))


def _native_stage_order_error(chart, dxs):
    # The locked iztro getHoroscope output begins at the five-element class
    # in the soul palace. Both saved stage tables can repeat a stale order.
    first_age = dxs[0]['startAge']
    bureau = chart.get('wuxingJu')
    if len(dxs) != 12 or not 2 <= first_age <= 6:
        return '原生大限应有十二步，首段年龄须为五行局数'
    if bureau is not None and (not _integer(bureau, 2, 6) or first_age != bureau):
        return '原生大限起始年龄与五行局不一致'
    if any(dx['startAge'] != first_age + i * 10 or dx['endAge'] != first_age + i * 10 + 9
           for i, dx in enumerate(dxs)):
        return '原生大限年龄未按连续十年段排列'
    soul = chart['mingGongBranch']
    step = (dxs[1]['palaceBranch'] - soul) % 12
    if step not in (1, 11) or any(dx['palaceBranch'] != (soul + i * step) % 12 for i, dx in enumerate(dxs)):
        return '原生大限未从命宫按同一方向排列'
    birth, lunar = chart.get('birthInfo'), chart.get('lunarInfo')
    gender = birth.get('gender') if isinstance(birth, dict) else None
    year_branch = lunar.get('yearBranch') if isinstance(lunar, dict) else None
    if ((gender is not None and gender not in ('male', 'female')) or
            (year_branch is not None and not _integer(year_branch, 0, 11))):
        return '原生大限顺逆依据的出生性别或农历年支无效'
    if gender is not None and year_branch is not None:
        expected_step = 1 if (gender == 'male') == (year_branch % 2 == 0) else 11
        if step != expected_step:
            return '原生大限顺逆与出生性别、农历年支不一致'
    return None


def _stages(chart, birth_year, analysis_year, domains, year_errors, uncertain, replayed_stage_rows):
    result = dict(status='withheld', age_contract='analysis Gregorian year - original civil birth year + 1',
                  birth_year=birth_year, analysis_year=analysis_year, rows=[], errors=list(year_errors),
                  current_age=chart.get('currentAge'), current_index=chart.get('currentDaXianIndex'),
                  current_status='unverified', covered_window=None,
                  identity='author_adaptation_of_legacy_annual_age_contract',
                  precision='whole_Gregorian_year_half_open_windows_not_birthday_or_lunar_new_year',
                  optional_transform_fields='not_inferred_or_used', net_effect='withheld')
    if not _integer(birth_year, 1, 9999) or not _integer(analysis_year, 1, 9999) or analysis_year < birth_year:
        result['errors'].append('缺少有效原民用出生年或分析年，不能映射年度窗')
    birth_info = chart.get('birthInfo')
    chart_year = birth_info.get('year') if isinstance(birth_info, dict) else None
    if _integer(birth_year, 1, 9999) and _integer(chart_year, 1, 9999) and abs(birth_year - chart_year) > 1:
        result['errors'].append('原民用出生年与已解析排盘钟面年不相容')
    if result['errors']:
        return result
    if chart.get('currentAge') != analysis_year - birth_year + 1 or type(chart.get('currentAge')) is not int:
        result['errors'].append('currentAge与原民用出生年/分析年合同冲突')
        return result
    dxs = chart.get('daXians')
    index = chart.get('currentDaXianIndex')
    if not isinstance(dxs, list) or not dxs or not _integer(index, -1, len(dxs)-1):
        result['errors'].append('原生daXians或currentDaXianIndex缺失/无效')
        return result
    expected_indices, windows = [], []
    by_branch = {row['branch']: row for row in domains}
    stage_ages = {}
    for i, dx in enumerate(dxs):
        if (not isinstance(dx, dict) or not _integer(dx.get('startAge'), 1, 9999) or
                not _integer(dx.get('endAge'), dx['startAge'], 9999) or not _integer(dx.get('palaceBranch'), 0, 11) or dx.get('palaceBranch') not in by_branch or
                _name(dx.get('palaceName')) != _name(by_branch[dx['palaceBranch']]['domain'])):
            result['errors'].append('原生大限年龄或宫位字段无效')
            result['rows'] = []
            return result
        start, end = birth_year + dx['startAge'] - 1, birth_year + dx['endAge']
        if not 1 <= start < end <= 9999 or any(start < right and end > left for left,right in windows):
            result['errors'].append('原生大限年度窗超范围或相互重叠')
            result['rows'] = []
            return result
        windows.append((start,end))
        stage_ages.setdefault(dx['palaceBranch'], []).append((dx['startAge'], dx['endAge']))
        active = dx['startAge'] <= chart['currentAge'] <= dx['endAge']
        if active:
            expected_indices.append(i)
        domain = by_branch[dx['palaceBranch']]
        result['rows'].append(dict(index=i, native=deepcopy(dx), current=active,
                                   window=dict(start_inclusive='%04d-01-01' % start, end_exclusive='%04d-01-01' % end),
                                   domain=domain['domain'], domain_status=domain['status'],
                                   topic_fact_paths=[t['fact_path'] for t in domain['major_topics']],
                                   role=domain['role'], status='withheld' if uncertain or domain['status']=='withheld' else 'conditional',
                                   empty_palace=domain['empty_palace']))
    expected = expected_indices[0] if len(expected_indices) == 1 else -1
    if len(expected_indices) > 1 or index != expected:
        result.update(rows=[], errors=['currentDaXianIndex与原生年龄段不一致'])
        return result
    current_branch = dxs[expected]['palaceBranch'] if expected >= 0 else None
    for palace in chart['palaces']:
        branch = palace['branch']
        ages = palace.get('daXianAge')
        if ages is not None and (not isinstance(ages, (list, tuple)) or len(ages) != 2 or
                any(type(age) is not int for age in ages) or stage_ages.get(branch) != [tuple(ages)]):
            result.update(rows=[], errors=['原生大限daXians与本宫daXianAge年龄段不一致：' + palace['name']])
            return result
        current = palace.get('isCurrentDaXian')
        if current is not None and current is not (branch == current_branch):
            result.update(rows=[], errors=['原生大限currentDaXianIndex与本宫isCurrentDaXian标记不一致：' + palace['name']])
            return result
    order_error = _native_stage_order_error(chart, dxs)
    if order_error:
        result.update(rows=[], errors=[order_error])
        return result
    if (replayed_stage_rows is not None and
            [_native_stage_placement(row) for row in dxs] !=
            [_native_stage_placement(row) for row in replayed_stage_rows]):
        result.update(rows=[], errors=['保存的大限年龄段或宫位与原生复盘不一致'])
        return result
    if not uncertain:
        result.update(status='conditional', covered_window=dict(
            start_inclusive=result['rows'][0]['window']['start_inclusive'],
            end_exclusive=result['rows'][-1]['window']['end_exclusive']))
        if index >= 0:
            result['current_status'] = 'active'
        elif analysis_year < windows[0][0]:
            result['current_status'] = 'before_first_stage'
        else:
            result['current_status'] = 'after_last_stage'
    return result


def _with_reviewed_models(panel, native_chart, root, *, natal_transform_error=None):
    birth = native_chart.get('birthInfo') if isinstance(native_chart, dict) else None
    errors = []
    if not isinstance(birth, dict) or not _integer(birth.get('hour'), 0, 11):
        # The legacy panel does not retain birth-hour provenance. Add this
        # boundary only to the new cases.
        errors.append('缺少已核出生时辰，暂缓三项判例')
    panel['case_judgments'] = case_judgments.evaluate(
        panel, root=root, input_errors=errors, natal_transform_error=natal_transform_error)
    stage_errors = ['缺少已核出生时辰，暂缓阶段和夫妻模型'] if errors else []
    lunar = native_chart.get('lunarInfo') if isinstance(native_chart, dict) else None
    natal_year_stem = lunar.get('yearStem') if isinstance(lunar, dict) else None
    panel['stage_relationship'] = stage_relationship.evaluate(
        panel, root=root, input_errors=stage_errors, natal_year_stem=natal_year_stem,
        natal_transform_error=natal_transform_error)
    return panel


def _natal_solar_date(chart):
    born = chart.get('birthInfo') if isinstance(chart, dict) else None
    if isinstance(born, dict):
        try:
            return date(born['year'], born['month'], born['day']).isoformat()
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    return None


def natal_stage_basis(native_chart):
    """Extract stage-order evidence from a freshly computed natal chart."""
    return dict(gender=native_chart['birthInfo']['gender'],
                year_branch=native_chart['lunarInfo']['yearBranch'],
                wuxing_ju=native_chart['wuxingJu'])


def analyze(native_chart, birth_year, analysis_year, dynamic_facts=None, temporal_uncertainty=False, root=None,
            year_errors=None, *, birth_replay_error=None, brightness_conflicts=(),
            replayed_stage_rows=None, expected_target_date=None, expected_target_time_index=None,
            replayed_natal=None, verified_target_clock=None, birth_scope=None):
    """Return a new research panel. Never mutate native fields or infer civil birth year."""
    expected_query_point = None
    query_civil_year = None
    if expected_target_date is not None or expected_target_time_index is not None:
        if expected_target_date is None or expected_target_time_index is None:
            raise ValueError('预期动态日期和时辰索引须成对提供')
        if dynamic_facts is None:
            raise ValueError('预期查询点须与完整动态输入一起提供')
        try:
            parsed_date = date.fromisoformat(expected_target_date)
            if parsed_date.isoformat() != expected_target_date:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError('预期动态日期须为YYYY-MM-DD') from None
        if not _integer(expected_target_time_index, 0, 12):
            raise ValueError('预期动态时辰索引须为0至12的整数')
        expected_query_point = (expected_target_date, expected_target_time_index)
        query_civil_year = parsed_date.year
    panel = dict(version=PROFILE, profile=PROFILE, reading_use='conditional_module_only', status='withheld',
                 predictive_validity='unvalidated', prediction_guarantee=False,
                 scope='领域、四化分量、身宫关注和旧年度大限议题底稿；不是个人倾向、人格或净运势裁决',
                 temporal_uncertainty=bool(temporal_uncertainty), source_errors=[], input_errors=[],
                 domains=[], modules={}, transformations=[], dynamic=dict(status='not_requested' if dynamic_facts is None else 'withheld'),
                 old_native_fields='preserved_without_reclassification', effect_assessment='withheld')
    panel.update(birth_scope or {})
    if query_civil_year is not None and query_civil_year != analysis_year:
        panel['stage_query_scope'] = dict(
            status='analysis_year_mismatch', snapshot_analysis_year=analysis_year,
            panel_analysis_year=analysis_year, requested_analysis_year=query_civil_year,
            query_civil_year=query_civil_year, aligned_to_query=False,
            reason='旧当前大限对应存档分析年，本次查询需要同公历年的大限')
    try:
        source_root, catalog = knowledge._catalog(root)
        records = knowledge._records('ziwei', PROFILE, RECORD_IDS, catalog)
        themes = {r['star']: r for r in knowledge._star_themes(catalog)}
        if any(not isinstance(r.get('question'), str) or not r['question'].strip() for r in themes.values()):
            raise ValueError('既有十四主星反证问题登记不完整')
        contexts = [knowledge._with_citation(r, catalog) for r in catalog['records']
                    if r.get('system') == 'ziwei' and r.get('profile') == 'ziwei-domain-conditional'
                    and r.get('status') == 'usable' and not r.get('star')]
        if {r['id'] for r in contexts} != {'ziwei-domain-domains', 'ziwei-domain-brightness'} or len(contexts) != 2:
            raise ValueError('既有四宫角色或亮度说明登记不完整')
        table = _table(source_root)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        panel['source_errors'] = [str(exc)]
        return _with_reviewed_models(panel, native_chart, root)
    cards = {r['rule_id']: _card(r) for r in records}
    panel['modules'] = cards
    panel['background_citations'] = [deepcopy(r['citation']) for r in contexts]
    try:
        birth_conflicts = [error for error in (year_errors or []) if '出生' in error and '冲突' in error]
        if birth_replay_error:
            birth_conflicts.append(birth_replay_error)
        if birth_conflicts:
            raise ValueError('；'.join(birth_conflicts))
        palaces, facts = _chart(native_chart)
        birth_gaps = []
        if replayed_natal is not None:
            observed = replayed_natal['birthInfo']
            saved = native_chart.get('birthInfo')
            _check_saved_birth_header(saved, observed)
            header = {'birthInfo': saved}
            birth_gaps = _fill_missing_birth_header(header, observed)
            if birth_gaps:
                native_chart = {**native_chart, **header}
    except (ValueError, TypeError, KeyError) as exc:
        panel['input_errors'] = [str(exc)]
        for card in cards.values():
            card.update(status='withheld', unresolved=panel['input_errors'][:])
        return _with_reviewed_models(panel, native_chart, root)
    solar = _natal_solar_date(replayed_natal or native_chart)
    if solar is not None:
        panel['natal_solar_date'] = solar
    if _integer(birth_year, 1, 9999):
        panel['natal_civil_birth_year'] = birth_year
    if replayed_natal is not None:
        panel['natal_stage_basis'] = natal_stage_basis(replayed_natal)
    uncertain = bool(temporal_uncertainty)
    if brightness_conflicts:
        for fact in facts:
            if fact['path'] in brightness_conflicts:
                fact['brightness_conflict'] = True
        panel['natal_brightness_errors'] = dict.fromkeys(brightness_conflicts, '保存的原始亮度与复盘不一致')
    domains = [_domain(p, facts, themes, cards.get(DOMAIN_RULES.get(_name(p['name']))), uncertain) for p in palaces]
    domain_citation = next(r['citation'] for r in contexts if r['id'] == 'ziwei-domain-domains')
    for row in domains:
        if row['source_rule'] == 'ziwei-domain-conditional':
            row['citation'] = deepcopy(domain_citation)
    panel['domains'] = domains
    for row in domains:
        if row['source_rule'] in cards:
            card = cards[row['source_rule']]
            card.update(status=row['status'], rows=[deepcopy(row)], unresolved=row['missing_conditions'][:])
    natal_error = None
    try:
        transforms, natal_errors = _natal_transforms(native_chart, facts, table)
    except (ValueError, TypeError, KeyError) as exc:
        transforms, natal_errors = [], dict.fromkeys(KINDS, str(exc))
    if natal_errors:
        panel['natal_transform_errors'] = natal_errors
        natal_error = '；'.join(dict.fromkeys(natal_errors.values()))
        panel['input_errors'].append(natal_error)
    from ziwei_query_windows import latest_birth_for_order

    latest = latest_birth_for_order(panel) if dynamic_facts is not None else None
    dynamic = _dynamic(dynamic_facts, native_chart, facts, birth_year, table, expected_query_point,
                       replayed_natal, verified_target_clock, latest, birth_gaps)
    identity_errors = [error for error in (year_errors or []) if '出生' in error or 'birthYear' in error]
    if identity_errors and dynamic_facts is not None:
        dynamic.update(status='withheld', transformations=[], errors=identity_errors, layers={})
    panel['dynamic'] = dynamic
    transforms.extend(dynamic['transformations'])
    panel['transformations'] = _transform_topics(transforms, cards, themes, uncertain)
    for kind, rule in zip(KINDS, RULE_IDS[8:12]):
        card = cards[rule]
        card['status'] = ('conditional' if any(r['status']=='conditional' for r in card['rows']) else
                          'withheld' if not card['rows'] or any(r['status']=='withheld' for r in card['rows']) else 'facts_only')
        if kind in natal_errors:
            card['unresolved'].append(natal_errors[kind])
        if dynamic_facts is None:
            card['unresolved'].append('动态未请求，不补查年月')
        elif dynamic['status'] != 'admitted':
            card['unresolved'].append('动态有拒用或未准入层：见dynamic.errors及各层errors')
    components = _components(panel['transformations'])
    cards['ZW-E05'].update(rows=components, status='conditional' if any(r['status']=='conditional' for r in components) else 'withheld',
                            unresolved=['旧K05及动态面板状态保持；未核交互限制依赖它的方向，不改变其它已核单项事实'])
    if natal_errors:
        cards['ZW-E05']['unresolved'].append('本命四化按已核分量分组，缺项仍未知：' + '、'.join(natal_errors))
    body = _body(native_chart, domains, uncertain)
    cards['ZW-S01'].update(rows=[body], status=body['status'])
    if 'branch' in body and (replayed_natal is None or body['branch'] == replayed_natal.get('shenGongBranch')):
        panel['natal_body_branch'] = body['branch']
    stages = _stages(native_chart, birth_year, analysis_year, domains, year_errors or [], uncertain, replayed_stage_rows)
    cards['ZW-T02'].update(rows=[stages], status=stages['status'], unresolved=stages['errors'][:])
    panel['status'] = 'partial' if (panel['input_errors'] or brightness_conflicts or stages['errors'] or
                                   dynamic['status'] in ('withheld', 'partial')) else ('withheld' if uncertain else 'conditional')
    return _with_reviewed_models(panel, native_chart, root, natal_transform_error=natal_error)


def _optional_clock(value):
    if not isinstance(value, str) or len(value) <= 10:
        return None
    try:
        return parse_query_point(value)
    except ValueError:
        return None


def _clock_minute(clock):
    return clock.replace(second=0, microsecond=0, tzinfo=None)


def physical_birth_bounds(first, last):
    """Keep the earliest instant and the latest boundary on the physical clock."""
    return dict(earliest_utc=first.astimezone(UTC).isoformat(), latest_utc=last.astimezone(UTC).isoformat())


def _original_civil_clock(inputs, civil_date):
    if civil_date is None or not isinstance(inputs.get('hour'), str):
        return None
    hour, minute = (int(value) for value in inputs['hour'].split(':'))
    return datetime.combine(civil_date, time(hour, minute))


def _check_recorded_civil_clock(resolved, zone, time_info):
    civil = _optional_clock(time_info.get('civil'))
    if (('civil' in time_info and (civil is None or resolved.isoformat() != civil.isoformat())) or
            ('iana_zone' in time_info and time_info['iana_zone'] != zone) or
            ('fold' in time_info and time_info['fold'] != resolved.fold) or
            ('instant_bj' in time_info and _optional_clock(time_info['instant_bj']) != resolved.astimezone(UTC))):
        raise ValueError('已存出生瞬间、时区或 fold 与原出生输入不一致')


def _recorded_birth_bounds(inputs, time_info, civil_date, scenario_bounds=None):
    zone, offset = inputs.get('timezone'), inputs.get('utc_offset')
    local = _original_civil_clock(inputs, civil_date)
    if local is None or (zone is None and offset is None):
        if scenario_bounds is not None:
            raise ValueError('缺少复核出生误差枚举的原民用钟面或时区')
        return None
    minutes = inputs.get('uncertainty_minutes', 0)
    if type(minutes) not in (int, float) or not 0 <= minutes < float('inf'):
        raise ValueError('原出生误差须为有限非负分钟数')
    resolved = resolve_civil(local, offset, zone, inputs.get('fold'))
    _check_recorded_civil_clock(resolved, zone, time_info)
    instant = resolved.astimezone(UTC)
    delta = timedelta(minutes=minutes)
    check_recorded_scenario_bounds(inputs, scenario_bounds, instant, delta)
    return physical_birth_bounds(instant - delta, instant + delta)


def _apparent_correction(inputs, civil, qizheng):
    eot = snapshot_apparent_correction(civil, inputs, qizheng)
    if eot is not None:
        return eot
    return qizheng.get('eot_minutes') if isinstance(qizheng, dict) else None


def _solar_input_conflicts(inputs, time_info, timezone_source, qizheng):
    """Compare the saved solar clock with its original input witnesses."""
    field = {'mean-solar': 'mean_solar', 'apparent-solar': 'apparent_solar'}.get(str(inputs.get('time_basis')))
    civil = _optional_clock(time_info.get('civil'))
    if field is None or civil is None or civil.utcoffset() is None:
        return []
    errors = []
    zone, observed_zone = inputs.get('timezone'), time_info.get('iana_zone')
    if 'timezone' in inputs and 'iana_zone' in time_info and zone != observed_zone:
        errors.append('原出生时区与time.iana_zone冲突')
    fold, observed_fold = inputs.get('fold'), time_info.get('fold')
    if _integer(fold, 0, 1) and _integer(observed_fold, 0, 1) and fold != observed_fold:
        errors.append('原出生时区fold与time.fold冲突')
    if isinstance(timezone_source, dict):
        source_zone, saved_digest = timezone_source.get('zone'), timezone_source.get('tzif_sha256')
        if 'timezone' in inputs and isinstance(source_zone, str) and source_zone != zone:
            errors.append('原出生时区与已记录TZif来源冲突')
        selected_fold = fold if _integer(fold, 0, 1) else observed_fold
        if (not errors and isinstance(zone, str) and source_zone == zone and
                isinstance(saved_digest, str) and saved_digest and _integer(selected_fold, 0, 1)):
            try:
                iana_zone(zone)
                current_digest = timezone_provenance(zone).get('tzif_sha256')
            except (ImportError, OSError, ValueError):
                current_digest = None
            if saved_digest == current_digest:
                try:
                    resolved = resolve_civil(civil.replace(tzinfo=None), zone=zone, fold=selected_fold)
                except (ValueError, OverflowError):
                    errors.append('原出生时区和fold与已记录TZif规则冲突')
                else:
                    if civil.utcoffset() != resolved.utcoffset():
                        errors.append('原出生时区和fold与time.civil的UTC偏移冲突')
    offset = inputs.get('utc_offset')
    if zone is None and observed_zone is None and offset is not None:
        try:
            expected_offset = fixed_utc_offset(offset).utcoffset(None)
        except ValueError:
            errors.append('原出生固定UTC偏移无效')
        else:
            if civil.utcoffset() != expected_offset:
                errors.append('原出生固定UTC偏移与time.civil冲突')
    instant_bj = _optional_clock(time_info.get('instant_bj'))
    if instant_bj is not None and instant_bj.utcoffset() is not None and civil != instant_bj:
        errors.append('time.civil与time.instant_bj出生瞬间冲突')
    lon = inputs.get('lon')
    if type(lon) not in (int, float) or not -180 <= lon <= 180:
        return errors
    corrections = {'mean_solar': 0}
    if field == 'apparent_solar':
        try:
            eot = _apparent_correction(inputs, civil, qizheng)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if type(eot) in (int, float):
                corrections[field] = eot
    for clock_field, correction in corrections.items():
        clock = _optional_clock(time_info.get(clock_field))
        if clock is None and clock_field == field:
            clock_field = 'chart_clock'
            clock = _optional_clock(time_info.get(clock_field))
        if clock is None:
            continue
        try:
            expected = solar_clock(civil, lon, correction)
        except (ValueError, OverflowError):
            errors.append(f'time.{clock_field}与原出生太阳钟面输入冲突')
        else:
            if _clock_minute(clock) != _clock_minute(expected):
                errors.append(f'time.{clock_field}与原出生民用瞬间、经度或均时差冲突')
    return errors


def _snapshot_replay_clock(inputs, time_info, native_inputs, civil_date, qizheng):
    """Recover the original chart clock, or the explicitly saved legacy shichen."""
    local = _original_civil_clock(inputs, civil_date)
    basis = inputs.get('time_basis')
    if local is not None and basis == 'civil':
        return local
    lon = inputs.get('lon')
    if basis in ('mean-solar', 'apparent-solar') and lon is not None:
        civil = _optional_clock(time_info.get('civil'))
        if civil is not None and local is not None and civil.replace(tzinfo=None) != local:
            raise ValueError('保存的民用钟面与原出生时分不一致')
        if civil is None and local is not None and ('utc_offset' in inputs or inputs.get('timezone')):
            civil = resolve_civil(local, inputs.get('utc_offset', 8), inputs.get('timezone'), inputs.get('fold'))
        if civil is not None and civil.utcoffset() is not None:
            eot = _apparent_correction(inputs, civil, qizheng) if basis == 'apparent-solar' else 0
            if eot is not None:
                return solar_clock(civil, lon, eot)
    clock = _optional_clock(time_info.get('chart_clock'))
    if clock is not None:
        return clock
    shichen = native_inputs.get('shichenIndex')
    if _integer(shichen, 0, 11) and isinstance(native_inputs.get('solar'), str):
        return datetime.combine(parse_birth_date(native_inputs['solar']), time(2 * shichen))
    raise ValueError('缺少可复盘的原出生钟面或旧紫微输入')


def _snapshot_birth_conflicts(inputs, time_info, native_inputs, chart, civil_date):
    """Compare present clock witnesses in their own frames, without reconstruction."""
    errors = []
    input_clock = None
    if isinstance(inputs.get('hour'), str):
        try:
            hour, minute = (int(part) for part in inputs['hour'].split(':'))
        except ValueError:
            pass
        else:
            input_clock = (hour, minute)
    civil = _optional_clock(time_info.get('civil'))
    if civil is not None:
        if civil_date is not None and civil_date != civil.date():
            errors.append('原input.solar与time.civil出生日期冲突')
        if input_clock is not None and input_clock != (civil.hour, civil.minute):
            errors.append('原input.hour与time.civil出生时分冲突')
    clock = _optional_clock(time_info.get('chart_clock'))
    selected_field = {'civil': 'civil', 'mean-solar': 'mean_solar',
                      'apparent-solar': 'apparent_solar'}.get(str(inputs.get('time_basis')))
    selected = _optional_clock(time_info.get(selected_field))
    if clock is not None and selected is not None and _clock_minute(clock) != _clock_minute(selected):
        errors.append('time.chart_clock与所选口径的出生钟面冲突')
    clock = clock or selected
    birth = chart.get('birthInfo') if isinstance(chart, dict) else None
    if not isinstance(birth, dict):
        birth = {}
    dates = set()
    try:
        dates.add(date.fromisoformat(native_inputs.get('solar')))
    except (TypeError, ValueError):
        pass
    try:
        dates.add(date(birth.get('year'), birth.get('month'), birth.get('day')))
    except (TypeError, ValueError):
        pass
    hours = {hour for hour in (native_inputs.get('shichenIndex'), birth.get('hour')) if _integer(hour, 0, 11)}
    if clock is not None:
        dates.add(clock.date())
        hours.add(((clock.hour + 1) // 2) % 12)
    if selected_field == 'civil':
        if civil_date is not None:
            dates.add(civil_date)
        if input_clock is not None and 0 <= input_clock[0] < 24 and 0 <= input_clock[1] < 60:
            hours.add(((input_clock[0] + 1) // 2) % 12)
    if len(dates) > 1:
        errors.append('排盘钟面与紫微输入或原盘出生日期冲突')
    if len(hours) > 1:
        errors.append('排盘钟面与紫微输入或原盘出生时辰冲突')
    declared_gender = {'男': 'male', '女': 'female'}.get(str(inputs.get('sex')))
    genders = {value for value in (declared_gender, native_inputs.get('gender'), birth.get('gender'))
               if value in ('male', 'female')}
    if len(genders) > 1:
        errors.append('原输入与紫微输入或原盘出生性别冲突')
    return errors


def _candidate_identity(solar, hour, birth_year):
    if not _integer(hour, 0, 11) or not _integer(birth_year, 1, 9999):
        raise ValueError('紫微候选集合的出生时辰或原民用年份无效')
    try:
        if date.fromisoformat(solar).isoformat() != solar:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('紫微候选集合的出生日期无效') from None
    return solar, hour, birth_year


def _candidate_groups(candidates, variants):
    groups = {}
    for number, variant in enumerate(variants, 1):
        fields = variant['fields']
        identity = _candidate_identity(fields.get('ziwei.solar_date'), fields.get('ziwei.shichen_index'),
                                       fields.get('ziwei.birth_year'))
        groups.setdefault(identity, []).append((f'candidate-{number}', variant))
    expected_ids = {key: f'ziwei-candidate-{index}' for index, key in enumerate(groups, 1)}
    seen = set()
    for candidate in candidates:
        identity = candidate.get('input') if isinstance(candidate, dict) else None
        if not isinstance(identity, dict) or not isinstance(candidate.get('id'), str) or not candidate['id']:
            raise ValueError('紫微候选集合含无效候选记录')
        key = _candidate_identity(identity.get('solar_date'), identity.get('shichen_index'), identity.get('birth_year'))
        if key not in groups or key in seen:
            raise ValueError('紫微候选集合与枚举身份不符或重复')
        if candidate['id'] != expected_ids[key]:
            raise ValueError('紫微候选 ID 与原枚举身份顺序冲突')
        if candidate.get('scenario_ids') != [alias for alias, _ in groups[key]]:
            raise ValueError('紫微候选的出生身份与可达枚举标识冲突')
        seen.add(key)
    if not groups or seen != groups.keys():
        raise ValueError('紫微候选集合未覆盖全部枚举身份')
    return groups


def _witness_identity(witness_utc, clock, zone):
    return clock.date().isoformat(), ((clock.hour + 1) // 2) % 12, witness_utc.astimezone(zone).year


def _check_candidate_intervals(groups, start, end, zone, basis, lon):
    """Verify saved coverage and Ziwei identity across the modeled clock cuts."""
    message = '出生误差枚举区间未完整覆盖或分段损坏'
    segments = []
    for identity, members in groups.items():
        for _, variant in members:
            intervals = variant.get('intervals')
            if not isinstance(intervals, list) or not intervals:
                raise ValueError(message)
            for interval in intervals:
                if not isinstance(interval, dict) or type(interval.get('end_inclusive')) is not bool:
                    raise ValueError(message)
                left = _optional_clock(interval.get('start_utc'))
                right = _optional_clock(interval.get('end_utc'))
                if left is None or right is None or left.utcoffset() is None or right.utcoffset() is None or left > right:
                    raise ValueError(message)
                segments.append((left, right, interval['end_inclusive'], identity))
    edge = start
    ordered = sorted(segments)
    for index, (left, right, inclusive, _) in enumerate(ordered):
        last = index == len(ordered) - 1
        if left != edge or inclusive != last or (left == right and not last):
            raise ValueError(message)
        edge = right
    if edge != end:
        raise ValueError(message)
    cuts = scenario_clock_boundaries(start, end, zone, basis, lon)
    for left, right, inclusive, identity in ordered:
        checkpoints = {point for point in cuts if left < point < right}
        checkpoints.add(left)
        if inclusive:
            checkpoints.add(right)
        if any(_witness_identity(point, scenario_clock_at(point, zone, basis, lon), zone) != identity
               for point in checkpoints):
            raise ValueError('出生误差枚举分段与原输入的紫微出生日期、时辰或民用年份冲突')


def _native_birth_chart(clock, sex, birth_year):
    """Replay natal facts independently of any saved target year."""
    payload, note = run_ziwei(clock.year, clock.month, clock.day, clock.hour, clock.minute,
                              sex, None, None, birth_year, birth_year, output_format='json')
    if payload is None:
        raise ValueError('无法用内置紫微引擎复盘：' + note)
    return json.loads(payload)['chart']


def _verify_candidate_chart(chart, clock, sex, birth_year):
    """Confirm saved natal placements independently of the saved birth header."""
    native = _native_birth_chart(clock, sex, birth_year)
    try:
        _, native_facts = _chart(native)
        _, saved_facts = _chart(chart)
        _unverified_static_fields(native, chart, native_facts, saved_facts,
                                  _table(Path(__file__).resolve().parents[1]),
                                  mismatch='本命命身宫、星表或农历记录不一致', allow_missing_chart_annotations=True)
        for key in ('wuxingJu', 'wuxingJuName', 'ziweiPos'):
            if chart.get(key) is not None and chart[key] != native[key]:
                raise ValueError('五行局或紫微星位置不一致')
    except ValueError as exc:
        raise ValueError('所选紫微候选的原盘与出生见证重算不一致：' + str(exc)) from exc
    return native


def _replay_snapshot_chart(chart, inputs, time_info, native_inputs, civil_date, qizheng):
    clock = _snapshot_replay_clock(inputs, time_info, native_inputs, civil_date, qizheng)
    sex = inputs.get('sex', {'male': '男', 'female': '女'}.get(native_inputs.get('gender')))
    if sex not in ('男', '女'):
        raise ValueError('缺少原出生性别')
    # A neutral age year for replay never supplies a missing civil birth year to T02.
    native = _native_birth_chart(clock, sex, clock.year)
    return native, _verify_replayed_placements(chart, native)


def _verify_replayed_placements(chart, native):
    """Check natal placement and keep present brightness conflicts scoped."""
    _check_saved_birth_header(chart.get('birthInfo'), native['birthInfo'])
    _, facts = _chart(chart)
    include_body = chart.get('shenGongBranch') is not None
    if _static_placements(chart, include_body=include_body) != _static_placements(native, include_body=include_body):
        raise ValueError('出生标头所对应的命身宫或实际星表不一致')
    lunar = chart.get('lunarInfo')
    if isinstance(lunar, dict):
        for key, expected in native['lunarInfo'].items():
            if key not in lunar or (key == 'yearStem' and lunar[key] is None):
                continue
            if lunar[key] != expected or (key == 'yearStem' and type(lunar[key]) is not int):
                raise ValueError('出生农历记录不一致')
    actual_brightness = {(p['branch'], s['name']): s.get('brightnessRaw')
                         for p in native['palaces'] for s in p['stars'] if s['type'] == 'major'}
    brightness_conflicts = [
        fact['path'] for fact in facts
        if fact['type'] == 'major' and fact['brightness_raw'] in case_judgments.RAW_BRIGHTNESS
        and fact['brightness_raw'] != actual_brightness[(fact['branch'], fact['name'])]
    ]
    return brightness_conflicts


def birth_candidate_year_gap(analysis_year, birth_year):
    """Describe the original year constraint without substituting a reference year."""
    return (f'原分析年 {analysis_year} 早于该候选的民用出生年 {birth_year}，该年无当前大限。'
            f'读取该候选的本命或后续大限时，请保留原出生参数，以 --analysis-year {birth_year} 或更晚的所问公历年重新建档。')


def _select_birth_candidate(snapshot, candidate_id, inputs, civil_date):
    """Resolve one witness from the snapshot, rather than infer a birth time."""
    time_info = snapshot.get('time', {})
    if not isinstance(time_info, dict):
        raise ValueError('候选紫微盘的已存出生时间记录须为对象')
    minutes = inputs.get('uncertainty_minutes')
    if (civil_date is None or inputs.get('enumerate_scenarios') is not True or
            type(minutes) not in (int, float) or not 0 < minutes <= 120):
        raise ValueError('候选紫微盘需要原民用出生时间与已枚举的非零误差区间')
    basis, lon = inputs.get('time_basis'), inputs.get('lon')
    if basis not in ('civil', 'mean-solar', 'apparent-solar'):
        raise ValueError('紫微候选需要原输入的排盘钟面口径')
    if lon is None and basis != 'civil':
        raise ValueError('太阳时紫微候选需要原输入的出生地经度')
    if lon is not None and (type(lon) not in (int, float) or not -180 <= lon <= 180):
        raise ValueError('紫微候选的原出生地经度无效')
    zone, offset = inputs.get('timezone'), inputs.get('utc_offset', 8)
    if ((zone is not None and not isinstance(zone, str)) or
            type(offset) not in (int, float) or not -14 <= offset <= 14):
        raise ValueError('紫微候选的原出生时区或固定偏移无效')
    local = _original_civil_clock(inputs, civil_date)
    if local is None or (zone is None and 'utc_offset' not in inputs):
        saved_civil = _optional_clock(time_info.get('civil'))
        if saved_civil is None or saved_civil.utcoffset() is None:
            raise ValueError('候选紫微盘缺少原出生时分或可核的出生偏移')
        if local is None:
            local = saved_civil.replace(tzinfo=None)
    resolved = resolve_civil(local, offset, zone, inputs.get('fold'))
    _check_recorded_civil_clock(resolved, zone, time_info)
    checked_time = dict(time_info, civil=resolved.isoformat())
    conflicts = _snapshot_birth_conflicts(inputs, checked_time, {}, None, civil_date)
    provenance = snapshot.get('provenance')
    if isinstance(provenance, dict) and 'timezone' in inputs and 'timezone_source' in provenance:
        check_timezone_source(provenance['timezone_source'], zone)
    conflicts.extend(_solar_input_conflicts(inputs, checked_time, None, snapshot.get('qizheng')))
    if conflicts:
        raise ValueError('；'.join(conflicts))
    birth_zone = resolved.tzinfo
    scenarios = snapshot.get('scenarios')
    comparison = snapshot.get('ziwei_scenario_comparison')
    if not isinstance(scenarios, dict) or not isinstance(comparison, dict):
        raise ValueError('缺少同一快照的出生误差枚举或紫微候选对照')
    coverage = scenarios.get('coverage')
    expected_coverage = ('numerical_witnesses_not_exhaustive' if basis == 'apparent-solar'
                         else 'complete_for_modeled_boundaries_not_astronomical_error')
    if coverage != expected_coverage or comparison.get('coverage') != coverage:
        raise ValueError('紫微候选对照与出生误差枚举的覆盖标记缺失或冲突')
    start = _optional_clock(scenarios.get('start_utc'))
    end = _optional_clock(scenarios.get('end_utc'))
    delta = timedelta(minutes=minutes)
    center = resolved.astimezone(UTC)
    if start != center - delta or end != center + delta:
        raise ValueError('出生误差枚举与原民用出生时间或误差区间冲突')
    candidates = comparison.get('candidates')
    variants = scenarios.get('variants')
    if (not isinstance(candidates, list) or not isinstance(variants, list) or
            any(not isinstance(row, dict) or not isinstance(row.get('fields'), dict) for row in variants)):
        raise ValueError('紫微候选或出生误差枚举结构无效')
    groups = _candidate_groups(candidates, variants)
    matches = [(i, row) for i, row in enumerate(candidates)
               if row['id'] == candidate_id]
    if not isinstance(candidate_id, str) or len(matches) != 1:
        raise ValueError('本快照未找到唯一的紫微候选 ID：' + str(candidate_id))
    index, candidate = matches[0]
    identity = candidate.get('input')
    chart = candidate.get('chart')
    solar, hour, birth_year = identity['solar_date'], identity['shichen_index'], identity['birth_year']
    if not isinstance(chart, dict) or candidate.get('degradation'):
        analysis_year = comparison.get('analysis_year')
        if chart is None and _integer(analysis_year, 1, 9999) and analysis_year < birth_year:
            raise ValueError(birth_candidate_year_gap(analysis_year, birth_year))
        raise ValueError('所选紫微候选缺少有效原盘，请查本候选的降级记录')
    members = groups[(solar, hour, birth_year)]
    first = members[0][1]
    dut1_seconds = 0.0
    if basis == 'apparent-solar':
        dut1_seconds = snapshot_dut1_seconds(inputs, snapshot.get('qizheng')) or 0.0
    if any(candidate.get(key) != first.get(key) for key in ('witness_utc', 'chart_clock')):
        raise ValueError('所选紫微候选的出生见证与可达枚举记录冲突')
    for _, witness in members:
        witness_utc = _optional_clock(witness.get('witness_utc'))
        clock = _optional_clock(witness.get('chart_clock'))
        if (witness_utc is None or witness_utc.utcoffset() is None or
                not start <= witness_utc <= end or clock is None):
            raise ValueError('所选紫微候选的出生见证与可达枚举记录冲突')
        if clock != scenario_clock_at(witness_utc, birth_zone, basis, lon, dut1_seconds=dut1_seconds):
            raise ValueError('所选紫微候选的见证钟面与原输入时区、经度或口径冲突，请按原参数重建')
        if _witness_identity(witness_utc, clock, birth_zone) != (solar, hour, birth_year):
            raise ValueError('所选紫微候选的出生身份与可达枚举见证冲突')
    if basis == 'apparent-solar':
        # These points were always sampled, even though the coverage is non-exhaustive.
        for point in scenario_clock_boundaries(start, end, birth_zone, basis, lon):
            clock = scenario_clock_at(point, birth_zone, basis, lon, dut1_seconds=dut1_seconds)
            if _witness_identity(point, clock, birth_zone) not in groups:
                raise ValueError('真太阳时已采样的出生见证缺少对应紫微候选')
    else:
        _check_candidate_intervals(groups, start, end, birth_zone, basis, lon)
    gender = {'男': 'male', '女': 'female'}.get(str(inputs.get('sex')))
    born_on = date.fromisoformat(solar)
    if gender is None:
        raise ValueError('所选紫微候选的原盘与出生见证或原输入性别冲突')
    try:
        _check_saved_birth_header(chart.get('birthInfo'),
                                  dict(year=born_on.year, month=born_on.month, day=born_on.day,
                                       hour=hour, gender=gender))
    except ValueError as exc:
        raise ValueError('所选紫微候选的原盘与出生见证或原输入性别冲突：' + str(exc)) from exc
    expected = enumerate_scenarios(resolved, minutes, basis, lon, inputs['sex'], dut1_seconds=dut1_seconds)
    if scenario_witnesses(scenarios) != scenario_witnesses(expected):
        raise ValueError('紫微候选的原枚举见证或标识与原出生输入重算不一致，请按原参数重建')
    replayed = _verify_candidate_chart(chart, datetime.fromisoformat(first['chart_clock']), inputs['sex'], birth_year)
    context = dict(id=candidate_id, scenario_ids=deepcopy(candidate['scenario_ids']), coverage=coverage,
                   witness_utc=candidate['witness_utc'], chart_clock=candidate['chart_clock'],
                   input=deepcopy(identity), chart_path=f'ziwei_scenario_comparison.candidates[{index}].chart',
                   scope='selected_birth_witness_only', birth_time_confirmed=False, time_basis=basis)
    if basis != 'apparent-solar':
        intervals = sorted((dict(interval) for _, variant in members for interval in variant['intervals']),
                           key=lambda interval: _optional_clock(interval['start_utc']))
        if basis == 'civil':
            # Verified enumerated segments already split at every change of civil offset.
            for interval in intervals:
                left = _optional_clock(interval['start_utc'])
                interval['civil_offset_seconds'] = int(left.astimezone(birth_zone).utcoffset().total_seconds())
        context['reachable_utc_intervals'] = intervals
        start = _optional_clock(intervals[0]['start_utc'])
        end = _optional_clock(intervals[-1]['end_utc'])
    context['birth_time_bounds'] = physical_birth_bounds(start, end)
    return chart, birth_year, context, replayed


def _chart_for_analysis_year(chart, verified_natal, birth_year, target_year):
    """Replay only the requested annual stage using the already verified birth."""
    born = verified_natal['birthInfo']
    sex = {'male': '男', 'female': '女'}[born['gender']]
    raw, note = run_ziwei(born['year'], born['month'], born['day'], None, None, sex, None, None,
                          age_year=target_year, birth_year=birth_year, output_format='json',
                          shichen=BRANCHES[born['hour']])
    if raw is None:
        raise ValueError('无法复核所问公历年的原生大限：' + note)
    wrapper = json.loads(raw)
    native = wrapper['chart']
    if (wrapper['input'].get('ageYear') != target_year or wrapper['input'].get('birthYear') != birth_year or
            _static_identity(native) != _static_identity(verified_natal) or native['daXians'] != verified_natal['daXians']):
        raise ValueError('所问公历年复盘的出生身份、分析年或原生大限表不一致')
    updated = deepcopy(chart)
    updated['currentAge'] = native['currentAge']
    updated['currentDaXianIndex'] = native['currentDaXianIndex']
    current_flags = {row['branch']: row['isCurrentDaXian'] for row in native['palaces']}
    for palace in updated['palaces']:
        if palace.get('isCurrentDaXian') is not None:
            palace['isCurrentDaXian'] = current_flags[palace['branch']]
    return updated


def _verify_target_clock(text, expected_date, expected_index, latest_birth):
    clock = _optional_clock(text)
    if (clock is None or clock.utcoffset() is None or clock.date().isoformat() != expected_date or
            not _integer(expected_index, 0, 12) or (clock.hour + 1) // 2 != expected_index):
        raise ValueError('带偏移的预期查询钟面须匹配独立确认的日期和时辰索引')
    if latest_birth is None or clock < latest_birth:
        raise ValueError('须按原始出生资料核对查询钟面已到达出生范围的最晚边界')
    return clock


def _replay_missing_current_fields(chart, verified_natal, birth_year, analysis_year):
    """Reconstruct absent redundant fields for validation of the saved stage table."""
    if (not isinstance(chart, dict) or verified_natal is None or
            not isinstance(chart.get('daXians'), list) or not _integer(birth_year, 1, 9999) or
            not _integer(analysis_year, birth_year, 9999)):
        return {}
    if 'currentAge' in chart and 'currentDaXianIndex' in chart:
        return {}
    age = analysis_year - birth_year + 1
    index = next((i for i, row in enumerate(verified_natal['daXians'])
                  if row['startAge'] <= age <= row['endAge']), -1)
    return {key: value for key, value in (('currentAge', age), ('currentDaXianIndex', index))
            if key not in chart}


def _analyze_snapshot_year(chart, verified_natal, birth_year, analysis_year, requested_analysis_year, *,
                           expected_target_civil=None, birth_scope=None, **options):
    verified_clock = None
    if expected_target_civil is not None:
        from ziwei_query_windows import latest_birth_for_order

        if options.get('birth_replay_error'):
            raise ValueError(options['birth_replay_error'])
        order_scope = dict(birth_scope or {}, natal_solar_date=_natal_solar_date(verified_natal or chart),
                           temporal_uncertainty=bool(options.get('temporal_uncertainty')))
        verified_clock = _verify_target_clock(expected_target_civil, options.get('expected_target_date'),
                                              options.get('expected_target_time_index'), latest_birth_for_order(order_scope))
    query_before_civil_birth_year = (verified_clock is not None and birth_year is not None and
                                     verified_clock.year < birth_year)
    if (requested_analysis_year is not None and birth_year is not None and requested_analysis_year < birth_year and
            (not query_before_civil_birth_year or requested_analysis_year != verified_clock.year)):
        raise ValueError('所问分析年须不早于原民用出生年')
    replayed_fields = {}
    if (requested_analysis_year is not None and not query_before_civil_birth_year and
            not (birth_scope or {}).get('birth_time_error')):
        replayed_fields = _replay_missing_current_fields(chart, verified_natal, birth_year, analysis_year)
        if replayed_fields:
            chart = {**chart, **replayed_fields}
            options['replayed_stage_rows'] = verified_natal['daXians']
    result = analyze(chart, birth_year, analysis_year, replayed_natal=verified_natal,
                     verified_target_clock=verified_clock, birth_scope=birth_scope, **options)
    if query_before_civil_birth_year:
        result['stage_query_scope'] = dict(
            status='before_birth_civil_year', snapshot_analysis_year=analysis_year,
            panel_analysis_year=analysis_year, requested_analysis_year=requested_analysis_year,
            query_civil_year=verified_clock.year, aligned_to_query=False,
            reason='查询时刻已出生，当地公历年早于原民用出生年，该查询年无旧大限')
        return result
    birth_time_unverified = result['dynamic'].get('birth_time_status') == 'birth_time_unverified'
    expected_date = options.get('expected_target_date')
    query_year = int(expected_date[:4]) if expected_date else None
    if requested_analysis_year is None and not birth_time_unverified and (
            query_year is None or query_year != analysis_year):
        return result
    scope = dict(status='withheld', snapshot_analysis_year=analysis_year, panel_analysis_year=analysis_year,
                 requested_analysis_year=requested_analysis_year, query_civil_year=query_year,
                 aligned_to_query=None if query_year is None else query_year == analysis_year)
    if birth_time_unverified:
        scope.update(status='birth_time_unverified', reason='查询钟面尚未证明已经出生，暂缓该点当前大限')
    elif result['modules'].get('ZW-T02', {}).get('status') != 'conditional' or verified_natal is None:
        scope['reason'] = '原出生范围或原大限表未复核，无法确认所问公历年的当前大限'
    else:
        try:
            if requested_analysis_year is not None and requested_analysis_year != analysis_year:
                updated = _chart_for_analysis_year(chart, verified_natal, birth_year, requested_analysis_year)
                refreshed = analyze(updated, birth_year, requested_analysis_year,
                                    replayed_natal=verified_natal, verified_target_clock=verified_clock,
                                    birth_scope=birth_scope, **options)
                if refreshed['modules'].get('ZW-T02', {}).get('status') != 'conditional':
                    raise ValueError('所问公历年的原生大限未通过当前阶段核对')
                result = refreshed
            panel_year = analysis_year if requested_analysis_year is None else requested_analysis_year
            scope.update(status='verified', panel_analysis_year=panel_year,
                         aligned_to_query=None if query_year is None else query_year == panel_year)
            if scope['aligned_to_query'] is False:
                scope.update(status='analysis_year_mismatch', reason='指定的大限分析年与动态查询公历年不同')
            if replayed_fields:
                scope['replayed_current_fields'] = list(replayed_fields)
        except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            scope['reason'] = str(exc)
    result['stage_query_scope'] = scope
    return result


def _check_requested_analysis_year(requested_analysis_year, dynamic_facts,
                                   expected_target_date, expected_target_time_index):
    if requested_analysis_year is not None and not _integer(requested_analysis_year, 1, 9999):
        raise ValueError('所问分析年须为 1 至 9999 的有效公历年份')
    if (requested_analysis_year is not None and dynamic_facts is not None and
            (expected_target_date is None or expected_target_time_index is None)):
        raise ValueError('指定大限分析年并续算动态时，须提供本次请求的预期日期与时辰索引')


def analyze_native_shichen(snapshot, birth_date, shichen, sex, dynamic_facts=None, root=None, *,
                           zone=None, utc_offset=None, expected_target_date=None,
                           expected_target_time_index=None, expected_target_civil=None,
                           requested_analysis_year=None):
    """Check a saved raw chart against an independently confirmed civil birth branch."""
    from ziwei_birth_time_candidates import civil_span_record, native_shichen_chart

    _check_requested_analysis_year(requested_analysis_year, dynamic_facts,
                                   expected_target_date, expected_target_time_index)
    if dynamic_facts is not None and (expected_target_date is None or expected_target_time_index is None):
        raise ValueError('民用时辰动态续算须提供本次请求的预期日期与时辰索引')
    if (not isinstance(birth_date, str) or not isinstance(shichen, str) or
            shichen not in tuple(BRANCHES) or sex not in ('男', '女')):
        raise ValueError('须独立确认原公历民用出生日期、时辰和性别')
    day = parse_birth_date(birth_date)
    index = BRANCHES.index(shichen)
    if ((zone is not None and (not isinstance(zone, str) or utc_offset is not None)) or
            (utc_offset is not None and type(utc_offset) not in (int, float))):
        raise ValueError('出生时区或固定 UTC 偏移无效')
    spans = None
    if zone is not None or utc_offset is not None:
        tz = iana_zone(zone) if zone is not None else None
        spans = [civil_span_record(left, right, tz) for left, right in civil_shichen_spans(day, shichen, utc_offset, zone)]
    source = snapshot.get('input') if isinstance(snapshot, dict) else None
    chart = snapshot.get('chart') if isinstance(snapshot, dict) else None
    if not isinstance(source, dict) or not isinstance(chart, dict) or snapshot.get('schema_version') != 1:
        raise ValueError('民用时辰续算须提供原生紫微 JSON')
    analysis_year = source.get('ageYear')
    if (not isinstance(source.get('solar'), str) or parse_birth_date(source['solar']) != day or
            not _integer(source.get('shichenIndex'), 0, 11) or source['shichenIndex'] != index or
            not _integer(source.get('birthYear'), 1, 9999) or source['birthYear'] != day.year or
            source.get('gender') != {'男': 'male', '女': 'female'}[sex] or
            source.get('temporalUncertainty', False) is not False or
            not _integer(analysis_year, day.year, 9999)):
        raise ValueError('原生紫微输入与独立确认的民用出生日期、时辰、性别或原分析年不一致')
    identity = dict(solar_date=day.isoformat(), birth_year=day.year, shichen_index=index, shichen=shichen, sex=sex)
    replay, error = native_shichen_chart(day, identity, analysis_year)
    if error:
        raise ValueError('无法用内置紫微引擎复盘已确认时辰：' + error)
    native = replay['chart']
    try:
        brightness_conflicts = _verify_replayed_placements(chart, native)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise ValueError('原生紫微盘与已确认民用时辰复盘不一致：' + str(exc)) from exc
    year_errors = []
    if chart.get('wuxingJu') is not None and chart['wuxingJu'] != native['wuxingJu']:
        year_errors.append('原生大限五行局与复盘不一致')
    context = dict(
        input=identity, chart_path='chart', scope='confirmed_civil_shichen_only', birth_time_confirmed=False,
        coverage=('verified_reachable_civil_shichen' if spans is not None else 'confirmed_civil_shichen_utc_coverage_unknown'),
        clock_intervals=[dict(start_inclusive=f'{start:02d}:00', end_exclusive=f'{end:02d}:00')
                         for start, end in civil_shichen_hours(index)],
        civil_spans=spans, timezone=zone, utc_offset_hours=utc_offset,
        timezone_source=timezone_provenance(zone) if spans is not None else None)
    panel = _analyze_snapshot_year(
        chart, native, day.year, analysis_year, requested_analysis_year, dynamic_facts=dynamic_facts,
        root=root, year_errors=year_errors, replayed_stage_rows=native['daXians'], brightness_conflicts=brightness_conflicts,
        expected_target_date=expected_target_date, expected_target_time_index=expected_target_time_index,
        expected_target_civil=expected_target_civil, birth_scope={'birth_scenario': context})
    return panel


def _saved_snapshot_analysis_year(inputs, provenance, native_inputs):
    analysis_year = provenance.get('resolved_age_year')
    native_age_year = native_inputs.get('ageYear')
    years = [value for value in (inputs.get('analysis_year'), inputs.get('age_year'), provenance.get('analysis_year'))
             if value is not None]
    errors = []
    if 'resolved_age_year' not in provenance:
        if not years or not _integer(native_age_year, 1, 9999):
            errors.append('缺少可相互核对的已记录分析年和紫微ageYear')
        elif any(type(value) is not int or value != native_age_year for value in years):
            errors.append('snapshot记录的分析年与紫微ageYear无效或冲突')
        else:
            analysis_year = native_age_year
    elif not _integer(analysis_year, 1, 9999):
        errors.append('snapshot记录的resolved_age_year无效')
    elif any(type(value) is not int or value != analysis_year for value in years):
        errors.append('snapshot分析年份字段冲突')
    if native_age_year is not None and (not _integer(native_age_year, 1, 9999) or
                                        (analysis_year is not None and native_age_year != analysis_year)):
        errors.append('紫微ageYear与snapshot分析年冲突')
    return analysis_year, errors


def analyze_snapshot(snapshot, dynamic_facts=None, root=None, *, expected_target_date=None,
                     expected_target_time_index=None, expected_target_civil=None, ziwei_candidate_id=None,
                     requested_analysis_year=None):
    """Read a complete chart or confirmed birth-band snapshot with original provenance."""
    if not isinstance(snapshot, dict):
        raise ValueError('snapshot必须是完整JSON对象')
    _check_requested_analysis_year(requested_analysis_year, dynamic_facts,
                                   expected_target_date, expected_target_time_index)
    if snapshot.get('schema_version') == BIRTH_BAND_SCHEMA:
        from ziwei_birth_time_candidates import select_birth_band_candidate

        if dynamic_facts is not None and expected_target_date is None and expected_target_time_index is None:
            raise ValueError('紫微候选动态续算须提供本次请求的预期日期与时辰索引')
        chart, replayed, birth_year, analysis_year, context = select_birth_band_candidate(snapshot, ziwei_candidate_id)
        result = _analyze_snapshot_year(
            chart, replayed, birth_year, analysis_year, requested_analysis_year, dynamic_facts=dynamic_facts,
            root=root, expected_target_date=expected_target_date, expected_target_time_index=expected_target_time_index,
            expected_target_civil=expected_target_civil, birth_scope={'birth_scenario': context})
        return result
    degradation = snapshot.get('degradation', {})
    if not isinstance(degradation, dict):
        raise ValueError('snapshot.degradation必须是对象')
    inputs = snapshot.get('input', {})
    provenance = snapshot.get('provenance', {})
    native = snapshot.get('ziwei')
    civil_date, year_errors = None, []
    if not isinstance(inputs, dict):
        inputs = {}
    if not isinstance(provenance, dict):
        provenance = {}
    native_inputs = native.get('input', {}) if isinstance(native, dict) else {}
    if not isinstance(native_inputs, dict):
        native_inputs = {}
    try:
        civil_date = parse_birth_date(inputs['solar'])
    except (ValueError, KeyError):
        year_errors.append('缺少原input.solar民用出生日期，不从太阳钟面推回出生年')
    analysis_year, analysis_year_errors = _saved_snapshot_analysis_year(inputs, provenance, native_inputs)
    year_errors.extend(analysis_year_errors)
    if ziwei_candidate_id is not None:
        if dynamic_facts is not None and expected_target_date is None and expected_target_time_index is None:
            raise ValueError('紫微候选动态续算须提供本次请求的预期日期与时辰索引')
        chart, birth_year, context, replayed = _select_birth_candidate(
            snapshot, ziwei_candidate_id, inputs, civil_date)
        candidate_year = snapshot['ziwei_scenario_comparison'].get('analysis_year')
        if not _integer(candidate_year, 1, 9999) or candidate_year != analysis_year:
            year_errors.append('紫微候选对照分析年与snapshot分析年冲突')
        result = _analyze_snapshot_year(
            chart, replayed, birth_year, analysis_year, requested_analysis_year, dynamic_facts=dynamic_facts,
            root=root, year_errors=year_errors, replayed_stage_rows=replayed['daXians'],
            expected_target_date=expected_target_date, expected_target_time_index=expected_target_time_index,
            expected_target_civil=expected_target_civil, birth_scope={'birth_scenario': context})
        return result
    birth_year = civil_date.year if civil_date is not None else None
    if isinstance(native, dict):
        if birth_year is not None and native_inputs.get('birthYear') not in (None, birth_year):
            year_errors.append('原民用出生年与紫微birthYear冲突')
    chart = native.get('chart') if isinstance(native, dict) else None
    time_info = snapshot.get('time')
    if not isinstance(time_info, dict):
        time_info = {}
    timezone_error = None
    if 'timezone' in inputs and 'timezone_source' in provenance:
        try:
            check_timezone_source(provenance['timezone_source'], inputs['timezone'])
        except ValueError as exc:
            timezone_error = str(exc)
            if inputs.get('time_basis') in ('mean-solar', 'apparent-solar'):
                year_errors.append('原出生时区来源冲突：' + timezone_error)
    year_errors.extend(_snapshot_birth_conflicts(inputs, time_info, native_inputs, chart, civil_date))
    year_errors.extend(_solar_input_conflicts(inputs, time_info, provenance.get('timezone_source'),
                                              snapshot.get('qizheng')))
    birth_replay_error = None
    brightness_conflicts = ()
    replayed = None
    if isinstance(chart, dict) and not any('出生' in error and '冲突' in error for error in year_errors):
        try:
            replayed, brightness_conflicts = _replay_snapshot_chart(
                chart, inputs, time_info, native_inputs, civil_date, snapshot.get('qizheng'))
        except (ValueError, TypeError, OverflowError) as exc:
            birth_replay_error = '紫微出生原盘复核失败。' + str(exc)
        else:
            if chart.get('wuxingJu') is not None and chart['wuxingJu'] != replayed['wuxingJu']:
                year_errors.append('原生大限五行局与复盘不一致')
    birth_scope = {}
    scenario_bounds = recorded_scenario_bounds(inputs, snapshot.get('scenarios'))
    uncertain = bool(inputs.get('uncertainty_minutes')) or bool(native_inputs.get('temporalUncertainty'))
    if scenario_bounds is not None:
        start, end = scenario_bounds
        uncertain = uncertain or start is None or end is None or start != end
    if replayed is not None:
        try:
            if timezone_error:
                raise ValueError(timezone_error)
            bounds = _recorded_birth_bounds(inputs, time_info, civil_date, scenario_bounds)
            if ('temporalUncertainty' in native_inputs and
                    native_inputs['temporalUncertainty'] is not bool(inputs.get('uncertainty_minutes'))):
                raise ValueError('紫微原生盘与原输入的出生时间精度不一致')
        except (TypeError, ValueError, OverflowError) as exc:
            birth_scope['birth_time_error'] = str(exc)
            if scenario_bounds is not None:
                uncertain = True
        else:
            if bounds is not None:
                birth_scope['birth_time_bounds'] = bounds
    result = _analyze_snapshot_year(
        chart, replayed, birth_year, analysis_year, requested_analysis_year, dynamic_facts=dynamic_facts,
        temporal_uncertainty=uncertain,
        root=root, year_errors=year_errors, birth_replay_error=birth_replay_error,
        brightness_conflicts=brightness_conflicts, replayed_stage_rows=replayed['daXians'] if replayed else None,
        expected_target_date=expected_target_date, expected_target_time_index=expected_target_time_index,
        expected_target_civil=expected_target_civil, birth_scope=birth_scope)
    if not isinstance(native, dict):
        result['input_errors'] = ['紫微原生数据缺失：' + str(degradation.get('ziwei') or '未提供')]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, help='完整 build_chart、民用出生钟面区间或原生紫微 JSON')
    parser.add_argument('--dynamic', help='独立ziwei_dynamic_facts.mjs完整JSON；不提供则未请求')
    birth = parser.add_mutually_exclusive_group()
    birth.add_argument('--ziwei-candidate', help='同一快照的紫微出生候选 ID，如 ziwei-candidate-1 或 ziwei-band-7')
    birth.add_argument('--native-shichen', choices=tuple(BRANCHES), help='独立确认的原生紫微民用出生时辰')
    parser.add_argument('--birth-date', help='独立确认的公历民用出生日期，与 --native-shichen 一起使用')
    parser.add_argument('--sex', choices=('男', '女'), help='独立确认的性别，与 --native-shichen 一起使用')
    zone = parser.add_mutually_exclusive_group()
    zone.add_argument('--timezone', help='已知的出生 IANA 时区，与 --native-shichen 一起使用')
    zone.add_argument('--utc-offset', type=float, help='已知的出生固定 UTC 偏移小时，与 --native-shichen 一起使用')
    parser.add_argument('--analysis-year', type=int, help='本次独立指定的旧大限公历分析年')
    parser.add_argument('--expected-target-date', help='本次独立解析的目标日期YYYY-MM-DD，与预期时辰索引成对使用')
    parser.add_argument('--expected-target-time-index', type=int, help='本次独立解析的时辰索引0至12，与预期日期成对使用')
    parser.add_argument('--expected-target-civil', help='独立查询计划的带偏移钟面，与预期日期及索引一起使用')
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding='utf-8'))
        dynamic = json.loads(Path(args.dynamic).read_text(encoding='utf-8')) if args.dynamic else None
        if not isinstance(snapshot, dict):
            raise ValueError('snapshot必须是完整JSON对象')
        request = dict(expected_target_date=args.expected_target_date,
                       expected_target_time_index=args.expected_target_time_index,
                       expected_target_civil=args.expected_target_civil,
                       requested_analysis_year=args.analysis_year)
        if args.native_shichen is not None:
            result = analyze_native_shichen(snapshot, args.birth_date, args.native_shichen, args.sex, dynamic,
                                            zone=args.timezone, utc_offset=args.utc_offset, **request)
        else:
            if any(value is not None for value in (args.birth_date, args.sex, args.timezone, args.utc_offset)):
                raise ValueError('出生日期、性别及时区参数用于 --native-shichen 原生盘续算')
            result = analyze_snapshot(snapshot, dynamic, ziwei_candidate_id=args.ziwei_candidate, **request)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result['status'] == 'withheld' else 0
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
