"""Fixed synthetic dates and coordinates for engineering regressions, not evidence for predictive validity or astronomical goldens."""
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
        # +08 to 90E is exactly -120 minutes when the EOT input is zero.
        civil = datetime(1986, 1, 4, 0, 10, tzinfo=bazi.BJ)
        value = chart.solar_clock(civil, 90, 0)
        self.assertEqual(value.isoformat(), '1986-01-03T22:10:00')
        self.assertTrue(chart.true_solar_time_text(0, 10, 90, 0).startswith('22:10'))
        self.assertIsNone(value.tzinfo)

    def test_naive_solar_clock_rejected(self):
        with self.assertRaises(ValueError):
            chart.solar_clock(datetime(1986, 1, 4), 90, 0)

    def test_eastward_year_rollover(self):
        civil = datetime(1986, 12, 31, 23, 50, tzinfo=bazi.BJ)
        self.assertEqual(chart.solar_clock(civil, 135, 0).date(), date(1987, 1, 1))

    def test_same_instant_different_offsets(self):
        civil = datetime(1986, 1, 4, 0, 10, tzinfo=bazi.BJ)
        self.assertEqual(chart.solar_clock(civil, 90, 2),
                         chart.solar_clock(civil.astimezone(timezone.utc), 90, 2))

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
            bazi.compute(date(1986, 1, 4), 0, 10, birth_instant=datetime(1986, 1, 4))

    def render(self, *extra):
        output = io.StringIO()
        with patch.object(chart, 'run_ziwei', return_value=('', None)) as ziwei, contextlib.redirect_stdout(output):
            chart.main(['--solar', '1986-01-04', '--hour', '00:10', '--sex', '男',
                        '--lat', '30', '--lon', '90', *extra])
        return output.getvalue(), ziwei.call_args.args

    def test_synthetic_apparent_clock_is_used_not_only_displayed(self):
        out, args = self.render('--time-basis', 'apparent-solar')
        # JD 2446434.173611111 gives EOT -4.533243min in the fixed formula;
        # 22:10 mean solar becomes 22:05:28 apparent, floored to minute 05.
        self.assertEqual(args[:5], (1986, 1, 3, 22, 5))
        self.assertIn('1986-01-03 22:05', out)
        self.assertIn('跨公历日期', out)

    def test_default_remains_civil(self):
        _, args = self.render()
        self.assertEqual(args[:5], (1986, 1, 4, 0, 10))

    def test_uncertainty_is_visible(self):
        out, _ = self.render('--uncertainty-minutes', '10')
        self.assertIn('未穷举误差区间', out)

    def test_dayun_rounded_month_windows_preserve_the_existing_schedule(self):
        args = ('--solar', '1982-12-14', '--hour', '12:00')
        data, _ = self.render(*args, '--format', 'json')
        natal = json.loads(data)['bazi']
        panel = natal['dayun_age_windows']
        self.assertEqual((natal['qiyun_years'], natal['qiyun_months']), (7, 7))
        self.assertEqual(panel['basis'], 'rounded_engine_age_months')
        self.assertFalse(panel['birth_time_is_reference'])
        rows = panel['windows']
        self.assertEqual([(r['sequence'], r['pillar']) for r in rows],
                         [(seq, pillar) for seq, _, pillar in natal['dayun_rows']])
        self.assertEqual([(r['start_months_inclusive'], r['end_months_exclusive']) for r in rows[:3]],
                         [(0, 91), (91, 211), (211, 331)])
        self.assertEqual(natal['dayun_rows'][2][1], '17-26岁')

        def selected(age_in_months):
            return next(r['pillar'] for r in rows
                        if r['start_months_inclusive'] <= age_in_months < r['end_months_exclusive'])

        self.assertEqual((selected(206), selected(211)), ('癸丑', '甲寅'))
        output, _ = self.render(*args)
        self.assertIn('整岁索引', output)
        self.assertIn('折月模型约从7岁7个月开始', output)
        first_luck = '| 1 | [7 岁 7 个月, 17 岁 7 个月) | [91, 211) | 癸丑 | 7-16岁 |'
        self.assertIn(first_luck, output)
        reference = bazi.compute(date(1982, 12, 14), shichen='午')
        self.assertTrue(reference['dayun_age_windows']['birth_time_is_reference'])
        reference_text = bazi.format_report(reference)
        self.assertIn('起运年龄基于参考时刻', reference_text)
        self.assertIn(first_luck, reference_text)

    def test_bazi_text_keeps_both_luck_windows_for_the_same_birth_candidate(self):
        args = ['--solar', '1982-12-14', '--hour', '14:58', '--sex', '男', '--analysis-year', '2026',
                '--uncertainty-minutes', '1', '--enumerate-scenarios']
        output, _ = self.render(*args)
        candidate_text, center_text = output.split('## 大运表', 1)
        self.assertIn('四柱见证：candidate-1 @ UTC 1982-12-14T06:57:00+00:00', candidate_text)
        self.assertIn('四柱见证：candidate-1 @ UTC 1982-12-14T06:58:41.878101+00:00', candidate_text)
        self.assertIn('| 4 | [37 岁 7 个月, 47 岁 7 个月) | [451, 571) | 丙辰 |', candidate_text)
        self.assertIn('| 4 | [37 岁 6 个月, 47 岁 6 个月) | [450, 570) | 丙辰 |', candidate_text)
        self.assertIn('下表按中心时刻计算', center_text)
        self.assertIn('| 3 | [27 岁 7 个月, 37 岁 7 个月) | [331, 451) | 乙卯 | 27-36岁 |', center_text)
        self.assertIn('| 4 | [37 岁 7 个月, 47 岁 7 个月) | [451, 571) | 丙辰 | 37-46岁 |', center_text)

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
                               '1986-01-04', '--hour', '00:10', '--sex', '男', *args],
                              cwd=ROOT / 'pai_pan_ziwei', capture_output=True, text=True)

    def test_target_year_and_nominal_age_control_decade(self):
        for year, interval in ((2020, '26-35'), (2021, '36-45')):
            with self.subTest(year=year):
                result = self.run_cli('--age-year', str(year))
                self.assertEqual(result.returncode, 0, result.stderr)
                selected = [line for line in result.stdout.splitlines() if '←目标年所在' in line]
                self.assertEqual(len(selected), 1)
                self.assertTrue(selected[0].startswith(interval), selected)
                self.assertIn(f'{year} 年所处大限', result.stdout)
                self.assertIn(f'公历目标年 {year} 年', result.stdout)
                self.assertIn('虚岁口径：%d' % (year - 1986 + 1), result.stdout)
                self.assertNotIn('当前大限', result.stdout)
                self.assertNotIn('←当前', result.stdout)

    def test_shared_report_identifies_historical_or_uncovered_stage(self):
        for year, palace in ((2020, '田宅'), (2021, '官禄'), (1980, None), (2105, None)):
            with self.subTest(year=year):
                result = subprocess.run(
                    [sys.executable, '-B', str(ROOT / 'build_chart.py'), '--solar', '1980-02-17',
                     '--hour', '10:00', '--sex', '男', '--analysis-year', str(year), '--format', 'text'],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'公历目标年 {year} 年', result.stdout)
                self.assertNotIn('当前大限', result.stdout)
                self.assertNotIn('←当前', result.stdout)
                if palace is None:
                    self.assertIn(f'{year} 年未落入已列大限', result.stdout)
                    self.assertNotIn('←目标年所在', result.stdout)
                    self.assertIn('32-41　田宅(子)', result.stdout)
                else:
                    self.assertRegex(result.stdout, rf'【{palace}】[^\n]+{year} 年所处大限')
                    self.assertRegex(result.stdout, rf'{palace}\([^\n]+\) ←目标年所在')

    def test_bad_dates_minutes_and_years_rejected(self):
        for extra in (['--solar', '1986-02-30'], ['--hour', '12:99'],
                      ['--age-year', 'bad'], ['--age-year', '1985'], ['--shichen', '子']):
            with self.subTest(extra=extra):
                self.assertEqual(self.run_cli(*extra).returncode, 2)

    def test_corrected_birth_year_does_not_change_age(self):
        result = self.run_cli('--solar', '1985-12-31', '--birth-year', '1986', '--age-year', '2021')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('虚岁口径：36', result.stdout)

    def test_text_stage_windows_use_civil_birth_year_even_when_chart_clock_crosses_year(self):
        command = [sys.executable, '-B', str(ROOT / 'build_chart.py'), '--solar', '2000-01-01',
                   '--hour', '00:10', '--sex', '男', '--utc-offset', '8', '--time-basis', 'mean-solar',
                   '--lon', '105', '--analysis-year', '2026']
        snapshot = json.loads(subprocess.check_output(command + ['--format', 'json'], text=True))
        self.assertTrue(snapshot['time']['chart_clock'].startswith('1999-12-31'))
        text = subprocess.check_output(command, text=True)
        self.assertIn('公历年度窗以原民用出生年 2000 为准', text)
        rows = snapshot['ziwei']['life_reading']['stage_relationship']['stages']
        self.assertEqual(len(rows), 12)
        printed_windows = [line for line in text.splitlines() if '｜[' in line and '-01-01)' in line]
        expected_windows = []
        for row in rows:
            legacy = row['legacy_stage']
            window = legacy['window']
            marker = ' ←目标年所在' if legacy['current'] else ''
            expected_windows.append(marker + '｜[' + window['start_inclusive'] + ', ' + window['end_exclusive'] + ')')
        self.assertEqual(len(printed_windows), len(expected_windows))
        for printed, expected in zip(printed_windows, expected_windows):
            self.assertTrue(printed.endswith(expected), printed)
        uncertain = subprocess.check_output(command + ['--uncertainty-minutes', '1'], text=True)
        self.assertIn('下表按中心时刻排出。实际出生候选的大限须分别核对。', uncertain)


if __name__ == '__main__':
    unittest.main(verbosity=2)
