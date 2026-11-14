"""Check raw native chart reuse from an independently confirmed civil shichen."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ziwei_life_reading import analyze_native_shichen


@unittest.skipUnless(shutil.which('node') and (ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(),
                     'Node and locked Ziwei dependencies required')
class ZiweiNativeShichenTests(unittest.TestCase):
    def native(self, flag, value, year=2026, *, day='1987-09-04'):
        command = ['node', '--import', 'tsx', 'pai_pan.ts', '--solar', day, flag, value,
                   '--sex', '男', '--age-year', str(year), '--format', 'json']
        return json.loads(subprocess.check_output(command, cwd=ROOT / 'scripts/pai_pan_ziwei',
                                                  text=True, timeout=45))

    def dynamic(self, index, day, *, birth_day='1987-09-04'):
        command = ['node', 'scripts/ziwei_dynamic_facts.mjs', '--solar', birth_day, '--birth-year', birth_day[:4],
                   '--shichen-index', str(index), '--sex', '男', '--target-date', day, '--target-time-index', '0',
                   '--source-label', 'synthetic-verified-native-shichen']
        return json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))

    def test_known_zi_replays_disjoint_civil_intervals_without_inventing_utc(self):
        raw = self.native('--shichen', '子')
        self.assertEqual(raw['chart'], self.native('--hour', '00:30')['chart'])
        self.assertEqual(raw['chart'], self.native('--hour', '23:30')['chart'])
        known = analyze_native_shichen(raw, '1987-09-04', '子', '男', zone='Asia/Shanghai')
        unknown = analyze_native_shichen(raw, '1987-09-04', '子', '男')
        born = known['birth_scenario']
        self.assertFalse(born['birth_time_confirmed'])
        self.assertEqual(born['clock_intervals'], [
            {'start_inclusive': '00:00', 'end_exclusive': '01:00'},
            {'start_inclusive': '23:00', 'end_exclusive': '24:00'}])
        self.assertEqual([s['start_inclusive'] for s in born['civil_spans']],
                         ['1987-09-04T00:00:00+09:00', '1987-09-04T23:00:00+09:00'])
        self.assertIsNone(unknown['birth_scenario']['civil_spans'])
        self.assertIsNone(unknown['birth_scenario']['timezone_source'])
        self.assertEqual(unknown['domains'], known['domains'])
        self.assertEqual(known['case_judgments']['modules']['ZW-RC02']['selected_branch'], 'tiantong_absent')

    def test_raw_cache_swap_and_dynamic_query_are_independently_checked(self):
        zi, chou = self.native('--shichen', '子'), self.native('--shichen', '丑')
        facts = self.dynamic(0, '2026-07-01')
        wrong_candidate = self.dynamic(1, '2026-07-01')
        query = dict(expected_target_date='2026-07-01', expected_target_time_index=0)
        valid = analyze_native_shichen(zi, '1987-09-04', '子', '男', facts, **query)
        self.assertEqual(valid['dynamic']['status'], 'admitted')
        rejected = analyze_native_shichen(zi, '1987-09-04', '子', '男', wrong_candidate, **query)
        self.assertEqual(rejected['dynamic']['status'], 'withheld')
        self.assertEqual(rejected['domains'], valid['domains'])
        self.assertEqual(rejected['stage_relationship'], valid['stage_relationship'])
        stale = analyze_native_shichen(zi, '1987-09-04', '子', '男', facts,
                                       **dict(query, expected_target_date='2026-07-02'))
        self.assertEqual(stale['dynamic']['status'], 'withheld')
        self.assertEqual(stale['domains'], valid['domains'])
        with self.assertRaisesRegex(ValueError, '预期日期与时辰索引'):
            analyze_native_shichen(zi, '1987-09-04', '子', '男', facts)
        swap = deepcopy(zi)
        swap['chart'] = deepcopy(chou['chart'])
        with self.assertRaisesRegex(ValueError, '与已确认民用时辰复盘不一致'):
            analyze_native_shichen(swap, '1987-09-04', '子', '男', wrong_candidate, **query)
        with self.assertRaisesRegex(ValueError, '与独立确认'):
            analyze_native_shichen(chou, '1987-09-04', '子', '男')

    def test_raw_shichen_cli_refreshes_requested_year_and_keeps_native_scope(self):
        raw = self.native('--shichen', '子')
        genuine = analyze_native_shichen(self.native('--shichen', '子', 2032), '1987-09-04', '子', '男')
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'raw-native.json'
            snapshot.write_text(json.dumps(raw), encoding='utf-8')
            command = [sys.executable, '-B', 'scripts/ziwei_life_reading.py', '--snapshot', str(snapshot),
                       '--native-shichen', '子', '--birth-date', '1987-09-04', '--sex', '男',
                       '--analysis-year', '2032']
            panel = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=45))
        self.assertEqual(panel['stage_query_scope']['status'], 'verified')
        self.assertEqual(panel['stage_query_scope']['panel_analysis_year'], 2032)
        self.assertEqual({key: value for key, value in panel.items() if key != 'stage_query_scope'}, genuine)

    def test_verified_shichen_recovers_missing_redundant_hour_for_reading(self):
        birth_day, target_day = '1967-06-17', '2031-11-12'
        raw = self.native('--shichen', '寅', day=birth_day)
        dynamic = self.dynamic(2, target_day, birth_day=birth_day)
        query = dict(expected_target_date=target_day, expected_target_time_index=0,
                     requested_analysis_year=2031)
        baseline = analyze_native_shichen(raw, birth_day, '寅', '男', dynamic, **query)
        self.assertEqual(baseline['stage_query_scope']['status'], 'verified')
        self.assertEqual(baseline['stage_relationship']['relationship']['selected_branch'],
                         'sun_giant_gate_stability')
        self.assertEqual(baseline['case_judgments']['modules']['ZW-RC02']['status'], 'conditional')
        self.assertEqual({name: layer['status'] for name, layer in baseline['dynamic']['layers'].items()},
                         {'yearly': 'admitted', 'monthly': 'admitted'})

        old = deepcopy(raw)
        del old['chart']['birthInfo']['hour']
        actual = analyze_native_shichen(old, birth_day, '寅', '男', dynamic, **query)
        baseline['dynamic']['unverified_static_fields'] = ['chart.birthInfo.hour']
        self.assertEqual(actual, baseline)
        self.assertNotIn('hour', old['chart']['birthInfo'])

        old['chart']['birthInfo']['hour'] = 3
        with self.assertRaisesRegex(ValueError, '原盘出生标头.*不一致'):
            analyze_native_shichen(old, birth_day, '寅', '男', dynamic, **query)

    def test_zone_gap_retains_only_the_reachable_part_of_same_date_zi(self):
        native = self.native('--shichen', '子', day='2018-11-04')
        panel = analyze_native_shichen(native, '2018-11-04', '子', '男', zone='America/Sao_Paulo')
        spans = panel['birth_scenario']['civil_spans']
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]['start_inclusive'], '2018-11-04T23:00:00-02:00')
        skipped = self.native('--shichen', '子', day='2011-12-30')
        with self.assertRaisesRegex(ValueError, '无可达出生时刻'):
            analyze_native_shichen(skipped, '2011-12-30', '子', '男', zone='Pacific/Apia')

    def test_known_shichen_keeps_independent_facts_on_local_conflicts(self):
        native = self.native('--shichen', '子')
        original = analyze_native_shichen(native, '1987-09-04', '子', '男')
        altered = deepcopy(native)
        spouse = next(row for row in altered['chart']['palaces'] if row['name'] == '夫妻')
        star = next(item for item in spouse['stars'] if item['name'] == '巨门')
        star['brightnessRaw'] = '庙' if star['brightnessRaw'] != '庙' else '陷'
        brightness = analyze_native_shichen(altered, '1987-09-04', '子', '男')
        self.assertEqual(len(brightness['domains']), 12)
        self.assertTrue(brightness['natal_brightness_errors'])
        self.assertEqual(brightness['case_judgments']['modules']['ZW-RC02']['status'], 'withheld')
        self.assertEqual(brightness['modules']['ZW-T02'], original['modules']['ZW-T02'])
        altered = deepcopy(native)
        altered['chart']['currentAge'] += 1
        stage = analyze_native_shichen(altered, '1987-09-04', '子', '男')
        self.assertEqual(stage['domains'], original['domains'])
        self.assertEqual(stage['modules']['ZW-T02']['status'], 'withheld')


if __name__ == '__main__':
    unittest.main()
