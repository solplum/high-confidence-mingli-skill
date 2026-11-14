"""Versioned structure with bounded strength hypotheses, not an event predictor.

Only accepts canonical engine pillar tuples. No new dependencies or network calls.
Rule definitions and exclusions: docs/bazi-core-reading.md, version 2.
"""
import hashlib
from pathlib import Path

import pai_pan_bazi as engine
import bazi_pattern_reasoning as pattern_reasoning
import bazi_strength_reasoning as strength_reasoning
import bazi_reviewed_structure as reviewed_structure
import bazi_purpose_extensions as purpose_extensions
import bazi_qiong_xin_zi as qiong_xin_zi
import bazi_primary_spouse as primary_spouse
from bazi_reviewed_structure import GROUP_RULES, PAIR_RULES

VERSION = 'bazi-structure-v2'
KEYS = ('year', 'month', 'day', 'hour')
LABELS = dict(zip(KEYS, ('年', '月', '日', '时')))
ELEMENTS = '木火土金水'


def element(gan):
    return engine.GAN_WUXING[engine.GAN.index(gan)]


def relation(a, b):
    delta = (ELEMENTS.index(b) - ELEMENTS.index(a)) % 5
    return ('同类', '生', '克', '受克于', '受生于')[delta]


def describe(items):
    return '、'.join(items) if items else '未见（仅限已知柱）'


def analyze(result, temporal_uncertainty=False, *, candidate_temporal_uncertainty=False):
    if not isinstance(result, dict) or not isinstance(result.get('pillars'), dict):
        raise ValueError('需要四柱映射')
    uncertain = temporal_uncertainty or bool(result.get('temporal_uncertainty', False))
    # The old comparison panels evaluate the witness as an exact four-pillar
    # input. These newer models carry the original uncertainty into follow-ups.
    model_uncertainty = uncertain or candidate_temporal_uncertainty
    p = result['pillars']
    for key in KEYS:
        row = p.get(key)
        if not isinstance(row, (list, tuple)) or len(row) != 4 or not all(isinstance(x, str) for x in row):
            raise ValueError('非规范四柱字段：' + key)
        if key == 'hour' and tuple(row) == ('未知',) * 4:
            continue
        if row[0] not in engine.GAN or row[1] not in engine.ZHI:
            raise ValueError('非规范四柱字段：' + key)
    day = p['day'][0]
    day_index = engine.GAN.index(day)
    known, missing, facts = {}, [], {}
    for key in KEYS:
        row = p[key]
        if key == 'hour' and row[0] == '未知':
            missing.append(key)
            continue
        if len(row) != 4 or row[0] not in engine.GAN or row[1] not in engine.ZHI:
            raise ValueError('非规范四柱字段：' + key)
        expected_hidden = engine.format_canggan(row[1])
        fact = engine.pillar_fact(row[0], row[1], day_index, is_day=key == 'day')
        if row[3] != expected_hidden or row[2] != fact['ten_god']:
            raise ValueError('藏干或十神与引擎口径不一致：' + key)
        known[key] = row
        facts[key] = fact
    wx = element(day)
    pairs, groups = reviewed_structure.relations_from_facts(facts)
    month = p['month'][1]
    exposures = []
    for g, w in engine.CANGGAN[month]:
        exposures.append({'stem': g, 'element': w,
                          'ten_god': engine.shishen_of(engine.GAN.index(day), engine.GAN.index(g)),
                          'exposed_at': [k for k in known if k != 'day' and p[k][0] == g],
                          'same_as_day': day == g})
    support, opposing, roots = [], [], []
    for key, row in known.items():
        for g, w in engine.CANGGAN[row[1]]:
            desc = LABELS[key] + '支' + row[1] + '藏' + g + w
            if w == wx:
                roots.append(desc)
            (support if relation(wx, w) in ('同类', '受生于') else opposing).append(desc)
        if key != 'day':
            desc = LABELS[key] + '干' + row[0] + element(row[0]) + '（' + row[2] + '）'
            (support if relation(wx, element(row[0])) in ('同类', '受生于') else opposing).append(desc)
    paths = []
    for a, b in zip(KEYS, KEYS[1:]):
        if a in known and b in known:
            paths.append({'from': a, 'to': b, 'relation': relation(element(p[a][0]), element(p[b][0]))})
    season = next(s for chars, s in [('寅卯辰', '春'), ('巳午未', '夏'),
                                     ('申酉戌', '秋'), ('亥子丑', '冬')] if month in chars)
    thermal = {w: [LABELS[k] + '干' + p[k][0] for k in known if element(p[k][0]) == w] +
               [LABELS[k] + '支' + p[k][1] + '藏' + g for k in known
                for g, hw in engine.CANGGAN[p[k][1]] if hw == w] for w in ('火', '水')}
    sections = []
    def add(id_, title, prose, prerequisites, counter, unresolved):
        sections.append({'id': id_, 'title': title, 'status': 'structural_only',
                         'evidence': list(known), 'prerequisites': prerequisites,
                         'counterevidence': counter, 'unresolved': unresolved, 'text': prose})
    pair_text = [describe([LABELS[k] for k in r['positions']]) + r['symbols'] + r['kind'] +
                 ('（相邻）' if r.get('adjacent') else '（隔柱）') for r in pairs]
    pair_text += [r['symbols'] + r['kind'] for r in groups]
    add('relations', '核心冲合',
        '按柱位逐对检查，检出：' + describe(pair_text) + '。这些是字与字的关系，不是事情必然发生的信号。'
        '同一字可以同时参与合与冲刑害，不能只挑一种来讲；合的配对或三字齐全也不等于已经合化。',
        ['已知柱的干支有效；两字配对需两个不同柱位，三字组需三种支齐全'],
        pair_text or ['当前未检出所列关系；不代表没有其他学派关系'],
        ['未判合化、合绊效果与刑冲力度；三刑缺字不按完整三刑输出'])
    visible = [LABELS[k] + '干' + p[k][0] + '为' + p[k][2] for k in known if k != 'day']
    glosses = {
        '同类': '同类关系（比劫）说的是与日主五行相同，不等于现实中一定竞争或破财',
        '生': '日主生出的关系（食伤）可理解为由自身向外表达的符号，但不证明才艺或职业',
        '克': '日主所克的关系（财）是作用方向的名称，不是收入金额或财富保证',
        '受克于': '克日主的关系（官杀）是约束的符号，不是官非、疾病或必然压力',
        '受生于': '生日主的关系（印）是支持的符号，不是学历、贵人或成功保证',
    }
    present_relations = list(dict.fromkeys(relation(wx, element(p[k][0])) for k in known if k != 'day'))
    meanings = '；'.join(glosses[r] for r in present_relations)
    path_text = [LABELS[x['from']] + '干' + p[x['from']][0] + element(p[x['from']][0]) +
                 x['relation'] + LABELS[x['to']] + '干' + p[x['to']][0] + element(p[x['to']][0]) for x in paths]
    add('ten_gods', '十神链', '以日干' + day + wx + '为参照：' + describe(visible) + '。'
        '这些名称用普通话说：' + meanings + '。按年、月、日、时的显示顺序，邻接关系为：' + describe(path_text) + '。'
        '“生”是五行关系，“克”是制约关系；这里没有把柱顺序当成人生阶段或真实能量流动。',
        ['十神与当前引擎按日干重算一致'], opposing,
        ['邻接关系不是全局作用强弱，也不推出性格、职业或财富'])
    pattern = pattern_reasoning.evaluate(facts, exposures, pairs, groups, missing)
    add('pattern', '格局候选判断', pattern['text'],
        ['采用月藏同干透出的有限路线；只选普通格候选，不代替成格审查'],
        [v for c in pattern['candidates'] for v in c['opposing_facts']] + pattern['purity_checks'],
        pattern['changing_conditions'])
    sections[-1]['status'] = pattern['status']
    season_note = {'春': '按春季背景观察生发，不能仅凭春月指定喜火或忌水',
                   '夏': '按夏季背景优先检查火与水的并存情况，不能见夏就认定必须补水',
                   '秋': '按秋季背景检查燥润问题，不能把秋季标签等同实际气候',
                   '冬': '按冬季背景优先检查火与水的并存情况，不能见冬就认定必须补火'}[season]
    add('climate', '调候', month + '月属于节气划分的' + season + '季。' + season_note + '。'
        '本盘火的位置：' + describe(thermal['火']) + '；水的位置：' + describe(thermal['水']) + '。'
        '出现的位置不等于实际有效的力量；某元素未出现也不自动构成缺陷。',
        ['季节按月支分类，不按公历月份或出生地天气'],
        ['火与水均按透干及藏干保留，没有用计数决定寒暖'],
        ['未量化寒暖燥湿；未确定调候用神，不据此推荐颜色、饰物、医疗或投资'])
    strength = strength_reasoning.evaluate(facts, pairs, groups, missing, temporal_uncertainty=uncertain)
    add('strength', '日主强弱', strength['text'],
        ['根气仅为藏干含同五行的项目操作定义；窄条件不等于通用强弱算法'],
        [e['text'] for e in strength['facts'] if e['id'] in strength['counterevidence_fact_ids']],
        strength['missing_conditions'] + strength['unresolved_effects'] + strength['changing_conditions'])
    sections[-1]['status'] = strength['status']
    reviewed = reviewed_structure.evaluate(
        facts, exposures, pairs, groups, pattern, strength, missing,
        temporal_uncertainty=uncertain,
        scenario_id=result.get('scenario_id'))
    purpose = purpose_extensions.evaluate(
        facts, pairs, groups, pattern, strength, missing,
        temporal_uncertainty=uncertain,
        scenario_id=result.get('scenario_id'))
    qiong = qiong_xin_zi.evaluate(
        facts, pairs, groups, missing,
        temporal_uncertainty=model_uncertainty,
        scenario_id=result.get('scenario_id'))
    primary_spouse_panel = primary_spouse.evaluate_bazi_primary_spouse(
        facts, pairs, groups, pattern, missing, sex=result.get('sex'),
        temporal_uncertainty=model_uncertainty,
        scenario_id=result.get('scenario_id'))
    root = Path(__file__).resolve().parents[1]
    return {'schema_version': 1, 'rule_version': VERSION,
            'scope': '单一输入候选的本命结构解释，非完整人生详批、非预测验证',
            'facts': facts, 'missing_pillars': missing, 'relations': pairs, 'groups': groups,
            'month_exposure': exposures, 'pattern_reasoning': pattern, 'strength_reasoning': strength,
            'reviewed_structure': reviewed, 'purpose_extensions': purpose,
            'qiong_xin_zi_model': qiong, 'primary_spouse': primary_spouse_panel,
            'paths': paths, 'support': support,
            'opposing': opposing, 'roots': roots, 'sections': sections,
            'source': {'kind': 'project_structural_definitions', 'path': 'docs/bazi-core-reading.md',
                       'version': VERSION, 'sha256': hashlib.sha256((root / 'docs/bazi-core-reading.md').read_bytes()).hexdigest()},
            'warnings': ['时柱未知：所有未见仅限已知三柱，不能推广到全盘。'] if missing else []}


def render(analysis):
    lines = ['', '### 八字核心解读（结构版）', '',
             '以下说明这张盘的具体结构，不把传统符号当作人生事实。' + analysis['scope'] + '。']
    lines.extend('注意：' + warning for warning in analysis['warnings'])
    for section in analysis['sections']:
        lines += ['', '**' + section['title'] + '**：' + section['text'],
                  '尚未确定：' + '；'.join(section['unresolved']) + '。']
    lines += ['', '依据：项目结构规则 ' + VERSION + '，docs/bazi-core-reading.md；'
              '四柱、藏干、十神来自 pai_pan_bazi.py。不是古籍原文或预测有效性认证。']
    lines += render_pattern_attribution(analysis['pattern_reasoning']['attribution'])
    lines += strength_reasoning.render_attribution(analysis['strength_reasoning']['attribution'])
    lines += reviewed_structure.render(analysis['reviewed_structure'])
    lines += purpose_extensions.render(analysis['purpose_extensions'])
    lines += qiong_xin_zi.render(analysis['qiong_xin_zi_model'])
    if 'primary_spouse' in analysis:
        lines += primary_spouse.render(analysis['primary_spouse'])
    return lines


def render_pattern_attribution(source, scope='本段候选解释'):
    """Keep standalone renderers explicit about adapted prose and its license."""
    span = source['source_span']
    location = str(span['start_line'])
    if span['end_line'] != span['start_line']:
        location += '-' + str(span['end_line'])
    return ['', '格局候选依据：' + source['interpretation_label'] + '；' + source['record_id'] +
            '；' + source['path'] + ':' + location + '；固定版本 ' + str(source['revision']) + '。',
            '署名：' + source['attribution'], '来源：' + source['upstream_url'],
            '贡献历史：' + source['contributors_url'],
            '改编：' + source['adaptation'],
            scope + '依 CC BY-SA 4.0 共享：' + source['license_url'] + '；其他代码许可不变。']
