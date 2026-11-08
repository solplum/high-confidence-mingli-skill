"""Synthetic boundary comparisons, not predictive validation."""
import contextlib
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bazi_scenario_reading as reading
import build_chart
import pai_pan_bazi as bazi
from time_scenarios import enumerate_scenarios, resolve_civil


class Comparisons(unittest.TestCase):
    def compare(self, civil, minutes=10, basis='civil'):
        scenarios = enumerate_scenarios(civil, minutes, basis, 120)
        result = reading.analyze(scenarios)
        self.assertEqual(len(result['candidates']), len(scenarios['variants']))
        for row, variant in zip(result['candidates'], scenarios['variants']):
            self.assertEqual(row['witness_utc'], variant['witness_utc'])
            self.assertEqual(row['intervals'], variant['intervals'])
            self.assertEqual(row['pillars'], {k: ''.join(variant['fields']['bazi.' + k]) for k in bazi_core_keys()})
        return result

    def test_s4_late_zi_recomputes_day_reference(self):
        result = self.compare(resolve_civil(datetime(2005, 12, 24, 23)))
        self.assertEqual(len(result['candidates']), 2)
        self.assertIn('day_master', result['changing_evidence'])
        self.assertIn('season', result['stable_evidence'])
        text = '\n'.join(reading.render(result))
        self.assertIn('必须按各自日干重算', text)
        for row in result['candidates']:
            self.assertIn(row['text'], text)
            for value in row['pillars'].values():
                self.assertIn(value, text)

    def test_s5_lichun_changes_season(self):
        result = self.compare(bazi.solar_term_beijing(2026, 315), 1)
        self.assertIn('season', result['changing_evidence'])
        self.assertIn('day_master', result['stable_evidence'])
        self.assertEqual({r['evidence']['season'] for r in result['candidates']}, {'丑月，节气划分的冬季', '寅月，节气划分的春季'})

    def test_numerical_mode_never_promises_stability(self):
        result = self.compare(resolve_civil(datetime(2005, 12, 24, 23)), basis='apparent-solar')
        self.assertEqual(result['stable_evidence'], {})
        self.assertTrue(result['observed_constant_evidence'])
        self.assertTrue(all(r['intervals'] == [] for r in result['candidates']))
        self.assertIn('不保证区间稳定', '\n'.join(reading.render(result)))

    def test_complete_coverage_with_no_common_evidence(self):
        # Align Lichun exactly with local 23:00: both day and season change.
        term = bazi.solar_term_beijing(2020, 315)
        utc = term.astimezone(timezone.utc)
        offset = datetime(2020, 2, 4, 23) - utc.replace(tzinfo=None)
        result = self.compare(term.astimezone(timezone(offset)), 1)
        self.assertEqual(result['stable_evidence'], {})
        self.assertEqual(result['observed_constant_evidence'], {})
        self.assertEqual(result['coverage'], 'complete_for_modeled_boundaries_not_astronomical_error')
        text = '\n'.join(reading.render(result))
        self.assertIn('区间内共同证据（仅当前模型）', text)
        self.assertIn('所列证据没有共同项', text)
        self.assertNotIn('不保证区间稳定', text)

    def test_nested_intervals_preserve_inner_candidates(self):
        civil = resolve_civil(datetime(2005, 12, 24, 23))
        small = self.compare(civil, 1)
        large = self.compare(civil, 120)
        encode = lambda r: tuple(r['pillars'].items())
        self.assertLessEqual({encode(r) for r in small['candidates']}, {encode(r) for r in large['candidates']})
        for k, v in large['stable_evidence'].items():
            self.assertEqual(small['stable_evidence'][k], v)

    def test_dst_gap_and_fold_keep_witnesses(self):
        for local, fold in [(datetime(2024, 3, 10, 1, 55), None), (datetime(2024, 11, 3, 1, 55), 0), (datetime(2024, 11, 3, 1, 55), 1)]:
            civil = resolve_civil(local, zone='America/New_York', fold=fold)
            result = self.compare(civil, 70)
            for row in result['candidates']:
                clock = datetime.fromisoformat(row['witness_utc']).astimezone(civil.tzinfo)
                self.assertEqual(clock.replace(tzinfo=None).isoformat(), row['chart_clock'])

    def test_standalone_pattern_attribution_complete_and_deduplicated(self):
        result = self.compare(resolve_civil(datetime(2005, 12, 24, 23)))
        original = copy.deepcopy(result)
        text = '\n'.join(reading.render(result))
        for row in result['candidates']:
            attribution = row['analysis']['pattern_reasoning']['attribution']
            for key in ('attribution', 'upstream_url', 'contributors_url', 'license_url',
                        'adaptation', 'interpretation_label', 'record_id'):
                self.assertIn(attribution[key], text)
            self.assertIn(row['evidence']['pattern'], text)
        self.assertEqual(text.count('格局候选依据：'), 1)
        self.assertIn('上述候选对照中的格局候选解释依 CC BY-SA 4.0 共享', text)
        self.assertEqual(result, original)

    def test_distinct_pattern_attributions_are_not_discarded(self):
        result = self.compare(resolve_civil(datetime(2005, 12, 24, 23)))
        source = result['candidates'][1]['analysis']['pattern_reasoning']['attribution']
        source['adaptation'] = '另一个候选的改编说明（合成测试）'
        source['source_span'] = {'start_line': 10, 'end_line': 12}
        text = '\n'.join(reading.render(result))
        self.assertEqual(text.count('格局候选依据：'), 2)
        self.assertIn(source['adaptation'], text)
        self.assertIn(source['path'] + ':10-12', text)

    def test_json_and_text_use_same_comparison(self):
        args = ['--solar', '2005-12-24', '--hour', '23:00', '--sex', '男', '--lat', '30', '--lon', '120', '--time-basis', 'civil', '--enumerate-scenarios', '--uncertainty-minutes', '10']
        outputs = []
        for extra in (['--format', 'json'], []):
            output = io.StringIO()
            with patch.object(build_chart, 'run_ziwei', return_value=(None, 'synthetic stub')), contextlib.redirect_stdout(output):
                build_chart.main(args + extra)
            outputs.append(output.getvalue())
        comparison = json.loads(outputs[0])['bazi_scenario_comparison']
        for row in comparison['candidates']:
            self.assertIn(row['text'], outputs[1])
        self.assertIn('以下三盘与大运数据为中心时刻', outputs[1])


def bazi_core_keys():
    return ('year', 'month', 'day', 'hour')


if __name__ == '__main__':
    unittest.main()
