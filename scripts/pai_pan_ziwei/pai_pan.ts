/**
 * 紫微斗数排盘 CLI — high-confidence-mingli-skill 内置引擎
 *
 * [来源] 拷贝自 ziwei-doushu skill (~/.agents/skills/ziwei-doushu/scripts/pai_pan.ts)，2026-10-01。
 * 本仓为独立副本（mingli v4 三盘引擎之一），上游修复不同步至此；本副本专属改动见 git log。
 * 引擎：vendor/（Renhuai123/ziwei-doushu@88194a4，MIT），底层排盘 iztro 2.6.1。
 * 输出以脚本 stdout 为准：十二宫、大限、四化均由引擎计算，禁止口算覆盖；格局仅为实现规则匹配。
 *
 * 用法（在本目录先 npm install 一次）：
 *   npx tsx pai_pan.ts --solar 1990-05-15 --shichen 午 --sex 男
 *   npx tsx pai_pan.ts --solar 1990-05-15 --hour 12:30 --sex 男 --name 张三 --place 北京
 *
 * 参数：
 *   --solar YYYY-MM-DD   阳历生日（必填）
 *   --hour HH:MM         具体出生时间（与 --shichen 互斥）
 *   --shichen 子|丑|寅|卯|辰|巳|午|未|申|酉|戌|亥  时辰地支（与 --hour 互斥）
 *   --sex 男|女           必填（决定大限顺逆）
 *   --name  姓名（可选，仅展示）
 *   --place 出生地（可选，仅展示）
 *   --explain-rules     显示实现规则的解释及局限（不启用事件预测）
 *   --temporal-uncertainty  出生时间存在非零误差，暂缓已审增补观察主题
 *   --format text|json  默认 text；两种格式共享 rule_output
 *   --age-year YYYY      查询该公历年的虚岁和所处大限（默认当年）
 */

import { generateChart, getLunarInfo } from './vendor/algorithm';
import { renderDomainReading } from './domain_reading';
import { renderReviewedStructure } from './reviewed_structure';
import { buildRuleOutput } from './rule_output';
import { getSiHuaByStem, getLiuNianSiHua, getYearStemIndex, getYearBranchIndex } from './vendor/sihua';
import { STEMS, BRANCHES } from './vendor/constants';

interface Args {
  solar?: string;
  hour?: string;
  shichen?: string;
  sex?: string;
  name?: string;
  place?: string;
  ageYear?: number;
  birthYear?: number;
  format?: string;
  explainRules?: boolean;
  temporalUncertainty?: boolean;
}

class UsageError extends Error {}

function fail(msg: string): never {
  throw new UsageError(msg);
}

function parseArgs(argv: string[]): Args {
  const args: Args = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    switch (key) {
      case '--explain-rules': args.explainRules = true; break;
      case '--temporal-uncertainty': args.temporalUncertainty = true; break;
      case '--format': args.format = value; i++; break;
      case '--solar': args.solar = value; i++; break;
      case '--hour': args.hour = value; i++; break;
      case '--shichen': args.shichen = value; i++; break;
      case '--sex': args.sex = value; i++; break;
      case '--name': args.name = value; i++; break;
      case '--place': args.place = value; i++; break;
      case '--age-year': args.ageYear = Number(value); i++; break;
      case '--birth-year': args.birthYear = Number(value); i++; break;
      default: fail('未知参数（仅支持 --solar --hour --shichen --sex --name --place --age-year）');
    }
  }
  return args;
}

/** HH:MM → 时辰地支索引（23:00-00:59=子, 01-02:59=丑, ...） */
function hourToShichenIndex(hhmm: string | undefined): number {
  const m = hhmm ? hhmm.match(/^(\d{1,2}):(\d{2})$/) : null;
  if (!m) fail('--hour 格式应为 HH:MM');
  const h = parseInt(m[1], 10);
  if (Number.isNaN(h) || h < 0 || h > 23) fail('--hour 小时应为 0-23');
  if (Number(m[2]) > 59) fail('--hour 分钟应为 00-59');
  return Math.floor(((h + 1) % 24) / 2);
}

const SHICHEN_NAMES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

function starText(star: { name: string; type: string; brightness?: string; brightnessRaw?: string | null; siHua?: string }): string {
  const parts = [star.name];
  if (star.type === 'major') {
    parts.push('(' + (star.brightnessRaw || '亮度未提供') + ')');
  }
  if (star.siHua) parts.push('化' + star.siHua);
  return parts.join(' ');
}

function palaceNameOf(chart: ReturnType<typeof generateChart>, starName: string): string {
  const p = chart.palaces.find(p => p.stars.some(s => s.name === starName));
  return p ? p.name : '不入十二宫';
}

function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.format !== undefined && !['text', 'json'].includes(args.format)) fail('--format 应为 text 或 json');

  if (!args.solar || !args.sex) {
    fail('必填: --solar YYYY-MM-DD --sex 男|女，时辰用 --hour HH:MM 或 --shichen 子');
  }
  const dateMatch = args.solar ? args.solar.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/) : null;
  if (!dateMatch) fail('--solar 格式应为 YYYY-MM-DD');
  const year = parseInt(dateMatch[1], 10);
  const month = parseInt(dateMatch[2], 10);
  const day = parseInt(dateMatch[3], 10);

  const checkedDate = new Date(0);
  checkedDate.setUTCFullYear(year, month - 1, day);
  if (year < 1 || checkedDate.getUTCFullYear() !== year || checkedDate.getUTCMonth() !== month - 1 || checkedDate.getUTCDate() !== day) fail('--solar 不是有效公历日期');
  if (args.hour && args.shichen) fail('--hour 与 --shichen 互斥');
  const ageYear = args.ageYear ?? new Date().getFullYear();
  const birthYear = args.birthYear ?? year;
  if (!Number.isInteger(birthYear) || Math.abs(birthYear - year) > 1 || birthYear < 1) fail('--birth-year 须为原始民用出生年，仅允许跨年校正');
  if (!Number.isInteger(ageYear) || ageYear < birthYear || ageYear > 9999) fail('--age-year 须为不早于出生年的有效年份');

  let shichenIndex: number;
  if (args.hour) {
    shichenIndex = hourToShichenIndex(args.hour);
  } else if (args.shichen) {
    shichenIndex = SHICHEN_NAMES.indexOf(args.shichen);
    if (shichenIndex < 0) fail('--shichen 应为 子丑寅卯辰巳午未申酉戌亥 之一');
  } else {
    fail('时辰必填: --hour HH:MM 或 --shichen 子（时辰未知无法定命宫，无法排盘）');
  }

  const gender = args.sex === '男' ? 'male' : args.sex === '女' ? 'female' : null;
  if (!gender) fail('--sex 应为 男 或 女');

  const chart = generateChart({
    year, month, day, hour: shichenIndex, gender,
    name: args.name, city: args.place,
  }, ageYear, birthYear);

  const lunar = getLunarInfo(year, month, day);

  const ruleOutput = buildRuleOutput(chart, args.explainRules, {temporalUncertainty:!!args.temporalUncertainty});
  if (args.format === 'json') {
    console.log(JSON.stringify({ schema_version: 1, engine: 'iztro 2.6.1 / vendored wrapper',
      input: { solar: args.solar, shichenIndex, gender, ageYear, birthYear, temporalUncertainty:!!args.temporalUncertainty }, lunar, chart, rule_output: ruleOutput }, null, 2));
    return;
  }
  // ── 输出 ──
  console.log('## 输入');
  console.log('阳历：' + year + '-' + String(month).padStart(2, '0') + '-' + String(day).padStart(2, '0'));
  console.log('时辰：' + SHICHEN_NAMES[shichenIndex] + (args.hour ? '（由 ' + args.hour + ' 换算）' : ''));
  console.log('性别：' + args.sex + (args.name ? '  姓名：' + args.name : '') + (args.place ? '  出生地：' + args.place : ''));

  console.log('\n## 农历');
  console.log('农历：' + lunar.lunarYear + '年' + (lunar.isLeapMonth ? '闰' : '') + lunar.lunarMonth + '月' + lunar.lunarDay + '日');
  console.log('年干支：' + STEMS[lunar.yearStem] + BRANCHES[lunar.yearBranch]);

  console.log('\n## 命盘');
  const mingPalace = chart.palaces.find(p => p.branch === chart.mingGongBranch)!;
  console.log('命宫：' + BRANCHES[chart.mingGongBranch] + '（' + STEMS[mingPalace.stem] + BRANCHES[chart.mingGongBranch] + '）');
  console.log('身宫：' + BRANCHES[chart.shenGongBranch]);
  console.log('五行局：' + chart.wuxingJuName);
  console.log('紫微：' + BRANCHES[chart.ziweiPos]);

  console.log('\n## 十二宫');
  for (const p of chart.palaces) {
    const ganZhi = STEMS[p.stem] + BRANCHES[p.branch];
    const majors = p.stars.filter(s => s.type === 'major').map(starText);
    const others = p.stars.filter(s => s.type !== 'major').map(starText);
    let line = '【' + p.name + '】' + ganZhi + '｜' + (majors.length ? majors.join(' ') : '空宫');
    if (p.isEmpty && p.borrowedFromName && p.borrowedStars?.length) {
      line += '（借' + p.borrowedFromName + '：' + p.borrowedStars.join('、') + '）';
    }
    if (others.length) line += '｜' + others.join(' ');
    if (p.daXianAge) line += '｜大限' + p.daXianAge[0] + '-' + p.daXianAge[1];
    const marks: string[] = [];
    if (p.isShenGong) marks.push('身宫');
    if (p.isCurrentDaXian) marks.push(`${ageYear} 年所处大限`);
    if (marks.length) line += '｜' + marks.join('/');
    console.log(line);
  }

  const nativeSiHua = getSiHuaByStem(lunar.yearStem);
  console.log('\n## 本命四化（年干 ' + STEMS[lunar.yearStem] + '）');
  for (const type of ['禄', '权', '科', '忌'] as const) {
    console.log('化' + type + '：' + nativeSiHua[type] + '（落 ' + palaceNameOf(chart, nativeSiHua[type]) + '）');
  }

  console.log(`\n## 大限（公历目标年 ${ageYear} 年，公历年差加一虚岁 ${chart.currentAge}）`);
  const hasAnnualWindows = chart.daXians.length > 0 &&
    birthYear + chart.daXians[chart.daXians.length - 1].endAge <= 9999;
  if (hasAnnualWindows) {
    console.log(`公历年度窗以原民用出生年 ${birthYear} 为准，左端包含、右端不包含。`);
  } else if (chart.daXians.length) {
    console.log('已列大限超出可表示的公历年度范围，保留原虚岁段。');
  }
  if (args.temporalUncertainty) {
    console.log('下表按中心时刻排出。实际出生候选的大限须分别核对。');
  }
  if (chart.currentDaXianIndex === -1) {
    console.log(`${ageYear} 年未落入已列大限。`);
  }
  chart.daXians.forEach((dx, i) => {
    const marker = i === chart.currentDaXianIndex ? ' ←目标年所在' : '';
    const window = hasAnnualWindows
      ? `｜[${String(birthYear + dx.startAge - 1).padStart(4, '0')}-01-01, ${String(birthYear + dx.endAge).padStart(4, '0')}-01-01)`
      : '';
    console.log(dx.startAge + '-' + dx.endAge + '　' + dx.palaceName + '(' + BRANCHES[dx.palaceBranch] + ')' + marker + window);
  });

  console.log('\n## 格局（实现规则匹配）');
  console.log(ruleOutput.scope);
  console.log('实现来源：' + ruleOutput.source);
  console.log(ruleOutput.terminology);
  if (!ruleOutput.patterns.length) console.log('（无匹配格局，不表示现实中缺乏某种能力或机会）');
  for (const pat of ruleOutput.patterns) {
    console.log(pat.name + '｜旧规则分类 ' + pat.level + '（不是风险或置信度评级）');
    console.log('  ' + pat.description);
    if (pat.conditions.bonus.length) console.log('  附加条件：' + pat.conditions.bonus.join('；'));
    if (pat.conditions.breaking.length) console.log('  限制条件：' + pat.conditions.breaking.join('；'));
    if (pat.explanation) {
      for (const value of Object.values(pat.explanation)) console.log('  说明：' + value);
    }
  }
  console.log(renderDomainReading(ruleOutput.domain_reading));
  console.log(renderReviewedStructure(ruleOutput.reviewed_structure));
  console.log('\n## 命宫小结（排布事实）');
  console.log('主星：' + (ruleOutput.ming_summary.stars.join('、') || '空宫（借星另列）'));
  console.log(ruleOutput.ming_summary.meaning);

  console.log(`\n## 流年（公历年度索引 ${ageYear} 年，虚岁口径：${chart.currentAge}）`);
  const ln = getLiuNianSiHua(ageYear);
  const lnBranch = BRANCHES[getYearBranchIndex(ageYear)];
  console.log(`公历年度干支 ${ln.stemName}${lnBranch}｜旧表四化 禄-${ln.transforms['禄']} 权-${ln.transforms['权']} 科-${ln.transforms['科']} 忌-${ln.transforms['忌']}`);
  for (const type of ['禄', '权', '科', '忌'] as const) {
    console.log('化' + type + '：' + ln.transforms[type] + '（落 ' + palaceNameOf(chart, ln.transforms[type]) + '）');
  }
  console.log('按实际查询日期核对流年时，以春节为年界，使用 scripts/ziwei_dynamic_facts.mjs。');
}

try {
  run();
} catch (error) {
  if (error instanceof UsageError) {
    console.error(error.message);
    process.exitCode = 2;
  } else {
    throw error;
  }
}
