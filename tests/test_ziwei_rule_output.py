"""Output provenance/safety regression tests, NOT predictive accuracy tests."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIWEI = ROOT / 'scripts/pai_pan_ziwei'
FORBIDDEN = ('主血光', '官非', '手术风险', '财源稳定', '富贵双全',
             '一生衣食无忧', '财来财去', '终身缢死', '限至投河',
             '口才生财', '武职大贵', '主大富大贵', '心理障碍', '财劫之兆')


@unittest.skipUnless((ZIWEI / 'node_modules/tsx').exists(), 'npm ci required')
class ZiweiRuleOutputTests(unittest.TestCase):
    def run_cli(self, solar, hour, sex, *options):
        return subprocess.run(['node', '--import', 'tsx', 'pai_pan.ts', '--solar', solar,
                               '--hour', hour, '--sex', sex, '--age-year', '2026', *options],
                              cwd=ZIWEI, text=True, capture_output=True, check=True).stdout

    def assert_descriptive(self, output):
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, output)
        self.assertIn('不证明古籍原文', output)

    def test_adversarial_cases_in_both_modes_and_explanation_settings(self):
        cases = [('1998-06-30', '23:00', '男'), ('1975-12-11', '06:30', '女'),
                 ('1990-05-15', '12:30', '男')]
        for case in cases:
            previous_chart = None
            for options in [[], ['--explain-rules']]:
                with self.subTest(case=case, options=options):
                    text = self.run_cli(*case, *options)
                    raw = self.run_cli(*case, '--format', 'json', *options)
                    self.assert_descriptive(text)
                    self.assert_descriptive(raw)
                    data = json.loads(raw)
                    self.assertEqual(data['schema_version'], 1)
                    if previous_chart is not None:
                        self.assertEqual(data['chart'], previous_chart)
                    previous_chart = data['chart']
                    rules = data['rule_output']
                    self.assertTrue(rules['patterns'])
                    for pattern in rules['patterns']:
                        self.assertIn(pattern['name'], text)
                        self.assertIn(pattern['description'], text)
                        for group in pattern['conditions'].values():
                            for condition in group:
                                self.assertIn(condition, text)
                        self.assertEqual('explanation' in pattern, bool(options))
                    if case[0] == '1998-06-30':
                        names = [p['name'] for p in rules['patterns']]
                        self.assertIn('廉杀羊', names)

    def test_ziwei_without_tianfu_does_not_imply_solitary_major_star(self):
        text = self.run_cli('1961-01-21', '00:00', '女', '--explain-rules')
        data = json.loads(self.run_cli('1961-01-21', '00:00', '女',
                                      '--format', 'json', '--explain-rules'))
        ming = next(p for p in data['chart']['palaces'] if p.get('isMingGong'))
        self.assertEqual({s['name'] for s in ming['stars'] if s['type'] == 'major'},
                         {'紫微', '破军'})
        pattern = next(p for p in data['rule_output']['patterns']
                       if any('无天府同宫' in c for c in p['conditions']['required']))
        self.assertIn('未排除其他主星同宫', pattern['description'])
        self.assertNotIn('紫微独坐命宫', text)
        self.assertIn('破军', pattern['explanation']['boundary_checks'])
        self.assertIn('chart.palaces[', pattern['explanation']['chart_facts'])
        self.assertIn(pattern['explanation']['chart_facts'], text)

    def test_explanations_depend_on_matched_stars_and_actual_chart(self):
        data = json.loads(self.run_cli('1990-05-15', '12:30', '男', '--format',
                                      'json', '--explain-rules'))
        patterns = data['rule_output']['patterns']
        evidence = [p['explanation']['chart_facts'] for p in patterns]
        self.assertGreater(len(set(evidence)), 1)
        partial = next(p for p in patterns if p['name'] == '机月同梁三星会')
        self.assertIn('天机', partial['explanation']['boundary_checks'])
        self.assertIn('不在命宫三方四正内者：天机', partial['explanation']['boundary_checks'])
        # All evidence coordinates must resolve to actual chart stars, not inferred traits.
        import re
        for pattern in patterns:
            for pi, si in re.findall(r'chart\.palaces\[(\d+)\]\.stars\[(\d+)\]',
                                     pattern['explanation']['chart_facts']):
                star = data['chart']['palaces'][int(pi)]['stars'][int(si)]
                self.assertIn(star['name'], pattern['explanation']['chart_facts'])

    def test_sitting_sha_alias_includes_actual_supporting_star(self):
        data = json.loads(self.run_cli('1960-06-15', '04:00', '男', '--format',
                                      'json', '--explain-rules'))
        pattern = next(p for p in data['rule_output']['patterns']
                       if p['name'] == '机月同梁')
        self.assertIn('命宫坐煞', pattern['conditions']['breaking'])
        self.assertIn('火星', pattern['explanation']['chart_facts'])
        self.assertIn('chart.palaces[2].stars[1]', pattern['explanation']['chart_facts'])
        double = json.loads(self.run_cli('1965-03-15', '22:00', '男', '--format',
                                        'json', '--explain-rules'))
        pattern = next(p for p in double['rule_output']['patterns']
                       if '紫府宫见双煞同坐' in p['conditions']['breaking'])
        for name in ('火星', '陀罗'):
            self.assertIn(name, pattern['explanation']['chart_facts'])

    def test_grid_preserves_all_matches_and_conditions_without_vendor_narratives(self):
        js = r'''
const {generateChart} = require('./vendor/algorithm.ts');
const {detectPatterns} = require('./vendor/patterns.ts');
const {buildRuleOutput, describeCondition} = require('./rule_output.ts');
const rows = [];
for (const year of [1975, 1984, 1990, 1998, 2001]) {
 for (const month of [1, 4, 7, 10]) {
  for (let hour = 0; hour < 12; hour++) {
   for (const gender of ['male', 'female']) {
    const chart = generateChart({year, month, day:15, hour, gender}, 2026);
    const before = JSON.stringify(chart);
    const raw = detectPatterns(chart);
    const safe = buildRuleOutput(chart, true);
    if (before !== JSON.stringify(chart)) throw Error('mutated chart');
    if (raw.length !== safe.patterns.length) throw Error('lost match');
    raw.forEach((r, i) => {
      const s = safe.patterns[i];
      if (r.name !== s.name || r.level !== s.level) throw Error('lost labels');
      for (const key of ['required', 'bonus', 'breaking']) {
        if (JSON.stringify((r.conditions?.[key] ?? []).map(describeCondition)) !==
            JSON.stringify(s.conditions[key])) throw Error('lost conditions');
      }
      if (r.description === s.description) throw Error('vendor prose leaked');
    });
    rows.push(safe);
   }
  }
 }
}
console.log(JSON.stringify(rows));
'''
        result = subprocess.run(['node', '--import', 'tsx', '-e', js], cwd=ZIWEI,
                                text=True, capture_output=True, check=True)
        self.assert_descriptive(result.stdout)
        self.assertEqual(len(json.loads(result.stdout)), 480)
        self.assertIn('机月同梁缺', result.stdout)  # Don't erase useful parentheses.

    def test_build_chart_and_old_shichen_cli(self):
        for fmt in ['text', 'json']:
            cmd = [sys.executable, str(ROOT / 'scripts/build_chart.py'), '--solar',
                   '1998-06-30', '--hour', '23:00', '--sex', '男', '--lat', '23.13',
                   '--lon', '113.26', '--analysis-year', '2026', '--format', fmt,
                   '--explain-rules']
            output = subprocess.run(cmd, text=True, capture_output=True, check=True).stdout
            # This guard owns Ziwei prose, not BaZi's explicit negations of predictions.
            ziwei_output = (json.dumps(json.loads(output)['ziwei'], ensure_ascii=False)
                            if fmt == 'json' else output.split('## 紫微斗数', 1)[1].split('## 七政四余', 1)[0])
            self.assert_descriptive(ziwei_output)
            self.assertIn('未运行流年事件触发', output)
            if fmt == 'json':
                snapshot = json.loads(output)
                self.assertIsNone(snapshot['degradation']['ziwei'])
                self.assertIn('rule_output', snapshot['ziwei'])
        old = subprocess.run(['node', '--import', 'tsx', 'pai_pan.ts', '--solar',
                              '1990-05-15', '--shichen', '午', '--sex', '男'], cwd=ZIWEI,
                             text=True, capture_output=True, check=True).stdout
        self.assert_descriptive(old)
        self.assertIn('## 十二宫', old)


if __name__ == '__main__':
    unittest.main()
