"""Approved stage and spouse cases exercised through synthetic native charts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'scripts/pai_pan_ziwei'
sys.path.insert(0, str(ROOT / 'scripts'))
import ziwei_life_reading as life
import ziwei_stage_relationship as models


@unittest.skipUnless((ENGINE / 'node_modules/tsx').exists(), 'npm ci required')
class ZiweiStageRelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panels = {}
        cls.charts = {}
        # Artificial witness inputs selected for coverage, not personal records.
        for key, solar, branch, sex, year in (
                ('F1', '1980-01-01', '子', '男', 2022),
                ('S1', '1981-02-05', '寅', '女', 2016),
                ('S2', '1984-02-07', '戌', '女', 2027),
                ('M1', '1981-02-06', '申', '男', 2035),
                ('M2', '1980-02-22', '卯', '男', 2045),
                ('WQ', '1980-02-16', '子', '男', 1984),
                ('WQ-exit', '1980-01-01', '未', '男', 2022),
                ('TX-positive', '1980-06-25', '子', '男', 2042),
                ('TX-negative', '1982-02-04', '巳', '男', 2016),
                ('TL-positive', '1980-02-25', '亥', '男', 2014),
                ('TL-exit', '1980-04-30', '戌', '男', 2042),
                ('TT-zi', '1983-02-20', '子', '男', 2005),
                ('TT-hai', '1981-02-05', '亥', '男', 2026),
                ('TT-wu', '1980-01-17', '卯', '男', 2020),
                ('TW-positive', '1980-02-16', '戌', '男', 2022),
                ('TW-next', '1980-02-16', '戌', '男', 2023),
                ('TW-fall', '1980-01-02', '丑', '男', 2049),
                ('PJ-positive', '1980-02-17', '巳', '男', 2020),
                ('PJ-next', '1980-02-17', '巳', '男', 2021),
                ('PJ-bell', '1980-01-01', '子', '男', 2050),
                ('PJ-fall', '1980-02-19', '未', '男', 2006),
                ('RL', '1980-06-14', '申', '男', 2026),
                ('RL-fire', '1980-04-16', '午', '男', 2026),
                ('RL-kong-jie', '1980-03-18', '巳', '男', 2026)):
            cmd = ['node_modules/.bin/tsx', 'pai_pan.ts', '--solar', solar, '--shichen', branch,
                   '--sex', sex, '--age-year', str(year), '--format', 'json']
            native = json.loads(subprocess.run(cmd, cwd=ENGINE, capture_output=True, text=True, check=True).stdout)
            cls.charts[key] = native['chart']
            cls.panels[key] = life.analyze(native['chart'], int(solar[:4]), year)

    def evaluate(self, key):
        return models.evaluate(self.panels[key], natal_year_stem=self.charts[key]['lunarInfo']['yearStem'])

    def current(self, result):
        return next(stage for stage in result['stages'] if stage['legacy_stage']['current'])

    def module(self, key, rule):
        return self.current(self.evaluate(key))['modules'][rule]

    def reread(self, chart):
        birth_year = chart['birthInfo']['year']
        return life.analyze(chart, birth_year, birth_year + chart['currentAge'] - 1)['stage_relationship']

    @staticmethod
    def context_with_malefics_outside(branch):
        return dict(surrounding=[dict(branch=(branch + step) % 12) for step in (0, 4, 6, 8)],
                    verified_malefic_positions={name: (branch + 1) % 12 for name in models.SIX_MALEFICS})

    def build(self, hour, *flags, solar='1980-06-14', basis='civil', year=2026):
        cmd = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
               '--solar', solar, '--hour', hour, '--sex', '男', '--lat', '30', '--lon', '120',
               '--time-basis', basis, '--analysis-year', str(year), '--format', 'json', *flags]
        return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)

    def test_snapshot_retains_single_candidate_and_opposite_sides_of_shichen_boundary(self):
        for hour, minutes, shichen, relationship in (
                ('16:30', '5', [8], ['conditional']),
                ('17:00', '1', [8, 9], ['conditional', 'not_triggered'])):
            with self.subTest(hour=hour):
                snapshot = self.build(hour, '--enumerate-scenarios', '--uncertainty-minutes', minutes)
                self.assertEqual(snapshot['ziwei']['life_reading']['stage_relationship']['status'], 'withheld')
                comparison = snapshot['ziwei_scenario_comparison']
                self.assertEqual(comparison['analysis_year'], snapshot['provenance']['resolved_age_year'])
                self.assertEqual(comparison['coverage'], 'complete_for_modeled_boundaries_not_astronomical_error')
                candidates = comparison['candidates']
                self.assertEqual([row['chart']['birthInfo']['hour'] for row in candidates], shichen)
                self.assertEqual([row['stage_relationship']['relationship']['status'] for row in candidates],
                                 relationship)
                self.assertEqual(candidates[0]['chart'], self.charts['RL'])
                self.assertEqual(candidates[0]['stage_relationship'], self.panels['RL']['stage_relationship'])
                if len(candidates) == 2:
                    stages = [{stage['legacy_stage']['window']['start_inclusive']
                               for stage in row['stage_relationship']['stages']
                               if stage['modules']['ZW-ST01']['fact_match']} for row in candidates]
                    self.assertEqual(stages, [{'2054-01-01'}, {'2031-01-01'}])

    def test_snapshot_deduplicates_bazi_only_changes_without_affecting_zero_uncertainty(self):
        # The winter jie changes a BaZi pillar while Ziwei remains within one input.
        args = ('23:28', '--enumerate-scenarios')
        snapshot = self.build(*args, '--uncertainty-minutes', '2', solar='1986-01-05')
        self.assertEqual(len(snapshot['scenarios']['variants']), 2)
        candidates = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['scenario_ids'], ['candidate-1', 'candidate-2'])
        self.assertIsNone(candidates[0]['degradation'])
        self.assertNotIn('ziwei_scenario_comparison', self.build(*args, solar='1986-01-05'))

    def test_snapshot_numeric_solar_witnesses_remain_nonexhaustive(self):
        snapshot = self.build('17:00', '--enumerate-scenarios', '--uncertainty-minutes', '5',
                              basis='apparent-solar')
        comparison = snapshot['ziwei_scenario_comparison']
        self.assertEqual(comparison['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertFalse(snapshot['scenarios']['stable_fields'])
        self.assertEqual([row['chart']['birthInfo']['hour'] for row in comparison['candidates']], [8, 9])

    def test_snapshot_keeps_valid_witness_when_other_birth_year_exceeds_analysis_year(self):
        snapshot = self.build('23:59', '--enumerate-scenarios', '--uncertainty-minutes', '2',
                              solar='1986-12-31', year=1986)
        early, late = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(early['input']['birth_year'], 1986)
        self.assertIsNotNone(early['stage_relationship'])
        self.assertIsNone(early['degradation'])
        self.assertEqual(late['input']['birth_year'], 1987)
        self.assertIsNone(late['chart'])
        self.assertIsNone(late['stage_relationship'])
        self.assertIn('该年无当前大限', late['degradation'])
        self.assertIn('--analysis-year 1987', late['degradation'])

    def test_native_stage_branches_keep_separate_objects_and_their_counterconditions(self):
        for key, rule, branch in (
                ('F1', 'ZW-ST01', 'tianfu_progress'),
                ('S1', 'ZW-ST02', 'taiyang_mao_support'),
                ('S2', 'ZW-ST02', 'taiyang_zi_fire_ji'),
                ('M1', 'ZW-ST03', 'taiyin_chou_support'),
                ('WQ', 'ZW-ST04', 'wuqu_quan_progress'),
                ('TX-positive', 'ZW-ST05', 'tianxiang_pursuit'),
                ('TX-negative', 'ZW-ST05', 'tianxiang_yang_restriction'),
                ('TL-positive', 'ZW-ST06', 'tianliang_progress'),
                ('TT-zi', 'ZW-ST07', 'tiantong_zi_progress'),
                ('TT-hai', 'ZW-ST07', 'tiantong_hai_progress'),
                ('TT-wu', 'ZW-ST07', 'tiantong_wu_opposite_fire')):
            with self.subTest(key=key, rule=rule):
                row = self.module(key, rule)
                self.assertEqual(row['status'], 'conditional')
                self.assertTrue(row['fact_match'])
                self.assertEqual(row['selected_branch'], branch)
                self.assertEqual([item['key'] for item in row['direction_branches']], [branch])
                self.assertTrue(row['direction_branches'][0]['counterconditions'])
                self.assertTrue(row['actual_major_facts'])
                self.assertEqual(row['overall_direction'], 'withheld')
        self.assertEqual(self.module('WQ', 'ZW-ST04')['actual_major_facts'][0]['brightness_raw'], '得')
        self.assertIsNone(self.module('TL-positive', 'ZW-ST06')['actual_major_facts'][0]['natal_transform'])

    def test_observed_taiyin_counter_remains_facts_only_and_other_exits_are_unsigned(self):
        observation = self.module('M2', 'ZW-ST03')
        self.assertEqual(observation['status'], 'facts_only')
        self.assertIsNone(observation['selected_branch'])
        self.assertEqual(observation['direction_branches'], [])
        self.assertEqual([item['key'] for item in observation['counter_observations']], ['taiyin_si_counter'])
        for key, rule in (('WQ-exit', 'ZW-ST04'), ('TL-exit', 'ZW-ST06')):
            row = self.module(key, rule)
            self.assertEqual(row['status'], 'not_triggered')
            self.assertFalse(row['fact_match'])
            self.assertEqual(row['direction_branches'], [])

    def test_tanlang_and_pojun_preserve_distinct_positive_objects_and_alternates(self):
        for key, rule, branch, start, end, fact, modifiers, alternate_words in (
                ('TW-positive', 'ZW-ST08', 'tanlang_coordination', '2013', '2023', '贪狼',
                 {'陀罗', '地空'}, ('科', '权')),
                ('PJ-positive', 'ZW-ST09', 'pojun_resource_support', '2011', '2021', '破军',
                 {'地空', '地劫'}, ('文昌', '魁钺'))):
            with self.subTest(rule=rule):
                result = self.evaluate(key)
                stage = self.current(result)
                row = stage['modules'][rule]
                self.assertEqual(stage['legacy_stage']['window'], {
                    'start_inclusive': start + '-01-01', 'end_exclusive': end + '-01-01'})
                self.assertEqual(row['status'], 'conditional')
                self.assertEqual(row['selected_branch'], branch)
                self.assertEqual([(s['name'], s['brightness_raw']) for s in row['actual_major_facts']],
                                 [(fact, '庙')])
                self.assertEqual({s['name'] for s in stage['context']['selected_malefic_facts']}, modifiers)
                direction, = row['direction_branches']
                for word in alternate_words:
                    self.assertIn(word, ' '.join(direction['counterconditions']))
                self.assertEqual(stage['overall_direction'], 'withheld')
                self.assertEqual(result['overall_direction'], 'withheld')

    def test_tanlang_and_pojun_scope_exits_stay_unsigned(self):
        for key, rule in (
                ('TW-next', 'ZW-ST08'), ('TW-fall', 'ZW-ST08'),
                ('PJ-next', 'ZW-ST09'), ('PJ-fall', 'ZW-ST09'), ('PJ-bell', 'ZW-ST09')):
            with self.subTest(key=key):
                row = self.module(key, rule)
                self.assertEqual(row['status'], 'not_triggered')
                self.assertFalse(row['fact_match'])
                self.assertEqual(row['direction_branches'], [])
                self.assertEqual(row['counter_observations'], [])
        bell = self.current(self.evaluate('PJ-bell'))
        row = bell['modules']['ZW-ST09']
        self.assertEqual([(s['name'], s['branch']) for s in bell['context']['selected_malefic_facts']],
                         [('铃星', 10)])
        self.assertEqual(row['checks']['pojun_resource_support'], {
            'compatible_actual_pojun_raw_temple': True, 'clear_four': False})

    def test_tanlang_and_pojun_require_only_approved_positions_with_raw_temple(self):
        cards = self.evaluate('TW-positive')['cards']
        natal = {'忌': {'fact': {'branch': 1}}, '权': {'fact': {'branch': 1}}}
        for rule, name, compatible in (
                ('ZW-ST08', '贪狼', (1, 4, 7, 10)), ('ZW-ST09', '破军', (0, 6))):
            for branch in range(12):
                for raw in ('庙', '旺'):
                    with self.subTest(rule=rule, branch=branch, brightness=raw):
                        anchor = {'branch': branch, 'facts': [
                            dict(name=name, type='major', brightness_raw=raw)]}
                        context = self.context_with_malefics_outside(branch)
                        row = models._stage_modules(anchor, context, natal, cards, None)[rule]
                        self.assertEqual(row['fact_match'], raw == '庙' and branch in compatible)

    def test_tiantong_negative_requires_actual_opposition_and_not_other_four_square_placements(self):
        panel = deepcopy(self.panels['TT-wu'])
        domains = {row['branch']: row for row in panel['domains']}
        fire = next(fact for fact in domains[0]['facts'] if fact['name'] == '火星')
        domains[0]['facts'].remove(fire)
        for other in (6, 10, 2):
            domains[other]['facts'].append(dict(fire, branch=other))
            result = self.current(models.evaluate(panel))['modules']['ZW-ST07']
            self.assertEqual(result['status'], 'not_triggered')
            self.assertFalse(result['checks']['tiantong_wu_opposite_fire']['opposite_fire'])
            domains[other]['facts'].pop()

    def test_compatibility_gates_keep_tianliang_eight_verified_positions_only(self):
        anchor = {'branch': 0, 'facts': [dict(name='天梁', type='major', brightness_raw='庙')]}
        natal = {'忌': {'fact': {'branch': 1}}, '权': {'fact': {'branch': 1}}}
        cards = self.evaluate('TL-positive')['cards']
        native_brightness = '庙旺庙庙庙陷庙旺陷得庙陷'
        for branch, raw in enumerate(native_brightness):
            anchor['branch'] = branch
            anchor['facts'][0]['brightness_raw'] = raw
            context = self.context_with_malefics_outside(branch)
            row = models._stage_modules(anchor, context, natal, cards, None)['ZW-ST06']
            with self.subTest(branch=branch, raw=raw):
                self.assertEqual(row['fact_match'], branch in (0, 2, 3, 4, 6, 8, 9, 10))

    def test_compatible_natal_role_requires_both_verified_stem_and_exact_attachment(self):
        for key, rule, expected_check in (('S2', 'ZW-ST02', 'compatible_natal_jia'),
                                          ('WQ', 'ZW-ST04', 'compatible_natal_geng')):
            with self.subTest(rule=rule):
                branch = self.module(key, rule)['selected_branch']
                for unavailable_stem in (None, False, 1):
                    result = models.evaluate(self.panels[key], natal_year_stem=unavailable_stem)
                    row = self.current(result)['modules'][rule]
                    if type(unavailable_stem) is int:
                        self.assertIs(row['checks'][branch][expected_check], False)
                        self.assertEqual(row['status'], 'not_triggered')
                    else:
                        self.assertIsNone(row['checks'][branch][expected_check])
                        self.assertEqual(row['status'], 'withheld')

    def test_relationship_matches_static_six_star_scope_without_current_spouse_stage(self):
        result = self.evaluate('RL')
        relationship = result['relationship']
        self.assertEqual(self.current(result)['legacy_stage']['domain'], '官禄')
        self.assertEqual(relationship['status'], 'conditional')
        self.assertEqual(relationship['selected_branch'], 'sun_giant_gate_stability')
        self.assertEqual({fact['name'] for fact in relationship['actual_major_facts']}, {'太阳', '巨门'})
        self.assertEqual(relationship['context']['selected_malefic_facts'], [])
        for key, counter in (('RL-fire', '火星'), ('RL-kong-jie', '地劫')):
            with self.subTest(key=key):
                row = self.evaluate(key)['relationship']
                self.assertTrue(row['checks']['sun_giant_gate_stability']['sun_and_giant_gate_actual_copresence'])
                self.assertEqual(row['status'], 'not_triggered')
                self.assertIn(counter, {fact['name'] for fact in row['context']['selected_malefic_facts']})
                self.assertEqual(row['direction_branches'], [])

    def test_t02_must_be_valid_but_does_not_gate_static_relationship(self):
        panel = deepcopy(self.panels['RL'])
        panel['modules']['ZW-T02']['status'] = 'withheld'
        result = models.evaluate(panel)
        self.assertEqual(result['stage_status'], 'withheld')
        self.assertTrue(result['stage_errors'])
        self.assertEqual(result['stages'], [])
        self.assertEqual(result['relationship']['status'], 'conditional')

    def test_unrelated_natal_transform_error_preserves_stage_and_relationship_results(self):
        for solar, hour, year, rule, expected in (
                ('1980-06-14', '16:00', 2026, 'relationship', 'sun_giant_gate_stability'),
                ('1980-04-16', '12:00', 2026, 'relationship', None),
                ('1980-01-01', '00:00', 2022, 'ZW-ST01', 'tianfu_progress'),
                ('1980-01-01', '00:00', 2031, 'ZW-ST01', None)):
            with self.subTest(solar=solar, year=year, rule=rule):
                snapshot = self.build(hour, solar=solar, year=year)
                original = snapshot['ziwei']['life_reading']['stage_relationship']
                chart = snapshot['ziwei']['chart']
                ke = next(star for palace in chart['palaces'] for star in palace['stars'] if star.get('siHua') == '科')
                ke['siHua'] = None
                reread = life.analyze_snapshot(snapshot)
                partial = reread['stage_relationship']
                self.assertIn(partial['natal_transform_error'], reread['input_errors'])
                self.assertEqual({row['kind'] for row in reread['transformations']}, {'禄', '权', '忌'})
                for result in (original, partial):
                    row = result[rule] if rule == 'relationship' else self.current(result)['modules'][rule]
                    self.assertEqual(row['selected_branch'], expected)
                    self.assertEqual(row['status'], 'conditional' if expected else 'not_triggered')
                self.assertEqual(self.current(partial)['legacy_stage'], self.current(original)['legacy_stage'])
                chart['birthInfo']['hour'] = None
                self.assertEqual(life.analyze_snapshot(snapshot)['stage_relationship'], partial)

                del snapshot['input']['hour']
                del snapshot['time']
                del snapshot['ziwei']['input']['shichenIndex']
                no_birth_clock = life.analyze_snapshot(snapshot)
                self.assertTrue(any('缺少可复盘的原出生钟面' in error for error in no_birth_clock['input_errors']))
                unverified_birth = no_birth_clock['stage_relationship']
                self.assertEqual(unverified_birth['status'], 'withheld')
                self.assertEqual(unverified_birth['stages'], [])

    def test_missing_transforms_hold_only_the_branch_that_needs_that_kind(self):
        for key, rule, kind, check in (
                ('S1', 'ZW-ST02', '忌', 'no_natal_ji_in_seat'),
                ('S2', 'ZW-ST02', '忌', 'natal_taiyang_ji'),
                ('M1', 'ZW-ST03', '忌', 'no_natal_ji_in_seat'),
                ('WQ', 'ZW-ST04', '权', 'natal_wuqu_quan'),
                ('M2', 'ZW-ST03', '忌', None)):
            with self.subTest(key=key, rule=rule):
                chart = deepcopy(self.charts[key])
                transforms = {star['siHua']: star for palace in chart['palaces'] for star in palace['stars']
                              if star.get('siHua')}
                baseline = self.module(key, rule)
                transforms['科']['siHua'] = None
                row = self.current(self.reread(chart))['modules'][rule]
                self.assertEqual(row['status'], baseline['status'])
                self.assertEqual(row['selected_branch'], baseline['selected_branch'])
                self.assertEqual(row['direction_branches'], baseline['direction_branches'])
                transforms[kind]['siHua'] = None
                row = self.current(self.reread(chart))['modules'][rule]
                if check is None:
                    self.assertEqual(row['status'], 'facts_only')
                    self.assertEqual([r['key'] for r in row['counter_observations']], ['taiyin_si_counter'])
                    continue
                self.assertEqual(row['status'], 'withheld')
                self.assertIsNone(row['fact_match'])
                self.assertIsNone(row['checks'][baseline['selected_branch']][check])
                self.assertFalse(row['direction_branches'])

    def test_missing_or_legacy_brightness_withholds_only_compatible_geometry(self):
        for key, rule, star_name in (
                ('S1', 'ZW-ST02', '太阳'), ('M1', 'ZW-ST03', '太阴'), ('M2', 'ZW-ST03', '太阴'),
                ('WQ', 'ZW-ST04', '武曲'), ('TX-positive', 'ZW-ST05', '天相'),
                ('TL-positive', 'ZW-ST06', '天梁'), ('TT-zi', 'ZW-ST07', '天同'),
                ('TW-positive', 'ZW-ST08', '贪狼'), ('PJ-positive', 'ZW-ST09', '破军'),
                ('PJ-bell', 'ZW-ST09', '破军'), ('F1', 'ZW-ST01', '天府')):
            with self.subTest(key=key, rule=rule):
                chart = deepcopy(self.charts[key])
                star = next(star for palace in chart['palaces'] for star in palace['stars']
                            if star['name'] == star_name and star['type'] == 'major')
                for raw in (None, 'bright'):
                    star['brightnessRaw'] = raw
                    row = self.current(self.reread(chart))['modules'][rule]
                    if key in ('F1', 'PJ-bell'):
                        self.assertEqual(row['status'], self.module(key, rule)['status'])
                    else:
                        self.assertEqual(row['status'], 'withheld')
                        self.assertIsNone(row['fact_match'])
                        self.assertIn('所需实坐主星原始亮度未核', row['reasons'])
                        self.assertFalse(row['direction_branches'])
                        self.assertFalse(row['counter_observations'])

    def test_missing_or_duplicate_malefic_cannot_make_a_false_stage_positive(self):
        baseline = self.evaluate('PJ-bell')
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                chart = deepcopy(self.charts['PJ-bell'])
                palace = next(palace for palace in chart['palaces']
                              if any(star['name'] == '铃星' for star in palace['stars']))
                bell = next(star for star in palace['stars'] if star['name'] == '铃星')
                if duplicate:
                    palace['stars'].append(deepcopy(bell))
                else:
                    palace['stars'].remove(bell)
                result = self.reread(chart)
                current = self.current(result)
                module = current['modules']['ZW-ST09']
                self.assertEqual(module['status'], 'withheld')
                self.assertIsNone(module['checks']['pojun_resource_support']['clear_four'])
                self.assertFalse(module['direction_branches'])
                self.assertIsNone(current['context']['verified_malefic_positions']['铃星'])
                self.assertEqual([stage['modules']['ZW-ST01']['status'] for stage in result['stages']],
                                 [stage['modules']['ZW-ST01']['status'] for stage in baseline['stages']])
        chart = deepcopy(self.charts['PJ-positive'])
        for palace in chart['palaces']:
            palace['stars'] = [star for star in palace['stars'] if star['name'] != '地劫']
        self.assertEqual(self.current(self.reread(chart))['modules']['ZW-ST09']['status'], 'conditional')

    def test_known_malefic_exit_stays_false_and_partial_absence_cannot_certify_relationship(self):
        chart = deepcopy(self.charts['RL-fire'])
        for removed, expected in (('火星', 'not_triggered'), ('铃星', 'withheld')):
            for palace in chart['palaces']:
                palace['stars'] = [star for star in palace['stars'] if star['name'] != removed]
            with self.subTest(removed=removed):
                row = self.reread(chart)['relationship']
                self.assertEqual(row['status'], expected)
                clear = row['checks']['sun_giant_gate_stability']['clear_six']
                self.assertIs(clear, False if expected == 'not_triggered' else None)
                self.assertFalse(row['direction_branches'])

    def test_single_position_malefic_predicate_needs_only_that_star(self):
        chart = deepcopy(self.charts['S2'])
        for removed, expected in (('擎羊', 'conditional'), ('火星', 'withheld')):
            for palace in chart['palaces']:
                palace['stars'] = [star for star in palace['stars'] if star['name'] != removed]
            with self.subTest(removed=removed):
                row = self.current(self.reread(chart))['modules']['ZW-ST02']
                self.assertEqual(row['status'], expected)
                self.assertIs(row['checks']['taiyang_zi_fire_ji']['same_palace_fire'],
                              True if expected == 'conditional' else None)

    def test_original_windows_and_actual_facts_are_preserved_and_dynamic_is_unread(self):
        class Unreadable:
            def __deepcopy__(self, memo):
                raise AssertionError('dynamic facts read')

            def get(self, key, default=None):
                raise AssertionError('dynamic facts read')

        panel = deepcopy(self.panels['F1'])
        prior = deepcopy(panel)
        panel['dynamic'] = Unreadable()
        result = models.evaluate(panel)
        stages = [stage['legacy_stage'] for stage in result['stages']]
        self.assertEqual(stages, prior['modules']['ZW-T02']['rows'][0]['rows'])
        self.assertEqual(result['stage_contract']['current_index'], self.charts['F1']['currentDaXianIndex'])
        current = self.current(result)
        self.assertEqual(current['legacy_stage']['window'], {'start_inclusive': '2021-01-01', 'end_exclusive': '2031-01-01'})
        self.assertFalse(result['full_interval_coverage'])
        self.assertEqual(result['overall_direction'], 'withheld')
        current['modules']['ZW-ST01']['actual_major_facts'][0]['brightness_raw'] = 'changed'
        self.assertEqual(panel['domains'], prior['domains'])
        self.assertEqual(panel['modules'], prior['modules'])

    def test_invalid_source_or_uncertain_birth_withholds_personal_use(self):
        panel = deepcopy(self.panels['RL'])
        panel['temporal_uncertainty'] = True
        result = models.evaluate(panel)
        self.assertEqual(result['status'], 'withheld')
        self.assertTrue(result['input_errors'])
        self.assertEqual(result['relationship']['direction_branches'], [])
        with patch.object(models, '_load_cards', side_effect=ValueError('source hash mismatch')):
            result = models.evaluate(self.panels['RL'])
        self.assertEqual(result['status'], 'withheld')
        self.assertEqual(result['source_errors'], ['source hash mismatch'])


if __name__ == '__main__':
    unittest.main()
