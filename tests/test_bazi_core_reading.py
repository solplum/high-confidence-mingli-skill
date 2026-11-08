import copy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pai_pan_bazi as engine
import bazi_core_reading as core
import build_chart


CASES = [('1988-03-18', 10, 20), ('2001-08-22', 16, 40),
         ('1975-12-11', 6, 30), ('1998-06-30', 23, 0), ('1992-02-04', 21, 48)]


def chart(solar, hour, minute):
    return engine.compute(date.fromisoformat(solar), hour=hour, minute=minute, now=date(2026, 1, 1))


def fixture(stems, branches):
    day = engine.GAN.index(stems[2])
    return {'pillars': {k: (g, z, '—' if k == 'day' else engine.shishen_of(day, engine.GAN.index(g)),
                            engine.format_canggan(z))
                        for k, g, z in zip(core.KEYS, stems, branches)}}


class CoreReadingTests(unittest.TestCase):
    def test_real_cases_distinct_and_complete(self):
        outputs = []
        for args in CASES:
            result = chart(*args)
            a = core.analyze(result)
            self.assertEqual(len(a['sections']), 5)
            for section in a['sections']:
                self.assertTrue(section['prerequisites'])
                self.assertTrue(section['unresolved'])
                self.assertTrue(set(section['evidence']) <= set(a['facts']))
            text = '\n'.join(build_chart.bazi_section(result))
            self.assertNotIn('<!-- agent:', text)
            self.assertIn('不是古籍原文', text)
            outputs.append(text)
        self.assertEqual(len(set(outputs)), 5)

    def test_exact_spring_fields(self):
        a = core.analyze(chart(*CASES[0]))
        self.assertEqual(a['facts']['day']['stem'], '壬')
        self.assertEqual(a['month_exposure'][0]['exposed_at'], ['month', 'hour'])
        self.assertIn('日支申藏壬水', a['roots'])

    def test_conflicting_relations_retained(self):
        a = core.analyze(fixture('甲丙戊壬', '寅巳申亥'))
        kinds = {r['kind'] for r in a['relations']}
        self.assertTrue({'六冲', '六合配对', '相害'} <= kinds)
        self.assertIn('三刑齐字', [g['kind'] for g in a['groups']])

    def test_partial_triple_is_not_full(self):
        a = core.analyze(fixture('甲丙戊壬', '巳申巳申'))
        self.assertFalse(a['groups'])
        self.assertEqual(sum(r['kind'] == '六合配对' for r in a['relations']), 4)
        self.assertFalse(any(r['kind'] == '自刑配对' for r in a['relations']))

    def test_self_punishment_requires_two_positions(self):
        a = core.analyze(fixture('甲丙戊壬', '辰辰酉子'))
        self.assertEqual(sum(r['kind'] == '自刑配对' for r in a['relations']), 1)

    def test_unknown_hour_not_negative_full_chart_claim(self):
        result = engine.compute(date(2000, 1, 1), now=date(2026, 1, 1))
        a = core.analyze(result)
        self.assertEqual(a['missing_pillars'], ['hour'])
        self.assertTrue(a['warnings'])
        self.assertEqual(len(a['paths']), 2)

    def test_day_stem_not_counted_as_exposure(self):
        a = core.analyze(fixture('壬丙甲戊', '子寅卯午'))
        self.assertTrue(a['month_exposure'][0]['same_as_day'])
        self.assertEqual(a['month_exposure'][0]['exposed_at'], [])
        self.assertIn('日支卯藏乙木', a['roots'])

    def test_tampered_derived_fields_rejected(self):
        for index in (2, 3):
            r = copy.deepcopy(chart(*CASES[0]))
            row = list(r['pillars']['month'])
            row[index] = '伪造'
            r['pillars']['month'] = row
            with self.assertRaises(ValueError):
                core.analyze(r)

    def test_malformed_pillars_rejected(self):
        for bad in ([], ['未知'], ['未知', '午', '伪造', '伪造'], None, [1, 2, 3, 4]):
            r = copy.deepcopy(chart(*CASES[0]))
            r['pillars']['hour'] = bad
            with self.assertRaises(ValueError):
                core.analyze(r)
        for bad in ({}, {'pillars': {}}, {'pillars': []}, None):
            with self.assertRaises(ValueError):
                core.analyze(bad)

    def test_deterministic_json_safe(self):
        r = chart(*CASES[0])
        self.assertEqual(core.analyze(r), core.analyze(r))
        json.dumps(core.analyze(r), ensure_ascii=False, allow_nan=False)

    def test_cli_snapshot_matches_text_analysis(self):
        cmd = [sys.executable, str(ROOT / 'scripts/build_chart.py'), '--solar', '1988-03-18',
               '--hour', '10:20', '--sex', '女', '--lat', '30.57', '--lon', '104.07', '--analysis-year', '2026']
        snapshot = json.loads(subprocess.check_output(cmd + ['--format', 'json'], text=True))
        text = subprocess.check_output(cmd, text=True)
        self.assertEqual(snapshot['bazi_core_reading'], core.analyze(snapshot['bazi']))
        for s in snapshot['bazi_core_reading']['sections']:
            self.assertIn(s['text'], text)
        self.assertEqual(snapshot['bazi']['pillars']['day'][:2], ['壬', '申'])


if __name__ == '__main__':
    unittest.main()
