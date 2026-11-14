"""Structural regressions; fixtures are synthetic and never predictive evidence."""
import copy
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
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

    def test_duplicate_keys_in_ledger_or_chart_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'ledger.json'
            clean = json.dumps(self.data, ensure_ascii=False)
            (root / 'chart.json').write_bytes((self.root / 'chart.json').read_bytes())
            (root / 'rules.md').write_bytes((self.root / 'rules.md').read_bytes())
            command = [sys.executable, '-B', str(ROOT / 'scripts/validate_claim_ledger.py'),
                       str(path), '--root', str(root)]

            path.write_text(clean, encoding='utf-8')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            path.write_text(clean.replace('"pointer": "/ziwei/palace"',
                                          '"pointer": "/ziwei/other", "pointer": "/ziwei/palace"'),
                            encoding='utf-8')
            proc = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("duplicate JSON object key: 'pointer'", json.loads(proc.stdout)['input_error'])

            ambiguous = '{"bazi":{"day_pillar":"甲子"},"ziwei":{"palace":"其他","palace":"命宫"}}'.encode('utf-8')
            (root / 'chart.json').write_bytes(ambiguous)
            for source in self.data['sources']:
                if source['kind'] == 'chart':
                    source['sha256'] = hashlib.sha256(ambiguous).hexdigest()
            path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
            proc = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("chart-ziwei: invalid chart JSON: duplicate JSON object key: 'palace'",
                          json.loads(proc.stdout)['errors'])

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

    def test_combined_snapshot_known_system_cannot_be_relabeled_with_its_source(self):
        root = ROOT / 'examples/engine-reading'
        ledger = json.loads((root / 'ledger.json').read_text())
        self.assertEqual(module.validate(ledger, root), [])
        ledger['claims'] = ledger['claims'][:1]
        ledger['syntheses'] = []
        ledger['sources'] = [row for row in ledger['sources'] if row['id'] != 'summer-ziwei']
        ledger['facts'] = [row for row in ledger['facts'] if row['source_id'] != 'summer-ziwei']
        source = next(row for row in ledger['sources'] if row['id'] == 'summer-bazi')
        source['pointer_prefix'] = '/ziwei'
        chart = json.loads((root / 'summer.json').read_text())
        for fact in ledger['facts']:
            if fact['source_id'] == source['id']:
                fact.update(pointer='/ziwei/chart/mingGongBranch', value=chart['ziwei']['chart']['mingGongBranch'])
        errors = module.validate(ledger, root)
        self.assertTrue(errors)
        self.assertTrue(all('combined snapshot section belongs to ziwei' in error for error in errors))
        with tempfile.TemporaryDirectory() as folder:
            old_root = Path(folder)
            for path in {row['path'] for row in ledger['sources']} - {source['path']}:
                (old_root / path).write_bytes((root / path).read_bytes())
            for key in ('time', 'provenance', 'degradation'):
                del chart[key]
            raw = json.dumps(chart, ensure_ascii=False).encode('utf-8')
            (old_root / source['path']).write_bytes(raw)
            for row in ledger['sources']:
                if row['path'] == source['path']:
                    row['sha256'] = hashlib.sha256(raw).hexdigest()
            self.assertEqual(module.validate(ledger, old_root), errors)

    def test_scenario_fact_cannot_be_relabeled(self):
        self.data['scenarios'].append(dict(id='alternate',label='边界',time_basis='另一口径',assumptions='待检'))
        fact = copy.deepcopy(self.data['facts'][0])
        fact.update(id='alternate-fact',scenario_id='alternate')
        self.data['facts'].append(fact)
        self.data['claims'][0].update(status='supported',boundary='stable',scenario_ids=['base','alternate'],fact_ids=['bazi-fact','alternate-fact'])
        self.assertTrue(any('scenario binding mismatch' in x for x in self.errors()))

    def test_exact_combined_snapshots_must_share_one_birth_instant_per_scenario(self):
        archived = ROOT / 'examples/engine-reading'
        first = json.loads((archived / 'summer.json').read_text())
        later = json.loads((archived / 'after-zi.json').read_text())
        sources = {row['system']: row for row in self.data['sources'] if row['kind'] == 'chart'}
        facts = {row['system']: row for row in self.data['facts']}
        joint = self.data['syntheses'][0]
        joint['relation'] = 'agreement'
        self.data['scenarios'].append(dict(id='later', label='另一已知时刻', time_basis='civil', assumptions='合成对照'))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'rules.md').write_bytes((self.root / 'rules.md').read_bytes())

            def attach(system, snapshot, scenario='base'):
                path = root / (system + '.json')
                payload = json.dumps(snapshot, ensure_ascii=False).encode('utf-8')
                path.write_bytes(payload)
                sources[system].update(path=path.name, sha256=hashlib.sha256(payload).hexdigest(),
                                       scenario_id=scenario)
                pointer, value = (
                    ('/bazi/pillars/day', snapshot['bazi']['pillars']['day']) if system == 'bazi' else
                    ('/ziwei/chart/mingGongBranch', snapshot['ziwei']['chart']['mingGongBranch']))
                facts[system].update(pointer=pointer, value=value, scenario_id=scenario)
                claim = next(row for row in self.data['claims'] if row['system'] == system)
                claim['scenario_ids'] = [scenario]

            attach('bazi', first)
            attach('ziwei', later)
            errors = module.validate(self.data, root)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('conflicts with', errors[0])
            self.assertIn('exact birth instant for scenario base', errors[0])

            alias = copy.deepcopy(first)
            alias['input'].update(hour='04:00', utc_offset=0)
            alias['time']['civil'] = '2000-05-15T04:00:00Z'
            attach('ziwei', alias)
            self.assertEqual(module.validate(self.data, root), [])

            other_basis = copy.deepcopy(first)
            other_basis['input']['time_basis'] = 'mean-solar'
            attach('ziwei', other_basis)
            errors = module.validate(self.data, root)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('selected chart time basis for scenario base', errors[0])

            other_clock = copy.deepcopy(first)
            other_clock['time']['chart_clock'] = '2000-05-15T13:00:00'
            attach('ziwei', other_clock)
            errors = module.validate(self.data, root)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('selected chart minute for scenario base', errors[0])
            other_clock['time']['chart_clock'] = '2000-05-15T12:00:59.9'
            attach('ziwei', other_clock)
            self.assertEqual(module.validate(self.data, root), [])

            other_native_clock = copy.deepcopy(first)
            del other_native_clock['time']
            other_native_clock['ziwei']['input']['shichenIndex'] = 8
            attach('ziwei', other_native_clock)
            errors = module.validate(self.data, root)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('selected chart date and shichen for scenario base', errors[0])

            mean = copy.deepcopy(other_basis)
            mean['time']['mean_solar'] = mean['time']['chart_clock']
            attach('bazi', mean)
            archived = copy.deepcopy(mean)
            del archived['time']['chart_clock']
            attach('ziwei', archived)
            self.assertEqual(module.validate(self.data, root), [])
            archived['time']['mean_solar'] = '2000-05-15T13:00:00'
            attach('ziwei', archived)
            errors = module.validate(self.data, root)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('selected chart minute for scenario base', errors[0])
            attach('bazi', first)

            different_sex = copy.deepcopy(first)
            different_sex['input']['sex'] = '女'
            different_sex['ziwei']['input']['gender'] = 'female'
            attach('ziwei', different_sex)
            self.assertTrue(any('birth sex for BaZi/Ziwei' in error for error in module.validate(self.data, root)))
            del different_sex['input']['sex']
            attach('ziwei', different_sex)
            self.assertTrue(any('birth sex for BaZi/Ziwei' in error for error in module.validate(self.data, root)))
            different_sex['input']['sex'] = '男'
            attach('ziwei', different_sex)
            self.assertTrue(any('saved birth sex disagrees' in error for error in module.validate(self.data, root)))
            attach('ziwei', first)
            self.assertEqual(module.validate(self.data, root), [])

            for label, snapshot, expected in (
                    ('same with no derived time', first, None),
                    ('other with no derived time', later, 'exact birth instant for scenario base')):
                with self.subTest(label=label):
                    old = copy.deepcopy(snapshot)
                    del old['time']
                    attach('ziwei', old)
                    errors = module.validate(self.data, root)
                    if expected is None:
                        self.assertEqual(errors, [])
                    else:
                        self.assertEqual(len(errors), 1, errors)
                        self.assertIn(expected, errors[0])

            copied = copy.deepcopy(first)
            copied['bazi']['birth_dt'] = later['bazi']['birth_dt']
            attach('ziwei', copied)
            self.assertTrue(any('saved clocks and native birth instant disagree' in error
                                for error in module.validate(self.data, root)))
            copied = copy.deepcopy(first)
            copied['input'].update(timezone=None, utc_offset=9)
            attach('ziwei', copied)
            self.assertTrue(any('fixed UTC offset disagrees' in error
                                for error in module.validate(self.data, root)))

            regional = copy.deepcopy(first)
            regional['input']['hour'] = '00:00'
            regional['time'].update(civil='2000-05-15T00:00:00-04:00', iana_zone='America/New_York')
            regional['provenance']['timezone_source'] = dict(zone='America/New_York', kind='host_iana_tzif')
            attach('ziwei', regional)
            self.assertEqual(module.validate(self.data, root), [])
            del regional['time']
            attach('ziwei', regional)
            self.assertEqual(module.validate(self.data, root), [])
            regional['input']['timezone'] = 'Europe/London'
            attach('ziwei', regional)
            self.assertTrue(any('saved timezone or fold disagrees' in error
                                for error in module.validate(self.data, root)))

            uncertain = copy.deepcopy(later)
            uncertain['input']['uncertainty_minutes'] = 2
            attach('ziwei', uncertain)
            self.assertEqual(module.validate(self.data, root), [])

            attach('ziwei', later, 'later')
            joint['relation'] = 'different_scope'
            self.assertEqual(module.validate(self.data, root), [])

    def test_exact_birth_replays_the_saved_iana_rules(self):
        from time_scenarios import iana_query_zone

        try:
            zone = iana_query_zone('America/New_York')
        except ValueError as error:
            self.skipTest(str(error))
        if not getattr(zone, 'tzif_source', {}).get('tzif_sha256'):
            self.skipTest('Requires readable IANA rules for America/New_York')
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '2000-10-29', '--hour', '01:30', '--sex', '男',
                   '--timezone', 'America/New_York', '--fold', '1',
                   '--analysis-year', '2026', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True, timeout=60))
        instant = module.datetime(2000, 10, 29, 6, 30, tzinfo=module.timezone.utc)
        self.assertEqual(module._exact_birth_instant(snapshot), instant)
        wrong = copy.deepcopy(snapshot)
        wrong['input']['fold'] = wrong['time']['fold'] = 0
        with self.assertRaisesRegex(ValueError, 'disagrees with the saved IANA rules'):
            module._exact_birth_instant(wrong)
        del wrong['time']
        with self.assertRaisesRegex(ValueError, 'disagrees with the saved IANA rules'):
            module._exact_birth_instant(wrong)
        wrong['provenance']['timezone_source']['tzif_sha256'] = '0' * 64
        self.assertEqual(module._exact_birth_instant(wrong), instant)
        del snapshot['input']['fold']
        del snapshot['time']['fold']
        self.assertEqual(module._exact_birth_instant(snapshot), instant)

    def test_qizheng_sampling_facts_bind_selected_witness_without_claiming_the_range(self):
        start = module.datetime(2000, 1, 1, tzinfo=module.timezone.utc)
        end = start + module.timedelta(minutes=10)

        def witness(point):
            return dict(witness_utc=point.isoformat(), witness_civil=point.isoformat(),
                        chart=dict(calculation_profile='physical-v2',
                                   jd_utc=2451544.5 + (point - start).total_seconds() / 86400))

        sample = dict(version='qizheng-time-sensitivity-v1', status='sampled_conditional',
                      interval=dict(start_utc=start.isoformat(), end_utc=end.isoformat()),
                      candidates=[witness(start), witness(end)])
        document = dict(version='qizheng-civil-band-sensitivity-v1', status='sampled_conditional',
                        input=dict(profile='physical-v2'), sampled_sections=[dict(sample=sample)],
                        coverage_complete=False)
        prefix = '/sampled_sections/0/sample/candidates'
        first, second = prefix + '/0/chart/jd_utc', prefix + '/1/chart/jd_utc'

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def verify(*pointers, system='qizheng'):
                raw = json.dumps(document).encode('utf-8')
                (root / 'sample.json').write_bytes(raw)
                source = dict(id='sampling', kind='chart', system=system, path='sample.json',
                              scenario_id='base', pointer_prefix='/sampled_sections',
                              sha256=hashlib.sha256(raw).hexdigest())
                facts = [dict(id=f'fact-{i}', system=system, scenario_id='base', source_id='sampling',
                              pointer=pointer, value=module._pointer(document, pointer))
                         for i, pointer in enumerate(pointers)]
                claim = dict(self.data['claims'][0], system=system, status='withheld', boundary='unassessed',
                             fact_ids=[fact['id'] for fact in facts], rule_ids=[], depends_on=[])
                ledger = dict(self.data, sources=[source], facts=facts, claims=[claim], rules=[], syntheses=[])
                return module.validate(ledger, root)

            self.assertEqual(verify(first, prefix + '/0/witness_utc'), [])
            self.assertEqual(verify('/sampled_sections/0/sample/interval', second), [])
            self.assertIn('no common Qizheng birth interval', verify(first, second)[0])
            self.assertIn('standalone snapshot section belongs to qizheng', verify(first, system='bazi')[0])
            sample['candidates'][0]['chart']['jd_utc'] = witness(end)['chart']['jd_utc']
            self.assertIn('Qizheng native UTC Julian day disagrees', verify(first)[0])
            sample['candidates'][0] = witness(end + module.timedelta(minutes=1))
            self.assertIn('outside its recorded sample range', verify(first)[0])

            sample['candidates'][0] = witness(start)
            section = document['sampled_sections'][0]
            section.update(start_utc=start.isoformat(),
                           end_exclusive_utc=(end + module.timedelta(microseconds=1)).isoformat())
            document['input'].update(birth_date='2000-01-01', utc_offset_hours=0,
                                     start_inclusive='00:00', end_exclusive='00:11')
            self.assertEqual(verify(first, prefix + '/0/witness_utc'), [])
            document['input']['start_inclusive'] = '00:05'
            self.assertIn('outside the original civil birth range', verify(first)[0])
            section['start_utc'] = (start + module.timedelta(minutes=5)).isoformat()
            self.assertIn('disagrees with its civil section', verify(first)[0])

            from qizheng_sensitivity import compare_civil_band

            def located(lon):
                return compare_civil_band(date(1980, 12, 24), '06:30', '06:33', 31.23, lon, utc_offset=8)

            document = located(121.47)
            foreign = located(150)
            first_day_night = prefix + '/0/chart/day_night/type'
            self.assertEqual(module._pointer(document, first_day_night), '夜生')
            self.assertEqual(module._pointer(foreign, first_day_night), '昼生')
            self.assertEqual(verify(first_day_night), [])
            detached = document['sampled_sections'][0]['sample']
            detached_foreign = foreign['sampled_sections'][0]['sample']
            detached_pointer = '/candidates/0/chart/day_night/type'
            scope, _ = module._qizheng_sampling_scope(detached, detached_pointer)
            self.assertEqual(scope['Qizheng birth longitude'], 121.47)
            wrong_place = copy.deepcopy(detached)
            wrong_place['candidates'][0] = detached_foreign['candidates'][0]
            with self.assertRaisesRegex(ValueError, 'disagrees with its birth coordinates'):
                module._qizheng_sampling_scope(wrong_place, detached_pointer)
            invalid = copy.deepcopy(detached)
            invalid['input']['lat'] = None
            with self.assertRaisesRegex(ValueError, '经纬度'):
                module._qizheng_sampling_scope(invalid, detached_pointer)
            row = module._pointer(document, prefix + '/0')
            row['fields']['day_night'] = '昼生'
            self.assertIn('disagrees with its replayed horizon summary',
                          verify(prefix + '/0/fields/day_night')[0])
            row['fields']['day_night'] = '夜生'
            row['chart'] = module._pointer(foreign, prefix + '/0/chart')
            self.assertIn('disagrees with its birth coordinates', verify(first_day_night)[0])

            document = located(121.47)
            row = module._pointer(document, prefix + '/0')
            row['witness_civil'] = row['witness_utc']
            self.assertIn('disagrees with its birth timezone', verify(first_day_night)[0])

            document = compare_civil_band(date(2025, 11, 2), '01:10', '01:13', 40.71, -74.01,
                                          zone='America/New_York')
            pointer = '/sampled_sections/1/sample/candidates/0'
            row = module._pointer(document, pointer)
            self.assertEqual(row['fold'], 1)
            self.assertEqual(verify(pointer + '/witness_civil'), [])
            row['fold'] = 0
            self.assertIn('disagrees with its birth timezone', verify(pointer + '/witness_civil')[0])

    def test_qizheng_sampled_bodies_replay_at_their_own_birth_instant(self):
        from qizheng_sensitivity import compare_civil_band

        prefix = '/sampled_sections/0/sample/candidates/0'
        moon = prefix + '/chart/bodies/月/mansion'
        summary = prefix + '/fields/bodies.月.mansion'
        for profile, start, end in (('physical-v2', '04:40', '05:25'), ('legacy-v1', '00:01', '00:12')):
            with self.subTest(profile=profile):
                sample = compare_civil_band(date(2000, 1, 1), start, end, 35, 120, utc_offset=8, profile=profile)
                first = module._pointer(sample, prefix)
                later = next(row for section in sample['sampled_sections'] for row in section['sample']['candidates']
                             if row['fields']['bodies.月.mansion'] == '亢')
                self.assertEqual(first['chart']['bodies']['月']['mansion'], '角')
                for path in (moon, summary, prefix):
                    module._qizheng_sampling_scope(sample, path)

                wrong = copy.deepcopy(sample)
                row = module._pointer(wrong, prefix)
                row['fields']['bodies.月.mansion'] = later['fields']['bodies.月.mansion']
                with self.assertRaisesRegex(ValueError, 'disagrees with its replayed sky summary'):
                    module._qizheng_sampling_scope(wrong, summary)
                module._qizheng_sampling_scope(wrong, moon)
                row['chart']['bodies']['月'] = later['chart']['bodies']['月']
                for path in (moon, prefix):
                    with self.assertRaisesRegex(ValueError, 'disagrees with its replayed birth instant'):
                        module._qizheng_sampling_scope(wrong, path)
                module._qizheng_sampling_scope(wrong, prefix + '/witness_civil')
                module._qizheng_sampling_scope(wrong, prefix + '/chart/bodies/日/mansion')

                sparse = dict(first, chart={**first['chart'], 'bodies': {'月': {'mansion': '角'}}})
                sparse['chart'].pop('ming_du')
                sparse['chart'].pop('day_night')
                sparse.pop('fields')
                detached = dict(sample['sampled_sections'][0]['sample'], candidates=[sparse])
                detached.pop('input')
                module._qizheng_sampling_scope(detached, '/candidates/0/chart/bodies/月/mansion')
                sparse['chart']['bodies']['月']['mansion'] = '亢'
                with self.assertRaisesRegex(ValueError, 'disagrees with its replayed birth instant'):
                    module._qizheng_sampling_scope(detached, '/candidates/0/chart/bodies/月/mansion')

    def test_standalone_ziwei_dynamic_facts_bind_system_and_recorded_birth(self):
        snapshot = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())
        dynamic_pointer = '/admitted_dynamic_facts/layers/monthly/heavenly_stem'

        def dynamic(solar='2000-05-15', shichen=6, year=2000, sex='男'):
            day = date.fromisoformat(solar)
            gender = 'male' if sex == '男' else 'female'
            return dict(
                schema_version='ziwei-dynamic-facts-v1',
                inputs=dict(birth=dict(solar=solar, shichen_index=shichen, original_civil_birth_year=year, sex=sex),
                            target=dict(solar_date='2030-03-24', civil_time='2030-03-24T10:00:00+05:00')),
                native_wrapper_snapshot=dict(
                    schema_version=1, engine='iztro 2.6.1 / vendored wrapper',
                    input=dict(solar=solar, shichenIndex=shichen, birthYear=year, gender=gender),
                    chart=dict(birthInfo=dict(year=day.year, month=day.month, day=day.day, hour=shichen, gender=gender),
                               palaces=[])),
                admitted_dynamic_facts=dict(profile='iztro-2.6.1-lunar-year-month-v1',
                                            layers=dict(monthly=dict(heavenly_stem='辛'), daily=dict(status='withheld'))))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def verify(document, system='ziwei'):
                sources, facts = [], []
                for role, name, data, pointer in [('ziwei', 'snapshot', snapshot, '/ziwei/chart/mingGongBranch'),
                                                   (system, 'dynamic', document, dynamic_pointer)]:
                    raw = json.dumps(data).encode('utf-8')
                    (root / (name + '.json')).write_bytes(raw)
                    sources.append(dict(id=name, kind='chart', path=name + '.json', system=role,
                                        sha256=hashlib.sha256(raw).hexdigest(), scenario_id='base', pointer_prefix=pointer))
                    facts.append(dict(id=name + '-fact', system=role, source_id=name, scenario_id='base',
                                      pointer=pointer, value=module._pointer(data, pointer)))
                claims = [dict(row, status='withheld', boundary='unassessed', rule_ids=[],
                               fact_ids=[fact['id'] for fact in facts if fact['system'] == row['system']])
                          for row in self.data['claims'] if row['system'] in {fact['system'] for fact in facts}]
                ledger = dict(self.data, sources=sources, facts=facts, claims=claims, rules=[], syntheses=[])
                return module.validate(ledger, root)

            self.assertEqual(verify(dynamic()), [])
            for candidate, field in ((dynamic(shichen=7), 'selected chart date and shichen'),
                                     (dynamic(solar='2000-05-16'), 'selected chart date and shichen'),
                                     (dynamic(sex='女'), 'birth sex for BaZi/Ziwei'),
                                     (dynamic(year=1999), 'Ziwei civil birth year')):
                self.assertIn(field, verify(candidate)[0])
            self.assertIn('standalone snapshot section belongs to ziwei', verify(dynamic(), 'bazi')[0])
            incomplete = dynamic()
            del incomplete['native_wrapper_snapshot']
            self.assertEqual(verify(incomplete), [])
            self.assertIn('standalone snapshot section belongs to ziwei', verify(incomplete, 'bazi')[0])
            mismatched = dynamic()
            mismatched['native_wrapper_snapshot']['chart']['birthInfo']['hour'] = 7
            self.assertIn('Ziwei dynamic birth identity disagrees with its native wrapper', verify(mismatched)[0])

    def test_standalone_ziwei_dynamic_facts_replay_the_cited_layer_at_its_query_point(self):
        command = ['node', str(ROOT / 'scripts/ziwei_dynamic_facts.mjs'), '--solar', '1994-02-19',
                   '--birth-year', '1994', '--shichen-index', '3', '--sex', '男', '--source-label', 'ledger-test']

        def dynamic(day, index=6, *args):
            return json.loads(subprocess.check_output(
                command + ['--target-date', day, '--target-time-index', str(index), *args], text=True, timeout=60))

        monthly, daily, current = (dynamic(day) for day in ('2026-11-08', '2026-11-14', '2026-11-15'))
        late = dynamic('2026-11-15', 12, '--target-civil', '2026-11-15T23:15:00+08:00')
        prefix = '/admitted_dynamic_facts'
        month_lu = '/layers/monthly/transformations/0/star'
        day_lu = '/layers/daily/transformations/0/star'
        year_lu = '/layers/yearly/transformations/0/star'
        self.assertEqual(module._pointer(monthly, prefix + month_lu), '贪狼')
        self.assertEqual(module._pointer(current, prefix + month_lu), '武曲')
        self.assertEqual(module._pointer(daily, prefix + day_lu), '天梁')
        self.assertEqual(module._pointer(current, prefix + day_lu), '破军')

        def stitched(saved, previous, layer):
            mixed = copy.deepcopy(saved)
            mixed['admitted_dynamic_facts']['layers'][layer] = previous['admitted_dynamic_facts']['layers'][layer]
            for key in ('selected_fact_views', 'raw_horoscope'):
                mixed['research_dynamic_iztro'][key][layer] = previous['research_dynamic_iztro'][key][layer]
            return mixed

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def verify(saved, *fields):
                raw = json.dumps(saved).encode('utf-8')
                (root / 'dynamic.json').write_bytes(raw)
                source = dict(id='dynamic', kind='chart', path='dynamic.json', system='ziwei',
                              scenario_id='base', pointer_prefix=prefix, sha256=hashlib.sha256(raw).hexdigest())
                facts = [dict(id='dynamic-fact-' + str(i), source_id='dynamic', system='ziwei', scenario_id='base',
                              pointer=prefix + field, value=module._pointer(saved, prefix + field))
                         for i, field in enumerate(fields)]
                claim = next(row for row in self.data['claims'] if row['system'] == 'ziwei')
                ledger = dict(self.data, sources=[source], facts=facts, rules=[], syntheses=[],
                              claims=[dict(claim, status='withheld', boundary='unassessed', rule_ids=[],
                                           fact_ids=[fact['id'] for fact in facts])])
                return module.validate(ledger, root)

            self.assertEqual(verify(current, '', month_lu, day_lu, year_lu), [])
            self.assertEqual(verify(monthly, month_lu), [])
            self.assertEqual(verify(daily, day_lu), [])
            self.assertEqual(verify(late, '/layers/daily/status', month_lu), [])
            for saved, field, healthy, layer in (
                    (stitched(current, monthly, 'monthly'), month_lu, year_lu, 'monthly'),
                    (stitched(current, daily, 'daily'), day_lu, month_lu, 'daily'),
                    (stitched(late, current, 'daily'), day_lu, month_lu, 'daily')):
                with self.subTest(layer=layer, target=saved['inputs']['target']):
                    errors = verify(saved, field, healthy)
                    self.assertEqual(len(errors), 1)
                    self.assertIn('Ziwei ' + layer + ' dynamic facts disagree', errors[0])

            reordered = copy.deepcopy(current)
            reordered['admitted_dynamic_facts']['layers']['monthly']['transformations'].reverse()
            self.assertEqual(verify(reordered, '/layers/monthly/transformations/3/star'), [])
            missing_month = copy.deepcopy(current)
            del missing_month['admitted_dynamic_facts']['layers']['monthly']
            self.assertEqual(verify(missing_month, year_lu), [])
            errors = verify(missing_month, '', '/layers', year_lu)
            self.assertEqual(len(errors), 2)
            self.assertTrue(all('exactly the replayed layers' in error for error in errors))
            changed_scope = copy.deepcopy(current)
            changed_scope['admitted_dynamic_facts']['full_interval_coverage'] = True
            errors = verify(changed_scope, '', '/full_interval_coverage', month_lu)
            self.assertEqual(len(errors), 2)
            self.assertTrue(all('admission metadata disagrees' in error for error in errors))
            changed_profile = copy.deepcopy(current)
            changed_profile['admitted_dynamic_facts']['profile'] = 'unapproved'
            self.assertIn('admission metadata disagrees', verify(changed_profile, '/profile')[0])
            incomplete = copy.deepcopy(current)
            del incomplete['inputs']['target']['time_index']
            self.assertIn('lack the original birth or query point', verify(incomplete, month_lu)[0])
            bad_clock = copy.deepcopy(late)
            bad_clock['inputs']['target']['civil_time'] = '2026-11-15T22:15:00+08:00'
            self.assertIn('could not be replayed at the recorded query point', verify(bad_clock, month_lu)[0])
            wrong_year = copy.deepcopy(current)
            wrong_year['native_wrapper_snapshot']['input']['ageYear'] = 2025
            self.assertIn('native reference year disagrees', verify(wrong_year, month_lu)[0])
            wrong_date = copy.deepcopy(current)
            wrong_date['research_dynamic_iztro']['raw_horoscope']['solarDate'] = '2026-11-14'
            self.assertIn('native date disagrees', verify(wrong_date, year_lu)[0])

    def test_exact_ziwei_sources_keep_original_civil_birth_year(self):
        first = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())
        first['input'].update(solar='1986-12-31', hour='23:30', utc_offset=0, time_basis='mean-solar')
        first['time'].update(civil='1986-12-31T23:30:00Z', instant_bj='1987-01-01T07:30:00+08:00',
                             chart_clock='1986-12-31T23:30:00')
        first['bazi']['birth_dt'] = first['time']['instant_bj']
        first['ziwei']['input'].update(solar='1986-12-31', shichenIndex=0, birthYear=1986)
        second = copy.deepcopy(first)
        second['input'].update(solar='1987-01-01', hour='07:30', utc_offset=8)
        second['time']['civil'] = first['time']['instant_bj']
        second['ziwei']['input']['birthYear'] = 1987

        self.data['sources'] = [s for s in self.data['sources'] if s.get('system') == 'ziwei']
        self.data['facts'] = [f for f in self.data['facts'] if f['system'] == 'ziwei']
        self.data['claims'] = [c for c in self.data['claims'] if c['system'] == 'ziwei']
        self.data.update(rules=[], syntheses=[])
        self.data['claims'][0].update(status='withheld', boundary='unassessed', rule_ids=[])
        source, fact = self.data['sources'][0], self.data['facts'][0]
        other_source = dict(source, id='second-ziwei')
        other_fact = dict(fact, id='second-ziwei-fact', source_id=other_source['id'])
        self.data['sources'].append(other_source)
        self.data['facts'].append(other_fact)
        self.data['claims'][0]['fact_ids'].append(other_fact['id'])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def write(document, chart_source, chart_fact):
                raw = json.dumps(document).encode('utf-8')
                path = root / (chart_source['id'] + '.json')
                path.write_bytes(raw)
                chart_source.update(path=path.name, sha256=hashlib.sha256(raw).hexdigest(), pointer_prefix='/ziwei')
                chart_fact.update(pointer='/ziwei/chart/mingGongBranch',
                                  value=document['ziwei']['chart']['mingGongBranch'])

            write(first, source, fact)
            write(first, other_source, other_fact)
            self.assertEqual(module.validate(self.data, root), [])
            archived = copy.deepcopy(second)
            del archived['ziwei']['input']['birthYear']
            for candidate in (second, archived):
                write(candidate, other_source, other_fact)
                errors = module.validate(self.data, root)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn('Ziwei civil birth year for scenario base', errors[0])
            second['ziwei']['input']['birthYear'] = 1986
            write(second, other_source, other_fact)
            self.assertTrue(any('birth year disagrees with the original birth input' in error
                                for error in module.validate(self.data, root)))

    def test_exact_qizheng_sources_bind_actual_inputs_and_direct_section(self):
        combined = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())
        combined['input'].update(qizheng_profile='physical-v2', dut1_seconds=0)
        chart = combined['qizheng']
        chart.update(jd_utc=chart['jd_ut'], calculation_profile='physical-v2',
                     horizon_contract={'dut1_seconds': 0.0})
        direct = {
            'input': {key: combined['input'][key] for key in ('solar', 'hour', 'lat', 'lon')},
            'chart': copy.deepcopy(chart), 'traditional_reading': {},
        }
        direct['input'].update(uncertain_time=False, profile='physical-v2', dut1_seconds=0.0)
        self.data.update(sources=[], facts=[], claims=[], rules=[], syntheses=[])
        self.data['claims'].append(dict(
            id='limited', system='qizheng', status='withheld', boundary='unassessed',
            statement='合成事实', domain='劳逸', time_scope='本命', conditions='需核实际输入',
            counterevidence='缺时段证据', alternatives='保留事实', limitations='没有预测',
            explanation=dict(plain='保留事实', technical='绑定盘面', action='无需行动'),
            fact_ids=['a', 'b'], rule_ids=[], depends_on=[], scenario_ids=['base'],
        ))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def attach(documents, system='qizheng'):
                self.data['sources'].clear()
                self.data['facts'].clear()
                self.data['claims'][0]['system'] = system
                for ident, document in zip(('a', 'b'), documents):
                    path = root / (ident + '.json')
                    raw = json.dumps(document).encode('utf-8')
                    path.write_bytes(raw)
                    prefix = 'chart' if 'chart' in document else 'qizheng'
                    self.data['sources'].append(dict(
                        id=ident, kind='chart', system=system, scenario_id='base',
                        pointer_prefix='/' + prefix, path=path.name, sha256=hashlib.sha256(raw).hexdigest(),
                    ))
                    self.data['facts'].append(dict(
                        id=ident, system=system, scenario_id='base', source_id=ident,
                        pointer='/' + prefix + '/ming_du', value=document[prefix]['ming_du'],
                    ))
                return module.validate(self.data, root)

            self.assertEqual(attach((combined, direct)), [])
            self.assertTrue(any('standalone snapshot section belongs to qizheng' in error
                                for error in attach((direct, direct), 'ziwei')))
            for field, change, native_change, expected in (
                ('lon', 60, None, 'Qizheng birth longitude'),
                ('profile', 'legacy-v1', ('calculation_profile', 'legacy-v1'), 'Qizheng calculation profile'),
                ('dut1_seconds', 0.9, ('horizon_contract', {'dut1_seconds': 0.9}), 'Qizheng DUT1'),
                ('hour', '12:01', ('jd_utc', chart['jd_utc'] + 60 / 86400), 'exact birth instant'),
            ):
                with self.subTest(field=field):
                    other = copy.deepcopy(direct)
                    other['input'][field] = change
                    if native_change:
                        other['chart'][native_change[0]] = native_change[1]
                    errors = attach((combined, other))
                    self.assertEqual(len(errors), 1, errors)
                    self.assertIn(expected + ' for scenario base', errors[0])
            other = copy.deepcopy(direct)
            other['input'].update(lat=None, lon=None, other_body='木')
            self.assertEqual(attach((combined, other)), [])
            other['input']['lat'] = -35
            self.assertTrue(any('Qizheng birth latitude' in error for error in attach((combined, other))))
            other['input']['lat'] = None
            other['input']['profile'] = 'legacy-v1'
            self.assertTrue(any('disagrees with the native chart' in error
                                for error in attach((combined, other))))
            other = copy.deepcopy(direct)
            other['input']['hour'] = '12:01'
            self.assertTrue(any('native UTC Julian day disagrees' in error
                                for error in attach((combined, other))))

            reference = copy.deepcopy(combined)
            reference['input']['uncertainty_minutes'] = 5
            self.assertEqual(attach((reference, direct)), [])
            other['chart']['jd_utc'] += 60 / 86400
            self.assertTrue(any('exact birth instant outside the reachable Qizheng birth intervals' in error
                                for error in attach((reference, other))))
            other['input']['uncertain_time'] = True
            self.assertTrue(any('no common Qizheng birth interval' in error
                                for error in attach((reference, other))))
            del reference['input']['uncertainty_minutes']
            self.assertTrue(any('no common Qizheng birth interval' in error
                                for error in attach((reference, other))))
            reference['qizheng']['jd_utc'] = other['chart']['jd_utc']
            self.assertTrue(any('native UTC Julian day disagrees' in error
                                for error in attach((reference, other))))

    def test_standalone_bazi_birth_windows_must_have_a_common_instant(self):
        exact = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())

        def spans(*bounds):
            return [dict(start='2000-05-15T' + start + ':00+08:00',
                         end='2000-05-15T' + end + ':00+08:00',
                         candidate_id=f'candidate-{index}')
                    for index, (start, end) in enumerate(bounds)]

        def snapshot(*bounds):
            return dict(kind='birth_date_known_clock_band', solar_date='2000-05-15', sex='男',
                        time_basis='civil', interval_semantics='start_inclusive_end_exclusive',
                        stable_pillars={'month': '辛巳'}, windows=spans(*bounds),
                        candidates=[dict(id=f'candidate-{index}', pillars={'hour': '甲午'})
                                    for index in range(len(bounds))])

        base = snapshot(('11:59', '12:00'), ('12:00', '12:01'))
        base['dayun_age_comparison'] = {'segments': [
            dict(start_utc='2000-05-15T03:59:00Z', end_utc='2000-05-15T04:00:00Z', end_inclusive=False),
        ]}
        legacy = dict(base)
        del legacy['windows']
        month = '/stable_pillars/month'
        first = ('base', base, '/candidates/0/pillars/hour')
        second = ('base', base, '/candidates/1/pillars/hour')
        exact_fact = ('exact', exact, '/bazi/pillars/day')
        self.data.update(sources=[], facts=[], rules=[], claims=[], syntheses=[])
        self.data['claims'].append(dict(
            id='limited', system='bazi', status='withheld', boundary='unassessed',
            statement='合成事实', domain='工作推进', time_scope='本命',
            conditions='需核出生范围', counterevidence='可能存在区间冲突', alternatives='拆开候选',
            limitations='只核时间证据', explanation=dict(plain='核对范围', technical='核对端点', action='拆分'),
            fact_ids=[], rule_ids=[], depends_on=[], scenario_ids=['base'],
        ))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def check(*rows, system='bazi'):
                sources, facts = {}, []
                for name, document, pointer in rows:
                    path = root / (name + '.json')
                    raw = json.dumps(document).encode('utf-8')
                    path.write_bytes(raw)
                    prefix = '/' + pointer.split('/')[1]
                    sid = name + prefix
                    sources[sid] = dict(
                        id=sid, kind='chart', system=system, scenario_id='base', pointer_prefix=prefix,
                        path=path.name, sha256=hashlib.sha256(raw).hexdigest(),
                    )
                    facts.append(dict(id=f'fact-{len(facts)}', system=system, source_id=sid, scenario_id='base',
                                      pointer=pointer, value=module._pointer(document, pointer)))
                self.data.update(sources=list(sources.values()), facts=facts)
                self.data['claims'][0].update(system=system, fact_ids=[row['id'] for row in facts])
                return module.validate(self.data, root)

            self.assertEqual(check(first, ('base', base, month)), [])
            self.assertEqual(check(second, exact_fact), [])
            self.assertEqual(check(exact_fact, ('legacy', legacy, month)), [])
            age_fact = ('base', base, '/dayun_age_comparison/segments/0/start_utc')
            self.assertEqual(check(first, age_fact), [])
            self.assertIn('no common BaZi birth interval', check(first, second)[0])
            self.assertIn('no common BaZi birth interval',
                          check(second, ('base', base, '/windows/0/start'))[0])
            self.assertIn('no common BaZi birth interval', check(second, age_fact)[0])
            for rows in ((first, exact_fact), (exact_fact, first)):
                self.assertIn('exact birth instant outside the reachable BaZi birth intervals', check(*rows)[0])
            self.assertIn('standalone snapshot section belongs to bazi',
                          check(('legacy', legacy, month), system='qizheng')[0])
            mean_solar = copy.deepcopy(exact)
            mean_solar['input']['time_basis'] = 'mean-solar'
            self.assertIn('selected chart time basis',
                          check(second, ('mean-solar', mean_solar, exact_fact[2]))[0])
            self.assertIn('birth sex for BaZi/Ziwei',
                          check(exact_fact, ('female', dict(base, sex='女'), month))[0])
            other_offset = snapshot(('13:00', '13:01'))
            other_offset['windows'][0].update(
                start='2000-05-15T13:00:00+09:00', end='2000-05-15T13:01:00+09:00')
            aliased_fact = ('other-offset', other_offset, month)
            self.assertIn('no common BaZi birth interval', check(second, aliased_fact)[0])
            self.assertIn('effective civil UTC offset disagrees', check(exact_fact, aliased_fact)[0])
            legacy_exact = copy.deepcopy(exact)
            del legacy_exact['time']['civil']
            legacy_fact = ('legacy-exact', legacy_exact, exact_fact[2])
            self.assertEqual(check(legacy_fact, second), [])

            from bazi_scenario_reading import analyze_birth_date

            native = analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8)
            late_day = '/candidates/1/analysis/facts/day/pillar'
            self.assertEqual(check(('native', native, late_day)), [])
            mixed = copy.deepcopy(native)
            mixed['windows'][0]['candidate_id'] = native['windows'][1]['candidate_id']
            self.assertIn('六字候选或实际区间与原民用生日重算不一致',
                          check(('wrong-window', mixed, late_day))[0])
            mixed = copy.deepcopy(native)
            mixed['candidates'][1]['analysis'] = native['candidates'][0]['analysis']
            self.assertIn('saved BaZi candidate fact disagrees with the replayed birth',
                          check(('wrong-fact', mixed, late_day))[0])
            for pointer in ('/candidates', '/candidates/1', '/candidates/1/analysis'):
                with self.subTest(pointer=pointer):
                    self.assertEqual(check(('genuine-parent', native, pointer)), [])
                    self.assertIn('saved BaZi candidate fact disagrees with the replayed birth',
                                  check(('wrong-parent', mixed, pointer))[0])
            self.assertEqual(check(('unaffected-candidate', mixed, '/candidates/0/analysis')), [])
            known = analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8, shichen='子')
            del known['dayun_age_comparison']
            self.assertEqual(check(('known-without-age-table', known, late_day)), [])
            known['windows'][0]['candidate_id'] = known['windows'][1]['candidate_id']
            self.assertIn('时辰候选区间与原出生输入重算不一致',
                          check(('wrong-known-window', known, late_day))[0])
            self.assertIn('effective civil UTC offset disagrees', check(legacy_fact, aliased_fact)[0])

            # Every pair overlaps, but the three unions share no common instant.
            a = ('a', snapshot(('10:00', '11:00'), ('12:00', '13:00')), month)
            b = ('b', snapshot(('10:00', '11:00'), ('14:00', '15:00')), month)
            c = ('c', snapshot(('12:00', '13:00'), ('14:00', '15:00')), month)
            for pair in ((a, b), (a, c), (b, c)):
                self.assertEqual(check(*pair), [])
            self.assertIn('no common BaZi birth interval', check(a, b, c)[0])

    def test_unlocated_confirmed_ziwei_clock_narrows_only_known_offset_spans(self):
        bazi = dict(kind='birth_date_unknown_hour', solar_date='2000-05-15', sex='男',
                    time_basis='civil', interval_semantics='start_inclusive_end_exclusive',
                    candidates=[dict(id=label) for label in ('early', 'middle', 'late')],
                    windows=[
                        dict(start=start, end=end, candidate_id=label) for start, end, label in (
                            ('2000-05-15T00:00:00+08:00', '2000-05-15T04:02:00+08:00', 'early'),
                            ('2000-05-15T04:02:00+08:00', '2000-05-15T23:00:00+08:00', 'middle'),
                            ('2000-05-15T23:00:00+08:00', '2000-05-16T00:00:00+08:00', 'late'),
                        )
                    ])

        def panel(index, *hours, day='2000-05-15'):
            return dict(version='ziwei-life-domains-v1', profile='ziwei-life-domains-v1',
                        reading_use='conditional_module_only', domains=[],
                        birth_scenario=dict(scope='confirmed_civil_shichen_only', civil_spans=None,
                                            input=dict(solar_date=day, birth_year=2000, shichen_index=index, sex='男'),
                                            clock_intervals=[dict(start_inclusive=left, end_exclusive=right)
                                                             for left, right in hours]))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def check(document, pointer):
                sources, facts, claims = [], [], []
                for index, (system, snapshot, path_pointer) in enumerate((
                        ('bazi', bazi, pointer), ('ziwei', document, '/birth_scenario/input/shichen_index'))):
                    path = root / (system + '.json')
                    raw = json.dumps(snapshot).encode('utf-8')
                    path.write_bytes(raw)
                    sources.append(dict(id=system, kind='chart', system=system, scenario_id='base',
                                        pointer_prefix=path_pointer, path=path.name, sha256=hashlib.sha256(raw).hexdigest()))
                    facts.append(dict(id=system, system=system, source_id=system, scenario_id='base',
                                      pointer=path_pointer, value=module._pointer(snapshot, path_pointer)))
                    claims.append(dict(self.data['claims'][index], status='withheld', boundary='unassessed',
                                       fact_ids=[system], rule_ids=[], depends_on=[], scenario_ids=['base']))
                ledger = dict(self.data, sources=sources, facts=facts, claims=claims, rules=[], syntheses=[])
                return module.validate(ledger, root)

            rooster = panel(9, ('17:00', '19:00'))
            rat = panel(0, ('00:00', '01:00'), ('23:00', '24:00'))
            self.assertEqual(check(rooster, '/solar_date'), [])
            self.assertIn('no common birth interval', check(rooster, '/candidates/0/id')[0])
            self.assertEqual(check(panel(2, ('03:00', '05:00')), '/candidates/0/id'), [])
            self.assertIn('no common birth interval',
                          check(panel(1, ('01:00', '03:00'), day='2000-05-16'), '/solar_date')[0])
            self.assertEqual(check(rat, '/candidates/0/id'), [])
            self.assertEqual(check(rat, '/candidates/2/id'), [])
            del rooster['birth_scenario']['clock_intervals']
            self.assertEqual(check(rooster, '/candidates/0/id'), [])

    def test_standalone_ziwei_birth_bands_and_panels_bind_reachable_instants(self):
        exact = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())
        identity = dict(solar_date='2000-05-15', birth_year=2000, shichen_index=6, sex='男')
        left = dict(start_inclusive='2000-05-15T11:59:00+08:00', end_exclusive='2000-05-15T12:00:00+08:00',
                    start_utc='2000-05-15T03:59:00Z', end_exclusive_utc='2000-05-15T04:00:00Z')
        right = dict(start_inclusive='2000-05-15T12:00:00+08:00', end_exclusive='2000-05-15T12:01:00+08:00',
                     start_utc='2000-05-15T04:00:00Z', end_exclusive_utc='2000-05-15T04:01:00Z')
        band = dict(schema_version='ziwei-birth-time-candidates-v1', status='partial',
                    input=dict(birth_date='2000-05-15', sex='男', time_basis='civil'),
                    interval_semantics='confirmed_civil_clock_membership_start_inclusive_end_exclusive',
                    candidates=[dict(input=identity, civil_spans=[span]) for span in (left, right)])
        panel = dict(version='ziwei-life-domains-v1', profile='ziwei-life-domains-v1', reading_use='conditional_module_only',
                     status='partial', domains=[], temporal_uncertainty=False, natal_civil_birth_year=2000,
                     birth_scenario=dict(scope='selected_reachable_civil_band_candidate_only',
                                         input=identity, civil_spans=[right]))
        instant = dict(panel, birth_scenario=None, birth_time_bounds=dict(
            earliest_utc='2000-05-15T04:00:00Z', latest_utc='2000-05-15T04:00:00+00:00'))
        legacy = dict(panel, birth_scenario=None, dynamic=dict(target_date='2027-06-01'))
        native = dict(exact['ziwei'], engine='iztro 2.6.1 / vendored wrapper')
        self.data.update(sources=[], facts=[], rules=[], claims=[], syntheses=[])
        self.data['claims'].append(dict(
            id='limited', system='ziwei', status='withheld', boundary='unassessed',
            statement='合成事实', domain='关系与阶段', time_scope='本命',
            conditions='需核出生范围', counterevidence='区间可能冲突', alternatives='拆开候选',
            limitations='核对时间证据', explanation=dict(plain='核对范围', technical='核对端点', action='拆分'),
            fact_ids=[], rule_ids=[], depends_on=[], scenario_ids=['base'],
        ))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def check(*rows, system='ziwei'):
                sources, facts = {}, []
                for name, document, pointer in rows:
                    path = root / (name + '.json')
                    raw = json.dumps(document).encode('utf-8')
                    path.write_bytes(raw)
                    prefix = '/' + pointer.split('/')[1]
                    sid = name + prefix
                    sources[sid] = dict(
                        id=sid, kind='chart', system=system, scenario_id='base', pointer_prefix=prefix,
                        path=path.name, sha256=hashlib.sha256(raw).hexdigest(),
                    )
                    facts.append(dict(id=f'fact-{len(facts)}', system=system, source_id=sid, scenario_id='base',
                                      pointer=pointer, value=module._pointer(document, pointer)))
                self.data.update(sources=list(sources.values()), facts=facts)
                self.data['claims'][0].update(system=system, fact_ids=[row['id'] for row in facts])
                return module.validate(self.data, root)

            first = ('band', band, '/candidates/0/input/shichen_index')
            second = ('band', band, '/candidates/1/input/shichen_index')
            point = ('panel', panel, '/status')
            exact_fact = ('exact', exact, '/ziwei/chart/mingGongBranch')
            exact_panel = ('instant', instant, '/status')
            native_fact = ('native', native, '/chart/mingGongBranch')
            self.assertEqual(check(second, point, exact_fact, exact_panel), [])
            self.assertEqual(check(('band', band, '/status'), first), [])
            self.assertEqual(check(('legacy', legacy, '/status'), second), [])
            for facts in ((first, second), (first, point)):
                self.assertIn('no common Ziwei birth interval', check(*facts)[0])
            for fact in (exact_fact, exact_panel):
                self.assertIn('exact birth instant outside the reachable Ziwei birth intervals', check(fact, first)[0])
            for fact in (second, point):
                self.assertIn('standalone snapshot section belongs to ziwei', check(fact, system='bazi')[0])
            changed = copy.deepcopy(band)
            changed['candidates'][1]['civil_spans'][0]['start_utc'] = '2000-05-15T04:00:01Z'
            self.assertIn('civil and UTC birth bounds disagree',
                          check(('changed', changed, second[2]))[0])
            archived = copy.deepcopy(band)
            archived['candidates'][1].pop('civil_spans')
            self.assertEqual(check(('archived', archived, second[2]), exact_fact), [])
            archived['candidates'][1]['input']['shichen_index'] = 5
            self.assertIn('selected chart date and shichen', check(('archived', archived, second[2]), exact_fact)[0])
            self.assertEqual(check(native_fact, first), [])
            self.assertEqual(check(native_fact, exact_fact), [])
            mean_solar = copy.deepcopy(exact)
            mean_solar['input']['time_basis'] = 'mean-solar'
            self.assertEqual(check(native_fact, ('mean-solar', mean_solar, exact_fact[2])), [])
            self.assertIn('standalone snapshot section belongs to ziwei', check(native_fact, system='qizheng')[0])
            incompatible = copy.deepcopy(native)
            incompatible['input']['shichenIndex'] = 5
            self.assertIn('selected chart date and shichen',
                          check(('incompatible', incompatible, native_fact[2]), second)[0])

    def test_combined_birth_candidates_bind_projections_to_reachable_instants(self):
        exact = json.loads((ROOT / 'examples/engine-reading/summer.json').read_text())
        comparison = copy.deepcopy(exact)
        comparison['input']['uncertainty_minutes'] = 3
        identity = {'ziwei.solar_date': '2000-05-15', 'ziwei.shichen_index': 6, 'ziwei.birth_year': 2000}

        def span(start, end, inclusive=False):
            return dict(start_utc='2000-05-15T' + start + 'Z',
                        end_utc='2000-05-15T' + end + 'Z', end_inclusive=inclusive)

        comparison['scenarios'] = dict(
            coverage='complete_for_modeled_boundaries_not_astronomical_error',
            variants=[
                dict(fields=identity, intervals=[span('03:57:00', '03:58:00')]),
                dict(fields=identity, intervals=[span('03:59:00', '04:00:00'), span('04:00:00', '04:00:00', True)]),
            ],
        )
        comparison['bazi_scenario_comparison'] = dict(candidates=[dict(id='candidate-2'), dict(id='candidate-1')])
        comparison['ziwei_scenario_comparison'] = dict(candidates=[dict(scenario_ids=['candidate-1', 'candidate-2'])])
        claim = dict(self.data['claims'][0], status='withheld', boundary='unassessed',
                     fact_ids=[], rule_ids=[], depends_on=[], scenario_ids=['base'])
        self.data.update(rules=[], claims=[claim], syntheses=[])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            documents = {'exact': exact, 'comparison': comparison}

            def check(*rows):
                sources, facts = {}, []
                for name, system, pointer in rows:
                    document = documents[name]
                    path = root / (name + '.json')
                    raw = json.dumps(document).encode('utf-8')
                    path.write_bytes(raw)
                    source_id = name + '-' + system
                    sources[source_id] = dict(id=source_id, kind='chart', system=system, scenario_id='base',
                                              path=path.name, sha256=hashlib.sha256(raw).hexdigest(),
                                              pointer_prefix='/' + pointer.split('/')[1])
                    facts.append(dict(id=f'fact-{len(facts)}', system=system, source_id=source_id,
                                      scenario_id='base', pointer=pointer, value=module._pointer(document, pointer)))
                self.data.update(sources=list(sources.values()), facts=facts)
                return module.validate(self.data, root)

            late = ('comparison', 'bazi', '/bazi_scenario_comparison/candidates/0/id')
            early = ('comparison', 'bazi', '/bazi_scenario_comparison/candidates/1/id')
            group = ('comparison', 'ziwei', '/ziwei_scenario_comparison/candidates/0/scenario_ids')
            point = ('exact', 'ziwei', '/ziwei/chart/mingGongBranch')
            self.assertIn('no common BaZi birth interval', check(late, early)[0])
            self.assertEqual(check(group, early), [])
            self.assertEqual(check(group, late, point), [])
            self.assertIn('exact birth instant outside the reachable BaZi/Ziwei birth intervals', check(group, early, point)[0])

            replayed = [dict(row, civil_offset_seconds=28800)
                        for variant in comparison['scenarios']['variants'] for row in variant['intervals']]
            context = dict(scope='selected_birth_witness_only', time_basis='civil',
                           coverage=comparison['scenarios']['coverage'],
                           input=dict(solar_date='2000-05-15', birth_year=2000, shichen_index=6),
                           reachable_utc_intervals=replayed)
            documents['panel'] = dict(version='ziwei-life-domains-v1', profile='ziwei-life-domains-v1',
                                      reading_use='conditional_module_only', domains=[], birth_scenario=context)
            panel = ('panel', 'ziwei', '/birth_scenario/scope')
            first_window = ('panel', 'ziwei', '/birth_scenario/reachable_utc_intervals/0/start_utc')
            self.assertEqual(check(panel, late, point), [])
            self.assertEqual(check(first_window, early), [])
            self.assertIn('no common BaZi/Ziwei birth interval', check(first_window, late)[0])
            self.assertIn('exact birth instant outside the reachable Ziwei birth intervals', check(first_window, point)[0])
            replayed[-1]['civil_offset_seconds'] = 32400
            self.assertIn('effective civil UTC offset disagrees', check(panel, point)[0])
            context['coverage'] = 'numerical_witnesses_not_exhaustive'
            self.assertIn('require complete modeled coverage', check(panel)[0])
            del context['reachable_utc_intervals']
            self.assertEqual(check(panel, point), [])

            comparison['scenarios']['variants'][1]['intervals'].pop()
            self.assertIn('exact birth instant outside the reachable BaZi/Ziwei birth intervals', check(group, late, point)[0])
            comparison['input']['time_basis'] = exact['input']['time_basis'] = 'apparent-solar'
            comparison['scenarios']['coverage'] = 'numerical_witnesses_not_exhaustive'
            for variant in comparison['scenarios']['variants']:
                variant['intervals'] = []
            self.assertEqual(check(group, late, point), [])

    def test_combined_candidates_check_chart_identity_for_leaf_and_parent_references(self):
        def birth(day, clock):
            command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                       '--solar', day, '--hour', clock, '--sex', '男', '--utc-offset', '8',
                       '--analysis-year', '2026', '--uncertainty-minutes', '2',
                       '--enumerate-scenarios', '--format', 'json']
            return json.loads(subprocess.check_output(command, text=True, timeout=60))

        bazi = birth('1971-01-06', '07:45')
        base = '/bazi_scenario_comparison/candidates'
        early, late = bazi['bazi_scenario_comparison']['candidates']
        self.assertEqual((early['pillars']['month'], late['pillars']['month']), ('戊子', '己丑'))
        module._combined_candidate_birth_scope(bazi, base, 'bazi')
        saved_model = early['analysis']['qiong_xin_zi_model']
        early['analysis']['qiong_xin_zi_model'] = late['analysis']['qiong_xin_zi_model']
        with self.assertRaisesRegex(ValueError, 'BaZi model disagrees'):
            module._combined_candidate_birth_scope(bazi, base + '/0/analysis/qiong_xin_zi_model', 'bazi')
        module._combined_candidate_birth_scope(bazi, base + '/0/analysis/facts/month', 'bazi')
        early['analysis']['qiong_xin_zi_model'] = saved_model
        early['analysis'] = late['analysis']
        for suffix in ('', '/0', '/0/analysis/facts/month', '/0/analysis/qiong_xin_zi_model'):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, 'BaZi analysis facts disagree'):
                module._combined_candidate_birth_scope(bazi, base + suffix, 'bazi')
        with self.assertRaisesRegex(ValueError, 'BaZi analysis facts disagree'):
            module._combined_candidate_birth_scope(bazi, '/bazi_scenario_comparison', 'bazi')
        module._combined_candidate_birth_scope(bazi, base + '/0/pillars/month', 'bazi')
        early['pillars'] = late['pillars']
        with self.assertRaisesRegex(ValueError, 'BaZi pillars disagree'):
            module._combined_candidate_birth_scope(bazi, base + '/0/pillars/month', 'bazi')

        ziwei = birth('1987-06-02', '17:00')
        base = '/ziwei_scenario_comparison/candidates'
        shen, you = ziwei['ziwei_scenario_comparison']['candidates']
        self.assertEqual((shen['input']['shichen_index'], you['input']['shichen_index']), (8, 9))
        module._combined_candidate_birth_scope(ziwei, base, 'ziwei')
        saved_cases = shen['case_judgments']
        shen['case_judgments'] = you['case_judgments']
        with self.assertRaisesRegex(ValueError, 'Ziwei case domains disagree'):
            module._combined_candidate_birth_scope(ziwei, base + '/0/case_judgments/modules/ZW-RC02', 'ziwei')
        module._combined_candidate_birth_scope(ziwei, base + '/0/chart/mingGongBranch', 'ziwei')
        shen['case_judgments'] = saved_cases
        shen['chart'] = you['chart']
        for suffix in ('', '/0/chart/mingGongBranch', '/0/case_judgments'):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, 'Ziwei chart birth inputs disagree'):
                module._combined_candidate_birth_scope(ziwei, base + suffix, 'ziwei')
        module._combined_candidate_birth_scope(ziwei, base + '/0/input', 'ziwei')
        shen['scenario_ids'] = you['scenario_ids']
        with self.assertRaisesRegex(ValueError, 'Ziwei candidate inputs disagree'):
            module._combined_candidate_birth_scope(ziwei, base + '/0/input', 'ziwei')

    def test_combined_ziwei_chart_replays_the_selected_birth_witness(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1967-06-17', '--hour', '05:00', '--sex', '男', '--timezone', 'Asia/Shanghai',
                   '--analysis-year', '2026', '--uncertainty-minutes', '2', '--enumerate-scenarios', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True, timeout=60))
        base = '/ziwei_scenario_comparison/candidates'
        first, second = module._pointer(snapshot, base)
        relation = '/stage_relationship/relationship/status'
        self.assertEqual(module._pointer(first, relation), 'conditional')
        self.assertEqual(module._pointer(second, relation), 'not_triggered')
        module._combined_candidate_birth_scope(snapshot, base, 'ziwei')

        stale = copy.deepcopy(snapshot)
        selected = module._pointer(stale, base + '/1')
        for key in ('chart', 'stage_relationship', 'case_judgments'):
            selected[key] = copy.deepcopy(first[key])
        selected['chart']['birthInfo'] = second['chart']['birthInfo']
        for path in (base, base + '/1', base + '/1/chart/mingGongBranch', base + '/1' + relation,
                     base + '/1/case_judgments/modules/ZW-RC02/selected_branch'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '原盘与出生见证重算不一致'):
                module._combined_candidate_birth_scope(stale, path, 'ziwei')
        module._combined_candidate_birth_scope(stale, base + '/1/witness_utc', 'ziwei')
        module._combined_candidate_birth_scope(stale, base + '/0/chart/mingGongBranch', 'ziwei')

    def test_combined_ziwei_stage_references_use_the_original_civil_birth_year(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '2026-01-01', '--hour', '00:01', '--sex', '男', '--utc-offset', '8',
                   '--lat', '31.2', '--lon', '116', '--time-basis', 'mean-solar',
                   '--analysis-year', '2026', '--uncertainty-minutes', '2',
                   '--enumerate-scenarios', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True, timeout=60))
        before, after = snapshot['ziwei_scenario_comparison']['candidates']
        self.assertEqual(before['chart']['birthInfo'], after['chart']['birthInfo'])
        self.assertEqual((before['chart']['currentAge'], after['chart']['currentAge']), (2, 1))
        base = '/ziwei_scenario_comparison/candidates'
        module._combined_candidate_birth_scope(snapshot, base, 'ziwei')
        before['chart']['currentAge'] = after['chart']['currentAge']
        with self.assertRaisesRegex(ValueError, 'Ziwei chart age disagrees'):
            module._combined_candidate_birth_scope(snapshot, base + '/0/chart/currentAge', 'ziwei')
        module._combined_candidate_birth_scope(snapshot, base + '/0/chart/mingGongBranch', 'ziwei')
        del before['chart']['currentAge']
        module._combined_candidate_birth_scope(snapshot, base + '/0', 'ziwei')
        before['stage_relationship'] = after['stage_relationship']
        with self.assertRaisesRegex(ValueError, 'Ziwei stage years disagree'):
            module._combined_candidate_birth_scope(snapshot, base + '/0/stage_relationship/stages', 'ziwei')
        module._combined_candidate_birth_scope(snapshot, base + '/0/stage_relationship/relationship', 'ziwei')

    def test_combined_exact_bazi_luck_evidence_replays_the_birth_minute(self):
        from bazi_scenario_reading import luck_contexts_at_age

        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'), '--solar', '1987-09-04',
                   '--timezone', 'Asia/Shanghai', '--sex', '男', '--analysis-year', '2026', '--format', 'json']
        early, late = [json.loads(subprocess.check_output(command + ['--hour', time], text=True, timeout=60))
                       for time in ('01:29', '01:30')]
        self.assertEqual(early['bazi']['pillars'], late['bazi']['pillars'])
        self.assertEqual(luck_contexts_at_age(early, 466)['contexts'][0]['luck']['pillar'], '甲辰')
        self.assertEqual(luck_contexts_at_age(late, 466)['contexts'][0]['luck']['pillar'], '乙巳')
        for path in ('/bazi', '/bazi/dayun_age_windows', '/bazi/dayun_rows', '/bazi/qiyun_text'):
            module._check_combined_projection(early, path, 'bazi')
            module._check_combined_projection(late, path, 'bazi')

        mixed = copy.deepcopy(early)
        for field in ('dayun_age_windows', 'qiyun_months', 'qiyun_text', 'dayun_rows'):
            mixed['bazi'][field] = late['bazi'][field]
        for path in ('/bazi', '/bazi/dayun_age_windows/windows/0/end_months_exclusive', '/bazi/qiyun_months',
                     '/bazi/qiyun_text', '/bazi/dayun_rows'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'BaZi luck ages disagree'):
                module._check_combined_projection(mixed, path, 'bazi')
        module._check_combined_projection(mixed, '/bazi/pillars/hour/0', 'bazi')
        module._check_combined_projection(mixed, '/bazi/qiyun_years', 'bazi')
        mixed['bazi']['dayun_age_windows']['birth_time_is_reference'] = True
        with self.assertRaisesRegex(ValueError, 'luck reference time disagrees'):
            module._check_combined_projection(mixed, '/bazi/dayun_age_windows', 'bazi')
        mixed['bazi']['hour_unknown'] = True
        with self.assertRaisesRegex(ValueError, 'luck reference time disagrees'):
            module._check_combined_projection(mixed, '/bazi/dayun_age_windows', 'bazi')

        legacy = copy.deepcopy(early)
        legacy['bazi']['dayun_age_windows'].pop('birth_time_is_reference')
        legacy['bazi'].pop('dayun_rows')
        module._check_combined_projection(legacy, '/bazi', 'bazi')
        old_term = json.loads((ROOT / 'examples/engine-reading/after-term.json').read_text())
        self.assertNotIn('dayun_age_windows', old_term['bazi'])
        module._check_combined_projection(old_term, '/bazi', 'bazi')

    def test_combined_exact_bazi_derived_evidence_matches_its_native_pillars(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1987-01-02', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json', '--hour']
        early, late = [json.loads(subprocess.check_output(command + [clock], text=True, timeout=60))
                       for clock in ('10:59', '11:01')]
        base = '/bazi_core_reading'
        module._check_combined_projection(early, base, 'bazi')
        model = early['bazi_core_reading']['qiong_xin_zi_model']
        model['temporal_scope'] = 'day'
        with self.assertRaisesRegex(ValueError, 'BaZi model disagrees with the native birth chart'):
            module._check_combined_projection(early, base + '/qiong_xin_zi_model', 'bazi')
        self.assertNotEqual(early['bazi']['pillars']['hour'], late['bazi']['pillars']['hour'])
        early['bazi_core_reading']['qiong_xin_zi_model'] = late['bazi_core_reading']['qiong_xin_zi_model']
        with self.assertRaisesRegex(ValueError, 'BaZi model disagrees with the native birth chart'):
            module._check_combined_projection(early, base + '/qiong_xin_zi_model/conditional_model_direction', 'bazi')
        module._check_combined_projection(early, base + '/facts/hour/pillar', 'bazi')
        early['bazi_core_reading'] = late['bazi_core_reading']
        for path in (base, base + '/facts/hour/pillar'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'BaZi analysis facts disagree'):
                module._check_combined_projection(early, path, 'bazi')
        module._check_combined_projection(early, '/bazi/pillars/hour', 'bazi')

    def test_combined_uncertain_center_retains_its_withheld_spouse_reference(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '2026-01-01', '--hour', '00:01', '--sex', '男', '--utc-offset', '8',
                   '--lat', '31.2', '--lon', '116', '--time-basis', 'mean-solar',
                   '--analysis-year', '2026', '--uncertainty-minutes', '2',
                   '--enumerate-scenarios', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True, timeout=60))
        model = snapshot['bazi_core_reading']['primary_spouse']
        self.assertEqual(model['temporal_scope'], 'central_reference_only')
        self.assertEqual(model['status'], 'withheld')
        path = '/bazi_core_reading/primary_spouse'
        module._check_combined_projection(snapshot, path, 'bazi')
        module._check_combined_projection(snapshot, '/bazi_core_reading', 'bazi')
        model['status'] = 'available'
        with self.assertRaisesRegex(ValueError, 'BaZi model disagrees with the native birth chart'):
            module._check_combined_projection(snapshot, path, 'bazi')

    def test_bazi_development_direction_and_countercondition_match_retained_native_pillars(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1987-01-02', '--hour', '10:59', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json']
        chart = json.loads(subprocess.check_output(command, text=True, timeout=60))
        analysis = chart['bazi_core_reading']
        model = analysis['qiong_xin_zi_model']
        base = '/bazi_core_reading/qiong_xin_zi_model'
        self.assertEqual(model['specific_gui_countercondition']['status'], 'present')
        module._check_combined_projection(chart, base, 'bazi')
        for field, value in (
                ('conditional_model_direction', 'development_configuration_relatively_favorable'),
                ('specific_gui_countercondition', dict(model['specific_gui_countercondition'], status='not_observed'))):
            with self.subTest(field=field):
                analysis['qiong_xin_zi_model'] = dict(model, **{field: value})
                with self.assertRaisesRegex(ValueError, 'BaZi natal development model disagrees'):
                    module._check_combined_projection(chart, base + '/' + field, 'bazi')
                module._check_combined_projection(chart, '/bazi_core_reading/facts/hour/pillar', 'bazi')

    def test_spouse_card_in_bazi_snapshot_matches_its_selected_birth(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1959-09-29', '--hour', '07:00', '--sex', '男', '--utc-offset', '8',
                   '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'json']
        archive = json.loads(subprocess.check_output(command, text=True, timeout=60))
        early, late = archive['bazi_scenario_comparison']['candidates']
        original = early['analysis']['primary_spouse']
        later = late['analysis']['primary_spouse']
        relative = 'analysis/primary_spouse/cards/1/status'
        fields = archive['scenarios']['variants'][0]['fields']
        self.assertEqual(original['cards'][1]['status'], 'requires_manual_review')
        self.assertEqual(later['cards'][1]['status'], 'outside_scope')
        module._check_combined_candidate_identity(early, fields, 'bazi', relative, '男', None, True)
        original['cards'][1] = later['cards'][1]
        for errors in ([], ['来源校验失败']):
            original['source_errors'] = errors
            with self.subTest(errors=errors), self.assertRaisesRegex(ValueError, 'spouse panel disagrees'):
                module._check_combined_candidate_identity(early, fields, 'bazi', relative, '男', None, True)
        module._check_combined_candidate_identity(early, fields, 'bazi', 'analysis/facts/hour', '男', None, True)

    def test_combined_exact_ziwei_chart_replays_original_birth(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1967-06-17', '--sex', '男', '--timezone', 'Asia/Shanghai',
                   '--analysis-year', '2030', '--format', 'json', '--hour']
        early, late = [json.loads(subprocess.check_output(command + [hour], text=True, timeout=60))
                       for hour in ('04:59', '05:01')]
        base = '/ziwei/life_reading'
        relation = base + '/stage_relationship/relationship/status'
        case = base + '/case_judgments/modules/ZW-RC02/selected_branch'
        self.assertEqual(module._pointer(early, relation), 'conditional')
        self.assertEqual(module._pointer(late, relation), 'not_triggered')
        early_stages = module._pointer(early, base + '/stage_relationship/stages')
        old_index = next(i for i, row in enumerate(early_stages) if row['legacy_stage']['current'])
        stage = base + f'/stage_relationship/stages/{old_index}/modules/ZW-ST01/selected_branch'
        self.assertEqual(module._pointer(early, stage), 'tianfu_progress')
        self.assertFalse(module._pointer(late, base + f'/stage_relationship/stages/{old_index}/legacy_stage/current'))
        module._check_combined_projection(late, '/ziwei', 'ziwei')

        mixed = copy.deepcopy(late)
        native = mixed['ziwei']
        native['chart'] = copy.deepcopy(early['ziwei']['chart'])
        native['chart']['birthInfo'] = late['ziwei']['chart']['birthInfo']
        native['life_reading'] = copy.deepcopy(early['ziwei']['life_reading'])
        native['life_reading']['birth_time_bounds'] = late['ziwei']['life_reading']['birth_time_bounds']
        for path in ('/ziwei/chart/mingGongBranch', '/ziwei', base, stage, relation, case):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '实际星表不一致'):
                module._check_combined_projection(mixed, path, 'ziwei')
        module._check_combined_projection(mixed, '/ziwei/input/shichenIndex', 'ziwei')
        module._check_combined_projection(mixed, '/bazi/pillars/hour', 'bazi')
        del mixed['input']['enumerate_scenarios']
        with self.assertRaisesRegex(ValueError, '实际星表不一致'):
            module._check_combined_projection(mixed, '/ziwei/chart/mingGongBranch', 'ziwei')

    def test_combined_exact_ziwei_brightness_replays_dependent_paths_only(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1987-09-22', '--hour', '19:00', '--sex', '男',
                   '--analysis-year', '2026', '--format', 'json']
        original = json.loads(subprocess.check_output(command, text=True, timeout=60))
        chart = original['ziwei']['chart']
        pidx, sidx = next((pi, si) for pi, palace in enumerate(chart['palaces'])
                          for si, star in enumerate(palace['stars']) if star['name'] == '贪狼')
        raw = f'/ziwei/chart/palaces/{pidx}/stars/{sidx}'
        stage = '/ziwei/life_reading/stage_relationship/stages'
        rows = module._pointer(original, stage)
        current = next(i for i, row in enumerate(rows) if row['legacy_stage']['current'])
        other = next(i for i, row in enumerate(rows) if row['modules']['ZW-ST01']['status'] == 'conditional')
        dependent = stage + f'/{current}/modules/ZW-ST08/status'
        independent = stage + f'/{other}/modules/ZW-ST01/status'
        self.assertEqual(module._pointer(original, dependent), 'conditional')
        self.assertEqual(module._pointer(original, raw + '/brightnessRaw'), '庙')

        saved = copy.deepcopy(original)
        module._pointer(saved, raw).update(brightnessRaw='陷', brightness='dim')
        with module._skill_scripts_path():
            from ziwei_life_reading import analyze, analyze_snapshot

            native = saved['ziwei']['chart']
            saved['ziwei']['life_reading'] = analyze(native, 1987, 2026)
            actual = analyze_snapshot(saved, requested_analysis_year=2026)
        checked = {}
        for path in (raw, raw + '/brightnessRaw', raw + '/brightness', '/ziwei/chart', '/ziwei'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei brightness disagrees'):
                module._check_combined_projection(saved, path, 'ziwei', checked)
        module._check_combined_projection(saved, raw + '/name', 'ziwei', checked)
        module._check_combined_projection(saved, independent, 'ziwei', checked)
        with self.assertRaisesRegex(ValueError, 'Ziwei stage or relationship model disagrees'):
            module._check_combined_projection(saved, dependent, 'ziwei', checked)
        self.assertEqual(actual['stage_relationship']['stages'][current]['modules']['ZW-ST08']['status'], 'withheld')
        saved['ziwei']['life_reading'] = actual
        for path in (dependent, independent, '/ziwei/life_reading/modules/ZW-T02/status',
                     '/ziwei/life_reading/case_judgments/modules/ZW-RC02/status',
                     '/ziwei/life_reading/stage_relationship/relationship/status'):
            module._check_combined_projection(saved, path, 'ziwei', checked)

    def test_combined_exact_ziwei_stage_clock_replays_the_native_bureau(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1994-02-19', '--hour', '05:25', '--sex', '男', '--timezone', 'Asia/Shanghai',
                   '--analysis-year', '2038', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True, timeout=60))
        chart = snapshot['ziwei']['chart']
        life = '/ziwei/life_reading'
        current = life + '/stage_relationship/stages/4'
        relation = life + '/stage_relationship/relationship/status'
        self.assertEqual(chart['wuxingJu'], 6)
        self.assertEqual(chart['currentDaXianIndex'], 3)
        self.assertFalse(module._pointer(snapshot, current + '/legacy_stage/current'))
        stage_leaf = current + '/modules/ZW-ST05/selected_branch'
        module._check_combined_projection(snapshot, stage_leaf, 'ziwei')

        mixed = copy.deepcopy(snapshot)
        chart = mixed['ziwei']['chart']
        chart.update(wuxingJu=5, wuxingJuName='土五局', currentDaXianIndex=4)
        for row in chart['daXians']:
            row['startAge'] -= 1
            row['endAge'] -= 1
        active_branch = chart['daXians'][4]['palaceBranch']
        for palace in chart['palaces']:
            palace['daXianAge'] = [age - 1 for age in palace['daXianAge']]
            palace['isCurrentDaXian'] = palace['branch'] == active_branch
        active_index = next(i for i, palace in enumerate(chart['palaces']) if palace['branch'] == active_branch)
        active = f'/ziwei/chart/palaces/{active_index}'
        with module._skill_scripts_path():
            from ziwei_life_reading import analyze, analyze_snapshot

            mixed['ziwei']['life_reading'] = analyze(chart, 1994, 2038)
            verified = analyze_snapshot(mixed, requested_analysis_year=2038)
        self.assertTrue(module._pointer(mixed, current + '/legacy_stage/current'))
        self.assertEqual(module._pointer(mixed, stage_leaf), 'tianxiang_yang_restriction')
        checked = {}
        for path in ('/ziwei/chart/wuxingJu', '/ziwei/chart/daXians/4/startAge', '/ziwei/chart/currentDaXianIndex',
                     active + '/daXianAge', active + '/isCurrentDaXian'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei stage evidence disagrees'):
                module._check_combined_projection(mixed, path, 'ziwei', checked)
        for path in (life + '/stage_relationship/stage_contract/covered_window', stage_leaf,
                     life + '/modules/ZW-T02/status'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei (stage or relationship model|T02 stage facts) disagree'):
                module._check_combined_projection(mixed, path, 'ziwei', checked)
        for path in ('/ziwei/chart/mingGongBranch', active + '/branch', relation):
            module._check_combined_projection(mixed, path, 'ziwei', checked)

        self.assertEqual(verified['stage_relationship']['stage_status'], 'withheld')
        self.assertEqual(verified['modules']['ZW-T02']['status'], 'withheld')
        mixed['ziwei']['life_reading'] = verified
        for path in (life + '/stage_relationship/stage_status', life + '/modules/ZW-T02/status', relation):
            module._check_combined_projection(mixed, path, 'ziwei', checked)

        wrong_year = copy.deepcopy(snapshot)
        wrapper = wrong_year['ziwei']
        wrapper['input']['ageYear'] = 2039
        chart = wrapper['chart']
        chart.update(currentAge=46, currentDaXianIndex=4)
        for palace in chart['palaces']:
            palace['isCurrentDaXian'] = palace['branch'] == active_branch
        with module._skill_scripts_path():
            wrapper['life_reading'] = analyze(chart, 1994, 2039)
            verified = analyze_snapshot(wrong_year)
        self.assertEqual(wrong_year['provenance']['resolved_age_year'], 2038)
        self.assertTrue(module._pointer(wrong_year, current + '/legacy_stage/current'))
        checked = {}
        for path in ('/ziwei/chart/currentAge', '/ziwei/chart/currentDaXianIndex', active + '/isCurrentDaXian',
                     current + '/legacy_stage/current'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei stage'):
                module._check_combined_projection(wrong_year, path, 'ziwei', checked)
        module._check_combined_projection(wrong_year, '/ziwei/chart/daXians/4/startAge', 'ziwei', checked)
        self.assertEqual(verified['modules']['ZW-T02']['status'], 'withheld')
        wrapper['life_reading'] = verified
        for path in (life + '/stage_relationship/stage_status', life + '/modules/ZW-T02/status', relation):
            module._check_combined_projection(wrong_year, path, 'ziwei', checked)

    def test_combined_exact_ziwei_derived_evidence_keeps_natal_and_stage_bindings(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1987-06-02', '--sex', '男', '--utc-offset', '8', '--format', 'json']
        early, late, later_year = [json.loads(subprocess.check_output(
            command + ['--hour', clock, '--analysis-year', year], text=True, timeout=60))
            for clock, year in (('16:59', '2026'), ('17:01', '2026'), ('16:59', '2032'))]
        base = '/ziwei/life_reading'
        module._check_combined_projection(early, base, 'ziwei')
        life = early['ziwei']['life_reading']
        life['stage_relationship'] = later_year['ziwei']['life_reading']['stage_relationship']
        with self.assertRaisesRegex(ValueError, 'Ziwei stage years disagree'):
            module._check_combined_projection(early, base + '/stage_relationship/stages', 'ziwei')
        module._check_combined_projection(early, base + '/domains', 'ziwei')
        life['case_judgments'] = late['ziwei']['life_reading']['case_judgments']
        with self.assertRaisesRegex(ValueError, 'Ziwei case domains disagree'):
            module._check_combined_projection(early, base + '/case_judgments', 'ziwei')
        life['birth_time_bounds'] = late['ziwei']['life_reading']['birth_time_bounds']
        with self.assertRaisesRegex(ValueError, 'Ziwei life birth bounds disagree'):
            module._check_combined_projection(early, base + '/birth_time_bounds', 'ziwei')
        early['ziwei']['life_reading'] = late['ziwei']['life_reading']
        with self.assertRaisesRegex(ValueError, 'Ziwei life inputs disagree'):
            module._check_combined_projection(early, '/ziwei', 'ziwei')
        module._check_combined_projection(early, '/ziwei/chart/mingGongBranch', 'ziwei')

    def test_ziwei_domain_facts_and_themes_match_the_retained_native_chart(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--hour', '19:00', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json']
        previous, current = [json.loads(subprocess.check_output(
            command + ['--solar', day], text=True, timeout=60)) for day in ('1980-10-10', '1980-10-11')]
        older, life = (snapshot['ziwei']['life_reading'] for snapshot in (previous, current))
        base = '/ziwei/life_reading'
        spouse = next(i for i, row in enumerate(life['domains']) if row['domain'] == '夫妻')
        rest = next(i for i, row in enumerate(life['domains']) if row['domain'] == '福德')
        health = next(i for i, row in enumerate(life['domains']) if row['domain'] == '疾厄')
        self.assertEqual(older['domains'][spouse]['branch'], life['domains'][spouse]['branch'])
        self.assertEqual([row['star'] for row in older['domains'][spouse]['major_topics']], ['廉贞', '天府'])
        self.assertEqual([row['star'] for row in life['domains'][spouse]['major_topics']], ['天机', '天梁'])
        self.assertTrue(life['domains'][rest]['empty_palace'])
        for path in (f'/domains/{spouse}/facts', f'/domains/{rest}/major_topics',
                     f'/domains/{health}/medical_boundary', '/modules/ZW-D07/rows', '/modules/ZW-E01'):
            module._check_combined_projection(current, base + path, 'ziwei')

        life['domains'][spouse]['facts'] = older['domains'][spouse]['facts']
        life['domains'][rest]['major_topics'] = older['domains'][rest]['major_topics']
        life['modules']['ZW-D07'] = older['modules']['ZW-D07']
        life['domains'][health]['medical_boundary'] = '过时说明'
        for path in (f'/domains/{spouse}/facts', f'/domains/{rest}/major_topics',
                     f'/domains/{health}/medical_boundary', '/modules/ZW-D07/rows', '/domains', '/modules', ''):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei domain evidence disagrees'):
                module._check_combined_projection(current, base + path, 'ziwei')
        module._check_combined_projection(current, base + f'/domains/{rest}/facts', 'ziwei')
        module._check_combined_projection(current, base + '/modules/ZW-D04', 'ziwei')
        module._check_combined_projection(current, '/ziwei/chart/mingGongBranch', 'ziwei')

        band_command = [sys.executable, '-B', str(ROOT / 'scripts/ziwei_birth_time_candidates.py'),
                        '--start', '19:00', '--end', '19:01', '--sex', '男', '--utc-offset', '8',
                        '--analysis-year', '2026']
        band = json.loads(subprocess.check_output(band_command + ['--birth-date', '1980-10-11'],
                                                 text=True, timeout=60))
        candidate, = band['candidates']
        band_life = candidate['life_reading']
        base = '/candidates/0/life_reading'
        spouse_facts = f'{base}/domains/{spouse}/facts'
        rest_card = base + '/modules/ZW-D07/rows'
        module._ziwei_birth_scope(band, spouse_facts)
        module._ziwei_birth_scope(band, rest_card)
        band_life['domains'][spouse]['facts'] = older['domains'][spouse]['facts']
        band_life['modules']['ZW-D07'] = older['modules']['ZW-D07']
        for path in (spouse_facts, rest_card):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'selected Ziwei birth-band chart'):
                module._ziwei_birth_scope(band, path)
        module._ziwei_birth_scope(band, f'{base}/domains/{rest}/facts')
        module._ziwei_birth_scope(band, '/candidates/0/native/chart/mingGongBranch')

    def test_ziwei_stage_and_relationship_cards_match_native_stars_with_same_palace_layout(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--hour', '04:25', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json']
        early, late = [json.loads(subprocess.check_output(
            command + ['--solar', day], text=True, timeout=60)) for day in ('1987-06-16', '1987-06-19')]
        stage = late['ziwei']['life_reading']['stage_relationship']
        stale = early['ziwei']['life_reading']['stage_relationship']
        self.assertEqual(stage['stage_contract'], stale['stage_contract'])
        self.assertEqual(stage['relationship']['status'], 'conditional')
        self.assertEqual(stale['relationship']['status'], 'not_triggered')
        path = '/ziwei/life_reading/stage_relationship'
        module._check_combined_projection(late, path, 'ziwei')
        card = stage['stages'][0]['modules']
        card['ZW-ST08'] = stale['stages'][0]['modules']['ZW-ST08']
        with self.assertRaisesRegex(ValueError, 'Ziwei stage or relationship model disagrees'):
            module._check_combined_projection(late, path + '/stages/0/modules/ZW-ST08/status', 'ziwei')
        module._check_combined_projection(late, path + '/relationship/status', 'ziwei')
        stage['relationship'] = stale['relationship']
        with self.assertRaisesRegex(ValueError, 'Ziwei stage or relationship model disagrees'):
            module._check_combined_projection(late, path + '/relationship/status', 'ziwei')
        module._check_combined_projection(late, '/ziwei/chart/mingGongBranch', 'ziwei')

    def test_ziwei_birth_band_stage_references_follow_the_archived_native_year(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/ziwei_birth_time_candidates.py'),
                   '--birth-date', '2007-06-18', '--start', '16:10', '--end', '16:11',
                   '--sex', '男', '--utc-offset', '8', '--analysis-year']
        old, current = [json.loads(subprocess.check_output(command + [str(year)], text=True, timeout=60))
                        for year in (2099, 2100)]
        old_candidate, = old['candidates']
        current_candidate, = current['candidates']
        old_stage = old_candidate['life_reading']['stage_relationship']
        current_stage = current_candidate['life_reading']['stage_relationship']
        prior_index = next(i for i, row in enumerate(old_stage['stages']) if row['legacy_stage']['current'])
        next_index = next(i for i, row in enumerate(current_stage['stages']) if row['legacy_stage']['current'])
        self.assertEqual(old_stage['stages'][prior_index]['legacy_stage']['domain'], '官禄')
        self.assertEqual(old_stage['stages'][prior_index]['modules']['ZW-ST01']['selected_branch'], 'tianfu_progress')
        self.assertEqual(current_stage['stages'][next_index]['legacy_stage']['domain'], '田宅')
        self.assertIsNone(current_stage['stages'][next_index]['modules']['ZW-ST01']['selected_branch'])
        base = '/candidates/0/life_reading'
        stage = base + '/stage_relationship'
        t02 = base + '/modules/ZW-T02'
        prior = f'{stage}/stages/{prior_index}'
        now = f'{stage}/stages/{next_index}'
        module._ziwei_birth_scope(old, prior + '/modules/ZW-ST01/selected_branch')
        module._ziwei_birth_scope(current, now + '/legacy_stage/current')
        module._ziwei_birth_scope(current, base)
        module._ziwei_birth_scope(current, t02 + f'/rows/0/rows/{next_index}/current')

        mixed = copy.deepcopy(current)
        mixed['candidates'][0]['life_reading']['stage_relationship'] = old_stage
        for path in (base, stage + '/stage_contract/analysis_year', prior + '/legacy_stage/current'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'stage years disagree'):
                module._ziwei_birth_scope(mixed, path)
        for path in (base + '/domains/0/facts', stage + '/relationship/status', '/candidates/0/native/chart/currentAge'):
            module._ziwei_birth_scope(mixed, path)

        stale_row = copy.deepcopy(current)
        stale_row['candidates'][0]['life_reading']['stage_relationship']['stages'][prior_index] = old_stage['stages'][prior_index]
        with self.assertRaisesRegex(ValueError, 'stage or relationship model disagrees'):
            module._ziwei_birth_scope(stale_row, prior + '/legacy_stage/current')
        module._ziwei_birth_scope(stale_row, now + '/legacy_stage/current')

        for field in ('currentAge', 'currentDaXianIndex', 'daXians'):
            older = copy.deepcopy(current)
            older_candidate = older['candidates'][0]
            del older_candidate['native']['chart'][field]
            with module._skill_scripts_path():
                from ziwei_life_reading import analyze_snapshot

                panel = analyze_snapshot(older, ziwei_candidate_id=older_candidate['id'])
            self.assertEqual(panel['stage_relationship']['stage_status'], 'withheld')
            older_candidate['life_reading'] = panel
            module._ziwei_birth_scope(older, stage + '/stage_status')
            module._ziwei_birth_scope(older, t02 + '/rows/0/status')

        mixed['candidates'][0]['native'] = old_candidate['native']
        with self.assertRaisesRegex(ValueError, 'native stage years disagree with the birth band'):
            module._ziwei_birth_scope(mixed, prior + '/legacy_stage/current')

    def test_ziwei_birth_band_chart_evidence_replays_the_selected_shichen(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/ziwei_birth_time_candidates.py'),
                   '--birth-date', '1977-04-16', '--start', '16:58', '--end', '17:02',
                   '--sex', '男', '--timezone', 'Asia/Shanghai', '--analysis-year', '2026']
        original = json.loads(subprocess.check_output(command, text=True, timeout=60))
        first, second = original['candidates']
        case = '/life_reading/case_judgments/modules/ZW-RC02/status'
        self.assertEqual(module._pointer(first, case), 'not_triggered')
        self.assertEqual(module._pointer(second, case), 'conditional')
        native = '/candidates/0/native/chart/mingGongBranch'
        for path in (native, '/candidates/0' + case, '/candidates/0', '/candidates'):
            module._ziwei_birth_scope(original, path)

        stale = copy.deepcopy(original)
        stale['candidates'][0]['life_reading']['case_judgments']['modules']['ZW-RC02'] = module._pointer(
            second, '/life_reading/case_judgments/modules/ZW-RC02')
        for path in ('/candidates/0' + case, '/candidates/0', '/candidates'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei interaction case disagrees'):
                module._ziwei_birth_scope(stale, path)
        module._ziwei_birth_scope(stale, '/candidates/0/life_reading/case_judgments/modules/ZW-RC01/status')

        mixed = copy.deepcopy(original)
        mixed['candidates'][0].update(native=copy.deepcopy(second['native']), life_reading=copy.deepcopy(second['life_reading']))
        for path in (native, '/candidates/0' + case, '/candidates/0', '/candidates'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '原生输入或原盘与出生区间复盘不一致'):
                module._ziwei_birth_scope(mixed, path)
        module._ziwei_birth_scope(mixed, '/candidates/0/civil_spans/0/start_utc')

        mixed_native = mixed['candidates'][0]['native']
        mixed_native['input'] = first['native']['input']
        mixed_native['chart']['birthInfo'] = first['native']['chart']['birthInfo']
        with self.assertRaisesRegex(ValueError, '原生输入或原盘与出生区间复盘不一致'):
            module._ziwei_birth_scope(mixed, native)
        del mixed['birth_candidate_coverage']
        with self.assertRaisesRegex(ValueError, '缺少可核的原民用出生钟面区间或区间口径'):
            module._ziwei_birth_scope(mixed, native)

        archived = copy.deepcopy(original)
        archived['timezone_source']['zone'] = 'Asia/Tokyo'
        with self.assertRaisesRegex(ValueError, '时区来源与原民用时区不一致'):
            module._ziwei_birth_scope(archived, native)
        del archived['timezone_source']
        module._ziwei_birth_scope(archived, native)

    def test_ziwei_birth_band_relationship_replays_without_requiring_stage_age(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/ziwei_birth_time_candidates.py'),
                   '--birth-date', '1967-06-17', '--start', '04:58', '--end', '05:02',
                   '--sex', '男', '--timezone', 'Asia/Shanghai', '--analysis-year']
        old, current = [json.loads(subprocess.check_output(command + [str(year)], text=True, timeout=60))
                        for year in (2025, 2026)]
        first, second = current['candidates']
        stage = '/candidates/1/life_reading/stage_relationship'
        relation = stage + '/relationship'
        old_age = stage + '/stage_contract/analysis_year'
        true_relation = module._pointer(current, relation)
        other_relation = first['life_reading']['stage_relationship']['relationship']
        self.assertEqual(other_relation['selected_branch'], 'sun_giant_gate_stability')
        self.assertEqual(true_relation['status'], 'not_triggered')
        module._ziwei_birth_scope(current, relation)

        stale = copy.deepcopy(current)
        module._pointer(stale, stage)['relationship'] = other_relation
        for path in (relation, relation + '/status', relation + '/selected_branch', stage):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Ziwei stage or relationship model disagrees'):
                module._ziwei_birth_scope(stale, path)
        module._ziwei_birth_scope(stale, old_age)
        module._ziwei_birth_scope(stale, '/candidates/1/life_reading/modules/ZW-D04/status')

        stale_age = copy.deepcopy(current)
        stale_age['candidates'][1]['life_reading']['stage_relationship'] = module._pointer(old, stage)
        self.assertEqual(module._pointer(stale_age, relation), true_relation)
        module._ziwei_birth_scope(stale_age, relation)
        with self.assertRaisesRegex(ValueError, 'stage years disagree'):
            module._ziwei_birth_scope(stale_age, old_age)

        legacy = copy.deepcopy(current)
        del legacy['candidates'][1]['native']['chart']['currentAge']
        with module._skill_scripts_path():
            from ziwei_life_reading import analyze_snapshot

            panel = analyze_snapshot(legacy, ziwei_candidate_id=second['id'])
        self.assertEqual(panel['stage_relationship']['stage_status'], 'withheld')
        self.assertEqual(panel['stage_relationship']['relationship'], true_relation)
        legacy['candidates'][1]['life_reading'] = panel
        module._ziwei_birth_scope(legacy, relation)

    def test_ziwei_t02_fact_references_follow_their_native_year_and_stage(self):
        for is_band in (False, True):
            with self.subTest(is_band=is_band):
                args = ['--sex', '男', '--utc-offset', '8', '--analysis-year']
                if is_band:
                    command = ['scripts/ziwei_birth_time_candidates.py', '--birth-date', '2007-06-18',
                               '--start', '16:10', '--end', '16:11', *args]
                    base = '/candidates/0/life_reading'
                    native = '/candidates/0/native'
                    check = module._ziwei_birth_scope
                else:
                    command = ['scripts/build_chart.py', '--solar', '2007-06-18', '--hour', '16:10',
                               '--format', 'json', *args]
                    base = '/ziwei/life_reading'
                    native = '/ziwei'

                    def check(document, path):
                        module._check_combined_projection(document, path, 'ziwei')

                old, current = [json.loads(subprocess.check_output(
                    [sys.executable, '-B', *command, str(year)], text=True, timeout=60)) for year in (2099, 2100)]
                t02 = base + '/modules/ZW-T02'
                old_t02, current_t02 = (module._pointer(doc, t02) for doc in (old, current))
                prior = old_t02['rows'][0]['current_index']
                current_path = f'/rows/0/rows/{prior}/current'
                self.assertIs(module._pointer(old_t02, current_path), True)
                self.assertIs(module._pointer(current_t02, current_path), False)
                check(current, t02 + current_path)
                check(old, t02)

                mixed = copy.deepcopy(current)
                module._pointer(mixed, base + '/modules')['ZW-T02'] = old_t02
                for path in (base, base + '/modules', t02, t02 + '/rows/0/analysis_year', t02 + current_path):
                    with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'T02 stage facts disagree'):
                        check(mixed, path)
                check(mixed, base + '/stage_relationship/stage_contract/analysis_year')
                check(mixed, base + '/domains/0/facts')

                stale_row = copy.deepcopy(current)
                module._pointer(stale_row, t02)['rows'][0]['rows'][prior] = old_t02['rows'][0]['rows'][prior]
                with self.assertRaisesRegex(ValueError, 'T02 stage facts disagree'):
                    check(stale_row, t02 + current_path)
                check(stale_row, t02 + '/rows/0/analysis_year')

                older = copy.deepcopy(current)
                del module._pointer(older, native + '/chart')['currentDaXianIndex']
                with module._skill_scripts_path():
                    from ziwei_life_reading import analyze_snapshot

                    options = {'ziwei_candidate_id': 'ziwei-band-8'} if is_band else {}
                    withheld = analyze_snapshot(older, **options)
                    explicit = analyze_snapshot(older, requested_analysis_year=2100, **options)
                self.assertEqual(withheld['modules']['ZW-T02']['status'], 'withheld')
                self.assertEqual(explicit['stage_query_scope']['status'], 'verified')
                self.assertEqual(explicit['modules']['ZW-T02'], current_t02)
                module._pointer(older, base + '/modules')['ZW-T02'] = withheld['modules']['ZW-T02']
                check(older, t02 + '/rows/0/status')

    def test_ziwei_interaction_card_with_same_palace_layout_is_checked_against_native_stars(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--hour', '04:25', '--sex', '男', '--utc-offset', '8',
                   '--analysis-year', '2026', '--format', 'json']
        early, late = [json.loads(subprocess.check_output(
            command + ['--solar', day], text=True, timeout=60)) for day in ('1987-06-16', '1987-06-19')]
        cases = late['ziwei']['life_reading']['case_judgments']['modules']
        stale = early['ziwei']['life_reading']['case_judgments']['modules']
        self.assertEqual(cases['ZW-RC02']['status'], 'conditional')
        self.assertEqual(stale['ZW-RC02']['status'], 'not_triggered')
        path = '/ziwei/life_reading/case_judgments/modules/'
        module._check_combined_projection(late, path + 'ZW-RC02/status', 'ziwei')
        cases['ZW-RC02'] = stale['ZW-RC02']
        with self.assertRaisesRegex(ValueError, 'Ziwei interaction case disagrees'):
            module._check_combined_projection(late, path + 'ZW-RC02/status', 'ziwei')
        module._check_combined_projection(late, path + 'ZW-RC01/status', 'ziwei')
        cases['ZW-RC03']['status'] = 'conditional'
        with self.assertRaisesRegex(ValueError, 'Ziwei interaction case disagrees'):
            module._check_combined_projection(late, path + 'ZW-RC03/status', 'ziwei')

    def test_qizheng_archived_rule_readings_match_the_native_point_and_selected_scope(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '2000-01-01', '--sex', '男', '--utc-offset', '8', '--lat', '35', '--lon', '120',
                   '--qizheng-tradition', 'qianyuan-palace-v1', '--analysis-year', '2026', '--format', 'json']
        early, late = [json.loads(subprocess.check_output(
            command + ['--hour', clock], text=True, timeout=60)) for clock in ('06:58', '07:42')]
        degree, tradition = 'qizheng_rule_reading', 'qizheng_traditional_reading'
        for section in (degree, tradition):
            module._check_qizheng_archive_reading(early, section)
        wrong = dict(early, **{degree: late[degree], tradition: late[tradition]})
        with self.assertRaisesRegex(ValueError, 'reading disagrees with its native chart'):
            module._check_qizheng_archive_reading(wrong, degree)
        with self.assertRaisesRegex(ValueError, 'different native chart digest'):
            module._check_qizheng_archive_reading(wrong, tradition)
        wrong[tradition].pop('chart_sha256')
        with self.assertRaisesRegex(ValueError, 'reading disagrees with its native chart'):
            module._check_qizheng_archive_reading(wrong, tradition)
        module._check_qizheng_archive_reading(wrong, 'qizheng')
        wrong_palace_claim = copy.deepcopy(early)
        wrong_palace_claim[degree]['claims'][1]['facts']['palace_lord'] = '金'
        module._check_qizheng_archive_reading(wrong_palace_claim, degree, ('claims', '0'))
        with self.assertRaisesRegex(ValueError, 'reading disagrees with its native chart'):
            module._check_qizheng_archive_reading(wrong_palace_claim, degree, ('claims', '1'))
        wrong = wrong_palace_claim[degree]['claims'][1]
        wrong['rule_id'] = 'QZ12'
        with self.assertRaisesRegex(ValueError, 'unrecognized conditional rule'):
            module._check_qizheng_archive_reading(wrong_palace_claim, degree, ('claims', '1'))
        wrong.update(rule_id='QZ02', status='withheld')
        with self.assertRaisesRegex(ValueError, 'withheld claim contains a conditional reading'):
            module._check_qizheng_archive_reading(wrong_palace_claim, degree, ('claims', '1'))
        module._check_qizheng_archive_reading(wrong_palace_claim, degree, ('claims', '0'))
        wrong_traditional_relation = copy.deepcopy(early)
        wrong_traditional_relation[tradition]['claims'][0]['calculation']['relation'] = 'invalid'
        with self.assertRaisesRegex(ValueError, 'reading disagrees with its native chart'):
            module._check_qizheng_archive_reading(wrong_traditional_relation, tradition)

        reference = dict(early, input=dict(early['input'], uncertainty_minutes=2))
        for section in (degree, tradition):
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, 'promotes an uncertain birth reference'):
                module._check_qizheng_archive_reading(reference, section)
        wrong_body = dict(early, input=dict(early['input'], qizheng_other_body='火'))
        with self.assertRaisesRegex(ValueError, 'body disagrees with its recorded selection'):
            module._check_qizheng_archive_reading(wrong_body, tradition)
        for field in ('input_facts', 'calculation'):
            wrong_element = copy.deepcopy(early)
            claim = wrong_element[tradition]['claims'][0]
            claim.pop('other_body')
            claim[field]['other_element'] = '火'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'element disagrees with its selected body'):
                module._check_qizheng_archive_reading(wrong_element, tradition)

        summary = {key: late[degree].get(key) for key in ('status', 'reason', 'claims')}
        row = dict(rule_reading=early[degree], fields=dict(rule_output=summary))
        module._check_qizheng_sample_reading(row, early['qizheng'], ['rule_reading'], {})
        with self.assertRaisesRegex(ValueError, 'rule summary disagrees with its reading'):
            module._check_qizheng_sample_reading(row, early['qizheng'], ['fields', 'rule_output'], {})
        del row['rule_reading']
        with self.assertRaisesRegex(ValueError, 'rule summary lacks its reading'):
            module._check_qizheng_sample_reading(row, early['qizheng'], ['fields', 'rule_output'], {})

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

    def test_conflict_requires_comparable_claims_and_directions(self):
        for key, value, expected, resolved_relation in (
                ('domain', '另一领域', 'mismatched domain', 'different_scope'),
                ('time_scope', '另一时段', 'mismatched time_scope', 'different_scope'),
                ('scenario_ids', ['base', 'alternate'], 'mismatched scenarios', 'different_scope'),
                ('status', 'withheld', 'uses withheld claim', 'insufficient')):
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                if key == 'scenario_ids':
                    data['scenarios'].append(dict(id='alternate', label='候选', time_basis='民用', assumptions='待比较'))
                data['claims'][1][key] = value
                data['syntheses'][0]['relation'] = 'conflict'
                self.assertTrue(any(expected in error for error in module.validate(data, self.root)))
                data['syntheses'][0]['relation'] = resolved_relation
                self.assertEqual(module.validate(data, self.root), [])

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
