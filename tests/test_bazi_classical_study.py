import importlib.util
import json
import copy
import hashlib
import shutil
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('knowledge', ROOT / 'scripts/knowledge_catalog.py')
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)


class BaZiStudyTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'knowledge/catalog.json').read_text())

    def test_fixed_sources_integrity_and_license(self):
        self.assertEqual(k.validate(self.data, ROOT), [])
        sources = [s for s in self.data['sources'] if s['id'].startswith('bazi-dts-')]
        self.assertEqual(len(sources), 2)
        for s in sources:
            self.assertEqual(s['revision'], '844410')
            self.assertFalse(s['classical_quote_verified'])
            self.assertIsNone(s['edition'])
            self.assertIn('CC BY-SA 4.0', (ROOT / s['license_path']).read_text())

    def test_study_cards_have_conditions_and_exact_local_locator(self):
        cards = k.query(self.data, 'bazi', 'bazi-classical-study')
        self.assertEqual(len(cards), 10)
        for c in cards:
            for field in ['conditions', 'exclusions', 'actionable_output']:
                self.assertTrue(c[field])
            self.assertEqual(c['license'], 'CC-BY-SA-4.0')
            path, line = c['study_locator'].rsplit(':', 1)
            self.assertTrue((ROOT / path).read_text().splitlines()[int(line)-1].startswith('## '))
        result = k.query(self.data, 'bazi', 'bazi-classical-study', '通关')
        self.assertEqual([r['id'] for r in result], ['bazi-dts-study-tongguan'])
        self.assertFalse(any(r['id'].startswith('bazi-dts-') for r in k.query(self.data, 'bazi', 'bazi-current')))

    def test_new_files_cannot_support_reading_or_classical_quote(self):
        for s in self.data['sources']:
            if not s['id'].startswith('bazi-dts-'):
                continue
            for line in [1, len((ROOT / s['path']).read_text().splitlines())]:
                rule = dict(locator=s['path'], start_line=line, end_line=line,
                            attribution_kind='registered_source_excerpt', source_label=s['citation_label'])
                self.assertTrue(any('quarantined' in e for e in k.check_ledger_rule(rule, s, self.data)))
            with self.assertRaises(ValueError):
                k.citation(self.data, ROOT, s['id'], 'classical_quote', 1, 1)

    def test_only_short_quotes_are_redistributed(self):
        p = ROOT / 'references/vendor/wikisource-ditiansui/short-excerpts.md'
        quotes = [line.split('：', 1)[1] for line in p.read_text().splitlines() if line.startswith('- ')]
        self.assertEqual(len(quotes), 10)
        self.assertEqual(sum(map(len, quotes)), 88)
        self.assertFalse(list(p.parent.glob('*.txt')))


    def test_export_carries_standalone_attribution_and_license(self):
        for sid in ['bazi-dts-short-excerpts', 'bazi-dts-study-cards']:
            exported = k.citation(self.data, ROOT, sid, 'source_excerpt', 1, 5)
            for key in ['license_id', 'license_url', 'attribution', 'contributors_url',
                        'change_notice', 'license_path', 'license_scope', 'license_notice',
                        'revision', 'upstream_url']:
                self.assertTrue(exported[key])
            self.assertEqual(exported['license_id'], 'CC-BY-SA-4.0')
            self.assertIn('action=history', exported['contributors_url'])
            self.assertIn('MIT', exported['license_notice'])
            self.assertIn('844410', exported['upstream_url'])
            self.assertIn('not an authenticated', exported['warning'])
        altered = copy.deepcopy(self.data)
        next(s for s in altered['sources'] if s['id'] == 'bazi-dts-study-cards').pop('attribution')
        self.assertTrue(any('missing redistribution attribution' in e for e in k.validate(altered, ROOT)))

    def test_packet_guard_checks_all_files_and_aggregate_quotes(self):
        packet = self.data['quotation_packets'][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = ROOT / packet['manifest_path']
            target = root / packet['manifest_path']
            shutil.copytree(original.parent, target.parent)
            self.assertEqual(k.validate_quotation_packet(root, packet), [])
            # Unknown extension and nested locations cannot escape the inventory.
            extra = target.parent / 'nested' / 'unreviewed.html'
            extra.parent.mkdir()
            extra.write_text('arbitrary extra quotation')
            self.assertIn('unreviewed', ' '.join(k.validate_quotation_packet(root, packet)))
            # Even registering a second quotation file cannot evade the aggregate cap.
            m = json.loads(target.read_text())
            extra.write_text('quote: extra')
            m['files']['nested/unreviewed.html'] = dict(
                sha256=hashlib.sha256(extra.read_bytes()).hexdigest(),
                quote_spans=[dict(line=1, prefix='quote: ')])
            target.write_text(json.dumps(m))
            edited_packet = dict(packet, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertIn('aggregate quotation budget exceeded',
                          ' '.join(k.validate_quotation_packet(root, edited_packet)))
            # Undeclared quotation additions to an existing non-quote file fail closed too.
            extra.unlink()
            target.write_bytes(original.read_bytes())
            card = target.parent / 'study-cards.md'
            card.write_text(card.read_text() + '\nnew unreviewed text')
            self.assertIn('unreviewed bytes', ' '.join(k.validate_quotation_packet(root, packet)))



if __name__ == '__main__':
    unittest.main()
