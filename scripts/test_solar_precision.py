"""Astronomical calendar regressions, not evidence for predictive validity."""
import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import unittest

import pai_pan_bazi as b

ROOT = Path(__file__).resolve().parent


class SolarPrecisionTests(unittest.TestCase):
    def test_hko_minute_samples_2014_and_2026(self):
        data = json.loads((ROOT.parent / 'tests/fixtures/hko_solar_term_minutes.json').read_text())
        for row in data['rows']:
            with self.subTest(row=row):
                ref = datetime.fromisoformat(row['reference_minute'])
                actual = b.solar_term_beijing(row['year'], row['longitude'])
                self.assertLess(abs((actual-ref).total_seconds()), 60)

    def test_port_matches_pinned_js_series_across_interval(self):
        # Same-family comparison only: verifies port fidelity, not accuracy.
        js = ROOT / 'pai_pan_ziwei/node_modules/lunar-javascript'
        if not js.exists():
            self.skipTest('npm ci needed for pinned dependency comparison')
        t = [-0.99, -0.5, 0.0, 0.14, 0.26, 0.5, 1.0]
        script = 'const s=require(process.argv[1]).ShouXingUtil; console.log(JSON.stringify('+json.dumps(t)+'.map(t => ((s.saLon(t,-1)*180/Math.PI)%360+360)%360)));'
        values = json.loads(subprocess.check_output(['node','-e',script,str(js)],text=True))
        for century, ref in zip(t, values):
            self.assertLess(abs(b._lon_delta(b.sun_apparent_longitude(b.J2000+century*36525),ref)),1e-8)

    def test_snapshot_hashes_solar_coefficients(self):
        output = subprocess.check_output([sys.executable, str(ROOT / 'build_chart.py'),
            '--solar', '2026-02-04', '--hour', '04:01', '--sex', '男',
            '--lat', '22.3', '--lon', '114.2', '--format', 'json'], text=True)
        snapshot = json.loads(output)
        path = ROOT / 'astro_data/solar_longitude.json'
        self.assertEqual(snapshot['provenance']['source_sha256']['astro_data/solar_longitude.json'],
                         hashlib.sha256(path.read_bytes()).hexdigest())

    def test_known_tt_utc_and_unknown_future(self):
        for utc, offset in [('1972-01-02T00:00:00+00:00',42.184),
                            ('2000-01-01T00:00:00+00:00',64.184),
                            ('2016-12-31T12:00:00+00:00',68.184),
                            ('2017-01-01T00:00:00+00:00',69.184),
                            ('2026-12-31T12:00:00+00:00',69.184)]:
            dt=datetime.fromisoformat(utc);tt=b.jd_from_datetime_utc(dt)+offset/86400
            self.assertAlmostEqual(b._known_tt_minus_utc(tt),offset)
            self.assertLess(abs((b.jd_tt_to_beijing(tt)-dt).total_seconds()),0.001)
        self.assertIsNone(b._known_tt_minus_utc(b.jd_from_datetime_utc(datetime(2030,1,1,tzinfo=timezone.utc))))
        self.assertIsNone(b._known_tt_minus_utc(b.jd_from_datetime_utc(datetime(1950,1,1,tzinfo=timezone.utc))))
        transition=b.jd_from_datetime_utc(datetime(2017,1,1,tzinfo=timezone.utc))+69.184/86400
        with self.assertRaises(ValueError):
            b.jd_tt_to_beijing(transition-0.5/86400)

    def test_utc_warning_tracks_used_terms_across_year_cutoffs(self):
        cases = ((1972, 1, 2, '1971年大雪'),
                 (1972, 1, 10, None),
                 (2026, 12, 1, None),
                 (2026, 12, 31, '2027年小寒'))
        for year, month, day, expected in cases:
            for sex in ('男', '女'):
                with self.subTest(date=(year, month, day), sex=sex):
                    dt = datetime(year, month, day, 12, tzinfo=b.BJ)
                    result = b.compute(dt.date(), dt.hour, dt.minute, sex=sex, birth_instant=dt)
                    warnings = [w for w in result['warnings'] if 'UT1+8' in w]
                    if expected:
                        self.assertEqual(len(warnings), 1)
                        self.assertIn(expected, warnings[0])
                    else:
                        self.assertEqual(warnings, [])

    def test_principal_term_does_not_warn_as_pillar_boundary(self):
        # Rain Water is a principal term, not one of the 12 month-boundary jie.
        dt = b.solar_term_beijing(2026, 330)
        result = b.compute(dt.date(), dt.hour, dt.minute, birth_instant=dt)
        self.assertFalse(any('边界归属不确定' in w for w in result['warnings']))

    def test_lichun_boundary_and_uncertainty_warning(self):
        before = datetime(2026,2,4,4,1,tzinfo=b.BJ)
        after = datetime(2026,2,4,4,3,tzinfo=b.BJ)
        self.assertEqual(''.join(b.resolve_year_pillar(before)[1:3]),'乙巳')
        self.assertEqual(''.join(b.resolve_year_pillar(after)[1:3]),'丙午')
        result=b.compute(before.date(),before.hour,before.minute,birth_instant=before)
        self.assertTrue(any('边界归属不确定' in w for w in result['warnings']))


if __name__ == '__main__':
    unittest.main()
