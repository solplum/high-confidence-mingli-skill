"""Legacy replay within floating roundoff and real chart-builder profile routing."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_chart
import pai_pan_qizheng as q
import qizheng_provenance as provenance
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

    def test_build_reports_distinct_withholding_reasons_from_native_evidence(self):
        location = ['--lat', '35', '--lon', '120']
        cases = (
            ('missing_longitude', '2000-01-01', '12:00', ['--lat', '35'], (),
             ('地平计算未取得',), ('缺少有效立命宫',)),
            ('undefined_ascendant', '2000-01-01', '12:00', ['--lat', '90', '--lon', '120'], (),
             ('东方上升交点未定义',), ()),
            ('natal_boundary', '2000-01-01', '00:28', location, (),
             ('命度靠近未校准宿界',), ()),
            ('boundary_and_time_error', '2000-01-01', '00:28', location, ('--uncertainty-minutes', '2'),
             ('出生时间存在误差', '命度靠近未校准宿界'), ()),
            ('solar_palace_boundary', '2000-02-22', '12:00', location, (),
             (), ('太阳靠近未校准宿宫界',)),
            ('solar_boundary_and_time_error', '2000-02-22', '12:00', location, ('--uncertainty-minutes', '2'),
             ('出生时间存在误差',), ('太阳靠近未校准宿宫界',)),
        )
        for name, day, clock, coordinates, extra, degree_reasons, palace_reasons in cases:
            with self.subTest(name=name):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    build_chart.main(['--solar', day, '--hour', clock, *coordinates, *extra,
                                      '--sex', '男', '--analysis-year', '2026',
                                      '--qizheng-tradition', 'qianyuan-palace-v1', '--format', 'json'])
                snapshot = json.loads(out.getvalue())
                native = snapshot['qizheng']
                degree = snapshot['qizheng_rule_reading']
                traditional = snapshot['qizheng_traditional_reading']
                self.assertEqual(traditional['status'], 'withheld')
                self.assertEqual(len(native['bodies']), 11)
                if degree_reasons:
                    self.assertEqual(degree['status'], 'withheld')
                    self.assertEqual(degree['claims'], [])
                    for expected in degree_reasons:
                        self.assertIn(expected, degree['reason'])
                else:
                    self.assertTrue(native['bodies']['日']['classification_quality']['near_boundary'])
                    self.assertIsNotNone(native['ming_gong'])
                    self.assertEqual(degree['claims'][0]['status'], 'conditional')
                    self.assertEqual(degree['claims'][1]['status'], 'withheld')
                    self.assertIn(palace_reasons[0], degree['claims'][1]['reason'])
                for expected in degree_reasons + palace_reasons:
                    self.assertIn(expected, traditional['reason'])
                self.assertNotIn('或靠近', traditional['reason'])

    def test_text_only_renders_admitted_degree_groups(self):
        boundary = ['--solar', '1990-01-01', '--hour', '00:43', '--lat', '39.9', '--lon', '116.4']
        normal = ['--solar', '2000-01-01', '--hour', '12:00', '--lat', '35', '--lon', '120']
        for argv, extra, gate in (
                (boundary, [], '靠近未校准宿界'),
                (normal, ['--uncertainty-minutes', '5', '--qizheng-sensitivity'], '出生时间存在误差'),
                (normal, [], None)):
            with self.subTest(argv=argv, extra=extra):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    build_chart.main(argv + ['--sex', '男', '--analysis-year', '2026'] + extra)
                text = out.getvalue()
                self.assertIn('| 日 |', text)
                self.assertIn('**立命宫**', text)
                if gate:
                    self.assertNotIn('**难仇恩用**', text)
                    self.assertIn(gate, text)
                else:
                    self.assertIn('**难仇恩用**', text)
                if extra:
                    self.assertIn('七政时间敏感性', text)

        for argv, gate in ((boundary, '靠近未校准宿界'), (normal, None)):
            with self.subTest(standalone=argv):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(q.run(argv), 0)
                text = out.getvalue()
                self.assertIn('## 七政四余躔度', text)
                self.assertIn('### 七政规则释义', text)
                self.assertNotIn('印贵扶持', text)
                self.assertNotIn('压力侵害', text)
                if gate:
                    self.assertIn(gate, text)
                    self.assertNotIn('恩=', text)
                else:
                    self.assertIn('恩=', text)

    def test_text_labels_legacy_ascendant_as_replay_in_both_entries(self):
        args = ['--solar', '1990-05-15', '--hour', '14:00', '--lat', '31.23', '--lon', '121.47']
        cases = (
            (q.run, args + ['--profile', 'legacy-v1'], '命度（旧版复现值'),
            (q.run, args, '命度（几何东方上升交点'),
            (build_chart.main, args + ['--sex', '男', '--analysis-year', '2026',
                                       '--qizheng-profile', 'legacy-v1'], '升点及昼夜计算存在已知错误'),
        )
        for entry, argv, expected in cases:
            with self.subTest(entry=entry.__module__, argv=argv):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(entry(argv), 0)
                text = out.getvalue()
                self.assertIn(expected, text)
                self.assertNotIn('命度（真升点', text)
                if 'legacy-v1' in argv:
                    self.assertIn('暂不解释', text)
                    self.assertNotIn('恩=', text)

    def test_degree_phase_text_distinguishes_luminary_mansion_hosts(self):
        for hour, host, phase in (('14:00', '日', '火'), ('15:00', '月', '水')):
            with self.subTest(hour=hour):
                args = ['--solar', '2000-01-01', '--hour', hour, '--lat', '35', '--lon', '120']
                for entry, argv in (
                        (build_chart.main, args + ['--sex', '男', '--analysis-year', '2026']),
                        (q.run, args)):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        self.assertEqual(entry(argv), 0)
                    text = out.getvalue()
                    self.assertIn(f'宿主：{host}，度主五行：{phase}', text)
                    self.assertIn(f'则以{phase}为我', text)
                    self.assertIn('| 入宿度 | 宿主 |', text)
                    self.assertNotIn(f'度主五行：{host}', text)

    def test_standalone_place_label_keeps_stars_when_coordinates_are_missing(self):
        argv = ['--solar', '2000-01-03', '--hour', '07:01', '--place', '上海']
        for coordinates, coordinate_text in (
                ([], '- 经纬度：未提供'),
                (['--lat', '31.23'], '- 经纬度：纬 31.23，经度未提供'),
                (['--lon', '121.47'], '- 经纬度：纬度未提供，经 121.47')):
            with self.subTest(coordinates=coordinates):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(q.run(argv + coordinates), 0)
                text = output.getvalue()
                self.assertIn('- 出生地：上海', text)
                self.assertIn(coordinate_text, text)
                for name in q.LUMINARIES:
                    self.assertIn('| %s |' % name, text)
                self.assertIn('命度/恩用难仇：未计算', text)
                self.assertIn('暂不解释', text)
                self.assertNotIn('恩=', text)

        for coordinate, reason in ((['--lat', '91'], 'latitude must be finite'),
                                   (['--lon', 'inf'], 'longitude must be finite')):
            with self.subTest(coordinate=coordinate):
                stderr, stdout = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
                    q.run(argv + coordinate)
                self.assertEqual(error.exception.code, 2)
                self.assertIn(reason, stderr.getvalue())
                self.assertEqual(stdout.getvalue(), '')

    def test_missing_qizheng_manifest_preserves_chart_and_numeric_witnesses(self):
        manifest = 'knowledge/qizheng-rule-sources.json'
        argv = ['--solar', '2000-01-01', '--hour', '12:00', '--sex', '男', '--lat', '35', '--lon', '120',
                '--analysis-year', '2026', '--qizheng-sensitivity', '--uncertainty-minutes', '1',
                '--qizheng-tradition', 'qianyuan-palace-v1', '--format', 'json']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (*provenance.FILES, *rules.SOURCE_PATHS.values()):
                if path == manifest or (root / path).exists():
                    continue
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).symlink_to(ROOT / path)
            out = io.StringIO()
            rendered = io.StringIO()
            with patch.object(provenance, 'ROOT', root), patch.object(rules, 'ROOT', root):
                with contextlib.redirect_stdout(out):
                    build_chart.main(argv)
                with contextlib.redirect_stdout(rendered):
                    build_chart.main(argv[:-2])
        self.assertIn('七政规则来源无法核验', rendered.getvalue())
        self.assertIn('| 日 |', rendered.getvalue())
        self.assertNotIn('**难仇恩用**', rendered.getvalue())
        snapshot = json.loads(out.getvalue())
        self.assertEqual(len(snapshot['bazi']['pillars']), 4)
        self.assertEqual(len(snapshot['ziwei']['chart']['palaces']), 12)
        self.assertEqual(len(snapshot['qizheng']['bodies']), 11)
        evidence = snapshot['qizheng']['model_provenance']
        self.assertIsNone(evidence['source_sha256'][manifest])
        self.assertEqual(evidence['unavailable_sources'][manifest], 'FileNotFoundError')
        for field in ('qizheng_rule_reading', 'qizheng_traditional_reading'):
            self.assertEqual(snapshot[field]['status'], 'withheld')
            self.assertEqual(snapshot[field]['claims'], [])
        candidates = snapshot['qizheng_sensitivity']['candidates']
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertEqual(len(candidate['chart']['bodies']), 11)
            self.assertEqual(candidate['rule_reading']['status'], 'withheld')
            self.assertEqual(candidate['rule_reading']['claims'], [])
            self.assertEqual(candidate['traditional_reading']['status'], 'withheld')

if __name__ == '__main__': unittest.main()
