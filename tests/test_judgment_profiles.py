"""Approved profile boundaries; these checks do not test forecast accuracy."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('judgment_knowledge', ROOT / 'scripts/knowledge_catalog.py')
KNOWLEDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KNOWLEDGE)


class JudgmentProfileTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())

    def test_exact_approved_cards_and_author_extension_identity(self):
        self.assertEqual(KNOWLEDGE.validate(self.catalog, ROOT), [])
        bazi = KNOWLEDGE.query(self.catalog, 'bazi', 'bazi-judgment-v1')
        ziwei = KNOWLEDGE.query(self.catalog, 'ziwei', 'ziwei-dynamic-reading-v1')
        self.assertEqual({r['rule_id'] for r in bazi}, {'BJ%02d' % i for i in range(1, 9)})
        self.assertEqual({r['rule_id'] for r in ziwei}, {'ZW-T01', 'ZW-L01', 'ZW-Q01'})
        for record in bazi + ziwei:
            self.assertEqual(record['usage_scope'], 'conditional_module_only')
        for record in bazi:
            if record['rule_id'] in {'BJ07', 'BJ08'}:
                self.assertEqual(record['source_identity'], 'author_temporal_extension')

    def test_a_new_rule_cannot_join_an_approved_profile_by_renaming(self):
        altered = copy.deepcopy(self.catalog)
        record = next(r for r in altered['records'] if r['id'] == 'bazi-judgment-BJ01')
        record['rule_id'] = 'BJ09'
        self.assertTrue(any('unapproved module record' in error
                            for error in KNOWLEDGE.validate(altered, ROOT)))

    def test_bibliography_cannot_bypass_the_module_only_reading_gate(self):
        source = next(s for s in self.catalog['sources'] if s['id'] == 'bazi-judgment-audit')
        rule = {'locator': source['path'], 'attribution_kind': 'registered_source_excerpt',
                'source_label': source['citation_label'], 'start_line': 17, 'end_line': 17}
        errors = KNOWLEDGE.check_ledger_rule(rule, source, self.catalog)
        self.assertTrue(any('bibliography-only' in error for error in errors))

    def test_new_cards_are_not_general_ledger_or_classical_quotes(self):
        for source_id in ('bazi-judgment-source', 'ziwei-dynamic-reading-source'):
            source = next(s for s in self.catalog['sources'] if s['id'] == source_id)
            record = next(r for r in self.catalog['records'] if r['source_id'] == source_id)
            rule = {'locator': source['path'], 'reading_use': 'conditional_module_only',
                    'attribution_kind': 'registered_source_excerpt',
                    'source_label': source['citation_label'], **record['source_span']}
            errors = KNOWLEDGE.check_ledger_rule(rule, source, self.catalog)
            self.assertTrue(any('module-only' in error for error in errors))
            with self.assertRaisesRegex(ValueError, 'refused'):
                KNOWLEDGE.citation(self.catalog, ROOT, source_id, 'classical_quote', 1, 1)


if __name__ == '__main__':
    unittest.main()
