"""Regression coverage for strict numeric inputs and datetime range guards."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pai_pan_qizheng as engine
import qizheng_sensitivity as sensitivity


class NumericGuards(unittest.TestCase):
    def test_invalid_numeric_inputs_fail_before_engine(self):
        invalid = (None, True, False, '0', [], {}, float('nan'),
                   float('inf'), -float('inf'), 10 ** 1000, -(10 ** 1000))
        for field in ('minutes', 'lat', 'lon', 'dut1_seconds'):
            for value in invalid:
                with self.subTest(field=field, value_type=type(value).__name__):
                    args = dict(civil=datetime(2000, 1, 1, tzinfo=timezone.utc),
                                minutes=0, lat=35, lon=120, dut1_seconds=0)
                    args[field] = value
                    with patch.object(engine, 'compute') as compute:
                        with self.assertRaises(ValueError):
                            sensitivity.compare(**args)
                        compute.assert_not_called()

    def test_core_dut1_rejects_invalid_numbers(self):
        for value in (None, True, False, '0', [], {}, float('nan'), float('inf'),
                      -float('inf'), 10 ** 1000, -10 ** 1000, .90001, -.90001):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    engine.compute((2000, 1, 1), 12, 0, 35, 120, dut1_seconds=value)

    def test_valid_dut1_boundaries(self):
        for value in (-.9, 0, .9):
            result = sensitivity.compare(datetime(2000, 1, 1, tzinfo=timezone.utc),
                                         0, 35, 120, dut1_seconds=value)
            self.assertEqual(1, result['method']['evaluation_count'])

    def test_malformed_and_extreme_datetimes_are_value_errors(self):
        dates = (None, '2000-01-01', 0, datetime(2000, 1, 1),
                 datetime.min.replace(tzinfo=timezone.utc),
                 datetime.max.replace(tzinfo=timezone.utc),
                 datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
                 datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))))
        for civil in dates:
            with self.subTest(civil=str(civil)):
                with patch.object(engine, 'compute') as compute:
                    with self.assertRaises(ValueError):
                        sensitivity.compare(civil, 120, 35, 120)
                    compute.assert_not_called()

    def test_supported_years_are_checked_in_utc(self):
        invalid = (datetime(1901, 1, 1, tzinfo=timezone(timedelta(hours=1))),
                   datetime(2099, 12, 31, 23, 59, tzinfo=timezone(timedelta(hours=-1))))
        for civil in invalid:
            with self.assertRaises(ValueError):
                sensitivity.compare(civil, 0, 35, 120)
        for civil in (datetime(1901, 1, 1, tzinfo=timezone.utc),
                      datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc)):
            with self.assertRaises(ValueError):
                sensitivity.compare(civil, 120, 35, 120)
        # Local 1900 can still be an accepted UTC 1901 instant.
        civil = datetime(1900, 12, 31, 23, tzinfo=timezone(timedelta(hours=-1)))
        result = sensitivity.compare(civil, 0, 35, 120)
        self.assertEqual('1901-01-01T00:00:00+00:00', result['interval']['center_utc'])


if __name__ == '__main__':
    unittest.main()
