import copy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bazi_core_reading as core
import bazi_primary_spouse as approved
import pai_pan_bazi as engine


def evaluate(analysis, **kwargs):
    return approved.evaluate_bazi_primary_spouse(
        analysis['facts'], analysis['relations'], analysis['groups'], analysis['pattern_reasoning'],
        analysis['missing_pillars'], **kwargs)


def native(birthday, hour, sex='男'):
    return engine.compute(birthday, hour=hour, minute=0, sex=sex)


def conditions(card):
    return {condition['id']: condition['status'] for condition in card['conditions']}


class PrimarySpouseTests(unittest.TestCase):
    def test_p1_matches_source_case_without_overriding_three_candidates(self):
        original = native(date(2078, 9, 5), 12)
        chart = core.analyze(original)
        unchanged = copy.deepcopy(chart)
        panel = evaluate(chart, sex=original['sex'])
        p1, r1 = panel['cards']
        self.assertEqual([chart['facts'][k]['pillar'] for k in core.KEYS], ['戊戌', '庚申', '乙卯', '壬午'])
        self.assertEqual(panel['source_errors'], [])
        self.assertEqual(panel['original_candidate_decision'], 'competing_candidates')
        self.assertIsNone(panel['original_selected_candidate'])
        self.assertEqual(chart, unchanged)
        self.assertTrue(all(c['verdict'] == 'eligible' for c in chart['pattern_reasoning']['candidates']))
        self.assertEqual(set(conditions(p1).values()), {'met'})
        self.assertEqual(p1['conditional_model_result']['branch'], 'officer_primary_resource_secondary')
        self.assertEqual(p1['conditional_model_result']['primary'], '正官')
        self.assertEqual(p1['conditional_model_result']['accompanying'], '正印')
        self.assertFalse(p1['manual_review_completed'])
        self.assertTrue(any(r['kind'] == '天干五合配对' for r in panel['natal_relations']))
        self.assertIsNone(r1['conditional_model_result'])
        self.assertEqual(conditions(r1)['independent_ordinary_officer_hypothesis'], 'requires_manual_review')

    def test_p1_native_same_day_exit_when_ren_is_only_hidden(self):
        chart = core.analyze(native(date(2078, 9, 5), 6))
        p1, r1 = evaluate(chart, sex='男')['cards']
        self.assertEqual(chart['facts']['hour']['pillar'], '己卯')
        self.assertIn('壬', [h['stem'] for h in chart['facts']['month']['hidden']])
        self.assertEqual(conditions(p1)['natal_ren_visible'], 'not_met')
        self.assertEqual(conditions(p1)['natal_wu_visible'], 'met')
        self.assertEqual(conditions(p1)['existing_eligible_geng_officer'], 'met')
        self.assertEqual(p1['status'], 'outside_scope')
        self.assertIsNone(p1['conditional_model_result'])
        self.assertEqual(r1['status'], 'outside_scope')
        self.assertEqual(r1['observations']['indirect_wealth_visible_ids'], ['hour.stem'])

    def test_r1_preserves_human_h1_on_the_native_positive_witness(self):
        original = native(date(1959, 9, 29), 14)
        chart = core.analyze(original)
        p1, r1 = evaluate(chart, sex=original['sex'])['cards']
        self.assertEqual([chart['facts'][k]['pillar'] for k in core.KEYS], ['己亥', '癸酉', '甲寅', '辛未'])
        self.assertEqual(p1['status'], 'outside_scope')
        self.assertEqual(r1['status'], 'requires_manual_review')
        self.assertEqual(r1['observations']['direct_wealth_visible_ids'], ['year.stem'])
        self.assertEqual(r1['observations']['indirect_wealth_visible_ids'], [])
        self.assertEqual(r1['observations']['ordinary_officer_candidates'][0]['fact_ids'],
                         ['month.hidden.辛', 'hour.stem'])
        self.assertIn('day.hidden.丙', r1['observations']['food_hurting_ids'])
        self.assertIn('hour.hidden.丁', r1['observations']['food_hurting_ids'])
        self.assertEqual(r1['countercondition_checks'][1]['status'], 'no_visible_killer_observed')
        self.assertEqual(r1['countercondition_checks'][0]['status'], 'requires_manual_review')
        self.assertFalse(r1['manual_review_completed'])
        self.assertIsNone(r1['conditional_model_result'])

    def test_r1_native_old_officer_route_exit_retains_hidden_food_hurting(self):
        chart = core.analyze(native(date(1959, 9, 29), 12))
        _, r1 = evaluate(chart, sex='男')['cards']
        self.assertEqual(chart['facts']['hour']['pillar'], '庚午')
        self.assertEqual(chart['pattern_reasoning']['decision'], 'no_candidate_on_route')
        self.assertEqual(r1['observations']['ordinary_officer_candidates'], [])
        self.assertEqual(r1['observations']['visible_killer_ids'], ['hour.stem'])
        self.assertIn('day.hidden.丙', r1['observations']['food_hurting_ids'])
        self.assertTrue(all('.hidden.' in id_ for id_ in r1['observations']['food_hurting_ids']))
        self.assertEqual(r1['countercondition_checks'][1]['status'], 'requires_manual_review')
        self.assertIsNone(r1['conditional_model_result'])

    def test_r1_day_clash_remains_an_observation_and_sex_must_be_known(self):
        chart = core.analyze(native(date(1959, 9, 29), 16))
        panel = evaluate(chart, sex='男')
        self.assertTrue(any(r['kind'] == '六冲' and 'day' in r['positions'] for r in panel['natal_relations']))
        self.assertEqual(panel['cards'][1]['status'], 'requires_manual_review')
        self.assertEqual(evaluate(chart, sex='女')['cards'][1]['status'], 'outside_scope')
        self.assertEqual(evaluate(chart)['cards'][1]['status'], 'withheld')

    def test_missing_hour_and_unbound_scenario_do_not_clear_complete_conditions(self):
        incomplete = core.analyze(native(date(1959, 9, 29), None))
        _, r1 = evaluate(incomplete, sex='男')['cards']
        self.assertEqual(conditions(r1)['unique_visible_direct_wealth_no_visible_indirect_wealth'], 'unknown')
        self.assertEqual(r1['countercondition_checks'][1]['status'], 'requires_manual_review')
        self.assertIsNone(r1['conditional_model_result'])
        p1_chart = core.analyze(native(date(2078, 9, 5), 12))
        panel = evaluate(p1_chart, sex='男', temporal_uncertainty=True)
        self.assertEqual(panel['status'], 'withheld')
        self.assertEqual(panel['temporal_scope'], 'central_reference_only')
        self.assertIsNone(panel['cards'][0]['conditional_model_result'])
        explicit = evaluate(p1_chart, sex='男', temporal_uncertainty=True, scenario_id='scenario-1')
        self.assertEqual(explicit['temporal_scope'], 'single_natal_input_candidate')
        self.assertEqual(explicit['cards'][0]['status'], 'conditional_candidate_requires_manual_review')

    def test_native_spouse_center_exit_does_not_apply_to_reachable_birth_candidates(self):
        command = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1959-09-29',
                   '--hour', '07:00', '--sex', '男', '--analysis-year', '2026',
                   '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
        center = snapshot['bazi_core_reading']['primary_spouse']
        self.assertEqual(center['temporal_scope'], 'central_reference_only')
        self.assertEqual(center['status'], 'withheld')
        self.assertEqual(center['cards'][1]['status'], 'outside_scope')
        self.assertEqual(center['cards'][1]['observations']['indirect_wealth_visible_ids'], ['hour.stem'])

        earlier, later = snapshot['bazi_scenario_comparison']['candidates']
        self.assertEqual([earlier['pillars']['hour'], later['pillars']['hour']], ['丁卯', '戊辰'])
        for candidate, status in ((earlier, 'requires_manual_review'), (later, 'outside_scope')):
            panel = candidate['analysis']['primary_spouse']
            self.assertEqual(panel['temporal_scope'], 'single_natal_input_candidate')
            self.assertEqual(panel['scenario_id'], candidate['id'])
            self.assertEqual(panel['cards'][1]['status'], status)
            self.assertIsNone(panel['cards'][1]['conditional_model_result'])

    def test_missing_source_withholds_both_approved_cards(self):
        chart = core.analyze(native(date(2078, 9, 5), 12))
        with tempfile.TemporaryDirectory() as empty:
            panel = evaluate(chart, sex='男', root=empty)
        self.assertTrue(panel['source_errors'])
        for card in panel['cards']:
            self.assertEqual(card['status'], 'withheld')
            self.assertIsNone(card['citation'])
            self.assertIsNone(card['conditional_model_result'])


if __name__ == '__main__':
    unittest.main()
