/** Presentation boundary: vendor recognizers are implementation rules, not predictions.
 * Keep vendor provenance/legal files intact. Never emit their narrative descriptions.
 */
import { buildDomainReading } from './domain_reading';
import { detectPatterns } from './vendor/patterns';
import type { ZiweiChart } from './vendor/types';

export const RULE_SCOPE = '仅为本仓实现的星曜组合匹配；不证明古籍原文、学派共识或现实预测能力。不能据此判断健康、事故、财富、职业或人格。';
export const RULE_SOURCE = 'scripts/pai_pan_ziwei/vendor/patterns.ts#detectPatterns';

// Reviewed replacements retain the actual tested condition, not its forecast.
// Do not remove all parentheses: some contain real constraints (e.g. missing stars).
const descriptiveConditions: Record<string, string> = {
  '紫微独坐命宫（无天府同坐）': '紫微入命且无天府同宫（未排除其他主星同宫）',
  '魁钺贵人加照': '三方四正有天魁或天钺',
  '地空地劫双夹会照（紫微忌空劫）': '三方四正地空、地劫计数至少为二（非夹宫判定）',
  '紫微天府同宫（不在命宫，会照减力）': '紫微天府同宫，不在命宫',
  '紫府宫坐空劫（破紫府之贵气）': '紫府同宫处有地空或地劫',
  '三方四正煞星过多': '三方四正四煞计数至少为三',
  '太阳落陷（阳梁失辉）': '太阳旧亮度分组为 dim（不或陷，非精确落陷）',
  '三方煞重': '三方四正四煞计数至少为二',
  '贪狼宫又见羊陀（破横发之力）': '贪狼所在宫有擎羊或陀罗',
  '贪狼遇空劫（财来财去）': '贪狼所在宫有地空或地劫',
  '三方有化禄或化权（动得有力）': '三方星名集合包含化禄或化权（旧规则按星名检查，非四化字段）',
  '辅弼同会（变动中得贵人）': '三方四正有左辅和右弼',
  '煞星过重（动而无成）': '三方四正四煞计数至少为三',
  '命坐空劫（动得辛苦）': '命宫有地空或地劫',
  '煞星过多（机月同梁忌煞）': '三方四正四煞计数至少为三',
  '廉相宫坐擎羊（廉杀羊倾向）': '廉贞天相所在宫有擎羊（不等于廉杀羊规则成立）',
  '武曲化忌（武曲化忌为财劫之兆）': '武曲化忌',
  '武杀宫煞星过多': '武曲七杀所在宫有至少一颗四煞',
  '未宫日月同辉（古书云未宫日月双美）': '太阳太阴同在未宫',
  '日月落陷（夹命无光）': '太阳或太阴旧亮度分组为 dim（不或陷，非精确落陷）',
  '寅宫太阳庙旺，巨门得日光化解是非': '巨门太阳同在寅宫（本条只检查宫位）',
  '巨门化禄/化权（口才生财）': '巨门化禄或化权',
  '巨门化忌（口舌官非）': '巨门化忌',
  '申宫太阳偏西，巨门暗曜更显': '巨门太阳同在申宫',
  '文昌会照（石中隐玉得明）': '三方四正有文昌',
  '巨门化忌（玉藏深泥）': '巨门化忌',
  '辅弼相助': '三方四正有左辅或右弼',
  '煞星会照（珠光黯淡）': '三方四正四煞计数至少为二',
  '无辅弼（孤君无臣）': '三方四正没有左辅和右弼',
  '紫微遇空劫（古书最忌）': '命宫有地空或地劫',
  '命坐空劫（双禄遇空，财来财去）': '命宫有地空或地劫',
  '再会七杀或破军（武职大贵）': '三方四正有七杀或破军',
};

export function describeCondition(value: string): string {
  return descriptiveConditions[value] ?? value;
}

const BRANCH_NAMES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const ALIASES: Record<string, string[]> = {
  '昌曲': ['文昌', '文曲'], '辅弼': ['左辅', '右弼'], '魁钺': ['天魁', '天钺'],
  '羊陀': ['擎羊', '陀罗'], '空劫': ['地空', '地劫'], '四煞': ['擎羊', '陀罗', '火星', '铃星'],
  '坐煞': ['擎羊', '陀罗', '火星', '铃星'], '双煞': ['擎羊', '陀罗', '火星', '铃星'],
  '煞星': ['擎羊', '陀罗', '火星', '铃星'], '日月': ['太阳', '太阴'],
};

/** Chart-specific evidence, not an independent reimplementation of the recognizer.
 * Include mentioned-but-outside stars: a missing member is often the useful countercheck.
 */
function explainChartConditions(chart: ZiweiChart, conditions: {required: string[]; bonus: string[]; breaking: string[]}) {
  const terms = Object.values(conditions).flat().join('；');
  const selected = new Set<string>();
  for (const [alias, names] of Object.entries(ALIASES)) {
    if (terms.includes(alias)) names.forEach(name => selected.add(name));
  }
  const sf = [0, 4, 8, 6].map(offset => (chart.mingGongBranch + offset) % 12);
  const rows: string[] = [];
  const outside: string[] = [];
  chart.palaces.forEach((palace, pi) => palace.stars.forEach((star, si) => {
    const mentionsTransform = star.siHua && terms.includes('化' + star.siHua);
    if (!terms.includes(star.name) && !selected.has(star.name) && !mentionsTransform) return;
    const relation = sf.includes(palace.branch) ? '在命宫三方四正内' : '不在命宫三方四正内';
    rows.push(`${star.name}在${palace.name.endsWith('宫') ? palace.name : palace.name + '宫'}（${BRANCH_NAMES[palace.branch]}），原始亮度${star.brightnessRaw || '未提供'}，${star.siHua ? '化' + star.siHua : '无本命四化标记'}，${relation} [chart.palaces[${pi}].stars[${si}]]`);
    if (!sf.includes(palace.branch)) outside.push(star.name);
  }));
  const ming = chart.palaces.find(p => p.branch === chart.mingGongBranch);
  const majors = ming?.stars.filter(star => star.type === 'major').map(star => star.name) ?? [];
  return {
    chart_facts: rows.length ? rows.join('；') : '本条没有可按完整星名或已知别名定位的星曜；请对照十二宫，不补猜。',
    boundary_checks: `命宫实际主星：${majors.join('、') || '无'}；本条提及的星中不在命宫三方四正内者：${outside.join('、') || '无'}。这不自动否定同宫、夹宫或身宫规则，须按本条要求的范围分别核对。`,
    matched_branches: `成立条件：${conditions.required.join('；')}。已触发附加分支：${conditions.bonus.join('；') || '无'}。已触发限制分支：${conditions.breaking.join('；') || '无'}。未触发限制不等于已经排除一切反证。`,
  };
}

export function buildRuleOutput(chart: ZiweiChart, explain = false) {
  return {
    kind: 'implementation_rule_matches',
    domain_reading: buildDomainReading(chart),
    scope: RULE_SCOPE,
    source: RULE_SOURCE,
    source_status: 'implementation_attribution_only; classical_citation_unverified',
    terminology: '三方四正指命宫及其地支偏移 +4、+8、+6 的宫位；四煞指擎羊、陀罗、火星、铃星。',
    patterns: detectPatterns(chart).map(pat => {
      const conditions = {
        required: (pat.conditions?.required ?? []).map(describeCondition),
        bonus: (pat.conditions?.bonus ?? []).map(describeCondition),
        breaking: (pat.conditions?.breaking ?? []).map(describeCondition),
      };
      return {
        name: pat.name,
        level: pat.level,
        level_meaning: '旧规则内部分类，不是好坏命、风险、概率或置信度评级',
        description: '本实现匹配条件：' + conditions.required.join('；'),
        palaces: pat.palaces,
        conditions,
        source: RULE_SOURCE,
        ...(explain ? { explanation: {
          ...explainChartConditions(chart, conditions),
          method: 'required 为识别器列出的成立条件；bonus / breaking 为已命中的附加分支，不是数值加分或事件预警。位置与亮度可对照 chart.palaces 复核。',
          limitations: '条件文字是代码摘要，规则可能简化或有实现缺陷；不能自动视为完整传统格局。旧亮度 bright 合并庙/旺，dim 合并不/陷；精确等级以 brightnessRaw 为准。未运行流年事件触发或现实风险评估。',
          classical_source_status: '上游文案所列书名与章节未逐条核验；不作为已核对的原典引文输出。详批需另行查阅来源登记并核对原文。',
        } } : {}),
      };
    }),
    ming_summary: {
      stars: chart.palaces.find(p => p.branch === chart.mingGongBranch)?.stars
        .filter(s => s.type === 'major').map(s => s.name) ?? [],
      meaning: '仅列命宫实际主星；空宫借星见十二宫 borrowedStars，不能据星名推断个人性格。',
    },
  };
}
