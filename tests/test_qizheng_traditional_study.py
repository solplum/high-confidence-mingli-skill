import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qizheng_traditional_study as study


def fixture():
    return study.load_registry()


class TraditionalStudyTests(unittest.TestCase):
    def setUp(self):
        self.registry = fixture()

    def run_rule(self, rid, facts):
        return study.evaluate(rid, facts, self.registry)

    def test_actual_registry_validates(self):
        self.assertEqual(study.validate(study.load_registry()), [])

    def test_palace_branch_not_lord(self):
        result = self.run_rule('QZT01', {'branch': '子'})
        self.assertEqual(result['calculation'], {'zhi': '子', 'branch_element': '水',
                         'palace_lord': '土', 'palace_lord_element': '土'})
        self.assertFalse(result['classical_quote_authorized'])
        self.assertFalse(result['personal_ledger_authorized'])
        self.assertTrue(result['conditions'])
        self.assertTrue(result['counterconditions'])
        self.assertTrue(result['sources'][0]['url'].startswith('https://'))
        self.assertTrue(result['source_locators'])

    def test_all_palaces_and_invalid_branches(self):
        for branch in study.BRANCHES:
            self.assertEqual(self.run_rule('QZT01', {'branch': branch})['status'], 'conditional_study')
        for branch in ('', '子丑', True, 0, [], {}, None):
            self.assertEqual(self.run_rule('QZT01', {'branch': branch})['status'], 'withheld')

    def test_dignity_always_withheld_not_numerical(self):
        for term in ('庙', '乐', '垣'):
            result = self.run_rule('QZT02', {'term': term, 'scheme': 'unresolved-legacy-compilation'})
            self.assertEqual(result['reason_code'], 'terminology_conflict')
            self.assertEqual(result['status'], 'withheld')
            self.assertNotIn('calculation', result)
        result = self.run_rule('QZT02', {'term': '庙', 'scheme': 'universal'})
        self.assertEqual(result['reason_code'], 'invalid_or_missing_requirements')

    def aspect_facts(self):
        return dict(longitude_a=359, longitude_b=1, branch_a='子', branch_b='午',
                    coordinate_frame='ecliptic-of-date')

    def test_angular_and_branch_relations_are_separate(self):
        result = self.run_rule('QZT03', self.aspect_facts())['calculation']
        self.assertEqual(result['separation_degrees'], 2)
        self.assertEqual(result['angular_residuals_degrees']['180'], 178)
        self.assertIn('对宫', result['branch_relations'])
        self.assertEqual(result['angular_contact_judgment'], 'not_evaluated_no_orb_contract')
        facts = self.aspect_facts()
        facts.update(longitude_a=0, longitude_b=120, branch_a='卯', branch_b='亥')
        result = self.run_rule('QZT03', facts)['calculation']
        self.assertEqual(result['angular_residuals_degrees']['120'], 0)
        self.assertEqual(result['branch_relations'], ['三方'])

    def test_reject_invalid_numbers_and_frames(self):
        for value in (True, False, float('nan'), float('inf'), -float('inf'), -1, 360, '90', None, [], 10**400):
            facts = self.aspect_facts()
            facts['longitude_a'] = value
            self.assertEqual(self.run_rule('QZT03', facts)['status'], 'withheld', repr(value))
        facts = self.aspect_facts()
        facts['coordinate_frame'] = 'mixed'
        self.assertEqual(self.run_rule('QZT03', facts)['status'], 'withheld')
        facts = self.aspect_facts()
        facts['orb'] = 8
        self.assertEqual(self.run_rule('QZT03', facts)['status'], 'withheld')

    def test_natal_palace_and_limit_mansion_never_combined(self):
        natal = dict(context='natal', reference_basis='palace_lord', branch='寅', other_element='火')
        limit = dict(context='limit', reference_basis='mansion_lord', mansion='房', other_element='火')
        nr = self.run_rule('QZT04', natal)['calculation']
        lr = self.run_rule('QZT05', limit)['calculation']
        self.assertEqual((nr['reference_element'], nr['relation']), ('木', '我生'))
        self.assertEqual((lr['reference_element'], lr['relation']), ('火', '同我'))
        self.assertNotIn('恩', json.dumps(nr, ensure_ascii=False))
        self.assertEqual(self.run_rule('QZT04', limit)['status'], 'withheld')
        self.assertEqual(self.run_rule('QZT05', natal)['status'], 'withheld')
        for field in natal:
            altered = dict(natal)
            del altered[field]
            self.assertEqual(self.run_rule('QZT04', altered)['status'], 'withheld')
        for field, value in [('context', 'limit'), ('reference_basis', 'mansion_lord'), ('other_element', True)]:
            altered = dict(natal, **{field: value})
            self.assertEqual(self.run_rule('QZT04', altered)['status'], 'withheld')

    def test_all_mansions_and_relations(self):
        expected = {'木': '同我', '火': '我生', '土': '我克', '金': '克我', '水': '生我'}
        for element, relation in expected.items():
            result = self.run_rule('QZT05', dict(context='limit', reference_basis='mansion_lord',
                                               mansion='角', other_element=element))
            self.assertEqual(result['calculation']['relation'], relation)
        for mansion in study.MANSION_LORDS:
            self.assertEqual(self.run_rule('QZT05', dict(context='limit', reference_basis='mansion_lord',
                                                       mansion=mansion, other_element='水'))['status'], 'conditional_study')

    def test_registry_drives_selection_and_provenance(self):
        self.assertEqual(self.run_rule('QZT01', {'branch': '子'})['conditions'],
                         self.registry['rule_cards'][0]['conditions'])
        altered = copy.deepcopy(self.registry)
        altered['rule_cards'][0]['conditions'] = ['self-certified new condition']
        self.assertEqual(study.evaluate('QZT01', {'branch': '子'}, altered)['reason_code'], 'invalid_registry')
        self.registry['rule_cards'][0]['selector'] = 'qianyuan_limit_mansion'
        self.assertEqual(self.run_rule('QZT01', {'branch': '子'})['reason_code'], 'invalid_registry')

    def test_unknown_and_malformed_registry_fail_closed(self):
        for rule_id in ('UNKNOWN', None, [], True):
            self.assertEqual(self.run_rule(rule_id, {})['status'], 'withheld')
        mutations = [lambda d: d.update(schema_version=True),
                     lambda d: d['rule_cards'].pop(),
                     lambda d: d['rule_cards'].append(copy.deepcopy(d['rule_cards'][0])),
                     lambda d: d['rule_cards'][0].update(source_ids=['unknown']),
                     lambda d: d['rule_cards'][0].update(id='UNKNOWN'),
                     lambda d: d['rule_cards'][0].update(conditions=[]),
                     lambda d: d['sources'][0].update(classical_quote_authorized=True),
                     lambda d: d['sources'][0].update(url=None)]
        mutations.extend([lambda d: d['sources'][0].update(kind='authenticated_classic'),
                          lambda d: d['rule_cards'][0].update(personal_ledger_authorized=True),
                          lambda d: d['rule_cards'][0].update(source_ids=['project-editorial'])])
        for mutate in mutations:
            registry = fixture()
            mutate(registry)
            self.assertTrue(study.validate(registry))
            self.assertEqual(study.evaluate('QZT01', {'branch': '子'}, registry)['status'], 'withheld')
        for data in (None, [], True, {}, {'sources': [None]}):
            self.assertTrue(study.validate(data))

    def test_all_registered_examples(self):
        for card in self.registry['rule_cards']:
            result = self.run_rule(card['id'], card['positive_example'])
            expected = 'withheld' if card['id'] == 'QZT02' else 'conditional_study'
            self.assertEqual(result['status'], expected, card['id'])
            self.assertEqual(self.run_rule(card['id'], card['counterexample'])['status'], 'withheld')
            for field in card['positive_example']:
                incomplete = dict(card['positive_example'])
                del incomplete[field]
                self.assertEqual(self.run_rule(card['id'], incomplete)['status'], 'withheld')

    def test_file_lock_and_nonfinite_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'altered.json'
            path.write_text(json.dumps(self.registry), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'evidence lock'):
                study.load_registry(path)
        self.registry['unexpected'] = float('nan')
        self.assertEqual(self.run_rule('QZT01', {'branch': '子'})['reason_code'], 'invalid_registry')

    def test_text_reading_preserves_specific_facts_and_sources(self):
        result = self.run_rule('QZT01', {'branch': '卯'})
        self.assertEqual(result['title'], self.registry['rule_cards'][0]['title'])
        self.assertEqual(result['plain_language'], self.registry['rule_cards'][0]['plain_language'])
        text = study.format_reading(result)
        for expected in ('卯宫', '地支五行木', '宫主火', '条件：', '反条件：', '来源：', '定位：',
                         '数字转录，未对影像校勘', 'https://'):
            self.assertIn(expected, text)
        facts = self.aspect_facts()
        facts.update(longitude_a=10, longitude_b=185)
        text = study.format_reading(self.run_rule('QZT03', facts))
        self.assertIn('黄经差：175°', text)
        self.assertIn('180°目标差5°', text)
        self.assertIn('对宫', text)
        self.assertNotIn('sha256', text)
        natal = study.format_reading(self.run_rule('QZT04', dict(context='natal',
                    reference_basis='palace_lord', branch='卯', other_element='金')))
        self.assertIn('地支五行木', natal)
        self.assertIn('宫主火', natal)
        self.assertIn('我克', natal)

    def test_text_cli_invalid_inputs_exit_one(self):
        script = str(ROOT / 'scripts/qizheng_traditional_study.py')
        for facts in ('{}', 'invalid json', '{"branch":true}'):
            proc = subprocess.run([sys.executable, script, 'evaluate', '--rule-id', 'QZT01',
                                   '--facts', facts, '--format', 'text'], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn('暂不判定', proc.stdout)
            self.assertIn('未判原因', proc.stdout)
        proc = subprocess.run([sys.executable, script, 'evaluate', '--rule-id', 'QZT01',
                               '--facts', '{"branch":"卯"}', '--format', 'text'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('地支五行木', proc.stdout)
        self.assertIn('宫主火', proc.stdout)

    def test_facts_parser_rejects_duplicate_keys_at_every_depth(self):
        for raw in ('{"branch":"子","branch":"卯"}',
                    '{"branch":"子","branch":"子"}',
                    '{"nested":{"x":1,"x":2}}',
                    '{"branch":"子","br\\u0061nch":"卯"}'):
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                study.parse_facts_json(raw)
        for raw in ('{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
            with self.assertRaisesRegex(ValueError, 'non-finite'):
                study.parse_facts_json(raw)
        self.assertEqual(study.parse_facts_json('{"branch":"卯"}'), {'branch': '卯'})
        self.assertEqual(study.evaluate('QZT01', {'branch': '卯'})['status'], 'conditional_study')

    def test_duplicate_keys_fail_cli_inline_and_file(self):
        script = str(ROOT / 'scripts/qizheng_traditional_study.py')
        raw = '{"branch":"子","branch":"卯"}'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'facts.json'
            path.write_text(raw, encoding='utf-8')
            for facts in (raw, '@' + str(path)):
                for fmt in ('json', 'text'):
                    proc = subprocess.run([sys.executable, script, 'evaluate', '--rule-id',
                                           'QZT01', '--facts', facts, '--format', fmt],
                                          capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                    self.assertIn('duplicate JSON key', proc.stdout)
                    if fmt == 'json':
                        self.assertEqual(json.loads(proc.stdout)['status'], 'withheld')

    def test_license_scope_is_explicit(self):
        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        for name in ('knowledge/qizheng-traditional-study.json',
                     'docs/qizheng-traditional-study.md',
                     'knowledge/licenses/qizheng-study-CC-BY-SA-4.0.txt'):
            self.assertIn(name, license_text)
        self.assertIn('generated JSON or text readings', license_text)
        self.assertIn('evaluator and tests', license_text)
        text = study.format_reading(study.evaluate('QZT01', {'branch': '卯'}))
        self.assertIn('https://creativecommons.org/licenses/by-sa/4.0/legalcode', text)
        self.assertIn('贡献历史：', text)
        self.assertIn('改编说明：', text)

    def test_cli_validate_and_evaluate(self):
        script = str(ROOT / 'scripts/qizheng_traditional_study.py')
        proc = subprocess.run([sys.executable, script, 'validate'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = subprocess.run([sys.executable, script, 'evaluate', '--rule-id', 'QZT01',
                               '--facts', '{"branch":"子"}'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'], 'conditional_study')
        proc = subprocess.run([sys.executable, script, 'evaluate', '--rule-id', 'QZT01',
                               '--facts', '{}'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)['status'], 'withheld')


if __name__ == '__main__':
    unittest.main()
