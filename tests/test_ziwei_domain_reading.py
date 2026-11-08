"""Conditional source-bound themes, not accuracy testing."""
import json
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
ZW=ROOT/'scripts/pai_pan_ziwei'
@unittest.skipUnless((ZW/'node_modules/tsx').exists(), 'npm ci required')
class DomainReadingTests(unittest.TestCase):
    def run_node(self, js):
        return json.loads(subprocess.run(['node','--import','tsx','-e',js],cwd=ZW,text=True,capture_output=True,check=True).stdout)
    def test_three_actual_engine_charts_vary_and_share_text_json(self):
        themes=[]
        for date,hour in [('1961-01-21','00:00'),('1990-05-15','12:30'),('1998-06-30','23:00')]:
            args=['node','--import','tsx','pai_pan.ts','--solar',date,'--hour',hour,'--sex','女']
            data=json.loads(subprocess.run(args+['--format','json'],cwd=ZW,text=True,capture_output=True,check=True).stdout)
            text=subprocess.run(args,cwd=ZW,text=True,capture_output=True,check=True).stdout
            reading=data['rule_output']['domain_reading']
            self.assertEqual(reading['status'],'conditional')
            self.assertEqual(len(reading['domains']),4)
            themes.append([d['theme'] for d in reading['domains']])
            for d in reading['domains']:
                self.assertIn(d['interpretation'],text)
                self.assertIn(d['transform_check'],text)
                for c in d['citations']:
                    self.assertEqual(c['attribution_kind'],'project_paraphrase')
                    self.assertIn(c['record_id'],text)
                for f in d['facts']:
                    import re
                    pi,si=map(int,re.findall(r'\[(\d+)\]',f['path']))
                    self.assertEqual(data['chart']['palaces'][pi]['stars'][si]['name'],f['name'])
            for c in reading['clusters']:
                self.assertIn(c['reasoning'],text)
        self.assertEqual(len({str(t) for t in themes}),3)
    def test_missing_brightness_and_empty_palace_do_not_gain_certainty(self):
        result=self.run_node("""
const {generateChart}=require('./vendor/algorithm.ts');
const {buildDomainReading}=require('./domain_reading.ts');
const c=generateChart({year:1961,month:1,day:21,hour:0,gender:'female'},2026);
const before=JSON.stringify(c);const first=buildDomainReading(c);
if(before!==JSON.stringify(c))throw Error('mutation');
c.palaces.forEach(p=>p.stars.forEach(s=>s.brightnessRaw=null));
const missing=buildDomainReading(c);
c.palaces.find(p=>p.branch===c.mingGongBranch).stars=[];
const empty=buildDomainReading(c);
c.palaces=[];const broken=buildDomainReading(c);
console.log(JSON.stringify({first,missing,empty,broken}));
""")
        self.assertTrue(any('缺少原始亮度' in b for d in result['missing']['domains'] for b in d['brightness_checks']))
        self.assertEqual(result['empty']['domains'][0]['status'],'withheld')
        self.assertEqual(result['broken']['status'],'withheld')
        self.assertIn('不完整',result['broken']['conclusion'])

    def test_text_deduplicates_only_shared_caveats_without_mutating_json(self):
        result=self.run_node("""
const {generateChart}=require('./vendor/algorithm.ts');
const {buildDomainReading,renderDomainReading}=require('./domain_reading.ts');
const reading=buildDomainReading(generateChart({year:1990,month:5,day:15,hour:6,gender:'female'},2026));
reading.domains[0].missing_conditions.push('本宫专有待核条件');
const before=JSON.stringify(reading);
const text=renderDomainReading(reading);
console.log(JSON.stringify({reading,text,unchanged:before===JSON.stringify(reading)}));
""")
        self.assertTrue(result['unchanged'])
        text=result['text']
        self.assertEqual(text.count('本宫专有待核条件'),1)
        self.assertIn('尚缺：本宫专有待核条件',text)
        for row in result['reading']['domains']:
            for condition in row['missing_conditions']:
                self.assertEqual(text.count(condition),1)
            self.assertIn(row['interpretation'],text)
        for row in result['reading']['relations']:
            self.assertEqual(text.count(row['reality_check']),1)
            self.assertIn(row['reasoning'],text)
        for row in result['reading']['clusters']:
            self.assertEqual(text.count(row['counterevidence']),1)
            self.assertEqual(text.count(row['missing_conditions']),1)
            self.assertIn(row['reasoning'],text)
    def test_exact_palace_mapping_and_malformed_coordinates(self):
        results=self.run_node("""
const {generateChart}=require('./vendor/algorithm.ts');
const {buildDomainReading}=require('./domain_reading.ts');
const base=generateChart({year:1961,month:1,day:21,hour:0,gender:'female'},2026);
const run=edit=>{const c=JSON.parse(JSON.stringify(base));edit(c);return buildDomainReading(c)};
const find=(c,name)=>c.palaces.find(p=>p.name.replace(/宫$/,'')===name);
const swap=(c,a,b)=>{const x=find(c,a),y=find(c,b);[x.branch,y.branch]=[y.branch,x.branch]};
const invalid=[
 c=>swap(c,'财帛','官禄'), c=>swap(c,'命','迁移'),
 c=>c.mingGongBranch=12, c=>c.mingGongBranch=0.5,
 c=>c.palaces[0].branch=-1, c=>c.palaces[0].branch=12,
 c=>c.palaces[0].branch=0.5,
 c=>c.palaces[0].branch=c.palaces[1].branch,
 c=>c.palaces[0].name=c.palaces[1].name+'宫',
 c=>c.palaces.pop(), c=>c.palaces.push({...c.palaces[0]})
].map(run);
console.log(JSON.stringify({invalid,original:buildDomainReading(base),reordered:run(c=>c.palaces.reverse())}));
""")
        for r in results['invalid']:
            self.assertEqual(r['status'],'withheld')
            self.assertEqual(r['domains'],[])
        self.assertEqual(results['reordered']['status'],'conditional')
        self.assertEqual([d['interpretation'] for d in results['original']['domains']],
                         [d['interpretation'] for d in results['reordered']['domains']])

    def test_malformed_domain_records_withhold(self):
        # Alter the consumer read only; ordinary catalog validation is insufficient
        # for these domain-specific fields. Each process starts with a fresh cache.
        for edit in [
            "delete r.theme; delete r.question; delete r.locator",
            "r.star='天机'", "r.id='duplicate'", "r.source_id='iztro-docs-palace'",
            "r.system='bazi'", "r.content_kind='source_excerpt'",
            "r.question='   '"]:
            with self.subTest(edit=edit):
                result=self.run_node("""
const fs=require('node:fs');const original=fs.readFileSync;
fs.readFileSync=function(path,...args){
 const value=original.call(this,path,...args);
 if(String(path).endsWith('/knowledge/catalog.json')){
  const c=JSON.parse(String(value));
  const r=c.records.find(r=>r.id==='ziwei-domain-star-0');
  EDIT;
  return JSON.stringify(c);
 }
 return value;
};
const {generateChart}=require('./vendor/algorithm.ts');
const {buildDomainReading}=require('./domain_reading.ts');
console.log(JSON.stringify(buildDomainReading(generateChart({year:1961,month:1,day:21,hour:0,gender:'female'},2026))));
""".replace('EDIT',edit))
                self.assertEqual(result['status'],'withheld')
                self.assertEqual(result['domains'],[])
                self.assertNotIn('undefined',json.dumps(result))

    def test_source_gate_failure_degrades_without_inference(self):
        result=self.run_node("""
process.env.PATH='/nonexistent';
const {generateChart}=require('./vendor/algorithm.ts');
const {buildDomainReading}=require('./domain_reading.ts');
console.log(JSON.stringify(buildDomainReading(generateChart({year:1990,month:5,day:15,hour:6,gender:'male'},2026))));
""")
        self.assertEqual(result['status'],'withheld')
        self.assertEqual(result['domains'],[])
