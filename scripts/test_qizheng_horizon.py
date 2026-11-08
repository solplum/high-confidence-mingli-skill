"""Physical geometry invariants and optional independent Swiss oracle.

No ephemeris/data/software is vendored. To run optional tests install pyswisseph
separately with its own licence, or use an already available installation.
"""
import math
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pai_pan_qizheng as q


def height(lon, theta, eps, lat):
    # Independent RA/declination transformation instead of intersection algebra.
    lam, ob, phi, st = map(math.radians, (lon, eps, lat, theta))
    ra = math.atan2(math.sin(lam) * math.cos(ob), math.cos(lam))
    dec = math.asin(math.sin(lam) * math.sin(ob))
    return math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(st - ra)


class HorizonTests(unittest.TestCase):
    def test_horizon_and_positive_rising_derivative_global_grid(self):
        for year in (1900, 2000, 2024, 2100):
            jd = q.jd_from_utc(datetime(year, 6, 21, tzinfo=timezone.utc))
            tt = jd + q.delta_t_seconds(year) / 86400
            eps = q.mean_obliquity_deg(tt)
            for lat in (-89.999999, -89, -80, -66.56, -45, 0, 45, 66.56, 80, 89, 89.999999):
                for lon in (-180, -120, -30, 0, 60, 120, 180):
                    for hours in (0, 6, 12, 18):
                        t = jd + hours / 24
                        asc = q.ascendant_tropical(t, tt, lat, lon)
                        self.assertIsNotNone(asc, (year, lat, lon, hours))
                        theta = (q.gmst_degrees(t) + lon) % 360
                        self.assertAlmostEqual(height(asc, theta, eps, lat), 0, delta=1e-14)
                        # Hold the star fixed and rotate the local meridian forward.
                        derivative = height(asc, theta + .001, eps, lat) - height(asc, theta - .001, eps, lat)
                        self.assertGreater(derivative, 0, (year, lat, lon, hours))

    def test_exact_poles_and_degenerate_geometry(self):
        for lat in (-90, 90):
            self.assertIsNone(q.ascendant_tropical(q.J2000, q.J2000, lat, 0))
            result, warnings = q.compute((2024, 6, 21), 12, 0, lat, 0)
            self.assertIsNone(result['ming_du'])
            self.assertIsNone(result['en_yong'])
            self.assertTrue(math.isfinite(result['day_night']['solar_altitude_deg']))
        # At the polar-circle latitude one orientation makes planes coincide.
        with patch.object(q, 'gmst_degrees', return_value=270):
            self.assertIsNone(q.ascendant_tropical(q.J2000, q.J2000, 90-q.mean_obliquity_deg(q.J2000), 0))

    def test_eot_never_changes_sidereal_geometry(self):
        args = (q.J2000, q.J2000, 31.23, 121.47)
        self.assertEqual(q.ascendant_tropical(*args, -20), q.ascendant_tropical(*args, 20))

    def test_timezone_and_dateline_invariance(self):
        instant = datetime(2024, 6, 21, 23, 30, tzinfo=timezone.utc)
        for lon in (-180, -120, 0, 120, 180):
            outputs = [q.compute((2024,6,21), 0, 0, 35, lon,
                       birth_instant=instant.astimezone(timezone(timedelta(hours=offset))))[0]
                       for offset in (-12, -8, 0, 5.5, 8, 14)]
            self.assertTrue(all(r == outputs[0] for r in outputs))
        west = q.compute((2024,6,21),0,0,35,-180,birth_instant=instant)[0]
        east = q.compute((2024,6,21),0,0,35,180,birth_instant=instant)[0]
        self.assertAlmostEqual(west['ming_du']['tropical'],east['ming_du']['tropical'],places=10)
        self.assertEqual(west['day_night'],east['day_night'])

    def test_daylight_utc_wrap_and_polar_seasons(self):
        for lat, month, expected in ((80,6,'昼生'),(80,12,'夜生'),(-80,6,'夜生'),(-80,12,'昼生')):
            for hour in (0,6,12,18):
                r,_ = q.compute((2024,month,21), hour, 0, lat, 120)
                self.assertEqual(r['day_night']['type'], expected)
        r,_ = q.compute((2024,6,21), 9, 0, 0, 120,
                        birth_instant=datetime(2024,6,20,22,tzinfo=timezone.utc))
        self.assertEqual(r['day_night']['type'],'昼生')
        old,_ = q.compute((2024,6,21),9,0,0,120,profile='legacy-v1',
                          birth_instant=datetime(2024,6,20,22,tzinfo=timezone.utc))
        self.assertEqual(old['day_night']['type'],'夜生')

    def test_dut1_contract_and_invalid_inputs(self):
        a,_=q.compute((2024,1,1),0,0,35,120)
        b,_=q.compute((2024,1,1),0,0,35,120,dut1_seconds=.8)
        self.assertAlmostEqual((b['jd_ut']-a['jd_ut'])*86400,.8,delta=.0001)
        self.assertNotEqual(a['ming_du'],b['ming_du'])
        for lat,lon in ((91,0),(0,181),(float('nan'),0),(0,float('inf'))):
            with self.assertRaises(ValueError): q.compute((2024,1,1),0,0,lat,lon)
        with self.assertRaises(ValueError): q.compute((2024,1,1),0,0,0,0,profile='guess')
        with self.assertRaises(ValueError): q.compute((2024,1,1),0,0,0,0,dut1_seconds=2)

    def test_legacy_profile_frozen_samples(self):
        for date, hour, lat, lon, expected in (
                ((1990,5,15),14,31.23,121.47,358.15751197140156),
                ((2000,1,1),20,39.9,116.4,315.2209920409449)):
            result, _ = q.compute(date,hour,0,lat,lon,profile='legacy-v1')
            self.assertAlmostEqual(result['ming_du']['tropical'],expected,places=10)
            self.assertEqual(result['ephemeris_contract']['planets'],'legacy-v1')
            self.assertEqual(result['ephemeris_contract']['moon'],'legacy-v1')

    def test_legacy_opposition_nonpolar(self):
        for lat in (-45,0,45):
            old=q.legacy_ascendant_tropical(q.J2000,q.J2000,lat,120,0)
            new=q.ascendant_tropical(q.J2000,q.J2000,lat,120)
            self.assertAlmostEqual((new-old)%360,180)


try:
    import swisseph as swe
except ImportError:
    swe = None


@unittest.skipUnless(swe, 'optional external Swiss Ephemeris not installed')
class IndependentSwissTests(unittest.TestCase):
    def test_mean_frame_ascendant_against_houses_armc(self):
        # Supply identical mean ARMC/obliquity, isolating geometric convention.
        # At polar latitudes Swiss may use a house convention rather than the
        # positive-rising intersection, so physical invariant tests cover those.
        for year in (1900,1950,2000,2024,2100):
            jd=q.jd_from_utc(datetime(year,3,20,12,tzinfo=timezone.utc))
            tt=jd+q.delta_t_seconds(year)/86400
            for lat in (-60,-30,0,30,60):
                for lon in (-180,-90,0,90,180):
                    expected=swe.houses_armc((q.gmst_degrees(jd)+lon)%360,lat,q.mean_obliquity_deg(tt),b'E')[1][0]
                    actual=q.ascendant_tropical(jd,tt,lat,lon)
                    self.assertLess(abs((actual-expected+180)%360-180),1e-9)

    def test_solar_altitude_against_independent_moshier(self):
        # Swiss Moshier mean-equator geometric true Sun; no data files.
        flags=swe.FLG_MOSEPH | swe.FLG_EQUATORIAL | swe.FLG_NONUT | swe.FLG_TRUEPOS
        for year in (1900,2000,2024,2100):
            for month in (3,6,9,12):
                jd=q.jd_from_utc(datetime(year,month,21,12,tzinfo=timezone.utc))
                tt=jd+q.delta_t_seconds(year)/86400
                equ, returned=swe.calc(tt,swe.SUN,flags)
                self.assertTrue(returned & swe.FLG_MOSEPH)
                for lat in (-89.9,-60,0,60,89.9):
                    for lon in (-180,-90,0,90,180):
                        phi,dec,h=map(math.radians,(lat,equ[1],q.gmst_degrees(jd)+lon-equ[0]))
                        expected=math.degrees(math.asin(math.sin(phi)*math.sin(dec)+math.cos(phi)*math.cos(dec)*math.cos(h)))
                        self.assertLess(abs(q.solar_altitude_deg(jd,tt,lat,lon)-expected),.03)

if __name__ == '__main__': unittest.main(verbosity=2)
