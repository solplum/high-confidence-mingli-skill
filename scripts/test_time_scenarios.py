"""Synthetic regressions for implemented contracts, not astronomical goldens."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import struct
import unittest
from unittest.mock import patch

import build_chart as chart
import pai_pan_bazi as bazi
import pai_pan_qizheng as qz
from time_scenarios import (
    enumerate_scenarios, fixed_offset_spans, parse_query_point, resolve_civil, scenario_clock_at, timezone_provenance,
)


def synthetic_tzif(version, transitions, offsets, footer=b''):
    """Create TZif bytes with explicit controls over the transition table."""
    abbreviations = b'STD\0DST\0'
    header = struct.pack('>4sc15x6I', b'TZif', version, 0, 0, 0,
                         len(transitions), len(offsets), len(abbreviations))
    indices = bytes(index for _, index in transitions)
    types = b''.join(struct.pack('>iBB', offset, dst, 4 * dst) for offset, dst in offsets)

    def block(fmt):
        return (header + b''.join(struct.pack(fmt, instant) for instant, _ in transitions)
                + indices + types + abbreviations)

    return block('>i') if version == b'\0' else block('>i') + block('>q') + b'\n' + footer + b'\n'


class ResolutionTests(unittest.TestCase):
    def test_query_clock_preserves_signed_fractional_offsets(self):
        local = datetime(2026, 11, 9, microsecond=1)
        for suffix, microseconds in (('+00:00:00.5', 500000), ('-00:00:00.5', -500000),
                                      ('+00:00:00.000001', 1), ('Z', 0)):
            with self.subTest(suffix=suffix):
                parsed = parse_query_point('2026-11-09T00:00:00.000001' + suffix)
                offset = timedelta(microseconds=microseconds)
                self.assertEqual(parsed.utcoffset(), offset)
                self.assertEqual(parsed.astimezone(timezone.utc), (local - offset).replace(tzinfo=timezone.utc))

    def test_gap_and_fold_are_not_silently_selected(self):
        with self.assertRaisesRegex(ValueError, 'gap'):
            resolve_civil(datetime(2024, 3, 10, 2, 30), zone='America/New_York')
        with self.assertRaisesRegex(ValueError, 'fold'):
            resolve_civil(datetime(2024, 11, 3, 1, 30), zone='America/New_York')
        a = resolve_civil(datetime(2024, 11, 3, 1, 30), zone='America/New_York', fold=0)
        b = resolve_civil(datetime(2024, 11, 3, 1, 30), zone='America/New_York', fold=1)
        self.assertEqual((b.astimezone(timezone.utc) - a.astimezone(timezone.utc)).total_seconds(), 3600)

    def test_normal_zone_and_invalid_selection(self):
        t = resolve_civil(datetime(1986, 1, 3), zone='Asia/Shanghai')
        self.assertEqual(t.utcoffset(), timedelta(hours=8))
        for kwargs in ({'zone': 'Missing/Zone'}, {'fold': 0}, {'zone': 'Asia/Shanghai', 'fold': 1}):
            with self.assertRaises(ValueError):
                resolve_civil(datetime(1986, 1, 3), **kwargs)

    def test_whole_minute_fixed_offsets_ignore_float_representation_noise(self):
        local = datetime(1935, 9, 15, 6)
        for minutes in range(-840, 841):
            self.assertEqual(resolve_civil(local, offset=minutes / 60).utcoffset(),
                             timedelta(minutes=minutes))
        for offset in (8.34, -8.34, 8.333333, 14.01, -14.01, float('nan')):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, '精确到整分钟'):
                resolve_civil(local, offset=offset)

    def test_timezone_source_and_mutually_exclusive_cli(self):
        self.assertEqual(len(timezone_provenance('Asia/Shanghai')['tzif_sha256']), 64)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            chart.main(['--solar', '1986-01-03', '--hour', '23:00', '--sex', '男', '--lat', '30', '--lon', '120', '--timezone', 'Asia/Shanghai', '--utc-offset', '8'])

    def test_historical_seconds_preserved_by_qizheng(self):
        t = resolve_civil(datetime(1901, 1, 1), zone='Europe/Paris')
        self.assertEqual(t.utcoffset(), timedelta(minutes=9, seconds=21))
        result, _ = qz.compute((1901, 1, 1), 0, 0, 30, 120, birth_instant=t)
        self.assertAlmostEqual(result['jd_ut'], qz.jd_from_utc(t.astimezone(timezone.utc)))

    def test_query_zone_indexes_recurring_tail_without_losing_half_open_edges(self):
        from zoneinfo import ZoneInfo
        from tzif_transitions import bind_query_zone

        raw = synthetic_tzif(b'2', (), ((-18000, 0), (-14400, 1)), b'EST5EDT,M3.2.0,M11.1.0')
        reference = ZoneInfo.from_file(io.BytesIO(raw), key='Synthetic/Recurring')
        with patch('tzif_transitions.read_tzif', return_value=(raw, 'host_iana_tzif')):
            query_zone = bind_query_zone(reference)
        start = datetime(2040, 1, 1, tzinfo=timezone.utc)
        end = datetime(2042, 1, 1, tzinfo=timezone.utc)
        cuts = [datetime.fromisoformat(clock) for clock in (
            '2040-03-11T07:00:00+00:00', '2040-11-04T06:00:00+00:00',
            '2041-03-10T07:00:00+00:00', '2041-11-03T06:00:00+00:00')]
        self.assertEqual(list(query_zone.offset_checkpoints(start, end)), cuts)
        spans = fixed_offset_spans(start, end, query_zone)
        self.assertEqual([left.astimezone(timezone.utc) for left, _ in spans], [start, *cuts])
        for cut in cuts:
            tick = timedelta(microseconds=1)
            for left, right in ((cut - tick, cut), (cut - tick, cut + tick), (cut, cut + tick)):
                self.assertEqual(fixed_offset_spans(left, right, query_zone),
                                 fixed_offset_spans(left, right, reference))

    def test_query_zone_keeps_exact_scan_for_dense_transitions_and_disagreeing_tail(self):
        from zoneinfo import ZoneInfo
        from tzif_transitions import bind_query_zone

        fixtures = (
            (synthetic_tzif(b'\0', ((90, 0), (96, 1)), ((0, 0), (-30, 0), (30, 0))), 180),
            (synthetic_tzif(b'2', ((90, 1),), ((0, 0), (3600, 0)), b'FIX0'), 3700),
        )
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        for raw, length in fixtures:
            with self.subTest(length=length):
                reference = ZoneInfo.from_file(io.BytesIO(raw), key='Synthetic/Fallback')
                with patch('tzif_transitions.read_tzif', return_value=(raw, 'host_iana_tzif')):
                    query_zone = bind_query_zone(reference)
                end = start + timedelta(seconds=length)
                self.assertEqual(fixed_offset_spans(start, end, query_zone),
                                 fixed_offset_spans(start, end, reference))

    def test_query_zone_scans_the_join_and_only_attributes_bound_source_bytes(self):
        from zoneinfo import ZoneInfo
        from tzif_transitions import bind_query_zone

        entered = datetime(2026, 3, 8, 2, tzinfo=timezone.utc)
        last = datetime(2026, 11, 1, 1, 1, tzinfo=timezone.utc)
        raw = synthetic_tzif(b'2', ((int(entered.timestamp()), 1), (int(last.timestamp()), 0)),
                             ((0, 0), (3600, 1)), b'STD0DST,M3.2.0/2,M11.1.0/2')
        reference = ZoneInfo.from_file(io.BytesIO(raw), key='Synthetic/Join')
        with patch('tzif_transitions.read_tzif', return_value=(raw, 'host_iana_tzif')):
            query_zone = bind_query_zone(reference)
        start, end = last - timedelta(minutes=2), last + timedelta(minutes=65)
        self.assertIn(last + timedelta(seconds=1), query_zone.offset_checkpoints(start, end))
        self.assertEqual(fixed_offset_spans(start, end, query_zone), fixed_offset_spans(start, end, reference))
        self.assertIsNotNone(timezone_provenance(reference.key, resolved_zone=query_zone)['tzif_sha256'])
        with patch('tzif_transitions.read_tzif', return_value=(b'broken replacement', 'host_iana_tzif')) as read:
            fallback = bind_query_zone(reference)
            self.assertIs(fallback, reference)
            self.assertIsNone(timezone_provenance(reference.key, resolved_zone=fallback)['tzif_sha256'])
            read.assert_called_once_with(reference.key)


class ScenarioTests(unittest.TestCase):
    def run_case(self, local, minutes=10, basis='civil', lon=120, zone=None, fold=None):
        return enumerate_scenarios(resolve_civil(local, zone=zone, fold=fold), minutes, basis, lon)

    def test_late_zi_and_midnight_are_distinct(self):
        result = self.run_case(datetime(1986, 1, 3, 23), 120)
        self.assertEqual(len(result['variants']), 4)
        self.assertIn('bazi.day', result['changing_fields'])
        self.assertIn('ziwei.solar_date', result['changing_fields'])
        self.assertIn('bazi.year', result['stable_fields'])

    def test_mean_solar_fractional_second_boundary(self):
        result = self.run_case(datetime(1986, 1, 3, 23), .1, 'mean-solar', 120.001)
        self.assertEqual(len(result['variants']), 2)
        boundary = result['variants'][1]['witness_utc']
        self.assertTrue(boundary.endswith('14:59:59.760000+00:00'), boundary)

    def test_lichun_actual_instant(self):
        term = bazi.solar_term_beijing(2026, 315)
        for basis in ('civil', 'mean-solar'):
            result = enumerate_scenarios(term, 1, basis, 100)
            self.assertEqual(len(result['variants']), 2)
            self.assertIn('bazi.year', result['changing_fields'])
            self.assertIn('bazi.month', result['changing_fields'])
            self.assertIn('bazi.day', result['stable_fields'])
            self.assertEqual(result['variants'][1]['witness_utc'], term.astimezone(timezone.utc).isoformat())

    def dayun_segment_at(self, result, instant):
        matches = []
        for row in result['dayun_age_comparison']['segments']:
            start = datetime.fromisoformat(row['start_utc'])
            end = datetime.fromisoformat(row['end_utc'])
            if start <= instant and (instant < end or (instant == end and row['end_inclusive'])):
                matches.append(row)
        self.assertEqual(len(matches), 1, (instant, matches))
        return matches[0]

    def test_dayun_age_changes_within_one_four_pillar_candidate(self):
        result = self.run_case(datetime(1982, 12, 14, 14), 59)
        panel = result['dayun_age_comparison']
        self.assertEqual(panel['coverage'], 'complete_for_rounded_model_not_ephemeris_error')
        self.assertEqual(panel['natal_candidate_coverage'], result['coverage'])
        variant, = result['variants']
        self.assertEqual(len(variant['intervals']), 2)
        self.assertFalse(result['changing_fields'])
        self.assertEqual([row['start_age_months'] for row in panel['segments']], [91, 90])
        for row in panel['segments']:
            first_luck = next(window for window in row['age_windows'] if window['sequence'] == '1')
            self.assertEqual(first_luck['start_months_inclusive'], row['start_age_months'])
            self.assertEqual(first_luck['end_months_exclusive'], row['start_age_months'] + 120)
            self.assertTrue(row['birth_witnesses'])
            self.assertEqual({w['scenario_id'] for w in row['birth_witnesses']}, {'candidate-1'})

    def test_dayun_interior_lichun_age_is_missed_by_whole_interval_endpoints(self):
        result = self.run_case(datetime(2026, 2, 4, 6, 2), 120)
        start = datetime.fromisoformat(result['start_utc'])
        end = datetime.fromisoformat(result['end_utc'])
        term = bazi.solar_term_beijing(2026, 315)
        rows = [self.dayun_segment_at(result, instant) for instant in (start, term, end)]
        self.assertEqual([row['start_age_months'] for row in rows], [118, 119, 118])
        self.assertEqual([row['month_pillar'] for row in rows], ['己丑', '庚寅', '庚寅'])
        self.assertEqual([row['forward'] for row in rows], [False, True, True])
        self.assertNotEqual(rows[0]['year_pillar'], rows[1]['year_pillar'])

    def test_dayun_closed_endpoint_at_jie_is_evaluated_on_new_month(self):
        term = bazi.solar_term_beijing(1983, 285)
        result = enumerate_scenarios(term - timedelta(minutes=1), 1, 'civil', 120)
        prior = self.dayun_segment_at(result, term - timedelta(microseconds=1))
        last = self.dayun_segment_at(result, term)
        self.assertEqual((prior['month_pillar'], prior['start_age_months']), ('壬子', 0))
        self.assertEqual((last['month_pillar'], last['start_age_months']), ('癸丑', 118))
        self.assertEqual(last['start_utc'], last['end_utc'])
        self.assertTrue(last['end_inclusive'])

    def test_dayun_rounding_ties_keep_native_edge_and_apparent_witnesses(self):
        term = bazi.solar_term_beijing(1983, 285)
        tick = timedelta(microseconds=1)
        for hours, expected in ((3, [1, 0, 0]), (9, [2, 2, 1])):
            tie = term - timedelta(hours=hours)
            with self.subTest(hours=hours):
                result = enumerate_scenarios(tie, 1, 'apparent-solar', 120)
                panel = result['dayun_age_comparison']
                self.assertEqual(panel['coverage'], 'complete_for_rounded_model_not_ephemeris_error')
                self.assertEqual(panel['natal_candidate_coverage'], 'numerical_witnesses_not_exhaustive')
                self.assertEqual([self.dayun_segment_at(result, t)['start_age_months']
                                  for t in (tie - tick, tie, tie + tick)], expected)
                self.assertFalse(result['stable_fields'])
                for row in panel['segments']:
                    self.assertTrue(row['birth_witnesses'])
                    for witness in row['birth_witnesses']:
                        instant = datetime.fromisoformat(witness['witness_utc'])
                        self.assertIs(self.dayun_segment_at(result, instant), row)
                        clock = scenario_clock_at(instant, tie.tzinfo, 'apparent-solar', 120)
                        birth = bazi.compute(clock.date(), clock.hour, clock.minute, birth_instant=instant)
                        self.assertEqual(birth['qiyun_years'] * 12 + birth['qiyun_months'],
                                         row['start_age_months'])
                        scenario_index = int(witness['scenario_id'].split('-')[-1]) - 1
                        fields = result['variants'][scenario_index]['fields']
                        self.assertEqual([fields['bazi.' + key] for key in birth['pillars']],
                                         [list(value[:2]) for value in birth['pillars'].values()])

    def test_gap_does_not_create_unreachable_shichen(self):
        result = self.run_case(datetime(2024, 3, 10, 1, 55), 10, zone='America/New_York')
        self.assertEqual({v['fields']['ziwei.shichen_index'] for v in result['variants']}, {1, 2})
        self.assertFalse(any('T02:' in v['chart_clock'] for v in result['variants']))

    def test_fold_intervals_are_actual_reachable_instants(self):
        result = self.run_case(datetime(2024, 11, 3, 1, 55), 70, zone='America/New_York', fold=0)
        self.assertEqual({v['fields']['ziwei.shichen_index'] for v in result['variants']}, {0, 1})
        for v in result['variants']:
            witness = datetime.fromisoformat(v['witness_utc'])
            from zoneinfo import ZoneInfo
            self.assertEqual(v['chart_clock'], witness.astimezone(ZoneInfo('America/New_York')).replace(tzinfo=None).isoformat())

    def test_caps_and_unsupported_mode_fail_closed(self):
        for local, minutes, basis in ((datetime(2000, 1, 1), 121, 'civil'),
                                      (datetime(1901, 1, 1), 120, 'civil'),
                                      (datetime(2100, 1, 1, 12), 1, 'civil'),
                                      (datetime(2000, 1, 1), 1, 'unknown')):
            with self.assertRaises(ValueError):
                self.run_case(local, minutes, basis)

    def test_supported_range_endpoints_and_zero_width(self):
        for instant in (datetime(1901, 1, 1, tzinfo=timezone.utc),
                        datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc)):
            result = enumerate_scenarios(instant, 0, 'civil', 0)
            self.assertEqual(len(result['variants']), 1)
            self.assertEqual(len(result['stable_fields']), 7)
            self.assertFalse(result['changing_fields'])

    def test_discrete_variants_cover_minute_witnesses(self):
        # Dense witness check supplements the analytical boundary partition.
        center = resolve_civil(datetime(1986, 1, 3, 23))
        for basis in ('civil', 'mean-solar'):
            result = enumerate_scenarios(center, 120, basis, 100)
            observed = [v['fields'] for v in result['variants']]
            for delta in range(-120, 121, 5):
                t = center.astimezone(timezone.utc) + timedelta(minutes=delta)
                c = t.astimezone(center.tzinfo).replace(tzinfo=None) if basis == 'civil' else chart.solar_clock(t, 100, 0)
                b = bazi.compute(c.date(), c.hour, c.minute, birth_instant=t)
                f = {'bazi.' + k: list(v[:2]) for k, v in b['pillars'].items()}
                f.update({'ziwei.solar_date': c.date().isoformat(), 'ziwei.shichen_index': ((c.hour + 1) // 2) % 12, 'ziwei.birth_year': t.astimezone(center.tzinfo).year})
                self.assertIn(f, observed)

    def test_historical_transition_interval_attribution(self):
        cases = [
            ('Australia/Lord_Howe', '2024-10-06T01:55:00', 0),
            ('Australia/Lord_Howe', '2024-04-07T01:40:00', 1),
            ('Pacific/Apia', '2011-12-29T23:55:00', 0),
            ('Pacific/Kwajalein', '1969-09-30T23:55:00', 0),
            ('Europe/Amsterdam', '1937-06-30T23:55:00', 0),
            ('Europe/Paris', '1911-03-10T23:55:00', 1),
            ('Asia/Kathmandu', '1985-12-31T23:55:00', 0),
        ]
        for zone, local, fold in cases:
            civil = resolve_civil(datetime.fromisoformat(local), zone=zone, fold=fold)
            for basis in ('civil', 'mean-solar'):
                result = enumerate_scenarios(civil, 120, basis, 120.001)
                for variant in result['variants']:
                    for interval in variant['intervals']:
                        start = datetime.fromisoformat(interval['start_utc'])
                        end = datetime.fromisoformat(interval['end_utc'])
                        probes = {start, start + (end - start) / 2,
                                  end - timedelta(microseconds=1) if end > start else end}
                        for t in probes:
                            c = t.astimezone(civil.tzinfo).replace(tzinfo=None) if basis == 'civil' else chart.solar_clock(t, 120.001, 0)
                            b = bazi.compute(c.date(), c.hour, c.minute, birth_instant=t)
                            fields = {'bazi.' + k: list(v[:2]) for k, v in b['pillars'].items()}
                            fields.update({'ziwei.solar_date': c.date().isoformat(),
                                           'ziwei.shichen_index': ((c.hour + 1) // 2) % 12,
                                           'ziwei.birth_year': t.astimezone(civil.tzinfo).year})
                            with self.subTest(zone=zone, basis=basis, instant=t):
                                self.assertEqual(fields, variant['fields'])

    def test_apparent_solar_brackets_do_not_claim_stability(self):
        # Select a synthetic instant whose apparent clock straddles 23:00.
        center = resolve_civil(datetime(1986, 1, 3, 23))
        eot = qz.equation_of_time_minutes(qz.jd_from_utc(center.astimezone(timezone.utc)))
        center -= timedelta(minutes=eot)
        result = enumerate_scenarios(center, 1, 'apparent-solar', 120)
        self.assertEqual(result['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertFalse(result['stable_fields'])
        self.assertEqual(len(result['variants']), 2)
        self.assertTrue(result['boundary_brackets'])
        for bracket in result['boundary_brackets']:
            low = datetime.fromisoformat(bracket['low_utc'])
            high = datetime.fromisoformat(bracket['high_utc'])
            self.assertLessEqual((high - low).total_seconds(), .001)
            target = datetime.fromisoformat(bracket['clock_boundary'])
            def clock(t):
                return chart.solar_clock(t, 120, qz.equation_of_time_minutes(qz.jd_from_utc(t)))
            self.assertLessEqual(clock(low), target)
            self.assertGreaterEqual(clock(high), target)
        for v in result['variants']:
            self.assertEqual(v['intervals'], [])

    def test_json_integration_and_legacy_fixed_offset(self):
        for extra in ([], ['--timezone', 'Asia/Shanghai']):
            out = io.StringIO()
            with patch.object(chart, 'run_ziwei', return_value=(None, 'stub')), contextlib.redirect_stdout(out):
                chart.main(['--solar', '1986-01-03', '--hour', '23:00', '--sex', '男', '--lat', '30', '--lon', '120', '--format', 'json', '--enumerate-scenarios', '--uncertainty-minutes', '10', *extra])
            result = json.loads(out.getvalue())
            self.assertEqual(len(result['scenarios']['variants']), 2)
            self.assertEqual(result['time']['civil'], '1986-01-03T23:00:00+08:00')


if __name__ == '__main__':
    unittest.main()
