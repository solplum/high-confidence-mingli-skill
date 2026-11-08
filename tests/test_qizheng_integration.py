"""Final integration: exact legacy replay and real chart-builder profile routing."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_chart
import pai_pan_qizheng as q
import qizheng_rule_profiles as rules

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_exact_old_keys_replay(self):
        fixture = json.loads((ROOT / 'tests/fixtures/qizheng/legacy-c49e6a5.json').read_text())
        for case in fixture['cases']:
            actual, _ = q.compute(*case['args'], profile='legacy-v1')
            self.assertEqual(case['expected'], {k: actual[k] for k in case['expected']})

    def test_dynamic_provenance(self):
        for profile in ('legacy-v1', 'physical-v2'):
            chart, _ = q.compute((2000,1,1),12,0,35,120,profile=profile)
            self.assertEqual(profile, chart['model_provenance']['calculation_profile'])
            for path, digest in chart['model_provenance']['source_sha256'].items():
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest)

    def test_boundary_and_range_gates(self):
        for date, hour, minute in (((1990,1,1),0,43), ((1800,1,1),12,0)):
            chart, _ = q.compute(date,hour,minute,39.9,116.4)
            self.assertEqual('withheld', rules.analyze(chart)['status'])
        chart,_ = q.compute((2000,1,1),12,0,35,120)
        chart['bodies']['日']['classification_quality']['near_boundary'] = True
        chart['ming_du']['classification_quality']['near_boundary'] = False
        self.assertEqual('withheld', rules.analyze(chart)['claims'][1]['status'])
        for invalid in ('', '木火', None):
            with self.assertRaises(ValueError): rules.relation(invalid,'木')

    def test_real_build_chart_profiles_and_uncertainty(self):
        for profile in ('legacy-v1', 'physical-v2'):
            argv=['--solar','2000-01-01','--hour','12:00','--sex','男',
                  '--lat','35','--lon','120','--analysis-year','2026','--qizheng-profile',profile]
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv+['--format','json'])
            snapshot=json.loads(out.getvalue())
            self.assertIsNotNone(snapshot['ziwei'], 'Requires real Node/tsx installation, not a skip or mock')
            self.assertEqual(profile,snapshot['qizheng_rule_reading']['calculation_profile'])
            self.assertEqual(rules.analyze(snapshot['qizheng']),snapshot['qizheng_rule_reading'])
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv)
            self.assertIn(rules.format_reading(snapshot['qizheng_rule_reading']),out.getvalue())
            out=io.StringIO()
            with contextlib.redirect_stdout(out): build_chart.main(argv+['--format','json','--uncertainty-minutes','5'])
            self.assertEqual('withheld',json.loads(out.getvalue())['qizheng_rule_reading']['status'])

if __name__ == '__main__': unittest.main()
