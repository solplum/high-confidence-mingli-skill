/** Bounded modern-source interpretation. Never an event/personality classifier. */
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { ZiweiChart, Palace } from './vendor/types';
const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';
let cached: any;
function sources() {
  if (cached) return cached;
  const check = spawnSync('python3', [ROOT + 'scripts/knowledge_catalog.py', 'validate'], {encoding:'utf8', timeout:15000});
  if (check.status !== 0) throw Error('来源登记未通过或 Python 检查不可用');
  const catalog = JSON.parse(readFileSync(ROOT + 'knowledge/catalog.json','utf8'));
  const records = catalog.records.filter((r:any) => r.profile === 'ziwei-domain-conditional' && r.status === 'usable');
  const stars = ['紫微','天机','太阳','武曲','天同','廉贞','天府','太阴','贪狼','巨门','天相','天梁','七杀','破军'];
  const expected = [...stars.map((star,i)=>({id:'ziwei-domain-star-'+i, star, source:'iztro-docs-major-star'})),
    {id:'ziwei-domain-domains',star:null,source:'iztro-docs-palace'},
    {id:'ziwei-domain-brightness',star:null,source:'iztro-docs-star'}];
  const text = (value:unknown)=>typeof value === 'string' && value.trim().length > 0;
  if (records.length !== expected.length || expected.some(e=> {
    const matches=records.filter((r:any)=>r.id===e.id);
    if (matches.length !== 1) return true;
    const r=matches[0];
    return r.system !== 'ziwei' || r.source_id !== e.source ||
      r.content_kind !== 'project_paraphrase' || !text(r.locator) ||
      (e.star ? r.star !== e.star || !text(r.theme) || !text(r.question) : r.star != null);
  })) throw Error('有限释义记录字段不完整或不符合登记口径');
  return cached = {records, catalog};
}
export function buildDomainReading(chart: ZiweiChart) {
  const base = {version:'ziwei-domain-v1', status:'conditional', scope:'以下是现代紫微资料支持的传统主题推演，不是已经证实的个人特征；现实经历可以直接否定它。只用固定本命星位，不混入宫干自化、大限或流年。'};
  try {
    const {records, catalog} = sources();
    const citation = (r:any) => {
      const s = catalog.sources.find((s:any)=>s.id===r.source_id);
      return {record_id:r.id, source_label:s.citation_label, revision:s.revision, locator:s.path+' / '+r.locator,
        attribution_kind:'project_paraphrase', url:s.upstream_url, license_path:s.license_path};
    };
    const keys = ['命宫','财帛','官禄','迁移'];
    const offsets = [0,8,4,6];
    const normalize = (name:string)=>name.replace(/宫$/, '');
    const validBranch = (branch:number)=>Number.isInteger(branch) && branch >= 0 && branch < 12;
    if (!validBranch(chart.mingGongBranch) || chart.palaces.length !== 12 ||
        chart.palaces.some(p=>!validBranch(p.branch)) ||
        new Set(chart.palaces.map(p=>p.branch)).size !== 12 ||
        new Set(chart.palaces.map(p=>normalize(p.name))).size !== 12) {
      throw Error('十二宫不完整、名称重复或地支无效');
    }
    const palaces = keys.map(name=>chart.palaces.find(p=>normalize(p.name)===normalize(name)));
    if (palaces.some((p,i)=>!p || p.branch !== (chart.mingGongBranch+offsets[i])%12)) {
      throw Error('命财官迁宫位不完整或关系不符');
    }
    const label = (p:Palace)=>p.name.replace(/宫$/,'')+'宫（'+BRANCHES[p.branch]+'）';
    const rows = palaces.map((p0, i)=> {
      const p = p0!;
      const majors = p.stars.filter(s=>s.type==='major');
      const terms = majors.map(s=>records.find((r:any)=>r.star===s.name));
      const unknown = majors.filter((s,j)=>!terms[j]).map(s=>s.name);
      const facts = p.stars.map(s=>({name:s.name,brightness:s.brightnessRaw??null,natal_transform:s.siHua??null,
        path:`chart.palaces[${chart.palaces.indexOf(p)}].stars[${p.stars.indexOf(s)}]`}));
      const theme = terms.filter(Boolean).map((r:any)=>r.theme).join('；');
      const meanings = ['自身如何选择和定方向','怎样分配与使用资源','怎样把事情做成','怎样面对外部环境与合作对象'];
      const brightness = majors.map(s=> {
        const b=s.brightnessRaw;
        const posture=['庙','旺'].includes(b??'')?'按这份现代说明可优先讨论主动、直接表达主题': ['不','陷'].includes(b??'')?'按这份现代说明应同时考虑保留表达或考虑更多，不能沿用主动表达的解释':b?'属于中间等级，本版不进一步强分表达强弱':'缺少原始亮度，表达强弱暂不判断';
        return `${s.name}亮度${b||'未提供'}：${posture}。`;
      });
      const questions = terms.filter(Boolean).map((r:any)=>r.question+'？');
      const transforms = p.stars.filter(s=>s.siHua).map(s=>s.name+'化'+s.siHua);
      return {domain:keys[i],palace:label(p),status:majors.length&&!unknown.length?'conditional':'withheld',facts,
        interpretation:majors.length?`这里讨论的是${meanings[i]}。${majors.map(s=>s.name).join('、')}落在本宫，因此可把“${theme||'未登记主题'}”作为这一领域的观察假设。${majors.length>1?'同宫两颗主星的主题须并列，不能只取喜欢的一面，也没有把两者量化相加。':''}`:`本宫没有主星，不能解释成这一领域没有能力或机会。对宫借星仅为另一处的参考，不当成本宫实坐；本版暂缓星性判断。`,
        brightness_checks:brightness,
        transform_check:transforms.length?`本宫本命四化为${transforms.join('、')}，仅保留事实；尚无本版已核读的四化组合规则，不能据此把主题升级为结果。`:'本宫无本命四化标记，不等于此领域没有助力或阻力。',
        counterchecks:questions.length?questions:['需先核对对宫实坐主星及借星适用条件。'],
        missing_conditions:[...unknown.map(s=>'未登记星性：'+s),'缺少本人实际选择、资源条件和他人反馈，不能确认主题适用于本人。','辅煞与完整组合权重尚未建模，不以没有触发旧格局限制充当排除反证。'],
        citations:terms.filter(Boolean).map(citation), theme};
    });
    const links = [[0,1,'方向与资源'],[1,2,'资源与落实'],[0,3,'自身与对外']].map(([a,b,title])=> {
      const left=rows[a as number],right=rows[b as number];
      return {title, status:left.status==='withheld'||right.status==='withheld'?'withheld':'conditional',
        reasoning:left.theme&&right.theme?`${left.palace}讨论“${left.theme}”，${right.palace}讨论“${right.theme}”。二者分别落在${left.domain}与${right.domain}，不是同一件事的重复证明。要检验的是：前者的做法能否给后者提供条件，还是在时间、资源或沟通上互相牵制；不能从任一宫直接推出另一领域的成绩。`:`${left.palace}与${right.palace}需连读，但至少一宫缺少可用主星主题，本版不借另一宫补成肯定判断。`,
        reality_check:`请分别找一个支持和一个不支持上述两宫主题的实际例子；若差别只来自岗位要求、预算或熟悉程度，应优先采用这些现实解释。`};
    });
    // Our synthesis of individually reviewed themes, NOT a claimed classical pattern.
    const clusters = [
      {name:'统筹、执行与要求', stars:['紫微','武曲','廉贞'], question:'统筹的目标是否给执行留足资源，而认真的标准是在帮助验收，还是让执行反复返工'},
      {name:'探索、坚持与重建', stars:['贪狼','七杀','破军'], question:'探索得到的新方向是否经过比较就进入持续推进；需要改掉旧办法时，能否保留退路而不是把坚持变成继续投入'}
    ].map(rule=> {
      const placements=rule.stars.map(name=> {
        const row=rows.find(r=>r.facts.some(f=>f.name===name));
        return {star:name, palace:row?.palace??null, domain:row?.domain??null,
          fact:row?.facts.find(f=>f.name===name)?.path??null};
      });
      const absent=placements.filter(p=>!p.fact).map(p=>p.star);
      return {name:rule.name,status:absent.length?'withheld':'conditional', placements,
        reasoning:absent.length?`四宫中未齐备：${absent.join('、')}。不能因部分星曜出现就套用整组主题。`:
          `${placements.map(p=>p.star+'在'+p.palace).join('，')}。把三处主题连起来，需要核对：${rule.question}？这是把已登记的单星讨论主题按实际宫位连接的项目推演，不是新认定的传统格局，也不证明本人具有这些特点。`,
        counterevidence:'宫位只提供讨论位置，不能证明现实因果；若实际决定主要受外部制度或资源限制，或实际做法与主题相反，就应撤回这组解释。',
        missing_conditions:'未建模辅煞、夹宫与完整同宫组合，不能断成格，也不能据此预测成败。',
        citations:rule.stars.map(name=>citation(records.find((r:any)=>r.star===name)))};
    });
    return {...base, domains:rows, relations:links, clusters, citations:records.filter((r:any)=>!r.star).map(citation),
      conclusion:'本次能交付的是四个领域各自的观察角度及相互限制，不是完整人生详批。没有计算事件发生时间、收益、事故概率，也没有由盘面反推过去经历。'};
  } catch (e) { return {...base,status:'withheld',domains:[],relations:[],clusters:[],citations:[],conclusion:'来源或盘面检查不足，暂缓四宫解释：'+(e instanceof Error?e.message:'未知错误')}; }
}
export function renderDomainReading(reading:ReturnType<typeof buildDomainReading>) {
  const lines=['\n## 四宫联读（有条件的传统主题）',reading.scope];
  const commonMissing = reading.domains.length > 1 ? reading.domains[0].missing_conditions.filter(
    text=>reading.domains.every(row=>row.missing_conditions.includes(text))) : [];
  for (const row of reading.domains) {
    lines.push(row.palace+'｜'+row.status,row.interpretation,...row.brightness_checks,row.transform_check,
      '反证核对：'+row.counterchecks.join('；'));
    const specificMissing = row.missing_conditions.filter(text=>!commonMissing.includes(text));
    if (specificMissing.length) lines.push('尚缺：'+specificMissing.join('；'));
    for (const c of row.citations) lines.push(`出处：${c.source_label} @ ${c.revision} / ${c.locator}（项目释义；${c.record_id}）`);
  }
  if (commonMissing.length) lines.push('四宫共同尚缺：'+commonMissing.join('；'));
  for (const r of reading.relations) lines.push(r.title+'：'+r.reasoning);
  for (const check of new Set(reading.relations.map(r=>r.reality_check))) lines.push('联读现实核对：'+check);
  for (const c of reading.clusters) lines.push(c.name+'｜'+c.status+'：'+c.reasoning);
  for (const caveat of new Set(reading.clusters.flatMap(c=>[c.counterevidence,c.missing_conditions]))) lines.push('主题组边界：'+caveat);
  for (const c of reading.citations) lines.push(`出处：${c.source_label} @ ${c.revision} / ${c.locator}（项目释义；${c.record_id}）`);
  lines.push(reading.conclusion);
  return lines.join('\n');
}
