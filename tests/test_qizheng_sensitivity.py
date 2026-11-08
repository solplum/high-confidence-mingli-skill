"""Synthetic public fixtures only: sampled evidence is not a stability certificate."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qizheng_sensitivity as sensitivity
import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules
import build_chart
from time_scenarios import resolve_civil


class SensitivityTests(unittest.TestCase):
    def test_real_boundaries_and_replay(self):
        result = sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),120,35,120)
        self.assertFalse(result['coverage_complete'])
        self.assertEqual({},result['stable_fields'])
        self.assertFalse(result['method']['root_completeness_proven'])
        self.assertIn('day_night',result['observed_changing_fields'])
        self.assertIn('ascendant.mansion',result['observed_changing_fields'])
        self.assertIn('ming_gong',result['observed_changing_fields'])
        self.assertIn('rule_output',result['observed_changing_fields'])
        candidates = {r['witness_utc']: r for r in result['candidates']}
        for b in result['boundaries']:
            self.assertLessEqual(b['width_seconds'],.1)
            a,c = (candidates[b[k]] for k in ('left_utc','right_utc'))
            self.assertNotEqual(a['fields'],c['fields'])
        for row in candidates.values():
            instant=datetime.fromisoformat(row['witness_utc'])
            bj=instant.astimezone(engine.BJ)
            chart,_=engine.compute((bj.year,bj.month,bj.day),bj.hour,bj.minute,35,120,birth_instant=instant)
            self.assertEqual(chart,row['chart'])
            self.assertEqual(rules.analyze(chart),row['rule_reading'])
        # Text carries the same evidence, including full numerical coordinates.
        self.assertEqual(result,json.loads(sensitivity.render(result, full_evidence=True)[-2]))

    def test_bounded_plain_summary_and_full_evidence(self):
        for lat, zone, fold, date in (
            (35, 'Asia/Shanghai', None, datetime(2000,1,1,8)),
            (90, 'America/New_York', 1, datetime(2024,11,3,1,30)),
            (35, 'America/New_York', None, datetime(2024,3,10,3,30)),
        ):
            result=sensitivity.compare(resolve_civil(date,zone=zone,fold=fold),120,lat,120)
            text='\n'.join(sensitivity.render(result))
            self.assertLess(len(text),6000)
            self.assertLessEqual(text.count('一次观察差异'),sensitivity.SUMMARY_MAX_CHANGES)
            self.assertNotIn('```json',text)
            self.assertIn('未观察到不等于稳定',text)
            self.assertIn(result['candidates'][0]['witness_civil'],text)
            self.assertIn(result['candidates'][-1]['witness_civil'],text)
            self.assertEqual(result,json.loads(sensitivity.render(result,True)[-2]))
            if date.month==3:
                self.assertIn('时区偏移变化或重复民用时刻',text)
            if lat==90:
                self.assertIn('上升交点未定义',text)
                self.assertIn('UTC 区分瞬间',text)
        point=sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),0,35,120)
        self.assertIn('不能据此说整个时段稳定','\n'.join(sensitivity.render(point)))

    def test_real_moon_mansion_boundary(self):
        result = sensitivity.compare(datetime(2000,1,3,tzinfo=timezone.utc),120,35,120)
        self.assertIn("bodies.月.mansion",result["observed_changing_fields"])
        self.assertTrue(any("bodies.月.mansion" in b["changed_fields"] for b in result["boundaries"]))

    def test_fold_elapsed_time_and_equivalent_offsets(self):
        civil=resolve_civil(datetime(2024,11,3,1,30),zone='America/New_York',fold=1)
        a=sensitivity.compare(civil,40,40,-74)
        b=sensitivity.compare(civil.astimezone(timezone.utc),40,40,-74)
        self.assertEqual(a['interval'],b['interval'])
        self.assertEqual(a['boundaries'],b['boundaries'])
        self.assertEqual([c['chart'] for c in a['candidates']],[c['chart'] for c in b['candidates']])
        self.assertEqual({0,1},{r['fold'] for r in a['candidates']})
        self.assertEqual(4800,(datetime.fromisoformat(a['interval']['end_utc'])-datetime.fromisoformat(a['interval']['start_utc'])).total_seconds())

    def test_pole_missing_ascendant_and_legacy(self):
        for profile in ('physical-v2','legacy-v1'):
            r=sensitivity.compare(datetime(2000,1,1,tzinfo=timezone.utc),2,90,0,profile)
            self.assertTrue(r['high_latitude_caution'])
            self.assertEqual(profile,r['calculation_profile'])
            if profile=='physical-v2':
                self.assertTrue(all(c['chart']['ming_du'] is None for c in r['candidates']))
                self.assertTrue(all(c['rule_reading']['status']=='withheld' for c in r['candidates']))

    def test_selected_tradition_composes_without_unlocking_center(self):
        import qizheng_traditional_reading as tradition
        civil=datetime(2000,1,1,tzinfo=timezone.utc)
        result=sensitivity.compare(civil,2,35,120,traditional_scheme=tradition.SCHEME)
        self.assertEqual('withheld',result['uncertain_birth_rule_status'])
        self.assertEqual(tradition.SCHEME,result['traditional_scheme'])
        for row in result['candidates']:
            self.assertEqual(tradition.analyze(row['chart'],tradition.SCHEME,birth_instant=datetime.fromisoformat(row['witness_utc'])),row['traditional_reading'])
            self.assertIn('traditional_rule_output',row['fields'])
        self.assertLess(result['method']['evaluation_count'],sensitivity.MAX_EVALUATIONS)
        text='\n'.join(sensitivity.render(result))
        self.assertIn('紫气为未独立校准',text)
        self.assertIn('真太阳时误差',text)

    def test_subsecond_traditional_witness_preserves_boundary_side(self):
        import qizheng_traditional_reading as tradition
        for microsecond in (999700, 999999):
            instant=datetime(2000,1,1,0,59,59,microsecond,tzinfo=timezone.utc)
            bj=instant.astimezone(engine.BJ)
            chart,_=engine.compute((bj.year,bj.month,bj.day),bj.hour,bj.minute,35,120,birth_instant=instant)
            reading=tradition.analyze(chart,tradition.SCHEME,birth_instant=instant)
            self.assertEqual('conditional',reading['status'])
            wrong=instant.replace(hour=3)
            self.assertEqual('withheld',tradition.analyze(chart,tradition.SCHEME,birth_instant=wrong)['status'])

    def test_budget_and_validation(self):
        center=datetime(2000,1,1,tzinfo=timezone.utc)
        with patch.object(sensitivity,'MAX_EVALUATIONS',241):
            r=sensitivity.compare(center,120,35,120)
        self.assertTrue(r['method']['budget_exhausted'])
        self.assertEqual(241,r['method']['evaluation_count'])
        self.assertTrue(any(b.get('unrefined') for b in r['boundaries']))
        for minutes in (-1,121,float('nan'),float('inf')):
            with self.assertRaises(ValueError): sensitivity.compare(center,minutes,35,120)
        with self.assertRaises(ValueError): sensitivity.compare(center.replace(tzinfo=None),1,35,120)
        with self.assertRaises(ValueError): sensitivity.compare(center,1,91,120)
        with self.assertRaises(ValueError): sensitivity.compare(center.replace(year=1900),1,35,120)

    def test_cli_opt_in_and_uncertainty_guard(self):
        args=['--solar','2000-01-01','--hour','08:00','--lat','35','--lon','120','--sex','男','--uncertainty-minutes','120','--analysis-year','2026']
        def run(extra):
            out=io.StringIO()
            with patch.object(build_chart,'run_ziwei',return_value=(None,'test only')),contextlib.redirect_stdout(out):
                build_chart.main(args+extra)
            return out.getvalue()
        old=json.loads(run(['--format','json']))
        new=json.loads(run(['--format','json','--qizheng-sensitivity']))
        self.assertIsNone(old['qizheng_sensitivity'])
        self.assertEqual(old['scenarios'],new['scenarios'])
        self.assertEqual(old['bazi'],new['bazi'])
        self.assertEqual(old['qizheng'],new['qizheng'])
        self.assertEqual('withheld',new['qizheng_rule_reading']['status'])
        self.assertTrue(any(c['rule_reading']['status']=='conditional' for c in new['qizheng_sensitivity']['candidates']))
        summary=run(['--qizheng-sensitivity'])
        self.assertNotIn('```json',summary)
        text=run(['--qizheng-sensitivity-evidence'])
        payload=text.split('```json\n',1)[1].split('\n```',1)[0]
        self.assertEqual(new['qizheng_sensitivity'],json.loads(payload))

if __name__=='__main__': unittest.main()
