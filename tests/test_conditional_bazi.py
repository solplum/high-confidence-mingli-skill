"""Restricted interpretation is useful, but cannot authorize predictive authority."""
import copy
import json
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ledger = load('conditional_ledger', 'scripts/validate_claim_ledger.py')
example = load('conditional_example', 'examples/bazi-conditional/generate.py')

class ConditionalBaZiTests(unittest.TestCase):
    def setUp(self):
        self.data = example.build()

    def errors(self):
        return ledger.validate(self.data, ROOT)

    def test_bound_structural_explanation_works(self):
        self.assertEqual(self.errors(), [])
        self.data['purpose'] = 'reading'
        self.assertEqual(self.errors(), [])

    def test_rule_attribution_authority_and_range_cannot_be_forged(self):
        for key, value in [('attribution_kind','classical_quote'), ('predictive_status','validated'),
                           ('authenticity_status','verified_edition'), ('guaranteed_prediction',True),
                           ('interpretation_label','权威原典'), ('start_line',1),
                           ('catalog_record_id','bazi-dts-study-geju'), ('quote','自行编造原文')]:
            with self.subTest(key=key):
                self.data = example.build()
                self.data['rules'][0][key] = value
                self.assertTrue(self.errors())

    def test_claim_cannot_become_prediction_or_authority(self):
        for key, value in [('status','supported'), ('predictive_status','validated'),
                           ('guaranteed_prediction',True), ('interpretation_label','权威原文'),
                           ('domain','财富预测'), ('reading_use','prediction')]:
            with self.subTest(key=key):
                self.data = example.build()
                self.data['claims'][0][key] = value
                self.assertTrue(self.errors())

    def test_conditions_and_counterevidence_need_bound_facts(self):
        for field in ['conditions','exclusions']:
            for key, value in [('fact_ids',[]),('fact_ids',['invented']),('assessment',''),
                               ('criterion','换一个容易满足的条件'),('result','unknown'),('result',[])]:
                with self.subTest(field=field,key=key):
                    self.data = example.build()
                    self.data['claims'][0]['application_checks'][0][field][0][key] = value
                    self.assertTrue(self.errors())
        self.data=example.build()
        self.data['claims'][0]['counterevidence']=''
        self.assertTrue(self.errors())

    def test_unmet_conditions_require_withholding(self):
        self.data['claims'][0]['application_checks'][0]['conditions'][0]['result']='not_met'
        self.assertTrue(self.errors())
        self.data['claims'][0]['status']='withheld'
        self.assertEqual(self.errors(), [])

    def test_dependency_cannot_launder_restricted_usage(self):
        downstream=copy.deepcopy(self.data['claims'][0])
        downstream.update(id='downstream',rule_ids=[],depends_on=['structure'],application_checks=[])
        downstream.pop('reading_use')
        self.data['claims'].append(downstream)
        self.assertTrue(any('restricted interpretation' in e for e in self.errors()))

    def test_chart_facts_are_still_validated(self):
        self.data['facts'][0]['value']=['invented']
        self.assertTrue(any('chart value mismatch' in e for e in self.errors()))

    def test_missing_partial_duplicate_and_unbound_scenario_checks_fail(self):
        for mutation in ['missing','partial','duplicate','scenario']:
            self.data=example.build()
            claim=self.data['claims'][0]
            if mutation=='missing':claim.pop('application_checks')
            elif mutation=='partial':claim['application_checks'][0]['conditions'].pop()
            elif mutation=='duplicate':claim['application_checks']*=2
            else:claim['scenario_ids'].append('not_bound')
            self.assertTrue(self.errors())

    def test_all_ten_precise_paraphrases_have_limited_entry(self):
        catalog=json.loads((ROOT/'knowledge/catalog.json').read_text())
        k=ledger._KNOWLEDGE
        records=k.query(catalog,'bazi','bazi-traditional-conditional')
        self.assertEqual(len(records),10)
        source=next(s for s in catalog['sources'] if s['id']=='bazi-dts-study-cards')
        for rec in records:
            rule=copy.deepcopy(self.data['rules'][0])
            rule.update(catalog_record_id=rec['id'],quote=rec['summary'],**rec['source_span'])
            self.assertIsNotNone(k.interpretation_record(rule,source,catalog))
            self.assertEqual(k.check_ledger_rule(rule,source,catalog),[])
            rule['end_line']+=1
            self.assertTrue(k.check_ledger_rule(rule,source,catalog))
        raw=next(s for s in catalog['sources'] if s['id']=='bazi-dts-short-excerpts')
        self.assertIsNone(k.interpretation_record(self.data['rules'][0],raw,catalog))
        self.assertTrue(k.check_ledger_rule(self.data['rules'][0],raw,catalog))

    def test_exported_example_retains_cc_scope(self):
        metadata=self.data['rules'][0]['redistribution']
        self.assertEqual(metadata['license_id'],'CC-BY-SA-4.0')
        self.assertIn('action=history',metadata['contributors_url'])
        self.assertIn('bazi-dts-interpret-*',metadata['license_notice'])



    def add_synthesis(self, relation='agreement', dependency=False, withheld=False):
        base=json.loads((ROOT/'examples/claim-ledger.example.json').read_text())
        for source in base['sources']:
            if source['id'] in ['chart-ziwei','rules']:
                source['path']='examples/ledger-fixture/'+source['path']
                if source['kind']=='chart':source['scenario_id']='fictional'
                self.data['sources'].append(source)
        fact=base['facts'][1]
        fact['scenario_id']='fictional'
        self.data['facts'].append(fact)
        self.data['rules'].append(base['rules'][1])
        other=base['claims'][1]
        other.update(scenario_ids=['fictional'],domain='传统结构解释',time_scope='虚构本命结构')
        if withheld:other['status']='withheld'
        self.data['claims'].append(other)
        member='structure'
        if dependency:
            self.data['rules'].append(base['rules'][0])
            downstream=copy.deepcopy(self.data['claims'][0])
            downstream.update(id='downstream',rule_ids=['bazi-rule'],depends_on=['structure'],application_checks=[])
            self.data['claims'].append(downstream)
            member='downstream'
        link=dict(id='restricted-synthesis',claim_ids=[member,other['id']],relation=relation,
                  explanation='仅比较结构解释，保留模型区别。',shared_inputs='同一合成输入，不是独立预测验证。',
                  limits='两体系相同表达不提高准确率；仅测试元数据继承。',
                  reading_use=example.USE,interpretation_label=example.LABEL,
                  authenticity_status='uncollated_digital_transcription',predictive_status='unvalidated',
                  guaranteed_prediction=False,domain='传统结构解释',status='withheld' if withheld else 'conditional')
        self.data['syntheses'].append(link)
        return link

    def test_synthesis_preserves_every_declaration_across_relations_and_dependencies(self):
        mutations=[('status','supported'),('interpretation_label','已核验权威原典'),
                   ('authenticity_status','verified_edition'),('domain','财富预测'),
                   ('reading_use','prediction'),('predictive_status','validated'),('guaranteed_prediction',True)]
        for relation in ['agreement','different_scope','conflict','insufficient']:
            for dependency in [False,True]:
                self.data=example.build()
                self.add_synthesis(relation,dependency)
                self.assertEqual(self.errors(),[])
                for key,value in mutations:
                    with self.subTest(relation=relation,dependency=dependency,key=key):
                        self.data=example.build()
                        link=self.add_synthesis(relation,dependency)
                        link[key]=value
                        self.assertTrue(self.errors())
                        link.pop(key)
                        self.assertTrue(self.errors())

    def test_reviewers_withheld_member_reproduction_cannot_strengthen(self):
        self.add_synthesis('different_scope',withheld=True)
        self.assertEqual(self.errors(),[])
        self.data['syntheses'][0]['status']='conditional'
        self.assertTrue(any('withheld member' in e for e in self.errors()))
        self.data['syntheses'][0].update(status='supported',interpretation_label='已核验权威原典',
                                       authenticity_status='verified_edition',domain='财富预测')
        errors=self.errors()
        for expected in ['cannot become supported','label required','authority claim forbidden','structural explanation']:
            self.assertTrue(any(expected in e for e in errors))

    def test_restricted_claim_authenticity_cannot_be_laundered(self):
        self.data['claims'][0]['authenticity_status']='verified_edition'
        self.assertTrue(any('authority claim forbidden' in e for e in self.errors()))

    def test_redistribution_metadata_required_unchanged_and_complete(self):
        self.data['rules'][0].pop('redistribution')
        self.assertTrue(any('redistribution' in e for e in self.errors()))
        for key in example.build()['rules'][0]['redistribution']:
            for value in [None,'changed',{},'']:
                with self.subTest(key=key,value=value):
                    self.data=example.build()
                    metadata=self.data['rules'][0]['redistribution']
                    if value is None:metadata.pop(key)
                    else:metadata[key]=value
                    self.assertTrue(any('redistribution' in e for e in self.errors()))
        self.data=example.build()
        self.data['rules'][0]['redistribution']='not a mapping'
        self.assertTrue(self.errors())


if __name__ == '__main__':
    unittest.main()
