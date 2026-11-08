"""Synthetic regression and independent numeric reference; no private cases."""
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import pai_pan_qizheng as q
from qizheng_star_frame import spica_mean_longitude, boundary_diagnostic, star_frame_contract


class StarFrameTests(unittest.TestCase):
    def test_catalog_coordinate_conversion_j2000(self):
        # Independent spherical formula for the frozen SIMBAD ICRS direction.
        ra, dec, eps = map(math.radians, (201.298247375, -11.161319472222222, 23.43929111111111))
        x = math.cos(dec)*math.cos(ra)
        y = math.cos(dec)*math.sin(ra)*math.cos(eps)+math.sin(dec)*math.sin(eps)
        expected = math.degrees(math.atan2(y,x)) % 360
        self.assertAlmostEqual(expected,203.8413578083478,places=10)
        self.assertAlmostEqual(spica_mean_longitude(q.J2000),expected,places=10)
        self.assertGreater(abs(expected-201.2983),2.5)

    def test_201_years_independent_erfa_iau2006(self):
        data=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/spica_erfa_mean_date.json').read_text())
        self.assertEqual(len(data['rows']),201)
        for year,jd,expected in data['rows']:
            self.assertLess(abs(q.lon_delta(spica_mean_longitude(jd),expected))*3600,1.0,str(year))

    def test_legacy_math_unchanged(self):
        for t in (-1,-.25,0,.3,1):
            jd=q.J2000+t*36525
            old=201.2983+(5028.796195*t+1.1054348*t*t+.00007964*t**3)/3600
            self.assertEqual(q.spica_ayanamsa(jd),old)
            self.assertEqual(q.spica_ayanamsa(jd,'legacy-v1'),old)
            self.assertEqual(q.to_sidereal(100,jd,'legacy-v1'),(100-old)%360)
        with self.assertRaises(ValueError):q.spica_ayanamsa(q.J2000,'unknown')

    def test_independent_approximate_boundaries_not_shifted(self):
        self.assertEqual(q.MANSIONS[0][2],0)
        self.assertEqual(q.MANSIONS[1][2],12)
        self.assertEqual(q.MANSIONS[-1][2],350)
        contract=star_frame_contract(q.J2000)
        self.assertFalse(contract['mansion_boundaries_validated'])
        self.assertIsNone(contract['mansion_boundary_error_deg'])
        # Same synthetic tropical direction changes mansion/palace solely by origin.
        old=q.to_sidereal(230,q.J2000,'legacy-v1')
        new=q.to_sidereal(230,q.J2000,'physical-v2')
        self.assertEqual(q.mansion_of(old)[0],'氐')
        self.assertEqual(q.mansion_of(new)[0],'亢')
        self.assertEqual(q.palace_of(old),'卯')
        self.assertEqual(q.palace_of(new),'辰')

    def test_boundary_screen_wrap_and_conditional_metadata(self):
        starts=[m[2] for m in q.MANSIONS]
        for lon in (0,.099,359.999,12,11.999):
            self.assertTrue(boundary_diagnostic(lon,starts)['near_boundary'])
        far=boundary_diagnostic(5,starts)
        self.assertEqual(far['status'],'approximate-unvalidated')
        self.assertFalse(far['validated'])
        result,warnings=q.compute((2000,1,1),12,0,30,120)
        self.assertEqual(result['star_frame_contract']['origin_model'],'spica-mean-date-iau1976-pm-v2')
        self.assertIn('conditional',result['classification_contract']['en_yong'])
        for b in result['bodies'].values():
            self.assertFalse(b['classification_quality']['validated'])
        self.assertTrue(any('独立近似边界' in w for w in warnings))

    def test_ming_du_boundary_propagates_conditional_warning(self):
        def at_boundary(jd_ut, jd_tt, *args):
            return (spica_mean_longitude(jd_tt)+12.01) % 360
        with patch.object(q, 'ascendant_tropical', at_boundary):
            result,warnings=q.compute((2000,1,1),12,0,30,120)
        self.assertTrue(result['classification_contract']['near_boundary'])
        self.assertTrue(any('度主/恩用难仇为条件结果' in w for w in warnings))
        # Origin-only change propagates to the element-dependent derived rule.
        old=q.mansion_of(q.to_sidereal(230,q.J2000,'legacy-v1'))[2]
        new=q.mansion_of(q.to_sidereal(230,q.J2000,'physical-v2'))[2]
        self.assertNotEqual(q.en_yong_chou_nan(old),q.en_yong_chou_nan(new))

    def test_sun_physical_mean_frame(self):
        r,_=q.compute((2000,1,1),12,0,None,None)
        tt=r['jd_ut']+q.delta_t_seconds(2000)/86400
        t=(tt-q.J2000)/36525
        expected=(q.sun_apparent_longitude(tt)+.00569+.00478*math.sin(math.radians(125.04-1934.136*t)))%360
        self.assertAlmostEqual(r['bodies']['日']['tropical'],expected,places=12)
        legacy,_=q.compute((2000,1,1),12,0,None,None,profile='legacy-v1')
        self.assertEqual(legacy['bodies']['日']['tropical'],q.sun_apparent_longitude(tt))
        self.assertNotIn('classification_quality',legacy['bodies']['日'])

    def test_out_of_range_and_nonfinite(self):
        self.assertFalse(star_frame_contract(2000000)['within_validated_range'])
        for value in (math.nan,math.inf,-math.inf):
            with self.assertRaises(ValueError):spica_mean_longitude(value)

if __name__ == '__main__':unittest.main(verbosity=2)
