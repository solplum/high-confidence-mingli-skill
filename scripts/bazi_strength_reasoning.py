"""MIT: bounded traditional evidence comparison, not predictive validation.

The conjunctions are project hypotheses, not a complete classical algorithm.
"""
import json
from pathlib import Path
import knowledge_catalog

VERSION = 'bazi-strength-evidence-v1'
ELEMENTS = '木火土金水'
LABELS = dict(zip(('year', 'month', 'day', 'hour'), ('年', '月', '日', '时')))
CORE_SEASON = dict(zip('寅卯巳午申酉亥子', '木木火火金金水水'))
PAGES = {'ST01': [21], 'ST02': [21, 22], 'ST03': [21, 22], 'ST04': [21, 25], 'ST05': [20, 21, 22, 23]}


def relation(day, other):
    return ('peer', 'output', 'wealth', 'officer', 'resource')[(ELEMENTS.index(other) - ELEMENTS.index(day)) % 5]


def evaluate(facts, pairs, groups, missing, temporal_uncertainty=False):
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / 'knowledge/catalog.json').read_text())
    errors = knowledge_catalog.validate(catalog, root)
    if errors:
        raise ValueError('强弱来源检查失败：' + '; '.join(errors))
    for rid in PAGES:
        record = next((r for r in catalog['records'] if r['id'] == 'bazi-strength-' + rid), {})
        if record.get('status') != 'usable' or record.get('profile') != 'bazi-strength-evidence' or record.get('source_id') != 'bazi-strength-project':
            raise ValueError('强弱规则未获来源门允许：' + rid)
    source = knowledge_catalog.citation(catalog, root, 'bazi-strength-project')
    source.update(pdf_sha256='b1ac0a7dd4dc260647b65bd9338ad815fc0855d78e0ea01ed428237b28eb61c8',
                  passage='論十干有得時不旺失時不弱；合冲与用神成败相关语境',
                  pdf_pages_one_based=PAGES, adaptation='项目窄条件比较，不是古文原句或普遍判强弱算法', output_license='MIT')
    day = facts['day']['stem']
    import pai_pan_bazi as engine
    def element(g):
        return engine.GAN_WUXING[engine.GAN.index(g)]
    dw = element(day)
    evidence = []
    for pos, f in facts.items():
        if pos != 'day':
            w = element(f['stem'])
            evidence.append(dict(id=pos + '.stem', position=pos, layer='visible', stem=f['stem'], element=w,
                                 relation=relation(dw, w), text=LABELS[pos] + '干' + f['stem'] + w + '（' + f['ten_god'] + '）'))
        for index, h in enumerate(f['hidden']):
            evidence.append(dict(id=pos + '.hidden.' + h['stem'], position=pos, layer='hidden',
                                 hidden_role='first_listed' if index == 0 else 'other_listed',
                                 stem=h['stem'], element=h['element'], relation=relation(dw, h['element']),
                                 text=LABELS[pos] + '支' + f['branch'] + '藏' + h['stem'] + h['element']))
    roots = [e for e in evidence if e['layer'] == 'hidden' and e['relation'] == 'peer']
    support = [e for e in evidence if e['relation'] in ('peer', 'resource')]
    counter = [e for e in evidence if e['relation'] not in ('peer', 'resource')]
    visible_support = [e for e in support if e['layer'] == 'visible']
    visible_opposition = [e for e in counter if e['layer'] == 'visible']
    hidden = [e for e in evidence if e['layer'] == 'hidden']
    support_paths = [dict(visible_id=e['id'], root_ids=[h['id'] for h in hidden if h['element'] == e['element']],
                          text=e['text'] + ('在支有同五行藏干支持' if any(h['element'] == e['element'] for h in hidden) else '在已知支未见同五行藏干支持')) for e in visible_support]
    pressure_paths = [dict(visible_id=e['id'], role=e['relation'], root_ids=[h['id'] for h in hidden if h['element'] == e['element']], text=e['text']) for e in visible_opposition]
    contested = []
    unassessed = []
    for r in pairs + groups:
        if r['kind'] not in ('六冲', '六合配对', '天干五合配对', '三合齐字', '三会齐字'):
            unassessed.append(dict(kind=r['kind'], positions=r['positions'],
                                   text='、'.join(LABELS[k] + facts[k]['pillar'] for k in r['positions']) + r['kind'] + '：本模块未评估其效力，不能将当前趋势当成含刑害审查的最终判断'))
            continue
        affected = [e['id'] for e in evidence if e['position'] in r['positions'] and
                    (e['layer'] == 'visible' if r['kind'] == '天干五合配对' else e['layer'] == 'hidden')]
        if affected:
            contested.append(dict(kind=r['kind'], positions=r['positions'], fact_ids=affected,
                                  text='、'.join(LABELS[k] + facts[k]['pillar'] for k in r['positions']) + r['kind'] + '：效力待审，未删除藏干或认定合化'))
    disputed = [LABELS[k] + f['branch'] for k, f in facts.items() if (day, f['branch']) in (('乙', '午'), ('丁', '酉'))]
    month = facts['month']['branch']
    seasonal = CORE_SEASON.get(month)
    blockers = []
    if missing:
        blockers.append('时柱未知，新增根、印比或克泄耗均可能改变比较')
    if temporal_uncertainty:
        blockers.append('输入出生时间未决；此处不是全时段结论，须逐可达候选重算')
    if disputed:
        blockers.append('阴长生来源与藏干模型口径未合：' + day + '见' + '、'.join(disputed) + '；暂停此争议条及趋势判定')
    if seasonal is None or dw == '土':
        blockers.append('本窄季节模型未处理四季土月或土日主的旺气判定')
    # Conservatively defer on any modeled interaction; no asserted cancellation.
    if contested:
        blockers.append('存在合冲/齐字的效力争议，未完成制化及根效力审查')
    gates = dict(season_matches=seasonal == dw,
                 month_main_root=any(e['position'] == 'month' and e['hidden_role'] == 'first_listed' for e in roots),
                 rooted_external_support=any(p['root_ids'] for p in support_paths),
                 no_visible_opposition=not visible_opposition,
                 season_controls=seasonal is not None and relation(dw, seasonal) == 'officer',
                 no_same_element_roots=not roots, no_visible_support=not visible_support,
                 no_hidden_resource=not any(e['relation'] == 'resource' for e in hidden),
                 rooted_visible_officer=any(p['role'] == 'officer' and p['root_ids'] for p in pressure_paths))
    if blockers:
        decision = 'conditions_unresolved'
    elif all(gates[k] for k in ('season_matches', 'month_main_root', 'rooted_external_support', 'no_visible_opposition')):
        decision = 'strong_tendency'
    elif all(gates[k] for k in ('season_controls', 'no_same_element_roots', 'no_visible_support', 'no_hidden_resource', 'rooted_visible_officer')):
        decision = 'weak_tendency'
    elif support and counter:
        decision = 'competing_evidence'
    else:
        decision = 'conditions_unresolved'
        blockers.append('未满足本模块的任一窄条件组合，不补造强弱定案')
    remaining = ['未建模司令、相对作用效力和特殊格；趋势只在本项目窄条件内成立',
                 '根气有字不保证有效；没有以数量或固定兑换权重比较']
    remaining += [u['text'] for u in unassessed]
    rules = []
    ids = lambda rows: [e['id'] for e in rows]
    for rid, fact_ids, counter_ids, gaps in [
        ('ST01', ['month.branch'], ids(visible_opposition), ['得令与失令均不足以单独定强弱']),
        ('ST02', ids(roots), [], ['同五行藏干根不是原书全部根义；主藏顺序不等于司令']),
        ('ST03', ids(visible_support), ids(visible_opposition), ['透干和根不能按固定数量兑换']),
        ('ST04', ids(support), ids(counter), ['相生相克方向不保证有效，克泄耗不等于现实凶事']),
        ('ST05', [x for c in contested for x in c['fact_ids']], [], ['合冲效力尚未裁决，所有原事实保留'])]:
        rules.append(dict(id=rid, facts=list(dict.fromkeys(fact_ids)), counterevidence=counter_ids,
                          missing_conditions=gaps, source_pages=PAGES[rid], status='conditional' if not blockers else 'withheld'))
    names = {'strong_tendency': '窄条件下偏强趋势', 'weak_tendency': '窄条件下偏弱趋势',
             'competing_evidence': '生扶与克泄耗证据相持，尚不能判定强弱', 'conditions_unresolved': '条件未决，暂不判强弱'}
    show = lambda rows: '、'.join(e['text'] for e in rows) if rows else '已知柱未见'
    why = {'strong_tendency': '月令同气且有月支主根，外部印比透干有根，未见外部克泄耗透干；隐藏反向线索仍保留',
           'weak_tendency': '月令旺气克日主，未见同五行根、外部印比或藏印，外部官杀有根；无根不等于从格',
           'competing_evidence': '两侧均有具体位置，未满足任何偏强或偏弱的窄条件组合；相持不表示力量相等',
           'conditions_unresolved': '；'.join(blockers)}[decision]
    text = '日干' + day + dw + '：' + names[decision] + '。理由：' + why + '。'
    text += month + '月的本模块核心旺气为' + (seasonal or '未判') + '，不把得令当成全盘强弱。'
    text += '同五行藏干根：' + show(roots) + '。支持偏强的生扶线索：' + show(support) + '。支持偏弱的反向线索：' + show(counter) + '。'
    text += '透干支持检查：' + ('；'.join(p['text'] for p in support_paths) or '已知柱无外部印比透干') + '。'
    if contested:
        text += '；'.join(c['text'] for c in contested) + '。'
    if unassessed:
        text += '未评估关系：' + '；'.join(u['text'] for u in unassessed) + '。'
    text += '未建模司令、相对作用效力和特殊格；本趋势仅对当前输入候选成立，改时、跨节令或跨日须重算。'
    text += '这是传统结构的项目条件假说，不是人生预测；月令用神不自动等于有利五行，不指定唯一喜忌。'
    return dict(rule_version=VERSION, decision=decision, status='withheld' if blockers else 'conditional',
                facts=[dict(id='month.branch', position='month', branch=month, seasonal_element=seasonal)] + evidence,
                supporting_fact_ids=ids(support), counterevidence_fact_ids=ids(counter), root_fact_ids=ids(roots),
                support_paths=support_paths, pressure_paths=pressure_paths, contested_effects=contested,
                unassessed_interactions=unassessed,
                source_model_conflicts=disputed, missing_conditions=blockers, unresolved_effects=remaining,
                conditions=gates, rules=rules, text=text, attribution=source,
                changing_conditions=['补全或改动时柱须重查两侧及所有根', '跨节令须重算月令；跨日须重算十神与根',
                                     '加入或移除印比、克泄耗透干或合冲关系须重新比较，不能沿用本次趋势'],
                temporal_scope='single_input_candidate', predictive_validity='unvalidated', prediction_guarantee=False,
                scope='日主承受证据比较；非完整强弱、成格、调候或喜忌算法')


def render_attribution(source):
    return ['', '强弱证据依据：' + source['label'] + '；' + source['path'] + '；ST01–ST05；'
            '《子平真诠》1926年第2卷 PDF20–23、25（1起算）。',
            '原扫描目录：' + source['upstream_url'],
            '来源/改编：' + source['adaptation'] + '；原创释义 MIT，既有滴天髓改编许可不变。']
