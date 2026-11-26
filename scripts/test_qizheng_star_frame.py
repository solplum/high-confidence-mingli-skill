"""Synthetic regression and independent SIMBAD/ERFA numeric reference; no private cases."""
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import pai_pan_qizheng as q
from qizheng_star_frame import (
    MANSION_CATALOG,
    boundary_diagnostic,
    calibrated_mansions,
    calibrated_palaces,
    spica_mean_longitude,
    star_frame_contract,
)

ROOT = Path(__file__).resolve().parents[1]


class StarFrameTests(unittest.TestCase):
    def test_catalog_coordinate_conversion_j2000(self):
        # Independent spherical formula for the frozen SIMBAD ICRS direction.
        ra, dec, eps = map(math.radians, (201.298247375, -11.161319472222222, 23.43929111111111))
        x = math.cos(dec) * math.cos(ra)
        y = math.cos(dec) * math.sin(ra) * math.cos(eps) + math.sin(dec) * math.sin(eps)
        expected = math.degrees(math.atan2(y, x)) % 360
        self.assertAlmostEqual(expected, 203.8413578083478, places=10)
        self.assertAlmostEqual(spica_mean_longitude(q.J2000), expected, places=10)
        self.assertGreater(abs(expected - 201.2983), 2.5)

    def test_201_years_independent_erfa_iau2006(self):
        data = json.loads((ROOT / "tests/fixtures/spica_erfa_mean_date.json").read_text())
        self.assertEqual(len(data["rows"]), 201)
        for year, jd, expected in data["rows"]:
            self.assertLess(abs(q.lon_delta(spica_mean_longitude(jd), expected)) * 3600, 1.0, str(year))

    def test_28_mansions_match_simbad_fixture_and_stay_monotonic_1900_to_2100(self):
        fixture = json.loads((ROOT / "tests/fixtures/qizheng/simbad-28-mansions.json").read_text())
        self.assertEqual(len(fixture["stars"]), 28)
        self.assertEqual(len(MANSION_CATALOG), 28)
        j2000_tbl = calibrated_mansions(q.J2000)
        spica0 = fixture["stars"][0]["j2000_ecl_lon_deg"]
        for ref, row in zip(fixture["stars"], j2000_tbl):
            self.assertEqual(row[0], ref["mansion"])
            self.assertEqual(row[3], ref["wx"])
            self.assertEqual(row[4], ref["palace"])
            ref_off = (ref["j2000_ecl_lon_deg"] - spica0) % 360.0
            self.assertLess(abs(q.lon_delta(row[2], ref_off)) * 3600.0, 0.5, ref["mansion"])
        # Verify strict monotonicity & 360-deg partition across 1900..2100
        for jd in (2415020.5, 2433282.5, 2451545.0, 2461041.5, 2488069.5):
            tbl = calibrated_mansions(jd)
            self.assertEqual(tbl[0][2], 0.0)
            widths = [m[5] for m in tbl]
            self.assertTrue(all(w > 1.0 for w in widths), jd)
            self.assertAlmostEqual(sum(widths), 360.0, places=9)
            palaces = calibrated_palaces(tbl)
            self.assertEqual(len(palaces), 12)
            self.assertAlmostEqual(sum(hi - lo for lo, hi in palaces.values()), 360.0, places=9)

    def test_legacy_math_unchanged(self):
        for t in (-1, -0.25, 0, 0.3, 1):
            jd = q.J2000 + t * 36525
            old = 201.2983 + (5028.796195 * t + 1.1054348 * t * t + 0.00007964 * t**3) / 3600
            self.assertEqual(q.spica_ayanamsa(jd), old)
            self.assertEqual(q.spica_ayanamsa(jd, "legacy-v1"), old)
            self.assertEqual(q.to_sidereal(100, jd, "legacy-v1"), (100 - old) % 360)
        with self.assertRaises(ValueError):
            q.spica_ayanamsa(q.J2000, "unknown")

    def test_calibrated_contract_and_legacy_separation(self):
        self.assertEqual(q.MANSIONS[0][2], 0.0)
        self.assertAlmostEqual(q.MANSIONS[1][2], 10.65236, places=4)
        self.assertEqual(q.LEGACY_MANSIONS[1][2], 12.0)
        contract = star_frame_contract(q.J2000)
        self.assertTrue(contract["mansion_boundaries_validated"])
        self.assertEqual(contract["mansion_boundary_model"], "simbad-icrs-28stars-iau1976-pm-v3")
        self.assertIsNotNone(contract["mansion_boundary_error_deg"])
        legacy_contract = star_frame_contract(q.J2000, legacy=True)
        self.assertFalse(legacy_contract["mansion_boundaries_validated"])
        # Same synthetic tropical direction 220°: legacy -> 亢(辰), calibrated -> 亢(辰); at 228°: legacy -> 亢(辰), calibrated -> 氐(卯)
        old = q.to_sidereal(228, q.J2000, "legacy-v1")
        new = q.to_sidereal(228, q.J2000, "calibrated-v3")
        self.assertEqual(q.mansion_of(old, mansions=q.LEGACY_MANSIONS)[0], "亢")
        self.assertEqual(q.mansion_of(new)[0], "氐")
        self.assertEqual(q.palace_of(old, palaces=q.LEGACY_PALACES), "辰")
        self.assertEqual(q.palace_of(new), "卯")

    def test_boundary_screen_wrap_and_calibrated_metadata(self):
        starts = [m[2] for m in q.MANSIONS]
        for lon in (0.0, 0.099, 359.999, starts[1], starts[1] - 0.001):
            self.assertTrue(boundary_diagnostic(lon, starts, validated=True)["near_boundary"])
        far = boundary_diagnostic(5.0, starts, validated=True)
        self.assertEqual(far["status"], "calibrated")
        self.assertTrue(far["validated"])
        result, warnings = q.compute((2000, 1, 1), 12, 0, 30, 120)
        self.assertEqual(result["calculation_profile"], "calibrated-v3")
        self.assertEqual(result["star_frame_contract"]["origin_model"], "spica-mean-date-iau1976-pm-v2")
        self.assertEqual(result["classification_contract"]["mansion_and_palace"], "calibrated-simbad-icrs-epoch-v3")
        for b in result["bodies"].values():
            self.assertTrue(b["classification_quality"]["validated"])
            self.assertIn("palace", b)
        self.assertFalse(any("独立近似边界" in w for w in warnings))

    def test_ming_du_boundary_propagates_warning(self):
        def at_boundary(jd_ut, jd_tt, *args):
            starts = [m[2] for m in calibrated_mansions(jd_tt)]
            return (spica_mean_longitude(jd_tt) + starts[1] + 0.01) % 360.0

        with patch.object(q, "ascendant_tropical", at_boundary):
            result, warnings = q.compute((2000, 1, 1), 12, 0, 30, 120)
        self.assertTrue(result["classification_contract"]["near_boundary"])
        self.assertTrue(any("命度接近校准宿界" in w for w in warnings))

    def test_sun_vsop87_geometric_mean_frame(self):
        r, _ = q.compute((2000, 1, 1), 12, 0, None, None)
        tt = r["jd_tt"]
        self.assertAlmostEqual(r["bodies"]["日"]["tropical"], q.sun_geometric_longitude(tt), places=12)
        self.assertEqual(r["ephemeris_contract"]["sun"], "vsop87-geometric-mean-ecliptic-v3")
        legacy, _ = q.compute((2000, 1, 1), 12, 0, None, None, profile="legacy-v1")
        self.assertEqual(legacy["bodies"]["日"]["tropical"], q.sun_apparent_longitude(tt))
        self.assertNotIn("classification_quality", legacy["bodies"]["日"])

    def test_out_of_range_and_nonfinite(self):
        self.assertFalse(star_frame_contract(2000000)["within_validated_range"])
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                spica_mean_longitude(value)
            with self.assertRaises(ValueError):
                q.sun_geometric_longitude(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
