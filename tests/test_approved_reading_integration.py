"""Synthetic chart-builder wiring for source-bound additions and time branches."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bazi_core_reading
import pai_pan_bazi


@unittest.skipUnless((ROOT / 'scripts/pai_pan_ziwei/node_modules/tsx').exists(), 'npm ci required')
class ApprovedReadingIntegrationTests(unittest.TestCase):
    def build(self, solar, hour, *extra):
        command = [sys.executable, 'scripts/build_chart.py', '--solar', solar, '--hour', hour,
                   '--sex', '男', '--lat', '30', '--lon', '120', '--analysis-year', '2026',
                   '--format', 'json', *extra]
        return json.loads(subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True).stdout)

    def test_uncertainty_reaches_both_new_panels_without_changing_native_chart(self):
        known = self.build('1960-02-15', '20:00')
        uncertain = self.build('1960-02-15', '20:00', '--uncertainty-minutes', '10')
        self.assertEqual(known['bazi']['pillars'], uncertain['bazi']['pillars'])
        self.assertEqual(known['ziwei']['chart'], uncertain['ziwei']['chart'])
        for field in ('domain_reading', 'patterns'):
            self.assertEqual(known['ziwei']['rule_output'][field], uncertain['ziwei']['rule_output'][field])
        self.assertEqual(uncertain['bazi_core_reading']['reviewed_structure']['status'], 'withheld')
        panel = uncertain['ziwei']['rule_output']['reviewed_structure']
        self.assertTrue(uncertain['ziwei']['input']['temporalUncertainty'])
        self.assertTrue(panel['temporal_uncertainty'])
        for name in ('fubi_observation', 'jiliang_observation', 'natal_lu_observation'):
            self.assertEqual(panel['modules'][name]['status'], 'withheld')
        self.assertEqual(known['ziwei']['rule_output']['reviewed_structure']['modules']['jiliang_observation']['status'], 'conditional')

    def test_day_boundary_uses_each_candidate_facts_and_keeps_old_strength_semantics(self):
        result = self.build('1986-01-04', '23:00', '--uncertainty-minutes', '10', '--enumerate-scenarios')
        comparison = result['bazi_scenario_comparison']
        candidates = comparison['candidates']
        self.assertGreater(len(candidates), 1)
        rows = []
        for candidate in candidates:
            core = candidate['analysis']
            panel = core['reviewed_structure']
            self.assertEqual(panel['scenario_id'], candidate['id'])
            k3 = next(card for card in panel['cards'] if card['id'] == 'BZ-K03')
            for pair in k3['pairs']:
                for endpoint in pair['endpoints']:
                    self.assertEqual(endpoint['stem'], core['facts'][endpoint['position']]['stem'])
            rows.append((core['facts']['day']['stem'], len(k3['pairs'])))
            # Each witness is still analyzed as its concrete pillar input;
            # input uncertainty is retained by the enclosing comparison.
            pillars = {key: (f['stem'], f['branch'], f['ten_god'], pai_pan_bazi.format_canggan(f['branch']))
                       for key, f in core['facts'].items()}
            self.assertEqual(core['strength_reasoning'], bazi_core_reading.analyze({'pillars': pillars})['strength_reasoning'])
        self.assertGreater(len(set(rows)), 1)
        self.assertTrue(all(pair_count > 0 for _, pair_count in rows))
        self.assertNotIn('reviewed_structure', comparison['stable_evidence'])


if __name__ == '__main__':
    unittest.main()
