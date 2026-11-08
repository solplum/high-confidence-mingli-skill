"""Symbolic adversarial inputs and synthetic engine dates, no personal data."""
import json
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from test_bazi_core_reading import fixture, chart
import bazi_core_reading as core
import bazi_strength_reasoning as strength


def read(stems, branches, missing=False):
    f = fixture(stems, branches)
    if missing:
        f['pillars']['hour'] = ('未知',) * 4
    return core.analyze(f)['strength_reasoning']


class StrengthTests(unittest.TestCase):
    def test_narrow_strong_and_hidden_counter_preserved(self):
        a = read('甲甲甲甲', '寅寅寅寅')
        self.assertEqual(a['decision'], 'strong_tendency')
        self.assertTrue(a['counterevidence_fact_ids'])
        self.assertTrue(a['conditions']['rooted_external_support'])
        self.assertEqual(a['status'], 'conditional')

    def test_narrow_weak_not_follow_pattern(self):
        a = read('庚辛甲庚', '酉酉午酉')
        self.assertEqual(a['decision'], 'weak_tendency')
        self.assertIn('无根不等于从格', a['text'])

    def test_season_alone_never_decides(self):
        self.assertNotEqual(read('庚辛甲庚', '酉寅午酉')['decision'], 'strong_tendency')
        self.assertNotEqual(read('甲甲甲甲', '寅酉寅寅')['decision'], 'weak_tendency')

    def test_same_visible_stems_different_roots(self):
        a = read('甲甲甲甲', '寅寅寅寅')
        b = read('甲甲甲甲', '午午午午')
        self.assertTrue(a['root_fact_ids'])
        self.assertFalse(b['root_fact_ids'])
        self.assertNotEqual(a['decision'], b['decision'])
        self.assertTrue(all(not p['root_ids'] for p in b['support_paths']))

    def test_hidden_resource_defeats_narrow_weak(self):
        a = read('庚辛甲庚', '酉酉亥酉')
        self.assertFalse(a['conditions']['no_hidden_resource'])
        self.assertNotEqual(a['decision'], 'weak_tendency')

    def test_visible_opposition_defeats_narrow_strong(self):
        a = read('甲甲甲丙', '寅寅寅寅')
        self.assertEqual(a['decision'], 'competing_evidence')
        self.assertFalse(a['conditions']['no_visible_opposition'])

    def test_clash_never_deletes_root(self):
        a = read('甲甲甲甲', '申寅寅寅')
        self.assertEqual(a['decision'], 'conditions_unresolved')
        self.assertTrue(a['root_fact_ids'])
        self.assertTrue(any(r['kind'] == '六冲' for r in a['contested_effects']))
        self.assertIn('未删除藏干', a['text'])

    def test_combination_does_not_transform_or_cancel(self):
        a = read('甲甲甲己', '寅寅寅亥')
        self.assertEqual(a['decision'], 'conditions_unresolved')
        self.assertTrue(a['root_fact_ids'])
        self.assertTrue({'六合配对', '天干五合配对'} <= {r['kind'] for r in a['contested_effects']})

    def test_disputed_yin_birth_cases_are_not_engine_roots(self):
        for stems, branches in [('甲甲乙甲', '午午午午'), ('丙丙丁丙', '酉酉酉酉')]:
            a = read(stems, branches)
            self.assertTrue(a['source_model_conflicts'])
            self.assertFalse(a['root_fact_ids'])
            self.assertEqual(a['decision'], 'conditions_unresolved')
            self.assertIn('阴长生', a['text'])

    def test_unassessed_punishment_and_harm_are_explicit(self):
        for branches, kind in [('寅寅寅巳','相害'), ('卯卯卯子','子卯刑')]:
            a = read('甲甲甲甲', branches)
            self.assertTrue(any(u['kind'] == kind for u in a['unassessed_interactions']))
            self.assertIn('未评估其效力', a['text'])
            self.assertTrue(any(kind in u for u in a['unresolved_effects']))

    def test_missing_hour_and_temporal_uncertainty_withhold(self):
        self.assertEqual(read('甲甲甲甲', '寅寅寅寅', True)['status'], 'withheld')
        f = fixture('甲甲甲甲', '寅寅寅寅')
        f['temporal_uncertainty'] = True
        a = core.analyze(f)['strength_reasoning']
        self.assertEqual(a['status'], 'withheld')
        self.assertIn('出生时间未决', a['text'])

    def test_earth_and_transition_months_outside_narrow_profile(self):
        for stems, branches in [('戊戊戊戊', '午午午午'), ('甲甲甲甲', '寅辰寅寅')]:
            self.assertEqual(read(stems, branches)['decision'], 'conditions_unresolved')

    def test_disjoint_references_source_and_no_score(self):
        a = read('甲甲甲丙', '寅寅寅寅')
        known = {f['id'] for f in a['facts']}
        self.assertFalse(set(a['supporting_fact_ids']) & set(a['counterevidence_fact_ids']))
        for r in a['rules']:
            self.assertFalse(set(r['facts']) & set(r['counterevidence']))
            self.assertTrue(set(r['facts'] + r['counterevidence']) <= known)
            self.assertTrue(r['source_pages'])
            self.assertTrue(r['missing_conditions'])
        self.assertFalse(a['prediction_guarantee'])
        self.assertEqual(a['predictive_validity'], 'unvalidated')
        self.assertNotIn('score', json.dumps(a))

    def test_source_integrity_fails_closed(self):
        # Called directly so a pattern-source guard cannot hide failure here.
        full = core.analyze(fixture('甲甲甲甲', '寅寅寅寅'))
        with patch.object(strength.knowledge_catalog, 'validate', return_value=['hash mismatch']):
            with self.assertRaises(ValueError):
                strength.evaluate(full['facts'], [], [], [])

    def test_cli_uncertainty_reaches_center_and_scenario_keeps_caveats(self):
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / 'scripts/build_chart.py'), '--solar', '1987-07-07',
               '--hour', '10:00', '--sex', '男', '--lat', '31.2', '--lon', '121.5',
               '--time-basis', 'civil', '--format', 'json', '--uncertainty-minutes', '5']
        value = json.loads(subprocess.check_output(cmd, text=True, cwd=root))
        self.assertEqual(value['bazi_core_reading']['strength_reasoning']['status'], 'withheld')
        self.assertTrue(any('出生时间未决' in t for t in value['bazi_core_reading']['strength_reasoning']['missing_conditions']))
        import bazi_scenario_reading as scenario
        from time_scenarios import enumerate_scenarios, resolve_civil
        from datetime import datetime
        compared = scenario.analyze(enumerate_scenarios(resolve_civil(datetime(1987,7,7,10)), 5, 'civil', 120))
        rendered = '\n'.join(scenario.render(compared))
        self.assertIn('未建模司令', rendered)
        self.assertIn('ST01–ST05', rendered)
        a = core.analyze(chart('1987-07-07', 10, 0))['strength_reasoning']
        self.assertEqual(a['decision'], 'strong_tendency')
        self.assertIn('未建模司令', a['text'])
        self.assertIn('当前输入候选', a['text'])

    def test_actual_engine_charts_vary_and_render_cites_source(self):
        results = [core.analyze(chart(d,h,m)) for d,h,m in
                   [('1988-03-18',10,20),('2001-08-22',16,40),('1975-12-11',6,30),('1998-06-30',23,0)]]
        self.assertEqual(len({a['strength_reasoning']['text'] for a in results}), 4)
        self.assertIn('1926', '\n'.join(core.render(results[0])))


if __name__ == '__main__':
    unittest.main()
