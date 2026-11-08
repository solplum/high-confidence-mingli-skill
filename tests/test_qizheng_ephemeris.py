"""Offline independent geometric reference, public synthetic dates only."""
import json
import hashlib
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pai_pan_qizheng as q

FIXTURE = Path(__file__).parent / 'fixtures/qizheng/geometric-vectors.json'


def mean_date_longitude(jd, xyz):
    """ICRF J2000 ecliptic -> mean equinox/ecliptic of date (IAU 1976).

    Independent reference-frame adapter (Meeus AA ch.21/22). ICRF/FK5 bias
    and modern precession differences are sub-arcsecond over this grid and
    immaterial to the explicit 0.1–0.25 degree low-precision budgets.
    """
    x, y, z = xyz
    eps0 = math.radians(84381.448/3600)
    y, z = y*math.cos(eps0)-z*math.sin(eps0), y*math.sin(eps0)+z*math.cos(eps0)
    ra, dec = math.atan2(y,x), math.atan2(z,math.hypot(x,y))
    t=(jd-2451545.0)/36525
    rad=lambda arcsec:math.radians(arcsec/3600)
    zeta=rad(2306.2181*t+0.30188*t*t+0.017998*t**3)
    zz=rad(2306.2181*t+1.09468*t*t+0.018203*t**3)
    theta=rad(2004.3109*t-0.42665*t*t-0.041833*t**3)
    a=math.cos(dec)*math.sin(ra+zeta)
    b=math.cos(theta)*math.cos(dec)*math.cos(ra+zeta)-math.sin(theta)*math.sin(dec)
    c=math.sin(theta)*math.cos(dec)*math.cos(ra+zeta)+math.cos(theta)*math.sin(dec)
    ra,dec=math.atan2(a,b)+zz,math.asin(c)
    x,y,z=math.cos(dec)*math.cos(ra),math.cos(dec)*math.sin(ra),math.sin(dec)
    eps=rad(84381.448-46.8150*t-0.00059*t*t+0.001813*t**3)
    return math.degrees(math.atan2(y*math.cos(eps)+z*math.sin(eps),x))%360


def residual_summary():
    data=json.loads(FIXTURE.read_text())
    result={}
    for name,body in data['bodies'].items():
        errors=[]
        for jd,*xyz in body['vectors']:
            actual=q.moon_longitude(jd) if name=='moon' else q.planet_longitude_tt(name,jd)
            errors.append(abs(q.lon_delta(actual,mean_date_longitude(jd,xyz))))
        result[name]={'n':len(errors),'max_deg':max(errors),'rms_deg':math.sqrt(sum(e*e for e in errors)/len(errors))}
    return result


class IndependentEphemerisTests(unittest.TestCase):
    def test_geometric_grid(self):
        # Fixed prospective acceptance budgets, not reference-derived rounding.
        # Sample pass is not an all-date bound and not astrological validation.
        budgets={'mercury':0.1,'venus':0.1,'mars':0.15,'jupiter':0.15,'saturn':0.25,'moon':0.05}
        for name,result in residual_summary().items():
            with self.subTest(body=name):
                self.assertEqual(result['n'],404)
                self.assertLess(result['max_deg'],budgets[name])

    def test_reference_provenance(self):
        data=json.loads(FIXTURE.read_text())
        for name,body in data['bodies'].items():
            raw=FIXTURE.with_name(name+'-horizons.txt').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),body['sha256'])
            self.assertIn('https://ssd.jpl.nasa.gov/api/horizons.api?',body['request_url'])
            self.assertIn(b'$$SOE',raw)
            self.assertEqual(len(body['vectors']),404)

    def test_frame_adapter_j2000_identity(self):
        for xyz in ((1,0,0),(0,1,0),(-1,0,0),(1,-1,0.5)):
            lon=math.degrees(math.atan2(xyz[1],xyz[0]))%360
            self.assertAlmostEqual(q.lon_delta(mean_date_longitude(2451545,xyz),lon),0,places=10)

    def test_wraparound(self):
        self.assertAlmostEqual(q.lon_delta(0.01,359.99),0.02)

    def test_invalid_model_and_time(self):
        with self.assertRaises(ValueError): q.planet_longitude('jupiter',2451545,model='typo')
        with self.assertRaises(ValueError): q.planet_longitude_tt('jupiter',float('nan'))
        with self.assertRaises(ValueError): q.moon_longitude(2451545,model='typo')
        with self.assertRaises(ValueError): q.moon_longitude(float('inf'))

    def test_legacy_replay(self):
        # Frozen from base c49e6a5, not corrected-model reference values.
        self.assertAlmostEqual(q.planet_longitude('jupiter',2451545,model='legacy-v1'),25.43595904129409,places=9)
        self.assertAlmostEqual(q.moon_longitude(2451545,model='legacy-v1'),223.31977577369756,places=9)


if __name__=='__main__':
    print(json.dumps(residual_summary(),indent=2))
    unittest.main()
