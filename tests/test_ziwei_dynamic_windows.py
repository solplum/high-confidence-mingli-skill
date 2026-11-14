"""Civil-date planning follows the approved lunar profile and actual point adapter."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from datetime import date, datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
PLANNER = SCRIPTS / 'ziwei_dynamic_windows.mjs'
QUERY = SCRIPTS / 'ziwei_query_windows.py'
POINT = SCRIPTS / 'ziwei_dynamic_facts.mjs'

sys.path.insert(0, str(SCRIPTS))
from ziwei_life_reading import STEMS, analyze_native_shichen, analyze_snapshot
from ziwei_birth_time_candidates import birth_time_candidates
from ziwei_query_windows import audit_query_windows, query_windows


@unittest.skipUnless(shutil.which('node'), 'Node required for the locked local engine')
class ZiweiDynamicWindowTests(unittest.TestCase):
    def command(self, start, end, layer):
        return ['node', str(PLANNER), '--start', start, '--end', end, '--layer', layer]

    def plan(self, start, end, layer, env=None):
        return json.loads(subprocess.check_output(
            self.command(start, end, layer), cwd=ROOT, env=env, text=True, timeout=45))

    def query_command(self, start, end, layer, zone=None):
        command = [sys.executable, '-B', str(QUERY), '--start', start, '--end', end, '--layer', layer]
        if zone is not None:
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(zone)
            except (ImportError, KeyError) as exc:
                self.skipTest(str(exc))
            command.extend(['--timezone', zone])
        return command

    def query(self, *args):
        return json.loads(subprocess.check_output(
            self.query_command(*args), cwd=ROOT, text=True, timeout=45))

    def point(self, target, index):
        data = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1984-06-17', '--birth-year', '1984',
            '--shichen-index', '6', '--sex', '女', '--source-label', 'window-regression',
            '--target-date', target, '--target-time-index', str(index),
        ], cwd=ROOT, text=True, timeout=45))
        return data['native_wrapper_snapshot']['chart']['currentAge'], data['admitted_dynamic_facts']

    def test_november_month_uses_lunar_new_month_and_preserves_late_zi_day_gate(self):
        plan = self.plan('2026-11-01', '2026-12-01', 'month')
        left, right = plan['segments']
        self.assertEqual((left['start_inclusive'], left['end_exclusive']),
                         ('2026-11-01', '2026-11-09'))
        self.assertEqual((right['start_inclusive'], right['end_exclusive']),
                         ('2026-11-09', '2026-12-01'))
        self.assertEqual(right['boundary_reasons'], ['lunar_month_start'])
        _, left_start = self.point(left['probe']['target_date'], left['probe']['target_time_index'])
        _, left_end = self.point('2026-11-08', 12)
        _, right_start = self.point(right['probe']['target_date'], right['probe']['target_time_index'])
        self.assertEqual(left_start['layers']['monthly'], left_end['layers']['monthly'])
        self.assertNotEqual(left_end['layers']['monthly'], right_start['layers']['monthly'])
        self.assertEqual(left_end['layers']['daily']['status'], 'withheld')
        self.assertFalse(right_start['full_interval_coverage'])

    def test_civil_year_and_lunar_year_are_separate_boundaries(self):
        segments = self.plan('2025-12-31', '2026-02-18', 'year')['segments']
        self.assertEqual([(s['start_inclusive'], s['end_exclusive']) for s in segments], [
            ('2025-12-31', '2026-01-01'), ('2026-01-01', '2026-02-17'), ('2026-02-17', '2026-02-18')])
        self.assertEqual(segments[1]['boundary_reasons'], ['legacy_civil_year'])
        self.assertEqual(segments[2]['boundary_reasons'], ['lunar_new_year'])
        outputs = [self.point(s['probe']['target_date'], 0) for s in segments]
        self.assertEqual([a for a, _ in outputs], [42, 43, 43])
        a, b, c = [f['layers']['yearly'] for _, f in outputs]
        self.assertEqual(a, b)
        self.assertNotEqual(b, c)

    def test_chart_text_distinguishes_legacy_year_table_from_actual_date(self):
        text = subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1984-06-17',
            '--hour', '12:00', '--sex', '女', '--analysis-year', '2026', '--format', 'text',
        ], cwd=ROOT, text=True, timeout=45)
        self.assertIn('## 流年（公历年度索引 2026 年', text)
        self.assertIn('公历年度干支 丙午｜旧表四化 禄-天同 权-天机', text)
        self.assertIn('按实际查询日期核对流年时，以春节为年界，使用 scripts/ziwei_dynamic_facts.mjs。', text)
        self.assertNotIn('2026 丙午年｜流年四化', text)

        _, before = self.point('2026-01-01', 0)
        _, after = self.point('2026-02-17', 0)
        before_year = before['layers']['yearly']
        after_year = after['layers']['yearly']
        self.assertEqual(before_year['heavenly_stem'] + before_year['earthly_branch'], '乙巳')
        self.assertEqual(after_year['heavenly_stem'] + after_year['earthly_branch'], '丙午')
        self.assertEqual([(row['kind'], row['star']) for row in before_year['transformations'][:2]],
                         [('禄', '天机'), ('权', '天梁')])
        self.assertEqual([(row['kind'], row['star']) for row in after_year['transformations'][:2]],
                         [('禄', '天同'), ('权', '天机')])

    def test_leap_month_entrance_second_half_and_exit_have_separate_windows(self):
        segments = self.plan('2025-07-24', '2025-08-24', 'month')['segments']
        self.assertEqual([s['start_inclusive'] for s in segments],
                         ['2025-07-24', '2025-07-25', '2025-08-09', '2025-08-23'])
        first, second = segments[1:3]
        self.assertEqual(first['calendar_at_start']['lunarDay'], 1)
        self.assertEqual(second['calendar_at_start']['lunarDay'], 16)
        self.assertTrue(first['calendar_at_start']['isLeap'])
        self.assertEqual(second['boundary_reasons'], ['leap_month_second_half'])
        _, before = self.point('2025-08-08', 12)
        _, after = self.point(second['probe']['target_date'], 0)
        self.assertNotEqual(before['layers']['monthly'], after['layers']['monthly'])
        self.assertEqual(before['layers']['yearly'], after['layers']['yearly'])

    def test_end_exclusive_and_process_timezone_do_not_change_calendar_plan(self):
        interval = ('2026-11-08', '2026-11-09', 'month')
        a = self.plan(*interval, env=dict(os.environ, TZ='America/Adak'))
        b = self.plan(*interval, env=dict(os.environ, TZ='Pacific/Kiritimati'))
        self.assertEqual(a, b)
        self.assertEqual(len(a['segments']), 1)
        self.assertEqual(a['segments'][0]['end_exclusive'], '2026-11-09')
        self.assertEqual(self.plan('2099-12-31', '2100-01-01', 'month')['segments'][0]['start_inclusive'],
                         '2099-12-31')

    def test_actual_query_reenters_previous_lunar_month_at_midnight_rollback(self):
        zone = 'America/St_Johns'
        segments = self.query('1989-10-28', '1989-10-30', 'month', zone)['segments']
        self.assertEqual([row['start_inclusive'] for row in segments], [
            '1989-10-28T00:00:00-02:30', '1989-10-29T00:00:00-02:30',
            '1989-10-28T23:01:00-03:30', '1989-10-29T00:00:00-03:30',
        ])
        self.assertEqual([row['calendar_window']['calendar_at_start']['lunarMonth'] for row in segments],
                         [9, 10, 9, 10])
        self.assertEqual(segments[2]['boundary_reasons'], ['iana_utc_offset_change', 'calendar_window_change'])
        self.assertEqual([row['probe']['fold'] for row in segments], [0, 0, 1, 1])
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(datetime.fromisoformat(left['end_exclusive']).astimezone(timezone.utc),
                             datetime.fromisoformat(right['start_inclusive']).astimezone(timezone.utc))
        facts = [self.point(row['probe']['target_date'], row['probe']['target_time_index'])[1] for row in segments]
        months = [row['layers']['monthly'] for row in facts]
        self.assertEqual(months[0], months[2])
        self.assertEqual(months[1], months[3])
        self.assertNotEqual(months[0], months[1])
        self.assertEqual(facts[2]['layers']['daily']['status'], 'withheld')

        day = self.query('1989-10-29', '1989-10-30', 'month', zone)['segments']
        for actual, expected in zip(day, segments[1::2]):
            for key in ('start_inclusive', 'end_exclusive', 'probe'):
                self.assertEqual(actual[key], expected[key])
        self.assertEqual([s['boundary_reasons'] for s in day],
                         [['query_start'], ['civil_date_membership_gap']])

    def test_actual_query_replaces_skipped_midnight_and_date_probes(self):
        segments = self.query('2011-12-30', '2012-01-02', 'year', 'Pacific/Apia')['segments']
        self.assertEqual([s['probe']['target_date'] for s in segments], ['2011-12-31', '2012-01-01'])
        self.assertEqual(segments[0]['probe']['civil_time'], '2011-12-31T00:00:00+14:00')
        rejected = subprocess.run(self.query_command('2011-12-30', '2011-12-31', 'month', 'Pacific/Apia'),
                                  cwd=ROOT, capture_output=True, text=True, timeout=45)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('无可达查询时刻', rejected.stderr)
        segment, = self.query('2018-11-04', '2018-11-06', 'month', 'America/Sao_Paulo')['segments']
        self.assertEqual(segment['probe']['civil_time'], '2018-11-04T01:00:00-02:00')
        self.assertEqual(segment['probe']['target_time_index'], 1)

    def test_actual_query_clips_a_fixed_offset_partial_day_and_uses_its_own_probe(self):
        segments = self.query('2026-11-08T19:00+08:00', '2026-11-09T01:00+08:00', 'month')['segments']
        self.assertEqual([s['probe']['target_time_index'] for s in segments], [10, 0])
        self.assertEqual(segments[0]['probe']['civil_time'], '2026-11-08T19:00:00+08:00')
        self.assertEqual(segments[1]['end_exclusive'], '2026-11-09T01:00:00+08:00')
        rejected = subprocess.run(self.query_command('1899-12-31', '2200-01-01', 'year', 'Asia/Shanghai'),
                                  cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('1901–2099', rejected.stderr)

    def test_daily_facts_distinguish_late_zi_and_next_civil_date(self):
        segments = self.query('2026-02-16T21:00+08:00', '2026-02-17T01:00+08:00', 'day')['segments']
        self.assertEqual([(row['start_inclusive'], row['end_exclusive']) for row in segments], [
            ('2026-02-16T21:00:00+08:00', '2026-02-16T23:00:00+08:00'),
            ('2026-02-16T23:00:00+08:00', '2026-02-17T00:00:00+08:00'),
            ('2026-02-17T00:00:00+08:00', '2026-02-17T01:00:00+08:00'),
        ])
        self.assertEqual([row['probe']['target_time_index'] for row in segments], [11, 12, 0])
        self.assertEqual(segments[1]['boundary_reasons'], ['late_zi_day_gate_change'])
        self.assertIn('lunar_new_year', segments[2]['calendar_window']['boundary_reasons'])
        self.assertIn('civil_date_change', segments[2]['calendar_window']['boundary_reasons'])
        a, b, c = [self.point(row['probe']['target_date'], row['probe']['target_time_index'])[1]['layers']
                   for row in segments]
        self.assertEqual([row['daily']['status'] for row in (a, b, c)],
                         ['facts_only', 'withheld', 'facts_only'])
        for layer in ('yearly', 'monthly'):
            self.assertEqual(a[layer], b[layer])
            self.assertNotEqual(b[layer], c[layer])

    def test_daily_facts_keep_reentered_late_zi_and_repeated_date_start(self):
        segments = self.query('1989-10-28T22:00', '1989-10-29T01:00', 'day', 'America/St_Johns')['segments']
        self.assertEqual([row['start_inclusive'] for row in segments], [
            '1989-10-28T22:00:00-02:30', '1989-10-28T23:00:00-02:30', '1989-10-29T00:00:00-02:30',
            '1989-10-28T23:01:00-03:30', '1989-10-29T00:00:00-03:30',
        ])
        self.assertEqual([row['probe']['target_time_index'] for row in segments], [11, 12, 0, 12, 0])
        self.assertEqual([row['probe']['fold'] for row in segments], [0, 0, 0, 1, 1])
        self.assertIn('iana_utc_offset_change', segments[3]['boundary_reasons'])
        self.assertIn('late_zi_day_gate_change', segments[3]['boundary_reasons'])
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(datetime.fromisoformat(left['end_exclusive']).astimezone(timezone.utc),
                             datetime.fromisoformat(right['start_inclusive']).astimezone(timezone.utc))

    def test_audit_replays_explicit_folds_and_requires_them_for_legacy_ambiguous_bounds(self):
        request = dict(start='2024-11-03T01:15', end='2024-11-03T01:15', layer='day',
                       timezone='America/New_York', start_fold=0, end_fold=1)
        plan = query_windows(request['start'], request['end'], request['layer'], request['timezone'],
                             start_fold=request['start_fold'], end_fold=request['end_fold'])
        self.assertEqual((plan['requested']['start_fold'], plan['requested']['end_fold']), (0, 1))
        natal = dict(domains=[dict(facts=[])])
        expected = audit_query_windows(plan, {}, natal_panel=natal)
        self.assertEqual([row['start_inclusive'] for row in expected['segments']],
                         ['2024-11-03T01:15:00-04:00', '2024-11-03T01:00:00-05:00'])
        legacy = deepcopy(plan)
        del legacy['requested']['start_fold'], legacy['requested']['end_fold']
        with self.assertRaisesRegex(ValueError, '所需 fold'):
            audit_query_windows(legacy, {}, natal_panel=natal)
        self.assertEqual(audit_query_windows(legacy, {}, natal_panel=natal, expected_request=request), expected)

    def test_audit_checks_saved_query_timezone_source_before_using_the_plan(self):
        cases = (
            ('2026-03-08', '2026-03-09', 'America/New_York'),
            ('2026-03-08T03:00-04:00', '2026-03-08T03:30-04:00', None),
        )
        natal = dict(domains=[dict(facts=[])])
        for start, end, zone in cases:
            plan = self.query(start, end, 'day', zone)
            expected = dict(start=start, end=end, layer='day', timezone=zone)
            baseline = audit_query_windows(plan, {}, natal_panel=natal, expected_request=expected)
            legacy = deepcopy(plan)
            del legacy['provenance']['timezone_source']
            source = plan['provenance']['timezone_source']
            wrong_kind = 'fixed_offset' if zone is not None else 'host_iana_tzif'
            changes = (None, dict(source, zone='Asia/Shanghai'), dict(source, kind=wrong_kind))
            for request in (None, expected):
                with self.subTest(request=request, zone=zone):
                    self.assertEqual(audit_query_windows(legacy, {}, natal_panel=natal,
                                                         expected_request=request), baseline)
                    for conflicting in changes:
                        archived = dict(plan, provenance=dict(plan['provenance'], timezone_source=conflicting))
                        with self.assertRaisesRegex(ValueError, '保存的时区来源'):
                            audit_query_windows(archived, {}, natal_panel=natal, expected_request=request)

    def test_audit_replays_current_stage_models_without_discarding_the_window(self):
        born, target = '1987-01-02', '2029-01-03'
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', born,
            '--hour', '22:30', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2028', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        dynamic = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', born, '--birth-year', '1987', '--shichen-index', '11',
            '--sex', '男', '--source-label', 'stage-model-test', '--target-date', target, '--target-time-index', '0',
        ], cwd=ROOT, text=True, timeout=45))
        plan = self.query(f'{target}T00:00+08:00', f'{target}T01:00+08:00', 'month')
        start = plan['segments'][0]['start_inclusive']
        options = dict(requested_analysis_year=2029, expected_target_date=target, expected_target_time_index=0)
        panel = analyze_snapshot(snapshot, dynamic, **options)

        def check(value, reference=natal):
            row, = audit_query_windows(plan, {start: value}, natal_panel=reference)['segments']
            self.assertEqual((row['stage_status'], row['stage_current_status']), ('verified', 'active'))
            self.assertEqual(row['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
            return row['stage_models']

        verified = dict(status='verified', unverified_rules=[])
        self.assertEqual(check(panel), verified)
        rows = panel['stage_relationship']['stages']
        current_index = panel['stage_relationship']['stage_contract']['current_index']
        current = rows[current_index]
        stale = next(row for row in rows if row['modules']['ZW-ST08']['selected_branch'] == 'tanlang_coordination')
        self.assertEqual(current['modules']['ZW-ST05']['selected_branch'], 'tianxiang_yang_restriction')
        self.assertEqual(current['modules']['ZW-ST08']['status'], 'not_triggered')
        self.assertNotEqual(current['context']['anchor'], stale['context']['anchor'])

        modified = deepcopy(panel)
        saved = modified['stage_relationship']['stages'][current_index]
        saved['modules']['ZW-ST08'] = stale['modules']['ZW-ST08']
        self.assertEqual(check(modified), dict(status='partial', unverified_rules=['ZW-ST08']))
        del saved['modules']['ZW-ST05']
        self.assertEqual(check(modified), dict(status='partial', unverified_rules=['ZW-ST05', 'ZW-ST08']))
        saved['context'] = stale['context']
        self.assertEqual(check(modified), dict(status='withheld', unverified_rules=list(current['modules'])))

        modified = deepcopy(panel)
        cards = modified['stage_relationship']['cards']
        cards['ZW-ST05'] = cards['ZW-ST08']
        self.assertEqual(check(modified), dict(status='partial', unverified_rules=['ZW-ST05']))
        del cards['ZW-ST08']
        self.assertEqual(check(modified), dict(status='partial', unverified_rules=['ZW-ST05', 'ZW-ST08']))

        for older in ('static', 'point'):
            reference, saved = deepcopy(natal), deepcopy(panel)
            stale_stem = reference if older == 'static' else saved
            stale_stem['stage_relationship']['natal_year_stem'] = 'legacy excerpt without source'
            state = check(saved, reference)
            self.assertEqual(state['status'], 'partial')
            self.assertNotIn('ZW-ST05', state['unverified_rules'])

        partial = deepcopy(snapshot)
        palace = next(row for row in partial['ziwei']['chart']['palaces'] if row['branch'] == current['context']['anchor'])
        star = next(row for row in palace['stars'] if row['name'] == '天相')
        del star['brightnessRaw']
        partial_panel = analyze_snapshot(partial, dynamic, **options)
        rule = partial_panel['stage_relationship']['stages'][current_index]['modules']['ZW-ST05']
        self.assertEqual(rule['status'], 'withheld')
        self.assertEqual(check(partial_panel), verified)

    def test_audit_keeps_explicit_static_stage_when_dynamic_is_unavailable(self):
        plan = self.query('2033-12-31', '2034-01-02', 'month', 'Asia/Shanghai')
        starts = [segment['start_inclusive'] for segment in plan['segments']]
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'birth.json'
            snapshot.write_bytes(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1980-02-24',
                '--hour', '00:30', '--sex', '女', '--utc-offset', '8',
                '--analysis-year', '2026', '--format', 'json',
            ], cwd=ROOT, timeout=45))

            def read_stage(*options):
                return json.loads(subprocess.check_output([
                    sys.executable, '-B', str(SCRIPTS / 'ziwei_life_reading.py'),
                    '--snapshot', str(snapshot), *options,
                ], cwd=ROOT, text=True, timeout=45))

            natal = read_stage()
            before = read_stage('--analysis-year', '2033')
            after = read_stage('--analysis-year', '2034')

        def audit(*panels):
            return audit_query_windows(plan, dict(zip(starts, panels)), natal_panel=natal)['segments']

        for panel, expected_branch in ((before, 'wuqu_quan_progress'), (after, None)):
            current, = [stage for stage in panel['stage_relationship']['stages']
                        if stage['legacy_stage']['current']]
            self.assertEqual(current['modules']['ZW-ST04']['selected_branch'], expected_branch)
        for row in audit(before, after):
            self.assertEqual((row['stage_status'], row['stage_current_status']), ('verified', 'active'))
            self.assertEqual(row['stage_models'], dict(status='verified', unverified_rules=[]))
            self.assertEqual(row['dynamic_layers'], dict(yearly='withheld', monthly='withheld'))
            self.assertEqual(row['annual_case_status'], 'unverified')
            self.assertEqual(row['natal_domain_topic_status']['ZW-D02'], 'verified')
            self.assertEqual(row['natal_domain_topic_status']['ZW-D07'], 'verified')

        self.assertEqual(audit(after, before)[0]['stage_status'], 'year_mismatch')
        unrequested = deepcopy(before)
        del unrequested['stage_query_scope']['requested_analysis_year']
        self.assertEqual(audit(unrequested, after)[0]['stage_status'], 'withheld')
        mismatched_probe = deepcopy(before)
        mismatched_probe['dynamic']['query_point'] = dict(solar_date='2033-12-30', time_index=0)
        self.assertEqual(audit(mismatched_probe, after)[0]['stage_status'], 'withheld')

    def test_stage_rule_uses_natal_attachment_independently_of_its_topic(self):
        start, end = '1984-02-03T00:00:00+08:00', '1984-02-03T01:00:00+08:00'
        plan = self.query(start, end, 'month')
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1980-02-16',
            '--hour', '00:30', '--sex', '男', '--timezone', 'Asia/Shanghai',
            '--analysis-year', '1984', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        dynamic = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1980-02-16', '--birth-year', '1980',
            '--shichen-index', '0', '--sex', '男', '--source-label', 'stage-transform-attachment',
            '--target-date', '1984-02-03', '--target-time-index', '0', '--target-civil', start,
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        point = analyze_snapshot(snapshot, dynamic, requested_analysis_year=1984,
                                 expected_target_date='1984-02-03', expected_target_time_index=0,
                                 expected_target_civil=start)
        current, = [row for row in point['stage_relationship']['stages'] if row['legacy_stage']['current']]
        rule = 'ZW-ST04'
        self.assertEqual(current['modules'][rule]['selected_branch'], 'wuqu_quan_progress')

        def audit(saved, reference=natal):
            row, = audit_query_windows(plan, {start: saved}, natal_panel=reference)['segments']
            return row

        clean = audit(point)
        self.assertEqual(clean['stage_models'], dict(status='verified', unverified_rules=[]))
        older = deepcopy(natal)
        del older['stage_relationship']['natal_year_stem']
        self.assertEqual(audit(point, older), clean)
        incomplete = deepcopy(older)
        del incomplete['natal_stage_basis']
        self.assertIn(rule, audit(point, incomplete)['stage_models']['unverified_rules'])
        older['stage_relationship']['natal_year_stem'] = {'path': 'chart.lunarInfo.yearStem', 'value': None}
        self.assertIn(rule, audit(point, older)['stage_models']['unverified_rules'])
        stale = deepcopy(point)
        power = next(row for row in stale['transformations'] if row['id'] == 'natal.权')
        power['status'] = 'withheld'
        checked = audit(stale)
        self.assertEqual(checked['natal_transformation_topic_status']['权'], 'withheld')
        self.assertEqual(checked['stage_models'], clean['stage_models'])
        self.assertEqual(checked['stage_status'], 'verified')
        power['source_path'] += '/wrong'
        checked = audit(stale)
        self.assertEqual(checked['stage_models'], dict(status='partial', unverified_rules=[rule]))
        self.assertEqual(checked['stage_status'], 'verified')

    def test_stage_topic_replays_current_palace_across_the_civil_year_boundary(self):
        born = '1971-01-06'
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', born,
            '--hour', '02:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2015', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        plan = self.query('2015-12-31T10:00+08:00', '2016-01-01T12:00+08:00', 'month')
        panels, dynamic_inputs = {}, {}

        def read_point(saved, dynamic, probe):
            target = probe['target_date']
            return analyze_snapshot(saved, dynamic, requested_analysis_year=int(target[:4]),
                                    expected_target_date=target, expected_target_time_index=probe['target_time_index'],
                                    expected_target_civil=probe['civil_time'])

        for segment in plan['segments']:
            probe = segment['probe']
            target, index, clock = (probe[key] for key in ('target_date', 'target_time_index', 'civil_time'))
            dynamic = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', born, '--birth-year', '1971', '--shichen-index', '1', '--sex', '男',
                '--source-label', 'stage-topic-test', '--target-date', target, '--target-time-index', str(index),
                '--target-civil', clock,
            ], cwd=ROOT, text=True, timeout=45))
            panels[segment['start_inclusive']] = read_point(snapshot, dynamic, probe)
            dynamic_inputs[segment['start_inclusive']] = (dynamic, probe)

        def current_stage(panel):
            return next(row['legacy_stage'] for row in panel['stage_relationship']['stages']
                        if row['legacy_stage']['current'])

        def application(panel):
            return panel['case_judgments']['modules']['ZW-RC03']

        def summaries(panel):
            contract, = panel['modules']['ZW-T02']['rows']
            native = next(row for row in contract['rows'] if row['current'])
            return native, current_stage(panel), application(panel)['context']['current_stage']

        start, next_start = panels
        earlier, current = current_stage(panels[start]), current_stage(panels[next_start])
        self.assertEqual((earlier['domain'], current['domain']), ('田宅', '官禄'))
        self.assertEqual(earlier['window']['end_exclusive'], current['window']['start_inclusive'])
        self.assertNotEqual(earlier['topic_fact_paths'], current['topic_fact_paths'])
        self.assertEqual(application(panels[start])['status'], 'not_triggered')
        self.assertEqual(application(panels[next_start])['selected_branch'], 'proactive_application_fit')

        reference = audit_query_windows(plan, panels, natal_panel=natal)['segments']
        for row in reference:
            self.assertEqual(row['stage_topic_status'], 'verified')
            self.assertEqual(row['stage_status'], 'verified')
            self.assertEqual(row['stage_models']['status'], 'verified')
            self.assertEqual(row['annual_case_status'], 'verified')
            self.assertEqual(row['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))

        for difference in ('retired_annotations', 'palace_spelling'):
            with self.subTest(difference=difference):
                archive = deepcopy(snapshot)
                chart = archive['ziwei']['chart']
                palace_stems = {row['branch']: row['stem'] for row in chart['palaces']}
                for stage in chart['daXians']:
                    if difference == 'retired_annotations':
                        stem = palace_stems[stage['palaceBranch']]
                        stage.update(stemIndex=stem, stemName=STEMS[stem], siHua=None)
                    else:
                        name = stage['palaceName']
                        stage['palaceName'] = name.removesuffix('宫') if name.endswith('宫') else name + '宫'
                legacy_natal = analyze_snapshot(archive)
                legacy_points = {key: read_point(archive, dynamic, probe)
                                 for key, (dynamic, probe) in dynamic_inputs.items()}
                self.assertEqual(audit_query_windows(plan, legacy_points, natal_panel=natal)['segments'], reference)
                self.assertEqual(audit_query_windows(plan, panels, natal_panel=legacy_natal)['segments'], reference)

        all_topic_fields = ('role', 'topic_fact_paths', 'empty_palace', 'domain_status', 'status')
        for selected, fields in (
            ((0,), all_topic_fields), ((1,), all_topic_fields), ((2,), all_topic_fields),
            ((0, 1, 2), ('role',)), ((0, 1, 2), ('topic_fact_paths',)), ((0, 1, 2), all_topic_fields),
        ):
            with self.subTest(selected=selected, fields=fields):
                changed = deepcopy(panels)
                stored = summaries(changed[next_start])
                for index in selected:
                    for field in fields:
                        stored[index][field] = deepcopy(earlier[field])
                audited = audit_query_windows(plan, changed, natal_panel=natal)['segments']
                self.assertEqual(audited, [reference[0], dict(reference[1], stage_topic_status='withheld')])

        changed = deepcopy(panels)
        summaries(changed[next_start])[0]['native']['startAge'] += 1
        earlier_audit, current_audit = audit_query_windows(plan, changed, natal_panel=natal)['segments']
        self.assertEqual(earlier_audit, reference[0])
        self.assertEqual((current_audit['stage_status'], current_audit['stage_topic_status']),
                         ('withheld', 'unverified'))
        self.assertEqual(current_audit['stage_models']['status'], 'unverified')
        self.assertEqual(current_audit['annual_case_status'], 'unverified')
        self.assertEqual(current_audit['dynamic_layers'], reference[1]['dynamic_layers'])

        changed = deepcopy(panels)
        summaries(changed[next_start])[2]['native']['startAge'] += 1
        audited = audit_query_windows(plan, changed, natal_panel=natal)['segments']
        self.assertEqual(audited, [reference[0], dict(reference[1], annual_case_status='withheld')])

    def test_cached_birth_year_conflict_is_limited_to_its_own_layer(self):
        start = '2030-11-10T00:00:00+08:00'
        plan = self.query(start, '2030-11-11T00:00:00+08:00', 'month')
        segment, = plan['segments']
        probe = segment['probe']
        target, index = probe['target_date'], probe['target_time_index']

        def read(civil_date, hour, *clock_options):
            snapshot = json.loads(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', civil_date,
                '--hour', hour, '--sex', '男', '--utc-offset', '8', '--analysis-year', '2026',
                '--format', 'json', *clock_options,
            ], cwd=ROOT, text=True, timeout=45))
            inputs = snapshot['ziwei']['input']
            dynamic = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', inputs['solar'], '--birth-year', str(inputs['birthYear']),
                '--shichen-index', str(inputs['shichenIndex']), '--sex', '男',
                '--source-label', 'cached-birth-year-scope', '--target-date', target,
                '--target-time-index', str(index), '--target-civil', probe['civil_time'],
            ], cwd=ROOT, text=True, timeout=45))
            return analyze_snapshot(snapshot), analyze_snapshot(
                snapshot, dynamic, requested_analysis_year=2030, expected_target_date=target,
                expected_target_time_index=index, expected_target_civil=probe['civil_time'])

        natal, clean = read('1987-01-01', '00:30', '--time-basis', 'mean-solar', '--lon', '105', '--lat', '31')
        _, other = read('1986-12-31', '23:30', '--time-basis', 'civil')
        self.assertEqual(clean['natal_solar_date'], other['natal_solar_date'])
        self.assertEqual(clean['domains'], other['domains'])
        self.assertEqual(clean['dynamic']['layers'], other['dynamic']['layers'])
        self.assertNotEqual(clean['birth_time_bounds'], other['birth_time_bounds'])
        self.assertEqual([next(row['legacy_stage']['domain'] for row in panel['stage_relationship']['stages']
                               if row['legacy_stage']['current']) for panel in (clean, other)], ['田宅', '官禄'])

        def audit(point):
            row, = audit_query_windows(plan, {start: point}, natal_panel=natal)['segments']
            return row

        verified = audit(clean)
        self.assertEqual(verified['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        self.assertEqual(verified['stage_status'], 'verified')
        self.assertEqual(verified['annual_case_status'], 'verified')
        self.assertEqual(verified['natal_relationship_status']['ZW-RL01'], 'verified')
        self.assertEqual(verified['natal_domain_topic_status']['ZW-D06'], 'verified')

        stale_stage = deepcopy(clean)
        stale_stage['stage_relationship'] = other['stage_relationship']
        stale_stage['modules']['ZW-T02'] = other['modules']['ZW-T02']
        stage_unverified = dict(stage_status='birth_mismatch', stage_current_status='unverified',
                                stage_topic_status='unverified',
                                stage_models=dict(status='unverified', unverified_rules=[]),
                                annual_case_status='unverified',
                                annual_case_stage_precondition=dict(status='unverified', domain=None, window=None))
        self.assertEqual(audit(stale_stage), dict(verified, **stage_unverified))

        wrong_layers = dict(yearly='birth_mismatch', monthly='birth_mismatch')
        stale_dynamic = dict(clean, dynamic=other['dynamic'])
        dynamic_result = audit(stale_dynamic)
        self.assertEqual(dynamic_result['dynamic_layers'], wrong_layers)
        self.assertEqual(dynamic_result['annual_case_status'], 'unverified')
        for key in ('stage_status', 'stage_current_status', 'stage_topic_status', 'stage_models',
                    'natal_relationship_status', 'natal_domain_topic_status'):
            self.assertEqual(dynamic_result[key], verified[key])
        self.assertEqual(audit(dict(stale_stage, dynamic=other['dynamic'])),
                         dict(dynamic_result, **stage_unverified))

        legacy = deepcopy(clean)
        del legacy['natal_civil_birth_year']
        self.assertEqual(audit(legacy), verified)
        for unbound in (other, dict(legacy, dynamic=other['dynamic'])):
            result = audit(unbound)
            self.assertEqual(result['dynamic_layers'], wrong_layers)
            self.assertEqual(result['stage_status'], 'birth_mismatch')
            self.assertEqual(result['natal_relationship_status']['ZW-RL01'], 'unverified')
            self.assertEqual(result['natal_domain_topic_status']['ZW-D06'], 'unverified')

    def test_static_birth_basis_binds_point_stage_when_natal_t02_is_unavailable(self):
        start, end = '2026-11-10T00:00+08:00', '2026-11-11T00:00+08:00'
        plan = self.query(start, end, 'month')
        segment, = plan['segments']
        probe = segment['probe']
        target, index = probe['target_date'], probe['target_time_index']

        def read(sex):
            snapshot = json.loads(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1980-06-14',
                '--hour', '16:00', '--sex', sex, '--utc-offset', '8', '--analysis-year', '2026',
                '--format', 'json',
            ], cwd=ROOT, text=True, timeout=45))
            dynamic = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '1980-06-14', '--birth-year', '1980',
                '--shichen-index', '8', '--sex', sex, '--source-label', 'window-birth-basis',
                '--target-date', target, '--target-time-index', str(index),
            ], cwd=ROOT, text=True, timeout=45))
            point = analyze_snapshot(snapshot, dynamic, expected_target_date=target,
                                     expected_target_time_index=index, requested_analysis_year=2026)
            return snapshot, point

        male, male_point = read('男')
        _, female_point = read('女')
        self.assertEqual(male_point['domains'], female_point['domains'])
        for point, domain in ((male_point, '官禄'), (female_point, '财帛')):
            current = next(row['legacy_stage'] for row in point['stage_relationship']['stages']
                           if row['legacy_stage']['current'])
            self.assertEqual(current['domain'], domain)

        full_natal = analyze_snapshot(male)
        del male['input']['analysis_year']
        del male['provenance']['analysis_year']
        del male['provenance']['resolved_age_year']
        natal = analyze_snapshot(male)
        self.assertEqual(natal['modules']['ZW-T02']['status'], 'withheld')
        self.assertEqual(natal['stage_relationship']['relationship']['status'], 'conditional')

        def audit(point, static=natal):
            row, = audit_query_windows(plan, {segment['start_inclusive']: point}, natal_panel=static)['segments']
            return row['dynamic_layers'], row['stage_status'], row['stage_current_status']

        admitted = dict(yearly='admitted', monthly='admitted')
        self.assertEqual(audit(male_point), (admitted, 'verified', 'active'))
        self.assertEqual(audit(female_point), (dict.fromkeys(admitted, 'birth_mismatch'),
                                              'birth_mismatch', 'unverified'))
        del male_point['natal_stage_basis']
        del female_point['natal_stage_basis']
        self.assertEqual(audit(male_point), (admitted, 'verified', 'active'))
        self.assertEqual(audit(female_point), (admitted, 'withheld', 'unverified'))
        del full_natal['natal_stage_basis']
        self.assertEqual(audit(male_point, full_natal), (admitted, 'verified', 'active'))
        self.assertEqual(audit(female_point, full_natal), (admitted, 'withheld', 'unverified'))
        old_natal = deepcopy(natal)
        del old_natal['natal_stage_basis']
        for point in (male_point, female_point):
            self.assertEqual(audit(point, old_natal), (admitted, 'withheld', 'unverified'))
        no_bureau = deepcopy(natal)
        del no_bureau['natal_stage_basis']['wuxing_ju']
        self.assertEqual(audit(male_point, no_bureau), (admitted, 'withheld', 'unverified'))

    def test_same_replayed_birth_preserves_independent_layers_with_optional_annotation_gaps(self):
        plan = self.query('2025-11-10T00:00+08:00', '2025-11-11T00:00+08:00', 'month')
        segment, = plan['segments']
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1971-01-06',
            '--hour', '02:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2025', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1971-01-06', '--birth-year', '1971',
            '--shichen-index', '1', '--sex', '男', '--source-label', 'window-optional-annotations',
            '--target-date', '2025-11-10', '--target-time-index', '0',
        ], cwd=ROOT, text=True, timeout=45))

        def read(saved):
            return analyze_snapshot(saved, facts, requested_analysis_year=2025,
                                    expected_target_date='2025-11-10', expected_target_time_index=0)

        def star(saved, name):
            return next(s for palace in saved['ziwei']['chart']['palaces'] for s in palace['stars'] if s['name'] == name)

        def audit_result(static, point):
            result, = audit_query_windows(plan, {segment['start_inclusive']: point}, natal_panel=static)['segments']
            return result

        def audit(static, point):
            result = audit_result(static, point)
            return result['dynamic_layers'], result['stage_status']

        static, full = analyze_snapshot(snapshot), read(snapshot)
        admitted = dict(yearly='admitted', monthly='admitted')
        mismatch = (dict.fromkeys(admitted, 'birth_mismatch'), 'birth_mismatch')
        self.assertEqual(audit(static, full), (admitted, 'verified'))
        self.assertEqual(full['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')

        def reorder(saved):
            reordered = deepcopy(saved)
            palaces = reordered['ziwei']['chart']['palaces']
            palaces.reverse()
            for palace in palaces:
                palace['stars'].reverse()
            return reordered

        reordered = reorder(snapshot)
        reordered_point = read(reordered)
        self.assertNotEqual(reordered_point['domains'], full['domains'])
        self.assertEqual(audit_result(static, reordered_point), audit_result(static, full))
        self.assertEqual(audit_result(analyze_snapshot(reordered), full), audit_result(static, full))
        invalid_path = deepcopy(reordered_point)
        invalid_path['domains'][0]['facts'][0]['path'] = 'chart.palaces[0].stars[99]'
        self.assertEqual(audit(static, invalid_path), mismatch)
        legacy_unbound = deepcopy(static)
        del legacy_unbound['natal_stage_basis']
        self.assertEqual(audit(legacy_unbound, reordered_point), mismatch)
        stale_month = deepcopy(reordered_point)
        stale_month['dynamic']['layers']['monthly'] = deepcopy(full['dynamic']['layers']['monthly'])
        for owner, previous in ((stale_month, full), (stale_month['dynamic'], full['dynamic'])):
            owner['transformations'] = [row for row in owner['transformations'] if row['layer'] != 'monthly']
            owner['transformations'].extend(deepcopy([row for row in previous['transformations']
                                                     if row['layer'] == 'monthly']))
        result = audit_result(static, stale_month)
        self.assertEqual(result['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
        self.assertEqual(result['stage_status'], 'verified')
        self.assertEqual(result['annual_case_status'], 'verified')

        partial_brightness = deepcopy(snapshot)
        del star(partial_brightness, '贪狼')['brightnessRaw']
        brightness_gap = read(partial_brightness)
        partial_transform = deepcopy(snapshot)
        del star(partial_transform, '太阴')['siHua']
        transform_gap = read(partial_transform)
        for partial, point, key, rc03 in (
                (partial_brightness, brightness_gap, 'brightnessRaw', 'conditional'),
                (partial_transform, transform_gap, 'siHua', 'withheld')):
            with self.subTest(annotation=key):
                self.assertTrue(point['dynamic']['unverified_static_fields'][0].endswith('.' + key))
                self.assertEqual(point['case_judgments']['modules']['ZW-RC03']['status'], rc03)
                self.assertEqual(audit(static, point), (admitted, 'verified'))
                self.assertEqual(audit(analyze_snapshot(partial), full), (admitted, 'verified'))

        wrong_brightness = deepcopy(snapshot)
        star(wrong_brightness, '贪狼')['brightnessRaw'] = '陷'
        self.assertEqual(audit(static, read(wrong_brightness)), mismatch)

        missing_proof = deepcopy(brightness_gap)
        del missing_proof['dynamic']['unverified_static_fields']
        self.assertEqual(audit(static, missing_proof), mismatch)
        reordered_gap = read(reorder(partial_brightness))
        self.assertNotEqual(reordered_gap['dynamic']['unverified_static_fields'],
                            brightness_gap['dynamic']['unverified_static_fields'])
        self.assertEqual(audit_result(static, reordered_gap), audit_result(static, brightness_gap))
        reordered_gap['dynamic']['unverified_static_fields'] = brightness_gap['dynamic']['unverified_static_fields']
        self.assertEqual(audit(static, reordered_gap), mismatch)
        damaged = deepcopy(brightness_gap)
        del next(row for row in damaged['domains'] if row['domain'] == '父母')['facts']
        self.assertEqual(audit(static, damaged), mismatch)

        missing_topic = deepcopy(brightness_gap)
        del next(row for row in missing_topic['domains'] if row['domain'] == '父母')['major_topics']
        result, = audit_query_windows(plan, {segment['start_inclusive']: missing_topic}, natal_panel=static)['segments']
        self.assertEqual(result['dynamic_layers'], admitted)
        self.assertEqual(result['stage_status'], 'verified')
        self.assertEqual(result['natal_domain_topic_status']['ZW-D08'], 'withheld')
        preserved, = audit_query_windows(plan, {segment['start_inclusive']: brightness_gap}, natal_panel=static)['segments']
        self.assertEqual(preserved['natal_domain_topic_status']['ZW-D08'], 'verified')

        # A complete panel's copied attachment cannot supply the point's missing natal annotation.
        stale_attachment = deepcopy(transform_gap)
        stale_attachment['dynamic']['layers']['yearly'] = deepcopy(full['dynamic']['layers']['yearly'])
        stale_attachment['dynamic']['transformations'] = deepcopy(full['dynamic']['transformations'])
        stale_attachment['transformations'] = deepcopy(full['transformations'])
        self.assertEqual(audit(static, stale_attachment), (dict(yearly='withheld', monthly='admitted'), 'verified'))

    def test_natal_domain_topics_are_replayed_apart_from_birth_and_query_facts(self):
        start, end = '2028-06-26T19:00:00+08:00', '2028-06-26T20:00:00+08:00'
        plan = self.query(start, end, 'month')

        def chart(hour):
            return json.loads(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1994-06-21',
                '--hour', hour, '--sex', '女', '--utc-offset', '8', '--analysis-year', '2028', '--format', 'json',
            ], cwd=ROOT, text=True, timeout=45))

        snapshot = chart('17:01')
        static, other = analyze_snapshot(snapshot), analyze_snapshot(chart('16:59'))
        facts = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1994-06-21', '--birth-year', '1994',
            '--shichen-index', '9', '--sex', '女', '--source-label', 'domain-topic-audit',
            '--target-date', '2028-06-26', '--target-time-index', '10', '--target-civil', start,
        ], cwd=ROOT, text=True, timeout=45))
        point = analyze_snapshot(snapshot, facts, requested_analysis_year=2028, expected_target_date='2028-06-26',
                                 expected_target_time_index=10, expected_target_civil=start)

        def audit(dynamic, natal=static):
            result, = audit_query_windows(plan, {start: dynamic}, natal_panel=natal)['segments']
            return result

        def domain(owner, rule):
            return next(row for row in owner['domains'] if row['source_rule'] == rule)

        clean = audit(point)
        topic_status = clean['natal_domain_topic_status']
        spouse, health, rest = 'ZW-D02', 'ZW-D04', 'ZW-D07'
        self.assertEqual([topic_status[rule] for rule in (spouse, health, rest)], ['verified'] * 3)
        self.assertEqual(clean['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        self.assertEqual(clean['stage_status'], 'verified')
        self.assertEqual(domain(other, rest)['major_topics'], [])

        self.assertNotEqual(point['natal_body_branch'], other['natal_body_branch'])
        self.assertEqual(clean['natal_body_topic_status'], 'verified')
        wrong_body = deepcopy(point)
        wrong_body['modules']['ZW-S01'] = other['modules']['ZW-S01']
        body_withheld = dict(clean, natal_body_topic_status='withheld')
        self.assertEqual(audit(wrong_body), body_withheld)
        wrong_static = deepcopy(static)
        wrong_static['modules']['ZW-S01'] = other['modules']['ZW-S01']
        self.assertEqual(audit(wrong_body, wrong_static), body_withheld)
        legacy_point = deepcopy(point)
        del legacy_point['natal_body_branch']
        self.assertEqual(audit(legacy_point), clean)
        legacy_static = deepcopy(static)
        del legacy_static['natal_body_branch']
        self.assertEqual(audit(point, legacy_static), dict(clean, natal_body_topic_status='unverified'))

        missing_boundary = deepcopy(point)
        del missing_boundary['modules'][health]['rows'][0]['medical_boundary']
        self.assertEqual(audit(missing_boundary), dict(clean, natal_domain_topic_status={**topic_status, health: 'withheld'}))

        wrong_spouse = deepcopy(point)
        wrong_spouse['modules'][spouse]['rows'][0]['major_topics'] = deepcopy(domain(other, spouse)['major_topics'])
        domain(wrong_spouse, spouse)['major_topics'] = deepcopy(domain(other, spouse)['major_topics'])
        self.assertEqual(audit(wrong_spouse), dict(clean, natal_domain_topic_status={**topic_status, spouse: 'withheld'}))

        wrong_rest, wrong_static = deepcopy(point), deepcopy(static)
        for owner in (wrong_rest, wrong_static):
            owner['modules'][rest]['rows'][0]['major_topics'] = []
            domain(owner, rest)['major_topics'] = []
            del owner['modules'][health]['rows'][0]['medical_boundary']
            del domain(owner, health)['medical_boundary']
        self.assertEqual(audit(wrong_rest, wrong_static), dict(
            clean, natal_domain_topic_status={**topic_status, rest: 'withheld', health: 'withheld'}))

        wrong_fact = deepcopy(point)
        domain(wrong_fact, health)['facts'].pop()
        mismatch = audit(wrong_fact)
        self.assertEqual(mismatch['dynamic_layers'], dict(yearly='birth_mismatch', monthly='birth_mismatch'))
        self.assertEqual(mismatch['stage_status'], 'birth_mismatch')
        self.assertEqual(mismatch['natal_domain_topic_status'], dict.fromkeys(topic_status, 'unverified'))

    def test_original_four_palaces_replay_role_and_themes_without_blocking_other_facts(self):
        start, end = '2026-11-12T19:00:00+08:00', '2026-11-12T20:00:00+08:00'
        plan = self.query(start, end, 'month')
        probe = plan['segments'][0]['probe']

        def chart(hour):
            return json.loads(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1981-02-05',
                '--hour', hour, '--sex', '男', '--timezone', 'Asia/Shanghai', '--analysis-year', '2026', '--format', 'json',
            ], cwd=ROOT, text=True, timeout=45))

        snapshot = chart('21:01')
        static, earlier = analyze_snapshot(snapshot), analyze_snapshot(chart('20:59'))
        facts = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1981-02-05', '--birth-year', '1981',
            '--shichen-index', str(snapshot['ziwei']['input']['shichenIndex']), '--sex', '男',
            '--source-label', 'original-four-palaces-topic-audit', '--target-date', probe['target_date'],
            '--target-time-index', str(probe['target_time_index']), '--target-civil', start,
        ], cwd=ROOT, text=True, timeout=45))

        def read(snap):
            return analyze_snapshot(snap, facts, requested_analysis_year=2026, expected_target_date=probe['target_date'],
                                    expected_target_time_index=probe['target_time_index'], expected_target_civil=start)

        def audit(dynamic, natal=static):
            result, = audit_query_windows(plan, {start: dynamic}, natal_panel=natal)['segments']
            return result

        def palace(owner, domain):
            return next(row for row in owner['domains'] if row['domain'] in (domain, domain + '宫'))

        point = read(snapshot)
        clean = audit(point)
        status = clean['natal_four_palace_topic_status']
        self.assertEqual(set(status), {'命', '财帛', '官禄', '迁移'})
        self.assertEqual(status['官禄'], 'facts_only')
        self.assertEqual(clean['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        self.assertEqual(clean['stage_status'], 'verified')
        self.assertEqual(clean['annual_case_status'], 'verified')

        swapped, stale_static = deepcopy(point), deepcopy(static)
        old_topics = palace(earlier, '官禄')['major_topics']
        self.assertEqual([row['star'] for row in old_topics], ['天同', '天梁'])
        for owner in (swapped, stale_static):
            palace(owner, '官禄')['major_topics'] = deepcopy(old_topics)
        damaged = dict(clean, natal_four_palace_topic_status={**status, '官禄': 'withheld'})
        self.assertEqual(audit(swapped), damaged)
        self.assertEqual(audit(swapped, stale_static), damaged)

        wrong_source = deepcopy(point)
        palace(wrong_source, '官禄')['citation']['record_id'] = 'ziwei-domain-brightness'
        self.assertEqual(audit(wrong_source), damaged)

        known = next(domain for domain, result in status.items() if result == 'verified')
        partial = deepcopy(snapshot)
        raw_palace = next(row for row in partial['ziwei']['chart']['palaces'] if row['name'] in (known, known + '宫'))
        del next(star for star in raw_palace['stars'] if star['type'] == 'major')['brightnessRaw']
        self.assertEqual(audit(read(partial))['natal_four_palace_topic_status'][known], 'verified')

    def test_annual_case_is_replayed_from_the_audited_point_and_stage(self):
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1971-01-06',
            '--hour', '02:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2025', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        rule = 'ZW-RC03'

        def read(start):
            end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
            plan = self.query(start, end, 'month')
            segment, = plan['segments']
            probe = segment['probe']
            target, index, civil = (probe[key] for key in ('target_date', 'target_time_index', 'civil_time'))
            facts = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '1971-01-06', '--birth-year', '1971',
                '--shichen-index', '1', '--sex', '男', '--source-label', 'annual-case-point-replay',
                '--target-date', target, '--target-time-index', str(index), '--target-civil', civil,
            ], cwd=ROOT, text=True, timeout=45))
            panel = analyze_snapshot(snapshot, facts, requested_analysis_year=int(target[:4]),
                                     expected_target_date=target, expected_target_time_index=index,
                                     expected_target_civil=civil)
            return plan, segment['start_inclusive'], panel, facts

        # One physical instant has different local lunar years. The next
        # civil year uses a new legacy stage, independently of lunar year.
        prior, favored, next_stage = (read(point) for point in (
            '2025-01-28T16:00+00:00', '2025-01-29T00:00+08:00', '2026-01-01T00:00+08:00'))
        self.assertEqual(datetime.fromisoformat(prior[1]), datetime.fromisoformat(favored[1]))

        def audit(entry, saved=None):
            plan, start, panel, _ = entry
            row, = audit_query_windows(plan, {start: panel if saved is None else saved}, natal_panel=natal)['segments']
            return row

        admitted = dict(yearly='admitted', monthly='admitted')
        positive = favored[2]['case_judgments']['modules'][rule]
        self.assertEqual(positive['status'], 'conditional')
        before_year = dict(status='excluded', attachments=[
            dict(kind='禄', star='廉贞', domain='子女', actual_major=True, matched=False),
            dict(kind='权', star='破军', domain='子女', actual_major=True, matched=False)])
        new_year = dict(status='met', attachments=[
            dict(kind='禄', star='天机', domain='官禄', actual_major=True, matched=True),
            dict(kind='权', star='天梁', domain='官禄', actual_major=True, matched=True)])
        unverified_year = dict(status='unverified', attachments=[])
        for entry, yearly_precondition in ((prior, before_year), (favored, new_year), (next_stage, new_year)):
            clean = audit(entry)
            self.assertEqual(clean['annual_case_status'], 'verified')
            self.assertEqual(clean['dynamic_layers'], admitted)
            self.assertEqual(clean['stage_status'], 'verified')
            self.assertEqual(clean['annual_case_yearly_precondition'], yearly_precondition)
        for entry in (prior, next_stage):
            mixed = deepcopy(entry[2])
            self.assertEqual(mixed['case_judgments']['modules'][rule]['status'], 'not_triggered')
            mixed['case_judgments']['modules'][rule] = deepcopy(positive)
            checked = audit(entry, mixed)
            self.assertEqual(checked['annual_case_status'], 'withheld')
            self.assertEqual(checked['dynamic_layers'], admitted)
            self.assertEqual(checked['stage_status'], 'verified')
        unverified_precondition = dict(status='unverified', domain=None, window=None)
        wrong_year = audit(next_stage, favored[2])
        self.assertEqual(wrong_year['stage_status'], 'year_mismatch')
        self.assertEqual(wrong_year['annual_case_status'], 'unverified')
        self.assertEqual(wrong_year['annual_case_stage_precondition'], unverified_precondition)
        self.assertEqual(wrong_year['annual_case_yearly_precondition'], unverified_year)

        for entry, condition, domain, first, last in (
                (favored, 'met', '官禄', '2016-01-01', '2026-01-01'),
                (next_stage, 'excluded', '仆役', '2026-01-01', '2036-01-01')):
            with self.subTest(annual_case_stage=condition):
                expected = dict(status=condition, domain=domain, window=dict(start_inclusive=first, end_exclusive=last))
                self.assertEqual(audit(entry)['annual_case_stage_precondition'], expected)
                _, start, _, facts = entry
                without_year = deepcopy(facts)
                del without_year['admitted_dynamic_facts']['layers']['yearly']
                monthly_only = analyze_snapshot(snapshot, without_year, requested_analysis_year=int(start[:4]),
                                                expected_target_date=start[:10], expected_target_time_index=0,
                                                expected_target_civil=start)
                self.assertEqual(monthly_only['case_judgments']['modules'][rule]['status'], 'withheld')
                checked = audit(entry, monthly_only)
                self.assertEqual(checked['dynamic_layers'], dict(yearly='withheld', monthly='admitted'))
                self.assertEqual(checked['stage_status'], 'verified')
                self.assertEqual(checked['annual_case_status'], 'unverified')
                self.assertEqual(checked['annual_case_stage_precondition'], expected)
                self.assertEqual(checked['annual_case_yearly_precondition'], unverified_year)

        wrong_month = deepcopy(favored[2])
        earlier = prior[2]
        wrong_month['dynamic']['layers']['monthly'] = deepcopy(earlier['dynamic']['layers']['monthly'])
        wrong_month['transformations'] = [row for row in wrong_month['transformations']
                                          if row['layer'] != 'monthly']
        wrong_month['transformations'].extend(row for row in earlier['transformations'] if row['layer'] == 'monthly')
        checked = audit(favored, wrong_month)
        self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='point_mismatch'))
        self.assertEqual(checked['stage_status'], 'verified')
        self.assertEqual(checked['annual_case_status'], 'verified')

        for layer, expected in (('monthly', 'verified'), ('yearly', 'unverified')):
            with self.subTest(layer=layer):
                wrong_source = deepcopy(favored[2])
                dynamic = wrong_source['dynamic']
                row_id = layer + '.禄'
                for owner in (dynamic['layers'][layer], dynamic, wrong_source):
                    row = next(row for row in owner['transformations'] if row['id'] == row_id)
                    row['admitted_attachment']['natal_star_locations'][0]['name'] = '错星'
                checked = audit(favored, wrong_source)
                self.assertEqual(checked['dynamic_layers'], dict(admitted, **{layer: 'withheld'}))
                self.assertEqual(checked['annual_case_status'], expected)
                self.assertEqual(checked['stage_status'], 'verified')
                self.assertEqual(checked['annual_case_yearly_precondition'],
                                 unverified_year if layer == 'yearly' else new_year)

        no_natal_kind = deepcopy(favored[2])
        no_natal_kind['transformations'] = [row for row in no_natal_kind['transformations']
                                            if (row['layer'], row['kind']) != ('natal', '忌')]
        checked = audit(favored, no_natal_kind)
        self.assertEqual(checked['dynamic_layers'], admitted)
        self.assertEqual(checked['stage_status'], 'verified')
        self.assertEqual(checked['annual_case_status'], 'withheld')
        self.assertEqual(checked['annual_case_yearly_precondition'], new_year)

        for kind, field, stale in (('忌', 'topic', '邻盘误贴主题'), ('禄', 'status', 'withheld')):
            with self.subTest(yearly_kind=kind, field=field):
                damaged = deepcopy(favored[2])
                row = next(row for row in damaged['transformations']
                           if row['layer'] == 'yearly' and row['kind'] == kind)
                row[field] = stale
                checked = audit(favored, damaged)
                self.assertEqual(checked['transformation_topic_status']['yearly'][kind], 'withheld')
                self.assertEqual(checked['annual_case_status'], 'verified')
                self.assertEqual(checked['dynamic_layers'], admitted)
                self.assertEqual(checked['stage_status'], 'verified')

        wrong_check = deepcopy(favored[2])
        evidence = wrong_check['case_judgments']['modules'][rule]['checks'][1]['evidence']
        evidence['topic'] = '邻盘误贴主题'
        self.assertEqual(audit(favored, wrong_check), audit(favored))
        evidence['source_path'] += '/wrong'
        self.assertEqual(audit(favored, wrong_check)['annual_case_status'], 'withheld')

        for variant in ('context_omits_projection', 'check_omits_projection', 'both_omit_projection',
                        'reordered_context', 'null_projection', 'omits_both_paths', 'wrong_raw_pointer',
                        'wrong_actual_fact', 'duplicate_context', 'missing_context'):
            with self.subTest(case_attachment=variant):
                saved = deepcopy(favored[2])
                module = saved['case_judgments']['modules'][rule]
                rows = module['context']['transformations']
                attached = next(row for row in rows if row['id'] == 'yearly.禄')
                check = module['checks'][1]['evidence']
                if variant in ('context_omits_projection', 'both_omit_projection',
                               'omits_both_paths', 'wrong_raw_pointer'):
                    del attached['source_path']
                if variant in ('check_omits_projection', 'both_omit_projection'):
                    del check['source_path']
                if variant == 'reordered_context':
                    rows.reverse()
                elif variant == 'null_projection':
                    attached['source_path'] = None
                elif variant == 'omits_both_paths':
                    del attached['admitted_attachment']['raw_pointer']
                elif variant == 'wrong_raw_pointer':
                    attached['admitted_attachment']['raw_pointer'] = (
                        '/research_dynamic_iztro/raw_horoscope/monthly/mutagen/0')
                elif variant == 'wrong_actual_fact':
                    attached['fact']['path'] += '/wrong'
                elif variant == 'duplicate_context':
                    rows.append(deepcopy(attached))
                elif variant == 'missing_context':
                    rows.remove(attached)
                original = deepcopy(saved)
                result = audit(favored, saved)
                expected = ('verified' if variant.endswith('_omits_projection') or
                            variant in ('both_omit_projection', 'reordered_context') else 'withheld')
                self.assertEqual(result['annual_case_status'], expected)
                self.assertEqual(result['dynamic_layers'], admitted)
                self.assertEqual(result['stage_status'], 'verified')
                self.assertEqual(saved, original)

    def test_transformation_topics_replay_independently_of_other_components(self):
        start, end = '2028-06-26T19:00:00+08:00', '2028-06-26T20:00:00+08:00'
        plan = self.query(start, end, 'month')
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1994-06-21',
            '--hour', '17:01', '--sex', '女', '--utc-offset', '8', '--analysis-year', '2028', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', '1994-06-21', '--birth-year', '1994',
            '--shichen-index', '9', '--sex', '女', '--source-label', 'transformation-topic-replay',
            '--target-date', '2028-06-26', '--target-time-index', '10', '--target-civil', start,
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        point = analyze_snapshot(snapshot, facts, requested_analysis_year=2028,
                                 expected_target_date='2028-06-26', expected_target_time_index=10,
                                 expected_target_civil=start)

        def topic(rows, item):
            return next(row for row in rows if row['id'] == item)

        def audit(saved, query=plan):
            row, = audit_query_windows(query, {start: saved}, natal_panel=natal)['segments']
            return row

        health = topic(point['transformations'], 'monthly.禄')
        auxiliary = topic(point['transformations'], 'monthly.科')
        self.assertEqual((health['star'], health['fact']['domain'], health['health_scope']),
                         ('贪狼', '疾厄', 'general_life_reflection_only'))
        self.assertEqual((auxiliary['star'], auxiliary['status'], auxiliary['topic']), ('右弼', 'facts_only', None))
        clean = audit(point)
        statuses = dict(禄='verified', 权='verified', 科='facts_only', 忌='verified')
        self.assertEqual(clean['transformation_topic_status'], dict(yearly=statuses, monthly=statuses))
        self.assertEqual(clean['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))

        month = point['dynamic']['layers']['monthly']['transformations']
        for name, kind in (('wrong_topic', '禄'), ('missing_boundary', '禄'), ('missing_card_boundary', '禄'),
                           ('duplicate_card_row', '禄'), ('promoted_auxiliary', '科'),
                           ('interpretation_copied_into_native_facts', '科')):
            with self.subTest(name=name):
                saved = deepcopy(point)
                item = 'monthly.' + kind
                row = topic(saved['transformations'], item)
                raw = topic(month, item)
                card = saved['modules'][row['rule_id']]['rows']
                if name == 'wrong_topic':
                    row['topic'] = topic(saved['transformations'], 'monthly.权')['topic']
                elif name == 'missing_boundary':
                    del row['medical_boundary']
                elif name == 'missing_card_boundary':
                    del topic(card, item)['medical_boundary']
                elif name == 'duplicate_card_row':
                    card.append(deepcopy(topic(card, item)))
                elif name == 'promoted_auxiliary':
                    row.update(status='conditional', topic=health['topic'])
                else:
                    # Raw admission used to accept a matching extra annotation in all three copies.
                    for rows in (saved['transformations'], saved['dynamic']['transformations'],
                                 saved['dynamic']['layers']['monthly']['transformations'], card):
                        topic(rows, item)['medical_boundary'] = health['medical_boundary']
                self.assertEqual({key: row[key] for key in raw}, raw)
                expected = deepcopy(clean)
                expected['transformation_topic_status']['monthly'][kind] = 'withheld'
                checked = audit(saved)
                self.assertEqual(checked.pop('transformation_components')['recorded_status'], 'unverified')
                del expected['transformation_components']
                self.assertEqual(checked, expected)

        missing_month = deepcopy(point)
        missing_month['dynamic']['layers']['monthly']['transformations'].pop()
        checked = audit(missing_month)
        self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
        self.assertEqual(checked['transformation_topic_status'],
                         dict(yearly=statuses, monthly=dict.fromkeys(statuses, 'unverified')))
        yearly = audit(missing_month, self.query(start, end, 'year'))
        self.assertEqual(yearly['transformation_topic_status'], dict(yearly=statuses))

    def test_multi_transformation_groups_use_checked_members_from_this_point(self):
        early, late = '2025-01-29T00:00:00+08:00', '2025-11-10T00:00:00+08:00'
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1971-01-06',
            '--hour', '02:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2025', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)

        def read(start):
            facts = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '1971-01-06', '--birth-year', '1971',
                '--shichen-index', '1', '--sex', '男', '--source-label', 'multi-transformation-replay',
                '--target-date', start[:10], '--target-time-index', '0', '--target-civil', start,
            ], cwd=ROOT, text=True, timeout=45))
            return analyze_snapshot(snapshot, facts, requested_analysis_year=2025, expected_target_date=start[:10],
                                    expected_target_time_index=0, expected_target_civil=start)

        def audit(panel, layer='month'):
            plan = self.query(late, '2025-11-10T01:00:00+08:00', layer)
            row, = audit_query_windows(plan, {late: panel}, natal_panel=natal)['segments']
            return row

        def card(panel):
            return panel['modules']['ZW-E05']

        def group(rows, kind, key):
            return next(row for row in rows if (row['kind'], row['key']) == (kind, key))

        original, current = read(early), read(late)
        clean = audit(current)
        components = clean['transformation_components']
        self.assertEqual((components['recorded_status'], components['incomplete_layers']), ('verified', []))
        self.assertEqual(components['groups'], card(current)['rows'])
        self.assertEqual(group(card(original)['rows'], 'same_star', '天机')['component_ids'],
                         ['yearly.禄', 'monthly.忌'])
        self.assertEqual(group(components['groups'], 'same_star', '天机')['component_ids'],
                         ['yearly.禄', 'monthly.权'])
        self.assertEqual(group(components['groups'], 'same_palace', 9)['fact_only_component_ids'], ['monthly.科'])

        item = 'monthly.权'
        for problem in ('omitted_projection', 'both_paths_missing', 'wrong_native_path', 'missing_citation'):
            with self.subTest(problem=problem):
                legacy = deepcopy(current)
                topic_rows = legacy['modules']['ZW-E02']['rows']
                for rows in (legacy['dynamic']['layers']['monthly']['transformations'],
                             legacy['dynamic']['transformations'], legacy['transformations'], topic_rows):
                    row = next(row for row in rows if row['id'] == item)
                    row.pop('source_path', None)
                    if problem == 'both_paths_missing':
                        row['admitted_attachment'].pop('raw_pointer', None)
                    elif problem == 'wrong_native_path':
                        row['admitted_attachment']['raw_pointer'] = (
                            '/research_dynamic_iztro/raw_horoscope/yearly/mutagen/1')
                if problem == 'missing_citation':
                    del next(row for row in topic_rows if row['id'] == item)['citation']
                checked = audit(legacy)
                if problem == 'omitted_projection':
                    self.assertEqual(checked, clean)
                else:
                    expected = 'unverified' if problem == 'wrong_native_path' else 'withheld'
                    self.assertEqual(checked['transformation_topic_status']['monthly']['权'], expected)
                    self.assertEqual(checked['transformation_topic_status']['yearly'],
                                     clean['transformation_topic_status']['yearly'])
                    for scope in ('stage_status', 'stage_models', 'annual_case_status', 'natal_relationship_status',
                                  'natal_domain_topic_status'):
                        self.assertEqual(checked[scope], clean[scope])
                    self.assertNotIn(dict(kind='same_star', key='天机'),
                                     [{'kind': row['kind'], 'key': row['key']}
                                      for row in checked['transformation_components']['groups']])

        self.assertEqual(clean['natal_transformation_topic_status']['忌'], 'verified')
        wrong_natal = deepcopy(current)
        next(row for row in wrong_natal['transformations'] if row['id'] == 'natal.忌')['topic'] = '错贴的主题'
        checked_natal = audit(wrong_natal)
        self.assertEqual(checked_natal['natal_transformation_topic_status'],
                         dict(clean['natal_transformation_topic_status'], 忌='withheld'))
        self.assertEqual(checked_natal['dynamic_layers'], clean['dynamic_layers'])
        self.assertEqual(checked_natal['transformation_topic_status'], clean['transformation_topic_status'])

        foreign = deepcopy(current)
        foreign['modules']['ZW-E05'] = deepcopy(card(original))
        for problem in ('other_month', 'cancellation', 'missing_row', 'duplicate_row', 'promoted_minor'):
            with self.subTest(problem=problem):
                damaged = foreign if problem == 'other_month' else deepcopy(current)
                rows = card(damaged)['rows']
                if problem == 'cancellation':
                    rows[0].update(net_effect='claimed_benefit', calculation='pressure_cancels')
                elif problem == 'missing_row':
                    rows.pop()
                elif problem == 'duplicate_row':
                    rows.append(deepcopy(rows[0]))
                elif problem == 'promoted_minor':
                    auxiliary = group(rows, 'same_palace', 9)
                    auxiliary['eligible_component_ids'].extend(auxiliary['fact_only_component_ids'])
                    auxiliary['fact_only_component_ids'].clear()
                expected = dict(clean, transformation_components=dict(components, recorded_status='withheld'))
                self.assertEqual(audit(damaged), expected)

        missing_topic = deepcopy(current)
        missing_topic['modules']['ZW-E02']['rows'].pop()
        checked = audit(missing_topic)
        self.assertEqual(checked['transformation_topic_status']['monthly']['权'], 'withheld')
        self.assertEqual(checked['annual_case_status'], 'verified')
        self.assertIn(dict(kind='same_star', key='天机'), checked['transformation_components']['withheld_groups'])
        self.assertNotIn(dict(kind='same_star', key='天同'), checked['transformation_components']['withheld_groups'])

        no_month = deepcopy(current)
        no_month['dynamic']['layers']['monthly']['transformations'].pop()
        scoped = audit(no_month)['transformation_components']
        self.assertEqual((scoped['recorded_status'], scoped['incomplete_layers']), ('unverified', ['monthly']))
        annual = audit(no_month, 'year')
        self.assertEqual(annual['annual_case_status'], 'verified')
        expected = dict(scoped, layers=['natal', 'yearly'], incomplete_layers=[], recorded_status='not_applicable')
        self.assertEqual(annual['transformation_components'], expected)
        self.assertEqual(annual, audit(current, 'year'))
        self.assertEqual(group(expected['groups'], 'same_palace', 4)['component_ids'], ['yearly.禄', 'yearly.权'])

    def test_natal_relationship_cases_replay_without_annual_or_stage_dependencies(self):
        start, end = '2028-06-26T19:00:00+08:00', '2028-06-26T20:00:00+08:00'
        plan = self.query(start, end, 'month')
        segment, = plan['segments']
        probe = segment['probe']
        target, index, civil = (probe[key] for key in ('target_date', 'target_time_index', 'civil_time'))
        options = dict(requested_analysis_year=2028, expected_target_date=target,
                       expected_target_time_index=index, expected_target_civil=civil)

        def read(day, hour, sex, shichen):
            snapshot = json.loads(subprocess.check_output([
                sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', day, '--hour', hour,
                '--sex', sex, '--timezone', 'Asia/Shanghai', '--analysis-year', '2028', '--format', 'json',
            ], cwd=ROOT, text=True, timeout=45))
            facts = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', day, '--birth-year', day[:4], '--shichen-index', str(shichen),
                '--sex', sex, '--source-label', 'natal-case-replay',
                '--target-date', target, '--target-time-index', str(index), '--target-civil', civil,
            ], cwd=ROOT, text=True, timeout=45))
            return snapshot, facts, analyze_snapshot(snapshot), analyze_snapshot(snapshot, facts, **options)

        def audit(point, natal):
            row, = audit_query_windows(plan, {segment['start_inclusive']: point}, natal_panel=natal)['segments']
            return row

        rl, rc1, rc2 = 'ZW-RL01', 'ZW-RC01', 'ZW-RC02'
        verified = dict.fromkeys((rl, rc1, rc2), 'verified')
        admitted = dict(yearly='admitted', monthly='admitted')
        _, _, _, yes_marriage = read('1994-06-21', '16:59', '女', 8)
        _, _, no_marriage_natal, no_marriage = read('1994-06-21', '17:01', '女', 9)
        before, raw, yes_natal, yes = read('1987-06-18', '06:56', '男', 3)
        no_snapshot, no_raw, no_natal, no = read('1987-06-18', '07:03', '男', 4)
        self.assertEqual(yes_marriage['stage_relationship']['relationship']['status'], 'conditional')
        self.assertEqual(no_marriage['stage_relationship']['relationship']['status'], 'not_triggered')
        self.assertEqual(audit(no_marriage, no_marriage_natal)['natal_relationship_status'], verified)
        for rule in (rc1, rc2):
            self.assertEqual(yes['case_judgments']['modules'][rule]['status'], 'conditional')
            self.assertEqual(no['case_judgments']['modules'][rule]['status'], 'not_triggered')

        # A legacy snapshot can retain full spouse geometry and omit the
        # natal stem. Exclusions based only on that geometry remain verifiable.
        del no_snapshot['ziwei']['chart']['lunarInfo']['yearStem']
        old_natal = analyze_snapshot(no_snapshot)
        old_point = analyze_snapshot(no_snapshot, no_raw, **options)
        for rule in (rc1, rc2):
            self.assertEqual(old_point['case_judgments']['modules'][rule]['status'], 'not_triggered')
        result = audit(old_point, old_natal)
        self.assertEqual(result['natal_relationship_status'], verified)
        self.assertEqual(result['dynamic_layers'], admitted)
        self.assertEqual(result['annual_case_status'], 'withheld')
        self.assertEqual(result['stage_status'], 'verified')
        withheld = dict(verified, **{rc1: 'withheld', rc2: 'withheld'})
        self.assertEqual(audit(old_point, no_natal)['natal_relationship_status'], withheld)
        contradicted_point, contradicted_natal = deepcopy(old_point), deepcopy(old_natal)
        natal_transform = next(row for row in no['transformations'] if row['layer'] == 'natal')
        for contradicted in (contradicted_point, contradicted_natal):
            contradicted['transformations'].append(deepcopy(natal_transform))
        self.assertEqual(audit(contradicted_point, old_natal)['natal_relationship_status'], withheld)
        self.assertEqual(audit(old_point, contradicted_natal)['natal_relationship_status'], withheld)
        for rule in (rc1, rc2):
            stale = deepcopy(old_point)
            stale['case_judgments']['modules'][rule] = deepcopy(yes['case_judgments']['modules'][rule])
            self.assertEqual(audit(stale, old_natal)['natal_relationship_status'],
                             dict(verified, **{rule: 'withheld'}))

        incomplete = deepcopy(before)
        del incomplete['ziwei']['chart']['lunarInfo']['yearStem']
        pending = analyze_snapshot(incomplete, raw, **options)
        self.assertEqual(audit(pending, analyze_snapshot(incomplete))['natal_relationship_status'], withheld)

        mixed = deepcopy(no_marriage)
        mixed_natal = deepcopy(no_marriage_natal)
        for panel in (mixed, mixed_natal):
            panel['stage_relationship']['relationship'] = deepcopy(yes_marriage['stage_relationship']['relationship'])
        result = audit(mixed, mixed_natal)
        self.assertEqual(result['natal_relationship_status'], dict(verified, **{rl: 'withheld'}))
        self.assertEqual(result['dynamic_layers'], admitted)
        self.assertEqual(result['stage_status'], 'verified')
        self.assertEqual(result['annual_case_status'], 'verified')
        self.assertEqual(audit(yes_marriage, no_marriage_natal)['natal_relationship_status'],
                         dict.fromkeys(verified, 'unverified'))

        for rule in (rc1, rc2):
            mixed = deepcopy(no)
            mixed['case_judgments']['modules'][rule] = deepcopy(yes['case_judgments']['modules'][rule])
            result = audit(mixed, no_natal)
            self.assertEqual(result['natal_relationship_status'], dict(verified, **{rule: 'withheld'}))
            self.assertEqual(result['dynamic_layers'], admitted)
            self.assertEqual(result['stage_status'], 'verified')

        missing_case = deepcopy(yes)
        del missing_case['case_judgments']['modules'][rc1]['citation']
        self.assertEqual(audit(missing_case, yes_natal)['natal_relationship_status'],
                         dict(verified, **{rc1: 'withheld'}))

        for kind, field, stale in (('科', 'topic', '邻盘误贴主题'), ('忌', 'status', 'withheld')):
            with self.subTest(natal_kind=kind, field=field):
                damaged = deepcopy(yes)
                row = next(row for row in damaged['transformations']
                           if row['layer'] == 'natal' and row['kind'] == kind)
                row[field] = stale
                self.assertEqual(audit(damaged, yes_natal)['natal_relationship_status'], verified)

        wrong_context = deepcopy(yes)
        evidence = next(row for row in wrong_context['case_judgments']['modules'][rc1]['context']['transformations']
                        if row['kind'] == '忌')
        evidence['topic'] = '邻盘误贴主题'
        self.assertEqual(audit(wrong_context, yes_natal), audit(yes, yes_natal))
        evidence['source_path'] += '/wrong'
        self.assertEqual(audit(wrong_context, yes_natal)['natal_relationship_status'],
                         dict(verified, **{rc1: 'withheld'}))

        for kind, expected in (('禄', verified), ('科', verified), ('权', dict(verified, **{rc1: 'withheld'})),
                               ('忌', dict(verified, **{rc1: 'withheld', rc2: 'withheld'}))):
            for bad_field in ('omitted', 'source_path'):
                with self.subTest(projected_kind=kind, bad_field=bad_field):
                    damaged = deepcopy(yes)
                    rows = damaged['transformations']
                    natal_row = next(row for row in rows if row['layer'] == 'natal' and row['kind'] == kind)
                    if bad_field == 'omitted':
                        rows.remove(natal_row)
                    else:
                        natal_row[bad_field] += '/wrong'
                    result = audit(damaged, yes_natal)
                    self.assertEqual(result['natal_relationship_status'], expected)
                    self.assertEqual(result['dynamic_layers'], admitted)
                    self.assertEqual(result['stage_status'], 'verified')
                    self.assertEqual(result['natal_transformation_topic_status'][kind], 'withheld')

        independent_exit = deepcopy(no)
        spouse = next(row for row in no['domains'] if row['domain'] == '夫妻')
        self.assertNotIn('巨门', [fact['name'] for fact in spouse['facts']])
        independent_exit['transformations'] = [row for row in no['transformations'] if row['layer'] != 'natal']
        self.assertEqual(audit(independent_exit, no_natal)['natal_relationship_status'][rc2], 'verified')

        for birth, hour, shichen, off_spouse in (('1987-06-19', '04:25', 2, '权'),
                                                  ('1987-06-20', '07:10', 4, '忌'),
                                                  ('1987-06-20', '06:50', 3, '权忌')):
            _, _, natal, point = read(birth, hour, '男', shichen)
            modules = point['case_judgments']['modules']
            self.assertEqual(modules[rc1]['status'], 'not_triggered')
            context = modules[rc1]['context']
            spouse_majors = [fact for fact in context['domain']['facts'] if fact['type'] == 'major']
            self.assertEqual(len(spouse_majors), 2)
            self.assertEqual({row['kind'] for row in context['transformations']
                              if row['kind'] in '权忌' and row['fact'] not in spouse_majors}, set(off_spouse))
            for unavailable in ('权', '忌', '权忌'):
                for source in ('projection', 'case_context'):
                    with self.subTest(off_spouse=off_spouse, unavailable=unavailable, source=source):
                        damaged = deepcopy(point)
                        if source == 'projection':
                            damaged['transformations'] = [
                                row for row in point['transformations']
                                if not (row['layer'] == 'natal' and row['kind'] in unavailable)
                            ]
                        else:
                            rows = damaged['case_judgments']['modules'][rc1]['context']['transformations']
                            for row in rows:
                                if row['kind'] in unavailable:
                                    row['source_path'] += '/wrong'
                        expected = dict(verified)
                        if not (set(off_spouse) - set(unavailable)):
                            expected[rc1] = 'withheld'
                        if source == 'projection' and '忌' in unavailable and modules[rc2]['status'] == 'conditional':
                            expected[rc2] = 'withheld'
                        result = audit(damaged, natal)
                        self.assertEqual(result['natal_relationship_status'], expected)
                        self.assertEqual(result['dynamic_layers'], admitted)
                        self.assertEqual(result['stage_status'], 'verified')

        missing_layers = deepcopy(yes)
        missing_layers['dynamic']['layers'] = {}
        missing_layers['stage_query_scope']['query_civil_year'] = 2027
        result = audit(missing_layers, yes_natal)
        self.assertEqual(result['natal_relationship_status'], verified)
        self.assertEqual(result['dynamic_layers'], dict(yearly='withheld', monthly='withheld'))
        self.assertEqual(result['stage_status'], 'year_mismatch')

        for kind, expected in (('科', verified), ('权', dict(verified, **{rc1: 'withheld'}))):
            with self.subTest(kind=kind):
                older = deepcopy(before)
                stars = (star for palace in older['ziwei']['chart']['palaces'] for star in palace['stars'])
                next(star for star in stars if star.get('siHua') == kind).pop('siHua')
                point = analyze_snapshot(older, raw, **options)
                result = audit(point, yes_natal)
                self.assertEqual(result['natal_relationship_status'], expected)
                self.assertEqual(result['dynamic_layers'], admitted)
                self.assertEqual(result['annual_case_status'], 'withheld')
                self.assertEqual(result['stage_status'], 'verified')

    def test_life_panels_are_checked_per_probe_birth_and_stage_year(self):
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1987-06-02',
            '--hour', '17:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '2026',
            '--uncertainty-minutes', '2', '--enumerate-scenarios', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        before_hour, after_hour = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual((before_hour['input']['shichen_index'], after_hour['input']['shichen_index']), (8, 9))
        natal = analyze_snapshot(snapshot, ziwei_candidate_id=after_hour['id'])

        def point_panel(segment, candidate, year):
            probe = segment['probe']
            target, index = probe['target_date'], probe['target_time_index']
            dynamic = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '1987-06-02', '--birth-year', '1987',
                '--shichen-index', str(candidate['input']['shichen_index']), '--sex', '男',
                '--source-label', 'window-audit', '--target-date', target, '--target-time-index', str(index),
            ], cwd=ROOT, text=True, timeout=45))
            return analyze_snapshot(snapshot, dynamic, ziwei_candidate_id=candidate['id'],
                                    expected_target_date=target, expected_target_time_index=index,
                                    requested_analysis_year=year)

        month = self.query('2026-11-01T00:00+08:00', '2026-12-01T00:00+08:00', 'month')
        early, late = month['segments']
        early_panel = point_panel(early, after_hour, 2026)
        late_panel = point_panel(late, after_hour, 2026)
        wrong_birth = point_panel(late, before_hour, 2026)
        admitted = dict(yearly='admitted', monthly='admitted')
        early_start, late_start = early['start_inclusive'], late['start_inclusive']

        def check(panels):
            return audit_query_windows(month, panels, natal_panel=natal)['segments']

        self.assertEqual(check({late_start: late_panel})[0]['dynamic_layers'],
                         dict(yearly='unread', monthly='unread'))
        self.assertEqual(check({early_start: early_panel, late_start: late_panel})[0]['dynamic_layers'], admitted)
        self.assertEqual(check({late_start: late_panel})[1]['stage_status'], 'verified')
        tail = {late_start: late_panel}
        truncated = deepcopy(month)
        truncated['segments'] = [late]
        self.assertEqual(audit_query_windows(truncated, tail, natal_panel=natal)['segments'], check(tail))
        subrange = self.query('2026-11-09T00:00+08:00', '2026-12-01T00:00+08:00', 'month')
        self.assertEqual(audit_query_windows(subrange, tail, natal_panel=natal)['segments'], check(tail)[1:])
        expected_request = dict(start=month['requested']['start'], end=month['requested']['end'], layer='month')
        with self.assertRaisesRegex(ValueError, '独立确认的原请求不一致'):
            audit_query_windows(subrange, tail, natal_panel=natal, expected_request=expected_request)

        def ji(panel):
            return next(row for row in panel['dynamic']['layers']['monthly']['transformations'] if row['kind'] == '忌')

        self.assertEqual(ji(early_panel)['star'], '天机')
        self.assertEqual(ji(late_panel)['star'], '文曲')

        def reuse_layer(previous, current, layer, *, copy_labels):
            cached = deepcopy(current)
            earlier_layer = previous['dynamic']['layers'][layer]
            target_layer = cached['dynamic']['layers'][layer]
            if copy_labels:
                for key in ('heavenly_stem', 'earthly_branch'):
                    target_layer[key] = earlier_layer[key]
            for owner, previous_owner in ((target_layer, earlier_layer),
                                           (cached['dynamic'], previous['dynamic']), (cached, previous)):
                owner['transformations'] = [
                    row for row in owner['transformations'] if row['layer'] != layer]
                owner['transformations'].extend(
                    dict(row, query_point=cached['dynamic']['query_point'])
                    for row in previous_owner['transformations'] if row['layer'] == layer)
            return cached

        for copy_labels in (True, False):
            with self.subTest(copy_labels=copy_labels):
                stale_month = reuse_layer(early_panel, late_panel, 'monthly', copy_labels=copy_labels)
                checked = check({early_start: early_panel, late_start: stale_month})
                self.assertEqual(checked[0]['dynamic_layers'], admitted)
                self.assertEqual(checked[1]['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
                self.assertEqual(checked[1]['stage_status'], 'verified')
                self.assertEqual(checked[1]['stage_models'], dict(status='verified', unverified_rules=[]))

        def reuse_coordinates(previous, current, layer):
            cached = deepcopy(current)
            older = previous['dynamic']['layers'][layer]
            row = cached['dynamic']['layers'][layer]
            for key in ('ming_coordinate', 'domain_coordinates'):
                row[key] = deepcopy(older[key])
            return cached

        earlier_ming = early_panel['dynamic']['layers']['monthly']['ming_coordinate']['earthly_branch']
        later_ming = late_panel['dynamic']['layers']['monthly']['ming_coordinate']['earthly_branch']
        self.assertEqual((earlier_ming, later_ming), ('未', '申'))
        wrong_index, missing_domains, wrong_role = (deepcopy(late_panel) for _ in range(3))
        wrong_index['dynamic']['layers']['monthly']['ming_coordinate']['iztro_array_index'] ^= 1
        del missing_domains['dynamic']['layers']['monthly']['domain_coordinates']
        wrong_role['dynamic']['layers']['monthly']['domain_coordinates'][0]['layer_palace_name'] = '未知'
        reference = check({late_start: late_panel})[1]
        for bad_month in (reuse_coordinates(early_panel, late_panel, 'monthly'),
                          wrong_index, missing_domains, wrong_role):
            checked = check({late_start: bad_month})[1]
            self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
            for key in ('stage_status', 'stage_models', 'annual_case_status',
                        'natal_relationship_status', 'natal_domain_topic_status'):
                self.assertEqual(checked[key], reference[key])

        new_year = self.query('2026-02-16T00:00+08:00', '2026-02-18T00:00+08:00', 'year')
        old_year, following_year = new_year['segments']
        old_panel = point_panel(old_year, after_hour, 2026)
        following_panel = point_panel(following_year, after_hour, 2026)
        for panel, expected in ((following_panel, 'admitted'),
                                (reuse_layer(old_panel, following_panel, 'yearly', copy_labels=False), 'withheld'),
                                (reuse_coordinates(old_panel, following_panel, 'yearly'), 'withheld')):
            checked = audit_query_windows(new_year, {following_year['start_inclusive']: panel}, natal_panel=natal)
            self.assertEqual(checked['segments'][1]['dynamic_layers'], dict(yearly=expected))
            self.assertEqual(checked['segments'][1]['stage_status'], 'verified')

        for projection in ('layer', 'dynamic', 'reading'):
            with self.subTest(projection=projection):
                incomplete = deepcopy(early_panel)
                if projection == 'layer':
                    incomplete['dynamic']['layers']['monthly']['transformations'].pop()
                else:
                    owner = incomplete['dynamic'] if projection == 'dynamic' else incomplete
                    owner['transformations'] = [row for row in owner['transformations']
                                                if (row['layer'], row['kind']) != ('monthly', '忌')]
                checked = check({early_start: incomplete})[0]
                self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
                self.assertEqual(checked['stage_status'], 'verified')

        no_attachment = deepcopy(early_panel)
        for owner in (no_attachment['dynamic']['layers']['monthly'], no_attachment['dynamic'], no_attachment):
            next(row for row in owner['transformations'] if row['id'] == 'monthly.忌').pop('fact', None)
        self.assertEqual(check({early_start: no_attachment})[0]['dynamic_layers'],
                         dict(yearly='admitted', monthly='withheld'))

        for field in ('source_path', 'mutagen_pointer', 'attached_palace', 'attached_star_pointer'):
            with self.subTest(field=field):
                cached = deepcopy(early_panel)
                month_layer = cached['dynamic']['layers']['monthly']
                for owner in (month_layer, cached['dynamic'], cached):
                    row = next(row for row in owner['transformations'] if row['id'] == 'monthly.忌')
                    attachment = row['admitted_attachment']
                    location, = attachment['natal_star_locations']
                    if field == 'source_path':
                        row['source_path'] = row['source_path'].replace('/monthly/', '/yearly/')
                    elif field == 'mutagen_pointer':
                        attachment['raw_pointer'] = attachment['raw_pointer'].replace('/monthly/', '/yearly/')
                    elif field == 'attached_palace':
                        other = next(row['natal_coordinate'] for row in month_layer['domain_coordinates']
                                     if row['natal_coordinate']['branch_index'] != location['location']['branch_index'])
                        location['location'] = deepcopy(other)
                    else:
                        location['raw_pointer'] = location['raw_pointer'].replace('/majorStars/', '/minorStars/')
                checked = check({early_start: cached})[0]
                self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='withheld'))
                self.assertEqual(checked['stage_status'], 'verified')
                self.assertEqual(checked['natal_relationship_status'],
                                 check({early_start: early_panel})[0]['natal_relationship_status'])

        cached = deepcopy(early_panel)
        del cached['dynamic']['layers']['monthly']['ming_coordinate']['raw_pointer']
        self.assertEqual(check({early_start: cached})[0]['dynamic_layers'], admitted)
        cached['dynamic']['layers']['monthly']['ming_coordinate']['raw_pointer'] = (
            '/research_dynamic_iztro/source_astrolabe/palaces/99')
        self.assertEqual(check({early_start: cached})[0]['dynamic_layers'],
                         dict(yearly='admitted', monthly='withheld'))

        reordered = deepcopy(early_panel)
        reordered['dynamic']['transformations'].reverse()
        reordered['transformations'].reverse()
        self.assertEqual(check({early_start: reordered})[0]['dynamic_layers'], admitted)

        detached = deepcopy(early_panel)
        detached['dynamic']['status'] = 'withheld'
        self.assertEqual(check({early_start: detached})[0]['dynamic_layers'],
                         dict(yearly='withheld', monthly='withheld'))

        partial = deepcopy(early_panel)
        partial['dynamic']['status'] = 'partial'
        partial['dynamic']['layers']['monthly'] = dict(status='withheld', transformations=[])
        for owner in (partial['dynamic'], partial):
            owner['transformations'] = [row for row in owner['transformations'] if row['layer'] != 'monthly']
        self.assertEqual(check({early_start: partial})[0]['dynamic_layers'],
                         dict(yearly='admitted', monthly='withheld'))

        stale = check({early_start: late_panel})[0]
        self.assertEqual(stale['dynamic_layers'], dict(yearly='point_mismatch', monthly='point_mismatch'))
        self.assertEqual(stale['stage_status'], 'verified')
        self.assertEqual(stale['stage_models'], dict(status='verified', unverified_rules=[]))
        relabeled = deepcopy(late_panel)
        relabeled['dynamic']['query_point'] = early_panel['dynamic']['query_point']
        self.assertEqual(check({early_start: relabeled})[0]['dynamic_layers'], stale['dynamic_layers'])
        wrong = check({late_start: wrong_birth})[1]
        self.assertEqual(wrong['dynamic_layers'], dict(yearly='birth_mismatch', monthly='birth_mismatch'))
        self.assertEqual(wrong['stage_status'], 'birth_mismatch')

        future = self.query('2032-11-09T00:00+08:00', '2032-11-10T00:00+08:00', 'month')
        future_segment, = future['segments']
        future_start = future_segment['start_inclusive']
        future_panel = point_panel(future_segment, after_hour, 2032)
        old_stage = point_panel(future_segment, after_hour, 2026)
        for panel, expected in ((future_panel, 'verified'), (old_stage, 'year_mismatch')):
            row, = audit_query_windows(future, {future_start: panel}, natal_panel=natal)['segments']
            self.assertEqual(row['dynamic_layers'], admitted)
            self.assertEqual(row['stage_status'], expected)
            self.assertEqual(row['stage_current_status'], 'active' if expected == 'verified' else 'unverified')

        future_stages = future_panel['stage_relationship']['stages']
        original, = [stage['legacy_stage']['domain'] for stage in future_stages if stage['legacy_stage']['current']]
        previous, = [stage['legacy_stage']['domain'] for stage in old_stage['stage_relationship']['stages']
                     if stage['legacy_stage']['current']]
        self.assertEqual((previous, original), ('子女', '财帛'))
        for change in ('old_projection', 'missing_projection', 'missing_t02', 'relabeled',
                       'wrong_palace', 'coherent_swap', 'reordered'):
            with self.subTest(change=change):
                saved = deepcopy(future_panel)
                stage = saved['stage_relationship']
                t02 = saved['modules']['ZW-T02']['rows'][0]
                if change == 'old_projection':
                    stage['stages'] = old_stage['stage_relationship']['stages']
                elif change == 'missing_projection':
                    stage['stages'] = []
                elif change == 'missing_t02':
                    t02['rows'] = []
                elif change == 'relabeled':
                    old_index = old_stage['stage_relationship']['stage_contract']['current_index']
                    stage['stage_contract']['current_index'] = t02['current_index'] = old_index
                    for rows in (t02['rows'], [item['legacy_stage'] for item in stage['stages']]):
                        for item in rows:
                            item['current'] = item['index'] == old_index
                elif change == 'wrong_palace':
                    for rows in (t02['rows'], [item['legacy_stage'] for item in stage['stages']]):
                        item = next(row for row in rows if row['current'])
                        item['domain'] = item['native']['palaceName'] = previous
                elif change == 'coherent_swap':
                    for rows in (t02['rows'], [item['legacy_stage'] for item in stage['stages']]):
                        index, = [i for i, row in enumerate(rows) if row['current']]
                        left, right = rows[index:index + 2]
                        for field in ('domain', 'role', 'topic_fact_paths'):
                            left[field], right[field] = right[field], left[field]
                        for field in ('palaceBranch', 'palaceName'):
                            left['native'][field], right['native'][field] = right['native'][field], left['native'][field]
                else:
                    t02['rows'].reverse()
                    stage['stages'].reverse()
                row, = audit_query_windows(future, {future_start: saved}, natal_panel=natal)['segments']
                self.assertEqual(row['dynamic_layers'], admitted)
                expected = ('verified', 'active') if change == 'reordered' else ('withheld', 'unverified')
                self.assertEqual((row['stage_status'], row['stage_current_status']), expected)
                self.assertEqual(row['stage_models']['status'], 'verified' if change == 'reordered' else 'unverified')
                if change == 'coherent_swap':
                    missing_baseline = deepcopy(natal)
                    del missing_baseline['modules']['ZW-T02']
                    for source, expected in ((future_panel, ('verified', 'active')),
                                             (saved, ('withheld', 'unverified'))):
                        row, = audit_query_windows(future, {future_start: source},
                                                   natal_panel=missing_baseline)['segments']
                        self.assertEqual(row['dynamic_layers'], admitted)
                        self.assertEqual((row['stage_status'], row['stage_current_status']), expected)

        infancy = self.query('1987-11-01T00:00+08:00', '1987-11-02T00:00+08:00', 'month')
        infancy_segment, = infancy['segments']
        infancy_panel = point_panel(infancy_segment, after_hour, 1987)
        infancy_start = infancy_segment['start_inclusive']
        row, = audit_query_windows(infancy, {infancy_start: infancy_panel}, natal_panel=natal)['segments']
        self.assertEqual(row['dynamic_layers'], admitted)
        self.assertEqual(row['stage_status'], 'verified')
        self.assertEqual(row['stage_current_status'], 'before_first_stage')
        self.assertEqual(row['stage_models'], dict(status='not_applicable', unverified_rules=[]))

        stage_unverified = deepcopy(infancy_panel)
        stage_unverified['stage_relationship']['stage_contract'] = None
        row, = audit_query_windows(infancy, {infancy_start: stage_unverified},
                                   natal_panel=stage_unverified)['segments']
        self.assertEqual(row['dynamic_layers'], admitted)
        self.assertEqual(row['stage_status'], 'withheld')
        self.assertEqual(row['stage_current_status'], 'unverified')

    def test_verified_pre_stage_excludes_annual_stage_precondition_without_yearly_facts(self):
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', '1901-04-11',
            '--hour', '02:00', '--sex', '男', '--utc-offset', '8', '--analysis-year', '1901', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        natal = analyze_snapshot(snapshot)
        contract = natal['stage_relationship']['stage_contract']
        start = contract['covered_window']['start_inclusive']
        end = contract['covered_window']['end_exclusive']
        expected_unknown = dict(status='unverified', domain=None, window=None)

        def read(day, *, include_year):
            stop = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
            plan = self.query(day + 'T00:00+08:00', stop + 'T00:00+08:00', 'month')
            point = plan['segments'][0]['probe']['civil_time']
            facts = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '1901-04-11', '--birth-year', '1901', '--shichen-index', '1',
                '--sex', '男', '--target-date', day, '--target-time-index', '0', '--target-civil', point,
                '--source-label', 'independent-pre-stage-test',
            ], cwd=ROOT, text=True, timeout=45))
            if not include_year:
                del facts['admitted_dynamic_facts']['layers']['yearly']
            panel = analyze_snapshot(snapshot, facts, requested_analysis_year=int(day[:4]),
                                     expected_target_date=day, expected_target_time_index=0, expected_target_civil=point)
            return plan, point, panel

        def audit(plan, point, panel):
            row, = audit_query_windows(plan, {point: panel}, natal_panel=natal)['segments']
            return row

        before = '1901-04-12'
        plan, point, monthly_only = read(before, include_year=False)
        row = audit(plan, point, monthly_only)
        expected_exit = dict(status='excluded', domain=None, window=None, reason='before_first_stage',
                             first_stage_start=start)
        self.assertEqual(row['dynamic_layers'], dict(yearly='withheld', monthly='admitted'))
        self.assertEqual((row['stage_status'], row['stage_current_status']), ('verified', 'before_first_stage'))
        self.assertEqual(row['annual_case_stage_precondition'], expected_exit)
        self.assertEqual(row['annual_case_status'], 'unverified')
        self.assertEqual(monthly_only['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
        self.assertEqual(audit(*read(before, include_year=True))['annual_case_status'], 'verified')

        unknown = deepcopy(monthly_only)
        unknown['stage_relationship']['stage_contract'] = None
        self.assertEqual(audit(plan, point, unknown)['annual_case_stage_precondition'], expected_unknown)
        after = audit(*read(end, include_year=False))
        self.assertEqual((after['stage_status'], after['stage_current_status']), ('verified', 'after_last_stage'))
        self.assertEqual(after['annual_case_stage_precondition'], expected_unknown)


    def test_actual_birth_boundary_splits_same_index_and_preserves_post_birth(self):
        born = '1987-06-02'
        exact = json.loads(subprocess.check_output([
            sys.executable, '-B', 'scripts/build_chart.py', '--solar', born, '--hour', '17:01',
            '--utc-offset', '8', '--sex', '男', '--analysis-year', '1987', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        band = birth_time_candidates(date.fromisoformat(born), '16:58', '17:02', '男', 1987, utc_offset=8)
        candidate_id = band['candidates'][1]['id']
        dynamic_command = [
            'node', str(POINT), '--solar', born, '--birth-year', '1987', '--shichen-index', '9', '--sex', '男',
            '--source-label', 'birth-window-test', '--target-date', born, '--target-time-index', '9',
        ]
        bare_dynamic = json.loads(subprocess.check_output(dynamic_command, cwd=ROOT, text=True, timeout=45))
        plan = query_windows(born + 'T16:59+08:00', born + 'T17:04+08:00', 'day')
        for snapshot, selected, boundary, expected in (
                (exact, None, '17:01', ['before_birth', 'after_birth']),
                (band, candidate_id, '17:02', ['before_birth', 'birth_time_uncertain', 'after_birth'])):
            with self.subTest(selected=selected):
                natal = analyze_snapshot(snapshot, ziwei_candidate_id=selected)
                options = dict(ziwei_candidate_id=selected, expected_target_date=born,
                               expected_target_time_index=9, requested_analysis_year=1987)
                bare = analyze_snapshot(snapshot, bare_dynamic, **options)
                self.assertEqual(bare['dynamic']['birth_time_status'], 'birth_time_unverified')
                self.assertEqual(bare['stage_query_scope']['status'], 'birth_time_unverified')
                self.assertTrue(bare['domains'])
                self.assertEqual(bare['modules']['ZW-T02']['status'], 'conditional')
                rows = audit_query_windows(plan, {}, natal_panel=natal)['segments']
                self.assertEqual([row['birth_time_status'] for row in rows], expected)
                self.assertEqual(rows[-1]['start_inclusive'], born + f'T{boundary}:00+08:00')
                self.assertEqual(rows[-1]['probe']['target_time_index'], 9)
                self.assertTrue(rows[-1]['requires_civil_clock'])
                self.assertEqual(rows[-1]['dynamic_layers'], dict(yearly='unread', monthly='unread'))
                clock = rows[-1]['probe']['civil_time']
                dynamic = json.loads(subprocess.check_output([*dynamic_command, '--target-civil', clock],
                                                            cwd=ROOT, text=True, timeout=45))
                point = analyze_snapshot(snapshot, dynamic, expected_target_civil=clock, **options)
                self.assertEqual(point['dynamic']['status'], 'admitted')
                stale = deepcopy(point)
                stale['dynamic']['query_point'].pop('civil_time')
                for owner in (stale, stale['dynamic'], *stale['dynamic']['layers'].values()):
                    for item in owner['transformations']:
                        if 'query_point' in item:
                            item['query_point'].pop('civil_time', None)
                stale_audit = audit_query_windows(plan, {clock: stale}, natal_panel=natal)['segments']
                self.assertEqual(stale_audit[-1]['dynamic_layers'],
                                 dict(yearly='point_mismatch', monthly='point_mismatch'))
                panels = {row['start_inclusive']: point for row in rows}
                audited = audit_query_windows(plan, panels, natal_panel=natal)['segments']
                for row, status in zip(audited[:-1], expected[:-1]):
                    self.assertEqual(row['dynamic_layers'], dict(yearly=status, monthly=status))
                    self.assertEqual(row['stage_status'], status)
                self.assertEqual(audited[-1]['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
                self.assertEqual(audited[-1]['stage_current_status'], 'before_first_stage')

        natal = exact['ziwei']['life_reading']
        same_instants = query_windows(born + 'T21:00+12:00', born + 'T21:02+12:00', 'month')
        rows = audit_query_windows(same_instants, {}, natal_panel=natal)['segments']
        self.assertEqual([row['birth_time_status'] for row in rows], ['before_birth', 'after_birth'])
        self.assertEqual(rows[-1]['start_inclusive'], born + 'T21:01:00+12:00')

        legacy = analyze_native_shichen(exact['ziwei'], born, '酉', '男', bare_dynamic,
                                        expected_target_date=born, expected_target_time_index=9,
                                        requested_analysis_year=1987)
        self.assertEqual(legacy['dynamic']['birth_time_status'], 'birth_time_unverified')
        with self.assertRaisesRegex(ValueError, '最晚边界'):
            analyze_native_shichen(exact['ziwei'], born, '酉', '男', bare_dynamic,
                                   expected_target_date=born, expected_target_time_index=9,
                                   expected_target_civil=born + 'T17:02:00+08:00')
        unverified, = audit_query_windows(plan, {plan['segments'][0]['start_inclusive']: legacy},
                                          natal_panel=legacy)['segments']
        self.assertEqual(unverified['dynamic_layers'], dict.fromkeys(('yearly', 'monthly'), 'birth_time_unverified'))
        self.assertEqual(unverified['stage_status'], 'birth_time_unverified')

    def test_post_birth_probe_keeps_fractional_offset_seconds(self):
        for birth_offset in ('8', '0'):
            with self.subTest(birth_offset=birth_offset):
                self.check_post_birth_fractional_offset(birth_offset)

    def check_post_birth_fractional_offset(self, birth_offset):
        born = '2026-11-09'
        offset = f'+{int(birth_offset):02d}:00'
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', str(SCRIPTS / 'build_chart.py'), '--solar', born, '--hour', '00:00',
            '--utc-offset', birth_offset, '--sex', '男', '--analysis-year', '2026', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        plan = self.query(born + 'T00:00:00.4' + offset + ':00.5',
                          born + 'T00:01:00.5' + offset + ':00.5', 'day')
        natal = analyze_snapshot(snapshot)
        before, after = audit_query_windows(plan, {}, natal_panel=natal)['segments']
        self.assertEqual((before['birth_time_status'], after['birth_time_status']),
                         ('before_birth', 'after_birth'))
        self.assertTrue(after['requires_civil_clock'])
        clock = after['probe']['civil_time']
        self.assertEqual(clock, born + 'T00:00:00.500000' + offset + ':00.500000')
        dynamic = json.loads(subprocess.check_output([
            'node', str(POINT), '--solar', born, '--birth-year', '2026', '--shichen-index', '0',
            '--sex', '男', '--source-label', 'fractional-offset-test', '--target-date', born,
            '--target-time-index', '0', '--target-civil', clock,
        ], cwd=ROOT, text=True, timeout=45))
        self.assertEqual(dynamic['inputs']['target']['civil_time'], clock)
        request = dict(expected_target_date=born, expected_target_time_index=0, requested_analysis_year=2026)
        point = analyze_snapshot(snapshot, dynamic, expected_target_civil=clock, **request)
        audited = audit_query_windows(plan, {clock: point}, natal_panel=natal)['segments'][-1]
        self.assertEqual(audited['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        self.assertEqual((audited['stage_status'], audited['stage_current_status']),
                         ('verified', 'before_first_stage'))
        with self.assertRaisesRegex(ValueError, '最晚边界'):
            analyze_snapshot(snapshot, dynamic, expected_target_civil=before['probe']['civil_time'], **request)
        changed = analyze_snapshot(snapshot, dynamic, expected_target_civil=born + 'T00:00:00' + offset, **request)
        self.assertEqual(changed['dynamic']['status'], 'withheld')

    def test_birth_order_for_later_local_dates_and_wide_unenumerated_uncertainty(self):
        build = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '2026-01-03', '--hour', '23:30',
                 '--utc-offset', '-12', '--sex', '男', '--analysis-year', '2026', '--format', 'json']
        exact, wide = [json.loads(subprocess.check_output([*build, *flags], cwd=ROOT, text=True, timeout=45))
                       for flags in ((), ('--uncertainty-minutes', '3000'))]

        def point(snapshot, day, index, clock=None):
            clock_args = ['--target-civil', clock] if clock else []
            dynamic = json.loads(subprocess.check_output([
                'node', str(POINT), '--solar', '2026-01-03', '--birth-year', '2026',
                '--shichen-index', '0', '--sex', '男', '--source-label', 'birth-order-test',
                '--target-date', day, '--target-time-index', str(index), *clock_args,
            ], cwd=ROOT, text=True, timeout=45))
            return analyze_snapshot(snapshot, dynamic, expected_target_date=day,
                                    expected_target_time_index=index, expected_target_civil=clock,
                                    requested_analysis_year=2026)

        for snapshot in (exact, wide):
            bare = point(snapshot, '2026-01-05', 0)
            self.assertEqual(bare['dynamic']['birth_time_status'], 'birth_time_unverified')
            with self.assertRaisesRegex(ValueError, '最晚边界'):
                point(snapshot, '2026-01-05', 0, '2026-01-05T00:00:00+14:00')
        self.assertEqual(point(exact, '2026-01-05', 1, '2026-01-05T01:30:00+14:00')['dynamic']['status'],
                         'admitted')
        last = '2026-01-06T13:30:00+00:00'
        with self.assertRaisesRegex(ValueError, '最晚边界'):
            point(wide, '2026-01-06', 7, '2026-01-06T13:29:59+00:00')
        after = point(wide, '2026-01-06', 7, last)
        self.assertEqual(after['birth_time_bounds']['latest_utc'], last)
        self.assertEqual(after['dynamic']['status'], 'admitted')
        self.assertTrue(after['temporal_uncertainty'])

    def test_repeated_birth_clock_uses_original_fold_and_rejects_conflicting_cache(self):
        birth = '2024-11-03'
        build = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', birth, '--hour', '01:15',
                 '--timezone', 'America/New_York', '--sex', '男', '--analysis-year', '2024', '--format', 'json']
        plan = self.query(birth + 'T01:30-04:00', birth + 'T01:10-05:00', 'day', 'America/New_York')
        early, late = [json.loads(subprocess.check_output([*build, '--fold', str(fold)],
                                                          cwd=ROOT, text=True, timeout=45)) for fold in (0, 1)]
        for snapshot, expected in ((early, 'after_birth'), (late, 'before_birth')):
            natal = analyze_snapshot(snapshot)
            rows = audit_query_windows(plan, {}, natal_panel=natal)['segments']
            self.assertEqual([row['birth_time_status'] for row in rows], [expected, expected])
        wrong = dict(late, time=early['time'])
        with self.assertRaisesRegex(ValueError, '已存出生瞬间、时区或 fold 与原出生输入不一致'):
            audit_query_windows(plan, {}, natal_panel=analyze_snapshot(wrong))

    def test_earlier_local_date_keeps_post_birth_lunar_facts_and_separate_stage_year(self):
        for born, target, expected_year, pillars, stage_status in (
                ('2024-02-10', '2024-02-09', 2024, ('癸卯', '乙丑'), 'verified'),
                ('1987-01-01', '1986-12-31', 1987, ('丙寅', '辛丑'), 'before_birth_civil_year')):
            with self.subTest(born=born):
                born_year, target_year = int(born[:4]), int(target[:4])
                snapshot = json.loads(subprocess.check_output([
                    sys.executable, '-B', 'scripts/build_chart.py', '--solar', born, '--hour', '00:01',
                    '--utc-offset', '14', '--sex', '男', '--analysis-year', str(born_year), '--format', 'json',
                ], cwd=ROOT, text=True, timeout=45))
                natal = analyze_snapshot(snapshot)
                start, end = target + 'T00:00-10:00', target + 'T00:03-10:00'
                plan = query_windows(start, end, 'day')
                before, after = audit_query_windows(plan, {}, natal_panel=natal)['segments']
                self.assertEqual((before['birth_time_status'], after['birth_time_status']), ('before_birth', 'after_birth'))
                clock = after['probe']['civil_time']
                self.assertEqual(clock, target + 'T00:01:00-10:00')
                command = ['node', str(POINT), '--solar', born, '--birth-year', str(born_year),
                           '--shichen-index', '0', '--sex', '男', '--source-label', 'cross-clock-test',
                           '--target-date', target, '--target-time-index', '0']
                legacy = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(legacy.returncode, 0)
                self.assertIn('Target precedes synthetic birth input', legacy.stderr)
                raw = json.loads(subprocess.check_output([*command, '--target-civil', clock],
                                                         cwd=ROOT, text=True, timeout=45))
                self.assertEqual(raw['native_wrapper_snapshot']['input']['ageYear'], expected_year)
                layers = raw['admitted_dynamic_facts']['layers']
                self.assertEqual(tuple(layers[key]['heavenly_stem'] + layers[key]['earthly_branch']
                                       for key in ('yearly', 'monthly')), pillars)
                request = dict(expected_target_date=target, expected_target_time_index=0)
                self.assertEqual(analyze_snapshot(snapshot, raw, **request)['dynamic']['status'], 'withheld')
                with self.assertRaisesRegex(ValueError, '最晚边界'):
                    analyze_snapshot(snapshot, raw, **request, expected_target_civil=before['probe']['civil_time'])
                point = analyze_snapshot(snapshot, raw, **request, expected_target_civil=clock,
                                         requested_analysis_year=target_year)
                self.assertEqual(point['dynamic']['status'], 'admitted')
                self.assertEqual(point['stage_query_scope']['status'], stage_status)
                audited = audit_query_windows(plan, {clock: point}, natal_panel=natal)['segments'][-1]
                self.assertEqual(audited['stage_status'], stage_status)
                self.assertEqual(audited['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
                later_clock = target + 'T00:02:00-10:00'
                wrong = analyze_snapshot(snapshot, raw, **request, expected_target_civil=later_clock)
                self.assertEqual(wrong['dynamic']['status'], 'withheld')
                later_plan = query_windows(later_clock, end, 'day')
                later, = audit_query_windows(later_plan, {later_clock: point}, natal_panel=natal)['segments']
                self.assertEqual(later['dynamic_layers'], dict(yearly='point_mismatch', monthly='point_mismatch'))
                stripped = deepcopy(point)
                dynamic = stripped['dynamic']
                dynamic['query_point'].pop('civil_time')
                for item in [*dynamic['transformations'], *stripped['transformations'],
                             *(item for layer in dynamic['layers'].values() for item in layer['transformations'])]:
                    item.get('query_point', {}).pop('civil_time', None)
                stripped_row = audit_query_windows(plan, {clock: stripped}, natal_panel=natal)['segments'][-1]
                self.assertEqual(stripped_row['dynamic_layers'], dict(yearly='point_mismatch', monthly='point_mismatch'))

    def test_invalid_or_unsupported_query_ranges_fail_without_a_plan(self):
        for start, end, layer in [
                ('2026-02-30', '2026-03-05', 'month'), ('2026-11-11', '2026-11-11', 'month'),
                ('1900-12-31', '1901-01-02', 'year'), ('2099-12-31', '2100-01-02', 'year'),
                ('2026-11-01', '2026-11-02', 'hour')]:
            with self.subTest(start=start, end=end, layer=layer):
                result = subprocess.run(self.command(start, end, layer), cwd=ROOT, capture_output=True,
                                        text=True, timeout=45)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertTrue(result.stderr)


if __name__ == '__main__':
    unittest.main()
