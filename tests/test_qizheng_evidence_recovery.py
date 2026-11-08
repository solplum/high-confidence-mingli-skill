"""Fail-closed evidence regression checks recovered after the final archive."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules
import qizheng_traditional_reading as tradition


class EvidenceRecovery(unittest.TestCase):
    def chart(self):
        return engine.compute((2000, 1, 1), 12, 0, 35, 120)[0]

    def test_missing_or_malformed_frame(self):
        for value in (None, {}, [], '', {'within_validated_range': 1},
                      {'within_validated_range': False}, {'within_validated_range': 'true'}):
            chart = self.chart()
            chart['star_frame_contract'] = value
            self.assertEqual('withheld', rules.analyze(chart)['status'])
            self.assertEqual('withheld', tradition.analyze(chart, tradition.SCHEME)['status'])

    def test_missing_or_malformed_ming_evidence(self):
        for key, values in (
            ('classification_quality', (None, {}, [], False, {'near_boundary': 0}, {'near_boundary': 'false'}, {'near_boundary': True})),
            ('tropical', (None, True, [], {}, '1', float('nan'), float('inf'), -1, 360, 10**1000)),
            ('sidereal', (None, True, [], {}, '1', float('nan'), float('inf'), -1, 360)),
            ('mansion', (None, [], {}, 'wrong')),
            ('wuxing', (None, [], {}, 'wrong'))):
            for value in values:
                with self.subTest(key=key, value=str(value)[:40]):
                    chart = self.chart()
                    chart['ming_du'][key] = value
                    self.assertEqual('withheld', rules.analyze(chart)['status'])
        for key in ('tropical', 'sidereal', 'classification_quality'):
            chart = self.chart()
            del chart['ming_du'][key]
            self.assertEqual('withheld', rules.analyze(chart)['status'])

    def test_bad_sun_withholds_only_palace(self):
        variants = (None, {}, [], False, {'日': None}, {'日': {}}, {'日': []})
        for bodies in variants:
            chart = self.chart()
            chart['bodies'] = bodies
            result = rules.analyze(chart)
            self.assertEqual('conditional', result['status'])
            self.assertEqual(['conditional', 'withheld'], [c['status'] for c in result['claims']])
        for key, value in (('classification_quality', {}), ('classification_quality', {'near_boundary': 0}),
                           ('tropical', True), ('sidereal', float('nan'))):
            chart = self.chart()
            chart['bodies']['日'][key] = value
            result = rules.analyze(chart)
            self.assertEqual(['conditional', 'withheld'], [c['status'] for c in result['claims']])

    def test_malformed_palace_and_uncertainty(self):
        for value in (None, [], {}, {'zhi': []}, {'zhi': {}}):
            chart = self.chart()
            chart['ming_gong'] = value
            self.assertEqual('withheld', rules.analyze(chart)['claims'][1]['status'])
        for value in (None, 0, 1, [], '', 'false'):
            self.assertEqual('withheld', rules.analyze(self.chart(), temporal_uncertainty=value)['status'])

    def test_no_mutation(self):
        chart = self.chart()
        before = copy.deepcopy(chart)
        rules.analyze(chart)
        self.assertEqual(before, chart)


if __name__ == '__main__':
    unittest.main()
