"""Bounded traditional structure, separate from the physical ephemeris.

No event predictions, classical quotation authorization, or imported source code.
"""
import hashlib
import json
from pathlib import Path

import pai_pan_qizheng as engine

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'qizheng-degree-relations-v1'
ELEMENTS = '木火土金水'
LORDS = dict(zip('子丑寅卯辰巳午未申酉戌亥', '土土木火金水日月水金火木'))
SOURCE_PATH = 'docs/qizheng-rule-profiles.md'
SOURCE_PATHS = {
    'qizheng-project-rules': SOURCE_PATH,
    'qizheng-states-local': 'references/qizheng/states-tables.md',
}
# This identifier describes the rule contract, not astronomical accuracy.
SUPPORTED_CALCULATIONS = ('legacy-v1', 'physical-v2')


def profile_metadata():
    return {
        'id': PROFILE, 'version': 1,
        'en_yong_reference': '命度宿主五行（日取火、月取水）',
        'relation_definition': {'恩': '生我', '用': '我生', '难': '克我', '仇': '我克', '同': '同我'},
        'palace_lords': dict(LORDS),
        'palace_assignment': 'engine mansion-aggregated branch sectors, not equal 30-degree zodiac signs',
        'ming_gong_hour': '北京时间民用时辰，非地方真太阳时',
        'mansion_status': 'approximate projected longitude sectors; not measured equatorial mansion degrees',
        'scope': 'conditional_traditional_structure_only',
        'predictive_validity': 'unvalidated',
        'unimplemented': ['身主/身宫', '宿内庙旺分度', '行限应期', '医学/婚姻/财运事件结论'],
    }


def palace_identity(zhi):
    if not isinstance(zhi, str) or zhi not in LORDS:
        raise ValueError('未知宫支')
    lord = LORDS[zhi]
    return {'zhi': zhi, 'branch_element': engine.PALACE_WUXING[zhi],
            'palace_lord': lord, 'palace_lord_element': engine.MANSION_WX_TO_PHASE[lord]}


def relation(reference, other):
    """Name the other element relative to reference; no school inference."""
    if not isinstance(reference, str) or not isinstance(other, str) or reference not in set(ELEMENTS) or other not in set(ELEMENTS):
        raise ValueError('五行必须明确')
    return ('同', '用', '仇', '难', '恩')[(ELEMENTS.index(other) - ELEMENTS.index(reference)) % 5]


def source_evidence():
    manifest = json.loads((ROOT / 'knowledge/qizheng-rule-sources.json').read_text(encoding='utf-8'))
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest['schema_version'] != 1):
        raise ValueError('七政规则来源清单版本无效')
    rows = manifest.get('sources')
    if not isinstance(rows, list) or len(rows) != len(SOURCE_PATHS):
        raise ValueError('七政规则来源清单不完整')
    evidence = []
    remaining = dict(SOURCE_PATHS)
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            raise ValueError('七政规则来源条目无效')
        path = remaining.pop(row['id'], None)
        if path is None or path != row.get('path') or row.get('classical_quote_authorized') is not False:
            raise ValueError('七政规则来源标识、路径或引用权限不符')
        data = (ROOT / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != row.get('sha256'):
            raise ValueError('七政规则来源已变更，须复核：' + path)
        evidence.append(dict(row))
    return evidence



def _coordinate_issue(item, label, boundary):
    """Explain the existing coordinate and boundary gate without changing it."""
    if not isinstance(item, dict) or any(
            type(item.get(key)) not in (int, float) or not 0 <= item[key] < 360
            for key in ('tropical', 'sidereal')):
        return label + '缺少有效坐标。'
    quality = item.get('classification_quality')
    near_boundary = quality.get('near_boundary') if isinstance(quality, dict) else None
    if near_boundary is True:
        return label + '靠近未校准' + boundary + '。'
    if near_boundary is not False:
        return label + '缺少明确的边界筛查证据。'
    return None


def palace_guard_reasons(chart):
    reasons = []
    mg = chart.get('ming_gong')
    if not isinstance(mg, dict) or not isinstance(mg.get('zhi'), str) or mg['zhi'] not in LORDS:
        reasons.append('缺少有效立命宫。')
    bodies = chart.get('bodies')
    sun = bodies.get('日') if isinstance(bodies, dict) else None
    issue = _coordinate_issue(sun, '太阳', '宿宫界')
    if issue:
        reasons.append(issue)
    return reasons


def analyze(chart, profile=PROFILE, temporal_uncertainty=False, *, withhold_on_source_error=False):
    if profile != PROFILE:
        raise ValueError('未知七政规则 profile，不能自动混用学派')
    if not isinstance(chart, dict):
        raise ValueError('需要七政引擎结果')
    out = {'profile': profile_metadata(), 'sources': [], 'claims': [],
           'predictive_validity': 'unvalidated', 'status': 'conditional',
           'calculation_profile': chart.get('calculation_profile', 'unspecified'),
           'limitations': ['宿界为近似模型，靠界及出生时间误差需重算场景，不能以小数位冒充精度。',
                           '规则标签不代表吉凶事件；同名格局或恩用表不能跨学派套用。']}
    try:
        out['sources'] = source_evidence()
    except (OSError, ValueError) as exc:
        if not withhold_on_source_error:
            raise
        out.update(status='withheld', reason='七政规则来源无法核验：' + str(exc))
        return out
    calculation = out['calculation_profile']
    reasons = []
    if calculation not in SUPPORTED_CALCULATIONS:
        reasons.append('未声明受支持的计算版本。旧盘须先明确 legacy-v1 或重新计算。')
    if type(temporal_uncertainty) is not bool or temporal_uncertainty:
        reasons.append('出生时间存在误差，须先比较完整七政候选盘。')
    md, mg = chart.get('ming_du'), chart.get('ming_gong')
    if md is None and all(key in chart for key in ('ming_du', 'ming_gong', 'day_night')):
        if mg is None and chart['day_night'] is None:
            reasons.append('依赖经纬度的地平计算未取得，缺少命度。')
        elif calculation == 'physical-v2' and isinstance(mg, dict) and isinstance(chart['day_night'], dict):
            reasons.append('东方上升交点未定义，缺少命度。')
        else:
            reasons.append('缺少命度。')
    else:
        if not isinstance(md, dict) or not isinstance(md.get('wuxing'), str) or md['wuxing'] not in engine.MANSION_WX_TO_PHASE:
            reasons.append('缺少有效命度宿主。')
        issue = _coordinate_issue(md, '命度', '宿界')
        if issue:
            reasons.append(issue)
    contract = chart.get('star_frame_contract')
    if not isinstance(contract, dict) or contract.get('within_validated_range') is not True:
        reasons.append('缺少明确的坐标模型日期范围核验。')
    if reasons:
        out.update(status='withheld', reason=''.join(reasons))
        return out
    mansion = md.get('mansion')
    expected = {row[0]: row[3] for row in engine.MANSIONS}
    if not isinstance(mansion, str) or mansion not in expected or expected[mansion] != md['wuxing']:
        out.update(status='withheld', reason='命度宿名与宿主不一致，不能沿用恩用表。')
        return out
    phase = engine.MANSION_WX_TO_PHASE[md['wuxing']]
    supplied = chart.get('du_zhu_wuxing')
    if supplied is not None and supplied != phase:
        out.update(status='withheld', reason='度主五行与命度宿主冲突。')
        return out
    groups = {key: [] for key in ('恩', '用', '难', '仇', '同')}
    for body in engine.LUMINARIES:
        groups[relation(phase, engine.LUMINARIES_WUXING[body])].append(body)
    if chart.get('en_yong') is not None and chart['en_yong'] != groups:
        out.update(status='withheld', reason='输入恩用表与所选度主学派不一致，禁止混表。')
        return out
    out['claims'].append({
        'rule_id': 'QZ01', 'status': 'conditional', 'facts': {'mansion': mansion, 'reference_element': phase},
        'groups': groups,
        'explanation': '若采用本盘近似宿界且命度属%s，则以%s为我：恩=%s，用=%s，难=%s，仇=%s。这里是生克分类，不是获助或受害的事实。' %
                       (mansion, phase, '、'.join(groups['恩']), '、'.join(groups['用']), '、'.join(groups['难']), '、'.join(groups['仇'])),
        'counterconditions': ['换宫主为我将改变分组', '宿界或出生时间改变可改变度主'],
        'source_ids': ['qizheng-project-rules']})
    palace_reasons = palace_guard_reasons(chart)
    if not palace_reasons:
        identity = palace_identity(mg['zhi'])
        rel = relation(phase, identity['palace_lord_element'])
        out['claims'].append({
            'rule_id': 'QZ02', 'status': 'conditional', 'facts': identity,
            'relation_to_degree_lord': rel,
            'explanation': '%s宫的支五行为%s；此规则的宫主为%s，折合%s。相对度主%s属于“%s”，不能用支五行替代，也不足以定宫度相得或成格。' %
                           (mg['zhi'], identity['branch_element'], identity['palace_lord'], identity['palace_lord_element'], phase, rel),
            'counterconditions': ['宫主体系不同须另设profile', '未合并日夜、四时、会合及强弱条件'],
            'source_ids': ['qizheng-project-rules', 'qizheng-states-local']})
    else:
        out['claims'].append({'rule_id': 'QZ02', 'status': 'withheld', 'reason': ''.join(palace_reasons)})
    return out


def format_reading(result):
    lines = ['### 七政规则释义（有条件，非预测验证）',
             '- 规则版本：' + result['profile']['id'],
             '- 计算版本：' + result['calculation_profile']]
    if result['status'] == 'withheld':
        lines.append('- 暂不解释：' + result['reason'])
    for claim in result['claims']:
        lines.append('- ' + claim.get('explanation', claim.get('reason', '')))
        if claim.get('groups'):
            lines.append('  同=' + '、'.join(claim['groups']['同']))
        if claim.get('counterconditions'):
            lines.append('  反条件：' + '；'.join(claim['counterconditions']))
        if claim.get('source_ids'):
            lines.append('  来源标识：' + '、'.join(claim['source_ids']))
    lines.extend('- ' + note for note in result['limitations'])
    if result.get('sources'):
        lines.append('- 出处：docs/qizheng-rule-profiles.md（项目规则释义）；原典归属未校勘，不作古籍逐字引文。')
    return '\n'.join(lines)
