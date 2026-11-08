"""Real corrected-engine charts, source gates, CLI routing, and withheld cases."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_chart
import pai_pan_qizheng as engine
import qizheng_traditional_reading as reading
import qizheng_traditional_study as study


class TraditionalReadingTests(unittest.TestCase):
    def chart(self, **kwargs):
        return engine.compute((2000, 1, 1), 12, 0, 35, 120, **kwargs)[0]

    def test_real_chart_conditional_and_provenance(self):
        chart = self.chart()
        out = reading.analyze(chart, reading.SCHEME)
        self.assertEqual('conditional', out['status'])
        claim = out['claims'][0]
        self.assertEqual(('戌', '火', '我克'), tuple(claim['calculation'][k] for k in ('zhi', 'reference_element', 'relation')))
        self.assertEqual('conditional', claim['status'])
        self.assertFalse(out['personal_ledger_authorized'])
        self.assertFalse(claim['classical_quote_authorized'])
        self.assertEqual('unvalidated', claim['predictive_validity'])
        self.assertEqual('CC-BY-SA-4.0', claim['license'])
        raw = json.dumps(chart, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), out['chart_sha256'])
        text = reading.render(out)
        for value in ('我克', '贡献历史', 'CC-BY-SA-4.0', '定位', '病寿'):
            self.assertIn(value, text)

    def test_absent_unsafe_and_explicit_scheme(self):
        for chart, scheme, uncertain in (
                (self.chart(), None, False), (self.chart(), 'other-school', False),
                (self.chart(), reading.SCHEME, True),
                (self.chart(profile='legacy-v1'), reading.SCHEME, False),
                (engine.compute((2000,1,1),12,0,None,None)[0], reading.SCHEME, False),
                (engine.compute((1800,1,1),12,0,35,120)[0], reading.SCHEME, False),
                (engine.compute((1990,1,1),0,43,39.9,116.4)[0], reading.SCHEME, False)):
            with self.subTest(scheme=scheme, uncertain=uncertain):
                out = reading.analyze(chart, scheme, temporal_uncertainty=uncertain)
                self.assertEqual('withheld', out['status'])
                self.assertEqual([], out['claims'])
        self.assertEqual('withheld', reading.analyze(self.chart(), reading.SCHEME, '罗')['status'])

    def test_missing_and_conflicting_fields(self):
        changes = [lambda c: c['ming_du'].pop('classification_quality'),
                   lambda c: c['bodies']['日'].pop('classification_quality'),
                   lambda c: c['bodies']['日']['classification_quality'].update(near_boundary=True),
                   lambda c: c['ming_gong'].update(zhi='子'),
                   lambda c: c['ming_gong'].pop('hour_zhi'),
                   lambda c: c['bodies'].pop('金'),
                   lambda c: c['bodies'].update(金=None),
                   lambda c: c['bodies'].update(金={}),
                   lambda c: c['bodies']['金'].update(tropical=float('nan')),
                   lambda c: c.pop('horizon_contract'),
                   lambda c: c.pop('jd_utc'),
                   lambda c: c['ming_gong'].update(hour_zhi='子', zhi=engine.ming_gong_zhi(c['sun_palace_zhi'], '子')),
                   lambda c: c.pop('star_frame_contract')]
        for change in changes:
            c = self.chart(); change(c)
            self.assertEqual('withheld', reading.analyze(c, reading.SCHEME)['status'])

    def test_changed_registry_and_source_fail_closed(self):
        with patch.object(study, 'REGISTRY_SHA256', 'bad'):
            self.assertEqual('withheld', reading.analyze(self.chart(), reading.SCHEME)['status'])
        with patch.object(reading.profiles, 'source_evidence', side_effect=ValueError('changed')):
            self.assertEqual('withheld', reading.analyze(self.chart(), reading.SCHEME)['status'])

    def test_standalone_cli_text_json_and_withheld(self):
        argv = [sys.executable, str(ROOT/'scripts/qizheng_traditional_reading.py'),
                '--solar', '2000-01-01', '--hour', '12:00', '--lat', '35', '--lon', '120',
                '--tradition', reading.SCHEME]
        for unsafe in (False, True):
            args = argv + (['--uncertain-time'] if unsafe else [])
            proc = subprocess.run(args + ['--format', 'json'], text=True, capture_output=True)
            self.assertEqual(int(unsafe), proc.returncode, proc.stderr)
            snapshot = json.loads(proc.stdout)
            report = snapshot['traditional_reading']
            proc = subprocess.run(args + ['--format', 'text'], text=True, capture_output=True)
            expected = reading.render(report) + '\n' + '\n'.join('引擎提示：' + w for w in snapshot['warnings']) + '\n'
            self.assertEqual(expected, proc.stdout)

    def test_real_build_chart_route(self):
        args = ['--solar','2000-01-01','--hour','12:00','--sex','男','--lat','35','--lon','120',
                '--analysis-year','2026','--qizheng-tradition', reading.SCHEME]
        for uncertain in (False, True):
            argv = args + (['--uncertainty-minutes','5'] if uncertain else [])
            out = io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv + ['--format','json'])
            snapshot = json.loads(out.getvalue())
            self.assertIsNotNone(snapshot['ziwei'], 'Node integration must really run')
            report = snapshot['qizheng_traditional_reading']
            self.assertEqual('withheld' if uncertain else 'conditional', report['status'])
            self.assertEqual(reading.analyze(snapshot['qizheng'], reading.SCHEME, temporal_uncertainty=uncertain), report)
            out = io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv)
            self.assertIn(reading.render(report), out.getvalue())


if __name__ == '__main__': unittest.main()
