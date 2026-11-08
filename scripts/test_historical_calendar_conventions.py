#!/usr/bin/env python3
"""Independent DE441 regression fixtures, not HKO historical-day overrides.

Astrodienst official sepl_18.se1/semo_18.se1 (DE441, 2026-05-26),
Swiss Ephemeris 2.10.03, apparent geocentric ecliptic longitude of date.
Numerically solved in TT. No Swiss Ephemeris runtime dependency.
See docs/historical-calendar-audit.md for policy, method and uncertainty.
"""
import unittest
from datetime import date
import pai_pan_bazi as b

MOONS = (('1914-11-18', 2420454.1680400483, '1914-11-18'), ('1916-02-04', 2420897.1705252575, '1916-02-04'), ('1920-11-11', 2422639.170259556, '1920-11-11'))
TERMS = ((1912, 240, 2419729.158592021, '1912-11-22'), (1913, 180, 2420034.161781585, '1913-09-23'), (1917, 255, 2421570.1675890293, '1917-12-08'), (1927, 165, 2425132.1707166024, '1927-09-09'), (1928, 90, 2425419.171370798, '1928-06-22'), (1979, 300, 2443894.1671829317, '1979-01-20'))


class IndependentHistoricalCalendarTests(unittest.TestCase):
    def test_historical_conjunctions_preserve_fixed_offset_policy(self):
        for iso, jde, expected in MOONS:
            with self.subTest(date=iso):
                k = b._k_near(jde)
                self.assertLess(abs(b.new_moon_jde(k) - jde) * 86400, 20)
                self.assertEqual(b.jd_tt_to_beijing(b.new_moon_jde(k)).date(),
                                 date.fromisoformat(expected))

    def test_six_hko_disagreements_against_independent_ephemeris(self):
        # Five seconds is a regression tolerance, not a claimed global bound.
        for year, longitude, jde, expected in TERMS:
            with self.subTest(year=year, longitude=longitude):
                actual = b.solar_term_jd(year, longitude)
                self.assertLess(abs(actual - jde) * 86400, 5)
                self.assertEqual(b.jd_tt_to_beijing(actual).date(),
                                 date.fromisoformat(expected))

    def test_1916_fixed_offset_calendar_is_not_historical_table(self):
        # HKO explicitly explains why its historical table starts Feb 3.
        self.assertEqual(b.solar_to_lunar(1916, 2, 4), (1916, 1, 1, False))
        self.assertEqual(b.lunar_to_solar(1916, 1, 1), date(1916, 2, 4))

    def test_2057_conjunction_remains_midnight_sensitive(self):
        # Both estimates lie close to midnight. Deliberately do not certify
        # either civil date, since future Delta T / UTC are not known.
        jde = 2472635.1679791072
        self.assertLess(abs(b.new_moon_jde(714) - jde) * 86400, 20)
        for event in (jde, b.new_moon_jde(714)):
            dt = b.jd_tt_to_beijing(event)
            seconds = dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6
            self.assertLess(min(seconds, 86400 - seconds), 120)

    def test_policy_and_2057_warning_do_not_override_dates(self):
        target = date(2057, 9, 28)
        policy = b.lunar_calendar_policy(target)
        event = policy["conjunctions"][0]
        self.assertEqual(event["lunation_index"], 714)
        self.assertEqual(event["civil_date"], "2057-09-28")
        self.assertTrue(event["near_midnight"])
        self.assertFalse(event["utc_conversion_verified"])
        self.assertEqual(event["civil_timescale"], "estimated_UT1+08:00")
        self.assertFalse(policy["historical_calendar_reconstruction"])
        self.assertIsNone(policy["historical_transition_rules"])
        self.assertFalse(policy["date_override_applied"])
        self.assertFalse(policy["trigger_is_accuracy_bound"])
        before = b.solar_to_lunar(2057, 9, 28)
        result = b.compute(target, 12, 0)
        self.assertEqual(b.solar_to_lunar(2057, 9, 28), before)
        self.assertEqual(result["lunar_text"], b.format_lunar(*before))
        self.assertEqual(result["calendar_policy"]["lunar_display_source"], "computed")
        self.assertEqual({k: v for k, v in result["calendar_policy"].items()
                          if k != "lunar_display_source"}, policy)
        self.assertTrue(any("不代表已判错" in w for w in result["warnings"]))
        self.assertTrue(any("未来 UTC 闰秒" in w for w in result["warnings"]))

    def test_month_end_and_whole_month_expose_relevant_conjunction(self):
        # The uncertain boundary affects both neighboring months, not just
        # a birth within two minutes of the astronomical conjunction.
        for target, role in [(date(2057,9,27), "next_month_start"),
                             (date(2057,10,10), "month_start")]:
            with self.subTest(target=target):
                events = b.lunar_calendar_policy(target)["conjunctions"]
                risk = [e for e in events if e["lunation_index"] == 714]
                self.assertEqual(len(risk), 1)
                self.assertEqual(risk[0]["role"], role)
                self.assertTrue(risk[0]["near_midnight"])

    def test_known_utc_and_non_risk_month(self):
        policy = b.lunar_calendar_policy(date(2026,2,20))
        for event in policy["conjunctions"]:
            self.assertEqual(event["civil_timescale"], "UTC+08:00")
            self.assertTrue(event["utc_conversion_verified"])
            self.assertFalse(event["near_midnight"])
        result = b.compute(date(2026,2,20),12,0)
        self.assertFalse(any("农历月界朔" in w for w in result["warnings"]))

    def test_policy_tracks_chart_date_not_birth_instant_or_custom_display(self):
        from datetime import datetime
        result = b.compute(date(1916,2,4), 0, 0, lunar_display="provided display",
                           birth_instant=datetime(1916,2,3,23,0,tzinfo=b.BJ))
        self.assertEqual(result["calendar_policy"]["chart_clock_date"], "1916-02-04")
        self.assertEqual(result["lunar_text"], "provided display")
        self.assertEqual(result["calendar_policy"]["lunar_display_source"], "caller_provided")
        self.assertFalse(result["calendar_policy"]["historical_calendar_reconstruction"])

    def test_month_brackets_match_unchanged_calendar_across_1901_2100(self):
        from datetime import timedelta
        for year in range(1901, 2101):
            for month in b.lunar_months_between_dongzhi(year):
                for offset in (0, month["days"] // 2, month["days"] - 1):
                    target = month["start"] + timedelta(days=offset)
                    with self.subTest(target=target):
                        start, end = b.lunar_calendar_policy(target)["conjunctions"]
                        self.assertEqual(start["jd_tt"], month["shuo_jd"])
                        self.assertEqual(start["civil_date"], month["start"].isoformat())
                        self.assertEqual(end["civil_date"],
                                         (month["start"] + timedelta(days=month["days"])).isoformat())

    def test_combined_json_metadata_and_warning_are_exposed(self):
        import json
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent
        output = subprocess.check_output([sys.executable, str(root / "build_chart.py"),
            "--solar", "2057-09-28", "--hour", "12:00", "--sex", "男",
            "--lat", "22.3", "--lon", "114.2", "--analysis-year", "2057",
            "--format", "json"], text=True)
        result = json.loads(output)
        self.assertEqual(result["schema_version"], 1)
        self.assertFalse(result["bazi"]["calendar_policy"]["date_override_applied"])
        self.assertTrue(any("不代表已判错" in w for w in result["warnings"]))

    def test_warning_trigger_is_inclusive_and_not_rounded_to_minutes(self):
        from unittest.mock import patch
        original = b.jd_tt_to_beijing
        for microsecond, expected in ((0, True), (1, False)):
            def converted(jde):
                return original(jde).replace(hour=0, minute=2, second=0,
                                             microsecond=microsecond)
            with patch.object(b, "jd_tt_to_beijing", side_effect=converted):
                for event in b.lunar_calendar_policy(date(2026,2,20))["conjunctions"]:
                    self.assertEqual(event["near_midnight"], expected)


if __name__ == '__main__':
    unittest.main()
