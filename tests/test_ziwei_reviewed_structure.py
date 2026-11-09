"""Approved source-bound structures and questions, not prediction/accuracy tests.

Every edited chart below is an explicitly synthetic test variant, never a claimed
real birth chart. No benchmark answers or holdout data are used.
"""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZW = ROOT / 'scripts/pai_pan_ziwei'
JS = r"""
const {generateChart}=require('./vendor/algorithm.ts');
const {SI_HUA_TABLE}=require('./vendor/constants.ts');
const {buildReviewedStructure,renderReviewedStructure,checkFlankingPair,ADJUNCT_GROUPS}=require('./reviewed_structure.ts');
const clone=c=>JSON.parse(JSON.stringify(c));
const base=()=>generateChart({year:1990,month:5,day:15,hour:6,gender:'male'},2026);
const palace=(c,name)=>c.palaces.find(p=>p.name.replace(/宫$/,'')===name);
// Synthetic variants preserve the actual arrays' star identities while relocating stars.
const move=(c,name,branch)=>{
 const old=c.palaces.find(p=>p.stars.some(s=>s.name===name));
 const i=old.stars.findIndex(s=>s.name===name),s=old.stars.splice(i,1)[0];
 c.palaces.find(p=>p.branch===branch).stars.push(s);
};
const repairBorrow=c=>{for(const p of c.palaces){
 p.oppositeBranch=(p.branch+6)%12;p.isEmpty=!p.stars.some(s=>s.type==='major');
 delete p.borrowedFromBranch;delete p.borrowedFromName;delete p.borrowedStars;
 if(p.isEmpty){const q=c.palaces.find(q=>q.branch===p.oppositeBranch);
 p.borrowedFromBranch=q.branch;p.borrowedFromName=q.name;p.borrowedStars=q.stars.filter(s=>s.type==='major').map(s=>s.name)}
}};
const assignStem=(c,stem)=>{c.lunarInfo.yearStem=stem;
 c.palaces.forEach(p=>p.stars.forEach(s=>delete s.siHua));
 ['禄','权','科','忌'].forEach((kind,i)=>c.palaces.flatMap(p=>p.stars).find(s=>s.name===SI_HUA_TABLE[stem][i]).siHua=kind);
};
const clearTransformsFrom=(c,branches,except)=>{
 const outside=c.palaces.find(p=>!branches.includes(p.branch)).branch;
 for(const name of c.palaces.filter(p=>branches.includes(p.branch)).flatMap(p=>p.stars).filter(s=>s.siHua&&s.name!==except).map(s=>s.name))move(c,name,outside);
 repairBorrow(c);
};
"""


@unittest.skipUnless((ZW/'node_modules/tsx').exists(), 'npm ci required')
class ReviewedStructureTests(unittest.TestCase):
    def node(self, script):
        return json.loads(subprocess.run(['node','--import','tsx','-e',JS+script],cwd=ZW,
                                         text=True,capture_output=True,check=True).stdout)

    def assert_fact_path(self, chart, fact):
        match = re.fullmatch(r'chart\.palaces\[(\d+)\]\.stars\[(\d+)\]', fact['path'])
        self.assertIsNotNone(match, fact)
        pi, si = map(int, match.groups())
        self.assertEqual(chart['palaces'][pi]['stars'][si]['name'], fact['name'])

    def test_real_engine_paths_no_mutation_and_default_json_text(self):
        for date, hour in [('1990-05-15','12:30'),('1960-02-15','20:00')]:
            args=['node','--import','tsx','pai_pan.ts','--solar',date,'--hour',hour,'--sex','男','--age-year','2026']
            data=json.loads(subprocess.run(args+['--format','json'],cwd=ZW,text=True,capture_output=True,check=True).stdout)
            text=subprocess.run(args,cwd=ZW,text=True,capture_output=True,check=True).stdout
            panel=data['rule_output']['reviewed_structure']
            self.assertNotEqual(panel['status'],'withheld',panel['errors'])
            self.assertEqual(len(panel['modules']),7)
            self.assertIn('未核实出生记录真实性',panel['input_status'])
            for module in panel['modules'].values():
                self.assertIn(module['record_id'],text)
                self.assertIn(module['summary'],text)
                self.assertIn(module['citation']['source_label'],text)
                self.assertEqual(module['citation']['attribution_kind'],'project_paraphrase')
                for row in module['rows']:
                    if row.get('question'):
                        self.assertIn(row['question'],text)
            for row in panel['modules']['palace_relations']['rows']:
                for relation in row['relations']:
                    for fact in relation['stars']:
                        self.assert_fact_path(data['chart'],fact)
            for row in panel['modules']['empty_borrowing']['rows']:
                for fact in row['borrowed_reference']:
                    self.assert_fact_path(data['chart'],fact)
                    self.assertNotIn('brightness_raw',fact)
                    self.assertNotIn('natal_transform',fact)
                    self.assertNotEqual(fact['source_branch'],row['branch'])
                self.assertEqual(row['interpretation_status'],'withheld')
        result=self.node("""
const {buildRuleOutput,RULE_SCOPE}=require('./rule_output.ts');
const {detectPatterns}=require('./vendor/patterns.ts');
const c=base(),before=JSON.stringify(c),table=JSON.stringify(SI_HUA_TABLE),patterns=JSON.stringify(detectPatterns(c));
const output=buildRuleOutput(c,true);renderReviewedStructure(output.reviewed_structure);
console.log(JSON.stringify({unchanged:before===JSON.stringify(c),tableUnchanged:table===JSON.stringify(SI_HUA_TABLE),patternsUnchanged:patterns===JSON.stringify(detectPatterns(c)),terminology:output.terminology,groups:ADJUNCT_GROUPS}));
""")
        self.assertTrue(result['unchanged'])
        self.assertTrue(result['tableUnchanged'])
        self.assertTrue(result['patternsUnchanged'])
        self.assertIn('四煞指擎羊、陀罗、火星、铃星',result['terminology'])
        self.assertEqual(result['groups']['six_sha'],['地空','地劫','火星','铃星','陀罗','擎羊'])
        self.assertEqual(sum(map(len,result['groups'].values())),14)
        self.assertNotIn('天空',sum(result['groups'].values(),[]))

    def test_empty_palace_provenance_mismatch_and_residuals(self):
        result=self.node("""
const c=base(),p=c.palaces.find(p=>p.isEmpty),branch=p.branch;
const run=edit=>{const x=clone(c);edit(x,x.palaces.find(p=>p.branch===branch));return buildReviewedStructure(x).modules.empty_borrowing.rows.find(r=>r.branch===branch)};
const valid=run(()=>{}),wrong=run((x,p)=>p.borrowedStars=['不存在星']),
 duplicate=run((x,p)=>p.borrowedStars.push(p.borrowedStars[0]));
const residual=run((x,p)=>p.stars.push({name:'虚构测试主星',type:'major',brightnessRaw:'庙'}));
console.log(JSON.stringify({valid,wrong,duplicate,residual}));
""")
        self.assertEqual(result['valid']['status'],'structure_only')
        for key in ('wrong','duplicate','residual'):
            self.assertEqual(result[key]['status'],'withheld')
            self.assertTrue(result[key]['checks'])
        self.assertEqual(result['residual']['borrowed_reference'],[])

    def test_all_twelve_targets_rotation_wraparound_and_flanking_sides(self):
        result=self.node("""
const c=base();move(c,'左辅',11);move(c,'右弼',1);repairBorrow(c);
const yes=checkFlankingPair(c,0,['左辅','右弼']);
const reverse=clone(c);reverse.palaces.reverse();
const reordered=checkFlankingPair(reverse,0,['左辅','右弼']);
const panel=buildReviewedStructure(c);
move(c,'右弼',11);repairBorrow(c);const sameSide=checkFlankingPair(c,0,['左辅','右弼']);
const sameName=checkFlankingPair(c,0,['左辅','左辅']);
c.palaces.find(p=>p.branch===1).stars.push({...c.palaces.find(p=>p.branch===11).stars.find(s=>s.name==='左辅')});
const duplicate=checkFlankingPair(c,0,['左辅','右弼']);
const rotations=[];for(let offset=0;offset<12;offset++){
 const x=base();x.mingGongBranch=(x.mingGongBranch+offset)%12;
 x.palaces.forEach(p=>p.branch=(p.branch+offset)%12);repairBorrow(x);
 rotations.push(buildReviewedStructure(x));
}
console.log(JSON.stringify({yes,reordered,sameSide,sameName,duplicate,panel,rotations}));
""")
        self.assertTrue(result['yes']['matched'])
        self.assertTrue(result['reordered']['matched'])
        self.assertFalse(result['sameSide']['matched'])
        self.assertEqual(result['sameName']['status'],'withheld')
        self.assertEqual(result['duplicate']['status'],'withheld')
        for panel in result['rotations']:
            self.assertNotEqual(panel['status'],'withheld')
            self.assertEqual(len(panel['modules']['palace_relations']['rows']),12)
            for target in panel['modules']['palace_relations']['rows']:
                self.assertEqual([r['branch'] for r in target['relations']],
                                 [(target['branch']+offset)%12 for offset in [0,4,8,6,1,11]])

    def test_fubi_question_requires_actual_same_palace_registered_domain_and_no_modifier(self):
        result=self.node("""
const c=base(),p=palace(c,'官禄');move(c,'左辅',p.branch);move(c,'右弼',p.branch);clearTransformsFrom(c,[p.branch]);repairBorrow(c);
const row=x=>buildReviewedStructure(x).modules.fubi_observation.rows.find(r=>r.branch===p.branch);
const positive=row(c),split=clone(c);move(split,'右弼',(p.branch+4)%12);repairBorrow(split);
const modified=clone(c);palace(modified,'官禄').stars.find(s=>s.name==='右弼').siHua='科';
const omitted=clone(c);assignStem(omitted,8);delete palace(omitted,'官禄').stars.find(s=>s.name==='左辅').siHua;
const majorModifier=clone(c),extra=majorModifier.palaces.flatMap(p=>p.stars).find(s=>s.siHua);move(majorModifier,extra.name,p.branch);repairBorrow(majorModifier);
const missing=clone(c);missing.palaces.find(p=>p.stars.some(s=>s.name==='地劫')).stars=missing.palaces.find(p=>p.stars.some(s=>s.name==='地劫')).stars.filter(s=>s.name!=='地劫');
const outside=clone(c);const q=palace(outside,'福德');move(outside,'左辅',q.branch);move(outside,'右弼',q.branch);repairBorrow(outside);
console.log(JSON.stringify({positive,split:row(split),modified:row(modified),omitted:row(omitted),majorModifier:row(majorModifier),missing:row(missing),outside:buildReviewedStructure(outside).modules.fubi_observation.rows.find(r=>r.branch===q.branch)}));
""")
        self.assertEqual(result['positive']['status'],'conditional')
        self.assertTrue(result['positive']['question'])
        self.assertTrue(all(f['brightness_raw'] is None for f in result['positive']['facts']))
        self.assertEqual(result['majorModifier']['status'],'conditional')
        self.assertTrue(result['majorModifier']['background'])
        for key in ('split','modified','omitted','missing','outside'):
            self.assertEqual(result[key]['status'],'withheld',key)
            self.assertIsNone(result[key]['question'])
        self.assertFalse(result['split']['structure_matched'])
        self.assertTrue(result['modified']['structure_matched'])

    def test_jiliang_requires_sitting_ming_brightness_and_complete_background(self):
        result=self.node("""
const actual=generateChart({year:1960,month:2,day:15,hour:10,gender:'male'},2026);
const c=clone(actual),sf=[0,4,8,6].map(o=>(c.mingGongBranch+o)%12);clearTransformsFrom(c,sf);
const row=x=>buildReviewedStructure(x).modules.jiliang_observation.rows[0];
const noBrightness=clone(c);palace(noBrightness,'命').stars.find(s=>s.name==='天机').brightnessRaw=null;
const borrowed=clone(c);move(borrowed,'天机',(c.mingGongBranch+6)%12);move(borrowed,'天梁',(c.mingGongBranch+6)%12);repairBorrow(borrowed);
const transformed=clone(c);palace(transformed,'命').stars.find(s=>s.name==='天机').siHua='忌';
const omitted=clone(c);assignStem(omitted,1);for(const name of ['天机','天梁'])delete palace(omitted,'命').stars.find(s=>s.name===name).siHua;
console.log(JSON.stringify({actual:row(actual),positive:row(c),noBrightness:row(noBrightness),borrowed:row(borrowed),transformed:row(transformed),omitted:row(omitted)}));
""")
        self.assertTrue(result['actual']['structure_matched'])
        self.assertEqual(result['actual']['status'],'conditional')
        self.assertTrue(any(f['natal_transform'] for f in result['actual']['background']))
        self.assertEqual(result['positive']['status'],'conditional')
        self.assertIn('何时过度',result['positive']['question'])
        for key in ('noBrightness','borrowed','transformed','omitted'):
            self.assertEqual(result[key]['status'],'withheld',key)
            self.assertIsNone(result[key]['question'])
        self.assertFalse(result['borrowed']['structure_matched'])

    def test_fixed_table_all_stems_chain_and_lu_narrow_question(self):
        result=self.node("""
const all=[];for(let stem=0;stem<10;stem++){const c=base();assignStem(c,stem);all.push(buildReviewedStructure(c).modules.natal_transforms)}
const c=base();assignStem(c,9);const p=palace(c,'官禄');move(c,'破军',p.branch);clearTransformsFrom(c,[p.branch],'破军');repairBorrow(c);
const get=x=>buildReviewedStructure(x);
const positive=get(c),dynamic=clone(c);dynamic.palaces.forEach(p=>{p.selfSihua=[{starName:'破军',siHua:'忌'}];p.overlay={liuNian:{破军:'忌'}}});dynamic.overlay={破军:{liuNian:'忌'}};
const multi=clone(c);const extra=multi.palaces.flatMap(p=>p.stars).find(s=>s.siHua==='权');move(multi,extra.name,p.branch);repairBorrow(multi);
const mismatch=clone(c);mismatch.palaces.flatMap(p=>p.stars).find(s=>s.name==='破军').siHua='权';
const onlyLucun=clone(c);onlyLucun.palaces.forEach(p=>p.stars.forEach(s=>delete s.siHua));onlyLucun.overlay={破军:{liuNian:'禄'}};
const invalidStem=clone(c);invalidStem.lunarInfo.yearStem=10;
console.log(JSON.stringify({all,positive,dynamic:get(dynamic),multi:get(multi),mismatch:get(mismatch),onlyLucun:get(onlyLucun),onlyLucunText:renderReviewedStructure(get(onlyLucun)),invalidStem:get(invalidStem)}));
""")
        for module in result['all']:
            self.assertEqual(module['status'],'structure_only')
            self.assertTrue(module['rows'][0]['table_check']['matched'])
            self.assertEqual(module['rows'][0]['table_check']['cells_checked'],40)
            for chain in module['rows'][0]['chain']:
                self.assertTrue(chain['matched'])
                self.assertEqual(chain['year_stem_path'],'chart.lunarInfo.yearStem')
                self.assertEqual(len(chain['actual_marked_stars']),1)
        lu=lambda panel: panel['modules']['natal_lu_observation']
        self.assertEqual(lu(result['positive'])['status'],'conditional')
        self.assertIn('成本、消耗或分心',lu(result['positive'])['rows'][0]['question'])
        self.assertEqual(result['positive'],result['dynamic'])
        self.assertIn('没有实际本命主星化禄标记，不能由禄存或动态字段补入',result['onlyLucunText'])
        for key in ('multi','mismatch','onlyLucun','invalidStem'):
            self.assertEqual(lu(result[key])['status'],'withheld',key)
            self.assertTrue(all(row['question'] is None for row in lu(result[key])['rows']))

    def test_table_mismatch_missing_coordinates_and_temporal_uncertainty(self):
        result=self.node("""
const fs=require('node:fs'),read=fs.readFileSync;
fs.readFileSync=function(path,...args){const value=read.call(this,path,...args);return String(path).endsWith('/learn/mutagen.md')?String(value).replace('|甲|廉贞|破军|武曲|太阳|','|甲|紫微|破军|武曲|太阳|'):value};
const tableMismatch=buildReviewedStructure(base());fs.readFileSync=read;
const c=base();const invalid=[];
for(const edit of [x=>x.palaces.pop(),x=>x.palaces[0].branch=x.palaces[1].branch,x=>x.palaces[0].branch=12,x=>x.palaces[0].stars=null,x=>x.palaces[0].name=x.palaces[1].name,...[false,0,'未知',{}].map(value=>x=>x.palaces[0].stars[0].siHua=value)]){const x=clone(c);edit(x);invalid.push(buildReviewedStructure(x))}
const uncertain=buildReviewedStructure(c,{temporalUncertainty:true});
console.log(JSON.stringify({tableMismatch,invalid,uncertain}));
""")
        self.assertEqual(result['tableMismatch']['modules']['natal_transforms']['status'],'withheld')
        self.assertFalse(result['tableMismatch']['modules']['natal_transforms']['rows'][0]['table_check']['matched'])
        for panel in result['invalid']:
            self.assertEqual(panel['status'],'withheld')
            self.assertTrue(all(module['status']=='withheld' for module in panel['modules'].values()))
        for key in ('fubi_observation','jiliang_observation','natal_lu_observation'):
            module=result['uncertain']['modules'][key]
            self.assertEqual(module['status'],'withheld')
            self.assertTrue(all(row['question'] is None for row in module['rows']))

    def test_sources_fail_closed_and_reload_in_same_process(self):
        result=self.node("""
const cp=require('node:child_process'),spawn=cp.spawnSync;
let broken=false;
cp.spawnSync=function(command,args,...rest){const result=spawn.call(this,command,args,...rest);
 if(broken&&args[0].endsWith('/reviewed_knowledge.py')&&result.status===0){const data=JSON.parse(result.stdout);data.records.pop();return {...result,stdout:JSON.stringify(data)}}return result;
};
const first=buildReviewedStructure(base());broken=true;const second=buildReviewedStructure(base());
process.env.PATH='/nonexistent';const absent=buildReviewedStructure(base());
console.log(JSON.stringify({first,second,absent}));
""")
        self.assertNotEqual(result['first']['status'],'withheld')
        for key in ('second','absent'):
            panel=result[key]
            self.assertEqual(panel['status'],'withheld')
            self.assertIn('source_gate_failed',panel['source_status'])
            self.assertTrue(all(module['citation'] is None for module in panel['modules'].values()))
            self.assertTrue(all(module['status']=='withheld' for module in panel['modules'].values()))

    def test_cli_temporal_flag_only_gates_new_theme_candidates(self):
        args=['node','--import','tsx','pai_pan.ts','--solar','1960-02-15','--hour','20:00','--sex','男','--age-year','2026']
        run=lambda options: subprocess.run(args+options,cwd=ZW,text=True,capture_output=True,check=True).stdout
        fixed=json.loads(run(['--format','json']))
        uncertain=json.loads(run(['--temporal-uncertainty','--format','json']))
        text=run(['--temporal-uncertainty'])
        self.assertFalse(fixed['input']['temporalUncertainty'])
        self.assertTrue(uncertain['input']['temporalUncertainty'])
        self.assertEqual(fixed['chart'],uncertain['chart'])
        self.assertEqual(fixed['rule_output']['domain_reading'],uncertain['rule_output']['domain_reading'])
        self.assertEqual(fixed['rule_output']['patterns'],uncertain['rule_output']['patterns'])
        self.assertEqual(fixed['rule_output']['reviewed_structure']['modules']['jiliang_observation']['status'],'conditional')
        for key in ('fubi_observation','jiliang_observation','natal_lu_observation'):
            module=uncertain['rule_output']['reviewed_structure']['modules'][key]
            self.assertEqual(module['status'],'withheld')
            self.assertTrue(all(row['question'] is None for row in module['rows']))
        self.assertIn('出生时间存在非零误差，主题候选暂缓',text)


if __name__=='__main__':
    unittest.main()
