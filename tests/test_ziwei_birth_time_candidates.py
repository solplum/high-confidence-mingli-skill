"""Run the real native branch entry and reuse checked civil clock bands."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ziwei_birth_time_candidates import _reachable_shichen
from ziwei_life_reading import analyze_snapshot
from ziwei_query_windows import audit_query_windows, query_windows


@unittest.skipUnless(shutil.which('node') and (ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(),
                     'Node and locked Ziwei dependencies required')
class ZiweiBirthTimeCandidatesTests(unittest.TestCase):
    def command(self, day, start, end, *zone):
        return [sys.executable, '-B', 'scripts/ziwei_birth_time_candidates.py', '--birth-date', day,
                '--start', start, '--end', end, '--sex', '男', '--analysis-year', '2026', *zone]

    def test_confirmed_afternoon_runs_all_three_native_branches(self):
        command = self.command('1988-10-18', '13:00', '19:00', '--utc-offset', '8')
        panel = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        self.assertEqual(panel['status'], 'conditional')
        self.assertFalse(panel['birth_time_confirmed'])
        self.assertEqual([r['input']['shichen_index'] for r in panel['candidates']], [7, 8, 9])
        self.assertEqual([r['native']['input']['shichenIndex'] for r in panel['candidates']], [7, 8, 9])
        self.assertEqual([r['civil_spans'][0]['start_inclusive'][11:16] for r in panel['candidates']],
                         ['13:00', '15:00', '17:00'])
        self.assertEqual([r['civil_spans'][0]['end_exclusive'][11:16] for r in panel['candidates']],
                         ['15:00', '17:00', '19:00'])
        self.assertTrue(all(len(r['life_reading']['domains']) == 12 for r in panel['candidates']))
        self.assertTrue(all('hour' not in r['input'] for r in panel['candidates']))

    def test_unreachable_clock_band_and_unspecified_day_fail(self):
        for day, start, end, zone, error in (
                ('2018-11-04', '00:00', '01:00', ('--timezone', 'America/Sao_Paulo'), '无可达时刻'),
                ('1988-10-18', '00:00', '24:00', ('--utc-offset', '8'), '时辰未知')):
            with self.subTest(day=day):
                result = subprocess.run(self.command(day, start, end, *zone), cwd=ROOT,
                                        text=True, capture_output=True, timeout=45)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(error, result.stderr)

    def test_saved_band_continuation_replays_coverage_and_selected_native_chart(self):
        command = self.command('1987-03-06', '10:58', '11:02', '--utc-offset', '8')
        snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        selected, neighbor = snapshot['candidates']
        target = '2026-11-09'
        facts = {}
        for candidate in (selected, neighbor):
            index = candidate['input']['shichen_index']
            cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1987-03-06', '--birth-year', '1987',
                   '--shichen-index', str(index), '--sex', '男', '--target-date', target,
                   '--target-time-index', '0', '--source-label', 'synthetic-saved-band-reuse']
            facts[candidate['id']] = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True, timeout=45))
        query = dict(ziwei_candidate_id=selected['id'], expected_target_date=target,
                     expected_target_time_index=0)
        valid_dynamic = facts[selected['id']]
        valid = analyze_snapshot(snapshot, valid_dynamic, **query)
        self.assertEqual(valid['dynamic']['status'], 'admitted')
        self.assertEqual(valid['birth_scenario']['civil_spans'], selected['civil_spans'])
        self.assertFalse(valid['birth_scenario']['birth_time_confirmed'])
        self.assertEqual(valid['domains'], selected['life_reading']['domains'])
        self.assertEqual(valid['birth_scenario'], selected['life_reading']['birth_scenario'])
        plan = query_windows(target, '2026-11-10', 'month', 'Asia/Shanghai')
        start = plan['segments'][0]['start_inclusive']
        same, = audit_query_windows(plan, {start: valid}, natal_panel=selected['life_reading'])['segments']
        self.assertEqual(same['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        other, = audit_query_windows(plan, {start: valid}, natal_panel=neighbor['life_reading'])['segments']
        self.assertEqual(other['dynamic_layers'], dict(yearly='birth_mismatch', monthly='birth_mismatch'))
        self.assertEqual(valid['case_judgments']['modules']['ZW-RC01']['status'], 'not_triggered')
        wrong_dynamic = analyze_snapshot(snapshot, facts[neighbor['id']], **query)
        self.assertEqual(wrong_dynamic['dynamic']['status'], 'withheld')
        self.assertEqual(wrong_dynamic['domains'], valid['domains'])
        self.assertEqual(wrong_dynamic['stage_relationship'], valid['stage_relationship'])
        wrong_point = analyze_snapshot(snapshot, valid_dynamic, **dict(query, expected_target_date='2026-11-01'))
        self.assertEqual(wrong_point['dynamic']['status'], 'withheld')
        self.assertEqual(wrong_point['domains'], valid['domains'])
        self.assertIn('与本次请求不一致', wrong_point['dynamic']['errors'][0])
        with self.assertRaisesRegex(ValueError, '预期日期'):
            analyze_snapshot(snapshot, valid_dynamic, ziwei_candidate_id=selected['id'])

        missing_peer = deepcopy(snapshot)
        missing_peer['candidates'].pop()
        changed_span = deepcopy(snapshot)
        changed_span['candidates'][1]['civil_spans'][0]['start_utc'] = '1987-03-06T03:01:00+00:00'
        wrong_chart = deepcopy(snapshot)
        wrong_chart['candidates'][0]['native']['chart'] = deepcopy(neighbor['native']['chart'])
        wrong_year = deepcopy(snapshot)
        wrong_year['candidates'][0]['native']['input']['ageYear'] = 2025
        for data, reason in ((missing_peer, '未覆盖'), (changed_span, '实际可达区间'),
                             (wrong_chart, '原盘与出生区间复盘'), (wrong_year, '原盘与出生区间复盘')):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                analyze_snapshot(data, valid_dynamic, **query)

        stale_derived = deepcopy(snapshot)
        stale_derived['candidates'][0]['life_reading'] = deepcopy(neighbor['life_reading'])
        self.assertEqual(analyze_snapshot(stale_derived, valid_dynamic, **query), valid)
        with TemporaryDirectory() as directory:
            path = Path(directory)
            band_file = path / 'band.json'
            dynamic_file = path / 'dynamic.json'
            dynamic_file.write_text(json.dumps(valid_dynamic), encoding='utf-8')
            cli = [sys.executable, '-B', 'scripts/ziwei_life_reading.py', '--snapshot', str(band_file),
                   '--ziwei-candidate', selected['id'], '--dynamic', str(dynamic_file),
                   '--expected-target-date', target, '--expected-target-time-index', '0']
            band_file.write_text(json.dumps(snapshot), encoding='utf-8')
            self.assertEqual(json.loads(subprocess.check_output(cli, cwd=ROOT, text=True, timeout=45)), valid)
            band_file.write_text(json.dumps(wrong_chart), encoding='utf-8')
            proc = subprocess.run(cli, cwd=ROOT, text=True, capture_output=True, timeout=45)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, '')
            self.assertIn('原盘与出生区间复盘', proc.stderr)

    def test_saved_band_scopes_per_palace_stage_mirrors_to_stage_and_annual_case(self):
        birth, target = '1971-01-06', '2025-11-10'
        command = self.command(birth, '02:45', '03:15', '--utc-offset', '8', '--analysis-year', '2025')
        snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth, '--birth-year', '1971',
            '--shichen-index', '1', '--sex', '男', '--target-date', target, '--target-time-index', '6',
            '--source-label', 'synthetic-band-stage-mirrors',
        ], cwd=ROOT, text=True, timeout=45))
        selected = dict(ziwei_candidate_id='ziwei-band-1')
        query = dict(selected, requested_analysis_year=2025, expected_target_date=target, expected_target_time_index=6)
        valid = analyze_snapshot(snapshot, facts, **query)
        self.assertEqual(valid['stage_query_scope']['status'], 'verified')
        cases = valid['case_judgments']['modules']
        self.assertEqual(cases['ZW-RC03']['selected_branch'], 'proactive_application_fit')
        plan = query_windows(target + 'T11:00:00+08:00', target + 'T12:00:00+08:00', 'month', 'Asia/Shanghai')
        start = plan['segments'][0]['start_inclusive']
        static = analyze_snapshot(snapshot, **selected)

        edited = deepcopy(snapshot)
        chart = edited['candidates'][0]['native']['chart']
        for palace in chart['palaces']:
            del palace['daXianAge'], palace['isCurrentDaXian']
        original = deepcopy(edited)
        recovered = analyze_snapshot(edited, facts, **query)
        self.assertEqual(edited, original)
        self.assertEqual(recovered, valid)
        audit, = audit_query_windows(plan, {start: recovered}, natal_panel=static)['segments']
        self.assertEqual(audit['annual_case_status'], 'verified')

        for omission in ('missing', 'null'):
            with self.subTest(wuxingJu=omission):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][0]['native']['chart']
                if omission == 'missing':
                    del chart['wuxingJu']
                else:
                    chart['wuxingJu'] = None
                original = deepcopy(edited)
                recovered = analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, original)
                self.assertEqual(recovered, valid)
                audit, = audit_query_windows(plan, {start: recovered}, natal_panel=static)['segments']
                self.assertEqual(audit['annual_case_status'], 'verified')

        for value in (5, 6.0, '6'):
            with self.subTest(wuxingJu=value):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][0]['native']['chart']
                self.assertEqual(chart['wuxingJu'], 6)
                chart['wuxingJu'] = value
                original = deepcopy(edited)
                result = analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, original)
                self.assertEqual(result['domains'], valid['domains'])
                self.assertEqual(result['dynamic'], valid['dynamic'])
                self.assertEqual(result['stage_query_scope']['status'], 'withheld')
                self.assertIn('五行局', result['modules']['ZW-T02']['rows'][0]['errors'][0])
                self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
                audit, = audit_query_windows(plan, {start: result}, natal_panel=static)['segments']
                self.assertEqual(audit['stage_status'], 'withheld')
                self.assertEqual(audit['annual_case_status'], 'unverified')
                self.assertEqual(audit['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))

        for field in ('daXianAge', 'isCurrentDaXian'):
            with self.subTest(field=field):
                edited = deepcopy(snapshot)
                palace = edited['candidates'][0]['native']['chart']['palaces'][0]
                palace[field] = ([1, 10] if field == 'daXianAge' else not palace[field])
                original = deepcopy(edited)
                result = analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, original)
                for key in ('domains', 'birth_scenario', 'dynamic'):
                    self.assertEqual(result[key], valid[key])
                self.assertEqual(result['stage_query_scope']['status'], 'withheld')
                self.assertIn(field, result['modules']['ZW-T02']['rows'][0]['errors'][0])
                result_cases = result['case_judgments']['modules']
                for rule in ('ZW-RC01', 'ZW-RC02'):
                    self.assertEqual(result_cases[rule], cases[rule])
                self.assertEqual(result_cases['ZW-RC03']['status'], 'withheld')
                audit, = audit_query_windows(plan, {start: result}, natal_panel=static)['segments']
                self.assertEqual(audit['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
                self.assertEqual(audit['natal_relationship_status'], dict.fromkeys(('ZW-RL01', 'ZW-RC01', 'ZW-RC02'), 'verified'))
                self.assertEqual(audit['stage_status'], 'withheld')
                self.assertEqual(audit['annual_case_status'], 'unverified')

        for omission in ('missing', 'null'):
            with self.subTest(stage_table=omission):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][0]['native']['chart']
                if omission == 'missing':
                    del chart['daXians']
                else:
                    chart['daXians'] = None
                saved = deepcopy(edited)
                result = analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, saved)
                self.assertEqual(result['domains'], valid['domains'])
                self.assertEqual(result['dynamic'], valid['dynamic'])
                self.assertEqual(result['stage_query_scope']['status'], 'withheld')
                self.assertEqual(result['modules']['ZW-T02']['status'], 'withheld')
                self.assertEqual(result['stage_relationship']['stages'], [])
                self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
                audit, = audit_query_windows(plan, {start: result}, natal_panel=static)['segments']
                self.assertEqual(audit['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
                self.assertEqual(audit['natal_relationship_status'],
                                 dict.fromkeys(('ZW-RL01', 'ZW-RC01', 'ZW-RC02'), 'verified'))
                self.assertEqual(audit['annual_case_yearly_precondition']['status'], 'met')
                self.assertEqual(audit['stage_status'], 'withheld')
                self.assertEqual(audit['annual_case_status'], 'unverified')

        for damage in ('changed', 'partial', 'empty'):
            with self.subTest(stage_table=damage):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][0]['native']['chart']
                if damage == 'changed':
                    chart['daXians'][0]['startAge'] += 1
                elif damage == 'partial':
                    chart['daXians'].pop()
                else:
                    chart['daXians'] = []
                with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
                    analyze_snapshot(edited, facts, **query)

    def test_saved_band_retains_annual_case_without_empty_palace_display_annotations(self):
        birth, target = '1971-01-06', '2025-11-10'
        command = self.command(birth, '01:40', '02:20', '--utc-offset', '8', '--analysis-year', '2024')
        snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth, '--birth-year', '1971',
            '--shichen-index', '1', '--sex', '男', '--target-date', target, '--target-time-index', '0',
            '--source-label', 'synthetic-band-empty-palace-display',
        ], cwd=ROOT, text=True, timeout=45))
        query = dict(ziwei_candidate_id='ziwei-band-1', requested_analysis_year=2025,
                     expected_target_date=target, expected_target_time_index=0)
        valid = analyze_snapshot(snapshot, facts, **query)
        self.assertEqual(valid['case_judgments']['modules']['ZW-RC03']['selected_branch'],
                         'proactive_application_fit')
        self.assertEqual(valid['dynamic']['status'], 'admitted')
        spouse = next(row for row in valid['domains'] if row['domain'] == '夫妻')
        self.assertTrue(spouse['empty_palace'])
        self.assertEqual(spouse['major_topics'], [])
        self.assertEqual(spouse['borrowed_topics'], [])

        for variant in ('missing_borrowed_stars', 'missing_display', 'null_borrowed_stars',
                        'wrong_borrowed_stars', 'wrong_native_star'):
            with self.subTest(variant=variant):
                edited = deepcopy(snapshot)
                palaces = edited['candidates'][0]['native']['chart']['palaces']
                empty = next(row for row in palaces if row['name'] == '夫妻')
                self.assertTrue(empty['isEmpty'] and empty['borrowedStars'])
                if variant == 'missing_borrowed_stars':
                    del empty['borrowedStars']
                elif variant == 'missing_display':
                    for palace in palaces:
                        for field in ('oppositeBranch', 'isEmpty', 'borrowedFromBranch', 'borrowedFromName',
                                      'borrowedStars'):
                            palace.pop(field, None)
                elif variant == 'null_borrowed_stars':
                    empty['borrowedStars'] = None
                elif variant == 'wrong_borrowed_stars':
                    empty['borrowedStars'] = ['紫微']
                else:
                    star = next(star for palace in palaces for star in palace['stars'] if star['name'] == '紫微')
                    star['name'] = '天机'
                original = deepcopy(edited)
                if variant.startswith('missing_'):
                    self.assertEqual(analyze_snapshot(edited, facts, **query), valid)
                else:
                    with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
                        analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, original)

    def test_saved_band_retains_stage_and_relationship_without_legacy_brightness_display(self):
        fixtures = (('1987-01-02', '22:10', '22:40', '2029-01-03', 11, '天相'),
                    ('1987-06-18', '06:50', '06:58', '2027-02-06', 3, '巨门'))
        for birth, lower, upper, target, index, name in fixtures:
            with self.subTest(birth=birth):
                command = self.command(birth, lower, upper, '--utc-offset', '8', '--analysis-year', target[:4])
                snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
                facts = json.loads(subprocess.check_output([
                    'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth, '--birth-year', birth[:4],
                    '--shichen-index', str(index), '--sex', '男', '--target-date', target, '--target-time-index', '0',
                    '--source-label', 'synthetic-band-legacy-brightness',
                ], cwd=ROOT, text=True, timeout=45))
                query = dict(ziwei_candidate_id=f'ziwei-band-{index}',
                             expected_target_date=target, expected_target_time_index=0)
                valid = analyze_snapshot(snapshot, facts, **query)
                self.assertEqual(valid['dynamic']['status'], 'admitted')
                if name == '天相':
                    current, = [row for row in valid['stage_relationship']['stages']
                                if row['legacy_stage']['current']]
                    self.assertEqual(current['modules']['ZW-ST05']['selected_branch'], 'tianxiang_yang_restriction')
                else:
                    cases = valid['case_judgments']['modules']
                    self.assertEqual([cases[rule]['status'] for rule in ('ZW-RC01', 'ZW-RC02')],
                                     ['conditional', 'conditional'])

                for variant in ('missing', 'all_missing', 'null', 'legacy_conflict', 'raw_conflict'):
                    with self.subTest(variant=variant):
                        edited = deepcopy(snapshot)
                        chart = edited['candidates'][0]['native']['chart']
                        stars = [star for palace in chart['palaces'] for star in palace['stars']
                                 if star['type'] == 'major']
                        star, = [star for star in stars if star['name'] == name]
                        if variant == 'missing':
                            del star['brightness']
                        elif variant == 'all_missing':
                            for item in stars:
                                del item['brightness']
                        elif variant == 'null':
                            star['brightness'] = None
                        elif variant == 'legacy_conflict':
                            star['brightness'] = 'bright' if star['brightness'] != 'bright' else 'dim'
                        else:
                            star['brightnessRaw'] = '陷' if star['brightnessRaw'] != '陷' else '庙'
                        original = deepcopy(edited)
                        if variant.endswith('_conflict'):
                            with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
                                analyze_snapshot(edited, facts, **query)
                        else:
                            self.assertEqual(analyze_snapshot(edited, facts, **query), valid)
                        self.assertEqual(edited, original)

    def test_reordered_saved_band_retains_its_own_palace_and_star_evidence_paths(self):
        birth, target = '1980-10-10', '2026-11-13'
        snapshot = json.loads(subprocess.check_output(
            self.command(birth, '18:58', '19:03', '--utc-offset', '8', '--analysis-year', '2026'),
            cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth, '--birth-year', '1980',
            '--shichen-index', '10', '--sex', '男', '--target-date', target, '--target-time-index', '0',
            '--source-label', 'synthetic-band-order',
        ], cwd=ROOT, text=True, timeout=45))
        selected = dict(ziwei_candidate_id='ziwei-band-10')
        query = dict(selected, expected_target_date=target, expected_target_time_index=0)
        plan = query_windows(target + 'T00:00:00+08:00', target + 'T01:00:00+08:00', 'month')
        start = plan['segments'][0]['start_inclusive']
        original_static = analyze_snapshot(snapshot, **selected)
        original_point = analyze_snapshot(snapshot, facts, **query)

        def verify(point, natal):
            row, = audit_query_windows(plan, {start: point}, natal_panel=natal)['segments']
            self.assertEqual(row['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
            self.assertEqual(row['natal_relationship_status'],
                             dict.fromkeys(('ZW-RL01', 'ZW-RC01', 'ZW-RC02'), 'verified'))
            self.assertEqual(row['natal_domain_topic_status']['ZW-D02'], 'verified')
            self.assertEqual(row['transformation_topic_status']['yearly']['忌'], 'verified')
            self.assertEqual(row['stage_status'], 'verified')

        def chart(archive):
            return archive['candidates'][1]['native']['chart']

        original_spouse = next(row for row in original_point['domains'] if row['domain'] == '夫妻')
        original_lianzhen = next(fact for fact in original_spouse['facts'] if fact['name'] == '廉贞')
        for reverse_palaces, reverse_stars, omit_brightness in (
                (True, False, False), (False, True, False), (True, True, False), (True, True, True)):
            with self.subTest(palaces=reverse_palaces, stars=reverse_stars, missing=omit_brightness):
                edited = deepcopy(snapshot)
                palaces = chart(edited)['palaces']
                if reverse_palaces:
                    palaces.reverse()
                if reverse_stars:
                    for palace in palaces:
                        palace['stars'].reverse()
                spouse_index, spouse = next((i, row) for i, row in enumerate(palaces) if row['name'] == '夫妻')
                star_index, star = next((i, row) for i, row in enumerate(spouse['stars']) if row['name'] == '廉贞')
                if omit_brightness:
                    del star['brightnessRaw']
                raw_path = f'chart.palaces[{spouse_index}].stars[{star_index}]'
                original = deepcopy(edited)
                natal = analyze_snapshot(edited, **selected)
                point = analyze_snapshot(edited, facts, **query)
                self.assertEqual(edited, original)
                relationship = point['stage_relationship']['relationship']
                positions = relationship['context']['verified_malefic_positions']
                four = {row['branch'] for row in relationship['context']['surrounding']}
                self.assertEqual(set(positions), {'擎羊', '陀罗', '火星', '铃星', '地空', '地劫'})
                self.assertTrue(all(type(branch) is int and branch not in four for branch in positions.values()))
                spouse_domain = next(row for row in point['domains'] if row['domain'] == '夫妻')
                self.assertEqual({fact['name'] for fact in spouse_domain['facts'] if fact['type'] == 'major'},
                                 {'廉贞', '天府'})
                lianzhen = next(fact for fact in spouse_domain['facts'] if fact['name'] == '廉贞')
                self.assertEqual(lianzhen['path'], raw_path)
                self.assertNotEqual(lianzhen['path'], original_lianzhen['path'])
                transform = next(row for row in point['transformations']
                                 if row['layer'] == 'yearly' and row['kind'] == '忌')
                self.assertEqual(transform['fact'], lianzhen)
                if omit_brightness:
                    self.assertIn(raw_path + '.brightnessRaw', point['dynamic']['unverified_static_fields'])
                verify(point, original_static)
                verify(original_point, natal)

        for damage in ('duplicate star', 'duplicate palace', 'changed star', 'changed brightness'):
            with self.subTest(damage=damage):
                edited = deepcopy(snapshot)
                palaces = chart(edited)['palaces']
                palaces.reverse()
                spouse = next(row for row in palaces if row['name'] == '夫妻')
                star = next(row for row in spouse['stars'] if row['name'] == '廉贞')
                if damage == 'duplicate star':
                    spouse['stars'].append(deepcopy(star))
                elif damage == 'duplicate palace':
                    palaces[0] = deepcopy(palaces[1])
                elif damage == 'changed star':
                    star['name'] = '天机'
                else:
                    star['brightnessRaw'] = '陷'
                with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
                    analyze_snapshot(edited, facts, **query)

    def test_saved_band_retains_verified_follow_up_with_missing_natal_annotations(self):
        command = self.command('1987-06-02', '16:58', '17:02', '--utc-offset', '8')
        snapshot = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        selected = snapshot['candidates'][1]
        target = '2032-11-09'
        command = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1987-06-02', '--birth-year', '1987',
                   '--shichen-index', '9', '--sex', '男', '--target-date', target, '--target-time-index', '0',
                   '--source-label', 'synthetic-legacy-band']
        facts = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        query = dict(ziwei_candidate_id=selected['id'], expected_target_date=target,
                     expected_target_time_index=0, requested_analysis_year=2032)
        valid = analyze_snapshot(snapshot, facts, **query)
        direct_reference = selected['life_reading']
        self.assertEqual(direct_reference['natal_stage_basis'], valid['natal_stage_basis'])
        self.assertEqual(valid['stage_query_scope']['status'], 'verified')
        self.assertEqual(valid['stage_query_scope']['panel_analysis_year'], 2032)
        current, = (row['legacy_stage'] for row in valid['stage_relationship']['stages']
                    if row['legacy_stage']['current'])
        self.assertEqual(current['window']['start_inclusive'], '2031-01-01')
        self.assertEqual(valid['case_judgments']['modules']['ZW-RC01']['status'], 'conditional')
        self.assertTrue(any((row['star'], row['fact']['domain'], row['kind']) == ('巨门', '夫妻', '禄')
                            for row in valid['dynamic']['layers']['monthly']['transformations']))
        plan = query_windows(target, '2032-11-10', 'month', 'Asia/Shanghai')
        start = plan['segments'][0]['start_inclusive']

        fields = ('currentAge', 'currentDaXianIndex')
        for omissions in ((fields[0],), (fields[1],), fields):
            with self.subTest(omissions=omissions):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][1]['native']['chart']
                for field in omissions:
                    del chart[field]
                original = deepcopy(edited)
                expected = deepcopy(valid)
                expected['stage_query_scope']['replayed_current_fields'] = list(omissions)
                self.assertEqual(analyze_snapshot(edited, facts, **query), expected)
                self.assertEqual(edited, original)

        legacy = deepcopy(snapshot)
        legacy_chart = legacy['candidates'][1]['native']['chart']
        del legacy_chart['currentAge'], legacy_chart['currentDaXianIndex']
        without_year = dict(query)
        del without_year['requested_analysis_year']
        no_stage = analyze_snapshot(legacy, facts, **without_year)
        self.assertEqual(no_stage['modules']['ZW-T02']['status'], 'withheld')
        self.assertEqual(no_stage['case_judgments']['modules']['ZW-RC01']['status'], 'conditional')
        self.assertEqual(no_stage['dynamic']['layers'], valid['dynamic']['layers'])
        legacy_chart['currentAge'] = None
        with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
            analyze_snapshot(legacy, facts, **query)

        for key in ('shenGongBranch', 'yearStem', 'lunarInfo'):
            with self.subTest(key=key):
                edited = deepcopy(snapshot)
                chart = edited['candidates'][1]['native']['chart']
                if key == 'yearStem':
                    del chart['lunarInfo'][key]
                    gap = 'chart.lunarInfo.yearStem'
                else:
                    del chart[key]
                    gap = 'chart.' + key
                original = deepcopy(edited)
                panel = analyze_snapshot(edited, facts, **query)
                self.assertEqual(panel['birth_scenario'], valid['birth_scenario'])
                self.assertEqual(panel['dynamic']['status'], 'admitted')
                self.assertEqual(panel['dynamic']['unverified_static_fields'], [gap])
                self.assertEqual(panel['dynamic']['layers'], valid['dynamic']['layers'])
                self.assertEqual(panel['stage_query_scope'], valid['stage_query_scope'])
                self.assertEqual(panel['domains'], valid['domains'])
                current_after, = (row['legacy_stage'] for row in panel['stage_relationship']['stages']
                                  if row['legacy_stage']['current'])
                self.assertEqual(current_after, current)
                case = panel['case_judgments']['modules']['ZW-RC01']
                if key == 'shenGongBranch':
                    self.assertEqual(panel['modules']['ZW-S01']['status'], 'withheld')
                    self.assertEqual(case['status'], 'conditional')
                else:
                    self.assertEqual(case['status'], 'withheld')
                    self.assertEqual(set(panel['natal_transform_errors']), set('禄权科忌'))
                    self.assertFalse(any(row['layer'] == 'natal' for row in panel['transformations']))
                self.assertEqual(edited, original)

        chart = selected['native']['chart']
        palace_index, spouse = next((index, p) for index, p in enumerate(chart['palaces']) if p['name'] == '夫妻')
        star_index = next(index for index, star in enumerate(spouse['stars']) if star['name'] == '天同')
        star_path = f'chart.palaces[{palace_index}].stars[{star_index}]'
        for field, fact_field, conflicting_value in (
                ('brightnessRaw', 'brightness_raw', '庙' if spouse['stars'][star_index]['brightnessRaw'] != '庙' else '陷'),
                ('siHua', 'natal_transform', '科')):
            saved_omissions = ('missing', None, '') if field == 'siHua' else ('missing', None)
            for omission in saved_omissions:
                with self.subTest(field=field, omission=omission):
                    edited = deepcopy(snapshot)
                    saved = edited['candidates'][1]['native']['chart']['palaces'][palace_index]['stars'][star_index]
                    if omission == 'missing':
                        del saved[field]
                    else:
                        saved[field] = omission
                    original = deepcopy(edited)
                    panel = analyze_snapshot(edited, facts, **query)
                    self.assertEqual(edited, original)
                    self.assertEqual(panel['stage_query_scope'], valid['stage_query_scope'])
                    self.assertEqual(panel['dynamic']['status'], 'admitted')
                    self.assertEqual(panel['dynamic']['unverified_static_fields'], [star_path + '.' + field])
                    self.assertTrue(any((row['star'], row['fact']['domain'], row['kind']) == ('巨门', '夫妻', '禄')
                                        for row in panel['dynamic']['layers']['monthly']['transformations']))
                    spouse_facts = next(row['facts'] for row in panel['domains'] if row['domain'] == '夫妻')
                    self.assertIsNone(next(fact[fact_field] for fact in spouse_facts if fact['path'] == star_path))
                    cases = panel['case_judgments']['modules']
                    self.assertEqual(cases['ZW-RC01']['status'], 'withheld')
                    if field == 'siHua':
                        self.assertEqual(cases['ZW-RC02']['status'], 'conditional')
                    if omission == 'missing':
                        checked, = audit_query_windows(plan, {start: panel}, natal_panel=direct_reference)['segments']
                        self.assertEqual(checked['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
                        self.assertEqual(checked['stage_status'], 'verified')
                        self.assertEqual(checked['natal_domain_topic_status']['ZW-D04'], 'verified')
                        self.assertEqual(checked['natal_domain_topic_status']['ZW-D07'], 'verified')
                        self.assertEqual(checked['natal_relationship_status']['ZW-RC01'], 'withheld')
                        if field == 'siHua':
                            self.assertEqual(checked['natal_relationship_status']['ZW-RC02'], 'verified')
                            legacy_reference = deepcopy(direct_reference)
                            del legacy_reference['natal_stage_basis']
                            stale, = audit_query_windows(plan, {start: panel}, natal_panel=legacy_reference)['segments']
                            self.assertEqual(stale['stage_status'], 'birth_mismatch')
                            reread = analyze_snapshot(snapshot, ziwei_candidate_id=selected['id'])
                            recovered, = audit_query_windows(plan, {start: panel}, natal_panel=reread)['segments']
                            self.assertEqual(recovered, checked)
                    saved[field] = conflicting_value
                    with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
                        analyze_snapshot(edited, facts, **query)

        conflicting = deepcopy(snapshot)
        chart = conflicting['candidates'][1]['native']['chart']
        del chart['shenGongBranch']
        chart['lunarInfo']['isLeapMonth'] = int(chart['lunarInfo']['isLeapMonth'])
        with self.assertRaisesRegex(ValueError, '原盘与出生区间复盘'):
            analyze_snapshot(conflicting, facts, **query)

    def test_narrowing_reuses_the_same_selected_span_across_native_row_positions(self):
        born, target = '1987-06-02', '2032-11-09'
        archives = [json.loads(subprocess.check_output(
            self.command(born, start, '17:02', '--utc-offset', '8'),
            cwd=ROOT, text=True, timeout=45)) for start in ('16:58', '17:00', '17:01')]
        facts = json.loads(subprocess.check_output([
            'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', born, '--birth-year', '1987',
            '--shichen-index', '9', '--sex', '男', '--target-date', target, '--target-time-index', '0',
            '--source-label', 'narrowed-civil-span',
        ], cwd=ROOT, text=True, timeout=45))
        plan = query_windows(target, '2032-11-10', 'month', 'Asia/Shanghai')
        segment, = plan['segments']
        start = segment['start_inclusive']
        selected = dict(ziwei_candidate_id='ziwei-band-9')
        static = [analyze_snapshot(archive, **selected) for archive in archives]
        points = [analyze_snapshot(archive, facts, **selected, requested_analysis_year=2032,
                                   expected_target_date=target, expected_target_time_index=0) for archive in archives]

        def audit(natal, point):
            row, = audit_query_windows(plan, {start: point}, natal_panel=natal)['segments']
            return row

        original, narrowed, changed = (owner['birth_scenario'] for owner in static)
        self.assertEqual(original['chart_path'], 'candidates[1].native.chart')
        self.assertEqual(narrowed['chart_path'], 'candidates[0].native.chart')
        self.assertEqual(original['civil_spans'], narrowed['civil_spans'])
        self.assertNotEqual(narrowed['civil_spans'], changed['civil_spans'])
        reference = audit(static[0], points[0])
        self.assertEqual(reference['dynamic_layers'], dict(yearly='admitted', monthly='admitted'))
        self.assertEqual(reference['stage_status'], 'verified')
        self.assertEqual(reference['natal_relationship_status']['ZW-RC02'], 'verified')
        self.assertEqual(points[1]['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
        self.assertEqual(audit(static[0], points[1]), reference)
        self.assertEqual(audit(static[1], points[0]), reference)
        self.assertEqual(audit(static[2], points[2]), reference)
        self.assertEqual(audit(static[0], points[2])['stage_status'], 'birth_mismatch')

        invalid_path = deepcopy(points[1])
        invalid_path['birth_scenario']['chart_path'] = 'candidates[12].native.chart'
        self.assertEqual(audit(static[0], invalid_path)['stage_status'], 'birth_mismatch')
        legacy = deepcopy(static[0])
        del legacy['natal_stage_basis']
        self.assertEqual(audit(legacy, points[1])['stage_status'], 'birth_mismatch')


class ZiweiCivilBandPartitionTests(unittest.TestCase):
    def test_fold_retains_both_actual_spans_for_one_branch(self):
        spans = _reachable_shichen(date(2024, 11, 3), 45, 135, 'America/New_York', None)
        self.assertEqual(list(spans), [0, 1])
        early, late = spans[1]
        self.assertEqual(early['start_inclusive'], '2024-11-03T01:00:00-04:00')
        self.assertEqual(late['start_inclusive'], '2024-11-03T01:00:00-05:00')
        self.assertEqual(early['end_exclusive_utc'], late['start_utc'])
        self.assertEqual((early['fold_at_start'], late['fold_at_start'], late['fold_at_last_included']),
                         (0, 1, 0))

    def test_same_civil_date_early_and_late_zi_share_one_discrete_branch(self):
        spans = _reachable_shichen(date(1988, 10, 18), 30, 23 * 60 + 30, None, 8)
        self.assertEqual([(r['start_inclusive'][11:16], r['end_exclusive'][11:16]) for r in spans[0]],
                         [('00:30', '01:00'), ('23:00', '23:30')])

    def test_gap_at_start_keeps_the_rest_of_the_confirmed_band(self):
        spans = _reachable_shichen(date(2018, 11, 4), 0, 210, 'America/Sao_Paulo', None)
        self.assertEqual(list(spans), [1, 2])
        self.assertEqual(spans[1][0]['start_inclusive'], '2018-11-04T01:00:00-02:00')
        self.assertEqual(spans[2][0]['end_exclusive'], '2018-11-04T03:30:00-02:00')


if __name__ == '__main__':
    unittest.main()
