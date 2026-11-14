"""Synthetic public fixtures only: sampled evidence is not a stability certificate."""
import contextlib
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qizheng_sensitivity as sensitivity
import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules
import build_chart
from time_scenarios import resolve_civil

ROOT = Path(__file__).resolve().parents[1]


class SensitivityTests(unittest.TestCase):
    def test_confirmed_zi_shichen_compares_two_disjoint_parts_without_a_center(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '1987-09-04', '--timezone', 'Asia/Shanghai',
                   '--lat', '31.23', '--lon', '121.47', '--shichen', '子']
        result = json.loads(subprocess.check_output(command, text=True, timeout=60))
        self.assertEqual(result['version'], 'qizheng-civil-shichen-sensitivity-v1')
        self.assertEqual(result['input']['shichen'], '子')
        self.assertNotIn('start_inclusive', result['input'])
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['stable_fields'], {})
        self.assertEqual(result['uncertain_birth_rule_status'], 'withheld')
        early, late = result['sampled_sections']
        self.assertEqual([(s['start_local'], s['end_exclusive_local']) for s in (early, late)], [
            ('1987-09-04T00:00:00+09:00', '1987-09-04T01:00:00+09:00'),
            ('1987-09-04T23:00:00+09:00', '1987-09-05T00:00:00+09:00'),
        ])
        for section, palace in ((early, '酉'), (late, '戌')):
            sample = section['sample']
            self.assertNotIn('center_utc', sample['interval'])
            self.assertTrue(all(section['start_utc'] <= row['witness_utc'] < section['end_exclusive_utc']
                                for row in sample['candidates']))
            self.assertEqual({row['chart']['ming_gong']['zhi'] for row in sample['candidates']}, {palace})
            self.assertNotIn('ming_gong', sample['observed_changing_fields'])
        self.assertIn('ming_gong', result['observed_changing_fields'])
        self.assertEqual(sum(s['sample']['method']['evaluation_count'] for s in (early, late)),
                         result['method']['evaluation_count'])
        summary = subprocess.check_output(command + ['--format', 'text'], text=True, timeout=60)
        self.assertIn('整段出生规则暂缓', summary)
        self.assertIn('可达时段 2 段', summary)
        self.assertIn('传统立命宫分别为酉宫／戌宫', summary)
        self.assertIn(early['sample']['candidates'][-1]['witness_utc'], summary)
        self.assertIn(late['start_utc'], summary)
        self.assertIn('仅说明两点有别', summary)

    def test_summary_prefers_rule_withdrawal_to_changed_palace_with_same_availability(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '2000-01-01', '--start', '06:55', '--end', '07:45',
                   '--utc-offset', '8', '--lat', '35', '--lon', '120',
                   '--qizheng-tradition', 'qianyuan-palace-v1']
        evidence = json.loads(subprocess.check_output(command, text=True, timeout=30))
        first, second = (row['sample'] for row in evidence['sampled_sections'])
        left, right = first['candidates'][-1], second['candidates'][0]
        self.assertNotEqual(left['chart']['ming_gong']['zhi'], right['chart']['ming_gong']['zhi'])
        for key in ('rule_output', 'traditional_rule_output'):
            self.assertEqual(left['fields'][key]['status'], 'conditional')
            self.assertEqual(right['fields'][key]['status'], 'conditional')
            self.assertTrue(any(row['fields'][key]['status'] == 'withheld' for row in second['candidates']))
        summary = subprocess.check_output(command + ['--format', 'text'], text=True, timeout=30)
        self.assertIn('传统立命宫分别为丑宫／子宫', summary)
        for label in ('条件规则解释', '乾元宫主条件参照'):
            self.assertIn(label + '：有条件解释 → 暂缓解释（命度靠近未校准宿界）', summary)
            self.assertIn(label + '在后续已计算见证 UTC', summary)
        self.assertIn('QZ01 斗宿取木为度主。QZ02 子宫主折土，对度主为仇', summary)
        self.assertIn('QZT04 金曜相对子宫主土为我生', summary)
        self.assertIn('UTC 1999-12-31 23:01 至 1999-12-31 23:02', summary)
        self.assertIn('整段出生规则暂缓', summary)
        self.assertIn('宿界及近似星历的误差仍在', summary)

        center = datetime(2000, 1, 1, 7, 10, tzinfo=engine.BJ)
        combined = sensitivity.compare(center, 20, 35, 120, traditional_scheme='qianyuan-palace-v1')
        text = '\n'.join(sensitivity.render(combined))
        self.assertIn('QZ01 斗宿取木为度主。QZ02 子宫主折土，对度主为仇', text)
        self.assertEqual(text.count('在后续已计算见证 UTC'), 2)

    def test_changed_palace_summary_names_the_two_actual_reference_results(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '1980-10-10', '--start', '18:59', '--end', '19:01',
                   '--utc-offset', '8', '--lat', '31.23', '--lon', '121.47']
        default = subprocess.check_output(command + ['--format', 'text'], text=True, timeout=30)
        self.assertIn('QZ01 两点均胃宿取土为度主', default)
        self.assertIn('QZ02 亥宫主折木，对度主为难／戌宫主折火，对度主为恩', default)
        self.assertNotIn('QZT04', default)
        self.assertIn('整段出生规则暂缓', default)
        selected = subprocess.check_output(command + [
            '--format', 'text', '--qizheng-tradition', 'qianyuan-palace-v1',
        ], text=True, timeout=30)
        self.assertIn('QZT04 金曜相对亥宫主木为克我／金曜相对戌宫主火为我克', selected)
        self.assertIn('QZ02 亥宫主折木，对度主为难／戌宫主折火，对度主为恩', selected)

        center = datetime(1980, 10, 10, 19, tzinfo=engine.BJ)
        compared = sensitivity.compare(center, 1, 31.23, 121.47)
        self.assertEqual(compared['uncertain_birth_rule_status'], 'withheld')
        summary = '\n'.join(sensitivity.render(compared))
        self.assertIn('QZ02 亥宫主折木，对度主为难 → 戌宫主折火，对度主为恩', summary)

    def test_unchanged_admitted_results_appear_as_shared_observations(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '1980-10-10', '--start', '18:55', '--end', '18:56',
                   '--utc-offset', '8', '--lat', '31.23', '--lon', '121.47', '--format', 'text']
        baseline = subprocess.check_output(command, text=True, timeout=30)
        self.assertIn('实测见证的共同结果（条件规则解释）。QZ01 胃宿取土为度主。'
                      'QZ02 亥宫主折木，对度主为难', baseline)
        self.assertNotIn('QZT04', baseline)
        selected = subprocess.check_output(command + ['--qizheng-tradition', 'qianyuan-palace-v1'],
                                           text=True, timeout=30)
        self.assertIn('实测见证的共同结果（乾元宫主条件参照）。QZT04 金曜相对亥宫主木为克我', selected)
        self.assertIn('整段出生规则暂缓', selected)

        center = datetime(1980, 10, 10, 18, 55, tzinfo=engine.BJ)
        compared = sensitivity.compare(center, 1, 31.23, 121.47)
        self.assertEqual(compared['observed_changing_fields'], [])
        self.assertEqual(compared['stable_fields'], {})
        self.assertFalse(compared['coverage_complete'])
        self.assertIn('QZ02 亥宫主折木，对度主为难', '\n'.join(sensitivity.render(compared)))

    def test_civil_shichen_and_clock_band_options_are_alternative_inputs(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '2000-01-01', '--utc-offset', '8', '--lat', '35', '--lon', '120']
        for extras, reason in [
                (['--shichen', '子', '--start', '00:00', '--end', '01:00'], '须择一组'),
                (['--start', '00:00'], '一对 --start 与 --end')]:
            with self.subTest(extras=extras):
                result = subprocess.run(command + extras, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(reason, result.stderr)

    def test_summary_names_unchanged_partial_and_withheld_rule_limits(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '2000-02-22', '--start', '11:59', '--end', '12:01',
                   '--utc-offset', '8', '--lat', '35', '--lon', '120',
                   '--qizheng-tradition', 'qianyuan-palace-v1']
        evidence = json.loads(subprocess.check_output(command, text=True, timeout=30))
        self.assertEqual(evidence['observed_changing_fields'], [])
        self.assertFalse(evidence['coverage_complete'])
        sample, = (row['sample'] for row in evidence['sampled_sections'])
        for row in sample['candidates']:
            self.assertEqual([(claim['rule_id'], claim['status']) for claim in row['rule_reading']['claims']],
                             [('QZ01', 'conditional'), ('QZ02', 'withheld')])
            self.assertEqual(row['traditional_reading']['status'], 'withheld')

        partial = '已采样时点的条件规则解释均为部分可解释（太阳靠近未校准宿宫界）'
        withheld = '已采样时点的乾元宫主条件参照均为暂缓解释（太阳靠近未校准宿宫界）'
        text = subprocess.check_output(command + ['--format', 'text'], text=True, timeout=30)
        self.assertIn(partial, text)
        self.assertIn(partial + '。QZ01 毕宿取水为度主。', text)
        self.assertIn(withheld, text)
        self.assertNotIn('在后续已计算见证 UTC', text)
        self.assertIn('整段出生规则暂缓', text)
        center = datetime(2000, 2, 22, 12, tzinfo=engine.BJ)
        result = sensitivity.compare(center, 1, 35, 120, traditional_scheme='qianyuan-palace-v1')
        summary = '\n'.join(sensitivity.render(result))
        self.assertIn(partial, summary)
        self.assertIn(partial + '。QZ01 毕宿取水为度主。', summary)
        self.assertIn(withheld, summary)

    def test_confirmed_long_band_cli_excludes_right_endpoint(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '2000-01-01', '--start', '06:00', '--end', '13:00',
                   '--utc-offset', '8', '--lat', '35', '--lon', '120']
        result = json.loads(subprocess.check_output(command, text=True, timeout=60))
        self.assertEqual(result['uncertain_birth_rule_status'], 'withheld')
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['stable_fields'], {})
        self.assertIn('day_night', result['observed_changing_fields'])
        self.assertIn('ming_gong', result['observed_changing_fields'])
        sections = result['sampled_sections']
        self.assertEqual(len(sections), 4)
        self.assertEqual(sections[-1]['end_exclusive_local'], '2000-01-01T13:00:00+08:00')
        for section in sections:
            first, last = [datetime.fromisoformat(section[key])
                           for key in ('start_utc', 'end_exclusive_utc')]
            sample = section['sample']
            self.assertNotIn('center_utc', sample['interval'])
            self.assertEqual(datetime.fromisoformat(sample['interval']['end_utc']),
                             last - timedelta(microseconds=1))
            self.assertTrue(all(first <= datetime.fromisoformat(row['witness_utc']) < last
                                for row in sample['candidates']))
        last = sections[-1]['sample']['candidates'][-1]
        self.assertEqual(last['witness_civil'], '2000-01-01T12:59:59.999999+08:00')
        self.assertEqual(last['chart']['ming_gong']['zhi'], '戌')
        self.assertEqual(engine.compute((2000, 1, 1), 13, 0, 35, 120)[0]['ming_gong']['zhi'], '酉')

    def test_narrowed_birth_summaries_show_observed_values_without_certifying_the_band(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '2000-01-01', '--utc-offset', '8', '--lat', '35', '--lon', '120']
        for start, end, day_night, mansion, palace in (
            ('06:58', '07:00', '夜生', '箕', '丑'),
            ('07:41', '07:43', '昼生', '斗', '子'),
        ):
            with self.subTest(start=start):
                args = command + ['--start', start, '--end', end]
                result = json.loads(subprocess.check_output(args, text=True, timeout=30))
                text = subprocess.check_output(args + ['--format', 'text'], text=True, timeout=30)
                self.assertEqual(result['observed_changing_fields'], [])
                self.assertEqual(result['stable_fields'], {})
                self.assertFalse(result['coverage_complete'])
                self.assertIn(f'已采样时点均观测到昼夜划分为{day_night}、命度所属宿为{mansion}、传统立命宫为{palace}宫', text)
                self.assertIn('整个出生范围仍未穷尽', text)
                self.assertIn('整段出生规则暂缓', text)
                self.assertNotIn('已采样时点的条件规则解释均为', text)
        text = subprocess.check_output(command + ['--start', '06:55', '--end', '07:45', '--format', 'text'],
                                       text=True, timeout=30)
        self.assertIn('昼夜划分：夜生 → 昼生', text)
        self.assertNotIn('均观测到昼夜划分', text)
        result = sensitivity.compare(datetime(2000, 1, 1, 7, 42, tzinfo=engine.BJ), 1, 35, 120)
        self.assertIn('昼夜划分为昼生', '\n'.join(sensitivity.render(result)))

    def test_fixed_offset_band_matches_historical_zone_at_whole_minutes(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                   '--birth-date', '1935-09-15', '--start', '06:00', '--end', '06:01',
                   '--lat', '4.9', '--lon', '114.9']
        zoned = json.loads(subprocess.check_output(command + ['--timezone', 'Asia/Brunei'],
                                                   text=True, timeout=30))
        fixed = json.loads(subprocess.check_output(command + ['--utc-offset', '8.333333333333334'],
                                                   text=True, timeout=30))
        zoned_input = zoned['sampled_sections'][0]['sample']['input']
        fixed_input = fixed['sampled_sections'][0]['sample']['input']
        self.assertEqual(zoned_input.pop('timezone'), 'Asia/Brunei')
        self.assertEqual(fixed_input.pop('utc_offset_hours'), 8 + 20 / 60)
        self.assertEqual(zoned['sampled_sections'], fixed['sampled_sections'])
        self.assertEqual(fixed['sampled_sections'][0]['start_utc'], '1935-09-14T21:40:00+00:00')
        self.assertEqual(fixed['uncertain_birth_rule_status'], 'withheld')
        invalid = subprocess.run(command + ['--utc-offset', '8.34'], text=True, capture_output=True, timeout=30)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, '')
        self.assertIn('精确到整分钟', invalid.stderr)

    def test_confirmed_repeated_wall_clock_does_not_sample_between_folds(self):
        result = sensitivity.compare_civil_band(date(2024, 11, 3), '01:10', '01:20', 40.7, -74,
                                                zone='America/New_York')
        early, late = result['sampled_sections']
        self.assertEqual(early['end_exclusive_utc'], '2024-11-03T05:20:00+00:00')
        self.assertEqual(late['start_utc'], '2024-11-03T06:10:00+00:00')
        self.assertIn('ascendant.mansion', result['observed_changing_fields'])
        for section, fold in ((early, 0), (late, 1)):
            sample = section['sample']
            self.assertTrue(all(row['fold'] == fold for row in sample['candidates']))
            self.assertTrue(all(section['start_utc'] <= row['left_utc'] < row['right_utc']
                                < section['end_exclusive_utc'] for row in sample['boundaries']))
        summary = '\n'.join(sensitivity.render_civil_birth(result))
        self.assertIn('命度所属宿分别为柳／星', summary)
        self.assertIn('2024-11-03T01:10:00-04:00', summary)
        self.assertIn('2024-11-03T01:10:00-05:00', summary)
        self.assertNotIn('一次观察差异位于', summary)
        self.assertIn('条件规则解释分别为有条件解释／有条件解释', summary)
        # At the spring offset transition these two sections are physically
        # contiguous, and the sample on each side keeps its own Beijing hour.
        spring = sensitivity.compare_civil_band(date(2024, 3, 10), '01:50', '03:10', 40.7, -74,
                                                zone='America/New_York')
        before, after = spring['sampled_sections']
        self.assertEqual(before['end_exclusive_utc'], after['start_utc'])
        self.assertEqual(before['sample']['candidates'][-1]['chart']['ming_gong']['zhi'], '未')
        self.assertEqual(after['sample']['candidates'][0]['chart']['ming_gong']['zhi'], '午')
        self.assertIn('ming_gong', spring['observed_changing_fields'])

    def test_confirmed_band_keeps_later_base_samples_under_global_budget(self):
        with patch.object(sensitivity, 'MAX_EVALUATIONS', 424):
            result = sensitivity.compare_civil_band(date(2000, 1, 1), '06:00', '13:00', 35, 120, utc_offset=8)
        self.assertEqual(result['method'], dict(max_evaluations=424, evaluation_count=424, budget_exhausted=True))
        self.assertEqual([s['sample']['method']['evaluation_count'] for s in result['sampled_sections']],
                         [61, 121, 121, 121])

    def test_real_boundaries_and_replay(self):
        result = sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),120,35,120)
        self.assertFalse(result['coverage_complete'])
        self.assertEqual({},result['stable_fields'])
        self.assertFalse(result['method']['root_completeness_proven'])
        self.assertIn('day_night',result['observed_changing_fields'])
        self.assertIn('ascendant.mansion',result['observed_changing_fields'])
        self.assertIn('ming_gong',result['observed_changing_fields'])
        self.assertIn('rule_output',result['observed_changing_fields'])
        candidates = {r['witness_utc']: r for r in result['candidates']}
        for b in result['boundaries']:
            self.assertLessEqual(b['width_seconds'],.1)
            a,c = (candidates[b[k]] for k in ('left_utc','right_utc'))
            self.assertNotEqual(a['fields'],c['fields'])
        for row in candidates.values():
            instant=datetime.fromisoformat(row['witness_utc'])
            bj=instant.astimezone(engine.BJ)
            chart,_=engine.compute((bj.year,bj.month,bj.day),bj.hour,bj.minute,35,120,birth_instant=instant)
            self.assertEqual(chart,row['chart'])
            self.assertEqual(rules.analyze(chart),row['rule_reading'])
        # Text carries the same evidence, including full numerical coordinates.
        self.assertEqual(result,json.loads(sensitivity.render(result, full_evidence=True)[-2]))

    def test_bounded_plain_summary_and_full_evidence(self):
        for lat, zone, fold, date in (
            (35, 'Asia/Shanghai', None, datetime(2000,1,1,8)),
            (90, 'America/New_York', 1, datetime(2024,11,3,1,30)),
            (35, 'America/New_York', None, datetime(2024,3,10,3,30)),
        ):
            result=sensitivity.compare(resolve_civil(date,zone=zone,fold=fold),120,lat,120)
            text='\n'.join(sensitivity.render(result))
            self.assertLess(len(text),6000)
            self.assertLessEqual(text.count('一次观察差异'),sensitivity.SUMMARY_MAX_CHANGES)
            self.assertNotIn('```json',text)
            self.assertIn('未观察到不等于稳定',text)
            self.assertIn(result['candidates'][0]['witness_civil'],text)
            self.assertIn(result['candidates'][-1]['witness_civil'],text)
            self.assertEqual(result,json.loads(sensitivity.render(result,True)[-2]))
            if date.month==3:
                self.assertIn('时区偏移变化或重复民用时刻',text)
            if lat==90:
                self.assertIn('上升交点未定义',text)
                self.assertIn('UTC 区分瞬间',text)
        point=sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),0,35,120)
        self.assertIn('不能据此说整个时段稳定','\n'.join(sensitivity.render(point)))

    def test_combined_summary_identifies_repeated_clocks_and_second_offsets(self):
        cases = (
            ('2024-11-03', '01:30', 'America/New_York', 10, '0', '05:20:00+00:00'),
            ('2024-11-03', '01:30', 'America/New_York', 10, '1', '06:20:00+00:00'),
            ('1918-04-15', '03:30', 'Europe/Riga', 60, None, '23:53:26+00:00'),
            ('2024-11-04', '01:30', 'America/New_York', 10, None, None),
        )
        for day, hour, zone, minutes, fold, utc_start in cases:
            with self.subTest(day=day, zone=zone, fold=fold):
                args = ['--solar', day, '--hour', hour, '--timezone', zone, '--sex', '男',
                        '--lat', '40.7128', '--lon', '-74.006', '--analysis-year', '2026',
                        '--qizheng-sensitivity', '--uncertainty-minutes', str(minutes)]
                if fold is not None:
                    args.extend(['--fold', fold])
                out = io.StringIO()
                with patch.object(build_chart, 'run_ziwei', return_value=(None, 'test only')), contextlib.redirect_stdout(out):
                    build_chart.main(args)
                summary = out.getvalue().split('## 七政时间敏感性', 1)[1].split('\n## ', 1)[0]
                if utc_start is None:
                    self.assertNotIn('UTC 区分瞬间', summary)
                else:
                    self.assertIn('UTC 区分瞬间', summary)
                    self.assertIn('本次比较的 UTC 时段', summary)
                    self.assertIn(utc_start, summary)

    def test_summary_keeps_clock_changes_between_retained_samples(self):
        from zoneinfo import ZoneInfo

        start = datetime(2000, 1, 1, 5, tzinfo=timezone.utc)
        second = int(start.timestamp())
        header = struct.pack('>4s16x6I', b'TZif', 0, 0, 0, 2, 2, 8)
        transitions = struct.pack('>2i2B', second + 15, second + 25, 1, 0)
        types = struct.pack('>iBBiBB', 0, 0, 0, 1, 1, 4)
        zone = ZoneInfo.from_file(io.BytesIO(header + transitions + types + b'STD\0ALT\0'))
        center = (start + timedelta(minutes=1)).astimezone(zone)
        result = sensitivity.compare(center, 1, 35, 120)
        self.assertTrue(all(not row['fold'] and datetime.fromisoformat(row['witness_civil']).utcoffset() == timedelta(0)
                            for row in result['candidates']))
        summary = '\n'.join(sensitivity.render(result, local_timezone=zone))
        self.assertIn('UTC 区分瞬间', summary)

    def test_real_moon_mansion_boundary(self):
        result = sensitivity.compare(datetime(2000,1,3,tzinfo=timezone.utc),120,35,120)
        self.assertIn("bodies.月.mansion",result["observed_changing_fields"])
        self.assertTrue(any("bodies.月.mansion" in b["changed_fields"] for b in result["boundaries"]))

    def test_fold_elapsed_time_and_equivalent_offsets(self):
        civil=resolve_civil(datetime(2024,11,3,1,30),zone='America/New_York',fold=1)
        a=sensitivity.compare(civil,40,40,-74)
        b=sensitivity.compare(civil.astimezone(timezone.utc),40,40,-74)
        self.assertEqual(a['interval'],b['interval'])
        self.assertEqual(a['boundaries'],b['boundaries'])
        self.assertEqual([c['chart'] for c in a['candidates']],[c['chart'] for c in b['candidates']])
        self.assertEqual({0,1},{r['fold'] for r in a['candidates']})
        self.assertEqual(4800,(datetime.fromisoformat(a['interval']['end_utc'])-datetime.fromisoformat(a['interval']['start_utc'])).total_seconds())

    def test_pole_missing_ascendant_and_legacy(self):
        for profile in ('physical-v2','legacy-v1'):
            r=sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),2,90,0,profile)
            self.assertTrue(r['high_latitude_caution'])
            self.assertEqual(profile,r['calculation_profile'])
            if profile=='physical-v2':
                self.assertTrue(all(c['chart']['ming_du'] is None for c in r['candidates']))
                self.assertTrue(all(c['rule_reading']['status']=='withheld' for c in r['candidates']))

    def test_selected_tradition_composes_without_unlocking_center(self):
        import qizheng_traditional_reading as tradition
        civil=datetime(2000,1,1,tzinfo=timezone.utc)
        result=sensitivity.compare(civil,2,35,120,traditional_scheme=tradition.SCHEME)
        self.assertEqual('withheld',result['uncertain_birth_rule_status'])
        self.assertEqual(tradition.SCHEME,result['traditional_scheme'])
        for row in result['candidates']:
            self.assertEqual(tradition.analyze(row['chart'],tradition.SCHEME,birth_instant=datetime.fromisoformat(row['witness_utc'])),row['traditional_reading'])
            self.assertIn('traditional_rule_output',row['fields'])
        self.assertLess(result['method']['evaluation_count'],sensitivity.MAX_EVALUATIONS)
        text='\n'.join(sensitivity.render(result))
        self.assertIn('紫气为未独立校准',text)
        self.assertIn('真太阳时误差',text)

    def test_subsecond_traditional_witness_preserves_boundary_side(self):
        import qizheng_traditional_reading as tradition
        for microsecond in (999700, 999999):
            instant=datetime(2000,1,1,0,59,59,microsecond,tzinfo=timezone.utc)
            bj=instant.astimezone(engine.BJ)
            chart,_=engine.compute((bj.year,bj.month,bj.day),bj.hour,bj.minute,35,120,birth_instant=instant)
            reading=tradition.analyze(chart,tradition.SCHEME,birth_instant=instant)
            self.assertEqual('conditional',reading['status'])
            wrong=instant.replace(hour=3)
            self.assertEqual('withheld',tradition.analyze(chart,tradition.SCHEME,birth_instant=wrong)['status'])

    def test_budget_and_validation(self):
        center=datetime(2000,1,1,tzinfo=timezone.utc)
        with patch.object(sensitivity,'MAX_EVALUATIONS',241):
            r=sensitivity.compare(center,120,35,120)
        self.assertTrue(r['method']['budget_exhausted'])
        self.assertEqual(241,r['method']['evaluation_count'])
        self.assertTrue(any(b.get('unrefined') for b in r['boundaries']))
        for minutes in (-1,121,float('nan'),float('inf')):
            with self.assertRaises(ValueError): sensitivity.compare(center,minutes,35,120)
        with self.assertRaises(ValueError): sensitivity.compare(center.replace(tzinfo=None),1,35,120)
        with self.assertRaises(ValueError): sensitivity.compare(center,1,91,120)
        with self.assertRaises(ValueError): sensitivity.compare(center.replace(year=1900),1,35,120)

    def test_cli_opt_in_and_uncertainty_guard(self):
        args=['--solar','2000-01-01','--hour','08:00','--lat','35','--lon','120','--sex','男','--uncertainty-minutes','120','--analysis-year','2026']
        def run(extra):
            out=io.StringIO()
            with patch.object(build_chart,'run_ziwei',return_value=(None,'test only')),contextlib.redirect_stdout(out):
                build_chart.main(args+extra)
            return out.getvalue()
        old=json.loads(run(['--format','json']))
        new=json.loads(run(['--format','json','--qizheng-sensitivity']))
        self.assertIsNone(old['qizheng_sensitivity'])
        self.assertEqual(old['scenarios'],new['scenarios'])
        self.assertEqual(old['bazi'],new['bazi'])
        self.assertEqual(old['qizheng'],new['qizheng'])
        self.assertEqual('withheld',new['qizheng_rule_reading']['status'])
        self.assertTrue(any(c['rule_reading']['status']=='conditional' for c in new['qizheng_sensitivity']['candidates']))
        summary=run(['--qizheng-sensitivity'])
        self.assertNotIn('```json',summary)
        text=run(['--qizheng-sensitivity-evidence'])
        payload=text.split('```json\n',1)[1].split('\n```',1)[0]
        self.assertEqual(new['qizheng_sensitivity'],json.loads(payload))

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_cli_preserves_other_charts_when_requested_sampling_lacks_coordinates(self):
        command = [
            sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
            '--solar', '1987-06-02', '--hour', '17:00', '--sex', '男', '--utc-offset', '8',
            '--uncertainty-minutes', '2', '--analysis-year', '2032', '--enumerate-scenarios',
        ]
        baseline = json.loads(subprocess.check_output(command + ['--format', 'json'], text=True, timeout=45))
        for coordinates, option, missing in (
                ([], '--qizheng-sensitivity', '--lat 和 --lon'),
                (['--lat', '31.23'], '--qizheng-sensitivity-evidence', '--lon'),
                (['--lon', '121.47'], '--qizheng-sensitivity', '--lat')):
            with self.subTest(coordinates=coordinates, option=option):
                snapshot = json.loads(subprocess.check_output(
                    command + ['--format', 'json', option, *coordinates], text=True, timeout=45))
                self.assertIsNone(snapshot['qizheng_sensitivity'])
                reason = '未执行七政时间敏感性比较，缺少出生地坐标 ' + missing
                self.assertEqual(reason, snapshot['degradation']['qizheng_sensitivity'])
                self.assertIn(reason, snapshot['warnings'])
                self.assertIsNone(snapshot['degradation']['ziwei'])
                for key in ('bazi', 'bazi_scenario_comparison', 'ziwei', 'ziwei_scenario_comparison', 'scenarios'):
                    self.assertIsNotNone(snapshot[key])
                    self.assertEqual(baseline[key], snapshot[key])
                self.assertEqual(11, len(snapshot['qizheng']['bodies']))
                self.assertEqual(baseline['qizheng']['bodies'], snapshot['qizheng']['bodies'])
                for key in ('ming_du', 'ming_gong', 'day_night', 'en_yong'):
                    self.assertIsNone(snapshot['qizheng'][key])
                self.assertEqual('withheld', snapshot['qizheng_rule_reading']['status'])
        output = subprocess.check_output(
            command + ['--qizheng-sensitivity-evidence'], text=True, timeout=45)
        self.assertIn('未执行七政时间敏感性比较，缺少出生地坐标 --lat 和 --lon', output)
        for heading in ('## 八字', '## 紫微斗数', '## 七政四余'):
            self.assertIn(heading, output)

    def test_sampling_still_rejects_invalid_parameters(self):
        chart = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                 '--solar', '1987-06-02', '--hour', '17:00', '--sex', '男', '--qizheng-sensitivity']
        standalone = [sys.executable, '-B', str(ROOT / 'scripts/qizheng_sensitivity.py'),
                      '--birth-date', '1987-06-02', '--shichen', '酉', '--utc-offset', '8']
        for command, extra, reason in (
                (chart, ['--lat', '91'], '纬度/经度超出范围'),
                (chart, ['--lon', 'nan'], '必须为有限数值'),
                (chart, ['--uncertainty-minutes', '121'], '0 至 120 分钟之间'),
                (chart, ['--time-basis', 'apparent-solar', '--lat', '31.23'], '需要出生地经度'),
                (standalone, ['--lon', '121.47'], '--lat')):
            with self.subTest(extra=extra):
                result = subprocess.run(command + extra, text=True, capture_output=True, timeout=15)
                self.assertEqual(2, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertIn(reason, result.stderr)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_cli_keeps_center_when_optional_intervals_cross_utc_year_limit(self):
        command = [
            sys.executable, '-B', str(ROOT/'scripts/build_chart.py'),
            '--solar', '1901-01-01', '--hour', '08:05', '--sex', '男',
            '--lat', '35', '--lon', '120', '--uncertainty-minutes', '10',
            '--analysis-year', '1920',
        ]
        flags = {
            '--enumerate-scenarios': 'scenarios',
            '--qizheng-sensitivity-evidence': 'qizheng_sensitivity',
        }
        baseline = json.loads(subprocess.check_output(command+['--format', 'json'], text=True))
        for selected in [*((flag,) for flag in flags), tuple(flags)]:
            with self.subTest(selected=selected):
                snapshot = json.loads(subprocess.check_output(
                    command + ['--format', 'json', *selected], text=True))
                expected_degradation = {'ziwei'}.union(flags[flag] for flag in selected)
                self.assertEqual(expected_degradation, snapshot['degradation'].keys())
                for key in ('bazi', 'ziwei', 'qizheng'):
                    self.assertIsNotNone(snapshot[key])
                    self.assertEqual(baseline[key], snapshot[key])
                self.assertEqual('withheld', snapshot['qizheng_rule_reading']['status'])
                self.assertEqual('withheld', snapshot['ziwei']['life_reading']['stage_relationship']['status'])
                self.assertIsNone(snapshot['bazi_scenario_comparison'])
                self.assertNotIn('ziwei_scenario_comparison', snapshot)
                self.assertTrue(any('仅中心时刻候选' in item for item in snapshot['warnings']))
                for flag in selected:
                    key = flags[flag]
                    self.assertIsNone(snapshot[key])
                    reason = snapshot['degradation'][key]
                    self.assertIn('1901–2099', reason)
                    self.assertIn(reason, snapshot['warnings'])
        output = subprocess.check_output(command+list(flags), text=True)
        self.assertIn('未执行出生时刻候选枚举', output)
        self.assertIn('未执行七政时间敏感性比较', output)
        self.assertIn('仅中心时刻候选', output)

if __name__=='__main__': unittest.main()
