"""Legacy replay within floating roundoff and real chart-builder profile routing."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_chart
import pai_pan_qizheng as q
import qizheng_rule_profiles as rules

ROOT = Path(__file__).resolve().parents[1]

# Absolute numerical-replay budgets, not astronomical accuracy claims. A small
# longitude roundoff can be many ULPs after subtracting a mansion boundary, so
# compare angular differences in degrees rather than ULPs of the small residue.
# Julian dates and all discrete classifications remain exact.
REPLAY_ABS_TOLERANCE = {
    'ayanamsa': 1e-12, 'tropical': 1e-12, 'sidereal': 1e-12, 'mansion_deg': 1e-12,  # degrees
    'eot_minutes': 1e-12,  # minutes
    'sunrise_local': 1e-12, 'sunset_local': 1e-12,  # hours
}


class IntegrationTests(unittest.TestCase):
    def assert_legacy_replay(self, expected, actual, path=()):
        label = '/'.join(map(str, path)) or '/'
        self.assertIs(type(actual), type(expected), label)
        if isinstance(expected, dict):
            self.assertEqual(expected.keys(), actual.keys(), label)
            for key in expected:
                self.assert_legacy_replay(expected[key], actual[key], path + (key,))
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), label)
            for index, (left, right) in enumerate(zip(expected, actual)):
                self.assert_legacy_replay(left, right, path + (index,))
        elif type(expected) is float and path[-1] in REPLAY_ABS_TOLERANCE:
            self.assertLessEqual(abs(expected - actual), REPLAY_ABS_TOLERANCE[path[-1]], label)
        else:
            self.assertEqual(expected, actual, label)

    def test_old_keys_replay_with_roundoff_budget(self):
        fixture = json.loads((ROOT / 'tests/fixtures/qizheng/legacy-c49e6a5.json').read_text())
        for case in fixture['cases']:
            with self.subTest(args=case['args']):
                actual, _ = q.compute(*case['args'], profile='legacy-v1')
                self.assert_legacy_replay(case['expected'], {k: actual[k] for k in case['expected']})

    def test_replay_accepts_only_unit_bounded_roundoff(self):
        expected = json.loads((ROOT / 'tests/fixtures/qizheng/legacy-c49e6a5.json').read_text())['cases'][0]['expected']
        actual = copy.deepcopy(expected)
        actual['bodies']['土']['mansion_deg'] += 5e-13
        actual['eot_minutes'] += 5e-13
        actual['day_night']['sunrise_local'] += 5e-13
        self.assert_legacy_replay(expected, actual)

    def test_replay_still_rejects_numerical_and_discrete_regressions(self):
        expected = json.loads((ROOT / 'tests/fixtures/qizheng/legacy-c49e6a5.json').read_text())['cases'][0]['expected']
        mutations = [
            ('angle', ('bodies', '土', 'tropical'), lambda value: value + 1e-9),
            ('full_turn', ('bodies', '土', 'sidereal'), lambda value: value + 360),
            ('eot', ('eot_minutes',), lambda value: value + 1e-9),
            ('sunrise', ('day_night', 'sunrise_local'), lambda value: value + 1e-9),
            ('julian_date', ('jd_ut',), lambda value: value + 1e-9),
            ('nonfinite', ('bodies', '土', 'tropical'), lambda value: float('nan')),
            ('mansion', ('bodies', '土', 'mansion'), lambda value: '角'),
            ('day_night', ('day_night', 'type'), lambda value: '夜生'),
            ('list_order', ('en_yong', '恩'), lambda value: list(reversed(value))),
            ('list_length', ('en_yong', '恩'), lambda value: value[:-1]),
            ('type', ('bodies', '土', 'mansion_deg'), lambda value: True),
        ]
        for name, path, mutate in mutations:
            with self.subTest(regression=name):
                actual = copy.deepcopy(expected)
                parent = actual
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = mutate(parent[path[-1]])
                with self.assertRaises(AssertionError):
                    self.assert_legacy_replay(expected, actual)
        for name, key in [('missing', 'mansion'), ('extra', 'unexpected')]:
            with self.subTest(regression=name):
                actual = copy.deepcopy(expected)
                if name == 'missing':
                    del actual['bodies']['土'][key]
                else:
                    actual['bodies']['土'][key] = None
                with self.assertRaises(AssertionError):
                    self.assert_legacy_replay(expected, actual)

    def test_dynamic_provenance(self):
        for profile in ('legacy-v1', 'physical-v2'):
            chart, _ = q.compute((2000,1,1),12,0,35,120,profile=profile)
            self.assertEqual(profile, chart['model_provenance']['calculation_profile'])
            for path, digest in chart['model_provenance']['source_sha256'].items():
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest)

    def test_boundary_and_range_gates(self):
        for date, hour, minute in (((1990,1,1),0,43), ((1800,1,1),12,0)):
            chart, _ = q.compute(date,hour,minute,39.9,116.4)
            self.assertEqual('withheld', rules.analyze(chart)['status'])
        chart,_ = q.compute((2000,1,1),12,0,35,120)
        chart['bodies']['日']['classification_quality']['near_boundary'] = True
        chart['ming_du']['classification_quality']['near_boundary'] = False
        self.assertEqual('withheld', rules.analyze(chart)['claims'][1]['status'])
        for invalid in ('', '木火', None):
            with self.assertRaises(ValueError): rules.relation(invalid,'木')

    def test_real_build_chart_profiles_and_uncertainty(self):
        for profile in ('legacy-v1', 'physical-v2'):
            argv=['--solar','2000-01-01','--hour','12:00','--sex','男',
                  '--lat','35','--lon','120','--analysis-year','2026','--qizheng-profile',profile]
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv+['--format','json'])
            snapshot=json.loads(out.getvalue())
            self.assertIsNotNone(snapshot['ziwei'], 'Requires real Node/tsx installation, not a skip or mock')
            self.assertEqual(profile,snapshot['qizheng_rule_reading']['calculation_profile'])
            self.assertEqual(rules.analyze(snapshot['qizheng']),snapshot['qizheng_rule_reading'])
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv)
            self.assertIn(rules.format_reading(snapshot['qizheng_rule_reading']),out.getvalue())
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv+['--format','json','--uncertainty-minutes','5'])
            self.assertEqual('withheld',json.loads(out.getvalue())['qizheng_rule_reading']['status'])

if __name__ == '__main__': unittest.main()
