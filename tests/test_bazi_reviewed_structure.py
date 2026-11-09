import copy
from datetime import date
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


def fixture(pillars):
    chars = pillars.split()
    day_index = engine.GAN.index(chars[2][0])
    return {'pillars': {k: (s[0], s[1], '—' if k == 'day' else engine.shishen_of(day_index, engine.GAN.index(s[0])),
                            engine.format_canggan(s[1])) for k, s in zip(core.KEYS, chars)}}


def card(analysis, rule):
    return next(c for c in analysis['reviewed_structure']['cards'] if c['id'] == rule)


def evaluate_again(analysis, **kwargs):
    return reviewed.evaluate(analysis['facts'], analysis['month_exposure'], analysis['relations'], analysis['groups'],
                             analysis['pattern_reasoning'], analysis['strength_reasoning'], analysis['missing_pillars'], **kwargs)


class ReviewedBaZiTests(unittest.TestCase):
    def test_officer_challenge_and_resource_rescue_are_parallel_not_verdicts(self):
        a = core.analyze(fixture('丁巳 辛酉 甲寅 癸亥'))
        k = card(a, 'BZ-K01')
        self.assertEqual(k['status'], 'conditional')
        self.assertEqual({b['id'] for b in k['branches']},
                         {'officer_challenged', 'resource_rescue_candidate', 'hidden_resource_direction_only', 'rescue_efficacy_unresolved'})
        self.assertTrue(any(p['from_id'] == 'year.stem' and p['to_id'] == 'month.stem' for p in k['paths']))
        self.assertTrue(any(p['from_id'] == 'hour.stem' and p['to_id'] == 'year.stem' for p in k['paths']))
        self.assertTrue(any(r.get('kind') == '六冲' for r in a['reviewed_structure']['context']['contested_effects']))
        self.assertEqual(k['effect_assessment'], 'withheld')
        self.assertEqual(k['citation']['record_id'], 'bazi-reviewed-BZ-K01')

    def test_no_external_resource_does_not_reuse_rescue(self):
        a = core.analyze(fixture('丁巳 辛酉 甲寅 戊午'))
        k = card(a, 'BZ-K01')
        self.assertEqual([b['id'] for b in k['branches']], ['officer_challenged'])
        self.assertFalse(any(p['kind'] == 'resource_controls_hurting_officer' for p in k['paths']))
        self.assertEqual(next(c for c in k['conditions'] if c['id'] == 'resource_visible')['status'], 'not_observed_known_pillars')

    def test_hidden_resource_is_not_a_visible_rescue(self):
        a = core.analyze(fixture('丁巳 辛酉 甲寅 戊辰'))
        k = card(a, 'BZ-K01')
        self.assertNotIn('resource_rescue_candidate', [b['id'] for b in k['branches']])
        self.assertIn('hidden_resource_direction_only', [b['id'] for b in k['branches']])
        self.assertTrue(any(n['id'] == 'hour.hidden.癸' and n['layer'] == 'hidden' for n in k['nodes']))
        counter = [p for p in k['counterevidence'] if p.get('kind') == 'wealth_controls_resource']
        self.assertTrue(any(p['from_id'] == 'hour.stem' and p['to_id'] == 'hour.hidden.癸' for p in counter))

    def test_killer_food_resource_chain_retains_competing_candidate(self):
        a = core.analyze(fixture('丙寅 庚申 甲午 壬辰'))
        k = card(a, 'BZ-K02')
        self.assertEqual({c['ten_god'] for c in a['reviewed_structure']['context']['candidates']}, {'偏官', '偏印'})
        self.assertEqual([c['ten_god'] for c in k['candidates']], ['偏官'])
        self.assertEqual([c['ten_god'] for c in k['exclusions'][0]['candidates']], ['偏印'])
        self.assertTrue(any(p['from_id'] == 'year.stem' and p['to_id'] == 'month.stem' and p['kind'] == 'food_controls_killer' for p in k['paths']))
        self.assertTrue(any(p['from_id'] == 'hour.stem' and p['to_id'] == 'year.stem' and p['kind'] == 'resource_controls_food' for p in k['paths']))
        self.assertTrue(k['reversal_chains'])
        month_wealth = next(n for n in k['nodes'] if n['id'] == 'month.hidden.戊')
        self.assertEqual(month_wealth['layer'], 'hidden')
        self.assertTrue(all(p['efficacy'] == 'withheld' for p in k['paths']))

    def test_same_wealth_has_reverse_roles_and_hidden_resource_is_kept(self):
        a = core.analyze(fixture('丙寅 庚申 甲午 戊辰'))
        k = card(a, 'BZ-K02')
        self.assertEqual({c['ten_god'] for c in a['reviewed_structure']['context']['candidates']}, {'偏官', '偏财'})
        self.assertFalse(any(n['layer'] == 'visible' and n['ten_god'] in reviewed.RESOURCE for n in k['nodes']))
        self.assertTrue(any(n['id'] == 'month.hidden.壬' for n in k['nodes']))
        roles = next(r for r in k['shared_wealth_roles'] if r['node_id'] == 'hour.stem')
        self.assertTrue(roles['controls_resource_path_ids'])
        self.assertTrue(roles['generates_killer_path_ids'])
        self.assertTrue(k['alternative_paths'])
        self.assertEqual(k['effect_assessment'], 'withheld')

    def test_hurting_officer_does_not_replace_food(self):
        a = core.analyze(fixture('丁卯 庚申 甲午 壬辰'))
        k = card(a, 'BZ-K02')
        self.assertFalse(any(n['ten_god'] == '食神' for n in k['nodes']))
        self.assertFalse(any(p['kind'] == 'food_controls_killer' for p in k['paths']))
        self.assertFalse(k['reversal_chains'])
        self.assertIn('year.stem', k['exclusions'][1]['fact_ids'])

    def test_self_other_and_separated_combination_roles(self):
        a = core.analyze(fixture('戊辰 庚申 乙丑 丙子'))
        pair = next(p for p in card(a, 'BZ-K03')['pairs'] if p['symbols'] == '庚乙')
        self.assertEqual(pair['role'], 'self')
        self.assertEqual(pair['positions'], ['month', 'day'])
        self.assertTrue(pair['adjacent'])
        b = core.analyze(fixture('乙卯 庚申 甲午 戊辰'))
        pair = next(p for p in card(b, 'BZ-K03')['pairs'] if p['symbols'] == '乙庚')
        self.assertEqual(pair['role'], 'other')
        c = core.analyze(fixture('甲寅 庚申 壬子 己未'))
        pair = next(p for p in card(c, 'BZ-K03')['pairs'] if p['symbols'] == '甲己')
        self.assertEqual([n['stem'] for n in pair['intervening_stems']], ['庚', '壬'])
        self.assertEqual(pair['efficacy'], 'withheld')

    def test_duplicate_stems_keep_position_and_shared_endpoint(self):
        a = core.analyze(fixture('甲寅 甲子 壬申 己未'))
        pairs = card(a, 'BZ-K03')['pairs']
        self.assertEqual(len(pairs), 2)
        self.assertEqual({tuple(p['positions']) for p in pairs}, {('year', 'hour'), ('month', 'hour')})
        self.assertTrue(all(p['shared_endpoint_pairs'][0]['shared_positions'] == ['hour'] for p in pairs))
        self.assertEqual(len([n for n in card(a, 'BZ-K03')['nodes'] if n['stem'] == '甲']), 2)

    def test_semantic_center_assistance_and_balancing_remain_separate(self):
        a = core.analyze(fixture('己巳 辛酉 甲寅 戊辰'))
        k = card(a, 'BZ-K04')
        self.assertEqual(len(k['semantic_objects']), 1)
        obj = k['semantic_objects'][0]
        self.assertEqual(obj['month_observation_center']['fact_ids'], ['month.hidden.辛', 'month.stem'])
        self.assertTrue({'year.stem', 'hour.stem'} <= {r['node_id'] for r in obj['assisting_candidates']})
        self.assertTrue(any(p.get('from_id') == 'year.stem' and p.get('to_id') == 'year.hidden.庚'
                            and p.get('kind') == 'wealth_generates_killer' for p in k['counterevidence']))
        self.assertEqual(obj['balancing_need']['status'], 'withheld')
        self.assertEqual(obj['balancing_need']['strength_decision'], a['strength_reasoning']['decision'])
        self.assertTrue(any(p['kind'] == '天干五合配对' for p in a['relations']))
        self.assertTrue(any(p['kind'] == '六合配对' for p in a['reviewed_structure']['context']['month_branch_relations']))
        b = core.analyze(fixture('己巳 丙酉 甲寅 戊辰'))
        self.assertEqual(card(b, 'BZ-K04')['semantic_objects'], [])
        self.assertEqual(card(b, 'BZ-K04')['status'], 'withheld')
        self.assertEqual(card(b, 'BZ-K01')['paths'], [])

    def test_competing_candidates_get_distinct_semantic_objects(self):
        a = core.analyze(fixture('丙寅 庚申 甲午 壬辰'))
        objects = card(a, 'BZ-K04')['semantic_objects']
        self.assertEqual({o['candidate_id'] for o in objects}, {'month.庚.偏官', 'month.壬.偏印'})
        self.assertTrue(all(o['balancing_need']['status'] == 'withheld' for o in objects))

    def test_unknown_hour_never_becomes_resource_or_competition_absence(self):
        r = fixture('丁巳 辛酉 甲寅 戊午')
        r['pillars']['hour'] = ('未知',) * 4
        a = core.analyze(r)
        panel = a['reviewed_structure']
        self.assertEqual(panel['status'], 'withheld')
        self.assertTrue(all(c['status'] == 'withheld' for c in panel['cards']))
        check = next(c for c in card(a, 'BZ-K01')['conditions'] if c['id'] == 'resource_visible')
        self.assertEqual(check['status'], 'unknown')
        self.assertEqual(card(a, 'BZ-K04')['semantic_objects'][0]['status'], 'withheld')
        shared_check = next(c for c in card(a, 'BZ-K03')['conditions'] if c['id'] == 'shared_pair_completeness')
        self.assertEqual(shared_check['status'], 'unknown')

    def test_nonzero_time_uncertainty_withholds_entire_panel(self):
        r = fixture('丁巳 辛酉 甲寅 癸亥')
        r['scenario_id'] = 'candidate-2'
        a = core.analyze(r, temporal_uncertainty=True)
        panel = a['reviewed_structure']
        self.assertEqual(panel['scenario_id'], 'candidate-2')
        self.assertTrue(panel['temporal_uncertainty'])
        self.assertTrue(all(c['status'] == 'withheld' for c in panel['cards']))
        self.assertTrue(card(a, 'BZ-K01')['paths'])
        self.assertEqual(a['pattern_reasoning']['decision'], 'single_candidate')

    def test_source_failure_withholds_new_panel_with_specific_reason(self):
        a = core.analyze(fixture('丁巳 辛酉 甲寅 癸亥'))
        with patch('reviewed_knowledge.load_profile', side_effect=ValueError('source SHA256 mismatch: bazi-reviewed-structure-source')):
            panel = evaluate_again(a)
        self.assertEqual(panel['status'], 'withheld')
        self.assertEqual(panel['source_errors'], ['source SHA256 mismatch: bazi-reviewed-structure-source'])
        self.assertTrue(all(c['status'] == 'withheld' and not c['paths'] and c['citation'] is None for c in panel['cards']))

    def test_inputs_and_previous_decisions_are_unchanged(self):
        result = fixture('丙寅 庚申 甲午 壬辰')
        original = copy.deepcopy(result)
        a = core.analyze(result)
        self.assertEqual(result, original)
        before = copy.deepcopy(a)
        evaluate_again(a)
        self.assertEqual(a, before)
        expected_pattern = pattern.evaluate(a['facts'], a['month_exposure'], a['relations'], a['groups'], a['missing_pillars'])
        expected_strength = strength.evaluate(a['facts'], a['relations'], a['groups'], a['missing_pillars'])
        self.assertEqual(a['pattern_reasoning'], expected_pattern)
        self.assertEqual(a['strength_reasoning'], expected_strength)
        self.assertEqual(len(a['sections']), 5)

    def test_real_engine_input_has_referentially_valid_nodes_and_sources(self):
        result = engine.compute(date(1988, 3, 18), hour=10, minute=20, now=date(2026, 1, 1))
        a = core.analyze(result)
        panel = a['reviewed_structure']
        self.assertEqual(panel, evaluate_again(a))
        self.assertEqual(len(panel['cards']), 4)
        for k in panel['cards']:
            ids = {n['id'] for n in k['nodes']}
            for edge in k['paths'] + k.get('alternative_paths', []):
                self.assertTrue({edge['from_id'], edge['to_id']} <= ids)
            self.assertEqual(k['citation']['source_id'], 'bazi-reviewed-structure-source')
            self.assertTrue(k['citation']['sha256'])
            self.assertEqual(k['effect_assessment'], 'withheld')
        self.assertEqual(panel['reading_use'], 'conditional_module_only')
        json.dumps(a, ensure_ascii=False, allow_nan=False)

    def test_real_engine_time_change_adds_and_removes_self_combination(self):
        analyses = [core.analyze(engine.compute(date(1988, 3, 18), hour=h, minute=20, now=date(2026, 1, 1)))
                    for h in (10, 14)]
        before, after = analyses
        self.assertEqual(before['facts']['day'], after['facts']['day'])
        self.assertEqual(card(before, 'BZ-K03')['pairs'], [])
        pair = card(after, 'BZ-K03')['pairs'][0]
        self.assertEqual(pair['positions'], ['day', 'hour'])
        self.assertEqual(pair['symbols'], '壬丁')
        self.assertEqual(pair['role'], 'self')
        self.assertEqual(pair['endpoints'][1]['ten_god'], '正财')
        self.assertEqual(pair['efficacy'], 'withheld')


if __name__ == '__main__':
    unittest.main()
