"""Behavioral boundaries of the approved Ziwei research panel, using engine-generated synthetic charts."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_chart
import ziwei_life_reading as life


@unittest.skipUnless((ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
class ZiweiLifeReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmd = [sys.executable, 'scripts/build_chart.py', '--solar', '1986-01-03', '--hour', '22:30',
               '--sex', '男', '--lat', '31.23', '--lon', '121.47', '--time-basis', 'civil',
               '--analysis-year', '2026', '--format', 'json']
        cls.snapshot = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1986-01-03', '--birth-year', '1986',
               '--shichen-index', '11', '--sex', '男', '--target-date', '2026-11-10', '--target-time-index', '12',
               '--source-label', 'synthetic-life-panel-regression']
        cls.dynamic = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        code = """
const {generateChart}=require('./vendor/algorithm.ts');
const inputs=[
 {year:1961,month:1,day:21,hour:0,gender:'female'},
 {year:1990,month:5,day:15,hour:6,gender:'female'},
 {year:1988,month:10,day:10,hour:3,gender:'male'},
 {year:2000,month:12,day:31,hour:11,gender:'male'}];
console.log(JSON.stringify(inputs.map((b,i)=>generateChart(b,2026,i===3?2001:b.year))));
"""
        cls.charts = json.loads(subprocess.run(['node', '--import', 'tsx', '-e', code],
                              cwd=ROOT/'scripts/pai_pan_ziwei', capture_output=True, text=True, check=True).stdout)

    def panel(self, snapshot=None, dynamic=None):
        return life.analyze_snapshot(snapshot or self.snapshot, dynamic)

    def test_synthetic_build_adds_panel_preserving_raw_native_output(self):
        snapshot = self.snapshot
        native_cmd = ['node', '--import', 'tsx', 'pai_pan.ts', '--solar', '1986-01-03', '--hour', '22:30',
                      '--sex', '男', '--age-year', '2026', '--birth-year', '1986', '--format', 'json']
        direct = json.loads(subprocess.run(native_cmd, cwd=ROOT/'scripts/pai_pan_ziwei', capture_output=True, text=True, check=True).stdout)
        self.assertEqual(snapshot['ziwei']['chart'], direct['chart'])
        self.assertEqual(snapshot['ziwei']['rule_output'], direct['rule_output'])
        panel = snapshot['ziwei']['life_reading']
        self.assertEqual(panel, self.panel())
        self.assertEqual(panel['profile'], 'ziwei-life-domains-v1')
        self.assertEqual(len(panel['modules']), 15)
        self.assertEqual(len(panel['domains']), 12)
        self.assertEqual(panel['dynamic']['status'], 'not_requested')
        spouse = next(row for row in panel['domains'] if row['domain']=='夫妻')
        self.assertEqual([r['star'] for r in spouse['major_topics']], ['天同'])
        self.assertEqual(panel['modules']['ZW-S01']['rows'][0]['domain'], '夫妻')
        self.assertEqual(panel['modules']['ZW-T02']['rows'][0]['birth_year'], 1986)

    def test_synthetic_dates_have_different_engine_topics(self):
        outputs = [life.analyze(c, 2001 if i==3 else c['birthInfo']['year'], 2026) for i,c in enumerate(self.charts)]
        self.assertTrue(all(p['status']=='conditional' for p in outputs))
        placements = [[(row['domain'], [t['star'] for t in row['major_topics']]) for row in p['domains']] for p in outputs]
        self.assertGreater(len({json.dumps(p) for p in placements}), 1)
        for chart, output in zip(self.charts, outputs):
            for row in output['domains']:
                palace = next(p for p in chart['palaces'] if p['branch']==row['branch'])
                self.assertEqual([f['name'] for f in row['facts']], [s['name'] for s in palace['stars']])

    def test_empty_palace_keeps_only_actual_stars_without_borrowed_topics(self):
        panel = self.panel()
        empty = next(row for row in panel['domains'] if row['domain']=='财帛')
        self.assertTrue(empty['empty_palace'])
        self.assertEqual(empty['status'], 'withheld')
        self.assertEqual(empty['major_topics'], [])
        self.assertEqual(empty['borrowed_topics'], [])
        native = next(p for p in self.snapshot['ziwei']['chart']['palaces'] if p['name']=='财帛')
        self.assertTrue(native['stars'])
        self.assertEqual([f['name'] for f in empty['facts']], [s['name'] for s in native['stars']])
        self.assertTrue(all(f['natal_transform'] is None for f in empty['facts']))

    def test_nonmajor_ke_and_ji_are_facts_only_and_daily_is_never_read(self):
        dynamic = deepcopy(self.dynamic)
        dynamic['admitted_dynamic_facts']['layers']['daily'] = {'status':'facts_only','transformations':'do not read'}
        dynamic['research_dynamic_iztro']['raw_horoscope'].update(age='poison',decadal='poison',hourly='poison',daily='poison')
        dynamic['research_dynamic_iztro']['source_astrolabe'] = 'poison'
        panel = self.panel(dynamic=dynamic)
        self.assertEqual(panel['dynamic']['status'], 'admitted')
        self.assertEqual(len(panel['transformations']), 12)
        self.assertEqual({r['layer'] for r in panel['transformations']}, {'natal','yearly','monthly'})
        for layer, star in [('yearly','文昌'), ('monthly','文曲')]:
            row = next(r for r in panel['transformations'] if r['layer']==layer and r['star']==star)
            self.assertEqual(row['status'], 'facts_only')
            self.assertIsNone(row['topic'])
            self.assertIsNone(row['star_theme'])
        self.assertFalse(panel['dynamic']['full_interval_coverage'])
        self.assertEqual(panel['dynamic']['query_point']['time_index'], 12)

    def test_cross_layer_components_do_not_reclassify_native_withheld(self):
        before = deepcopy(self.snapshot)
        dynamic_before = deepcopy(self.dynamic)
        panel = self.panel(dynamic=self.dynamic)
        groups = panel['modules']['ZW-E05']['rows']
        group = next(g for g in groups if g['kind']=='same_star' and g['key']=='天机')
        self.assertEqual(set(group['component_ids']), {'natal.禄', 'yearly.权'})
        self.assertEqual(group['source_identity'], 'author_extension_same_star_or_cross_layer')
        self.assertEqual(group['net_effect'], 'withheld')
        self.assertEqual(group['calculation'], 'no_sum_no_cancellation_no_net_auspiciousness')
        self.assertEqual(self.snapshot, before)
        self.assertEqual(self.dynamic, dynamic_before)
        self.assertEqual(panel['old_native_fields'], 'preserved_without_reclassification')

    def test_wrong_profile_raw_input_and_birth_identity_are_refused_locally(self):
        bad_inputs = [self.dynamic['research_dynamic_iztro']]
        wrong_profile = deepcopy(self.dynamic)
        wrong_profile['admitted_dynamic_facts']['profile']='other-profile'
        bad_inputs.append(wrong_profile)
        wrong_birth = deepcopy(self.dynamic)
        wrong_birth['inputs']['birth']['shichen_index']=0
        bad_inputs.append(wrong_birth)
        wrong_native = deepcopy(self.dynamic)
        wrong_native['native_wrapper_snapshot']['chart']['palaces'][0]['stars'][0]['brightnessRaw']='陷'
        bad_inputs.append(wrong_native)
        raw_admitted = deepcopy(self.dynamic)
        raw_admitted['admitted_dynamic_facts']['layers']['age']={'status':'facts_only'}
        bad_inputs.append(raw_admitted)
        for bad in bad_inputs:
            with self.subTest(bad=bad.get('schema_version')):
                panel = self.panel(dynamic=bad)
                self.assertEqual(panel['dynamic']['status'], 'withheld')
                self.assertTrue(panel['dynamic']['errors'])
                self.assertEqual(len(panel['transformations']), 4)
                self.assertEqual(next(r for r in panel['domains'] if r['domain']=='夫妻')['status'], 'conditional')
                self.assertEqual(panel['modules']['ZW-T02']['status'], 'conditional')

    def test_missing_static_star_details_do_not_withhold_verified_dynamic_layers(self):
        native_before = deepcopy(self.dynamic)
        complete = self.panel(dynamic=self.dynamic)
        natal_kinds = {row['kind'] for row in complete['transformations'] if row['layer'] == 'natal'}
        for field, canonical_field in (('brightnessRaw', 'brightness_raw'), ('siHua', 'natal_transform')):
            with self.subTest(field=field):
                snapshot = deepcopy(self.snapshot)
                star = next(star for palace in snapshot['ziwei']['chart']['palaces'] for star in palace['stars']
                            if star['name'] == '天机')
                self.assertTrue(star.pop(field))
                panel = self.panel(snapshot, self.dynamic)
                dynamic = panel['dynamic']
                self.assertEqual(dynamic['status'], 'admitted')
                for layer in ('yearly', 'monthly'):
                    result = dynamic['layers'][layer]
                    self.assertEqual(result['status'], 'admitted')
                    self.assertEqual([(row['id'], row['star'], row['fact']['branch'])
                                      for row in result['transformations']],
                                     [(row['id'], row['star'], row['fact']['branch'])
                                      for row in complete['dynamic']['layers'][layer]['transformations']])
                fact = next(fact for domain in panel['domains'] for fact in domain['facts'] if fact['name'] == '天机')
                self.assertEqual(dynamic['unverified_static_fields'], [fact['path'] + '.' + field])
                self.assertIsNone(fact[canonical_field])
                yearly_power = next(row for row in panel['transformations'] if row['id'] == 'yearly.权')
                self.assertEqual(yearly_power['status'], 'conditional')
                self.assertEqual(yearly_power['fact'], fact)
                self.assertNotIn(field, star)
                expected_kinds = natal_kinds - {'禄'} if field == 'siHua' else natal_kinds
                self.assertEqual({row['kind'] for row in panel['transformations'] if row['layer'] == 'natal'},
                                 expected_kinds)
                rc03 = panel['case_judgments']['modules']['ZW-RC03']
                if field == 'siHua':
                    lu_module = panel['modules']['ZW-E01']
                    self.assertEqual(lu_module['status'], 'conditional')
                    self.assertEqual([(row['id'], row['status']) for row in lu_module['rows']],
                                     [('yearly.禄', 'conditional'), ('monthly.禄', 'conditional')])
                    self.assertEqual(rc03['status'], 'withheld')
                    self.assertIn(panel['case_judgments']['natal_transform_error'], rc03['reasons'])
                else:
                    self.assertEqual(rc03['status'], complete['case_judgments']['modules']['ZW-RC03']['status'])
        self.assertEqual(self.dynamic, native_before)

    def test_dynamic_identity_rejects_conflicts_and_invalid_extra_natal_markers(self):
        for mutation in ('raw_grade', 'legacy_grade', 'natal_kind', 'native_no_grade', 'native_bad_grade',
                         'native_no_kind', 'wrong_kind_location', 'extra_kind', 'swapped_palaces'):
            with self.subTest(mutation=mutation):
                snapshot, dynamic = deepcopy(self.snapshot), deepcopy(self.dynamic)
                static_palaces = snapshot['ziwei']['chart']['palaces']
                native_palaces = dynamic['native_wrapper_snapshot']['chart']['palaces']
                static_star = next(star for palace in static_palaces for star in palace['stars']
                                   if star['name'] == '天机')
                native_star = next(star for palace in native_palaces for star in palace['stars']
                                   if star['name'] == '天机')
                if mutation == 'raw_grade':
                    static_star['brightnessRaw'] = '陷'
                elif mutation == 'legacy_grade':
                    static_star['brightnessRaw'] = '庙旺'
                elif mutation == 'natal_kind':
                    static_star['siHua'] = '权'
                elif mutation == 'native_no_grade':
                    native_star.pop('brightnessRaw')
                elif mutation == 'native_bad_grade':
                    static_star.pop('brightnessRaw')
                    native_star['brightnessRaw'] = '庙旺'
                elif mutation == 'native_no_kind':
                    native_star.pop('siHua')
                elif mutation in ('wrong_kind_location', 'extra_kind'):
                    static_star.pop('siHua')
                    if mutation == 'wrong_kind_location':
                        native_star.pop('siHua')
                    unmarked = next(star for palace in native_palaces for star in palace['stars']
                                    if star['name'] == '巨门')
                    self.assertFalse(unmarked.get('siHua'))
                    unmarked['siHua'] = '禄'
                else:
                    other, current = (palace['stars'] for palace in native_palaces[:2])
                    other[0], current[0] = current[0], other[0]
                panel = self.panel(snapshot, dynamic)
                self.assertEqual(panel['dynamic']['status'], 'withheld')
                self.assertIn('本命星表与实际出生盘不一致', panel['dynamic']['errors'][0])
                self.assertTrue(all(row['layer'] == 'natal' for row in panel['transformations']))

    def test_wrong_dynamic_attachment_or_layer_coordinates_only_blocks_that_layer(self):
        bad = deepcopy(self.dynamic)
        layers = bad['admitted_dynamic_facts']['layers']
        layers['yearly']['transformations'][0]['natal_star_locations'][0]['location'] = deepcopy(layers['yearly']['ming_coordinate'])
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['status'], 'partial')
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'admitted')
        self.assertEqual({r['layer'] for r in panel['transformations']}, {'natal','monthly'})
        bad = deepcopy(self.dynamic)
        bad['admitted_dynamic_facts']['layers']['monthly']['domain_coordinates'][0]['layer_palace_name']='夫妻BAD'
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')

    def test_swapped_dynamic_layers_and_transformation_paths_are_refused(self):
        bad = deepcopy(self.dynamic)
        layers = bad['admitted_dynamic_facts']['layers']
        layers['yearly'], layers['monthly'] = layers['monthly'], layers['yearly']
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['status'], 'withheld')
        self.assertEqual({r['layer'] for r in panel['transformations']}, {'natal'})
        bad = deepcopy(self.dynamic)
        bad['admitted_dynamic_facts']['layers']['monthly']['transformations'][0]['raw_pointer'] = '/research_dynamic_iztro/raw_horoscope/yearly/mutagen/0'
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')

    def test_target_year_and_yearly_branch_are_bound_to_actual_source(self):
        bad = deepcopy(self.dynamic)
        bad['inputs']['target']['solar_date'] = '2033-09-14'
        self.assertEqual(self.panel(dynamic=bad)['dynamic']['status'], 'withheld')
        bad = deepcopy(self.dynamic)
        layer = bad['admitted_dynamic_facts']['layers']['yearly']
        layer['earthly_branch'] = '子' if layer['earthly_branch'] != '子' else '丑'
        bad['research_dynamic_iztro']['selected_fact_views']['yearly']['earthly_branch'] = layer['earthly_branch']
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'admitted')

    def test_query_date_calendar_boundaries_and_derived_views_are_audited_locally(self):
        for changed_date in ('2026-11-11', '2026-12-10'):
            bad = deepcopy(self.dynamic)
            bad['inputs']['target']['solar_date'] = changed_date
            panel = self.panel(dynamic=bad)
            self.assertEqual(panel['dynamic']['status'], 'withheld')
            self.assertIn('solarDate', panel['dynamic']['errors'][0])
            self.assertEqual(len(panel['transformations']), 4)
        for mutation in ('target_month','birth_month','derived_view','missing_view'):
            bad = deepcopy(self.dynamic)
            research = bad['research_dynamic_iztro']
            if mutation == 'target_month':
                target = research['calendar_observation']['target_lunar']
                target['lunarMonth'] = target['lunarMonth'] % 12 + 1
            elif mutation == 'birth_month':
                birth = research['calendar_observation']['birth_lunar']
                birth['lunarMonth'] = birth['lunarMonth'] % 12 + 1
            elif mutation == 'derived_view':
                research['selected_fact_views']['monthly']['heavenly_stem'] = '甲'
            else:
                del research['selected_fact_views']['monthly']
            with self.subTest(mutation=mutation):
                panel = self.panel(dynamic=bad)
                self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
                self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')
                self.assertEqual(next(r for r in panel['domains'] if r['domain']=='夫妻')['status'], 'conditional')
        bad = deepcopy(self.dynamic)
        del bad['research_dynamic_iztro']['raw_horoscope']['solarDate']
        self.assertEqual(self.panel(dynamic=bad)['dynamic']['status'], 'withheld')

    def test_missing_month_calendar_metadata_preserves_verified_yearly_application_case(self):
        birth = '1971-01-06'
        target = '2025-11-10'
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', 'scripts/build_chart.py', '--solar', birth, '--hour', '02:00',
            '--sex', '男', '--utc-offset', '8', '--analysis-year', '2025', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        facts = json.loads(subprocess.check_output([
            'node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth, '--birth-year', '1971',
            '--shichen-index', '1', '--sex', '男', '--target-date', target, '--target-time-index', '0',
            '--source-label', 'synthetic-partial-calendar-metadata',
        ], cwd=ROOT, text=True, timeout=45))
        query = dict(expected_target_date=target, expected_target_time_index=0, requested_analysis_year=2025)
        baseline = life.analyze_snapshot(snapshot, facts, **query)
        self.assertEqual(baseline['dynamic']['status'], 'admitted')
        self.assertEqual(baseline['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')

        for missing in ('lunarMonth', 'lunarDay', 'isLeap'):
            with self.subTest(missing=missing):
                partial = deepcopy(facts)
                del partial['research_dynamic_iztro']['calendar_observation']['target_lunar'][missing]
                panel = life.analyze_snapshot(snapshot, partial, **query)
                self.assertEqual(panel['dynamic']['status'], 'partial')
                self.assertEqual(panel['dynamic']['layers']['yearly'], baseline['dynamic']['layers']['yearly'])
                self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
                self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], 'conditional')
                self.assertEqual(panel['stage_query_scope'], baseline['stage_query_scope'])

        invalid = deepcopy(facts)
        invalid['research_dynamic_iztro']['calendar_observation']['target_lunar']['isLeap'] = 1
        panel = life.analyze_snapshot(snapshot, invalid, **query)
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')

        missing_year = deepcopy(facts)
        del missing_year['research_dynamic_iztro']['calendar_observation']['target_lunar']['lunarYear']
        panel = life.analyze_snapshot(snapshot, missing_year, **query)
        self.assertEqual(panel['dynamic']['status'], 'withheld')
        self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')

    def test_month_stem_and_transformations_cannot_be_borrowed_from_previous_month(self):
        cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1986-01-03', '--birth-year', '1986',
               '--shichen-index', '11', '--sex', '男', '--target-date', '2026-11-08', '--target-time-index', '0',
               '--source-label', 'synthetic-previous-month-stem']
        before = json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        previous = before['admitted_dynamic_facts']['layers']['monthly']
        self.assertEqual((previous['heavenly_stem'], previous['earthly_branch']), ('戊', '戌'))
        query = dict(expected_target_date='2026-11-10', expected_target_time_index=12)
        valid = life.analyze_snapshot(self.snapshot, self.dynamic, **query)
        admitted = valid['dynamic']['layers']['monthly']
        self.assertEqual((admitted['status'], admitted['heavenly_stem'], admitted['earthly_branch']),
                         ('admitted', '己', '亥'))

        bad = deepcopy(self.dynamic)
        for layer in (bad['admitted_dynamic_facts']['layers']['monthly'],
                      bad['research_dynamic_iztro']['selected_fact_views']['monthly']):
            for key in ('heavenly_stem', 'transformations'):
                layer[key] = deepcopy(previous[key])
        panel = life.analyze_snapshot(self.snapshot, bad, **query)
        rejected = panel['dynamic']['layers']['monthly']
        self.assertEqual(panel['dynamic']['status'], 'partial')
        self.assertEqual(rejected['status'], 'withheld')
        self.assertIn('闰月半月边界不一致', rejected['errors'][0])
        self.assertEqual(panel['dynamic']['layers']['yearly'], valid['dynamic']['layers']['yearly'])
        self.assertEqual(panel['modules']['ZW-T02'], valid['modules']['ZW-T02'])
        self.assertEqual(panel['domains'], valid['domains'])
        self.assertEqual({row['layer'] for row in panel['transformations']}, {'natal', 'yearly'})

    def test_real_leap_month_fifteen_sixteen_boundary_and_mislabeled_calendar(self):
        dynamics, panels = [], []
        for target_date in ('2023-04-05','2023-04-06'):
            cmd = ['node','scripts/ziwei_dynamic_facts.mjs','--solar','1986-01-03','--birth-year','1986',
                   '--shichen-index','11','--sex','男','--target-date',target_date,'--target-time-index','0',
                   '--source-label','synthetic-life-query-boundary-regression']
            dynamic = json.loads(subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True).stdout)
            dynamics.append(dynamic)
            panels.append(self.panel(dynamic=dynamic))
        lunar = [d['research_dynamic_iztro']['calendar_observation']['target_lunar'] for d in dynamics]
        self.assertEqual([(r['isLeap'],r['lunarMonth'],r['lunarDay']) for r in lunar], [(True,2,15),(True,2,16)])
        self.assertTrue(all(p['dynamic']['status']=='admitted' for p in panels))
        months = [p['dynamic']['layers']['monthly'] for p in panels]
        self.assertEqual([r['heavenly_stem'] + r['earthly_branch'] for r in months], ['乙卯', '丙辰'])
        branches = [r['ming_coordinate']['branch_index'] for r in months]
        self.assertEqual((branches[1]-branches[0])%12, 1)
        bad = deepcopy(dynamics[0])
        bad['research_dynamic_iztro']['calendar_observation']['target_lunar']['lunarDay'] = 16
        panel = self.panel(dynamic=bad)
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['layers']['yearly']['status'], 'admitted')

        stale = deepcopy(dynamics[0])
        stale['inputs']['target']['solar_date'] = '2023-04-06'
        stale['research_dynamic_iztro']['raw_horoscope']['solarDate'] = '2023-4-6'
        panel = life.analyze_snapshot(self.snapshot, stale, expected_target_date='2023-04-06',
                                      expected_target_time_index=0)
        self.assertEqual(panel['dynamic']['status'], 'partial')
        self.assertEqual(panel['dynamic']['layers']['monthly']['status'], 'withheld')
        self.assertIn('实际查询日期', panel['dynamic']['layers']['monthly']['errors'][0])
        self.assertEqual(panel['dynamic']['layers']['yearly'], panels[1]['dynamic']['layers']['yearly'])
        self.assertEqual(panel['domains'], panels[1]['domains'])

    def test_relabeling_a_prespring_snapshot_cannot_supply_new_lunar_year_facts(self):
        cmd = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1986-01-03', '--birth-year', '1986',
               '--shichen-index', '11', '--sex', '男', '--target-time-index', '12',
               '--source-label', 'synthetic-lunar-new-year-cache-regression', '--target-date']
        before, after = [json.loads(subprocess.check_output([*cmd, day], cwd=ROOT, text=True))
                         for day in ('2026-02-16', '2026-02-17')]
        self.assertEqual(self.panel(dynamic=before)['dynamic']['status'], 'admitted')
        native = self.panel(dynamic=after)
        self.assertEqual(native['dynamic']['status'], 'admitted')
        self.assertEqual([r['research_dynamic_iztro']['calendar_observation']['target_lunar']['lunarYear']
                          for r in (before, after)], [2025, 2026])
        before['inputs']['target']['solar_date'] = '2026-02-17'
        before['research_dynamic_iztro']['raw_horoscope']['solarDate'] = '2026-2-17'
        stale = life.analyze_snapshot(self.snapshot, before, expected_target_date='2026-02-17',
                                      expected_target_time_index=12)
        self.assertEqual(stale['dynamic']['status'], 'withheld')
        self.assertEqual(set(stale['dynamic']['layers']), {'yearly', 'monthly'})
        for layer in stale['dynamic']['layers'].values():
            self.assertEqual(layer['status'], 'withheld')
            self.assertIn('来源农历年与实际查询日期', layer['errors'][0])
        self.assertEqual(stale['domains'], native['domains'])

    def test_wrong_natal_attachment_withholds_only_affected_kinds_without_rewriting_facts(self):
        snapshot = deepcopy(self.snapshot)
        stars = [s for p in snapshot['ziwei']['chart']['palaces'] for s in p['stars']]
        next(s for s in stars if s.get('siHua')=='禄')['siHua']='权'
        panel = self.panel(snapshot)
        self.assertTrue(panel['input_errors'])
        self.assertEqual(set(panel['natal_transform_errors']), {'禄', '权'})
        self.assertEqual(panel['transformations'], [row for row in self.panel()['transformations']
                                                   if row['kind'] in ('科', '忌')])
        self.assertEqual(panel['modules']['ZW-E01']['status'], 'withheld')
        self.assertEqual(panel['modules']['ZW-E02']['status'], 'withheld')
        self.assertEqual(next(r for r in panel['domains'] if r['domain']=='福德')['status'], 'conditional')
        self.assertEqual(next(f for r in panel['domains'] for f in r['facts'] if f['name']=='天机')['natal_transform'], '权')

    def test_legacy_or_unknown_brightness_cannot_supply_an_intermediate_grade(self):
        snapshot = deepcopy(self.snapshot)
        palace = next(p for p in snapshot['ziwei']['chart']['palaces'] if p['name']=='福德')
        star = next(s for s in palace['stars'] if s['type']=='major')
        for raw in ('平', '庙旺', '不明'):
            with self.subTest(raw=raw):
                star['brightnessRaw'] = raw
                row, = self.panel(snapshot)['modules']['ZW-D07']['rows']
                topic = next(t for t in row['major_topics'] if t['star']==star['name'])
                self.assertEqual(row['status'], 'conditional')
                self.assertEqual(topic['brightness_raw'], raw)
                expected = '保存亮度与复盘不一致' if raw=='平' else '缺少原始亮度'
                self.assertIn(expected, topic['brightness_discussion'])

    def test_t02_exact_current_annual_window_and_optional_fields_remain_missing(self):
        stages = self.panel()['modules']['ZW-T02']['rows'][0]
        current = next(r for r in stages['rows'] if r['current'])
        self.assertEqual(stages['current_age'], 41)
        self.assertEqual(stages['current_index'], 3)
        self.assertEqual(current['domain'], '子女')
        self.assertEqual(current['window'], {'start_inclusive':'2021-01-01','end_exclusive':'2031-01-01'})
        self.assertNotIn('siHua', current['native'])
        self.assertNotIn('stemName', current['native'])
        chart = deepcopy(self.snapshot['ziwei']['chart'])
        for age, index, year in ((25, 1, 2010), (26, 2, 2011)):
            chart.update(currentAge=age, currentDaXianIndex=index)
            branch = chart['daXians'][index]['palaceBranch']
            for palace in chart['palaces']:
                palace['isCurrentDaXian'] = palace['branch'] == branch
            module = life.analyze(chart, 1986, year)['modules']['ZW-T02']
            self.assertEqual(module['status'], 'conditional')
            rows = module['rows'][0]['rows']
        self.assertEqual(next(r for r in rows if r['current'])['domain'],'夫妻')

    def test_conflicting_native_palace_stage_facts_only_withhold_stage_and_annual_case(self):
        snapshot = json.loads(subprocess.check_output(
            [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1971-01-06', '--hour', '02:00',
             '--sex', '男', '--analysis-year', '2026', '--format', 'json'], cwd=ROOT, text=True))
        target = '2026-01-02'
        dynamic = json.loads(subprocess.check_output(
            ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', '1971-01-06', '--birth-year', '1971',
             '--shichen-index', '1', '--sex', '男', '--target-date', target, '--target-time-index', '0',
             '--source-label', 'synthetic-native-stage-conflict'], cwd=ROOT, text=True))
        query = dict(expected_target_date=target, expected_target_time_index=0)
        baseline = life.analyze_snapshot(snapshot, dynamic, **query)
        current = next(row for row in baseline['stage_relationship']['stages'] if row['legacy_stage']['current'])
        self.assertEqual(current['legacy_stage']['domain'], '仆役')
        self.assertEqual(baseline['case_judgments']['modules']['ZW-RC03']['status'], 'not_triggered')
        self.assertEqual([(row['star'], row['fact']['domain']) for row in baseline['transformations']
                          if row['id'] in ('yearly.禄', 'yearly.权')], [('天机', '官禄'), ('天梁', '官禄')])

        legacy = deepcopy(snapshot)
        for palace in legacy['ziwei']['chart']['palaces']:
            palace.pop('daXianAge', None)
            palace.pop('isCurrentDaXian', None)
        self.assertEqual(life.analyze_snapshot(legacy, dynamic, **query), baseline)

        for mutation, marker in (('swap_palaces', 'daXianAge'), ('omit_current', 'daXianAge'),
                                 ('wrong_current_flag', 'isCurrentDaXian')):
            with self.subTest(mutation=mutation):
                damaged = deepcopy(snapshot)
                chart = damaged['ziwei']['chart']
                index = chart['currentDaXianIndex']
                active = chart['daXians'][index]
                if mutation == 'swap_palaces':
                    career = next(row for row in chart['daXians'] if row['palaceName'] == '官禄')
                    for field in ('palaceName', 'palaceBranch'):
                        career[field], active[field] = active[field], career[field]
                elif mutation == 'omit_current':
                    chart['daXians'].pop(index)
                    chart['currentDaXianIndex'] = -1
                else:
                    palace = next(row for row in chart['palaces'] if row['branch'] == active['palaceBranch'])
                    palace['isCurrentDaXian'] = False
                panel = life.analyze_snapshot(damaged, dynamic, **query)
                stage = panel['modules']['ZW-T02']
                self.assertEqual(stage['status'], 'withheld')
                self.assertIn(marker, stage['rows'][0]['errors'][0])
                self.assertEqual(stage['rows'][0]['rows'], [])
                self.assertEqual(panel['stage_relationship']['stage_status'], 'withheld')
                self.assertEqual(panel['case_judgments']['modules']['ZW-RC03']['status'], 'withheld')
                self.assertEqual(panel['stage_relationship']['relationship'], baseline['stage_relationship']['relationship'])
                self.assertEqual(panel['modules']['ZW-D04'], baseline['modules']['ZW-D04'])
                self.assertEqual(panel['dynamic'], baseline['dynamic'])
                for rule in ('ZW-RC01', 'ZW-RC02'):
                    self.assertEqual(panel['case_judgments']['modules'][rule], baseline['case_judgments']['modules'][rule])

    def test_stage_order_cannot_come_from_an_opposite_sex_native_chart(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1980-02-17', '--hour', '10:00',
               '--analysis-year', '2020', '--format', 'json']
        male, female = (json.loads(subprocess.check_output([*cmd, '--sex', sex], cwd=ROOT, text=True))
                        for sex in ('男', '女'))
        baseline = self.panel(male)
        stage = next(row for row in baseline['stage_relationship']['stages'] if row['legacy_stage']['current'])
        self.assertEqual(stage['legacy_stage']['domain'], '田宅')
        self.assertEqual(stage['legacy_stage']['window'],
                         {'start_inclusive': '2011-01-01', 'end_exclusive': '2021-01-01'})
        self.assertEqual(stage['modules']['ZW-ST09']['selected_branch'], 'pojun_resource_support')
        self.assertEqual(self.panel(female)['modules']['ZW-T02']['status'], 'conditional')

        mixed = deepcopy(male)
        recipient = mixed['ziwei']['chart']
        donor = female['ziwei']['chart']
        for field in ('daXians', 'currentDaXianIndex'):
            recipient[field] = donor[field]
        donor_palaces = {palace['branch']: palace for palace in donor['palaces']}
        for palace in recipient['palaces']:
            for field in ('daXianAge', 'isCurrentDaXian'):
                palace[field] = donor_palaces[palace['branch']][field]
        panel = self.panel(mixed)
        t02 = panel['modules']['ZW-T02']
        self.assertEqual(t02['status'], 'withheld')
        self.assertIn('顺逆', t02['unresolved'][0])
        self.assertEqual(panel['stage_relationship']['stages'], [])
        self.assertEqual(panel['stage_relationship']['relationship'], baseline['stage_relationship']['relationship'])
        self.assertEqual(panel['modules']['ZW-D04'], baseline['modules']['ZW-D04'])

    def test_stage_recovers_missing_resolved_year_from_corroborated_explicit_year(self):
        baseline = self.panel()
        for section, field in (('input', 'analysis_year'), ('input', 'age_year'), ('provenance', 'analysis_year')):
            with self.subTest(section=section, field=field):
                snapshot = deepcopy(self.snapshot)
                del snapshot['provenance']['resolved_age_year']
                del snapshot['provenance']['analysis_year']
                del snapshot['input']['analysis_year']
                snapshot[section][field] = 2026
                panel = self.panel(snapshot)
                self.assertEqual(panel['modules']['ZW-T02'], baseline['modules']['ZW-T02'])
                self.assertEqual(panel['stage_relationship'], baseline['stage_relationship'])

    def test_stage_withholds_missing_year_when_explicit_evidence_is_insufficient_or_inconsistent(self):
        baseline = self.panel()
        for label, analysis_year, provenance_year, native_age_year in (
                ('native only', None, None, 2026),
                ('request only', 2026, None, None),
                ('conflicting request years', 2026, 2027, 2026),
                ('conflicting native year', 2026, 2026, 2027),
                ('malformed request year', 2026.0, 2026, 2026),
                ('malformed native year', 2026, 2026, 2026.0)):
            with self.subTest(label=label):
                snapshot = deepcopy(self.snapshot)
                del snapshot['provenance']['resolved_age_year']
                snapshot['input']['analysis_year'] = analysis_year
                snapshot['provenance']['analysis_year'] = provenance_year
                snapshot['ziwei']['input']['ageYear'] = native_age_year
                panel = self.panel(snapshot)
                self.assertEqual(panel['modules']['ZW-T02']['status'], 'withheld')
                self.assertIsNone(panel['modules']['ZW-T02']['rows'][0]['analysis_year'])
                self.assertEqual(panel['stage_relationship']['stages'], [])
                self.assertEqual(panel['stage_relationship']['relationship'], baseline['stage_relationship']['relationship'])
                self.assertEqual(panel['domains'], baseline['domains'])

    def test_missing_civil_year_or_conflicting_target_age_only_limits_relevant_layers(self):
        for edit in ('missing','age'):
            snapshot = deepcopy(self.snapshot)
            if edit=='missing':
                del snapshot['input']['solar']
            else:
                snapshot['ziwei']['chart']['currentAge']=42
            panel = self.panel(snapshot)
            self.assertEqual(panel['modules']['ZW-T02']['status'], 'withheld')
            self.assertEqual(next(r for r in panel['domains'] if r['domain']=='夫妻')['status'], 'conditional')
            self.assertEqual(len(panel['transformations']), 4)
        snapshot = deepcopy(self.snapshot)
        snapshot['provenance']['resolved_age_year']=2027
        panel = self.panel(snapshot, self.dynamic)
        self.assertEqual(panel['modules']['ZW-T02']['status'], 'withheld')
        self.assertEqual(panel['dynamic']['status'], 'admitted')

    def test_explicit_birth_identity_conflicts_withhold_personal_panels(self):
        for section, field, value in (
                ('input', 'solar', '1985-01-03'),
                ('input', 'solar', '1986-01-04'),
                ('input', 'solar', '1986-1-4'),
                ('input', 'hour', '23:30'),
                ('input', 'hour', '25:00'),
                ('input', 'sex', '女'),
                ('time', 'chart_clock', '1986-01-03T23:30:00'),
                ('ziwei_input', 'solar', '1986-01-04'),
                ('ziwei_input', 'shichenIndex', 0)):
            with self.subTest(section=section, field=field, value=value):
                snapshot = deepcopy(self.snapshot)
                target = snapshot['ziwei']['input'] if section == 'ziwei_input' else snapshot[section]
                target[field] = value
                panel = self.panel(snapshot, self.dynamic)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn('出生', panel['input_errors'][0])
                self.assertIn('冲突', panel['input_errors'][0])
                self.assertEqual(panel['domains'], [])
                self.assertEqual(panel['dynamic']['status'], 'withheld')
                self.assertTrue(all(r['status'] == 'withheld' for r in panel['case_judgments']['modules'].values()))
                self.assertEqual(panel['stage_relationship']['status'], 'withheld')
                self.assertEqual(snapshot['ziwei']['chart'], self.snapshot['ziwei']['chart'])

    def test_unpadded_birth_date_preserves_static_and_dynamic_reading(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-1-3', '--hour', '22:30',
               '--sex', '男', '--lat', '31.23', '--lon', '121.47', '--time-basis', 'civil',
               '--analysis-year', '2026', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))
        self.assertEqual(snapshot['input']['solar'], '1986-1-3')
        self.assertEqual(snapshot['time'], self.snapshot['time'])
        self.assertEqual(snapshot['ziwei'], self.snapshot['ziwei'])
        self.assertEqual(self.panel(snapshot, self.dynamic), self.panel(dynamic=self.dynamic))

    def test_unpadded_birth_date_preserves_enumerated_candidate_reading(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-5-27', '--hour', '17:00',
               '--sex', '男', '--analysis-year', '2026', '--format', 'json',
               '--enumerate-scenarios', '--uncertainty-minutes', '1']
        snapshot = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))
        candidates = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(len(candidates), 2)
        for candidate in candidates:
            with self.subTest(candidate=candidate['id']):
                panel = life.analyze_snapshot(snapshot, ziwei_candidate_id=candidate['id'])
                self.assertEqual(panel['stage_relationship'], candidate['stage_relationship'])
                self.assertEqual(panel['case_judgments'], candidate['case_judgments'])

    def test_enumerated_candidates_rebuild_missing_saved_civil_clock_and_check_conflicts(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '2024-11-03', '--hour', '01:00',
               '--sex', '男', '--timezone', 'America/New_York', '--fold', '1', '--analysis-year', '2026',
               '--format', 'json', '--enumerate-scenarios', '--uncertainty-minutes', '2']
        snapshot = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True, timeout=60))
        candidate = snapshot['ziwei_scenario_comparison']['candidates'][0]
        options = dict(ziwei_candidate_id=candidate['id'])
        intact = life.analyze_snapshot(snapshot, **options)
        self.assertEqual(snapshot['scenarios']['start_utc'], '2024-11-03T05:58:00+00:00')
        self.assertEqual(snapshot['scenarios']['end_utc'], '2024-11-03T06:02:00+00:00')
        self.assertEqual(intact['status'], 'conditional')
        scope = intact['birth_scenario']
        self.assertEqual(scope['time_basis'], 'civil')
        self.assertEqual([
            (row['start_utc'], row['end_utc'], row['end_inclusive'], row['civil_offset_seconds'])
            for row in scope['reachable_utc_intervals']
        ], [
            ('2024-11-03T05:58:00+00:00', '2024-11-03T06:00:00+00:00', False, -14400),
            ('2024-11-03T06:00:00+00:00', '2024-11-03T06:02:00+00:00', False, -18000),
            ('2024-11-03T06:02:00+00:00', '2024-11-03T06:02:00+00:00', True, -18000),
        ])
        for missing in ('time', 'civil', 'legacy_input_hour'):
            with self.subTest(missing=missing):
                old = deepcopy(snapshot)
                if missing == 'time':
                    del old['time']
                elif missing == 'civil':
                    del old['time']['civil']
                else:
                    del old['input']['hour']
                original = deepcopy(old)
                self.assertEqual(life.analyze_snapshot(old, **options), intact)
                self.assertEqual(old, original)
        for key, value in (('instant_bj', '2024-11-03T13:00:00+08:00'),
                           ('iana_zone', 'America/Chicago'), ('fold', 0)):
            with self.subTest(conflict=key):
                old = deepcopy(snapshot)
                del old['time']['civil']
                old['time'][key] = value
                with self.assertRaisesRegex(ValueError, '已存出生瞬间、时区或 fold 与原出生输入不一致'):
                    life.analyze_snapshot(old, **options)
        incomplete = deepcopy(snapshot)
        del incomplete['time']
        del incomplete['input']['hour']
        with self.assertRaisesRegex(ValueError, '缺少原出生时分或可核的出生偏移'):
            life.analyze_snapshot(incomplete, **options)
        mismatch_zone = deepcopy(snapshot)
        del mismatch_zone['time']
        mismatch_zone['input']['timezone'] = 'America/Toronto'
        with self.assertRaisesRegex(ValueError, '保存的时区来源'):
            life.analyze_snapshot(mismatch_zone, **options)
        mismatch_kind = deepcopy(snapshot)
        mismatch_kind['provenance']['timezone_source'] = dict(kind='fixed_offset', tzif_sha256=None)
        with self.assertRaisesRegex(ValueError, '保存的时区来源'):
            life.analyze_snapshot(mismatch_kind, **options)

    def test_snapshot_accepts_resolved_solar_rollover_and_unpadded_civil_hour(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '2001-01-01',
               '--hour', '0:5', '--sex', '男', '--lat', '30', '--lon', '105',
               '--time-basis', 'mean-solar', '--analysis-year', '2026', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))
        self.assertTrue(snapshot['time']['civil'].startswith('2001-01-01'))
        self.assertTrue(snapshot['time']['chart_clock'].startswith('2000-12-31'))
        panel = self.panel(snapshot)
        self.assertEqual(panel['status'], 'conditional')
        self.assertEqual(panel['modules']['ZW-T02']['status'], 'conditional')
        self.assertEqual(panel['input_errors'], [])

        enumerated = json.loads(subprocess.check_output(
            [*cmd, '--enumerate-scenarios', '--uncertainty-minutes', '2'], cwd=ROOT, text=True, timeout=60))
        candidate = enumerated['ziwei_scenario_comparison']['candidates'][0]
        options = dict(ziwei_candidate_id=candidate['id'])
        intact = life.analyze_snapshot(enumerated, **options)
        self.assertEqual(intact['natal_solar_date'], '2000-12-31')
        self.assertEqual(intact['natal_civil_birth_year'], 2001)
        scope = intact['birth_scenario']
        self.assertEqual(scope['time_basis'], 'mean-solar')
        self.assertEqual(scope['reachable_utc_intervals'], enumerated['scenarios']['variants'][0]['intervals'])
        del enumerated['time']['civil']
        del enumerated['time']['mean_solar']
        self.assertEqual(life.analyze_snapshot(enumerated, **options), intact)
        enumerated['time']['chart_clock'] = '2001-01-01T00:05:00'
        with self.assertRaisesRegex(ValueError, 'time.chart_clock与原出生民用瞬间'):
            life.analyze_snapshot(enumerated, **options)

    def test_civil_year_can_differ_from_solar_clock_year_without_reconstruction(self):
        chart = self.charts[3]
        panel = life.analyze(chart, 2001, 2026)
        stages = panel['modules']['ZW-T02']['rows'][0]
        self.assertEqual(chart['birthInfo']['year'], 2000)
        self.assertEqual(stages['birth_year'], 2001)
        self.assertEqual(stages['current_age'], 26)
        self.assertEqual(stages['status'], 'conditional')
        self.assertEqual(life.analyze(chart, 2000, 2026)['modules']['ZW-T02']['status'], 'withheld')

    def test_health_has_only_life_reflection_without_condition_or_disease_output(self):
        panel = self.panel(dynamic=self.dynamic)
        health = next(r for r in panel['domains'] if r['domain']=='疾厄')
        self.assertEqual(health['health_scope'],'general_life_reflection_only')
        self.assertEqual(health['role'],'身体管理与劳逸安排的一般生活反思')
        disease_words = ('体质强','体质弱','器官薄弱','患病','疾病风险增加','健康不利','易生病','肝脏','肾脏','心脏')
        content = ' '.join([t['theme'] for t in health['major_topics']] + [r['topic'] or '' for r in panel['transformations'] if r['fact']['domain']=='疾厄'])
        self.assertFalse(any(word in content for word in disease_words))
        self.assertTrue(all(r['health_scope']=='general_life_reflection_only' for r in panel['transformations'] if r['fact']['domain']=='疾厄'))

    def test_legacy_civil_snapshot_checks_original_birth_without_saved_clocks(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1997-02-16',
               '--sex', '男', '--time-basis', 'civil', '--analysis-year', '2026', '--format', 'json']
        earlier, later = [json.loads(subprocess.check_output([*cmd, '--hour', hour], cwd=ROOT, text=True))
                          for hour in ('20:59', '21:00')]

        def health_stars(panel):
            health = next(row for row in panel['domains'] if row['domain'] == '疾厄')
            return [topic['star'] for topic in health['major_topics']]

        expected = self.panel(earlier)
        self.assertEqual(health_stars(expected), ['天府'])
        self.assertEqual(health_stars(self.panel(later)), ['廉贞', '天府'])
        earlier.pop('time')
        self.assertEqual(self.panel(earlier), expected)

        wrong_date = deepcopy(earlier)
        wrong_date['input']['solar'] = '1997-02-17'
        earlier['ziwei'] = later['ziwei']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.json'
            for snapshot, issue in ((earlier, '出生时辰冲突'), (wrong_date, '出生日期冲突')):
                with self.subTest(issue=issue):
                    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
                    result = subprocess.run([sys.executable, '-B', 'scripts/ziwei_life_reading.py',
                                             '--snapshot', str(path)], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    panel = json.loads(result.stdout)
                    self.assertEqual(panel['domains'], [])
                    self.assertIn(issue, panel['input_errors'][0])

    def test_exact_snapshot_replays_actual_star_placements_under_unchanged_birth_header(self):
        cmd = [sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-09-22',
               '--sex', '男', '--analysis-year', '2026', '--format', 'json']
        before, after = [json.loads(subprocess.check_output([*cmd, '--hour', hour], cwd=ROOT, text=True))
                         for hour in ('18:59', '19:00')]
        for saved, status in ((before, 'not_triggered'), (after, 'conditional')):
            panel = self.panel(saved)
            self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], status)
            self.assertEqual(panel['modules']['ZW-T02']['status'], 'conditional')
        legacy_header = deepcopy(before)
        legacy_header['ziwei']['chart']['birthInfo'] = None
        self.assertEqual(self.panel(legacy_header), self.panel(before))

        def current_tanlang(panel):
            current = next(row for row in panel['stage_relationship']['stages'] if row['legacy_stage']['current'])
            return current['modules']['ZW-ST08']['status']

        brightness = deepcopy(after)
        self.assertEqual(current_tanlang(self.panel(brightness)), 'conditional')
        tanlang = next(star for p in brightness['ziwei']['chart']['palaces'] for star in p['stars']
                       if star['name'] == '贪狼')
        self.assertEqual(tanlang['brightnessRaw'], '庙')
        tanlang['brightnessRaw'] = '陷'
        panel = self.panel(brightness)
        self.assertEqual(current_tanlang(panel), 'withheld')
        self.assertEqual(panel['modules']['ZW-T02']['status'], 'conditional')
        self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
        self.assertEqual(set(panel['natal_brightness_errors'].values()), {'保存的原始亮度与复盘不一致'})
        self.assertEqual(tanlang['brightnessRaw'], '陷')

        other = deepcopy(after['ziwei']['chart'])
        other['birthInfo'] = deepcopy(before['ziwei']['chart']['birthInfo'])
        before['ziwei']['chart'] = other
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                if legacy:
                    del before['time']
                panel = self.panel(before)
                self.assertEqual(panel['status'], 'withheld')
                self.assertIn('命身宫或实际星表不一致', panel['input_errors'][0])
                self.assertEqual(panel['domains'], [])
                self.assertEqual(panel['case_judgments']['modules']['ZW-RC02']['status'], 'withheld')
                self.assertEqual(panel['stage_relationship']['stage_status'], 'withheld')

    def test_source_gate_failure_withholds_new_panel_and_chart_builder_still_returns_native(self):
        with patch.object(life, '_table', side_effect=ValueError('registered source check failed')):
            panel = self.panel()
            self.assertEqual(panel['status'], 'withheld')
            self.assertEqual(panel['domains'], [])
            self.assertTrue(panel['source_errors'])
            output = io.StringIO()
            with redirect_stdout(output):
                build_chart.main(['--solar','1986-01-03','--hour','22:30','--sex','男','--lat','31.23','--lon','121.47',
                                  '--time-basis','civil','--analysis-year','2026','--format','json'])
            snapshot = json.loads(output.getvalue())
            self.assertEqual(snapshot['ziwei']['chart'], self.snapshot['ziwei']['chart'])
            self.assertEqual(snapshot['ziwei']['rule_output'], self.snapshot['ziwei']['rule_output'])
            self.assertEqual(snapshot['ziwei']['life_reading']['status'], 'withheld')

    def test_uncertainty_keeps_facts_and_withholds_conditional_topics(self):
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1986-01-03', '--hour', '22:30',
            '--sex', '男', '--lat', '31.23', '--lon', '121.47', '--time-basis', 'civil',
            '--analysis-year', '2026', '--uncertainty-minutes', '5', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        panel = self.panel(snapshot, self.dynamic)
        self.assertEqual(panel['status'],'withheld')
        self.assertEqual(panel['dynamic']['status'], 'admitted')
        self.assertEqual(len(panel['domains']),12)
        self.assertTrue(all(r['status']=='withheld' for r in panel['domains']))
        self.assertTrue(all(r['status'] in ('withheld','facts_only') for r in panel['transformations']))
        self.assertEqual(panel['modules']['ZW-E01']['status'],'withheld')
        self.assertEqual(snapshot['ziwei']['chart'], self.snapshot['ziwei']['chart'])

        conflicting = deepcopy(self.snapshot)
        conflicting['input']['uncertainty_minutes'] = 5
        rejected = self.panel(conflicting, self.dynamic)
        self.assertIn('出生时间精度不一致', rejected['birth_time_error'])
        self.assertEqual(rejected['dynamic']['birth_time_status'], 'birth_time_unverified')
        self.assertEqual(rejected['dynamic']['transformations'], [])

    def test_enumerated_birth_range_prevents_a_false_exact_center_in_an_old_snapshot(self):
        snapshot = json.loads(subprocess.check_output([
            sys.executable, '-B', 'scripts/build_chart.py', '--solar', '1987-09-04',
            '--hour', '00:59', '--sex', '女', '--utc-offset', '8', '--analysis-year', '2028',
            '--uncertainty-minutes', '5', '--enumerate-scenarios', '--format', 'json',
        ], cwd=ROOT, text=True, timeout=45))
        range_expected = dict(earliest_utc='1987-09-03T16:54:00+00:00',
                              latest_utc='1987-09-03T17:04:00+00:00')
        for change in ('original', 'native_marker_missing', 'minutes_missing', 'both_missing', 'false_zero',
                       'wrong_range'):
            with self.subTest(change=change):
                archive = deepcopy(snapshot)
                if change in ('native_marker_missing', 'both_missing'):
                    del archive['ziwei']['input']['temporalUncertainty']
                if change in ('minutes_missing', 'both_missing', 'wrong_range'):
                    del archive['input']['uncertainty_minutes']
                if change == 'false_zero':
                    archive['input']['uncertainty_minutes'] = 0
                    archive['ziwei']['input']['temporalUncertainty'] = False
                if change == 'wrong_range':
                    archive['scenarios']['end_utc'] = '1987-09-03T17:05:00+00:00'
                result = self.panel(archive)
                self.assertEqual(len(result['domains']), 12)
                self.assertTrue(result['temporal_uncertainty'])
                cases = result['case_judgments']['modules']
                self.assertEqual(cases['ZW-RC02']['status'], 'withheld')
                self.assertEqual(result['stage_relationship']['relationship']['status'], 'withheld')
                self.assertTrue(all(result['modules'][rule]['status'] == 'withheld'
                                    for rule in ('ZW-D02', 'ZW-D04', 'ZW-D07', 'ZW-T02')))
                if change in ('original', 'native_marker_missing'):
                    self.assertEqual(result['birth_time_bounds'], range_expected)
                    self.assertNotIn('birth_time_error', result)
                else:
                    self.assertNotIn('birth_time_bounds', result)
                    self.assertIn('出生误差', result['birth_time_error'])
                if change == 'both_missing':
                    with self.assertRaisesRegex(ValueError, '非零误差区间'):
                        life.analyze_snapshot(archive, ziwei_candidate_id='ziwei-candidate-1')
        for identifier, expected in (('ziwei-candidate-1', 'conditional'), ('ziwei-candidate-2', 'not_triggered')):
            result = life.analyze_snapshot(snapshot, ziwei_candidate_id=identifier)
            self.assertEqual(result['birth_scenario']['id'], identifier)
            self.assertEqual(result['case_judgments']['modules']['ZW-RC02']['status'], expected)

        exact = deepcopy(self.snapshot)
        del exact['input']['uncertainty_minutes']
        del exact['ziwei']['input']['temporalUncertainty']
        expected = self.panel()
        self.assertEqual(self.panel(exact), expected)
        exact['ziwei']['life_reading'] = snapshot['ziwei']['life_reading']
        exact['ziwei_scenario_comparison'] = snapshot['ziwei_scenario_comparison']
        self.assertEqual(self.panel(exact), expected)

    def test_missing_ziwei_preserves_builder_degradation_contract(self):
        output = io.StringIO()
        with patch.object(build_chart,'run_ziwei',return_value=(None,'紫微测试依赖缺失')), redirect_stdout(output):
            build_chart.main(['--solar','1986-01-03','--hour','22:30','--sex','男','--lat','31.23','--lon','121.47','--analysis-year','2026','--format','json'])
        snapshot=json.loads(output.getvalue())
        self.assertIsNone(snapshot['ziwei'])
        self.assertEqual(snapshot['degradation']['ziwei'],'紫微测试依赖缺失')
        panel=self.panel(snapshot)
        self.assertEqual(panel['status'],'withheld')
        self.assertEqual(panel['domains'],[])

    def test_malformed_lunar_info_is_local_and_malformed_degradation_is_format_error(self):
        snapshot = deepcopy(self.snapshot)
        snapshot['ziwei']['chart']['lunarInfo'] = []
        panel = self.panel(snapshot)
        self.assertEqual(panel['status'], 'partial')
        self.assertEqual(len(panel['domains']), 12)
        self.assertEqual(panel['transformations'], [])
        self.assertIn('lunarInfo', panel['input_errors'][0])
        with self.assertRaisesRegex(ValueError, 'degradation'):
            life.analyze_snapshot({'ziwei':None, 'degradation':[]})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            for data, expected_code in ((snapshot, 0), ({'ziwei':None,'degradation':[]}, 2)):
                path.write_text(json.dumps(data), encoding='utf-8')
                result = subprocess.run([sys.executable,'scripts/ziwei_life_reading.py','--snapshot',str(path)],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected_code)
                self.assertNotIn('Traceback', result.stderr)
                if expected_code == 0:
                    self.assertEqual(json.loads(result.stdout)['status'], 'partial')

    def test_expected_query_point_rejects_stale_cache_without_discarding_natal_facts(self):
        baseline = self.panel(dynamic=self.dynamic)
        self.assertEqual(baseline['dynamic']['status'], 'admitted')
        matching = life.analyze_snapshot(self.snapshot, self.dynamic,
                                         expected_target_date='2026-11-10', expected_target_time_index=12)
        self.assertNotIn('stage_query_scope', baseline)
        stage_scope = dict(status='verified', snapshot_analysis_year=2026, panel_analysis_year=2026,
                           requested_analysis_year=None, query_civil_year=2026, aligned_to_query=True)
        self.assertEqual(matching, dict(baseline, stage_query_scope=stage_scope))
        for requested_date, requested_index in [('2026-11-08', 12), ('2026-11-10', 0)]:
            with self.subTest(requested_date=requested_date, requested_index=requested_index):
                panel = life.analyze_snapshot(self.snapshot, self.dynamic,
                                              expected_target_date=requested_date, expected_target_time_index=requested_index)
                self.assertEqual(panel['status'], 'partial')
                self.assertEqual(panel['dynamic']['status'], 'withheld')
                self.assertEqual(panel['dynamic']['layers'], {})
                self.assertEqual(panel['dynamic']['transformations'], [])
                self.assertIn('实际为 2026-11-10（时辰索引 12）', panel['dynamic']['errors'][0])
                self.assertIn(f'预期为 {requested_date}（时辰索引 {requested_index}）', panel['dynamic']['errors'][0])
                self.assertEqual(panel['domains'], baseline['domains'])
                self.assertEqual(panel['modules']['ZW-T02'], baseline['modules']['ZW-T02'])
                self.assertEqual(panel['transformations'], [r for r in baseline['transformations'] if r['layer'] == 'natal'])
                self.assertEqual(panel['stage_query_scope'], stage_scope)
        other_year = life.analyze_snapshot(self.snapshot, self.dynamic, expected_target_date='2027-11-10',
                                            expected_target_time_index=12)
        self.assertEqual(other_year['stage_query_scope']['status'], 'analysis_year_mismatch')
        self.assertEqual(other_year['modules']['ZW-T02'], baseline['modules']['ZW-T02'])

    def test_expected_query_point_arguments_are_strictly_paired(self):
        for requested_date, requested_index, message in [
                ('2026-11-10', None, '成对'), (None, 0, '成对'),
                ('20261110', 0, 'YYYY-MM-DD'), ('2026-02-30', 0, 'YYYY-MM-DD'),
                ('2026-11-10', False, '0至12'), ('2026-11-10', 13, '0至12')]:
            with self.subTest(requested_date=requested_date, requested_index=requested_index):
                with self.assertRaisesRegex(ValueError, message):
                    life.analyze_snapshot(self.snapshot, self.dynamic,
                                          expected_target_date=requested_date, expected_target_time_index=requested_index)
        with self.assertRaisesRegex(ValueError, '完整动态输入'):
            life.analyze_snapshot(self.snapshot, expected_target_date='2026-11-10', expected_target_time_index=0)

    def test_malformed_dynamic_cannot_bypass_birth_order_for_requested_stage(self):
        natal = self.panel()
        before = life.analyze_snapshot(self.snapshot, {}, expected_target_date='1986-01-03',
                                       expected_target_time_index=11, requested_analysis_year=1986)
        self.assertEqual(before['dynamic']['status'], 'withheld')
        self.assertEqual(before['dynamic']['birth_time_status'], 'birth_time_unverified')
        self.assertEqual(before['stage_query_scope']['status'], 'birth_time_unverified')
        self.assertEqual(before['domains'], natal['domains'])
        self.assertEqual(before['modules']['ZW-T02'], natal['modules']['ZW-T02'])
        after = life.analyze_snapshot(self.snapshot, {}, expected_target_date='2026-11-10',
                                      expected_target_time_index=12, requested_analysis_year=2026)
        self.assertEqual(after['dynamic']['status'], 'withheld')
        self.assertEqual(after['stage_query_scope']['status'], 'verified')

    def test_cli_returns_the_same_panel_and_accepts_the_expected_query_point(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'chart.json'; path.write_text(json.dumps(self.snapshot),encoding='utf-8')
            dynamic_path=Path(directory)/'dynamic.json'; dynamic_path.write_text(json.dumps(self.dynamic),encoding='utf-8')
            cmd = [sys.executable, 'scripts/ziwei_life_reading.py', '--snapshot', str(path), '--dynamic', str(dynamic_path)]
            baseline = self.panel(dynamic=self.dynamic)
            automatic = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(automatic.stdout), baseline)
            point_args = ['--expected-target-date', '2026-11-10', '--expected-target-time-index', '12']
            confirmed = subprocess.run(cmd + point_args, cwd=ROOT, capture_output=True, text=True, check=True)
            scope = dict(status='verified', snapshot_analysis_year=2026, panel_analysis_year=2026,
                         requested_analysis_year=None, query_civil_year=2026, aligned_to_query=True)
            self.assertEqual(json.loads(confirmed.stdout), dict(baseline, stage_query_scope=scope))
            mismatch = subprocess.run(cmd + ['--expected-target-date', '2026-11-08', '--expected-target-time-index', '12'],
                                      cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(mismatch.stdout)['dynamic']['status'], 'withheld')
            incomplete = subprocess.run(cmd + ['--expected-target-date', '2026-11-10'],
                                        cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(incomplete.returncode, 2)
            self.assertIn('成对', incomplete.stderr)


if __name__=='__main__':
    unittest.main()
