"""Approved native panels stay source-bound and do not open ledger permissions."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import knowledge_catalog as knowledge
import reviewed_knowledge as reviewed


class ReviewedKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())

    def record(self, catalog=None):
        return next(r for r in (catalog or self.catalog)['records'] if r['id'] == 'bazi-reviewed-BZ-K01')

    def test_independent_profiles_load_exact_approved_sets_with_evidence(self):
        for profile, contract in knowledge.REVIEWED_PROFILES.items():
            records = reviewed.load_profile(contract['system'], profile, contract['records'])
            self.assertEqual({r['id'] for r in records}, set(contract['records']))
            for row in records:
                citation = row['citation']
                self.assertEqual(citation['sha256'], hashlib.sha256((ROOT / citation['path']).read_bytes()).hexdigest())
                self.assertTrue(citation['primary_sources'])
                self.assertEqual(row['usage_scope'], knowledge.MODULE_ONLY)
        with self.assertRaises(ValueError):
            reviewed.load_profile('ziwei', 'bazi-reviewed-structure-v1', [])
        with self.assertRaises(ValueError):
            reviewed.load_profile('bazi', 'bazi-reviewed-structure-v1', ['bazi-reviewed-BZ-K01'])

    def test_new_cards_do_not_enter_old_profiles(self):
        for system, profile in [('bazi', 'bazi-current'), ('ziwei', 'ziwei-domain-conditional')]:
            self.assertFalse(any(r.get('usage_scope') == knowledge.MODULE_ONLY for r in knowledge.query(self.catalog, system, profile)))
        self.assertEqual(len(reviewed._star_themes(self.catalog)), 14)

    def test_missing_or_quarantined_card_cannot_be_loaded_as_complete(self):
        contract = knowledge.REVIEWED_PROFILES['bazi-reviewed-structure-v1']
        for action in ('remove', 'quarantine'):
            data = copy.deepcopy(self.catalog)
            if action == 'remove':
                data['records'].remove(self.record(data))
            else:
                self.record(data)['status'] = 'quarantined'
            with self.assertRaises(ValueError):
                reviewed._records('bazi', 'bazi-reviewed-structure-v1', contract['records'], data)

    def test_exact_summary_scope_and_checklists_are_required(self):
        changes = [lambda r: r.update(summary='换成未审核的新断语'),
                   lambda r: r.update(conditions=[]), lambda r: r.update(exclusions=[]),
                   lambda r: r.update(usage_scope='unrestricted'),
                   lambda r: r.update(profile='bazi-current'),
                   lambda r: r.update(profile=[]),
                   lambda r: r.update(source_span={'start_line': 1, 'end_line': 1}),
                   lambda r: r.update(rule_id='BZ-K05')]
        for change in changes:
            data = copy.deepcopy(self.catalog)
            change(self.record(data))
            self.assertTrue(knowledge.validate(data, ROOT))

    def test_primary_sources_must_be_locatable_and_same_system(self):
        changes = [lambda r: r.update(primary_sources=[]),
                   lambda r: r['primary_sources'][0].update(source_id='iztro-docs-basis'),
                   lambda r: r['primary_sources'][0].update(source_id='missing'),
                   lambda r: r['primary_sources'][0].update(locator=''),
                   lambda r: r['primary_sources'][0].update(artifact_sha256='not-a-hash')]
        for change in changes:
            data = copy.deepcopy(self.catalog)
            change(self.record(data))
            self.assertTrue(knowledge.validate(data, ROOT))

    def test_source_byte_change_refuses_loader(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder)
            for name in ('references', 'docs', 'knowledge'):
                shutil.copytree(ROOT / name, fake / name)
            shutil.copy2(ROOT / 'LICENSE', fake / 'LICENSE')
            path = fake / 'references/approved/bazi-reviewed-structure-v1.md'
            path.write_bytes(path.read_bytes() + b'\nchanged')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                reviewed.load_profile('bazi', 'bazi-reviewed-structure-v1', knowledge.REVIEWED_PROFILES['bazi-reviewed-structure-v1']['records'], root=fake)

    def test_module_sources_cannot_be_laundered_into_general_ledger_rules(self):
        for profile, contract in knowledge.REVIEWED_PROFILES.items():
            rec = next(r for r in self.catalog['records'] if r['profile'] == profile)
            source = next(s for s in self.catalog['sources'] if s['id'] == rec['source_id'])
            rule = dict(locator=source['path'], quote=rec['summary'],
                        start_line=rec['source_span']['start_line'], end_line=rec['source_span']['end_line'],
                        attribution_kind='registered_source_excerpt', source_label=source['citation_label'])
            self.assertTrue(any('module-only' in e for e in knowledge.check_ledger_rule(rule, source, self.catalog)))
            # A renamed copy with identical bytes remains module-only.
            rule['locator'] = 'renamed.md'
            self.assertTrue(any('module-only' in e for e in knowledge.check_ledger_rule(rule, {'sha256': source['sha256']}, self.catalog)))


if __name__ == '__main__':
    unittest.main()
