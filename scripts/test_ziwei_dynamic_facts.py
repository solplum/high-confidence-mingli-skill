"""Facts-adapter regressions; no forecast interpretation or validity claims."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'scripts' / 'ziwei_dynamic_facts.mjs'


@unittest.skipUnless(shutil.which('node'), 'Node required for the locked local engine')
class DynamicFactsTests(unittest.TestCase):
    @classmethod
    def invoke(cls, date='2026-11-10', index=6, env=None, birth_solar='1984-06-17', birth_year=1984):
        command = ['node', str(ADAPTER), '--solar', birth_solar, '--birth-year', str(birth_year),
                   '--shichen-index', '6', '--sex', '女',
                   '--target-date', date, '--target-time-index', str(index),
                   '--source-label', 'synthetic-regression']
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=45, env=env)
        if result.returncode:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)

    @classmethod
    def setUpClass(cls):
        cls.ordinary = cls.invoke()
        cls.late_zi = cls.invoke(index=12)
        cls.age_conflict = cls.invoke(date='2009-01-15')

    def test_only_independent_year_month_day_layers_are_admitted(self):
        facts = self.ordinary['admitted_dynamic_facts']
        self.assertEqual(set(facts['layers']), {'yearly', 'monthly', 'daily'})
        self.assertEqual(set(facts['forbidden_layers']), {'age', 'decadal', 'hourly'})
        self.assertFalse(facts['full_interval_coverage'])
        for layer in facts['layers'].values():
            self.assertEqual(layer['status'], 'facts_only')
            self.assertEqual(layer['interpretation_status'], 'facts_only_no_effect_verdict')

    def test_late_zi_blocks_combined_daily_view_but_keeps_source(self):
        data = self.late_zi
        daily = data['admitted_dynamic_facts']['layers']['daily']
        self.assertEqual(daily['status'], 'withheld')
        self.assertNotIn('transformations', daily)
        self.assertNotIn('ming_coordinate', daily)
        self.assertIn('daily', data['research_dynamic_iztro']['raw_horoscope'])
        derived = data['research_dynamic_iztro']['selected_fact_views']['daily']
        self.assertEqual(derived['status'], 'withheld')
        self.assertNotIn('transformations', derived)
        self.assertNotIn('ming_coordinate', derived)
        for scope in ('yearly', 'monthly'):
            self.assertEqual(data['admitted_dynamic_facts']['layers'][scope]['status'], 'facts_only')

    def test_age_conflict_does_not_overwrite_current_contract(self):
        data = self.age_conflict
        conflict = data['research_dynamic_iztro']['conflicts'][0]
        self.assertTrue(conflict['age_differs'])
        self.assertEqual(data['native_wrapper_snapshot']['chart']['currentAge'], 26)
        self.assertEqual(conflict['raw_iztro_age'], 25)
        self.assertTrue(data['admitted_dynamic_facts']['native_age_and_decadal_unchanged'])
        self.assertNotIn('age', data['admitted_dynamic_facts']['layers'])
        self.assertNotIn('decadal', data['admitted_dynamic_facts']['layers'])

    def test_empty_indices_and_source_label_are_rejected(self):
        base = ['node', str(ADAPTER), '--solar', '1984-06-17', '--birth-year', '1984',
                '--shichen-index', '6', '--sex', '女', '--target-date', '2026-11-10',
                '--target-time-index', '6', '--source-label', 'synthetic-regression']
        for key, value in [('--shichen-index', ''), ('--shichen-index', '  '),
                           ('--target-time-index', ''), ('--target-time-index', '  '),
                           ('--source-label', '')]:
            with self.subTest(key=key, value=value):
                command = list(base)
                command[command.index(key) + 1] = value
                result = subprocess.run(command, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_resolved_solar_clock_crossing_year_preserves_civil_birth_year(self):
        data = self.invoke(birth_solar='1984-12-31', birth_year=1985)
        self.assertEqual(data['inputs']['birth']['original_civil_birth_year'], 1985)
        self.assertEqual(data['native_wrapper_snapshot']['chart']['currentAge'], 42)
        self.assertEqual(data['native_wrapper_snapshot']['input']['birthYear'], 1985)

    def test_explicit_calendar_view_is_independent_of_process_timezone(self):
        env = dict(os.environ, TZ='Pacific/Kiritimati')
        shifted = self.invoke(env=env)
        self.assertEqual(shifted['admitted_dynamic_facts'],
                         self.ordinary['admitted_dynamic_facts'])
        self.assertEqual(shifted['native_wrapper_snapshot'],
                         self.ordinary['native_wrapper_snapshot'])


if __name__ == '__main__':
    unittest.main()
