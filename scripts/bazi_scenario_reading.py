"""Compare reachable four-pillar witnesses; never infer event probabilities."""
import bazi_core_reading as core
import pai_pan_bazi as engine

VERSION = 'bazi-scenario-comparison-v1'
LABELS = {'day_master': '日主参照', 'season': '月令与季节', 'roots': '同五行根气',
          'relations': '冲合刑害配对', 'month_exposure': '月支藏干透出',
          'support': '生扶线索', 'opposing': '克泄耗线索'}


def canonical_pillars(fields):
    """The enumerator retains only stems/branches; derive annotations by engine."""
    day = fields['bazi.day'][0]
    return {key: (fields['bazi.' + key][0], fields['bazi.' + key][1],
                  '—' if key == 'day' else engine.shishen_of(
                      engine.GAN.index(day), engine.GAN.index(fields['bazi.' + key][0])),
                  engine.format_canggan(fields['bazi.' + key][1])) for key in core.KEYS}


def evidence(analysis):
    facts = analysis['facts']
    month = facts['month']['branch']
    season = next(s for chars, s in [('寅卯辰', '春'), ('巳午未', '夏'),
                                    ('申酉戌', '秋'), ('亥子丑', '冬')] if month in chars)
    relations = [core.describe([core.LABELS[k] + '柱' for k in r['positions']]) +
                 r['symbols'] + r['kind'] for r in analysis['relations'] + analysis['groups']]
    exposure = [r['stem'] + '（' + r['ten_god'] + '）' +
                ('透于' + core.describe([core.LABELS[k] + '干' for k in r['exposed_at']])
                 if r['exposed_at'] else '未透于年/月/时干') +
                ('，与日干相同' if r['same_as_day'] else '') for r in analysis['month_exposure']]
    return {'day_master': facts['day']['stem'] + core.element(facts['day']['stem']),
            'season': month + '月，节气划分的' + season + '季',
            'roots': core.describe(analysis['roots']), 'relations': core.describe(relations),
            'month_exposure': '；'.join(exposure),
            'support': core.describe(analysis['support']),
            'opposing': core.describe(analysis['opposing'])}


def analyze(scenarios):
    rows = []
    for i, variant in enumerate(scenarios['variants'], 1):
        analysis = core.analyze({'pillars': canonical_pillars(variant['fields']),
                                 'scenario_id': 'candidate-' + str(i)})
        facts = evidence(analysis)
        # Newer rule versions may expose a conditional pattern decision. Keep
        # the comparison valid with the original structural-only analyzer too.
        if 'pattern_reasoning' in analysis:
            facts['pattern'] = analysis['pattern_reasoning']['text']
        facts['strength'] = analysis['strength_reasoning']['text']
        rows.append({'id': 'candidate-' + str(i), 'witness_utc': variant['witness_utc'],
                     'chart_clock': variant['chart_clock'], 'intervals': variant['intervals'],
                     'pillars': {k: analysis['facts'][k]['pillar'] for k in core.KEYS},
                     'evidence': facts, 'analysis': analysis})
    if not rows:
        raise ValueError('候选比较至少需要一个可达候选')
    constant = {k: v for k, v in rows[0]['evidence'].items()
                if all(row['evidence'][k] == v for row in rows)}
    changed = [k for k in rows[0]['evidence'] if k not in constant]
    complete = scenarios['coverage'] == 'complete_for_modeled_boundaries_not_astronomical_error'
    labels = dict(LABELS, pattern='格局条件判断', strength='强弱条件比较')
    for row in rows:
        row['text'] = '；'.join(labels[k] + '：' + row['evidence'][k] for k in changed) if changed else '所列结构证据与其他候选相同。'
    return {'schema_version': 1, 'rule_version': VERSION, 'coverage': scenarios['coverage'],
            'scope': '仅比较枚举器返回的八字四柱结构；不代表完整紫微、七政、起运或人生预测',
            'reviewed_panel_scope': '新增卡片逐候选解释，仅对相应见证输入成立；未将卡片结论纳入区间稳定性判定。',
            'context': {k: scenarios[k] for k in ('start_utc', 'end_utc', 'interval_semantics', 'excluded')},
            'stable_evidence': constant if complete else {},
            'observed_constant_evidence': {} if complete else constant,
            'changing_evidence': changed, 'labels': labels, 'candidates': rows,
            'warnings': ['差别来自出生时刻输入的不确定性，不是多个未来结果的概率；没有给候选分配可信度。',
                         '根气仅指藏干有日主同五行；配对不等于合化或事件。共同线索也不直接推出强弱、喜忌。'] +
                        ([] if complete else ['真太阳时仅比较已找到的数值样本，不能声称覆盖全部候选或保证结构稳定。'])}


def render(comparison):
    lines = ['', '### 出生时刻候选的八字对照', '', comparison['scope'] + '。']
    constant = comparison['stable_evidence'] or comparison['observed_constant_evidence']
    heading = ('区间内共同证据（仅当前模型）'
               if comparison['coverage'] == 'complete_for_modeled_boundaries_not_astronomical_error'
               else '已找到样本的共同证据（不保证区间稳定）')
    lines.append(heading + '：')
    lines.extend('- ' + comparison['labels'][k] + '：' + value for k, value in constant.items())
    if not constant:
        lines.append('- 所列证据没有共同项。')
    for i, row in enumerate(comparison['candidates'], 1):
        lines += ['', '**候选 %d**：' % i + '、'.join(core.LABELS[k] + '柱' + v for k, v in row['pillars'].items()) +
                  '；可达样本 UTC ' + row['witness_utc'] + '。', row['text']]
    if 'day_master' in comparison['changing_evidence']:
        lines.append('日主改变后，十神和根气都必须按各自日干重算，不能把中心盘的身份或生扶判断搬到另一候选。')
    if 'season' in comparison['changing_evidence']:
        lines.append('跨节气改变月令和季节背景，取格与调候的前提随之改变；不能共用中心盘的月令判断。')
    lines.extend('注意：' + w for w in comparison['warnings'])
    sources = {(r['analysis']['source']['path'], r['analysis']['source']['version']) for r in comparison['candidates']}
    lines.append('依据：' + '；'.join(path + '，' + version for path, version in sorted(sources)) + '；候选保留原枚举器的 UTC 见证与区间。')
    pattern_sources = []
    for row in comparison['candidates']:
        pattern = row['analysis'].get('pattern_reasoning')
        if pattern and pattern['attribution'] not in pattern_sources:
            pattern_sources.append(pattern['attribution'])
    for source in pattern_sources:
        lines += core.render_pattern_attribution(source, scope='上述候选对照中的格局候选解释')
    lines += core.strength_reasoning.render_attribution(comparison['candidates'][0]['analysis']['strength_reasoning']['attribution'])
    return lines
