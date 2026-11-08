"""Structural regressions; fixtures are synthetic and never predictive evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ledger", ROOT / "scripts/validate_claim_ledger.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/claim-ledger.example.json").read_text())
        self.root = ROOT / "examples/ledger-fixture"

    def errors(self):
        return module.validate(self.data, self.root)

    def test_nested_json_types_are_exact(self):
        self.assertFalse(module._json_equal([1], [True]))
        self.assertFalse(module._json_equal({"a": [0]}, {"a": [False]}))
        self.assertFalse(module._json_equal({"a": 1}, {"a": 1.0}))
        self.assertTrue(module._json_equal({"a": [1, True, None]}, {"a": [1, True, None]}))

    def test_valid_fixture(self):
        self.assertEqual(self.errors(), [])

    def test_duplicate_id(self):
        self.data['claims'].append(copy.deepcopy(self.data['claims'][0]))
        self.assertTrue(any('duplicate id' in x for x in self.errors()))

    def test_missing_reference(self):
        self.data['claims'][0]['rule_ids'] = ['nonexistent']
        self.assertTrue(any('unknown rule_ids' in x for x in self.errors()))

    def test_invented_quote(self):
        self.data['rules'][0]['quote'] = '古籍里并不存在的一句'
        self.assertTrue(any('quote not found' in x for x in self.errors()))

    def test_changed_source_hash(self):
        self.data['sources'][0]['sha256'] = '0' * 64
        self.assertTrue(any('hash mismatch' in x for x in self.errors()))

    def test_chart_value_mismatch(self):
        self.data['facts'][0]['value'] = '乙丑'
        self.assertTrue(any('value mismatch' in x for x in self.errors()))

    def test_path_escape(self):
        self.data['sources'][0]['path'] = '../claim-ledger.example.json'
        self.assertTrue(any('out-of-root' in x for x in self.errors()))

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'root'
            root.mkdir()
            (Path(d) / 'outside').write_text('data')
            (root / 'escape').symlink_to(Path(d) / 'outside')
            self.data['sources'][0]['path'] = 'escape'
            self.assertTrue(any('out-of-root' in x for x in module.validate(self.data, root)))

    def test_cross_system_dependency(self):
        self.data['claims'][0]['depends_on'] = ['ziwei-claim']
        self.assertTrue(any('cross-system' in x for x in self.errors()))

    def test_cycle(self):
        self.data['claims'][0]['depends_on'] = ['bazi-claim']
        self.assertTrue(any('cyclic' in x for x in self.errors()))

    def test_withheld_dependency(self):
        extra = copy.deepcopy(self.data['claims'][0])
        extra.update(id='withheld', status='withheld')
        self.data['claims'].append(extra)
        self.data['claims'][0]['depends_on'] = ['withheld']
        self.assertTrue(any('withheld claim' in x for x in self.errors()))

    def test_unassessed_cannot_be_supported(self):
        self.data['claims'][0]['status'] = 'supported'
        self.assertTrue(any('cannot be supported' in x for x in self.errors()))

    def test_stability_requires_all_scenarios(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        self.data['claims'][0]['boundary'] = 'stable'
        self.assertTrue(any('every scenario' in x for x in self.errors()))

    def test_stability_requires_actual_scenario_facts(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        self.data['claims'][0].update(boundary='stable',scenario_ids=['base','alternate'])
        self.assertTrue(any('lacks evidence' in x for x in self.errors()))

    def test_agreement_cannot_mix_scopes(self):
        self.data['syntheses'][0]['relation'] = 'agreement'
        self.data['claims'][1]['time_scope'] = '其他年份'
        self.assertTrue(any('mismatched time_scope' in x for x in self.errors()))

    def test_percent_and_star_confidence_disallowed(self):
        self.data['syntheses'][0]['confidence_percent'] = 95
        self.assertTrue(any('confidence field' in x for x in self.errors()))

    def test_counterevidence_required(self):
        self.data['claims'][0]['counterevidence'] = ''
        self.assertTrue(any('counterevidence' in x for x in self.errors()))

    def test_malformed_types_report_not_crash(self):
        for field,value in [('depends_on',None),('source_id',[]),('system',{})]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.data)
                mutated['claims'][0][field] = value
                self.assertTrue(module.validate(mutated,self.root))

    def test_bad_quote_type(self):
        self.data["rules"][0]["quote"] = None
        self.assertTrue(self.errors())

    def test_bad_purpose_type(self):
        self.data["purpose"] = []
        self.assertTrue(self.errors())

    def test_absolute_source_rejected(self):
        self.data["sources"][0]["path"] = str(self.root / "chart.json")
        self.assertTrue(any("relative" in x for x in self.errors()))

    def test_system_scope_cannot_be_relabeled(self):
        self.data['facts'][0].update(pointer='/ziwei/palace', value='命宫')
        self.assertTrue(any('outside system scope' in x for x in self.errors()))

    def test_scenario_fact_cannot_be_relabeled(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        fact = copy.deepcopy(self.data['facts'][0])
        fact.update(id='alternate-fact',scenario_id='alternate')
        self.data['facts'].append(fact)
        self.data['claims'][0].update(status='supported',boundary='stable',scenario_ids=['base','alternate'],fact_ids=['bazi-fact','alternate-fact'])
        self.assertTrue(any('scenario binding mismatch' in x for x in self.errors()))

    def test_source_path_not_reused_between_scenarios(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        source = copy.deepcopy(self.data['sources'][0])
        source.update(id='alternate-source', scenario_id='alternate')
        self.data['sources'].append(source)
        self.assertTrue(any('reused across scenarios' in x for x in self.errors()))

    def test_dependency_scope_mismatch(self):
        extra = copy.deepcopy(self.data['claims'][0])
        extra.update(id='other',time_scope='别的时期')
        self.data['claims'].append(extra)
        self.data['claims'][0]['depends_on'] = ['other']
        self.assertTrue(any('dependency time_scope' in x for x in self.errors()))

    def test_self_loop_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'loop').symlink_to('loop')
            self.data['sources'][0]['path'] = 'loop'
            self.assertTrue(module.validate(self.data,d))

    def test_directory_not_read_as_source(self):
        self.data['sources'][0]['path'] = '.'
        self.assertTrue(any('regular file' in x for x in self.errors()))

    def test_conflict_retained_without_forced_agreement(self):
        self.data['syntheses'][0].update(relation='conflict',explanation='两套合成规则给出不同方向，保留分歧。')
        self.data['claims'][1]['statement'] = '合成相反解释，不对应真实人。'
        self.assertEqual(self.errors(), [])

    def test_agreement_rejects_withheld_claim(self):
        self.data['claims'][1]['status'] = 'withheld'
        self.data['syntheses'][0]['relation'] = 'agreement'
        self.assertTrue(any('agreement uses withheld' in x for x in self.errors()))

    def test_dependency_requires_scenario_coverage(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        extra = copy.deepcopy(self.data['claims'][0])
        extra.update(id='other',scenario_ids=['alternate'],fact_ids=[] ,status='withheld')
        self.data['claims'].append(extra)
        self.data['claims'][0]['depends_on'] = ['other']
        self.assertTrue(any('does not cover claim scenarios' in x for x in self.errors()))

    def test_missing_collections(self):
        self.assertTrue(module.validate({},self.root))

    def test_bad_quote_range(self):
        self.data['rules'][0]['start_line'] = 0
        self.assertTrue(any('line range' in x for x in self.errors()))


if __name__ == '__main__':
    unittest.main()
