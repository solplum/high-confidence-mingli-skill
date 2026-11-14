import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('knowledge', ROOT / 'scripts/knowledge_catalog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())

    def test_catalog_integrity(self):
        self.assertEqual(module.validate(self.catalog, ROOT), [])

    def test_legacy_bytes_unchanged(self):
        import hashlib
        for src in json.loads((ROOT / 'knowledge/legacy-manifest.json').read_text()):
            self.assertEqual(hashlib.sha256((ROOT / src['path']).read_bytes()).hexdigest(), src['sha256'])

    def test_query_is_useful_and_filtered(self):
        matches = module.query(self.catalog, 'ziwei', 'ziwei-fixed-natal', '三方四正')
        self.assertEqual([r['id'] for r in matches], ['ziwei-three-four'])
        self.assertEqual(module.query(self.catalog, 'ziwei', 'ziwei-flying', '四化'), [])
        self.assertEqual(module.query(self.catalog, 'bazi', 'ziwei-fixed-natal'), [])
        self.assertEqual(module.query(self.catalog, 'ziwei', 'ziwei-fixed-natal', '紫微化忌'), [])

    def test_existing_rule_identifiers_resolve_within_their_profiles(self):
        cases = [
            ('ziwei', 'ziwei-dynamic-reading-v1', 'ZW-Q01', ['ziwei-dynamic-ZW-Q01']),
            ('ziwei', 'ziwei-reviewed-structure-v1', 'ZW-K05',
             ['ziwei-reviewed-ZW-K05-attachment', 'ziwei-reviewed-ZW-K05-lu']),
            ('bazi', 'bazi-judgment-v1', 'BJ08', ['bazi-judgment-BJ08']),
            ('bazi', 'bazi-qiong-xin-zi-v1', 'BZ-QX02', ['bazi-qiong-QX02']),
        ]
        for system, profile, rule_id, record_ids in cases:
            with self.subTest(rule_id=rule_id):
                matches = module.query(self.catalog, system, profile, rule_id)
                self.assertEqual([r['id'] for r in matches], record_ids)
                for record in matches:
                    self.assertEqual(module.query(self.catalog, system, profile, record['id']), [record])
                self.assertEqual(module.query(self.catalog, system, profile, rule_id.lower()), matches)

    def test_identifier_lookup_keeps_system_profile_and_status_filters(self):
        profile = 'ziwei-dynamic-reading-v1'
        self.assertEqual(module.query(self.catalog, 'bazi', profile, 'ZW-Q01'), [])
        self.assertEqual(module.query(self.catalog, 'ziwei', 'ziwei-fixed-natal', 'ZW-Q01'), [])
        self.assertEqual(module.query(self.catalog, 'ziwei', 'unknown-profile', 'ZW-Q01'), [])
        altered = copy.deepcopy(self.catalog)
        record = next(r for r in altered['records'] if r.get('rule_id') == 'ZW-Q01')
        record['status'] = 'quarantined'
        self.assertEqual(module.query(altered, 'ziwei', profile, 'ZW-Q01'), [])
        self.assertEqual(module.query(altered, 'ziwei', profile, record['id']), [])

    def test_officer_luck_stays_in_the_approved_manual_profile(self):
        profile = 'bazi-officer-luck-v1'
        record, = module.query(self.catalog, 'bazi', profile, '卯大运')
        self.assertEqual(record['id'], 'bazi-officer-luck-OL01')
        self.assertEqual(module.query(self.catalog, 'bazi', profile, 'BZ-OL01'), [record])
        self.assertEqual(module.query(self.catalog, 'bazi', 'bazi-judgment-v1', 'BZ-OL01'), [])
        source = next(s for s in self.catalog['sources'] if s['id'] == record['source_id'])
        rule = dict(locator=source['path'], attribution_kind='registered_source_excerpt',
                    source_label=source['citation_label'], **record['source_span'])
        errors = module.check_ledger_rule(rule, source, self.catalog)
        self.assertTrue(any('not authorized as a general ledger rule' in error for error in errors))

    def test_chou_natal_rule_stays_in_the_approved_manual_profile(self):
        profile = 'bazi-qiong-xin-chou-v1'
        record, = module.query(self.catalog, 'bazi', profile)
        self.assertEqual(record['rule_id'], 'BZ-QXC01')
        self.assertEqual(module.query(self.catalog, 'bazi', profile, '专业发展'), [record])
        self.assertEqual(module.query(self.catalog, 'bazi', 'bazi-qiong-xin-zi-v1', 'BZ-QXC01'), [])
        self.assertEqual(module.query(self.catalog, 'ziwei', profile, 'BZ-QXC01'), [])
        source = next(s for s in self.catalog['sources'] if s['id'] == record['source_id'])
        rule = dict(locator=source['path'], attribution_kind='registered_source_excerpt',
                    source_label=source['citation_label'], **record['source_span'])
        errors = module.check_ledger_rule(rule, source, self.catalog)
        self.assertTrue(any('not authorized as a general ledger rule' in error for error in errors))

    def test_life_domains_are_discoverable_from_user_topics(self):
        profile = 'ziwei-life-domains-v1'
        for topic, rule_id in [('感情', 'ZW-D02'), ('健康', 'ZW-D04'),
                               ('一生', 'ZW-T02'), ('兄弟姐妹', 'ZW-D01'),
                               ('家庭', 'ZW-D06'), ('交友', 'ZW-D05')]:
            with self.subTest(topic=topic):
                matches = module.query(self.catalog, 'ziwei', profile, topic)
                self.assertIn(rule_id, [r['rule_id'] for r in matches])
                self.assertTrue(all(r['profile'] == profile for r in matches))

    def test_lianfu_marriage_rule_stays_in_the_approved_manual_profile(self):
        profile = 'ziwei-lianfu-marriage-v1'
        record, = module.query(self.catalog, 'ziwei', profile, 'ZW-RL02')
        self.assertEqual(record['id'], 'ziwei-lianfu-marriage-ZW-RL02')
        self.assertEqual(module.query(self.catalog, 'ziwei', profile, '长期婚姻'), [record])
        self.assertEqual(module.query(self.catalog, 'bazi', profile, 'ZW-RL02'), [])
        for other in ('ziwei-stage-relationship-v1', 'ziwei-judgment-cases-v1'):
            self.assertEqual(module.query(self.catalog, 'ziwei', other, 'ZW-RL02'), [])
        source = next(s for s in self.catalog['sources'] if s['id'] == record['source_id'])
        rule = dict(locator=source['path'], attribution_kind='registered_source_excerpt',
                    source_label=source['citation_label'], **record['source_span'])
        errors = module.check_ledger_rule(rule, source, self.catalog)
        self.assertTrue(any('not authorized as a general ledger rule' in error for error in errors))

    def test_unverified_classical_quotes_refused(self):
        for src in self.catalog['sources']:
            with self.assertRaisesRegex(ValueError, 'refused'):
                module.citation(self.catalog, ROOT, src['id'], 'classical_quote', 1, 1)

    def test_excerpt_honestly_labeled(self):
        result = module.citation(self.catalog, ROOT, 'iztro-docs-palace', 'source_excerpt', 376, 378)
        self.assertIn('三方四正', result['text'])
        self.assertIn('现代说明', result['label'])
        self.assertIn('not an authenticated', result['warning'])

    def test_bad_source_hash(self):
        self.catalog['sources'][0]['sha256'] = '0' * 64
        self.assertTrue(any('hash mismatch' in s for s in module.validate(self.catalog, ROOT)))

    def test_fake_verification_is_rejected(self):
        self.catalog['sources'][0]['classical_quote_verified'] = True
        self.assertTrue(any('edition' in s for s in module.validate(self.catalog, ROOT)))

    def test_duplicate_and_cross_system(self):
        self.catalog['records'][0]['system'] = 'ziwei'
        self.catalog['sources'].append(copy.deepcopy(self.catalog['sources'][0]))
        errors = module.validate(self.catalog, ROOT)
        self.assertTrue(any('Duplicate source' in s for s in errors))
        self.assertTrue(any('cross-system' in s for s in errors))

    def test_paths_and_excerpt_limits(self):
        for path in ['/etc/passwd', '../escape']:
            with self.assertRaises(ValueError):
                module.local_file(ROOT, path)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'link').symlink_to(ROOT / 'SKILL.md')
            with self.assertRaises(ValueError):
                module.local_file(d, 'link')
        for start, end in [(True, 1), (0, 1), (2, 1), (1, 30)]:
            with self.assertRaises(ValueError):
                module.citation(self.catalog, ROOT, 'ziwei-classics', 'source_excerpt', start, end)

    def test_all_workflows_have_gate(self):
        for path in [ROOT / 'SKILL.md', *(ROOT / 'workflows').glob('*.md'), ROOT / 'references/README.md']:
            self.assertIn('knowledge/README.md', path.read_text())

    def test_ledger_renamed_hash_still_requires_attribution(self):
        source = next(s for s in self.catalog['sources'] if s['id'] == 'ziwei-classics')
        rule = dict(locator='renamed.md:20', quote='紫微化忌主受制于人', start_line=20, end_line=20)
        errors = module.check_ledger_rule(rule, {'sha256': source['sha256']}, self.catalog)
        self.assertTrue(any('attribution_kind' in e for e in errors))
        self.assertTrue(any('quarantined' in e for e in errors))
        rule.update(attribution_kind='registered_source_excerpt', source_label=source['citation_label'])
        self.assertTrue(any('quarantined' in e for e in module.check_ledger_rule(rule, source, self.catalog)))

    def test_ledger_clean_excerpt_works(self):
        source = next(s for s in self.catalog['sources'] if s['id'] == 'bazi-wuxing-tables')
        rule = dict(locator='references/bazi/wuxing-tables.md:1',quote='test',start_line=1,end_line=1,attribution_kind='registered_source_excerpt',source_label=source['citation_label'])
        self.assertEqual(module.check_ledger_rule(rule, source, self.catalog), [])

class LedgerKnowledgeIntegrationTests(unittest.TestCase):
    def test_real_fixture_requires_source_attribution(self):
        spec = importlib.util.spec_from_file_location('ledger_knowledge', ROOT / 'scripts/validate_claim_ledger.py')
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        data = json.loads((ROOT / 'examples/engine-reading/ledger.json').read_text())
        self.assertEqual(ledger.validate(data, ROOT / 'examples/engine-reading'), [])
        data['rules'][0].pop('attribution_kind')
        self.assertTrue(any('attribution_kind' in e for e in ledger.validate(data, ROOT / 'examples/engine-reading')))


class ProvenanceBypassRegressionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('ledger_bypass', ROOT / 'scripts/validate_claim_ledger.py')
        self.ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ledger)
        self.data = json.loads((ROOT / 'examples/engine-reading/ledger.json').read_text())
        self.data['purpose'] = 'reading'

    def test_partial_quarantined_quote_is_blocked(self):
        self.data['rules'][1].update(start_line=20, end_line=20, quote='紫微化忌', locator='references/ziwei/classics.md:20')
        self.assertTrue(any('quarantined source range' in e for e in self.ledger.validate(self.data, ROOT / 'examples/engine-reading')))

    def test_whole_isolated_paragraph_blocked_conservatively(self):
        self.data['rules'][1].update(start_line=20, end_line=20, quote='紫微化权主独断', locator='references/ziwei/classics.md:20')
        self.assertTrue(any('quarantined source range' in e for e in self.ledger.validate(self.data, ROOT / 'examples/engine-reading')))

    def test_unknown_renamed_modified_source_cannot_claim_verified(self):
        import hashlib
        import shutil
        with tempfile.TemporaryDirectory() as d:
            evidence = Path(d) / 'evidence'
            shutil.copytree(ROOT / 'examples/engine-reading', evidence)
            rule = self.data['rules'][0]
            src = next(s for s in self.data['sources'] if s['id'] == rule['source_id'])
            raw = (evidence / src['path']).read_bytes() + b'\n'
            (evidence / 'unknown.md').write_bytes(raw)
            src.update(path='unknown.md', sha256=hashlib.sha256(raw).hexdigest())
            rule.update(locator='unknown.md:22',source_label='Original ancient text verified')
            rule.pop('attribution_kind')
            errors = self.ledger.validate(self.data, evidence)
            self.assertTrue(any('caller_declared_unverified' in e for e in errors))
            rule.update(attribution_kind='caller_declared_unverified',source_label='调用方提供的未核验资料（非核验古籍原文）')
            self.assertEqual(self.ledger.validate(self.data, evidence), [])

    def test_self_signed_edition_never_enables_classical_quote(self):
        catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())
        src = catalog['sources'][0]
        src.update(kind='classical_edition',classical_quote_verified=True,edition='invented edition',verification_record='SKILL.md')
        self.assertTrue(any('self-declared' in e for e in module.validate(catalog, ROOT)))
        with self.assertRaisesRegex(ValueError, 'no externally verified editions'):
            module.citation(catalog, ROOT, src['id'], 'classical_quote', 1, 1)

    def test_quarantine_cannot_drop_its_source_range(self):
        catalog = json.loads((ROOT / 'knowledge/catalog.json').read_text())
        next(r for r in catalog['records'] if r['status'] == 'quarantined').pop('source_span')
        self.assertTrue(any('source_span required' in e for e in module.validate(catalog, ROOT)))



class ImportedKnowledgeExampleTests(unittest.TestCase):
    def test_imported_source_example_binds_real_fields(self):
        spec = importlib.util.spec_from_file_location('imported_ledger', ROOT / 'scripts/validate_claim_ledger.py')
        ledger_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger_module)
        data = json.loads((ROOT / 'examples/imported-knowledge/ledger.json').read_text())
        self.assertEqual(ledger_module.validate(data, ROOT), [])
        self.assertEqual(len(data['facts']), 4)
        self.assertEqual(data['rules'][0]['attribution_kind'], 'registered_source_excerpt')
        self.assertIn('references/vendor/iztro-docs/', data['sources'][1]['path'])
        snapshot = json.loads((ROOT / data['sources'][0]['path']).read_text())
        self.assertIsNotNone(snapshot['ziwei'])
        self.assertEqual(len({f['value']['branch'] for f in data['facts']}), 4)
        data['rules'][0]['source_label'] = 'Verified ancient original'
        self.assertTrue(any('source_label' in error for error in ledger_module.validate(data, ROOT)))

if __name__ == '__main__':
    unittest.main()
