import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pai_pan_bazi as engine
import bazi_core_reading as core
import bazi_pattern_reasoning as pattern
import bazi_strength_reasoning as strength
import bazi_reviewed_structure as reviewed
import bazi_purpose_extensions as purpose


def fixture(pillars):
    chars = pillars.split()
    day = engine.GAN.index(chars[2][0])
    return {'pillars': {k: (s[0], s[1], '—' if k == 'day' else engine.shishen_of(day, engine.GAN.index(s[0])),
                            engine.format_canggan(s[1])) for k, s in zip(core.KEYS, chars)}}


def card(analysis, rule):
    return next(c for c in analysis['purpose_extensions']['cards'] if c['id'] == rule)


def evaluate_again(a, **kwargs):
    return purpose.evaluate(a['facts'], a['relations'], a['groups'], a['pattern_reasoning'],
                            a['strength_reasoning'], a['missing_pillars'], **kwargs)


class PurposeExtensionTests(unittest.TestCase):
    def test_unexposed_single_month_opens_only_new_condition_route(self):
        a = core.analyze(fixture('乙酉 戊子 辛巳 己亥'))
        m1, m2 = card(a, 'BZ-M01'), card(a, 'BZ-M02')
        self.assertEqual(m1['decision'], 'unexposed_candidate')
        self.assertEqual(m1['candidates'][0]['exposure_status'], 'unexposed_in_current_candidate')
        self.assertEqual(m1['candidates'][0]['fact_ids'], ['month.hidden.癸'])
        self.assertEqual(m2['candidates'][0]['route_ids'], [purpose.ROUTE])
        self.assertEqual(a['pattern_reasoning']['decision'], 'no_candidate_on_route')
        self.assertIsNone(a['pattern_reasoning']['selected_candidate'])
        self.assertEqual(a['strength_reasoning']['status'], 'withheld')
        self.assertTrue(all(not c['candidates'] for c in a['reviewed_structure']['cards']))
        self.assertTrue(all(b['status'] == 'withheld' for b in m2['branches']))
        self.assertTrue(all(c['effect_assessment'] == 'withheld' for c in a['purpose_extensions']['cards']))

    def test_already_exposed_record_is_not_mislabeled_unexposed(self):
        a = core.analyze(fixture('癸酉 戊子 辛巳 己亥'))
        m1, m2 = card(a, 'BZ-M01'), card(a, 'BZ-M02')
        self.assertEqual(m1['decision'], 'exposed_record')
        self.assertEqual(m1['candidates'][0]['exposed_at'], ['year'])
        self.assertEqual(m1['candidates'][0]['exposure_status'], 'exposed_known_pillars')
        self.assertEqual(a['pattern_reasoning']['decision'], 'single_candidate')
        self.assertEqual(len(m2['candidates']), 1)
        self.assertEqual(set(m2['candidates'][0]['route_ids']), {purpose.ROUTE, a['pattern_reasoning']['rule_version']})

    def test_unknown_hour_keeps_month_center_without_full_unexposed_claim(self):
        result = fixture('乙酉 戊子 辛巳 己亥')
        result['pillars']['hour'] = ('未知',) * 4
        a = core.analyze(result)
        m1 = card(a, 'BZ-M01')
        self.assertEqual(m1['decision'], 'incomplete_hour')
        c = m1['candidates'][0]
        self.assertEqual(c['exposure_status'], 'unknown_full_chart_exposure')
        self.assertFalse(c['full_chart_exposure_checked'])
        self.assertEqual(c['status'], 'withheld')
        self.assertTrue(all(c['status'] == 'withheld' for c in a['purpose_extensions']['cards']))
        text = '\n'.join(purpose.render(a['purpose_extensions']))
        self.assertIn('缺时不能确认全盘未透', text)

    def test_multi_hidden_wu_and_peers_do_not_open_new_ordinary_route(self):
        for pillars, expected in [('乙酉 戊午 辛巳 己亥', 'outside_route'),
                                  ('乙酉 戊亥 辛巳 己亥', 'outside_route'),
                                  ('己丑 丙酉 辛亥 戊子', 'outside_ordinary')]:
            with self.subTest(pillars=pillars):
                a = core.analyze(fixture(pillars))
                m1 = card(a, 'BZ-M01')
                self.assertEqual(m1['decision'], expected)
                self.assertEqual(m1['candidates'], [])
                self.assertEqual(m1['status'], 'withheld')

    def test_non_killing_food_resource_wealth_directions_keep_costs_and_efficacy(self):
        a = core.analyze(fixture('乙酉 戊子 辛巳 己亥'))
        m2 = card(a, 'BZ-M02')
        self.assertTrue(any(p['kind'] == 'wealth_controls_resource' and p['from_id'] == 'year.stem' for p in m2['paths']))
        self.assertTrue(any(p['kind'] == 'resource_controls_food' and p['to_id'] == 'month.hidden.癸' for p in m2['paths']))
        self.assertTrue(any(p['kind'] == 'resource_generates_day' for p in m2['paths']))
        self.assertTrue(any(p['kind'] == 'wealth_generates_officer_or_killer' and p['to_id'] == 'day.hidden.丙' for p in m2['paths']))
        self.assertTrue(all(p['efficacy'] == 'withheld' for p in m2['paths']))
        self.assertTrue(all(c['status'] == 'withheld' for c in m2['manual_checks']))
        hidden_only = core.analyze(fixture('庚酉 戊子 辛巳 己亥'))
        m2_hidden = card(hidden_only, 'BZ-M02')
        self.assertEqual(next(c for c in m2_hidden['conditions'] if c['id'] == 'wealth_visible')['status'], 'not_observed_known_pillars')
        self.assertEqual(next(c for c in m2_hidden['conditions'] if c['id'] == 'wealth_hidden')['status'], 'present')
        self.assertEqual(m2_hidden['branches'][1]['visible_wealth_fact_ids'], [])

    def test_summer_wood_enters_seasonal_checks_without_proving_heat_or_water_effect(self):
        summer = core.analyze(fixture('丙午 癸巳 甲子 丙寅'))
        m3 = card(summer, 'BZ-M03')
        self.assertEqual(m3['domain_status'], 'summer_wood')
        self.assertEqual(len(m3['candidates']), 1)
        self.assertTrue(any(p['kind'] == 'water_resource_generates_wood' for p in m3['paths']))
        self.assertTrue(any(p['kind'] == 'water_resource_controls_food' for p in m3['paths']))
        self.assertTrue(all(c['status'] == 'withheld' for c in m3['manual_checks']))
        self.assertEqual(m3['effect_assessment'], 'withheld')
        winter = card(core.analyze(fixture('乙酉 戊子 辛巳 己亥')), 'BZ-M03')
        self.assertEqual(winter['domain_status'], 'outside_summer_wood_scope')
        self.assertEqual(winter['candidates'], [])
        self.assertEqual(winter['paths'], [])
        self.assertEqual(winter['status'], 'withheld')

    def test_time_uncertainty_preserves_local_facts_but_withholds_scope(self):
        result = fixture('乙酉 戊子 辛巳 己亥')
        result['scenario_id'] = 'boundary-candidate-2'
        a = core.analyze(result, temporal_uncertainty=True)
        panel = a['purpose_extensions']
        self.assertEqual(panel['scenario_id'], 'boundary-candidate-2')
        self.assertEqual(panel['temporal_scope'], 'single_input_candidate')
        self.assertEqual(panel['status'], 'withheld')
        self.assertTrue(card(a, 'BZ-M01')['candidates'])
        self.assertEqual(a['pattern_reasoning']['decision'], 'no_candidate_on_route')

    def test_sources_fail_closed_without_new_candidates_or_fallback(self):
        a = core.analyze(fixture('乙酉 戊子 辛巳 己亥'))
        with patch('reviewed_knowledge.load_profile', side_effect=ValueError('purpose source hash mismatch')):
            panel = evaluate_again(a)
        self.assertEqual(panel['status'], 'withheld')
        self.assertEqual(panel['source_errors'], ['purpose source hash mismatch'])
        self.assertTrue(all(not c['candidates'] and not c['paths'] and c['citation'] is None for c in panel['cards']))

    def test_old_outputs_and_inputs_remain_equal_and_new_references_resolve(self):
        result = fixture('丙午 癸巳 甲子 丙寅')
        before = copy.deepcopy(result)
        a = core.analyze(result)
        snapshot = copy.deepcopy(a)
        self.assertEqual(a['purpose_extensions'], evaluate_again(a))
        self.assertEqual(a, snapshot)
        self.assertEqual(result, before)
        self.assertEqual(a['pattern_reasoning'], pattern.evaluate(a['facts'], a['month_exposure'], a['relations'], a['groups'], a['missing_pillars']))
        self.assertEqual(a['strength_reasoning'], strength.evaluate(a['facts'], a['relations'], a['groups'], a['missing_pillars']))
        self.assertEqual(a['reviewed_structure'], reviewed.evaluate(a['facts'], a['month_exposure'], a['relations'], a['groups'], a['pattern_reasoning'], a['strength_reasoning'], a['missing_pillars']))
        self.assertEqual(len(a['sections']), 5)
        ids = {n['id'] for n in a['purpose_extensions']['nodes']}
        for c in a['purpose_extensions']['cards']:
            self.assertEqual(c['citation']['source_id'], 'bazi-purpose-extensions-source')
            self.assertEqual(c['citation']['primary_sources'][0]['source_id'], 'bazi-purpose-extensions-audit')
            for p in c['paths']:
                self.assertTrue({p['from_id'], p['to_id']} <= ids)
        self.assertIn('八字分目的受限增补', '\n'.join(core.render(a)))
        json.dumps(a, ensure_ascii=False, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
