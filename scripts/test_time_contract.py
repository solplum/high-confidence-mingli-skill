"""Engineering regressions, not evidence for predictive validity or astronomical goldens."""
import contextlib
import io
import json
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import build_chart as chart
import pai_pan_bazi as bazi

ROOT = Path(__file__).resolve().parent


class TimeContractTests(unittest.TestCase):
    def test_negative_solar_hour_rolls_to_previous_day(self):
        civil = datetime(2005, 12, 24, 0, 5, tzinfo=bazi.BJ)
        value = chart.solar_clock(civil, 102.18, 0)
        self.assertEqual(value.isoformat(), '2005-12-23T22:53:43.200000')
        self.assertTrue(chart.true_solar_time_text(0, 5, 102.18, 0).startswith('22:53'))
        self.assertIsNone(value.tzinfo)

    def test_naive_solar_clock_rejected(self):
        with self.assertRaises(ValueError):
            chart.solar_clock(datetime(2005, 12, 24), 102.18, 0)

    def test_eastward_year_rollover(self):
        civil = datetime(2005, 12, 31, 23, 50, tzinfo=bazi.BJ)
        self.assertEqual(chart.solar_clock(civil, 135, 0).date(), date(2006, 1, 1))

    def test_same_instant_different_offsets(self):
        civil = datetime(2005, 12, 24, 0, 5, tzinfo=bazi.BJ)
        self.assertEqual(chart.solar_clock(civil, 102.18, 2),
                         chart.solar_clock(civil.astimezone(timezone.utc), 102.18, 2))

    def test_lichun_instant_is_not_shifted_by_solar_clock(self):
        instant = bazi.solar_term_beijing(2026, 315) + timedelta(minutes=1)
        clock = instant.replace(tzinfo=None) - timedelta(hours=2)
        civil = bazi.compute(instant.date(), instant.hour, instant.minute, birth_instant=instant)
        solar = bazi.compute(clock.date(), clock.hour, clock.minute, birth_instant=instant)
        for key in ('year', 'month'):
            self.assertEqual(civil['pillars'][key][:2], solar['pillars'][key][:2])
        self.assertEqual(civil['qiyun_text'], solar['qiyun_text'])
        self.assertEqual(solar['birth_dt'], instant)
        self.assertIn('立春前后', solar['warnings'])

    def test_naive_instant_rejected(self):
        with self.assertRaises(ValueError):
            bazi.compute(date(2005, 12, 24), 0, 5, birth_instant=datetime(2005, 12, 24))

    def render(self, *extra):
        output = io.StringIO()
        with patch.object(chart, 'run_ziwei', return_value=('test-only ziwei stub', None)) as ziwei, contextlib.redirect_stdout(output):
            chart.main(['--solar', '2005-12-24', '--hour', '00:05', '--sex', '男',
                        '--lat', '27.4', '--lon', '102.18', *extra])
        return output.getvalue(), ziwei.call_args.args

    def test_dechang_fixture_clock_is_used_not_only_displayed(self):
        out, args = self.render('--time-basis', 'apparent-solar')
        self.assertEqual(args[:5], (2005, 12, 23, 22, 54))
        self.assertIn('2005-12-23 22:54', out)
        self.assertIn('跨公历日期', out)

    def test_default_remains_civil(self):
        _, args = self.render()
        self.assertEqual(args[:5], (2005, 12, 24, 0, 5))

    def test_uncertainty_is_visible(self):
        out, _ = self.render('--uncertainty-minutes', '10')
        self.assertIn('未穷举误差区间', out)

    def test_bazi_warnings_survive_render(self):
        out = io.StringIO()
        with patch.object(chart, 'run_ziwei', return_value=('', None)), contextlib.redirect_stdout(out):
            chart.main(['--solar', '2026-02-04', '--hour', '12:00', '--sex', '男',
                        '--lat', '30', '--lon', '120'])
        self.assertIn('立春前后', out.getvalue())

    def test_invalid_input_rejected(self):
        for extra in (['--lon', 'nan'], ['--lat', '91'], ['--solar', '2026-02-30'],
                      ['--uncertainty-minutes', '-1'], ['--utc-offset', '15']):
            with self.subTest(extra=extra), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.render(*extra)


@unittest.skipUnless((ROOT / 'pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
class ZiweiContractTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(['node', '--import', 'tsx', 'pai_pan.ts', '--solar',
                               '2005-12-24', '--hour', '00:05', '--sex', '男', *args],
                              cwd=ROOT / 'pai_pan_ziwei', capture_output=True, text=True)

    def test_target_year_and_nominal_age_control_decade(self):
        for year, interval in ((2039, '26-35'), (2040, '36-45')):
            result = self.run_cli('--age-year', str(year))
            self.assertEqual(result.returncode, 0, result.stderr)
            current = [line for line in result.stdout.splitlines() if '←当前' in line]
            self.assertEqual(len(current), 1)
            self.assertTrue(current[0].startswith(interval), current)
            self.assertIn('虚岁口径：%d' % (year - 2005 + 1), result.stdout)

    def test_bad_dates_minutes_and_years_rejected(self):
        for extra in (['--solar', '2005-02-30'], ['--hour', '12:99'],
                      ['--age-year', 'bad'], ['--age-year', '2004'], ['--shichen', '子']):
            with self.subTest(extra=extra):
                self.assertEqual(self.run_cli(*extra).returncode, 2)

    def test_corrected_birth_year_does_not_change_age(self):
        result = self.run_cli('--solar', '2004-12-31', '--birth-year', '2005', '--age-year', '2040')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('虚岁口径：36', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
