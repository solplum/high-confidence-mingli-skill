"""BaZi query intervals use the native term and civil-day boundaries."""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import bazi_core_reading as core
import bazi_period_facts as periods
import bazi_qiong_xin_zi as qiong
import pai_pan_bazi as engine


def _pillars(result):
    return [{fact['layer']: fact['pillar'] for fact in segment['facts']}
            for segment in result['segments']]


class BaziPeriodFactsTests(unittest.TestCase):
    def require_zone(self, name):
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(name)
        except (ImportError, KeyError):
            self.skipTest('IANA timezone data unavailable: ' + name)

    def test_november_month_cli_splits_at_li_dong_and_keeps_year(self):
        result = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'),
            '--start', '2026-11-01T00:00+08:00', '--end', '2026-12-01T00:00+08:00',
            '--layer', 'month',
        ], text=True))
        term = engine.solar_term_beijing(2026, 225).isoformat()
        left, right = result['segments']
        self.assertEqual(result['time_basis'], 'civil_fixed_offset')
        self.assertEqual(result['interval_semantics'], 'start_inclusive_end_exclusive')
        self.assertEqual(left['end'], term)
        self.assertEqual(right['start'], term)
        self.assertEqual(result['boundaries'], [dict(at=term, reasons=[
            dict(kind='jie', name='立冬', time_bj=term),
        ])])
        self.assertEqual(_pillars(result), [dict(year='丙午', month='戊戌'),
                                            dict(year='丙午', month='己亥')])
        for segment in result['segments']:
            for fact in segment['facts']:
                self.assertEqual(fact['source'], 'scripts/pai_pan_bazi.py:resolve_' + fact['layer'] + '_pillar')
                self.assertEqual(fact['window'], '[' + segment['start'] + ', ' + segment['end'] + ')')

    def test_li_chun_is_same_instant_on_previous_local_calendar_date(self):
        beijing_cut = engine.solar_term_beijing(2026, 315)
        cut = beijing_cut.astimezone(timezone(timedelta(hours=-5)))
        self.assertLess(cut.date(), beijing_cut.date())
        microsecond = timedelta(microseconds=1)
        result = periods.period_facts(cut - microsecond, cut + microsecond, 'month')
        self.assertEqual(result['boundaries'][0]['at'], cut.isoformat())
        self.assertEqual(result['boundaries'][0]['reasons'][0]['time_bj'], beijing_cut.isoformat())
        self.assertEqual(_pillars(result), [dict(year='乙巳', month='己丑'),
                                            dict(year='丙午', month='庚寅')])

    def test_jie_at_interval_endpoint_has_no_zero_width_segment(self):
        cut = engine.solar_term_beijing(2026, 315)
        microsecond = timedelta(microseconds=1)
        before = periods.period_facts(cut - microsecond, cut, 'year')
        after = periods.period_facts(cut, cut + microsecond, 'year')
        self.assertFalse(before['boundaries'])
        self.assertFalse(after['boundaries'])
        self.assertEqual(_pillars(before), [dict(year='乙巳')])
        self.assertEqual(_pillars(after), [dict(year='丙午')])

    def test_fractional_offset_preserves_both_sides_of_li_chun_for_qx(self):
        cut = engine.solar_term_beijing(2026, 315).astimezone(timezone.utc)
        local = cut.replace(tzinfo=None)
        suffix = '+00:00:00.5'
        plan = periods.query_period_facts(local.isoformat() + suffix,
                                         (local + timedelta(seconds=1)).isoformat() + suffix, 'year')
        left, right = plan['segments']
        expected_cut = cut.astimezone(timezone(timedelta(milliseconds=500))).isoformat()
        self.assertEqual(left['end'], expected_cut)
        self.assertEqual(right['start'], expected_cut)
        self.assertEqual(_pillars(plan), [dict(year='乙巳'), dict(year='丙午')])

        natal = core.analyze(engine.compute(date(1980, 12, 14), 15, 12, sex='男'))
        for segment in (left, right):
            window = '[' + segment['start'] + ', ' + segment['end'] + ')'
            luck = dict(layer='luck', pillar=None, source='大运未核', window=window)
            result = qiong.evaluate_periods(natal, [luck, *segment['facts']], expected_window=window)
            self.assertEqual(result['year']['temporal_facts'][1:], segment['facts'])

    def test_civil_day_changes_at_23_only_and_month_view_ignores_it(self):
        start = datetime.fromisoformat('2026-11-11T22:59:59.999999-05:00')
        end = datetime.fromisoformat('2026-11-12T00:01:00-05:00')
        day = periods.period_facts(start, end, 'day')
        self.assertEqual(day['boundaries'], [dict(at='2026-11-11T23:00:00-05:00', reasons=[
            dict(kind='civil_23h_day_boundary'),
        ])])
        self.assertEqual(_pillars(day), [dict(year='丙午', month='己亥', day='己丑'),
                                         dict(year='丙午', month='己亥', day='庚寅')])
        month = periods.period_facts(start, end, 'month')
        self.assertFalse(month['boundaries'])
        self.assertEqual(_pillars(month), [dict(year='丙午', month='己亥')])

    def test_year_query_spans_multiple_li_chun_not_gregorian_new_year(self):
        start = datetime.fromisoformat('2025-01-01T00:00+08:00')
        end = datetime.fromisoformat('2026-03-01T00:00+08:00')
        result = periods.period_facts(start, end, 'year')
        self.assertEqual([boundary['at'] for boundary in result['boundaries']],
                         [engine.solar_term_beijing(year, 315).isoformat() for year in (2025, 2026)])
        self.assertEqual(_pillars(result), [dict(year='甲辰'), dict(year='乙巳'), dict(year='丙午')])

    def test_year_table_labels_gregorian_year_separately_from_lichun(self):
        report = subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'pai_pan_bazi.py'),
            '--solar', '1980-12-24', '--hour', '17:00', '--sex', '男', '--deceased-year', '2026',
        ], text=True)
        section = report.split('## 流年\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('所选公历年度标签为 2026 年丙午', section)
        self.assertIn('具体时点的年柱按实际立春换年', section)
        self.assertNotIn('当前：', section)
        start = datetime(2026, 1, 1, tzinfo=engine.BJ)
        result = periods.period_facts(start, start + timedelta(days=1), 'year')
        self.assertEqual(_pillars(result), [dict(year='乙巳')])

    def test_requires_explicit_compatible_clock_and_nonempty_interval(self):
        start = datetime.fromisoformat('2026-03-08T00:00-05:00')
        with self.assertRaisesRegex(ValueError, '明确带固定 UTC 偏移'):
            periods.period_facts(start.replace(tzinfo=None), start + timedelta(days=1), 'day')
        with self.assertRaisesRegex(ValueError, '同一固定 UTC 偏移'):
            periods.period_facts(start, datetime.fromisoformat('2026-03-09T00:00-04:00'), 'day')
        with self.assertRaisesRegex(ValueError, '起点须早于终点'):
            periods.period_facts(start, start, 'day')

    def test_nuuk_clock_jump_at_late_zi_changes_the_qx_day_conclusion(self):
        zone = 'America/Nuuk'
        self.require_zone(zone)
        start = '2015-03-28T21:55:00.123456-03:00'
        end = '2015-03-28T23:05:00-02:00'
        result = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'),
            '--start', start, '--end', end, '--timezone', zone, '--layer', 'day',
        ], text=True))
        self.assertEqual(result['time_basis'], 'civil_iana')
        self.assertEqual(result['timezone'], zone)
        before, after = result['segments']
        self.assertEqual((before['start'], before['end'], after['start'], after['end']), (
            start, '2015-03-28T22:00:00-03:00', '2015-03-28T23:00:00-02:00', end))
        self.assertEqual(datetime.fromisoformat(before['end']), datetime.fromisoformat(after['start']))
        self.assertEqual(result['boundaries'], [dict(at=after['start'], reasons=[
            dict(kind='iana_utc_offset_change', previous_clock=before['end']),
        ])])
        self.assertEqual(_pillars(result), [dict(year='乙未', month='己卯', day='癸卯'),
                                            dict(year='乙未', month='己卯', day='甲辰')])

        natal = engine.compute(date(1980, 12, 14), 15, 12, sex='男')
        analysis = core.analyze(natal)
        age_months = 411
        luck, = [row for row in natal['dayun_age_windows']['windows']
                 if row['start_months_inclusive'] <= age_months < row['end_months_exclusive']]
        self.assertEqual(luck['pillar'], '辛卯')
        luck_fact = dict(layer='luck', pillar=luck['pillar'], source='原引擎合成盘大运',
                         window='合成查询年龄 411 月')

        def query_window(segment):
            return '[' + segment['start'] + ', ' + segment['end'] + ')'

        panels = [qiong.evaluate_periods(analysis, [luck_fact, *segment['facts']],
                                         expected_window=query_window(segment))
                  for segment in (before, after)]
        self.assertEqual([panel['day']['conditional_model_direction'] for panel in panels],
                         ['development_support_restricted', 'development_configuration_relatively_favorable'])
        self.assertEqual({panel['month']['conditional_model_direction'] for panel in panels},
                         {'development_configuration_relatively_favorable'})

        # Keeping the starting offset covers the same physical time but reads the wrong local day.
        fixed_start = datetime.fromisoformat(start)
        fixed_end = datetime.fromisoformat(end).astimezone(fixed_start.tzinfo)
        flattened, = periods.period_facts(fixed_start, fixed_end, 'day')['segments']
        self.assertEqual(flattened['facts'][-1]['pillar'], '癸卯')
        with self.assertRaisesRegex(ValueError, '日层须使用本次查询的固定民用偏移'):
            qiong.evaluate_periods(analysis, [luck_fact, *flattened['facts']],
                                   expected_window=query_window(after))

    def test_regional_month_keeps_physical_jie_and_offset_change(self):
        zone = 'America/New_York'
        self.require_zone(zone)
        result = periods.regional_period_facts(datetime(2026, 11, 1), datetime(2026, 11, 8),
                                               'month', zone)
        term = engine.solar_term_beijing(2026, 225)
        local_term = term.astimezone(timezone(timedelta(hours=-5))).isoformat()
        self.assertEqual(result['boundaries'], [
            dict(at='2026-11-01T01:00:00-05:00', reasons=[
                dict(kind='iana_utc_offset_change', previous_clock='2026-11-01T02:00:00-04:00'),
            ]),
            dict(at=local_term, reasons=[dict(kind='jie', name='立冬', time_bj=term.isoformat())]),
        ])
        self.assertEqual(_pillars(result), [dict(year='丙午', month='戊戌'),
                                            dict(year='丙午', month='戊戌'),
                                            dict(year='丙午', month='己亥')])

    def test_equal_fold_labels_cover_rollback_and_repeat_late_zi_in_utc_order(self):
        zone = 'Pacific/Kwajalein'
        self.require_zone(zone)
        label = '1969-09-30T23:30'
        result = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'),
            '--start', label, '--start-fold', '0', '--end', label, '--end-fold', '1',
            '--timezone', zone, '--layer', 'day',
        ], text=True))
        segments = result['segments']
        self.assertEqual([(row['start'], row['end']) for row in segments], [
            ('1969-09-30T23:30:00+11:00', '1969-10-01T00:00:00+11:00'),
            ('1969-09-30T01:00:00-12:00', '1969-09-30T23:00:00-12:00'),
            ('1969-09-30T23:00:00-12:00', '1969-09-30T23:30:00-12:00'),
        ])
        self.assertEqual([row['day'] for row in _pillars(result)], ['己酉', '戊申', '己酉'])
        start, end = (datetime.fromisoformat(result[key]) for key in ('start', 'end'))
        self.assertEqual(end - start, timedelta(hours=23))
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(datetime.fromisoformat(left['end']), datetime.fromisoformat(right['start']))
        with self.assertRaisesRegex(ValueError, '起点须早于终点'):
            point = datetime.fromisoformat(label)
            periods.regional_period_facts(point, point, 'day', zone, start_fold=1, end_fold=0)

    def test_civil_date_query_covers_midnight_gap(self):
        zone = 'America/Santiago'
        self.require_zone(zone)
        cmd = [sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'),
               '--timezone', zone, '--layer', 'day']
        result = json.loads(subprocess.check_output(cmd + ['--start', '2024-09-08', '--end', '2024-09-09']))
        self.assertEqual(result.pop('civil_dates'), dict(start_inclusive='2024-09-08', end_exclusive='2024-09-09'))
        self.assertEqual(result, periods.regional_period_facts(datetime(2024, 9, 8, 1),
                                                               datetime(2024, 9, 9), 'day', zone))
        self.assertEqual(result['start'], '2024-09-08T01:00:00-03:00')
        self.assertEqual([row['day'] for row in _pillars(result)], ['乙亥', '丙子'])
        rejected = subprocess.run(cmd + ['--start', '2024-09-08T00:00', '--end', '2024-09-09T00:00'],
                                  capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('此民用时间不存在', rejected.stderr)

    def test_civil_date_query_excludes_interleaved_date_during_rollback(self):
        zone = 'America/Goose_Bay'
        self.require_zone(zone)
        start, end = date(1988, 10, 29), date(1988, 10, 30)
        result = periods.regional_date_facts(start, end, 'day', zone)
        segments = result['segments']
        self.assertEqual([row['day'] for row in _pillars(result)], ['丁巳', '戊午', '丁巳', '戊午'])
        before, after = datetime.fromisoformat(segments[1]['end']), datetime.fromisoformat(segments[2]['start'])
        self.assertEqual(after - before, timedelta(minutes=1))
        self.assertEqual(result['boundaries'][1], dict(at='1988-10-29T22:01:00-04:00', reasons=[
            dict(kind='civil_date_membership_gap', previous_clock='1988-10-30T00:00:00-02:00'),
        ]))
        combined = periods.regional_date_facts(start, date(1988, 10, 31), 'day', zone)
        self.assertIn(dict(at='1988-10-29T22:01:00-04:00', reasons=[
            dict(kind='iana_utc_offset_change', previous_clock='1988-10-30T00:01:00-02:00'),
        ]), combined['boundaries'])
        for left, right in zip(combined['segments'], combined['segments'][1:]):
            self.assertEqual(datetime.fromisoformat(left['end']), datetime.fromisoformat(right['start']))
        explicit_fold = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'), '--timezone', zone, '--layer', 'day',
            '--start', '1988-10-30', '--start-fold', '0', '--end', '1988-10-31',
        ]))
        self.assertNotIn('civil_dates', explicit_fold)
        self.assertEqual(explicit_fold['segments'][1]['start'], '1988-10-29T22:01:00-04:00')

    def test_civil_date_query_handles_completely_skipped_date(self):
        zone = 'Pacific/Apia'
        self.require_zone(zone)
        with self.assertRaisesRegex(ValueError, '民用日期范围无可达查询时刻'):
            periods.regional_date_facts(date(2011, 12, 30), date(2011, 12, 31), 'day', zone)
        result = periods.regional_date_facts(date(2011, 12, 29), date(2012, 1, 1), 'day', zone)
        self.assertEqual([row['day'] for row in _pillars(result)], ['戊午', '己未', '庚申', '辛酉'])
        self.assertEqual([row['start'][:10] for row in result['segments']],
                         ['2011-12-29', '2011-12-29', '2011-12-31', '2011-12-31'])
        for left, right in zip(result['segments'], result['segments'][1:]):
            self.assertEqual(datetime.fromisoformat(left['end']), datetime.fromisoformat(right['start']))

    def test_civil_date_and_clock_queries_agree_on_ordinary_midnights(self):
        zone = 'America/New_York'
        self.require_zone(zone)
        start, end = date(2026, 11, 1), date(2026, 11, 3)
        result = periods.regional_date_facts(start, end, 'month', zone)
        result.pop('civil_dates')
        self.assertEqual(result, periods.regional_period_facts(datetime(2026, 11, 1),
                                                               datetime(2026, 11, 3), 'month', zone))

    def test_regional_query_rejects_gaps_ambiguous_and_mismatched_endpoints(self):
        zone = 'America/New_York'
        self.require_zone(zone)
        for start, end, flags, message in (
                ('2024-03-10T02:10', '2024-03-10T03:20', [], '请核实查询钟面'),
                ('2024-11-03T01:10', '2024-11-03T02:00', [], '--start-fold'),
                ('2024-11-03T00:10', '2024-11-03T01:00', [], '--end-fold'),
                ('2024-11-03T01:10-06:00', '2024-11-03T02:00', [], '指定 IANA 时区不符'),
                ('2024-11-03T01:10-04:00', '2024-11-03T02:00',
                 ['--start-fold', '0'], '已有明确偏移')):
            with self.subTest(start=start, end=end, flags=flags):
                completed = subprocess.run([
                    sys.executable, '-B', str(SCRIPTS / 'bazi_period_facts.py'),
                    '--start', start, '--end', end, '--timezone', zone, '--layer', 'day', *flags,
                ], text=True, capture_output=True)
                self.assertEqual(completed.returncode, 2)
                self.assertFalse(completed.stdout)
                self.assertIn(message, completed.stderr)


if __name__ == '__main__':
    unittest.main()
