import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pai_pan_qizheng as engine
import qizheng_rule_profiles as rules


class RuleProfiles(unittest.TestCase):
    def chart(self):
        return {'calculation_profile': 'physical-v2',
                'ming_du': {'mansion': '牛', 'wuxing': '金', 'tropical': 50., 'sidereal': 180., 'classification_quality': {'near_boundary': False}},
                'star_frame_contract': {'within_validated_range': True},
                'bodies': {'日': {'tropical': 50., 'sidereal': 180., 'classification_quality': {'near_boundary': False}}},
                'ming_gong': {'zhi': '卯', 'wuxing': '木'},
                'du_zhu_wuxing': '金', 'en_yong': engine.en_yong_chou_nan('金')}

    def test_branch_is_not_lord(self):
        row = rules.palace_identity('卯')
        self.assertEqual(('木', '火', '火'), (row['branch_element'], row['palace_lord'], row['palace_lord_element']))
        self.assertEqual('月', rules.palace_identity('未')['palace_lord'])
        self.assertEqual('水', rules.palace_identity('未')['palace_lord_element'])

    def test_concrete_conditional_example(self):
        result = rules.analyze(self.chart())
        self.assertEqual('conditional', result['status'])
        self.assertEqual(['土', '计都'], result['claims'][0]['groups']['恩'])
        self.assertEqual('难', result['claims'][1]['relation_to_degree_lord'])
        self.assertIn('不能用支五行替代', rules.format_reading(result))
        self.assertEqual('unvalidated', result['predictive_validity'])

    def test_all_five_phase_groups_preserve_engine(self):
        for wx in rules.ELEMENTS:
            actual = {k: [] for k in ('恩', '用', '仇', '难', '同')}
            for star in engine.LUMINARIES:
                actual[rules.relation(wx, engine.LUMINARIES_WUXING[star])].append(star)
            self.assertEqual(engine.en_yong_chou_nan(wx), actual)

    def test_unknown_versions_do_not_guess(self):
        chart = self.chart(); del chart['calculation_profile']
        self.assertEqual('withheld', rules.analyze(chart)['status'])
        with self.assertRaises(ValueError):
            rules.analyze(chart, profile='other-school')
        chart['calculation_profile'] = 'future-v8'
        self.assertEqual('withheld', rules.analyze(chart)['status'])

    def test_missing_ascendant_and_uncertainty(self):
        chart = self.chart(); chart['ming_du'] = None
        self.assertEqual([], rules.analyze(chart)['claims'])
        self.assertEqual('withheld', rules.analyze(self.chart(), temporal_uncertainty=True)['status'])

    def test_conflicting_inputs_fail_closed(self):
        for key, value in [('ming_du', {'mansion': '牛', 'wuxing': '木'}),
                           ('en_yong', {'恩': ['金']}), ('du_zhu_wuxing', '火')]:
            chart = self.chart(); chart[key] = value
            self.assertEqual('withheld', rules.analyze(chart)['status'])

    def test_missing_palace_withholds_only_palace(self):
        chart = self.chart(); chart['ming_gong'] = None
        claims = rules.analyze(chart)['claims']
        self.assertEqual(['conditional', 'withheld'], [c['status'] for c in claims])

    def test_source_pin_and_no_mutation(self):
        evidence = rules.source_evidence()
        self.assertTrue(all(not s['classical_quote_authorized'] for s in evidence))
        chart = self.chart(); before = copy.deepcopy(chart)
        rules.analyze(chart)
        self.assertEqual(before, chart)

    def test_source_changes_are_rejected(self):
        with patch.object(Path, "read_bytes", return_value=b"modified source"):
            with self.assertRaises(ValueError):
                rules.analyze(self.chart())

    def test_incomplete_or_mislabeled_manifest_cannot_authorize_claims(self):
        relative = Path('knowledge/qizheng-rule-sources.json')
        manifest = json.loads((rules.ROOT / relative).read_text())
        cases = (
            [],
            [manifest['sources'][0]],
            [manifest['sources'][0]] * 2,
            [dict(manifest['sources'][0], classical_quote_authorized=True), manifest['sources'][1]],
            [dict(manifest['sources'][0], path=manifest['sources'][1]['path']), manifest['sources'][1]],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / relative
            path.parent.mkdir()
            for entry in manifest['sources']:
                target = root / entry['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(rules.ROOT / entry['path'])
            with patch.object(rules, 'ROOT', root):
                for rows in cases:
                    with self.subTest(rows=rows):
                        path.write_text(json.dumps(dict(manifest, sources=rows)))
                        with self.assertRaises(ValueError):
                            rules.analyze(self.chart())
                        panel = rules.analyze(self.chart(), withhold_on_source_error=True)
                        self.assertEqual(panel['status'], 'withheld')
                        self.assertEqual(panel['claims'], [])
                        self.assertEqual(panel['sources'], [])
                        self.assertNotIn('出处：', rules.format_reading(panel))

    def test_real_legacy_engine_output(self):
        chart, _ = engine.compute((1990, 1, 1), 12, 0, 39.9, 116.4, profile='legacy-v1')
        self.assertEqual('legacy-v1', chart['calculation_profile'])
        result = rules.analyze(chart)
        # Genuine legacy output lacks boundary checks and cannot authorize claims.
        self.assertEqual('withheld', result['status'])
        self.assertEqual([], result['claims'])


if __name__ == '__main__':
    unittest.main()
