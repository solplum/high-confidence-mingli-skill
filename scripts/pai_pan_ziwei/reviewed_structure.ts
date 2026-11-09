/** Approved, bounded project paraphrases. Coordinates do not establish personal effects. */
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SI_HUA_TABLE } from './vendor/constants';
import type { ZiweiChart, Palace } from './vendor/types';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';
const STEMS = '甲乙丙丁戊己庚辛壬癸';
const MAJORS = ['紫微','天机','太阳','武曲','天同','廉贞','天府','太阴','贪狼','巨门','天相','天梁','七杀','破军'];
export const ADJUNCT_GROUPS = {
  six_lucky: ['左辅','右弼','天魁','天钺','文昌','文曲'],
  six_sha: ['地空','地劫','火星','铃星','陀罗','擎羊'],
  two_assisting: ['天马','禄存'],
};
const ADJUNCTS = Object.values(ADJUNCT_GROUPS).flat();
const DOMAINS: Record<string,string> = {命:'自身选择与方向',财帛:'资源分配与使用',官禄:'做事与落实方式',迁移:'对外互动'};
const RECORD_IDS = ['ziwei-reviewed-ZW-K01','ziwei-reviewed-ZW-K02-groups','ziwei-reviewed-ZW-K02-fubi',
  'ziwei-reviewed-ZW-K03','ziwei-reviewed-ZW-K04','ziwei-reviewed-ZW-K05-attachment','ziwei-reviewed-ZW-K05-lu'];
const NAMED_PAIRS: [string,string][] = [['左辅','右弼'],['天魁','天钺'],['文昌','文曲'],['地空','地劫'],['擎羊','陀罗'],['火星','铃星'],['太阳','太阴']];
const normalize = (name:string) => name.replace(/宫$/, '');
const validBranch = (value:number) => Number.isInteger(value) && value >= 0 && value < 12;
const nonempty = (value:unknown):value is string => typeof value === 'string' && value.trim().length > 0;
const validNatalTransform = (value:unknown) => value===undefined || value===null || value==='' || (typeof value==='string'&&['禄','权','科','忌'].includes(value));
const palaceLabel = (p:Palace) => normalize(p.name)+'宫（'+BRANCHES[p.branch]+'）';
const RELATION_LABELS:Record<string,string>={actual:'实坐',trine_plus4:'三合/扶拱',trine_plus8:'三合/扶拱',opposite:'对宫',next:'后邻宫',previous:'前邻宫'};
type Status = 'structure_only' | 'conditional' | 'not_applicable' | 'withheld';
interface RecordEntry { id:string; rule_id:string; summary:string; conditions:unknown; exclusions:unknown; citation:any; [key:string]:any }
interface Module { rule_id:string; record_id:string; status:Status; summary:string; conditions:unknown; exclusions:unknown;
  citation:any; rows:any[]; counterevidence:string[]; unknown:string[] }
interface Panel { version:string; status:Status; scope:string; source_status:string; input_status:string; temporal_uncertainty:boolean;
  errors:string[]; roster:any; modules:Record<string,Module> }

function loadSources(): {records:RecordEntry[];star_themes:any[]} {
  // Reload on every call: editing or corrupting sources in this process must revoke eligibility.
  const result = spawnSync('python3', [ROOT+'scripts/reviewed_knowledge.py','--system','ziwei','--profile','ziwei-reviewed-structure-v1'],
    {encoding:'utf8',timeout:15000,maxBuffer:2*1024*1024});
  if (result.status !== 0) throw Error('受限增补来源门不可用或未通过：'+(result.stdout?.trim() || result.error?.message || '检查失败'));
  const data = JSON.parse(result.stdout);
  if (!Array.isArray(data.records) || data.records.length !== RECORD_IDS.length || RECORD_IDS.some(id=> {
    const matches=data.records.filter((r:any)=>r.id===id);
    if (matches.length !== 1) return true;
    const r=matches[0], c=r.citation;
    return r.system!=='ziwei' || r.profile!=='ziwei-reviewed-structure-v1' || r.source_id!=='ziwei-reviewed-structure-source' ||
      r.content_kind!=='project_paraphrase' || r.usage_scope!=='conditional_module_only' ||
      !nonempty(r.rule_id) || !nonempty(r.summary) || !r.conditions || !r.exclusions || !r.source_span ||
      !c || c.record_id!==id || c.source_id!==r.source_id || c.attribution_kind!=='project_paraphrase' ||
      !nonempty(c.source_label) || !nonempty(c.revision) || !nonempty(c.locator);
  })) throw Error('受限增补记录缺失、重复或字段不符合登记口径');
  if (!Array.isArray(data.star_themes) || data.star_themes.length!==14 || MAJORS.some((star,i)=> {
    const matches=data.star_themes.filter((r:any)=>r.star===star);
    return matches.length!==1 || matches[0].id!=='ziwei-domain-star-'+i ||
      matches[0].profile!=='ziwei-domain-conditional' || !nonempty(matches[0].theme) || !nonempty(matches[0].question) ||
      matches[0].citation?.record_id!==matches[0].id || matches[0].citation?.attribution_kind!=='project_paraphrase';
  })) throw Error('原有十四主星主题的登记不完整');
  return data;
}

function chartError(chart:ZiweiChart):string|null {
  if (!chart || !validBranch(chart.mingGongBranch) || !Array.isArray(chart.palaces) || chart.palaces.length!==12 ||
      chart.palaces.some(p=>!p || !validBranch(p.branch) || !nonempty(p.name) || !Array.isArray(p.stars)) ||
      new Set(chart.palaces.map(p=>p.branch)).size!==12 || new Set(chart.palaces.map(p=>normalize(p.name))).size!==12) {
    return '十二宫不完整、名称重复或地支无效，不能核对位置与缺席';
  }
  const names=['命','父母','福德','田宅','官禄','仆役','迁移','疾厄','财帛','子女','夫妻','兄弟'];
  if (chart.palaces.some(p=>normalize(p.name)!==names[(p.branch-chart.mingGongBranch+12)%12])) return '宫名与命宫地支关系不符';
  if (chart.palaces.some(p=>p.stars.some(s=>!s || !nonempty(s.name) || !['major','minor','lucky','sha'].includes(s.type)))) return '星曜数组含缺失或非法字段';
  if (chart.palaces.some(p=>p.stars.some(s=>!validNatalTransform(s.siHua)))) return '原始 siHua 含非法值，不能把它当作无四化';
  return null;
}

function starFacts(chart:ZiweiChart,p:Palace) {
  const pi=chart.palaces.indexOf(p);
  return p.stars.map((s,si)=>({name:s.name,type:s.type,brightness_raw:s.brightnessRaw??null,natal_transform:s.siHua||null,
    palace:p.name,branch:p.branch,palace_path:`chart.palaces[${pi}]`,path:`chart.palaces[${pi}].stars[${si}]`}));
}
function rosterOf(chart:ZiweiChart,names:string[],major=false) {
  const rows=names.map(name=>({name,locations:chart.palaces.flatMap(p=>starFacts(chart,p)).filter(s=>s.name===name)}));
  const problems=rows.filter(r=>r.locations.length!==1 || (major && r.locations[0].type!=='major')).map(r=>r.name);
  if (major) problems.push(...chart.palaces.flatMap(p=>p.stars).filter(s=>s.type==='major'&&!names.includes(s.name)).map(s=>s.name));
  return {complete:problems.length===0,unverified:problems,rows};
}

/** A position check only: a named star must occur exactly once on each opposite adjacent side. */
export function checkFlankingPair(chart:ZiweiChart,targetBranch:number,pair:[string,string]) {
  const reason=chartError(chart);
  if (reason || !validBranch(targetBranch) || pair[0]===pair[1]) return {stars:pair,status:'withheld',matched:false,facts:[],reason:reason||'目标宫无效或两星同名'};
  const locations=pair.map(name=>chart.palaces.flatMap(p=>starFacts(chart,p)).filter(s=>s.name===name));
  if (locations.some(rows=>rows.length!==1)) return {stars:pair,status:'withheld',matched:false,facts:locations.flat(),reason:'指定两星未各有全局唯一实际位置，不能用缺席或重复证明两侧'};
  const facts=locations.flat(), before=(targetBranch+11)%12,after=(targetBranch+1)%12;
  const matched=(facts[0].branch===before&&facts[1].branch===after)||(facts[1].branch===before&&facts[0].branch===after);
  return {stars:pair,status:'structure_only',matched,facts,reason:matched?'两星实际分处前后邻宫；仅为坐标结构，不是格局效力':'两星未分处前后邻宫，同侧、实坐或三方不能替代'};
}

function reviewedTableCheck() {
  const text=readFileSync(ROOT+'references/vendor/iztro-docs/learn/mutagen.md','utf8');
  const rows=text.split('\n').map(line=>line.trim().match(/^\|([甲乙丙丁戊己庚辛壬癸])\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|$/)).filter(Boolean);
  if (rows.length!==10 || new Set(rows.map(r=>r![1])).size!==10 || rows.some(r=>r!.slice(2).some((name,i)=>name.trim()!==SI_HUA_TABLE[STEMS.indexOf(r![1])]?.[i]))) {
    return {matched:false,cells_checked:40,reason:'固定数字资料的十干四化表与本地表不一致'};
  }
  return {matched:true,cells_checked:40,reason:'固定版数字表与本地十干四化表逐格一致；不证明输入年干或现实效力'};
}

export function buildReviewedStructure(chart:ZiweiChart,{temporalUncertainty=false}:{temporalUncertainty?:boolean}={}):Panel {
  const panel:Panel={version:'ziwei-reviewed-structure-v1',status:'structure_only',
    scope:'已批准的固定本命结构与少量有条件观察问题。结构匹配不表示效力、个人特征、预测能力或人生结果；不启用个人 ledger 新用途。',
    source_status:'pending',input_status:'仅据给定排盘输入生成候选；未核实出生记录真实性。',temporal_uncertainty:temporalUncertainty,
    errors:[],roster:null,modules:{}};
  let records:RecordEntry[]=[],themes:any[]=[];
  try {const source=loadSources();records=source.records;themes=source.star_themes;panel.source_status='registered_project_paraphrase; modern_compilation; pinned_digital_source_only; classical_quote_unverified; unvalidated';}
  catch(error) {panel.errors.push(error instanceof Error?error.message:'来源门失败');panel.source_status='withheld; source_gate_failed';}
  const invalid=chartError(chart);
  if (invalid) panel.errors.push(invalid);
  const make=(key:string,index:number,counterevidence:string[],unknown:string[])=> {
    const r=records.find(r=>r.id===RECORD_IDS[index]);
    return panel.modules[key]={rule_id:r?.rule_id??RECORD_IDS[index],record_id:RECORD_IDS[index],status:panel.errors.length?'withheld':'structure_only',
      summary:r?.summary??'来源未通过，暂缓已核来源释义。',conditions:r?.conditions??[],exclusions:r?.exclusions??[],citation:r?.citation??null,
      rows:[],counterevidence,unknown:[...unknown,...panel.errors]};
  };
  const empty=make('empty_borrowing',0,['本宫实有任一主星即不满足空宫；借星清单无对宫实际路径或字段残留时暂缓。'],['空宫现实效力与借星权重未知；不继承对宫亮度或本命四化。']);
  const groups=make('adjunct_groups',1,['十四辅星分组按精确星名；天空不属于六煞，旧 type 和四煞计数保持原样。'],['分类不表示现实好坏、吉煞抵消或辅煞权重。']);
  const fubi=make('fubi_observation',2,['若实际没有相应协作行为，或角色职责、训练更能解释，应撤回适用于本人的假设。'],['缺少本人实际例子；辅弼亮度缺失时只保留未知，不推表达强弱。']);
  const jiliang=make('jiliang_observation',3,['若本人偏好独立完成、不愿介入群体或有反向实例，应撤回，不能归因于特质被压抑。'],['缺少本人在群体中协调的支持与反向实例，尚未确认适用。','辅煞与完整格局权重未建模；不能据此认定格名、人格或职位。']);
  const relations=make('palace_relations',4,['两星同在一个邻宫、仅在三方四正或同星重复都不满足两侧夹结构。'],['这里只核坐标；未登记夹拱效力、强弱倍率或事件意义。']);
  const transforms=make('natal_transforms',5,['仅有禄存、宫干自化、运限 overlay 都不能满足本命附着链；错配不补造标记。'],['年界与输入年干真实性未由此表校核证明；四化不是独立实体星。']);
  const lu=make('natal_lu_observation',6,['若无该主题活动增加、观察期不清，或预算、岗位、机会更能解释，不认定主题适用。'],['本人实际投入变化、比较基线与观察期尚未提供，不能确认适用。','化禄增加是象征性观察问题，不是收入、财富、好运或成功；权科忌及多化修饰未建模。']);
  if (invalid) {panel.status='withheld';return panel;}

  const majors=rosterOf(chart,MAJORS,true),adjuncts=rosterOf(chart,ADJUNCTS);
  panel.roster={major_stars:majors,adjunct_stars:adjuncts,
    boundary:'仅检查十四主星和十四辅星的全局唯一实际位置；其他杂曜数组完整性未独立认证，不能由未列出推出缺席。'};
  const rosterComplete=majors.complete&&adjuncts.complete;
  const backgroundMissing=rosterComplete?[]:['十四主星或十四辅星未各有全局唯一实际位置，相关缺席与主题条件未知'];
  const eligible=(module:Module,reasons:string[]):Status => module.citation&&!reasons.length?'conditional':'withheld';
  const commonReasons=[...panel.errors,...backgroundMissing,...(temporalUncertainty?['出生时间存在非零误差，主题候选暂缓']:[])];
  const yearStem=chart.lunarInfo?.yearStem;
  const validStem=Number.isInteger(yearStem)&&yearStem>=0&&yearStem<10;
  const modifierConsistency=(facts:ReturnType<typeof starFacts>)=> {
    if (!validStem) return ['生年干未知，不能核对相关星的本命四化修饰是否漏标'];
    return facts.filter(f=> {
      const index=SI_HUA_TABLE[yearStem].indexOf(f.name);
      const expected=index<0?null:['禄','权','科','忌'][index];
      return f.natal_transform!==expected;
    }).map(f=>f.name+'原始本命四化标记与年干表不一致，不能作为无修饰证据');
  };
  const factsAt=(branch:number)=>starFacts(chart,chart.palaces.find(p=>p.branch===branch)!);
  const offsets=[['actual',0],['trine_plus4',4],['trine_plus8',8],['opposite',6],['next',1],['previous',11]] as const;
  const coordinates=(p:Palace)=>offsets.map(([relation,offset])=> {
    const branch=(p.branch+offset)%12,q=chart.palaces.find(q=>q.branch===branch)!;
    return {relation,offset,branch,palace:q.name,palace_path:`chart.palaces[${chart.palaces.indexOf(q)}]`,stars:factsAt(branch)};
  });
  for (const p of chart.palaces) {
    const actual=starFacts(chart,p),sitting=actual.filter(s=>s.type==='major');
    const opposite=chart.palaces.find(q=>q.branch===(p.branch+6)%12)!;
    const oppositeMajors=starFacts(chart,opposite).filter(s=>s.type==='major');
    const checks:string[]=[];
    if (p.isEmpty!==(sitting.length===0)) checks.push('isEmpty 与实际主星数不一致');
    if (p.oppositeBranch!==opposite.branch) checks.push('oppositeBranch 与 +6 对宫不一致');
    if (!sitting.length) {
      if (p.borrowedFromBranch!==opposite.branch || p.borrowedFromName!==opposite.name || !Array.isArray(p.borrowedStars) ||
          p.borrowedStars.length!==oppositeMajors.length || p.borrowedStars.some((name,i)=>name!==oppositeMajors[i].name)) checks.push('借星清单或源宫字段与实际对宫主星不一致');
    } else if (p.borrowedFromBranch!==undefined || p.borrowedFromName!==undefined || p.borrowedStars!==undefined) checks.push('非空宫仍有借星字段残留');
    empty.rows.push({palace:p.name,branch:p.branch,is_empty:sitting.length===0,status:panel.errors.length||checks.length||!majors.complete?'withheld':sitting.length?'not_applicable':'structure_only',
      actual_stars:actual,borrowed_reference:!sitting.length?oppositeMajors.map(s=>({name:s.name,path:s.path,source_palace:s.palace,source_branch:s.branch,source_palace_path:s.palace_path})):[],
      checks:[...checks,...(!majors.complete?['十四主星位置未核完整，空宫条件未知']:[])],interpretation_status:'withheld',
      explanation:sitting.length?'本宫有实际主星，不使用空宫借星解释。':'本宫无实际主星仍可有辅杂曜；对宫仅作源宫参考，空宫星性继续暂缓。'});
    const relationRows=coordinates(p);
    relations.rows.push({palace:p.name,branch:p.branch,relations:relationRows,
      flanking_checks:NAMED_PAIRS.map(pair=>checkFlankingPair(chart,p.branch,pair)),
      terminology:'实坐0；三合/扶拱+4、+8；对宫+6（此处冲仅是坐标术语）；前后+1、+11。会照不得替代精确坐标。'});
    groups.rows.push({palace:p.name,branch:p.branch,relations:relationRows.map(r=>({...r,stars:r.stars.filter(s=>ADJUNCTS.includes(s.name))})),
      groups:Object.entries(ADJUNCT_GROUPS).map(([group,names])=>({group,names,actual_stars:actual.filter(s=>names.includes(s.name))}))});
    const pair=actual.filter(s=>s.name==='左辅'||s.name==='右弼');
    const matched=pair.length===2&&new Set(pair.map(s=>s.name)).size===2;
    const domain=DOMAINS[normalize(p.name)]??null;
    const fubiReasons=[...commonReasons,...modifierConsistency(pair),...(!domain?['该宫领域未登记为窄主题用途']:[]),...(!matched?['左辅右弼没有各一颗实际同宫']:[]),
      ...(pair.some(s=>s.natal_transform)?['辅弼自身存在未登记的本命四化修饰']:[])];
    fubi.rows.push({palace:p.name,branch:p.branch,domain,structure_matched:matched,status:eligible(fubi,fubiReasons),facts:pair,actual_major_stars:sitting,
      question:eligible(fubi,fubiReasons)==='conditional'?`在${domain}领域，你的支持或协调是否兼有直接介入与倾听配合？是否尊重对方需要，还是造成代办或犹豫？`:null,
      background:actual.filter(s=>s.natal_transform&&!pair.some(f=>f.path===s.path)),
      checks:fubiReasons,brightness_boundary:'原始亮度只列实际值；此问题不推表达强弱。同宫其他四化只留事实，不能自行增减主题效力。'});
  }
  if (empty.rows.some(row=>row.status==='withheld')) empty.unknown.push('部分宫借星结构或主星完整性未通过，逐宫见 checks。');
  groups.unknown.push(...backgroundMissing);

  const ming=chart.palaces.find(p=>p.branch===chart.mingGongBranch)!;
  const mingMajors=starFacts(chart,ming).filter(s=>s.type==='major');
  const jlMatched=mingMajors.length===2&&['天机','天梁'].every(name=>mingMajors.some(s=>s.name===name));
  const jlBackground=[0,4,8,6].flatMap(offset=>factsAt((ming.branch+offset)%12)).filter(s=>ADJUNCTS.includes(s.name)||s.natal_transform);
  const jlReasons=[...commonReasons,...modifierConsistency(starFacts(chart,ming)),...(!jlMatched?['命宫实际主星集合不恰为天机、天梁（借星或三方齐星不满足）']:[]),
    ...(mingMajors.some(s=>!nonempty(s.brightness_raw)||!['庙','旺','得','利','平','不','陷'].includes(s.brightness_raw))?['机梁任一原始亮度缺失或等级未知']:[]),
    ...(starFacts(chart,ming).some(s=>s.natal_transform)?['命宫存在未登记的本命四化组合修饰']:[])];
  jiliang.rows.push({palace:ming.name,branch:ming.branch,structure_matched:jlMatched,status:eligible(jiliang,jlReasons),facts:mingMajors,
    background:jlBackground,background_boundary:'三方其他宫本命四化与辅煞只列未建模背景，既不据此增减效力，也不把存在本身当作确定阻断。',
    checks:jlReasons,question:eligible(jiliang,jlReasons)==='conditional'?'你是否会在群体中调整沟通方式、主动协调并照应他人？这种介入何时有效，何时过度？':null});

  let table:any;
  try {table=reviewedTableCheck();} catch(error) {table={matched:false,cells_checked:0,reason:'固定表资料读取失败：'+(error instanceof Error?error.message:'未知错误')};}
  const allFacts=chart.palaces.flatMap(p=>starFacts(chart,p));
  const marked=allFacts.filter(s=>s.natal_transform);
  const attachmentErrors=[...panel.errors,...backgroundMissing,...(!table.matched?[table.reason]:[]),...(!validStem?['chart.lunarInfo.yearStem 不在 0–9']:[])];
  if (marked.some(s=>!['禄','权','科','忌'].includes(s.natal_transform!))) attachmentErrors.push('原始 siHua 含未知化类');
  const chain=['禄','权','科','忌'].map((kind,i)=> {
    const expected=validStem?SI_HUA_TABLE[yearStem][i]:null;
    const markedRows=marked.filter(s=>s.natal_transform===kind),positions=allFacts.filter(s=>s.name===expected);
    const matched=!!expected&&markedRows.length===1&&positions.length===1&&markedRows[0].name===expected;
    if (!matched) attachmentErrors.push('本命化'+kind+'标记与实际唯一位置/年干表不一致');
    return {year_stem:validStem?STEMS[yearStem]:null,year_stem_index:yearStem??null,year_stem_path:'chart.lunarInfo.yearStem',kind,
      expected_star:expected,actual_marked_stars:markedRows,matched,source_paths:markedRows.map(s=>s.path+'.siHua')};
  });
  transforms.rows.push({status:attachmentErrors.length?'withheld':'structure_only',table_check:table,chain,checks:attachmentErrors,
    excluded_layers:'不读取 selfSihua、大限、流年、流月、来因宫或 overlay；禄存仅是独立星名。'});
  transforms.status=attachmentErrors.length?'withheld':'structure_only';
  const nativeLu=marked.filter(s=>s.natal_transform==='禄');
  for (const fact of nativeLu) {
    const p=chart.palaces.find(p=>p.branch===fact.branch)!;
    const theme=themes.find(r=>r.star===fact.name),domain=DOMAINS[normalize(p.name)]??null;
    const others=starFacts(chart,p).filter(s=>s.path!==fact.path&&s.natal_transform);
    const reasons=[...commonReasons,...attachmentErrors,...(fact.type!=='major'||!theme?['实际化禄星不是已登记主题的主星']:[]),
      ...(!domain?['该宫领域未登记为窄主题用途']:[]),...(others.length?['同宫另有未建模本命多化组合修饰']:[])];
    lu.rows.push({palace:p.name,branch:p.branch,domain,status:eligible(lu,reasons),facts:[fact],other_transforms:others,
      theme:theme?.theme??null,theme_citation:theme?.citation??null,checks:[...new Set(reasons)],
      question:eligible(lu,reasons)==='conditional'?`在${domain}领域，“${theme.theme}”是否出现更多投入或活动？增加是否也包含成本、消耗或分心？`:null});
  }
  if (!nativeLu.length) lu.rows.push({status:'withheld',facts:[],question:null,checks:[...attachmentErrors,'没有实际本命主星化禄标记，不能由禄存或动态字段补入']});
  for (const module of [fubi,jiliang,lu]) module.status=module.rows.some(row=>row.status==='conditional')?'conditional':'withheld';
  panel.status=panel.errors.length?'withheld':Object.values(panel.modules).some(module=>module.status==='conditional')?'conditional':'structure_only';
  return panel;
}

function describeFact(f:any) {return `${f.name}@${normalize(f.palace)}宫${BRANCHES[f.branch]} [${f.path}]（原始亮度${f.brightness_raw??'未提供'}；${f.natal_transform?'本命化'+f.natal_transform:'无本命四化标记'}）`;}
function citationText(c:any) {return `出处：${c.source_label} @ ${c.revision} / ${c.locator}（项目释义；${c.record_id}）`;}
export function renderReviewedStructure(panel:Panel) {
  const lines=['\n## 已审增补（固定本命结构与条件问题）',panel.scope,panel.input_status,'来源状态：'+panel.source_status,
    '时间误差：'+(panel.temporal_uncertainty?'存在，全部观察主题暂缓':'未提供非零误差；仅据给定输入列候选')];
  if (panel.errors.length) lines.push('暂缓原因：'+panel.errors.join('；'));
  if (panel.roster) lines.push('星表检查：十四主星'+(panel.roster.major_stars.complete?'齐备且唯一':'未完整核对')+'；十四辅星'+(panel.roster.adjunct_stars.complete?'齐备且唯一':'未完整核对'),panel.roster.boundary);
  for (const [key,module] of Object.entries(panel.modules)) {
    lines.push(`${module.rule_id}｜${module.status}｜${module.record_id}`,module.summary);
    if (module.citation) lines.push(citationText(module.citation));
    lines.push('登记前提：'+JSON.stringify(module.conditions),'登记排除：'+JSON.stringify(module.exclusions));
    if (key==='adjunct_groups' && panel.roster) {
      for (const [group,names] of Object.entries(ADJUNCT_GROUPS)) {
        const placements=panel.roster.adjunct_stars.rows.filter((r:any)=>names.includes(r.name));
        lines.push(group+'：'+placements.map((r:any)=>r.name+'：'+(r.locations.map(describeFact).join('；')||'位置未核对')).join('；'));
      }
      lines.push('各目标宫的实坐、三合、对宫与前后邻宫分组坐标详见 JSON adjunct_groups；不以原 type 或旧四煞替换十四星分组。');
    }
    for (const row of module.rows) {
      if (key==='adjunct_groups') continue;
      if (key==='empty_borrowing' && !row.is_empty && row.status!=='withheld') continue;
      if (key==='fubi_observation' && !row.structure_matched && !row.facts?.length) continue;
      if (key==='palace_relations' && !DOMAINS[normalize(row.palace)] && !row.flanking_checks.some((c:any)=>c.matched||c.status==='withheld')) continue;
      if (row.palace) lines.push(`${palaceLabel({name:row.palace,branch:row.branch} as Palace)}｜${row.status??module.status}`);
      if (key==='empty_borrowing') {
        lines.push(row.explanation,'本宫实际：'+row.actual_stars.map(describeFact).join('；'));
        if (row.borrowed_reference.length) lines.push('对宫参考（不继承亮度/四化）：'+row.borrowed_reference.map((s:any)=>`${s.name}@${s.source_palace}（${BRANCHES[s.source_branch]}） [${s.path}]`).join('；'));
      } else if (key==='palace_relations') {
        lines.push(row.relations.map((r:any)=>`${RELATION_LABELS[r.relation]} +${r.offset} ${r.palace}（${BRANCHES[r.branch]}）`).join('；'));
        for (const check of row.flanking_checks.filter((c:any)=>c.matched||c.status==='withheld')) lines.push(check.stars.join('/')+'夹宫坐标｜'+check.status+'｜'+String(check.matched)+'：'+check.reason+'；'+check.facts.map((s:any)=>s.name+' ['+s.path+']').join('；'));
      } else if (key==='natal_transforms') {
        lines.push('40格校核：'+String(row.table_check.matched)+'；'+row.table_check.reason,row.excluded_layers);
        for (const c of row.chain) lines.push(`${c.year_stem??'未知年干'} [${c.year_stem_path}] → 化${c.kind} → ${c.expected_star??'未知星'}｜匹配${c.matched}：${c.actual_marked_stars.map(describeFact).join('；')||'无实际标记'}`);
      } else {
        lines.push('实际星源：'+row.facts.map(describeFact).join('；'));
        if (row.actual_major_stars) lines.push('本宫主星：'+row.actual_major_stars.map(describeFact).join('；'));
        if (row.background) lines.push((key==='fubi_observation'?'本宫其他本命四化背景：':'三方四正辅煞/本命四化背景：')+row.background.map(describeFact).join('；'));
        if (row.background_boundary) lines.push(row.background_boundary);
        if (row.other_transforms?.length) lines.push('同宫其他四化：'+row.other_transforms.map(describeFact).join('；'));
        if (row.question) lines.push('条件观察：'+row.question);
        if (row.brightness_boundary) lines.push(row.brightness_boundary);
        if (row.theme_citation) lines.push(citationText(row.theme_citation));
      }
      if (row.checks?.length) lines.push('逐项待核/排除：'+row.checks.join('；'));
    }
    lines.push('反证：'+module.counterevidence.join('；'),'未知/暂缓：'+module.unknown.join('；'));
  }
  return lines.join('\n');
}
