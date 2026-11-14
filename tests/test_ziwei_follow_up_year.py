"""Verify current-stage replays against native snapshots from the requested year."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ziwei_life_reading import analyze_native_shichen, analyze_snapshot


@unittest.skipUnless(shutil.which('node') and (ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(),
                     'Node and locked Ziwei dependencies required')
class ZiweiFollowUpYearTests(unittest.TestCase):
    def run_json(self, command):
        return json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))

    def snapshot(self, year, kind='exact'):
        if kind == 'band':
            return self.run_json([sys.executable, '-B', 'scripts/ziwei_birth_time_candidates.py',
                                  '--birth-date', '1986-12-23', '--start', '19:10', '--end', '23:20',
                                  '--sex', '男', '--analysis-year', str(year), '--utc-offset', '8'])
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-12-23', '--hour', '19:30',
               '--sex', '男', '--analysis-year', str(year), '--utc-offset', '8', '--format', 'json']
        if kind == 'enumerated':
            cmd += ['--uncertainty-minutes', '1', '--enumerate-scenarios']
        return self.run_json(cmd)

    def dynamic(self, birth, index, target):
        return self.run_json(['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth,
                              '--birth-year', birth[:4], '--shichen-index', str(index), '--sex', '男',
                              '--target-date', target, '--target-time-index', '0',
                              '--source-label', 'synthetic-follow-up-year'])

    def current(self, panel):
        return next(row for row in panel['stage_relationship']['stages'] if row['legacy_stage']['current'])

    def test_requested_year_matches_fresh_native_across_snapshot_types(self):
        target = '2029-11-09'
        facts = self.dynamic('1986-12-23', 10, target)
        for kind, identity in (('exact', None), ('enumerated', 'ziwei-candidate-1'), ('band', 'ziwei-band-10')):
            with self.subTest(kind=kind):
                saved = self.snapshot(2026, kind)
                genuine = self.snapshot(2029, kind)
                original = deepcopy(saved)
                query = dict(ziwei_candidate_id=identity, expected_target_date=target,
                             expected_target_time_index=0)
                old = analyze_snapshot(saved, facts, **query)
                verified = analyze_snapshot(saved, facts, requested_analysis_year=2029, **query)
                fresh = analyze_snapshot(genuine, facts, **query)
                self.assertEqual(saved, original)
                self.assertEqual(old['stage_query_scope']['status'], 'analysis_year_mismatch')
                self.assertEqual(self.current(old)['legacy_stage']['domain'], '田宅')
                self.assertEqual(self.current(old)['modules']['ZW-ST01']['selected_branch'], 'tianfu_progress')
                self.assertEqual(verified['stage_query_scope']['status'], 'verified')
                self.assertEqual(verified['stage_query_scope']['panel_analysis_year'], 2029)
                self.assertEqual(self.current(verified)['legacy_stage']['domain'], '官禄')
                self.assertEqual(fresh['stage_query_scope'], dict(
                    status='verified', snapshot_analysis_year=2029, panel_analysis_year=2029,
                    requested_analysis_year=None, query_civil_year=2029, aligned_to_query=True))
                self.assertEqual({key: value for key, value in verified.items() if key != 'stage_query_scope'},
                                 {key: value for key, value in fresh.items() if key != 'stage_query_scope'})
                self.assertEqual(old['domains'], verified['domains'])
                self.assertEqual(old['dynamic'], verified['dynamic'])
                if kind == 'band':
                    with TemporaryDirectory() as directory:
                        path = Path(directory) / 'band.json'
                        path.write_text(json.dumps(saved), encoding='utf-8')
                        panel = self.run_json([sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                                               '--snapshot', str(path), '--ziwei-candidate', identity,
                                               '--analysis-year', '2029'])
                    self.assertEqual(self.current(panel), self.current(fresh))
                    self.assertEqual(panel['dynamic']['status'], 'not_requested')

    def test_year_replay_uses_original_civil_birth_year_after_solar_rollover(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-12-31', '--hour', '23:59',
               '--sex', '男', '--utc-offset', '8', '--lon', '135', '--time-basis', 'mean-solar',
               '--format', 'json', '--analysis-year']
        saved = self.run_json(cmd + ['2026'])
        fresh = analyze_snapshot(self.run_json(cmd + ['2029']))
        result = analyze_snapshot(saved, requested_analysis_year=2029)
        self.assertEqual(result['stage_query_scope']['status'], 'verified')
        self.assertEqual(saved['ziwei']['input']['solar'], '1987-01-01')
        self.assertEqual(result['stage_relationship']['stage_contract']['birth_year'], 1986)
        self.assertEqual(result['stage_relationship']['stage_contract']['current_age'], 44)
        self.assertEqual({key: value for key, value in result.items() if key != 'stage_query_scope'}, fresh)

    def test_requested_year_rebuilds_only_absent_redundant_stage_fields(self):
        snapshot = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
                                  '--hour', '02:00', '--sex', '男', '--utc-offset', '8',
                                  '--analysis-year', '2025', '--format', 'json'])
        incomplete = deepcopy(snapshot)
        chart = incomplete['ziwei']['chart']
        self.assertEqual(chart['wuxingJu'], 6)
        del chart['currentAge'], chart['currentDaXianIndex']
        saved = deepcopy(incomplete)
        for year, status in ((1975, 'before_first_stage'), (1976, 'active'),
                             (2095, 'active'), (2096, 'after_last_stage')):
            with self.subTest(year=year):
                checked = analyze_snapshot(incomplete, requested_analysis_year=year)
                complete = analyze_snapshot(snapshot, requested_analysis_year=year)
                self.assertEqual(checked['stage_query_scope']['status'], 'verified')
                self.assertEqual(checked['stage_query_scope']['replayed_current_fields'],
                                 ['currentAge', 'currentDaXianIndex'])
                self.assertEqual(checked['stage_relationship'], complete['stage_relationship'])
                self.assertEqual(checked['stage_relationship']['stage_contract']['current_status'], status)
        self.assertEqual(incomplete, saved)
        self.assertEqual(analyze_snapshot(incomplete)['modules']['ZW-T02']['status'], 'withheld')

        chart['currentAge'] = 54  # Correct age for the original year is 55.
        self.assertEqual(analyze_snapshot(incomplete, requested_analysis_year=1976)['stage_query_scope']['status'],
                         'withheld')
        del chart['currentAge'], chart['daXians']
        self.assertEqual(analyze_snapshot(incomplete, requested_analysis_year=1976)['stage_query_scope']['status'],
                         'withheld')

    def test_birth_candidate_in_later_civil_year_reports_why_to_rebuild(self):
        command = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-12-31', '--hour', '23:59',
                   '--sex', '男', '--utc-offset', '8', '--uncertainty-minutes', '2', '--enumerate-scenarios',
                   '--format', 'json', '--analysis-year']
        saved = self.run_json([*command, '1986'])
        old_comparison = saved['ziwei_scenario_comparison']
        before_midnight, after_midnight = old_comparison['candidates']
        self.assertEqual(old_comparison['analysis_year'], 1986)
        self.assertIsNotNone(before_midnight['chart'])
        self.assertEqual(after_midnight['input']['birth_year'], 1987)
        self.assertIsNone(after_midnight['chart'])
        self.assertIsNone(after_midnight['stage_relationship'])
        reason = after_midnight['degradation']
        self.assertIn('原分析年 1986 早于该候选的民用出生年 1987', reason)
        self.assertIn('--analysis-year 1987', reason)
        self.assertNotIn('npm ci', reason)

        target = '2029-11-09'
        facts = self.dynamic('1987-01-01', 0, target)
        fresh = self.run_json([*command, '2029'])
        fresh_comparison = fresh['ziwei_scenario_comparison']
        self.assertEqual([row['input'] for row in fresh_comparison['candidates']],
                         [row['input'] for row in old_comparison['candidates']])
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'birth.json'
            dynamic = Path(directory) / 'dynamic.json'
            dynamic.write_text(json.dumps(facts), encoding='utf-8')
            read = [sys.executable, '-B', 'scripts/ziwei_life_reading.py', '--snapshot', str(path),
                    '--ziwei-candidate', after_midnight['id'], '--analysis-year', '2029', '--dynamic', str(dynamic),
                    '--expected-target-date', target, '--expected-target-time-index', '0']
            path.write_text(json.dumps(saved), encoding='utf-8')
            failed = subprocess.run(read, cwd=ROOT, capture_output=True, text=True, timeout=45)
            self.assertEqual(failed.returncode, 2)
            self.assertIn(reason, failed.stderr)

            path.write_text(json.dumps(fresh), encoding='utf-8')
            panel = self.run_json(read)
            self.assertEqual(panel['stage_query_scope']['status'], 'verified')
            self.assertEqual(self.current(panel)['legacy_stage']['domain'], '田宅')
            self.assertEqual(panel['dynamic']['status'], 'admitted')
            spouse = next(row for row in panel['domains'] if row['domain'] == '夫妻')
            self.assertEqual([star['name'] for star in spouse['facts'] if star['type'] == 'major'], ['紫微', '七杀'])

    def test_requested_year_gate_preserves_independent_dynamics_when_replay_fails(self):
        saved = self.snapshot(2026)
        facts = self.dynamic('1986-12-23', 10, '2029-11-09')
        query = dict(expected_target_date='2029-11-09', expected_target_time_index=0)
        initial = analyze_snapshot(saved, facts, **query)
        with patch('ziwei_life_reading._chart_for_analysis_year', side_effect=ValueError('synthetic replay failure')):
            result = analyze_snapshot(saved, facts, requested_analysis_year=2029, **query)
        self.assertEqual(result['stage_query_scope']['status'], 'withheld')
        self.assertEqual(result['stage_query_scope']['reason'], 'synthetic replay failure')
        self.assertEqual(result['domains'], initial['domains'])
        self.assertEqual(result['dynamic'], initial['dynamic'])
        self.assertEqual(result['stage_relationship'], initial['stage_relationship'])
        self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')

    def test_requested_year_and_annual_case_keep_independently_replayed_birth_date(self):
        snapshot = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
                                  '--hour', '02:00', '--sex', '男', '--utc-offset', '8',
                                  '--analysis-year', '2026', '--format', 'json'])
        target = '2025-12-31'
        facts = self.dynamic('1971-01-06', 1, target)
        options = dict(requested_analysis_year=2025, expected_target_date=target,
                       expected_target_time_index=0)
        baseline = analyze_snapshot(snapshot, facts, **options)
        self.assertEqual(self.current(baseline)['legacy_stage']['domain'], '官禄')
        self.assertEqual(baseline['case_judgments']['modules']['ZW-RC03']['selected_branch'],
                         'proactive_application_fit')

        archived = deepcopy(snapshot)
        born = archived['ziwei']['chart']['birthInfo']
        born['month'] = None
        del born['day']
        source = deepcopy(archived)
        restored = analyze_snapshot(archived, facts, **options)
        self.assertEqual(archived, source)
        self.assertEqual(restored['dynamic'].pop('unverified_static_fields'),
                         ['chart.birthInfo.month', 'chart.birthInfo.day'])
        self.assertEqual(restored, baseline)

        born['month'] = 2
        inconsistent = analyze_snapshot(archived, facts, **options)
        self.assertIn('已存出生日期分量与原出生资料复盘不一致', inconsistent['input_errors'][0])
        self.assertEqual(inconsistent['stage_query_scope']['status'], 'withheld')
        self.assertEqual(inconsistent['dynamic']['status'], 'withheld')
        with self.assertRaisesRegex(ValueError, '已存出生日期分量与原出生资料复盘不一致'):
            analyze_snapshot(archived, facts, expected_target_civil=target + 'T00:00:00+08:00', **options)

    def test_verified_year_and_month_survive_missing_saved_natal_annotations(self):
        birth_command = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-06-02',
                         '--hour', '17:01', '--sex', '男', '--utc-offset', '8',
                         '--format', 'json', '--analysis-year', '2026']
        saved = self.run_json(birth_command)
        target = '2032-11-09'
        facts = self.dynamic('1987-06-02', 9, target)
        query = dict(requested_analysis_year=2032, expected_target_date=target, expected_target_time_index=0)
        baseline = analyze_snapshot(saved, facts, **query)
        self.assertEqual(baseline['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
        self.assertTrue(any(row['id'] == 'monthly.禄' and row['fact']['domain'] == '夫妻' and
                            row['status'] == 'conditional' for row in baseline['transformations']))

        for key in ('shenGongBranch', 'yearStem', 'null_year_stem', 'lunarInfo'):
            with self.subTest(key=key):
                snapshot = deepcopy(saved)
                chart = snapshot['ziwei']['chart']
                if key == 'yearStem':
                    del chart['lunarInfo'][key]
                    missing = 'chart.lunarInfo.yearStem'
                elif key == 'null_year_stem':
                    chart['lunarInfo']['yearStem'] = None
                    missing = 'chart.lunarInfo.yearStem'
                else:
                    del chart[key]
                    missing = 'chart.' + key
                original = deepcopy(snapshot)
                known_branch = analyze_native_shichen(snapshot['ziwei'], '1987-06-02', '酉', '男', facts,
                                                      utc_offset=8, **query)
                for panel in (analyze_snapshot(snapshot, facts, **query), known_branch):
                    self.assertEqual(panel['dynamic']['status'], 'admitted')
                    self.assertEqual(panel['dynamic']['unverified_static_fields'], [missing])
                    self.assertEqual(panel['domains'], baseline['domains'])
                    self.assertEqual(panel['dynamic']['layers'], baseline['dynamic']['layers'])
                    if key == 'shenGongBranch':
                        self.assertEqual(panel['modules']['ZW-S01']['status'], 'withheld')
                        self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
                    else:
                        self.assertEqual(set(panel['natal_transform_errors']), set('禄权科忌'))
                        self.assertFalse(any(row['layer'] == 'natal' for row in panel['transformations']))
                        self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], 'withheld')
                    if key != 'lunarInfo':
                        self.assertEqual(panel['stage_query_scope']['status'], 'verified')
                        self.assertEqual(self.current(panel)['legacy_stage'], self.current(baseline)['legacy_stage'])
                self.assertEqual(snapshot, original)

        enumerated = self.run_json([*birth_command, '--enumerate-scenarios', '--uncertainty-minutes', '1'])
        candidate, = enumerated['ziwei_scenario_comparison']['candidates']
        del candidate['chart']['lunarInfo']['yearStem']
        enumerated_result = analyze_snapshot(enumerated, facts, ziwei_candidate_id=candidate['id'], **query)
        self.assertEqual(enumerated_result['dynamic']['layers'], baseline['dynamic']['layers'])
        self.assertEqual(enumerated_result['dynamic']['unverified_static_fields'], ['chart.lunarInfo.yearStem'])
        self.assertEqual(enumerated_result['stage_query_scope']['status'], 'verified')
        self.assertEqual(set(enumerated_result['natal_transform_errors']), set('禄权科忌'))

        snapshot = deepcopy(saved)
        del snapshot['ziwei']['chart']['shenGongBranch']
        wrong_source = deepcopy(facts)
        del wrong_source['native_wrapper_snapshot']['chart']['shenGongBranch']
        invalid = analyze_snapshot(snapshot, wrong_source, **query)
        self.assertEqual(invalid['dynamic']['status'], 'withheld')
        self.assertEqual(invalid['domains'], baseline['domains'])
        self.assertEqual(invalid['stage_query_scope']['status'], 'verified')

        year_stem = saved['ziwei']['chart']['lunarInfo']['yearStem']
        for invalid in ('不明', (year_stem + 1) % 10, float(year_stem)):
            with self.subTest(invalid_year_stem=invalid):
                snapshot = deepcopy(saved)
                snapshot['ziwei']['chart']['lunarInfo']['yearStem'] = invalid
                explicit_conflict = analyze_snapshot(snapshot, facts, **query)
                self.assertEqual(explicit_conflict['dynamic']['status'], 'withheld')
                self.assertEqual(explicit_conflict['domains'], [])

    def test_duplicate_birth_header_recovery_preserves_relationship_and_rest_at_stage_boundary(self):
        saved = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-06-02',
                               '--hour', '17:01', '--sex', '男', '--utc-offset', '8',
                               '--analysis-year', '2026', '--format', 'json'])
        for target, domain in (('2033-01-01', '财帛'), ('2040-12-31', '财帛'), ('2041-01-01', '疾厄')):
            with self.subTest(target=target):
                facts = self.dynamic('1987-06-02', 9, target)
                request = dict(requested_analysis_year=int(target[:4]), expected_target_date=target,
                               expected_target_time_index=0)
                reference = analyze_snapshot(saved, facts, **request)
                self.assertEqual(self.current(reference)['legacy_stage']['domain'], domain)
                self.assertEqual(reference['dynamic']['status'], 'admitted')
                self.assertEqual(reference['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
                self.assertEqual(reference['modules']['ZW-D04']['status'], 'conditional')
                if target == '2033-01-01':
                    self.assertTrue(any(row['id'] == 'monthly.权' and row['status'] == 'conditional' and
                                        row['fact']['domain'] in ('夫妻', '福德', '疾厄')
                                        for row in reference['transformations']))
                for scope in ('exact', 'shichen'):
                    source = deepcopy(saved if scope == 'exact' else saved['ziwei'])
                    chart = source['ziwei']['chart'] if scope == 'exact' else source['chart']
                    read = analyze_snapshot if scope == 'exact' else analyze_native_shichen
                    options = () if scope == 'exact' else ('1987-06-02', '酉', '男')
                    baseline = read(source, *options, facts, **request)
                    for omission in ('gender', 'header', 'null'):
                        with self.subTest(scope=scope, omission=omission):
                            chart['birthInfo'] = deepcopy(saved['ziwei']['chart']['birthInfo'])
                            if omission == 'gender':
                                del chart['birthInfo']['gender']
                            elif omission == 'header':
                                del chart['birthInfo']
                            else:
                                chart['birthInfo'] = None
                            before = deepcopy(source)
                            restored = read(source, *options, facts, **request)
                            self.assertEqual(restored['dynamic'].pop('unverified_static_fields'),
                                             ['chart.birthInfo.gender' if omission == 'gender' else 'chart.birthInfo'])
                            self.assertEqual(restored, baseline)
                            self.assertEqual(source, before)

        for bad in ('', {'gender': 'female'}, {'gender': 'unknown'}, {'hour': True}):
            with self.subTest(bad=bad):
                broken = deepcopy(saved)
                broken['ziwei']['chart']['birthInfo'] = bad
                result = analyze_snapshot(broken, facts, **request)
                self.assertEqual(result['stage_query_scope']['status'], 'withheld')
                self.assertEqual(result['dynamic']['status'], 'withheld')
                self.assertEqual(result['domains'], [])

    def test_enumerated_candidate_uses_verified_hour_when_raw_duplicate_is_absent(self):
        snapshot = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1967-06-17',
                                  '--hour', '03:01', '--sex', '男', '--utc-offset', '8', '--format', 'json',
                                  '--analysis-year', '2026', '--uncertainty-minutes', '2', '--enumerate-scenarios'])
        earlier, selected = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual([row['input']['shichen_index'] for row in (earlier, selected)], [1, 2])
        target = '2031-11-12'
        facts = self.dynamic('1967-06-17', 2, target)
        query = dict(ziwei_candidate_id=selected['id'], requested_analysis_year=2031)
        point = dict(expected_target_date=target, expected_target_time_index=0)
        static = analyze_snapshot(snapshot, **query)
        expected = analyze_snapshot(snapshot, facts, **query, **point)
        self.assertEqual(expected['dynamic']['status'], 'admitted')
        self.assertEqual(expected['stage_query_scope']['status'], 'verified')
        self.assertEqual(self.current(expected)['modules']['ZW-ST01']['selected_branch'], 'tianfu_progress')
        self.assertEqual(expected['stage_relationship']['relationship']['selected_branch'], 'sun_giant_gate_stability')
        self.assertEqual(expected['case_judgments']['modules']['ZW-RC02']['selected_branch'], 'tiantong_absent')
        expected['dynamic']['unverified_static_fields'] = ['chart.birthInfo.hour']

        header = selected['chart']['birthInfo']
        for omission in ('absent', 'null'):
            with self.subTest(omission=omission):
                if omission == 'absent':
                    del header['hour']
                else:
                    header['hour'] = None
                before = deepcopy(snapshot)
                self.assertEqual(analyze_snapshot(snapshot, **query), static)
                self.assertEqual(analyze_snapshot(snapshot, facts, **query, **point), expected)
                self.assertEqual(snapshot, before)

        del selected['chart']['birthInfo']
        expected['dynamic']['unverified_static_fields'] = ['chart.birthInfo']
        self.assertEqual(analyze_snapshot(snapshot, **query), static)
        self.assertEqual(analyze_snapshot(snapshot, facts, **query, **point), expected)
        self.assertNotIn('birthInfo', selected['chart'])
        selected['chart']['birthInfo'] = header

        for bad_hour in (1, True, '2'):
            with self.subTest(bad_hour=bad_hour):
                header['hour'] = bad_hour
                with self.assertRaisesRegex(ValueError, '原盘与出生见证或原输入性别冲突'):
                    analyze_snapshot(snapshot, facts, **query, **point)
        del header['hour']
        wrong_dynamic = self.dynamic('1967-06-17', 1, target)
        different = analyze_snapshot(snapshot, wrong_dynamic, **query, **point)
        self.assertEqual(different['dynamic']['status'], 'withheld')
        self.assertEqual(different['stage_relationship'], static['stage_relationship'])
        del selected['witness_utc']
        with self.assertRaisesRegex(ValueError, '出生见证与可达枚举记录冲突'):
            analyze_snapshot(snapshot, **query)

    def test_dynamic_replay_requires_typed_and_matching_birth_identity(self):
        snapshot = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
                                  '--hour', '02:00', '--sex', '男', '--utc-offset', '8',
                                  '--format', 'json', '--analysis-year', '2025'])
        facts = self.dynamic('1971-01-06', 1, '2025-11-10')
        query = dict(expected_target_date='2025-11-10', expected_target_time_index=0)
        del snapshot['ziwei']['chart']['shenGongBranch']
        valid = analyze_snapshot(snapshot, facts, **query)
        self.assertEqual(valid['dynamic']['status'], 'admitted')
        self.assertEqual(valid['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')

        conflicts = (
            (('native_wrapper_snapshot', 'input', 'solar'), '1971-01-07'),
            (('native_wrapper_snapshot', 'input', 'shichenIndex'), 2),
            (('native_wrapper_snapshot', 'input', 'gender'), 'female'),
            (('native_wrapper_snapshot', 'input', 'birthYear'), 1972),
            (('native_wrapper_snapshot', 'chart', 'birthInfo', 'hour'), True),
            (('inputs', 'birth', 'shichen_index'), True),
        )
        for path, value in conflicts:
            with self.subTest(path=path):
                edited = deepcopy(facts)
                location = edited
                for key in path[:-1]:
                    location = location[key]
                location[path[-1]] = value
                result = analyze_snapshot(snapshot, edited, **query)
                self.assertEqual(result['dynamic']['status'], 'withheld')
                self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
                self.assertEqual(result['domains'], valid['domains'])
                self.assertEqual(self.current(result), self.current(valid))

        saved_lunar = snapshot['ziwei']['chart']['lunarInfo']
        saved_lunar['isLeapMonth'] = int(saved_lunar['isLeapMonth'])
        result = analyze_snapshot(snapshot, facts, **query)
        self.assertEqual(result['dynamic']['status'], 'withheld')
        self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')

    def test_requested_year_with_dynamic_requires_independent_query_point(self):
        snapshot = self.run_json([sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
                                  '--hour', '02:00', '--sex', '男', '--utc-offset', '8',
                                  '--format', 'json', '--analysis-year', '2025'])
        november = self.dynamic('1971-01-06', 1, '2025-11-10')
        january = self.dynamic('1971-01-06', 1, '2025-01-20')

        def rc03(panel):
            return panel['case_judgments']['modules']['ZW-RC03']['status']

        self.assertEqual(rc03(analyze_snapshot(snapshot, november)), 'conditional')
        with self.assertRaisesRegex(ValueError, '须提供本次请求的预期日期与时辰索引'):
            analyze_snapshot(snapshot, november, requested_analysis_year=2025)
        query = dict(requested_analysis_year=2025, expected_target_date='2025-01-20',
                     expected_target_time_index=0)
        stale = analyze_snapshot(snapshot, november, **query)
        valid = analyze_snapshot(snapshot, january, **query)
        self.assertEqual(stale['dynamic']['status'], 'withheld')
        self.assertEqual(rc03(stale), 'withheld')
        self.assertEqual(valid['dynamic']['status'], 'admitted')
        self.assertEqual(rc03(valid), 'not_triggered')
        self.assertEqual(self.current(stale), self.current(valid))


if __name__ == '__main__':
    unittest.main()
