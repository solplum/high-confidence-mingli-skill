#!/usr/bin/env python3
"""Regression checks for UTC+8 civil-day lunar-month assignment.

HKO sources (Gregorian/Lunar conversion tables, not predictive validation):
https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2033e.txt
https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2034e.txt
https://www.hko.gov.hk/en/gts/time/calendar/text/files/T1984e.txt
https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2014e.txt
"""
import unittest
from datetime import date, timedelta

import pai_pan_bazi as bazi


class LunarCivilDateTests(unittest.TestCase):
    def test_hko_leap_eleven_boundaries_2033_2034(self):
        cases = (
            ((2033, 12, 21), (2033, 11, 30, False)),
            ((2033, 12, 22), (2033, 11, 1, True)),
            ((2034, 1, 19), (2033, 11, 29, True)),
            ((2034, 1, 20), (2033, 12, 1, False)),
            ((2034, 2, 18), (2033, 12, 30, False)),
            ((2034, 2, 19), (2034, 1, 1, False)),
        )
        for solar, lunar in cases:
            with self.subTest(solar=solar):
                self.assertEqual(bazi.solar_to_lunar(*solar), lunar)
                self.assertEqual(bazi.lunar_to_solar(*lunar[:3], leap=lunar[3]), date(*solar))

    def test_term_before_same_day_new_moon_belongs_to_new_month(self):
        term = bazi.solar_term_jd(2034, 300)
        k = bazi._last_new_moon_k_on_or_before_beijing_date(term)
        moon = bazi.new_moon_jde(k)
        self.assertLess(term, moon)
        self.assertEqual(bazi.jd_tt_to_beijing(term).date(), date(2034, 1, 20))
        self.assertEqual(bazi.jd_tt_to_beijing(moon).date(), date(2034, 1, 20))
        leap_months = [m for m in bazi.lunar_months_between_dongzhi(2033) if m['leap']]
        self.assertEqual([(m['year'], m['month'], m['start']) for m in leap_months],
                         [(2033, 11, date(2033, 12, 22))])

    def test_hko_solstice_before_same_day_new_moon_anchors_month_eleven(self):
        for year in (1984, 2014):
            with self.subTest(year=year):
                term = bazi.solar_term_jd(year, 270)
                k = bazi._last_new_moon_k_on_or_before_beijing_date(term)
                self.assertLess(term, bazi.new_moon_jde(k))
                self.assertEqual(bazi.jd_tt_to_beijing(term).date(), date(year, 12, 22))
                self.assertEqual(bazi.solar_to_lunar(year, 12, 22), (year, 11, 1, False))
                self.assertEqual(bazi.lunar_to_solar(year, 11, 1), date(year, 12, 22))

    def test_span_structure_1901_through_2100(self):
        # Internal consistency, not an independent accuracy measurement.
        for year in range(1901, 2101):
            with self.subTest(year=year):
                months = bazi.lunar_months_between_dongzhi(year)
                self.assertIn(len(months), (12, 13))
                self.assertEqual((months[0]['month'], months[0]['leap']), (11, False))
                self.assertEqual(sum(m['leap'] for m in months), len(months) - 12)
                next_start = bazi.lunar_months_between_dongzhi(year + 1)[0]['start']
                for i, month in enumerate(months):
                    self.assertIn(month['days'], (29, 30))
                    expected_end = months[i + 1]['start'] if i + 1 < len(months) else next_start
                    self.assertEqual(month['start'] + timedelta(days=month['days']), expected_end)


if __name__ == '__main__':
    unittest.main()
