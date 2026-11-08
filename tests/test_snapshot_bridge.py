"""Integration checks of computed snapshots, not predictive accuracy."""
from datetime import date, datetime
import contextlib
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
        self.assertIn('目标 2026 年',b.stdout)
        self.assertNotIn('紫微数据缺失',b.stdout)

    @unittest.skipUnless((ROOT/'scripts/pai_pan_ziwei/node_modules/tsx').exists(),'npm ci required')
    def test_ziwei_rejects_invalid_format(self):
        r=subprocess.run(['node','--import','tsx','pai_pan.ts','--format','xml'],cwd=ROOT/'scripts/pai_pan_ziwei',text=True,capture_output=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('--format',r.stderr)

if __name__=='__main__':
    unittest.main()
