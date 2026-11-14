"""Exact approved case predicates, using independent synthetic native A/B/C inputs."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ziwei_case_judgments as cases
import ziwei_life_reading as life


@unittest.skipUnless((ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
class ZiweiCaseJudgmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dynamics = {}
        cls.panels = {}
        # Synthetic search examples; these dates are not personal records.
        for key, solar, hour, target in (
                ('A', '1987-03-06', 6, '2026-11-10'),
                ('B', '1987-03-01', 8, '2026-11-10'),
                ('C', '1971-01-06', 1, '2025-11-10')):
            cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', solar,
                   '--birth-year', solar[:4], '--shichen-index', str(hour), '--sex', '男',
                   '--target-date', target, '--target-time-index', '6',
                   '--source-label', 'synthetic-approved-cases-' + key]
            dynamic = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                                text=True, check=True).stdout)
            cls.dynamics[key] = dynamic
            cls.panels[key] = life.analyze(dynamic['native_wrapper_snapshot']['chart'],
                                          int(solar[:4]), int(target[:4]), dynamic)

    def modules(self, key):
        return self.panels[key]['case_judgments']['modules']

    def test_native_a_and_b_distinguish_spouse_cases_and_actual_copresence(self):
        a, b = self.modules('A'), self.modules('B')
        self.assertEqual(a['ZW-RC01']['status'], 'conditional')
        self.assertTrue(a['ZW-RC01']['fact_match'])
        self.assertEqual(b['ZW-RC01']['status'], 'not_triggered')
        for modules, branch in ((a, 'tiantong_copresent'), (b, 'tiantong_absent')):
            row = modules['ZW-RC02']
            self.assertEqual(row['status'], 'conditional')
            self.assertEqual(row['selected_branch'], branch)
            self.assertEqual([item['key'] for item in row['direction_branches']], [branch])
            self.assertEqual(row['reality_status'], 'not_observed_or_inferred')
            self.assertEqual(row['overall_direction'], 'withheld')
            self.assertTrue(row['counterexamples'])
        stars = a['ZW-RC01']['context']['domain']['facts']
        self.assertEqual([(f['name'], f['brightness_raw'], f['natal_transform'])
                          for f in stars if f['type'] == 'major'],
                         [('天同', '不', '权'), ('巨门', '不', '忌')])
        self.assertEqual(b['ZW-RC02']['context']['domain']['major_topics'][0]['star'], '巨门')
        self.assertTrue(all(f['name'] != '天同' for f in b['ZW-RC02']['context']['domain']['facts']))

    def test_native_c_matches_only_current_career_stage_and_both_yearly_major_attachments(self):
        row = self.modules('C')['ZW-RC03']
        self.assertEqual(row['status'], 'conditional')
        self.assertEqual(row['selected_branch'], 'proactive_application_fit')
        context = row['context']
        self.assertEqual(context['query_point']['solar_date'], '2025-11-10')
        self.assertFalse(context['full_interval_coverage'])
        self.assertEqual(context['current_stage']['domain'], '官禄')
        self.assertEqual(context['current_stage']['native']['startAge'], 46)
        self.assertEqual(context['current_stage']['native']['endAge'], 55)
        self.assertEqual(context['current_stage']['window'],
                         {'start_inclusive': '2016-01-01', 'end_exclusive': '2026-01-01'})
        evidence = [check['evidence'] for check in row['checks'][1:]]
        self.assertEqual([(r['kind'], r['star'], r['fact']['domain']) for r in evidence],
                         [('禄', '天机', '官禄'), ('权', '天梁', '官禄')])
        self.assertEqual(len(context['natal_ming_surrounding']), 4)
        self.assertEqual(len(context['career_stage_surrounding']), 4)
        self.assertEqual({f['domain'] for f in context['career_stage_surrounding']},
                         {'官禄', '财帛', '夫妻', '命宫'})
        self.assertEqual(len(row['author_adaptations']), 3)
        # Natal/annual 忌 and unassigned minor stars remain facts, not cancellations.
        self.assertTrue(any(t['kind'] == '忌' and t['fact']['domain'] in ('命', '命宫')
                            for t in context['transformations']))
        self.assertTrue(any(f['type'] != 'major' for domain in context['career_stage_surrounding']
                            for f in domain['facts']))
        self.assertEqual(row['overall_direction'], 'withheld')

    def test_spouse_cases_require_original_brightness_only_for_supporting_stars(self):
        for key, domain, star_name, expected in (
                ('A', '夫妻', '巨门', ('withheld', 'withheld')),
                ('A', '夫妻', '天同', ('withheld', 'withheld')),
                ('A', '福德', None, ('conditional', 'conditional')),
                ('B', '夫妻', '巨门', ('not_triggered', 'withheld'))):
            with self.subTest(chart=key, domain=domain, star=star_name):
                chart = deepcopy(self.dynamics[key]['native_wrapper_snapshot']['chart'])
                palace = next(row for row in chart['palaces'] if row['name'] == domain)
                star = next(row for row in palace['stars']
                            if row['type'] == 'major' and (star_name is None or row['name'] == star_name))
                star.pop('brightnessRaw')
                panel = life.analyze(chart, 1987, 2026)
                modules = panel['case_judgments']['modules']
                results = [modules[rule] for rule in ('ZW-RC01', 'ZW-RC02')]
                self.assertEqual(tuple(row['status'] for row in results), expected)
                for row in results:
                    if row['status'] == 'withheld':
                        self.assertIsNone(row['fact_match'])
                        self.assertIsNone(row['selected_branch'])
                        self.assertEqual(row['direction_branches'], [])
                        self.assertIn(star_name, row['reasons'][0])
                        self.assertIn('原始亮度', row['reasons'][0])
                self.assertEqual(panel['stage_relationship']['relationship']['status'],
                                 self.panels[key]['stage_relationship']['relationship']['status'])

    def test_future_career_or_one_yearly_attachment_does_not_trigger_rc03(self):
        for key in ('A', 'B'):
            row = self.modules(key)['ZW-RC03']
            self.assertEqual(row['status'], 'not_triggered')
            stages = self.panels[key]['modules']['ZW-T02']['rows'][0]['rows']
            self.assertTrue(any(stage['domain'] == '官禄' and not stage['current'] for stage in stages))
            self.assertEqual(row['context']['current_stage']['domain'], '子女')
        b_checks = self.modules('B')['ZW-RC03']['checks']
        self.assertTrue(b_checks[2]['matched'])
        self.assertFalse(b_checks[1]['matched'])

    def test_natal_cases_work_without_dynamic_and_year_month_cannot_supply_natal(self):
        dynamic = self.dynamics['A']
        panel = life.analyze(dynamic['native_wrapper_snapshot']['chart'], 1987, 2026)
        modules = panel['case_judgments']['modules']
        self.assertEqual(modules['ZW-RC01']['status'], 'conditional')
        self.assertEqual(modules['ZW-RC02']['status'], 'conditional')
        self.assertEqual(modules['ZW-RC03']['status'], 'withheld')
        panel = deepcopy(self.panels['A'])
        panel['transformations'] = [t for t in panel['transformations'] if t['layer'] != 'natal']
        modules = cases.evaluate(panel)['modules']
        self.assertEqual(modules['ZW-RC01']['status'], 'withheld')
        self.assertEqual(modules['ZW-RC02']['status'], 'withheld')

    def test_natal_cases_preserve_only_independently_verified_prerequisites(self):
        for key, original_kind, replacement, expected in (
                ('A', '科', None, ('conditional', 'conditional')),
                ('A', '权', None, ('withheld', 'conditional')),
                ('A', '科', '权', ('withheld', 'conditional')),
                ('A', '忌', None, ('withheld', 'withheld')),
                ('B', '科', None, ('not_triggered', 'conditional')),
                ('B', '忌', None, ('not_triggered', 'withheld'))):
            with self.subTest(chart=key, original_kind=original_kind, replacement=replacement):
                chart = deepcopy(self.dynamics[key]['native_wrapper_snapshot']['chart'])
                star = next(star for palace in chart['palaces'] for star in palace['stars']
                            if star.get('siHua') == original_kind)
                star['siHua'] = replacement
                panel = life.analyze(chart, 1987, 2026)
                cases_result = panel['case_judgments']
                self.assertIn(cases_result['natal_transform_error'], panel['input_errors'])
                rc01, rc02 = (cases_result['modules'][rule] for rule in ('ZW-RC01', 'ZW-RC02'))
                self.assertEqual((rc01['status'], rc02['status']), expected)
                for row in (rc01, rc02):
                    if row['status'] == 'withheld':
                        self.assertIsNone(row['fact_match'])
                        self.assertEqual(row['direction_branches'], [])
                        self.assertIn('权' if original_kind == '权' or replacement == '权' else '忌',
                                      row['reasons'][0])
                    elif row['status'] == 'not_triggered':
                        self.assertFalse(row['fact_match'])
                if rc02['status'] == 'conditional':
                    self.assertEqual(rc02['selected_branch'], 'tiantong_copresent' if key == 'A' else 'tiantong_absent')

    def test_annual_case_still_requires_complete_natal_context(self):
        dynamic = deepcopy(self.dynamics['C'])
        chart = dynamic['native_wrapper_snapshot']['chart']
        star = next(star for palace in chart['palaces'] for star in palace['stars']
                    if star.get('siHua') == '科')
        star.pop('siHua')
        panel = life.analyze(chart, 1971, 2025, dynamic)
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')
        cases_result = panel['case_judgments']
        self.assertEqual(cases_result['modules']['ZW-RC03']['status'], 'withheld')
        self.assertIn(cases_result['natal_transform_error'], cases_result['modules']['ZW-RC03']['reasons'])

    def test_direct_partial_panel_rejects_a_stale_detached_natal_attachment(self):
        chart = deepcopy(self.dynamics['A']['native_wrapper_snapshot']['chart'])
        star = next(star for palace in chart['palaces'] for star in palace['stars']
                    if star.get('siHua') == '权')
        star.pop('siHua')
        panel = life.analyze(chart, 1987, 2026)
        self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
        detached = deepcopy(next(row for row in self.panels['A']['transformations']
                                 if row['layer'] == 'natal' and row['kind'] == '权'))
        detached['fact'] = deepcopy(next(fact for palace in panel['domains'] for fact in palace['facts']
                                         if fact['name'] == '天同'))
        panel['transformations'].append(detached)
        summary = panel['case_judgments']['natal_transform_error']
        result = cases.evaluate(panel, natal_transform_error=summary)
        self.assertEqual(result['modules']['ZW-RC01']['status'], 'withheld')
        self.assertIn('来源路径不一致', result['modules']['ZW-RC01']['reasons'][0])

    def test_missing_or_invalid_yearly_cannot_be_replaced_by_monthly(self):
        panel = deepcopy(self.panels['C'])
        panel['transformations'] = [t for t in panel['transformations'] if t['layer'] != 'yearly']
        self.assertEqual(cases.evaluate(panel)['modules']['ZW-RC03']['status'], 'withheld')
        bad = deepcopy(self.dynamics['C'])
        bad['admitted_dynamic_facts']['layers']['yearly']['transformations'][0]['natal_star_locations'] = []
        panel = life.analyze(bad['native_wrapper_snapshot']['chart'], 1971, 2025, bad)
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'admitted')
        self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')

    def test_derived_views_cannot_override_the_actual_year_or_month_source(self):
        dynamics = {}
        for target in ('2025-01-28', '2025-01-29', '2025-02-27', '2025-02-28'):
            cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1971-01-06', '--birth-year', '1971',
                   '--shichen-index', '1', '--sex', '男', '--target-date', target, '--target-time-index', '0',
                   '--source-label', 'synthetic-source-crossover']
            dynamics[target] = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))

        def panel(data, target):
            return life.analyze(self.dynamics['C']['native_wrapper_snapshot']['chart'], 1971, 2025, data,
                                expected_target_date=target, expected_target_time_index=0)

        for date, stale_date, expected, expected_rc03 in (
                ('2025-01-28', '2025-01-29', ('withheld', 'withheld'), 'withheld'),
                ('2025-02-28', '2025-02-27', ('admitted', 'withheld'), 'conditional')):
            with self.subTest(date=date):
                baseline = panel(dynamics[date], date)
                self.assertEqual(baseline['dynamic']['status'], 'admitted')
                baseline_rc03 = baseline['case_judgments']['modules']['ZW-RC03']
                self.assertEqual(baseline_rc03['status'], 'not_triggered' if date == '2025-01-28' else 'conditional')

                mixed = deepcopy(dynamics[date])
                stale = dynamics[stale_date]
                research = mixed['research_dynamic_iztro']
                cached = stale['research_dynamic_iztro']
                research['calendar_observation']['target_lunar'] = deepcopy(cached['calendar_observation']['target_lunar'])
                for layer in ('yearly', 'monthly'):
                    research['selected_fact_views'][layer] = deepcopy(cached['selected_fact_views'][layer])
                    mixed['admitted_dynamic_facts']['layers'][layer] = deepcopy(stale['admitted_dynamic_facts']['layers'][layer])
                result = panel(mixed, date)
                layers = result['dynamic']['layers']
                self.assertEqual(tuple(layers[layer]['status'] for layer in ('yearly', 'monthly')), expected)
                for row in layers.values():
                    if row['status'] == 'withheld':
                        self.assertIn('来源原生层缺失或与准入事实不一致', row['errors'][0])
                self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], expected_rc03)
                self.assertEqual(result['domains'], baseline['domains'])
                self.assertEqual(result['stage_relationship'], baseline['stage_relationship'])

        target = '2025-02-28'
        missing = deepcopy(dynamics[target])
        del missing['research_dynamic_iztro']['raw_horoscope']['monthly']
        result = panel(missing, target)
        self.assertEqual(result['dynamic']['layers']['monthly']['status'], 'withheld')
        self.assertEqual(result['dynamic']['layers']['yearly']['status'], 'admitted')
        self.assertEqual(result['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')

    def test_rejected_dynamic_status_cannot_leave_a_usable_yearly_residue(self):
        panel = deepcopy(self.panels['C'])
        panel['dynamic']['status'] = 'withheld'
        self.assertEqual(cases.evaluate(panel)['modules']['ZW-RC03']['status'], 'withheld')
        panel['dynamic']['status'] = 'partial'
        panel['dynamic']['layers']['monthly']['status'] = 'withheld'
        self.assertEqual(cases.evaluate(panel)['modules']['ZW-RC03']['status'], 'conditional')

    def test_wrong_canonical_profile_or_version_is_withheld(self):
        for field in ('profile', 'version'):
            panel = deepcopy(self.panels['A'])
            panel[field] = 'other-profile'
            result = cases.evaluate(panel)
            self.assertEqual(result['status'], 'withheld')
            self.assertTrue(result['input_errors'])

    def test_query_must_match_the_existing_t02_year_and_window(self):
        panel = deepcopy(self.panels['C'])
        panel['modules']['ZW-T02']['rows'][0]['analysis_year'] = 2024
        row = cases.evaluate(panel)['modules']['ZW-RC03']
        self.assertEqual(row['status'], 'withheld')
        self.assertIn('不一致', row['reasons'][0])

    def test_t02_outer_withholding_and_wrong_dynamic_profile_block_residual_rows(self):
        panel = deepcopy(self.panels['C'])
        panel['modules']['ZW-T02']['status'] = 'withheld'
        self.assertEqual(cases.evaluate(panel)['modules']['ZW-RC03']['status'], 'withheld')
        panel = deepcopy(self.panels['C'])
        panel['dynamic']['profile'] = 'other-profile'
        self.assertEqual(cases.evaluate(panel)['modules']['ZW-RC03']['status'], 'withheld')

    def test_uncertainty_missing_hour_and_original_input_errors_withhold_cases(self):
        chart = deepcopy(self.dynamics['A']['native_wrapper_snapshot']['chart'])
        uncertain = life.analyze(chart, 1987, 2026, temporal_uncertainty=True)
        self.assertTrue(all(row['status'] == 'withheld'
                            for row in uncertain['case_judgments']['modules'].values()))
        self.assertEqual(len(uncertain['case_judgments']['facts']['domains']), 12)
        del chart['birthInfo']['hour']
        missing = life.analyze(chart, 1987, 2026)
        self.assertEqual(missing['status'], 'conditional')
        self.assertEqual(missing['input_errors'], [])
        self.assertEqual(missing['case_judgments']['status'], 'withheld')
        self.assertIn('时辰', missing['case_judgments']['input_errors'][0])
        chart = deepcopy(self.dynamics['A']['native_wrapper_snapshot']['chart'])
        next(s for p in chart['palaces'] for s in p['stars'] if s.get('siHua') == '忌')['siHua'] = '权'
        broken = life.analyze(chart, 1987, 2026)
        self.assertTrue(broken['input_errors'])
        self.assertTrue(all(row['status'] == 'withheld'
                            for row in broken['case_judgments']['modules'].values()))

    def test_new_source_failure_is_explicit_and_preserves_old_panel_values(self):
        dynamic = self.dynamics['A']
        before = deepcopy(dynamic)
        load_profile = cases.knowledge.load_profile

        def fail_case_profile(system, profile, expected_ids, root=None):
            if profile == cases.PROFILE:
                raise ValueError('case source byte mismatch')
            return load_profile(system, profile, expected_ids, root=root)

        with patch.object(cases.knowledge, 'load_profile', side_effect=fail_case_profile):
            failed = life.analyze(dynamic['native_wrapper_snapshot']['chart'], 1987, 2026, dynamic)
        self.assertEqual(failed.pop('case_judgments')['source_errors'], ['case source byte mismatch'])
        expected = deepcopy(self.panels['A'])
        expected.pop('case_judgments')
        self.assertEqual(failed, expected)
        self.assertEqual(len(failed['modules']), 15)
        self.assertEqual(dynamic, before)

    def test_real_new_source_byte_failure_preserves_global_source_gate_contract(self):
        dynamic = self.dynamics['A']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('knowledge', 'references', 'docs'):
                shutil.copytree(ROOT / name, root / name)
            shutil.copyfile(ROOT / 'LICENSE', root / 'LICENSE')
            constants = root / 'scripts/pai_pan_ziwei/vendor/constants.ts'
            constants.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'scripts/pai_pan_ziwei/vendor/constants.ts', constants)
            source = root / 'references/approved/ziwei-judgment-cases-v1.md'
            source.write_text(source.read_text(encoding='utf-8') + '\nchanged bytes\n', encoding='utf-8')
            failed = life.analyze(dynamic['native_wrapper_snapshot']['chart'], 1987, 2026, dynamic, root=root)
            new = failed['case_judgments']
            self.assertEqual(new['status'], 'withheld')
            self.assertTrue(any('source hash mismatch' in error for error in new['source_errors']))
            self.assertEqual(failed['status'], 'withheld')
            self.assertEqual(failed['domains'], [])
            self.assertEqual(failed['modules'], {})
            self.assertTrue(failed['source_errors'])
            before = deepcopy(self.panels['A'])
            helper = cases.evaluate(self.panels['A'], root=root)
            self.assertEqual(helper['status'], 'withheld')
            self.assertTrue(helper['source_errors'])
            self.assertEqual(self.panels['A'], before)
            old_source = root / 'references/approved/ziwei-life-domains-v1.md'
            old_source.write_text(old_source.read_text(encoding='utf-8') + '\nchanged bytes\n', encoding='utf-8')
            failed = life.analyze(dynamic['native_wrapper_snapshot']['chart'], 1987, 2026, root=root)
            self.assertEqual(failed['status'], 'withheld')
            self.assertEqual(failed['domains'], [])
            self.assertTrue(failed['source_errors'])

    def test_helper_preserves_complete_canonical_facts_and_never_reads_forbidden_layers(self):
        class Poison:
            def __deepcopy__(self, memo):
                raise AssertionError('forbidden layer read')
            def get(self, key, default=None):
                raise AssertionError('forbidden layer read')
        panel = deepcopy(self.panels['C'])
        before = deepcopy(panel)
        panel['dynamic'].update(research_dynamic_iztro=Poison(), raw=Poison(), daily=Poison(),
                                decadal=Poison(), age=Poison(), hourly=Poison())
        panel['dynamic']['layers']['daily'] = Poison()
        result = cases.evaluate(panel)
        self.assertEqual(result['modules']['ZW-RC03']['status'], 'conditional')
        self.assertEqual(result['facts']['domains'], before['domains'])
        self.assertEqual(result['facts']['transformations'], before['transformations'])
        result['facts']['domains'][0]['facts'].clear()
        self.assertEqual(panel['domains'], before['domains'])
        self.assertEqual(panel['modules'], before['modules'])

    def test_existing_cli_exposes_cases_without_reclassifying_native_fields(self):
        dynamic = self.dynamics['C']
        snapshot = dict(input={'solar': '1971-01-06'}, provenance={'resolved_age_year': 2025},
                        ziwei=dynamic['native_wrapper_snapshot'])
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path, dynamic_path = Path(directory) / 'snapshot.json', Path(directory) / 'dynamic.json'
            snapshot_path.write_text(json.dumps(snapshot), encoding='utf-8')
            dynamic_path.write_text(json.dumps(dynamic), encoding='utf-8')
            output = subprocess.run([sys.executable, 'scripts/ziwei_life_reading.py',
                                     '--snapshot', str(snapshot_path), '--dynamic', str(dynamic_path)],
                                    cwd=ROOT, capture_output=True, text=True, check=True)
        panel = json.loads(output.stdout)
        self.assertEqual(panel['case_judgments']['profile'], cases.PROFILE)
        self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')
        self.assertEqual(len(panel['modules']), 15)
        self.assertEqual(snapshot['ziwei'], dynamic['native_wrapper_snapshot'])

    def test_normal_cli_preserves_natal_case_differences_on_both_birth_witnesses(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-03-06', '--hour', '11:00',
               '--sex', '男', '--lat', '30', '--lon', '120', '--analysis-year', '2026',
               '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))
        center = snapshot['ziwei']['life_reading']['case_judgments']['modules']
        self.assertTrue(all(row['status'] == 'withheld' for row in center.values()))
        before, after = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(before['input']['shichen_index'], 5)
        self.assertEqual(after['input']['shichen_index'], 6)
        for witness, branches in ((before, (None, None)),
                                  (after, ('negotiation_friction', 'tiantong_copresent'))):
            panel = witness['case_judgments']
            expected = life.analyze(witness['chart'], witness['input']['birth_year'], 2026)
            self.assertEqual(panel, expected['case_judgments'])
            modules = panel['modules']
            self.assertEqual(tuple(modules[k]['selected_branch'] for k in ('ZW-RC01', 'ZW-RC02')), branches)
            self.assertEqual(modules['ZW-RC03']['status'], 'withheld')
            self.assertFalse(panel['full_interval_coverage'])

    def test_candidate_follow_up_preserves_annual_branch_difference_and_cache_identity(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06', '--hour', '01:00',
             '--sex', '男', '--lat', '30', '--lon', '120', '--analysis-year', '2025',
             '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        target = '2025-11-10'
        other = json.loads(subprocess.check_output(
            ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1971-01-06', '--birth-year', '1971',
             '--shichen-index', '0', '--sex', '男', '--target-date', target, '--target-time-index', '6',
             '--source-label', 'synthetic-candidate-follow-up'], cwd=ROOT, text=True))
        primary = self.dynamics['C']
        before, after = snapshot['ziwei_scenario_comparison']['candidates']
        selected = dict(ziwei_candidate_id=after['id'], expected_target_date=target, expected_target_time_index=6)
        original = deepcopy(snapshot)
        c = life.analyze_snapshot(snapshot, primary, **selected)
        b = life.analyze_snapshot(snapshot, other, **dict(selected, ziwei_candidate_id=before['id']))
        mismatch = life.analyze_snapshot(snapshot, other, **selected)
        stale = life.analyze_snapshot(snapshot, primary, **dict(selected, expected_target_date='2025-11-11'))
        for panel, candidate, expected in (
                (b, before, 'not_triggered'), (c, after, 'conditional'),
                (mismatch, after, 'withheld'), (stale, after, 'withheld')):
            self.assertEqual(panel['birth_scenario']['id'], candidate['id'])
            self.assertEqual(panel['birth_scenario']['scenario_ids'], candidate['scenario_ids'])
            self.assertEqual(panel['birth_scenario']['coverage'], snapshot['scenarios']['coverage'])
            self.assertFalse(panel['birth_scenario']['birth_time_confirmed'])
            self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], expected)
            self.assertFalse(panel['case_judgments']['full_interval_coverage'])
        self.assertEqual(c['case_judgments']['modules']['ZW-RC03']['selected_branch'], 'proactive_application_fit')
        self.assertEqual(c['dynamic']['status'], 'admitted')
        self.assertEqual(mismatch['dynamic']['status'], 'withheld')
        self.assertEqual(c['domains'], mismatch['domains'])
        self.assertEqual(c['domains'], stale['domains'])
        wrong_year = deepcopy(snapshot)
        wrong_year['ziwei_scenario_comparison']['analysis_year'] = 2026
        year_conflict = life.analyze_snapshot(wrong_year, primary, **selected)
        self.assertEqual(year_conflict['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
        self.assertEqual(year_conflict['domains'], c['domains'])
        self.assertEqual(life.analyze_snapshot(snapshot, primary)['status'], 'withheld')
        self.assertEqual(snapshot, original)
        with self.assertRaisesRegex(ValueError, '预期日期'):
            life.analyze_snapshot(snapshot, primary, ziwei_candidate_id=after['id'])
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path, dynamic_path = Path(directory) / 'snapshot.json', Path(directory) / 'dynamic.json'
            snapshot_path.write_text(json.dumps(snapshot), encoding='utf-8')
            dynamic_path.write_text(json.dumps(primary), encoding='utf-8')
            command = [sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                       '--snapshot', str(snapshot_path), '--dynamic', str(dynamic_path),
                       '--expected-target-date', target, '--expected-target-time-index', '6',
                       '--ziwei-candidate']
            output = subprocess.check_output([*command, after['id']], cwd=ROOT, text=True)
            self.assertEqual(json.loads(output), c)
            bad = subprocess.run([*command, 'ziwei-candidate-3'], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, '')
            self.assertIn('未找到唯一的紫微候选 ID', bad.stderr)

    def test_saved_stage_ranges_are_checked_against_native_replay_even_without_bureau(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
               '--hour', '02:00', '--sex', '男', '--analysis-year', '2015', '--format', 'json']
        day = '2015-11-10'
        dynamic = json.loads(subprocess.check_output(
            ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1971-01-06', '--birth-year', '1971',
             '--shichen-index', '1', '--sex', '男', '--target-date', day, '--target-time-index', '6',
             '--source-label', 'synthetic-native-stage-start-age'], cwd=ROOT, text=True))
        for extra in ([], ['--uncertainty-minutes', '1', '--enumerate-scenarios']):
            with self.subTest(uncertainty=bool(extra)):
                snapshot = json.loads(subprocess.check_output([*cmd, *extra], cwd=ROOT, text=True))
                selected = dict(expected_target_date=day, expected_target_time_index=6)
                if extra:
                    candidate, = snapshot['ziwei_scenario_comparison']['candidates']
                    selected['ziwei_candidate_id'] = candidate['id']
                    chart = candidate['chart']
                else:
                    chart = snapshot['ziwei']['chart']
                genuine = life.analyze_snapshot(snapshot, dynamic, **selected)
                self.assertEqual(genuine['dynamic']['status'], 'admitted')
                self.assertEqual(genuine['case_judgments']['modules']['ZW-RC03']['status'], 'not_triggered')
                stages = genuine['modules']['ZW-T02']['rows'][0]
                self.assertEqual(next(row for row in stages['rows'] if row['current'])['domain'], '田宅')

                del chart['wuxingJu']
                for palace in chart['palaces']:
                    palace.pop('daXianAge', None)
                    palace.pop('isCurrentDaXian', None)
                self.assertEqual(life.analyze_snapshot(snapshot, dynamic, **selected), genuine)
                for row in chart['daXians']:
                    row['startAge'] -= 1
                    row['endAge'] -= 1
                chart['currentDaXianIndex'] = 4
                stale = life.analyze_snapshot(snapshot, dynamic, **selected)
                stage = stale['modules']['ZW-T02']['rows'][0]
                self.assertEqual(stage['status'], 'withheld')
                self.assertEqual(stage['rows'], [])
                self.assertIn('与原生复盘不一致', stage['errors'][0])
                self.assertEqual(stale['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
                self.assertEqual(stale['dynamic'], genuine['dynamic'])
                self.assertEqual(stale['domains'], genuine['domains'])

    def test_annual_case_distinguishes_verified_first_and_final_stage_boundaries(self):
        birth_cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06',
                     '--hour', '02:00', '--sex', '男', '--format', 'json', '--analysis-year']
        dynamic_cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1971-01-06',
                       '--birth-year', '1971', '--shichen-index', '1', '--sex', '男',
                       '--target-time-index', '0', '--source-label', 'synthetic-stage-coverage',
                       '--target-date']
        snapshots, dynamics = {}, {}
        def panel(day, year):
            return life.analyze_snapshot(snapshots[year], dynamics[day], expected_target_date=day,
                                         expected_target_time_index=0)

        natal = None
        for day, position, index, verdict, marker in (
                ('1975-12-31', 'before_first_stage', -1, 'not_triggered', '1976-01-01'),
                ('1976-01-01', 'active', 0, 'not_triggered', None),
                ('2095-12-31', 'active', 11, 'not_triggered', None),
                ('2096-01-01', 'after_last_stage', -1, 'withheld', '2096-01-01')):
            with self.subTest(day=day):
                year = day[:4]
                snapshots[year] = json.loads(subprocess.check_output([*birth_cmd, year], cwd=ROOT, text=True))
                dynamics[day] = json.loads(subprocess.check_output([*dynamic_cmd, day], cwd=ROOT, text=True))
                result = panel(day, year)
                stage, = result['modules']['ZW-T02']['rows']
                self.assertEqual(stage['covered_window'], {'start_inclusive': '1976-01-01',
                                                           'end_exclusive': '2096-01-01'})
                self.assertEqual(stage['current_status'], position)
                self.assertEqual(stage['current_index'], index)
                self.assertEqual(len(stage['rows']), 12)
                self.assertEqual(result['dynamic']['status'], 'admitted')
                rc03 = result['case_judgments']['modules']['ZW-RC03']
                self.assertEqual(rc03['status'], verdict)
                if marker:
                    self.assertIn(marker, rc03['reasons'][0])
                    self.assertEqual(rc03['context']['current_status'], position)
                    self.assertEqual(rc03['context']['covered_window'], stage['covered_window'])
                if natal is None:
                    natal = result['domains']
                self.assertEqual(result['domains'], natal)

        mismatched = panel('1976-01-01', '1975')
        rc03 = mismatched['case_judgments']['modules']['ZW-RC03']
        self.assertEqual(rc03['status'], 'withheld')
        self.assertIn('分析年度或当前年度窗不一致', rc03['reasons'][0])
        self.assertEqual(mismatched['dynamic'], panel('1976-01-01', '1976')['dynamic'])
        missing = life.analyze_snapshot(snapshots['1975'])['case_judgments']['modules']['ZW-RC03']
        self.assertEqual(missing['status'], 'withheld')
        self.assertIn('准入年层缺失', missing['reasons'][0])

    def test_candidate_follow_up_checks_witness_identity_and_uses_candidate_civil_year(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-12-31', '--hour', '23:59',
             '--sex', '男', '--lat', '30', '--lon', '120', '--analysis-year', '2026',
             '--uncertainty-minutes', '2', '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        early, late = snapshot['ziwei_scenario_comparison']['candidates']
        for candidate, expected in ((early, 1986), (late, 1987)):
            panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
            self.assertEqual(panel['modules']['ZW-T02']['rows'][0]['birth_year'], expected)
            self.assertEqual(panel['birth_scenario']['input']['birth_year'], expected)
        for field, value, error in (
                ('scenario_ids', early['scenario_ids'], '可达枚举标识冲突'),
                ('witness_utc', early['witness_utc'], '可达枚举记录冲突'),
                ('chart', early['chart'], '原盘与出生见证'),
                ('chart', None, '缺少有效原盘')):
            broken = deepcopy(snapshot)
            broken['ziwei_scenario_comparison']['candidates'][1][field] = value
            with self.subTest(field=field, error=error), self.assertRaisesRegex(ValueError, error):
                life.analyze_snapshot(broken, ziwei_candidate_id=late['id'])

    def test_candidate_follow_up_rejects_whole_cache_from_another_clock_basis(self):
        command = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-01-03',
                   '--hour', '23:00', '--sex', '男', '--lat', '31', '--lon', '90',
                   '--analysis-year', '2026', '--uncertainty-minutes', '1',
                   '--enumerate-scenarios', '--format', 'json', '--time-basis']
        civil = json.loads(subprocess.check_output([*command, 'civil'], cwd=ROOT, text=True))
        solar = json.loads(subprocess.check_output([*command, 'mean-solar'], cwd=ROOT, text=True))
        candidate = 'ziwei-candidate-1'
        for snapshot, hour in ((civil, '22:59:00'), (solar, '20:59:00')):
            panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate)
            self.assertEqual(panel['birth_scenario']['chart_clock'], '1986-01-03T' + hour)
        self.assertEqual(civil['scenarios']['coverage'], solar['scenarios']['coverage'])
        mixed = dict(solar, scenarios=civil['scenarios'],
                     ziwei_scenario_comparison=civil['ziwei_scenario_comparison'])
        with self.assertRaisesRegex(ValueError, '见证钟面与原输入时区、经度或口径冲突'):
            life.analyze_snapshot(mixed, ziwei_candidate_id=candidate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mixed.json'
            path.write_text(json.dumps(mixed), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                 '--snapshot', str(path), '--ziwei-candidate', candidate],
                cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertIn('见证钟面与原输入时区、经度或口径冲突', result.stderr)

    def test_candidate_follow_up_checks_other_witnesses_sharing_one_ziwei_input(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-01-05', '--hour', '23:28',
             '--sex', '男', '--lat', '30', '--lon', '120', '--analysis-year', '2026',
             '--uncertainty-minutes', '2', '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        candidate, = snapshot['ziwei_scenario_comparison']['candidates']
        panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
        self.assertEqual(panel['birth_scenario']['scenario_ids'], ['candidate-1', 'candidate-2'])
        second = snapshot['scenarios']['variants'][1]
        second['chart_clock'] = snapshot['scenarios']['variants'][0]['chart_clock']
        with self.assertRaisesRegex(ValueError, '见证钟面与原输入时区、经度或口径冲突'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])

    def test_candidate_follow_up_detects_missing_alias_with_unchanged_ziwei_interval(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-01-05', '--hour', '23:28',
             '--sex', '男', '--analysis-year', '2026', '--uncertainty-minutes', '2',
             '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        candidate, = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(candidate['scenario_ids'], ['candidate-1', 'candidate-2'])
        scenarios = snapshot['scenarios']
        first, second = scenarios['variants']
        first['intervals'].extend(second['intervals'])
        scenarios['variants'].pop()
        candidate['scenario_ids'].pop()
        with self.assertRaisesRegex(ValueError, '原枚举见证或标识与原出生输入重算不一致'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])

    def test_candidate_follow_up_rejects_adjacent_star_table_under_correct_birth_header(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1997-07-11', '--hour', '19:00',
             '--sex', '男', '--analysis-year', '2026', '--uncertainty-minutes', '1',
             '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        early, late = snapshot['ziwei_scenario_comparison']['candidates']
        for candidate, status in ((early, 'not_triggered'), (late, 'conditional')):
            panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
            self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], status)
        mixed = deepcopy(late['chart'])
        mixed['birthInfo'] = early['chart']['birthInfo']
        early['chart'] = mixed
        with self.assertRaisesRegex(ValueError, '原盘与出生见证重算不一致'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=early['id'])

    def test_candidate_follow_up_rejects_an_incomplete_saved_candidate_set(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-03-06', '--hour', '13:00',
             '--sex', '男', '--lat', '31.23', '--lon', '121.47', '--analysis-year', '2026',
             '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        before, after = snapshot['ziwei_scenario_comparison']['candidates']
        for candidate, branch in ((before, 'tiantong_copresent'), (after, None)):
            panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
            self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['selected_branch'], branch)

        degraded = deepcopy(snapshot)
        degraded_after = degraded['ziwei_scenario_comparison']['candidates'][1]
        degraded_after.update(chart=None, degradation='测试中的原盘降级')
        usable = life.analyze_snapshot(degraded, ziwei_candidate_id=before['id'])
        self.assertEqual(usable['birth_scenario']['id'], before['id'])
        with self.assertRaisesRegex(ValueError, '查本候选的降级记录'):
            life.analyze_snapshot(degraded, ziwei_candidate_id=after['id'])

        only_group_missing = deepcopy(snapshot)
        only_group_missing['ziwei_scenario_comparison']['candidates'].pop()
        with self.assertRaisesRegex(ValueError, '未覆盖全部枚举身份'):
            life.analyze_snapshot(only_group_missing, ziwei_candidate_id=before['id'])

        missing_variant = deepcopy(only_group_missing)
        missing_variant['scenarios']['variants'].pop()
        missing_closed_end = deepcopy(snapshot)
        missing_closed_end['scenarios']['variants'][-1]['intervals'].pop()
        early_inclusive = deepcopy(snapshot)
        early_inclusive['scenarios']['variants'][0]['intervals'][0]['end_inclusive'] = True
        for invalid in (missing_variant, missing_closed_end, early_inclusive):
            with self.assertRaisesRegex(ValueError, '枚举区间未完整覆盖或分段损坏'):
                life.analyze_snapshot(invalid, ziwei_candidate_id=before['id'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'incomplete.json'
            path.write_text(json.dumps(missing_variant), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                 '--snapshot', str(path), '--ziwei-candidate', before['id']],
                cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertIn('枚举区间未完整覆盖或分段损坏', result.stderr)

    def test_candidate_follow_up_detects_missing_apparent_solar_birth_witness(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1980-06-14', '--hour', '17:00',
             '--sex', '男', '--lat', '30', '--lon', '120', '--time-basis', 'apparent-solar',
             '--analysis-year', '2026', '--uncertainty-minutes', '5', '--enumerate-scenarios',
             '--format', 'json'], cwd=ROOT, text=True))
        early, late = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual([row['input']['shichen_index'] for row in (early, late)], [8, 9])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps(snapshot), encoding='utf-8')
            command = [sys.executable, '-B', 'scripts/ziwei_life_reading.py', '--snapshot', str(path),
                       '--ziwei-candidate']
            for candidate, status in ((early, 'conditional'), (late, 'not_triggered')):
                panel = json.loads(subprocess.check_output([*command, candidate['id']], cwd=ROOT, text=True))
                self.assertEqual(panel['stage_relationship']['relationship']['status'], status)
                self.assertEqual(panel['birth_scenario']['coverage'], 'numerical_witnesses_not_exhaustive')

            snapshot['scenarios']['variants'].pop()
            snapshot['ziwei_scenario_comparison']['candidates'].pop()
            path.write_text(json.dumps(snapshot), encoding='utf-8')
            result = subprocess.run([*command, early['id']], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertIn('真太阳时已采样的出生见证缺少对应紫微候选', result.stderr)

    def test_candidate_follow_up_detects_missing_short_apparent_solar_year_overlap(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '2001-01-01', '--hour', '00:00',
             '--sex', '男', '--lat', '30', '--lon', '121', '--time-basis', 'apparent-solar',
             '--analysis-year', '2026', '--uncertainty-minutes', '2', '--enumerate-scenarios',
             '--format', 'json'], cwd=ROOT, text=True))
        candidates = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual([(row['input']['solar_date'], row['input']['birth_year']) for row in candidates],
                         [('2000-12-31', 2000), ('2001-01-01', 2000), ('2001-01-01', 2001)])
        before, overlap, after = candidates
        panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=overlap['id'])
        self.assertEqual(panel['birth_scenario']['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertEqual(panel['modules']['ZW-T02']['rows'][0]['birth_year'], 2000)
        overlap['id'], after['id'] = after['id'], overlap['id']
        with self.assertRaisesRegex(ValueError, '候选 ID 与原枚举身份顺序冲突'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=after['id'])
        candidates.remove(overlap)
        snapshot['scenarios']['variants'].pop(1)
        after['scenario_ids'] = ['candidate-2']
        with self.assertRaisesRegex(ValueError, '原枚举见证或标识与原出生输入重算不一致'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=before['id'])

    def test_candidate_follow_up_checks_shichen_assignment_and_the_inclusive_end(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1997-02-16', '--hour', '20:59',
             '--sex', '男', '--analysis-year', '2026', '--uncertainty-minutes', '1',
             '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        early, late = snapshot['ziwei_scenario_comparison']['candidates']
        end = snapshot['scenarios']['end_utc']
        self.assertEqual(late['witness_utc'], end)
        for candidate, branch in ((early, 'tiantong_absent'), (late, 'tiantong_copresent')):
            panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
            self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['selected_branch'], branch)

        wrong_boundary = deepcopy(snapshot)
        first, last = wrong_boundary['scenarios']['variants']
        edge = '1997-02-16T12:59:00+00:00'
        first['intervals'][-1]['end_utc'] = edge
        last['intervals'][0]['start_utc'] = edge
        missing_end_candidate = deepcopy(snapshot)
        first = missing_end_candidate['scenarios']['variants'][0]
        first['intervals'][-1].update(end_utc=end, end_inclusive=True)
        missing_end_candidate['scenarios']['variants'].pop()
        missing_end_candidate['ziwei_scenario_comparison']['candidates'].pop()
        for damaged in (wrong_boundary, missing_end_candidate):
            with self.assertRaisesRegex(ValueError, '枚举分段与原输入的紫微出生日期、时辰或民用年份冲突'):
                life.analyze_snapshot(damaged, ziwei_candidate_id=early['id'])

    def test_candidate_follow_up_checks_an_interior_dst_excursion(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1988-10-29', '--hour', '22:45',
             '--sex', '男', '--timezone', 'America/Goose_Bay', '--fold', '0', '--analysis-year', '2026',
             '--uncertainty-minutes', '100', '--enumerate-scenarios', '--format', 'json'], cwd=ROOT, text=True))
        candidates = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertGreater(len(candidates), 1)
        for candidate in candidates:
            self.assertEqual(life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])['birth_scenario']['input'],
                             candidate['input'])

        # The two-hour rollback brings both endpoints into the same shichen.
        # The exact interval also visits the next shichen and the next date.
        scenarios = snapshot['scenarios']
        first = scenarios['variants'][0]
        first['intervals'] = [dict(start_utc=scenarios['start_utc'], end_utc=scenarios['end_utc'], end_inclusive=True)]
        scenarios['variants'] = [first]
        candidates[0]['scenario_ids'] = ['candidate-1']
        del candidates[1:]
        with self.assertRaisesRegex(ValueError, '枚举分段与原输入的紫微出生日期、时辰或民用年份冲突'):
            life.analyze_snapshot(snapshot, ziwei_candidate_id=candidates[0]['id'])

    def test_static_candidate_follow_up_reads_rest_domain_without_a_query_date(self):
        command = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-01-03',
                   '--sex', '男', '--lat', '31.23', '--lon', '121.47', '--analysis-year', '2026',
                   '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json']
        civil = json.loads(subprocess.check_output([*command, '--hour', '13:00'], cwd=ROOT, text=True))
        self.assertEqual(civil['ziwei']['life_reading']['modules']['ZW-D07']['status'], 'withheld')
        before, after = civil['ziwei_scenario_comparison']['candidates']
        before['case_judgments'] = {'ignored_cached_panel': True}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'complete.json'
            path.write_text(json.dumps(civil), encoding='utf-8')
            panel = json.loads(subprocess.check_output(
                [sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                 '--snapshot', str(path), '--ziwei-candidate', before['id']],
                cwd=ROOT, text=True))
        self.assertEqual(panel['modules']['ZW-D07']['status'], 'conditional')
        self.assertIn('modules', panel['case_judgments'])
        self.assertEqual(panel['dynamic']['status'], 'not_requested')
        exit_panel = life.analyze_snapshot(civil, ziwei_candidate_id=after['id'])
        self.assertEqual(exit_panel['modules']['ZW-D07']['status'], 'withheld')

        solar = json.loads(subprocess.check_output(
            [*command, '--hour', '08:00', '--time-basis', 'apparent-solar'], cwd=ROOT, text=True))
        candidate, = solar['ziwei_scenario_comparison']['candidates']
        sampled = life.analyze_snapshot(solar, ziwei_candidate_id=candidate['id'])
        self.assertEqual(sampled['birth_scenario']['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertEqual(sampled['modules']['ZW-D07']['status'], 'conditional')
        self.assertEqual(sampled['dynamic']['status'], 'not_requested')

    def test_target_year_conflict_does_not_erase_independent_natal_cases(self):
        dynamic = self.dynamics['A']
        snapshot = dict(input={'solar': '1987-03-06', 'analysis_year': 2027},
                        provenance={'resolved_age_year': 2026}, ziwei=dynamic['native_wrapper_snapshot'])
        panel = life.analyze_snapshot(snapshot, dynamic)
        self.assertEqual(panel['modules']['ZW-T02']['status'], 'withheld')
        modules = panel['case_judgments']['modules']
        self.assertEqual(modules['ZW-RC01']['selected_branch'], 'negotiation_friction')
        self.assertEqual(modules['ZW-RC02']['selected_branch'], 'tiantong_copresent')
        self.assertEqual(modules['ZW-RC03']['status'], 'withheld')


if __name__ == '__main__':
    unittest.main()
