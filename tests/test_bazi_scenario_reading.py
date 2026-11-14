"""Synthetic boundary comparisons, not predictive validation."""
import contextlib
import copy
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bazi_scenario_reading as reading
import bazi_qiong_xin_zi as qiong
from bazi_period_facts import period_facts
import build_chart
import pai_pan_bazi as bazi
from time_scenarios import enumerate_scenarios, resolve_civil


class Comparisons(unittest.TestCase):
    def compare(self, civil, minutes=10, basis='civil'):
        scenarios = enumerate_scenarios(civil, minutes, basis, 120)
        result = reading.analyze(scenarios)
        self.assertEqual(len(result['candidates']), len(scenarios['variants']))
        for row, variant in zip(result['candidates'], scenarios['variants']):
            self.assertEqual(row['witness_utc'], variant['witness_utc'])
            self.assertEqual(row['intervals'], variant['intervals'])
            self.assertEqual(row['pillars'], {k: ''.join(variant['fields']['bazi.' + k]) for k in bazi_core_keys()})
        return result

    def test_date_only_cli_recomputes_lichun_and_late_zi_without_inventing_an_hour(self):
        data = json.loads(subprocess.check_output(
            [sys.executable, '-B', reading.__file__, '--birth-date', '2026-02-04', '--sex', '男'],
            text=True))
        self.assertEqual(data['stable_pillars'], {})
        self.assertEqual([tuple(row['pillars'].values()) for row in data['candidates']], [
            ('乙巳', '己丑', '己酉'), ('丙午', '庚寅', '己酉'), ('丙午', '庚寅', '庚戌')])
        self.assertEqual([row['end'] for row in data['windows']], [
            bazi.solar_term_beijing(2026, 315).isoformat(), '2026-02-04T23:00:00+08:00',
            '2026-02-05T00:00:00+08:00'])
        for candidate, window in zip(data['candidates'], data['windows']):
            self.assertEqual(window['candidate_id'], candidate['id'])
            self.assertEqual(candidate['analysis']['missing_pillars'], ['hour'])
            self.assertEqual(set(candidate['analysis']['facts']), {'year', 'month', 'day'})
            self.assertTrue(candidate['analysis']['primary_spouse']['temporal_uncertainty'])
        self.assertIn('dayun_ages', data['excluded'])

    def test_date_only_cli_accepts_unpadded_birth_date(self):
        command = [sys.executable, '-B', reading.__file__, '--sex', '男', '--birth-date']
        canonical = subprocess.check_output([*command, '2026-02-04'], text=True)
        self.assertEqual(subprocess.check_output([*command, '2026-2-4'], text=True), canonical)
        invalid = subprocess.run([*command, '2026-2-30'], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, '')

    def test_date_only_repeated_and_skipped_civil_dates(self):
        try:
            resolve_civil(datetime(2024, 11, 3), zone='America/New_York')
            resolve_civil(datetime(2011, 12, 29), zone='Pacific/Apia')
        except ValueError as exc:
            self.skipTest(str(exc))
        data = reading.analyze_birth_date(date(2024, 11, 3), '男', zone='America/New_York')
        windows = data['windows']
        self.assertEqual(windows[0]['end'], '2024-11-03T02:00:00-04:00')
        self.assertEqual(windows[1]['start'], '2024-11-03T01:00:00-05:00')
        self.assertEqual(windows[0]['candidate_id'], windows[1]['candidate_id'])
        intervals = [(datetime.fromisoformat(row['start']), datetime.fromisoformat(row['end']))
                     for row in windows]
        self.assertTrue(all(left[1] == right[0] for left, right in zip(intervals, intervals[1:])))
        self.assertEqual(sum((end - start for start, end in intervals), timedelta()), timedelta(hours=25))
        with self.assertRaisesRegex(ValueError, '无可达出生时刻'):
            reading.analyze_birth_date(date(2011, 12, 30), '女', zone='Pacific/Apia')

    def test_confirmed_branch_cli_splits_lichun_and_pairs_each_age_window(self):
        data = json.loads(subprocess.check_output(
            [sys.executable, '-B', reading.__file__, '--birth-date', '2026-02-04',
             '--shichen', '寅', '--utc-offset', '8', '--sex', '男'], text=True))
        self.assertEqual(data['kind'], 'birth_date_known_shichen')
        self.assertEqual(data['stable_pillars'], {'day': '己酉', 'hour': '丙寅'})
        self.assertEqual([tuple(row['pillars'].values()) for row in data['candidates']], [
            ('乙巳', '己丑', '己酉', '丙寅'), ('丙午', '庚寅', '己酉', '丙寅')])
        term = bazi.solar_term_beijing(2026, 315)
        self.assertEqual([(w['start'], w['end']) for w in data['windows']], [
            ('2026-02-04T03:00:00+08:00', term.isoformat()),
            (term.isoformat(), '2026-02-04T05:00:00+08:00')])
        age = data['dayun_age_comparison']['segments']
        self.assertEqual([(r['start_age_months'], r['forward']) for r in age], [(118, False), (119, True)])
        self.assertEqual(age[0]['end_utc'], age[1]['start_utc'])
        self.assertFalse(any(r['end_inclusive'] for r in age))
        for candidate, row in zip(data['candidates'], age):
            self.assertEqual(candidate['analysis']['missing_pillars'], [])
            self.assertEqual(row['birth_witnesses'],
                             [{'scenario_id': candidate['id'], 'witness_utc': row['start_utc']}])

    def test_confirmed_branch_rejects_wrong_basis_and_conflicting_pillar_summaries(self):
        snapshot = reading.analyze_birth_date(date(1986, 12, 23), '男', shichen='子')
        self.assertEqual([row['pillars']['day'] for row in snapshot['candidates']], ['辛丑', '壬寅'])
        self.assertNotIn('day', snapshot['stable_pillars'])
        self.assertEqual(len(reading.birth_luck_tables(snapshot)['tables']), 2)

        wrong_candidate = copy.deepcopy(snapshot)
        wrong_candidate['candidates'][1]['pillars']['day'] = '辛丑'
        wrong_stable = copy.deepcopy(snapshot)
        wrong_stable['stable_pillars']['day'] = '辛丑'
        for conflict in (wrong_candidate, wrong_stable):
            with self.assertRaisesRegex(ValueError, '出生时辰的四柱摘要与原出生输入重算不一致'):
                reading.birth_luck_tables(conflict)
        with self.assertRaisesRegex(ValueError, '出生时辰须采用原民用钟面'):
            reading.birth_luck_tables(dict(snapshot, time_basis='apparent-solar'))

    def test_confirmed_branch_keeps_distinct_ages_for_one_four_pillar_candidate(self):
        data = reading.analyze_birth_date(date(1982, 12, 14), '男', shichen='未')
        candidate, = data['candidates']
        self.assertEqual(data['stable_pillars'], candidate['pillars'])
        ages = data['dayun_age_comparison']['segments']
        self.assertEqual([r['start_age_months'] for r in ages], [91, 90])
        self.assertEqual(ages[0]['end_utc'], '1982-12-14T06:58:41.878101+00:00')
        directions = []
        for row in ages:
            self.assertEqual(row['birth_witnesses'][0]['scenario_id'], candidate['id'])
            active, = (w for w in row['age_windows']
                       if w['start_months_inclusive'] <= 450 < w['end_months_exclusive'])
            luck = dict(layer='luck', pillar=active['pillar'], source='confirmed branch',
                        window='rounded age month 450')
            directions.append(qiong.evaluate_periods(candidate['analysis'], [luck])
                              ['luck']['conditional_model_direction'])
        self.assertEqual(directions, ['ordinary_positive_not_established',
                                     'development_configuration_relatively_favorable'])

    def test_confirmed_clock_band_reuses_folded_luck_by_actual_birth_witness(self):
        command = [sys.executable, '-B', reading.__file__, '--birth-date', '1982-12-14', '--sex', '男',
                   '--start', '12:58', '--end', '15:02', '--utc-offset', '8']
        data = json.loads(subprocess.check_output(command, text=True))
        self.assertEqual(data['kind'], 'birth_date_known_clock_band')
        self.assertEqual(data['clock_band'], {'start_inclusive': '12:58', 'end_exclusive': '15:02'})
        self.assertEqual([row['pillars']['hour'] for row in data['candidates']], ['甲午', '乙未', '丙申'])
        self.assertEqual([(row['start'][11:16], row['end'][11:16]) for row in data['windows']],
                         [('12:58', '13:00'), ('13:00', '15:00'), ('15:00', '15:02')])
        ages = data['dayun_age_comparison']['segments']
        self.assertEqual([row['start_age_months'] for row in ages], [91, 91, 90, 90])
        self.assertEqual(ages[1]['end_utc'], '1982-12-14T06:58:41.878101+00:00')
        self.assertTrue(all(not row['end_inclusive'] for row in ages))
        first, second = [row['birth_witnesses'][0] for row in ages[1:3]]
        self.assertEqual(first['scenario_id'], second['scenario_id'])
        self.assertNotEqual(first['witness_utc'], second['witness_utc'])

        tables = reading.birth_luck_tables(data)['tables']
        self.assertEqual([table['witness'] for table in tables], [row['birth_witnesses'][0] for row in ages])
        segment, = period_facts(datetime.fromisoformat('2020-06-15T09:00+08:00'),
                                datetime.fromisoformat('2020-06-15T17:00+08:00'), 'day')['segments']
        for witness, pillar, direction in ((first, '乙卯', 'ordinary_positive_not_established'),
                                           (second, '丙辰', 'development_configuration_relatively_favorable')):
            result, = qiong.evaluate_query_segment(data, segment, 450, expected_birth_witness=witness)['readings']
            self.assertEqual(result['witness'], witness)
            self.assertEqual(result['age_window']['pillar'], pillar)
            self.assertEqual(result['panels']['day']['conditional_model_direction'], direction)

        with self.assertRaisesRegex(ValueError, '须采用原民用钟面'):
            reading.birth_luck_tables(dict(data, time_basis='apparent-solar'))
        missing_age_span = copy.deepcopy(data)
        del missing_age_span['dayun_age_comparison']['segments'][2]
        with self.assertRaisesRegex(ValueError, '折月段.*与原出生输入重算不一致'):
            reading.birth_luck_tables(missing_age_span)
        wrong_candidate_summary = copy.deepcopy(data)
        wrong_candidate_summary['candidates'][0]['pillars']['hour'] = '丁酉'
        wrong_stable_summary = copy.deepcopy(data)
        wrong_stable_summary['stable_pillars']['hour'] = '丁酉'
        for wrong_summary in (wrong_candidate_summary, wrong_stable_summary):
            with self.assertRaisesRegex(ValueError, '四柱摘要与原出生输入重算不一致'):
                reading.birth_luck_tables(wrong_summary)

    def test_luck_replays_officer_candidates_for_each_verified_hour(self):
        snapshot = reading.analyze_birth_date(date(2000, 9, 13), '女', utc_offset=8,
                                              clock_band=('12:58', '13:02'))
        expected = reading.luck_contexts_at_age(snapshot, 624)
        early, late = [row['analysis'] for row in snapshot['candidates']]
        early['pattern_reasoning'], late['pattern_reasoning'] = late['pattern_reasoning'], early['pattern_reasoning']
        actual = reading.luck_contexts_at_age(snapshot, 624)
        self.assertEqual(actual, expected)
        for context in actual['contexts']:
            self.assertEqual(context['age_window']['pillar'], '己卯')
            analysis = context['analysis']
            candidate, = [row for row in analysis['pattern_reasoning']['candidates'] if row['ten_god'] == '正官']
            if analysis['facts']['hour']['pillar'] == '辛未':
                self.assertEqual((candidate['verdict'], candidate['exposed_at']), ('eligible', ['hour']))
            else:
                self.assertEqual(analysis['facts']['hour']['pillar'], '庚午')
                self.assertEqual((candidate['verdict'], candidate['exposed_at']), ('not_established', []))

    def test_luck_range_keeps_partial_ends_and_outside_ranges_per_birth_table(self):
        snapshot = reading.analyze_birth_date(date(2000, 9, 13), '女', utc_offset=8,
                                              clock_band=('12:58', '13:02'))
        original = copy.deepcopy(snapshot)
        native = reading.birth_luck_tables(snapshot)
        result = reading.luck_windows_in_range(snapshot, 621, 746)
        self.assertEqual(result['coverage'], native['coverage'])
        self.assertEqual(result['requested_age_range'], dict(start_months_inclusive=621, end_months_exclusive=746))
        for table, reference in zip(result['tables'], native['tables']):
            self.assertEqual({key: table[key] for key in reference}, reference)
            first, middle, last = table['intersections']
            self.assertEqual(first['age_range']['start_months_inclusive'], 621)
            self.assertEqual(last['age_range']['end_months_exclusive'], 746)
            self.assertEqual(first['native_window']['end_months_exclusive'], middle['native_window']['start_months_inclusive'])
            self.assertEqual(middle['native_window']['end_months_exclusive'], last['native_window']['start_months_inclusive'])
            self.assertEqual(middle['age_range'], {key: middle['native_window'][key] for key in middle['age_range']})
            self.assertGreater(first['age_range']['start_months_inclusive'], first['native_window']['start_months_inclusive'])
            self.assertLess(last['age_range']['end_months_exclusive'], last['native_window']['end_months_exclusive'])
            self.assertEqual(table['outside_table'], [])
            end = reference['windows'][-1]['end_months_exclusive']
            tail = reading.luck_windows_in_range(snapshot, end - 1, end + 1)
            clipped = next(row for row in tail['tables'] if row['witness'] == reference['witness'])
            self.assertEqual(len(clipped['intersections']), 1)
            self.assertEqual(clipped['outside_table'], [dict(start_months_inclusive=end, end_months_exclusive=end + 1)])
        self.assertEqual(snapshot, original)

    def test_luck_range_reports_startup_row_and_missing_ages_separately(self):
        snapshot = reading.analyze_birth_date(date(2000, 9, 13), '女', utc_offset=8,
                                              clock_band=('12:58', '13:02'))
        for table in reading.luck_windows_in_range(snapshot, 0, 1)['tables']:
            startup, = table['intersections']
            self.assertEqual(startup['native_window']['sequence'], '起运前')
            self.assertEqual(table['outside_table'], [])
        del snapshot['dayun_age_comparison']
        result = reading.luck_windows_in_range(snapshot, 0, 1)
        self.assertEqual(result['tables'], [])
        self.assertEqual(result['coverage'], 'birth_luck_unverified')
        self.assertTrue(result['natal_candidates'])
        for start, end in ((-1, 10), (10, 10), (20, 10), (True, 5), (3, 4.5)):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, '半开区间'):
                reading.luck_windows_in_range(snapshot, start, end)

    def test_exact_officer_luck_recovers_omitted_table_reference_marker(self):
        command = [sys.executable, '-B', build_chart.__file__, '--solar', '2008-09-11',
                   '--hour', '08:59', '--utc-offset', '8', '--sex', '女',
                   '--analysis-year', '2026', '--format', 'json']
        snapshot = json.loads(subprocess.check_output(command, text=True))
        archive = copy.deepcopy(snapshot)
        del archive['bazi']['dayun_age_windows']['birth_time_is_reference']
        compact = copy.deepcopy(archive)
        del compact['bazi']['pillars']['hour']
        del compact['bazi_core_reading']
        for age, pillar in ((614, '丙辰'), (615, '乙卯'), (734, '乙卯'), (735, '甲寅')):
            with self.subTest(age=age):
                expected = reading.luck_contexts_at_age(snapshot, age)
                self.assertEqual(reading.luck_contexts_at_age(archive, age), expected)
                self.assertEqual(reading.luck_contexts_at_age(compact, age), expected)
                context, = expected['contexts']
                self.assertEqual(context['age_window']['pillar'], pillar)
                self.assertEqual(context['analysis']['facts']['hour']['pillar'], '戊辰')

        no_precision = copy.deepcopy(compact)
        del no_precision['bazi']['hour_unknown']
        self.assertEqual(reading.luck_contexts_at_age(no_precision, 615)['contexts'], [])
        compact['bazi']['dayun_age_windows']['windows'][0]['end_months_exclusive'] += 1
        with self.assertRaisesRegex(ValueError, '大运表与出生见证的原生折月不一致'):
            reading.luck_contexts_at_age(compact, 615)

        raw = archive['bazi']
        table = raw['dayun_age_windows']
        table['birth_time_is_reference'] = True
        self.assertEqual(reading.luck_contexts_at_age(archive, 615)['contexts'], [])
        table['birth_time_is_reference'] = False
        raw['hour_unknown'] = True
        with self.assertRaisesRegex(ValueError, '时柱未知.*精确时间标记冲突'):
            reading.luck_contexts_at_age(archive, 615)
        raw['hour_unknown'] = False
        raw['pillars']['hour'] = ['己', '巳', '正财', '丙火、戊土、庚金']
        with self.assertRaisesRegex(ValueError, '原四柱与已核本命核心不一致'):
            reading.luck_contexts_at_age(archive, 615)

    def test_confirmed_clock_band_splits_solar_term_and_late_zi(self):
        winter = reading.analyze_birth_date(date(1989, 12, 7), '男', utc_offset=8, clock_band=('10:58', '13:02'))
        term = bazi.solar_term_beijing(1989, 255).isoformat()
        self.assertEqual([row['end'] for row in winter['windows']], [
            '1989-12-07T11:00:00+08:00', term, '1989-12-07T13:00:00+08:00', '1989-12-07T13:02:00+08:00'])
        self.assertEqual([row['pillars']['month'] for row in winter['candidates']], ['乙亥', '乙亥', '丙子', '丙子'])
        ages = winter['dayun_age_comparison']['segments']
        self.assertEqual([row['start_age_months'] for row in ages], [119, 119, 0, 0])
        self.assertEqual([row['status'] for row in reading.luck_contexts_at_age(winter, 0)['contexts']],
                         ['before_major_luck', 'before_major_luck', 'active', 'active'])

        late = reading.analyze_birth_date(date(1988, 2, 17), '男', utc_offset=8, clock_band=('22:59', '24:00'))
        self.assertEqual([row['end'] for row in late['windows']],
                         ['1988-02-17T23:00:00+08:00', '1988-02-18T00:00:00+08:00'])
        self.assertEqual([row['pillars']['day'] for row in late['candidates']], ['壬寅', '癸卯'])
        self.assertEqual(len(reading.birth_luck_tables(late)['tables']), 2)

    def test_confirmed_clock_band_keeps_both_reachable_fold_witnesses(self):
        try:
            resolve_civil(datetime(2024, 11, 3), zone='America/New_York')
        except ValueError as exc:
            self.skipTest(str(exc))
        fold = reading.analyze_birth_date(date(2024, 11, 3), '男', zone='America/New_York',
                                          clock_band=('00:45', '02:15'))
        self.assertEqual([(row['start'], row['end']) for row in fold['windows']], [
            ('2024-11-03T00:45:00-04:00', '2024-11-03T01:00:00-04:00'),
            ('2024-11-03T01:00:00-04:00', '2024-11-03T02:00:00-04:00'),
            ('2024-11-03T01:00:00-05:00', '2024-11-03T02:15:00-05:00')])
        _, earlier, later = reading.birth_luck_tables(fold)['tables']
        self.assertEqual(earlier['witness']['scenario_id'], later['witness']['scenario_id'])
        self.assertEqual([row['witness']['witness_utc'] for row in (earlier, later)],
                         ['2024-11-03T05:00:00+00:00', '2024-11-03T06:00:00+00:00'])
        with self.assertRaisesRegex(ValueError, '出生钟面区间无可达时刻'):
            reading.analyze_birth_date(date(2024, 3, 10), '男', zone='America/New_York', clock_band=('02:00', '03:00'))

    def test_confirmed_zi_keeps_only_two_parts_of_original_date(self):
        data = reading.analyze_birth_date(date(1988, 2, 17), '男', shichen='子')
        self.assertEqual([(w['start'], w['end']) for w in data['windows']], [
            ('1988-02-17T00:00:00+08:00', '1988-02-17T01:00:00+08:00'),
            ('1988-02-17T23:00:00+08:00', '1988-02-18T00:00:00+08:00')])
        self.assertEqual([(r['pillars']['day'], r['pillars']['hour']) for r in data['candidates']],
                         [('壬寅', '庚子'), ('癸卯', '壬子')])
        self.assertEqual([r['start_age_months'] for r in data['dayun_age_comparison']['segments']], [71, 67])

    def test_confirmed_branch_keeps_repeated_clocks_and_skips_nonexistent_clocks(self):
        try:
            resolve_civil(datetime(2024, 11, 3), zone='America/New_York')
            resolve_civil(datetime(2024, 10, 6), zone='Australia/Lord_Howe')
            resolve_civil(datetime(2018, 10, 7), zone='Antarctica/Casey')
        except ValueError as exc:
            self.skipTest(str(exc))
        fold = reading.analyze_birth_date(date(2024, 11, 3), '男', zone='America/New_York', shichen='丑')
        self.assertEqual([(w['start'], w['end']) for w in fold['windows']], [
            ('2024-11-03T01:00:00-04:00', '2024-11-03T02:00:00-04:00'),
            ('2024-11-03T01:00:00-05:00', '2024-11-03T03:00:00-05:00')])
        self.assertEqual(len(fold['candidates']), 1)
        gap = reading.analyze_birth_date(date(2024, 10, 6), '男', zone='Australia/Lord_Howe', shichen='丑')
        self.assertEqual([(w['start'], w['end']) for w in gap['windows']], [
            ('2024-10-06T01:00:00+10:30', '2024-10-06T02:00:00+10:30'),
            ('2024-10-06T02:30:00+11:00', '2024-10-06T03:00:00+11:00')])
        ages = gap['dayun_age_comparison']['segments']
        self.assertEqual([r['start_age_months'] for r in ages], [9, 9, 8])
        self.assertEqual(ages[-1]['start_utc'], '2024-10-05T15:59:57.439188+00:00')
        self.assertFalse(ages[-1]['end_inclusive'])
        with self.assertRaisesRegex(ValueError, '所给民用时辰无可达'):
            reading.analyze_birth_date(date(2018, 10, 7), '男', zone='Antarctica/Casey', shichen='卯')

    def test_s4_late_zi_recomputes_day_reference(self):
        result = self.compare(resolve_civil(datetime(1986, 1, 3, 23)))
        self.assertEqual(len(result['candidates']), 2)
        self.assertIn('day_master', result['changing_evidence'])
        self.assertIn('season', result['stable_evidence'])
        text = '\n'.join(reading.render(result))
        self.assertIn('必须按各自日干重算', text)
        for row in result['candidates']:
            self.assertIn(row['text'], text)
            for value in row['pillars'].values():
                self.assertIn(value, text)

    def test_s5_lichun_changes_season(self):
        result = self.compare(bazi.solar_term_beijing(2026, 315), 1)
        self.assertIn('season', result['changing_evidence'])
        self.assertIn('day_master', result['stable_evidence'])
        self.assertEqual({r['evidence']['season'] for r in result['candidates']}, {'丑月，节气划分的冬季', '寅月，节气划分的春季'})

    def test_numerical_mode_never_promises_stability(self):
        result = self.compare(resolve_civil(datetime(1986, 1, 3, 23)), basis='apparent-solar')
        self.assertEqual(result['stable_evidence'], {})
        self.assertTrue(result['observed_constant_evidence'])
        self.assertTrue(all(r['intervals'] == [] for r in result['candidates']))
        self.assertIn('不保证区间稳定', '\n'.join(reading.render(result)))

    def test_complete_coverage_with_no_common_evidence(self):
        # Align Lichun exactly with local 23:00: both day and season change.
        term = bazi.solar_term_beijing(2020, 315)
        utc = term.astimezone(timezone.utc)
        offset = datetime(2020, 2, 4, 23) - utc.replace(tzinfo=None)
        result = self.compare(term.astimezone(timezone(offset)), 1)
        self.assertEqual(result['stable_evidence'], {})
        self.assertEqual(result['observed_constant_evidence'], {})
        self.assertEqual(result['coverage'], 'complete_for_modeled_boundaries_not_astronomical_error')
        text = '\n'.join(reading.render(result))
        self.assertIn('区间内共同证据（仅当前模型）', text)
        self.assertIn('所列证据没有共同项', text)
        self.assertNotIn('不保证区间稳定', text)

    def test_nested_intervals_preserve_inner_candidates(self):
        civil = resolve_civil(datetime(1986, 1, 3, 23))
        small = self.compare(civil, 1)
        large = self.compare(civil, 120)
        encode = lambda r: tuple(r['pillars'].items())
        self.assertLessEqual({encode(r) for r in small['candidates']}, {encode(r) for r in large['candidates']})
        for k, v in large['stable_evidence'].items():
            self.assertEqual(small['stable_evidence'][k], v)

    def test_dst_gap_and_fold_keep_witnesses(self):
        for local, fold in [(datetime(2024, 3, 10, 1, 55), None), (datetime(2024, 11, 3, 1, 55), 0), (datetime(2024, 11, 3, 1, 55), 1)]:
            civil = resolve_civil(local, zone='America/New_York', fold=fold)
            result = self.compare(civil, 70)
            for row in result['candidates']:
                clock = datetime.fromisoformat(row['witness_utc']).astimezone(civil.tzinfo)
                self.assertEqual(clock.replace(tzinfo=None).isoformat(), row['chart_clock'])

    def test_standalone_pattern_attribution_complete_and_deduplicated(self):
        result = self.compare(resolve_civil(datetime(1986, 1, 3, 23)))
        original = copy.deepcopy(result)
        text = '\n'.join(reading.render(result))
        for row in result['candidates']:
            attribution = row['analysis']['pattern_reasoning']['attribution']
            for key in ('attribution', 'upstream_url', 'contributors_url', 'license_url',
                        'adaptation', 'interpretation_label', 'record_id'):
                self.assertIn(attribution[key], text)
            self.assertIn(row['evidence']['pattern'], text)
        self.assertEqual(text.count('格局候选依据：'), 1)
        self.assertIn('上述候选对照中的格局候选解释依 CC BY-SA 4.0 共享', text)
        self.assertEqual(result, original)

    def test_distinct_pattern_attributions_are_not_discarded(self):
        result = self.compare(resolve_civil(datetime(1986, 1, 3, 23)))
        source = result['candidates'][1]['analysis']['pattern_reasoning']['attribution']
        source['adaptation'] = '另一个候选的改编说明（合成测试）'
        source['source_span'] = {'start_line': 10, 'end_line': 12}
        text = '\n'.join(reading.render(result))
        self.assertEqual(text.count('格局候选依据：'), 2)
        self.assertIn(source['adaptation'], text)
        self.assertIn(source['path'] + ':10-12', text)

    def test_json_and_text_use_same_comparison(self):
        args = ['--solar', '1986-01-03', '--hour', '23:00', '--sex', '男', '--lat', '30', '--lon', '120', '--time-basis', 'civil', '--enumerate-scenarios', '--uncertainty-minutes', '10']
        outputs = []
        for extra in (['--format', 'json'], []):
            output = io.StringIO()
            with patch.object(build_chart, 'run_ziwei', return_value=(None, 'synthetic stub')), contextlib.redirect_stdout(output):
                build_chart.main(args + extra)
            outputs.append(output.getvalue())
        comparison = json.loads(outputs[0])['bazi_scenario_comparison']
        for row in comparison['candidates']:
            self.assertIn(row['text'], outputs[1])
        self.assertIn('以下三盘与大运数据为中心时刻', outputs[1])

    def test_native_text_keeps_approved_natal_models_under_their_candidates(self):
        for solar, hour, markers in (
            ('1982-08-10', '07:00', (
                (),
                ('官为主线，印保留兼用', '财星事实通过筛查。方向待核具体发展目标、独立官用H1及其反条'),
            )),
            ('1980-12-24', '17:00', (
                ('所选 B 的普通正支已匹配，传统模型内发展配置相对有利',
                 '保守继承无戊字面门：戊透退出普通正支'),
                ('普通正支未完整匹配',),
            )),
        ):
            with self.subTest(solar=solar):
                command = [sys.executable, '-B', build_chart.__file__, '--solar', solar,
                           '--hour', hour, '--sex', '男', '--utc-offset', '8', '--analysis-year', '2026',
                           '--uncertainty-minutes', '1', '--enumerate-scenarios', '--format', 'text']
                text = subprocess.check_output(command, text=True)
                comparison = text.split('### 出生时刻候选的八字对照', 1)[1]
                comparison = comparison.split('### 出生误差下的八字折月起运', 1)[0]
                before, after = comparison.split('**候选 2**', 1)
                for marker in markers[0]:
                    self.assertIn(marker, before)
                    self.assertNotIn(marker, after)
                for marker in markers[1]:
                    self.assertIn(marker, after)
                    self.assertNotIn(marker, before)

    def build_qiong_scenarios(self, minutes, hour='17:00'):
        cmd = [sys.executable, '-B', build_chart.__file__, '--solar', '1980-12-24',
               '--hour', hour, '--sex', '男', '--lat', '30', '--lon', '120',
               '--analysis-year', '2026', '--uncertainty-minutes', str(minutes),
               '--enumerate-scenarios', '--format', 'json']
        return json.loads(subprocess.check_output(cmd, text=True))

    def test_normal_snapshot_preserves_candidate_uncertainty_in_period_followup(self):
        snapshot = self.build_qiong_scenarios(1)
        center = snapshot['bazi_core_reading']['qiong_xin_zi_model']
        self.assertEqual(center['status'], 'withheld')
        candidates = snapshot['bazi_scenario_comparison']['candidates']
        self.assertEqual([row['pillars']['hour'] for row in candidates], ['丙申', '丁酉'])
        directions = ('development_configuration_relatively_favorable',
                      'ordinary_positive_not_established')
        for row, variant, direction in zip(candidates, snapshot['scenarios']['variants'], directions):
            with self.subTest(candidate=row['id']):
                analysis = row['analysis']
                witness = reading.core.analyze(
                    {'pillars': reading.canonical_pillars(variant['fields']),
                     'scenario_id': row['id'], 'sex': '男'})
                for key in ('facts', 'pattern_reasoning', 'strength_reasoning',
                            'reviewed_structure', 'purpose_extensions'):
                    self.assertEqual(analysis[key], witness[key])
                self.assertTrue(analysis['primary_spouse']['temporal_uncertainty'])

                clock = datetime.fromisoformat(row['chart_clock'])
                instant = datetime.fromisoformat(row['witness_utc'])
                natal = bazi.compute(clock.date(), clock.hour, clock.minute, sex='男',
                                     birth_instant=instant)
                _, age_window, pillar = natal['dayun_rows'][1]
                panels = qiong.evaluate_periods(analysis, [
                    {'layer': 'luck', 'pillar': pillar, 'source': '原生dayun_rows首步',
                     'window': age_window},
                ])
                self.assertEqual(analysis['qiong_xin_zi_model'], panels['natal'])
                self.assertEqual(panels['natal']['conditional_model_direction'], direction)
                for panel in panels.values():
                    self.assertEqual(panel['status'], 'conditional_candidate_requires_manual_review')
                    self.assertEqual(panel['scenario_id'], row['id'])
                    self.assertTrue(panel['temporal_uncertainty'])
                    self.assertFalse(panel['unique_input_result'])
                    self.assertFalse(panel['interval_stability_assessed'])

    def test_folded_luck_clips_birth_ranges_to_the_candidate_in_lifetime_and_period_reads(self):
        snapshot = self.build_qiong_scenarios(1, hour='16:59')
        boundary = '1980-12-24T09:00:00+00:00'
        spans = [dict(start_utc='1980-12-24T08:58:00+00:00', end_utc=boundary, end_inclusive=False),
                 dict(start_utc=boundary, end_utc=boundary, end_inclusive=True)]
        tables = reading.birth_luck_tables(snapshot)['tables']
        self.assertEqual([row['birth_segments'] for row in tables], [[span] for span in spans])
        self.assertEqual([row['birth_segment'] for row in tables], spans)
        self.assertEqual([row['analysis']['qiong_xin_zi_model']['conditional_model_direction'] for row in tables],
                         ['development_configuration_relatively_favorable', 'ordinary_positive_not_established'])

        start = datetime.fromisoformat('2025-11-11T00:00+08:00')
        end = datetime.fromisoformat('2025-11-12T00:00+08:00')
        for layer in ('month', 'day'):
            for query in period_facts(start, end, layer)['segments']:
                with self.subTest(layer=layer, start=query['start']):
                    window = f"[{query['start']}, {query['end']})"
                    rows = qiong.evaluate_query_segment(snapshot, query, 538, expected_window=window,
                                                        expected_layer=layer)['readings']
                    self.assertEqual([row['birth_segments'] for row in rows], [[span] for span in spans])
                    self.assertEqual([row['panels'][layer]['conditional_model_direction'] for row in rows],
                                     ['development_support_restricted', 'ordinary_positive_not_established'])

    def test_iana_fallback_preserves_disconnected_birth_ranges(self):
        cmd = [sys.executable, '-B', build_chart.__file__, '--solar', '1989-10-29',
               '--hour', '00:00', '--sex', '男', '--timezone', 'America/St_Johns', '--fold', '0',
               '--analysis-year', '2025', '--uncertainty-minutes', '70', '--enumerate-scenarios',
               '--format', 'json']
        snapshot = json.loads(subprocess.check_output(cmd, text=True))
        _, second, third = reading.birth_luck_tables(snapshot)['tables']
        first_piece, second_piece = second['birth_segments']
        self.assertIsNone(second['birth_segment'])
        self.assertEqual(first_piece['end_utc'], '1989-10-29T02:30:00+00:00')
        self.assertEqual(second_piece['start_utc'], '1989-10-29T02:31:00+00:00')
        self.assertFalse(first_piece['end_inclusive'])
        self.assertEqual(third['birth_segments'][0],
                         dict(start_utc=first_piece['end_utc'], end_utc=second_piece['start_utc'],
                              end_inclusive=False))

    def test_exact_zero_error_snapshot_keeps_exact_witness_metadata(self):
        snapshot = self.build_qiong_scenarios(0)
        row, = snapshot['bazi_scenario_comparison']['candidates']
        panel = row['analysis']['qiong_xin_zi_model']
        self.assertFalse(panel['temporal_uncertainty'])
        self.assertTrue(panel['unique_input_result'])
        self.assertEqual(panel['status'], 'conditional_requires_manual_review')


def bazi_core_keys():
    return ('year', 'month', 'day', 'hour')


if __name__ == '__main__':
    unittest.main()
