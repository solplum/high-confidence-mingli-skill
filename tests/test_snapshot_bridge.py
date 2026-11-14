"""Integration checks of computed snapshots, not predictive accuracy."""
from datetime import date, datetime, timezone
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_chart
from pai_pan_qizheng import equation_of_time_minutes, jd_from_utc

ARGS = ['--solar','2000-05-15','--hour','12:00','--sex','男','--lat','31.23','--lon','121.47','--age-year','2026']

class SnapshotBridgeTests(unittest.TestCase):
    def test_json_degrades_without_ziwei_and_keeps_provenance(self):
        out=io.StringIO()
        with patch.object(build_chart,'run_ziwei',return_value=(None,'test dependency unavailable')), contextlib.redirect_stdout(out):
            build_chart.main(ARGS+['--format','json'])
        s=json.loads(out.getvalue())
        self.assertIsNone(s['ziwei'])
        self.assertIn('unavailable',s['degradation']['ziwei'])
        self.assertEqual(s['bazi']['pillars']['day'][:2],['癸','酉'])
        self.assertEqual(s['provenance']['resolved_age_year'],2026)
        self.assertIn('pai_pan_bazi.py',s['provenance']['source_sha256'])
        self.assertIn('pai_pan_ziwei/vendor/algorithm.ts',s['provenance']['source_sha256'])

    def render_at_year(self, year, extra):
        class RuntimeDate(date):
            @classmethod
            def today(cls):
                return cls(year, 12, 31)
        class RuntimeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(year, 12, 31, tzinfo=tz)
        out = io.StringIO()
        with patch.object(build_chart, 'date', RuntimeDate), patch.object(build_chart.bazi, 'datetime', RuntimeDatetime), contextlib.redirect_stdout(out):
            build_chart.main(ARGS[:-2] + extra + ['--format', 'json'])
        return out.getvalue()

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_global_analysis_year_is_byte_stable_across_runtime_years(self):
        a = self.render_at_year(2026, ['--analysis-year', '2025'])
        b = self.render_at_year(2027, ['--analysis-year', '2025'])
        self.assertEqual(a, b)
        s = json.loads(a)
        self.assertEqual(s['bazi']['current_year'], 2025)
        self.assertEqual(s['bazi']['liunian_years'][-1], 2025)
        self.assertEqual(s['bazi']['current_gz'], build_chart.bazi.liunian_gz(2025))
        self.assertEqual(s['ziwei']['input']['ageYear'], 2025)
        self.assertEqual(s['provenance']['resolved_bazi_year'], 2025)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_default_and_legacy_year_semantics_preserved(self):
        for year in (2026, 2027):
            s = json.loads(self.render_at_year(year, []))
            self.assertEqual(s['bazi']['current_year'], year)
            self.assertEqual(s['ziwei']['input']['ageYear'], year)
            legacy = json.loads(self.render_at_year(year, ['--age-year', '2025']))
            self.assertEqual(legacy['bazi']['current_year'], year)
            self.assertEqual(legacy['ziwei']['input']['ageYear'], 2025)

    def test_global_year_rejects_conflict_and_invalid_range(self):
        for extra in (['--analysis-year', '2025'], ['--analysis-year', '1999'], ['--analysis-year', '10000']):
            with self.subTest(extra=extra), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                build_chart.main(ARGS + extra)

    def test_global_year_allows_matching_legacy_flag(self):
        out = io.StringIO()
        with patch.object(build_chart, 'run_ziwei', return_value=(None, 'unavailable')), contextlib.redirect_stdout(out):
            build_chart.main(ARGS + ['--analysis-year', '2026', '--format', 'json'])
        s = json.loads(out.getvalue())
        self.assertEqual(s['bazi']['current_year'], 2026)
        self.assertEqual(s['provenance']['resolved_age_year'], 2026)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_actual_combined_snapshot_and_default_text(self):
        cmd=[sys.executable,str(ROOT/'scripts/build_chart.py')]+ARGS
        a=subprocess.run(cmd+['--format','json'],check=True,text=True,capture_output=True)
        s=json.loads(a.stdout)
        self.assertEqual(s['ziwei']['input']['ageYear'],2026)
        self.assertEqual(s['ziwei']['chart']['currentAge'],27)
        self.assertEqual(s['degradation']['ziwei'],None)
        self.assertEqual(len(s['ziwei']['chart']['palaces']),12)
        b=subprocess.run(cmd,check=True,text=True,capture_output=True)
        self.assertIn('# 命盘数据',b.stdout)
        self.assertIn('公历目标年 2026 年',b.stdout)
        self.assertNotIn('紫微数据缺失',b.stdout)
        self.assertIn('将三引擎盘面输出到标准输出', b.stdout)
        self.assertNotIn('存放于', b.stdout)
        self.assertIn('解释及其条件、反证和未决项见本次分析记录', b.stdout)
        self.assertNotIn('解释器种子', b.stdout)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_civil_without_coordinates_preserves_bazi_and_ziwei_candidates(self):
        command = [sys.executable, str(ROOT/'scripts/build_chart.py'), '--solar', '1987-03-06',
                   '--hour', '11:00', '--sex', '男', '--timezone', 'Asia/Shanghai',
                   '--analysis-year', '2026']
        requested = command + ['--format', 'json', '--enumerate-scenarios', '--uncertainty-minutes', '2']
        partial = json.loads(subprocess.check_output(requested, text=True))
        complete = json.loads(subprocess.check_output(requested + ['--lat', '31.23', '--lon', '121.47'], text=True))
        for key in ('bazi', 'bazi_core_reading', 'ziwei', 'scenarios', 'bazi_scenario_comparison', 'ziwei_scenario_comparison'):
            self.assertEqual(partial[key], complete[key], key)
        self.assertIsNone(partial['input']['lat'])
        self.assertIsNone(partial['input']['lon'])
        self.assertIsNone(partial['time']['apparent_solar'])
        self.assertIsNone(partial['time']['mean_solar'])
        self.assertEqual(partial['time']['chart_clock'], complete['time']['chart_clock'])
        self.assertEqual(partial['qizheng']['bodies'], complete['qizheng']['bodies'])
        for field in ('ming_du', 'ming_gong', 'day_night', 'en_yong'):
            self.assertIsNone(partial['qizheng'][field])
        self.assertEqual(partial['qizheng_rule_reading']['status'], 'withheld')
        candidates = partial['ziwei_scenario_comparison']['candidates']
        self.assertEqual(len(candidates), 2)
        for candidate in candidates:
            panel = build_chart.ziwei_life_reading.analyze_snapshot(partial, ziwei_candidate_id=candidate['id'])
            self.assertEqual(panel['case_judgments'], candidate['case_judgments'])
            self.assertEqual(panel['stage_relationship'], candidate['stage_relationship'])
        text = subprocess.check_output(command, text=True)
        self.assertIn('| 真太阳时 | 未计算 |', text)
        self.assertIn('**立命宫**：缺经纬度，未计算。', text)
        self.assertIn('| 日 |', text)

    def test_coordinate_requirements_for_clock_and_invalid_values(self):
        args = ARGS[:6] + ['--format', 'json']
        for extra, expected in ((['--time-basis', 'mean-solar'], '需要出生地经度'),
                                (['--time-basis', 'apparent-solar'], '需要出生地经度'),
                                (['--lon', 'nan'], '必须为有限数值'),
                                (['--lat', '91'], '纬度/经度超出范围')):
            error = io.StringIO()
            with self.subTest(extra=extra), contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                build_chart.main(args + extra)
            self.assertIn(expected, error.getvalue())
        out = io.StringIO()
        with patch.object(build_chart, 'run_ziwei', return_value=(None, 'unavailable')), contextlib.redirect_stdout(out):
            build_chart.main(args + ['--time-basis', 'mean-solar', '--lon', '90'])
        partial = json.loads(out.getvalue())
        self.assertEqual(partial['time']['chart_clock'], '2000-05-15T10:00:00')
        self.assertIsNone(partial['qizheng']['ming_du'])

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_solar_snapshot_refuses_stale_birth_offset_and_longitude(self):
        command = [sys.executable, str(ROOT/'scripts/build_chart.py'), '--solar', '1997-02-16',
                   '--hour', '21:00', '--sex', '男', '--lon', '120', '--analysis-year', '2026',
                   '--format', 'json']
        normal = command + ['--time-basis', 'mean-solar', '--utc-offset']
        original = json.loads(subprocess.check_output(normal + ['8'], text=True))
        corrected = json.loads(subprocess.check_output(normal + ['9'], text=True))

        def reading(snapshot):
            return build_chart.ziwei_life_reading.analyze_snapshot(snapshot)

        def branch(snapshot):
            return reading(snapshot)['case_judgments']['modules']['ZW-RC02']['selected_branch']

        self.assertEqual(branch(original), 'tiantong_copresent')
        self.assertEqual(branch(corrected), 'tiantong_absent')
        for key, value, reason in (('utc_offset', 9, '出生固定UTC偏移'),
                                   ('lon', 105, '原出生民用瞬间、经度')):
            stale = deepcopy(original)
            stale['input'][key] = value
            if key == 'lon':
                del stale['time']['mean_solar']
            with self.subTest(key=key):
                panel = reading(stale)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn(reason, panel['input_errors'][0])
                self.assertIsNone(branch(stale))
        legacy = deepcopy(original)
        for key in ('timezone', 'utc_offset', 'lon'):
            del legacy['input'][key]
        for key in ('mean_solar', 'iana_zone', 'fold', 'instant_bj'):
            del legacy['time'][key]
        self.assertEqual(branch(legacy), 'tiantong_copresent')
        civil = json.loads(subprocess.check_output(command, text=True))
        civil['input']['utc_offset'] = 9
        self.assertEqual(branch(civil), 'tiantong_copresent')

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_civil_snapshot_preserves_natal_facts_when_timezone_source_conflicts(self):
        command = [sys.executable, '-B', str(ROOT/'scripts/build_chart.py'), '--solar', '1989-12-07',
                   '--hour', '11:45', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json']
        original = json.loads(subprocess.check_output(command, text=True))
        analyze = build_chart.ziwei_life_reading.analyze_snapshot
        intact = analyze(original, requested_analysis_year=2026)
        self.assertIn('birth_time_bounds', intact)

        original['provenance']['timezone_source'] = dict(kind='host_iana_tzif', zone='Asia/Tokyo')
        conflicted = analyze(original, requested_analysis_year=2026)
        self.assertNotIn('birth_time_bounds', conflicted)
        self.assertIn('时区来源', conflicted['birth_time_error'])
        self.assertEqual(conflicted['stage_query_scope'], intact['stage_query_scope'])
        self.assertEqual(conflicted['domains'], intact['domains'])

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_true_solar_snapshot_checks_saved_iana_fold_and_engine_eot(self):
        command = [sys.executable, str(ROOT/'scripts/build_chart.py'), '--solar', '2024-11-03',
                   '--hour', '01:30', '--sex', '女', '--lon', '-75', '--timezone', 'America/New_York',
                   '--fold', '0', '--analysis-year', '2026', '--time-basis', 'apparent-solar',
                   '--dut1-seconds', '0.8', '--format', 'json']
        original = json.loads(subprocess.check_output(command, text=True))
        analyze = build_chart.ziwei_life_reading.analyze_snapshot
        self.assertEqual(analyze(original)['status'], 'conditional')
        other_command = command.copy()
        other_command[other_command.index('--fold') + 1] = '1'
        other = json.loads(subprocess.check_output(other_command, text=True))
        other_panel = analyze(other)
        self.assertEqual(other_panel['status'], 'conditional')
        self.assertNotEqual(original['ziwei']['chart']['birthInfo']['hour'], other['ziwei']['chart']['birthInfo']['hour'])
        for section, key, value, reason in (
                ('input', 'timezone', 'America/Chicago', '原出生时区与time.iana_zone冲突'),
                ('input', 'fold', 1, '原出生时区fold与time.fold冲突'),
                ('time', 'instant_bj', '2024-11-03T14:30:00+08:00', '出生瞬间冲突'),
                ('input', 'lon', -90, 'time.apparent_solar与原出生民用瞬间')):
            with self.subTest(section=section, key=key):
                stale = deepcopy(original)
                stale[section][key] = value
                del stale['time']['mean_solar']
                panel = analyze(stale)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn(reason, panel['input_errors'][0])
        for legacy_labels in (False, True):
            with self.subTest(legacy_labels=legacy_labels):
                stale = deepcopy(other)
                stale['input']['fold'] = 0
                if legacy_labels:
                    del stale['time']['fold']
                    del stale['time']['iana_zone']
                else:
                    stale['time']['fold'] = 0
                panel = analyze(stale)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn('fold与time.civil的UTC偏移冲突', panel['input_errors'][0])
        older_tzif = deepcopy(original)
        older_tzif['provenance']['timezone_source']['tzif_sha256'] = 'f' * 64
        self.assertEqual(analyze(older_tzif), analyze(original))

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
    def test_exact_apparent_solar_replays_original_dut1_when_stored_eot_and_chart_are_stale(self):
        jd = jd_from_utc(datetime(1980, 12, 24, 9, tzinfo=timezone.utc))
        lon = 120 - (equation_of_time_minutes(jd) + equation_of_time_minutes(jd + 0.9 / 86400)) / 8
        cmd = [sys.executable, '-B', str(ROOT/'scripts/build_chart.py'), '--solar', '1980-12-24',
               '--hour', '17:00', '--sex', '男', '--lon', str(lon), '--analysis-year', '2026',
               '--time-basis', 'apparent-solar', '--format', 'json', '--dut1-seconds']
        original, other = [json.loads(subprocess.check_output([*cmd, value], text=True)) for value in ('0', '0.9')]
        read = build_chart.ziwei_life_reading.analyze_snapshot
        self.assertEqual([snapshot['ziwei']['chart']['birthInfo']['hour'] for snapshot in (original, other)], [9, 8])
        self.assertTrue(all(read(snapshot)['status'] == 'conditional' for snapshot in (original, other)))
        original['ziwei'] = other['ziwei']
        for key in ('chart_clock', 'apparent_solar'):
            original['time'][key] = other['time'][key]
        for eot in (other['qizheng']['eot_minutes'], None):
            with self.subTest(eot=eot):
                original['qizheng']['eot_minutes'] = eot
                panel = read(original)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn('time.apparent_solar与原出生民用瞬间', panel['input_errors'][0])
                self.assertEqual(panel['domains'], [])
        del original['input']['dut1_seconds']
        self.assertEqual(read(original)['status'], 'withheld')
        other['input']['qizheng_profile'] = 'legacy-v1'
        panel = read(other)
        self.assertEqual(panel['status'], 'withheld')
        self.assertIn('DUT1与legacy-v1', panel['input_errors'][0])

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_apparent_candidates_use_the_same_recorded_dut1_as_center(self):
        from bazi_scenario_reading import birth_luck_tables

        jd = jd_from_utc(datetime(1980, 12, 24, 9, tzinfo=timezone.utc))
        lon = 120 - (equation_of_time_minutes(jd) + equation_of_time_minutes(jd + 0.9 / 86400)) / 8
        command = [sys.executable, '-B', str(ROOT/'scripts/build_chart.py'), '--solar', '1980-12-24',
                   '--hour', '17:00', '--sex', '男', '--lon', str(lon), '--analysis-year', '2026',
                   '--time-basis', 'apparent-solar', '--format', 'json',
                   '--enumerate-scenarios', '--uncertainty-minutes', '0.000001']
        zero, selected = [json.loads(subprocess.check_output([*command, '--dut1-seconds', value], text=True))
                          for value in ('0', '0.9')]
        read = build_chart.ziwei_life_reading.analyze_snapshot
        for snapshot, index, hour in ((zero, 9, '丁酉'), (selected, 8, '丙申')):
            variant, = snapshot['scenarios']['variants']
            self.assertEqual(snapshot['ziwei']['input']['shichenIndex'], index)
            self.assertEqual(variant['fields']['ziwei.shichen_index'], index)
            self.assertEqual(''.join(variant['fields']['bazi.hour']), hour)
            self.assertEqual(snapshot['scenarios']['stable_fields'], {})
            self.assertEqual(variant['intervals'], [])
            ziwei_candidate, = snapshot['ziwei_scenario_comparison']['candidates']
            panel = read(snapshot, ziwei_candidate_id=ziwei_candidate['id'])
            self.assertEqual(panel['birth_scenario']['input']['shichen_index'], index)
            self.assertEqual(birth_luck_tables(snapshot)['tables'][0]['analysis']['facts']['hour']['pillar'], hour)
        fallback = deepcopy(selected)
        del fallback['input']['dut1_seconds']
        self.assertEqual(birth_luck_tables(fallback), birth_luck_tables(selected))
        candidate_id = selected['ziwei_scenario_comparison']['candidates'][0]['id']
        self.assertEqual(read(fallback, ziwei_candidate_id=candidate_id),
                         read(selected, ziwei_candidate_id=candidate_id))
        for key in ('scenarios', 'bazi_scenario_comparison', 'ziwei_scenario_comparison'):
            selected[key] = zero[key]
        with self.assertRaises(ValueError):
            birth_luck_tables(selected)
        with self.assertRaisesRegex(ValueError, '按原参数重建'):
            read(selected, ziwei_candidate_id=candidate_id)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_ziwei_rejects_invalid_format(self):
        r=subprocess.run(['node','--import','tsx','pai_pan.ts','--format','xml'],cwd=ROOT/'scripts/pai_pan_ziwei',text=True,capture_output=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('--format',r.stderr)

if __name__=='__main__':
    unittest.main()
