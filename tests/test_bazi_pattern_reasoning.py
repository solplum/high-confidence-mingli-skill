"""Fixtures are symbolic unit cases, not claimed historical birth charts."""
import unittest
from test_bazi_core_reading import fixture, chart
import bazi_core_reading as core


def reason(stems, branches, missing=False):
    value = fixture(stems, branches)
    if missing:
        value['pillars']['hour'] = ('未知',) * 4
    return core.analyze(value)['pattern_reasoning']


class PatternReasoningTests(unittest.TestCase):
    def test_unique_candidate_and_falsification(self):
        a = reason('戊乙壬乙', '辰卯申巳')
        self.assertEqual(a['selected_candidate'], '伤官格候选')
        self.assertEqual(a['decision'], 'single_candidate')
        self.assertIn('食伤制杀的五行方向', a['text'])
        b = reason('戊丁壬丁', '辰卯申巳')
        self.assertEqual(b['decision'], 'no_candidate_on_route')
        self.assertIsNone(b['selected_candidate'])

    def test_same_element_different_polarity_does_not_expose(self):
        a = reason('辛丙丁戊', '巳申巳申')
        # 申藏庚壬戊：辛偏财 is not 庚正财; 戊伤官 really is exposed.
        self.assertEqual(a['selected_candidate'], '伤官格候选')
        self.assertEqual(next(c for c in a['candidates'] if c['stem'] == '庚')['verdict'], 'not_established')

    def test_engine_pianguan_name_is_an_ordinary_candidate(self):
        a = reason('庚丙甲丁', '辰申寅卯')
        self.assertEqual(a['selected_candidate'], '偏官格候选')
        self.assertEqual(a['decision'], 'single_candidate')

    def test_competing_exposures_not_ranked_by_hidden_order(self):
        a = reason('庚壬丁戊', '辰申巳子')
        self.assertEqual(a['decision'], 'competing_candidates')
        self.assertIsNone(a['selected_candidate'])
        self.assertEqual(sum(c['verdict'] == 'eligible' for c in a['candidates']), 3)

    def test_missing_hour_can_add_competitor(self):
        a = reason('庚丙丁壬', '辰申巳子', missing=True)
        b = reason('庚丙丁壬', '辰申巳子')
        self.assertEqual(a['status'], 'withheld')
        self.assertEqual(a['decision'], 'incomplete_hour')
        self.assertEqual(b['decision'], 'competing_candidates')

    def test_day_stem_and_peer_not_ordinary_pattern(self):
        a = reason('壬丙甲戊', '子寅卯午')
        self.assertEqual(next(c for c in a['candidates'] if c['stem'] == '甲')['verdict'], 'outside_route')
        self.assertNotIn('比肩格候选【入选】', a['text'])

    def test_interactions_not_automatically_cancelled(self):
        a = reason('庚乙壬乙', '酉卯申巳')
        self.assertEqual(a['decision'], 'single_candidate')
        self.assertTrue({'六冲', '天干五合配对'} <= {r['kind'] for r in a['interactions']})
        self.assertIn('不能据配对直接撤格', a['text'])

    def test_no_candidate_is_not_a_negative_relation_check(self):
        cases = [chart('1975-12-11', 6, 30), fixture('戊丁壬丁', '辰卯申巳')]
        for value in cases:
            with self.subTest(pillars=value['pillars']):
                full = core.analyze(value)
                a = full['pattern_reasoning']
                self.assertTrue(any('month' in r['positions'] for r in full['relations']))
                self.assertEqual(a['decision'], 'no_candidate_on_route')
                self.assertEqual(a['interaction_check_status'], 'not_applicable_no_candidate')
                self.assertEqual(a['interactions'], [])
                self.assertIn('未进行候选受制审查', a['text'])
                self.assertNotIn('已知柱未检出', a['text'])

    def test_actual_relation_check_status_when_candidate_exists(self):
        a = reason('戊乙壬乙', '辰卯申巳')
        self.assertEqual(a['interaction_check_status'], 'checked_known_pillars')
        self.assertTrue(a['interactions'])

    def test_competing_officer_paths_preserved(self):
        a = reason('辛庚甲丁', '辰酉寅卯')
        self.assertTrue(a['purity_checks'])
        self.assertIn('不足以断破格', a['text'])
        self.assertIn('救应。候选与其他透干', a['text'])

    def test_real_case_change_in_month_changes_basis(self):
        a = core.analyze(chart('1992-02-04', 20, 0))['pattern_reasoning']
        b = core.analyze(chart('1992-02-04', 23, 0))['pattern_reasoning']
        self.assertNotEqual([c['stem'] for c in a['candidates']], [c['stem'] for c in b['candidates']])
        self.assertNotEqual(a['text'], b['text'])

    def test_attribution_and_validity_never_upgraded(self):
        a = reason('戊乙壬乙', '辰卯申巳')
        self.assertEqual(a['status'], 'conditional')
        self.assertFalse(a['prediction_guarantee'])
        self.assertEqual(a['predictive_validity'], 'unvalidated')
        for key in ('license_notice', 'contributors_url', 'revision', 'source_span', 'adaptation'):
            self.assertTrue(a['attribution'][key])


if __name__ == '__main__':
    unittest.main()
