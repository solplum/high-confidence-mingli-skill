"""Ordinary-branch, countercondition and temporal isolation regressions."""
import copy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bazi_core_reading as core
import bazi_period_facts as period_facts
import bazi_qiong_xin_zi as qiong
import bazi_scenario_reading as scenarios
import pai_pan_bazi as engine
from pai_pan_qizheng import equation_of_time_minutes, jd_from_utc


def fixture(chars):
    chars = chars.split()
    day = engine.GAN.index(chars[2][0])
    return {'pillars': {k: (p[0], p[1], '—' if k == 'day' else engine.shishen_of(day, engine.GAN.index(p[0])),
                            engine.format_canggan(p[1])) for k, p in zip(core.KEYS, chars)}}


def period(layer, pillar):
    return dict(layer=layer, pillar=pillar, source='engine-derived synthetic fixture',
                window='explicit fixture window; not an independently calculated interval')


class QiongXinZiTests(unittest.TestCase):
    def analyze(self, chars):
        return core.analyze(fixture(chars))

    def model(self, chars):
        return self.analyze(chars)['qiong_xin_zi_model']

    def test_a_positive_preserves_source_and_does_not_claim_effect_efficacy(self):
        p = self.model('壬申 丙子 辛巳 乙酉')
        self.assertEqual(p['matched_branch'], 'A_strict_ordinary_positive')
        self.assertEqual(p['conditional_model_direction'], 'development_configuration_relatively_favorable')
        self.assertFalse(p['manual_review_completed'])
        self.assertEqual(p['robustness']['status'], 'not_established')
        self.assertEqual(p['effect_assessment'], 'not_automatically_adjudicated')
        self.assertEqual(len(p['cards']), 3)
        self.assertTrue(all(c['citation']['primary_sources'] for c in p['cards']))

    def test_b_selected_reading_allows_wu_but_conservative_reading_exits(self):
        p = self.model('丙寅 戊子 辛巳 己亥')
        self.assertEqual(p['matched_branch'], 'B_selected_graded_positive')
        self.assertEqual(p['observed']['ren_visible_ids'], [])
        self.assertTrue(p['observed']['wu_visible_ids'])
        self.assertEqual(p['alternative_conservative_reading']['ordinary_positive'], 'not_established')
        self.assertTrue(any(r['id'] == 'supported_necessary_use_defeaters_and_same_scope_counterevidence'
                            for r in p['required_manual_review']))

    def test_ren_both_hidden_and_visible_cannot_bypass_failed_a_via_b(self):
        p = self.model('壬申 戊子 辛巳 丙申')
        self.assertTrue(p['observed']['ren_visible_ids'])
        self.assertTrue(p['observed']['ren_hidden_ids'])
        self.assertIsNone(p['matched_branch'])
        self.assertEqual(p['conditional_model_direction'], 'ordinary_positive_not_established')

    def test_gui_specific_counter_precedes_positive_even_with_wu_gui_pair(self):
        p = self.model('丙寅 戊子 辛巳 癸亥')
        self.assertEqual(p['matched_branch'], 'gui_visible_obstruction')
        self.assertEqual(p['conditional_model_direction'], 'development_support_restricted')
        self.assertEqual(p['specific_gui_countercondition']['rescue_assessment'], 'not_established_by_pairing_or_presence')
        self.assertTrue(any(r['kind'] == '天干五合配对' and set(r['symbols']) == set('戊癸') for r in p['natal_relations']))

    def test_native_text_keeps_known_gui_counter_when_center_is_withheld(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', '1986-12-23', '--hour', '10:00', '--sex', '男',
                   '--analysis-year', '2026', '--format', 'text']
        complete, uncertain = (
            subprocess.check_output(command + extra, text=True)
            .split('### 十一月辛完整条件模型', 1)[1].split('\n###', 1)[0]
            for extra in ([], ['--uncertainty-minutes', '5'])
        )
        self.assertIn('模型发展支持受限', complete)
        self.assertIn('完整模型结果暂缓', uncertain)
        self.assertIn('丙透有结构根且癸透', uncertain)
        self.assertIn('本结果不能推广到区间', uncertain)
        self.assertNotIn('模型发展支持受限', uncertain)
        self.assertNotIn('普通正支未完整匹配', uncertain)

    def test_withheld_temporal_render_does_not_invent_gui_counter(self):
        analysis = self.analyze('丙寅 戊子 辛巳 己亥')
        for pillar, counter_status in (('癸巳', 'present'), ('甲午', 'unknown')):
            with self.subTest(pillar=pillar):
                panel = qiong.evaluate_periods(analysis, [period('luck', None), period('year', pillar)])['year']
                rendered = '\n'.join(qiong.render(panel))
                self.assertEqual(panel['conditional_model_direction'], 'withheld')
                self.assertEqual(panel['specific_gui_countercondition']['status'], counter_status)
                self.assertIn('时间层未知：luck', rendered)
                self.assertEqual('丙透有结构根且癸透' in rendered, counter_status == 'present')
                self.assertNotIn('普通正支未完整匹配', rendered)

    def test_hidden_gui_is_not_visible_counter_and_ding_root_is_explicit_project_definition(self):
        p = self.model('丙午 戊子 辛酉 己亥')
        self.assertEqual(p['matched_branch'], 'B_selected_graded_positive')
        self.assertEqual(p['observed']['direct_bing_hidden_root_ids'], [])
        self.assertTrue(p['observed']['same_element_fire_root_ids'])
        self.assertEqual(p['specific_gui_countercondition']['status'], 'not_observed')
        self.assertIn('current_project_same_element', p['root_definition'])

    def test_incomplete_conditions_are_not_automatically_negative(self):
        for chars in ('乙酉 戊子 辛巳 己亥', '丙申 戊子 辛酉 己亥', '丙午 戊子 辛酉 己丑'):
            with self.subTest(chars=chars):
                p = self.model(chars)
                self.assertEqual(p['conditional_model_direction'], 'ordinary_positive_not_established')
                self.assertIsNone(p['matched_branch'])
        self.assertEqual(self.model('壬申 丙寅 辛巳 乙酉')['status'], 'outside_scope')

    def test_unknown_hour_and_temporal_uncertainty_do_not_assert_full_gate(self):
        result = fixture('丙寅 戊子 辛巳 己亥')
        result['pillars']['hour'] = ('未知',) * 4
        unknown = core.analyze(result)['qiong_xin_zi_model']
        self.assertEqual(unknown['conditional_model_direction'], 'withheld')
        result = fixture('丙寅 戊子 辛巳 己亥')
        central = core.analyze(result, temporal_uncertainty=True)['qiong_xin_zi_model']
        self.assertEqual(central['conditional_model_direction'], 'withheld')
        result['scenario_id'] = 'candidate-B'
        uncertain = core.analyze(result, temporal_uncertainty=True)
        periods = qiong.evaluate_periods(uncertain, [period('luck', '丙戌')])
        self.assertTrue(all(p['temporal_uncertainty'] for p in periods.values()))
        self.assertTrue(all(p['matched_branch'] == 'B_selected_graded_positive' for p in periods.values()))
        self.assertTrue(all(p['status'] == 'conditional_candidate_requires_manual_review' for p in periods.values()))
        self.assertFalse(periods['luck']['unique_input_result'])
        self.assertFalse(periods['luck']['interval_stability_assessed'])
        self.assertEqual(periods['luck']['scenario_id'], 'candidate-B')

    def test_dynamic_adaptation_does_not_rewrite_birth_and_day_cannot_pollute_month(self):
        natal = self.analyze('乙酉 戊子 辛巳 己亥')
        frozen = copy.deepcopy(natal)
        rows = [period('luck', '丙戌'), period('year', '丙午'), period('month', '己亥'), period('day', '癸巳')]
        panels = qiong.evaluate_periods(natal, rows)
        self.assertEqual(natal, frozen)
        self.assertEqual(panels['natal']['conditional_model_direction'], 'ordinary_positive_not_established')
        self.assertEqual(panels['month']['matched_branch'], 'B_selected_graded_positive')
        self.assertEqual(panels['day']['conditional_model_direction'], 'development_support_restricted')
        self.assertFalse(any(n['id'].startswith('temporal.day.') for n in panels['month']['nodes']))
        self.assertEqual(panels['month']['natal_pillars']['month'], '戊子')
        self.assertFalse(panels['day']['full_interval_coverage'])
        self.assertEqual(panels['month']['facts_origin'], 'canonical_core_facts_and_caller_supplied_engine_period_facts')

    def test_all_supplied_upper_layers_remain_included_and_unknown_is_not_empty(self):
        natal = self.analyze('丙寅 戊子 辛巳 己亥')
        panels = qiong.evaluate_periods(natal, [period('luck', '壬申'), period('year', '丙午')])
        self.assertEqual(panels['natal']['matched_branch'], 'B_selected_graded_positive')
        self.assertIsNone(panels['year']['matched_branch'])
        self.assertIn('temporal.luck.stem', panels['year']['observed']['ren_visible_ids'])
        unknown = qiong.evaluate_periods(natal, [period('luck', None), period('year', '丙午')])
        self.assertEqual(unknown['natal']['matched_branch'], 'B_selected_graded_positive')
        self.assertEqual(unknown['year']['conditional_model_direction'], 'withheld')
        self.assertEqual(unknown['year']['unknown_temporal_layers'], ['luck'])
        self.assertFalse(unknown['year']['unique_input_result'])

    def test_period_input_boundary_rejects_skips_duplicates_invalid_or_unattributed_pillars(self):
        natal = self.analyze('丙寅 戊子 辛巳 己亥')
        invalid = [[period('year', '丙午')], [period('luck', '丙戌'), period('luck', '壬申')],
                   [period('luck', '甲丑')], [dict(layer='luck', pillar='丙戌')],
                   [dict(layer='luck', source='fixture', window='fixture')],
                   [period('luck', ['丙', '戌'])]]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                qiong.evaluate_periods(natal, rows)
        del natal['qiong_xin_zi_model']
        with self.assertRaisesRegex(ValueError, '当前core'):
            qiong.evaluate_periods(natal, [period('luck', '丙戌')])

    def _cli_snapshot(self, hour, *flags, birthday='1980-12-24', longitude='120'):
        command = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'),
                   '--solar', birthday, '--hour', hour, '--sex', '男',
                   '--lat', '30', '--lon', longitude, '--analysis-year', '2026', '--format', 'json',
                   *flags]
        return json.loads(subprocess.check_output(command))

    def test_normal_cli_period_followup_rejects_mixed_birth_candidate_cache(self):
        uncertain = self._cli_snapshot('17:00', '--uncertainty-minutes', '1', '--enumerate-scenarios')
        exact = self._cli_snapshot('17:00')['bazi_core_reading']
        candidate = uncertain['bazi_scenario_comparison']['candidates'][0]['analysis']
        self.assertEqual(candidate['facts']['hour']['pillar'], '丙申')
        self.assertEqual(exact['facts']['hour']['pillar'], '丁酉')
        panels = qiong.evaluate_periods(candidate, [period('luck', '丙戌')])
        self.assertEqual(panels['luck']['scenario_id'], 'candidate-1')
        self.assertFalse(panels['luck']['unique_input_result'])
        mixed = copy.deepcopy(candidate)
        mixed['qiong_xin_zi_model'] = exact['qiong_xin_zi_model']
        with self.assertRaisesRegex(ValueError, '同一出生候选'):
            qiong.evaluate_periods(mixed, [period('luck', '丙戌')])

    def test_normal_cli_same_pillars_keep_separate_exact_and_candidate_metadata(self):
        uncertain = self._cli_snapshot('16:30', '--uncertainty-minutes', '1', '--enumerate-scenarios')
        exact = self._cli_snapshot('16:30')['bazi_core_reading']
        candidate, = uncertain['bazi_scenario_comparison']['candidates']
        core_analysis = candidate['analysis']
        self.assertEqual(core_analysis['facts'], exact['facts'])
        legacy = copy.deepcopy(core_analysis)
        del legacy['primary_spouse']
        self.assertFalse(qiong.evaluate_periods(legacy, [])['natal']['unique_input_result'])
        mixed = copy.deepcopy(core_analysis)
        mixed['qiong_xin_zi_model'] = exact['qiong_xin_zi_model']
        with self.assertRaisesRegex(ValueError, '出生时间场景冲突'):
            qiong.evaluate_periods(mixed, [])

    def test_period_followup_requires_natal_model_profile_version_and_missing_pillars(self):
        natal = self.analyze('丙寅 戊子 辛巳 己亥')
        for key, value, error in (
                ('profile', 'unrelated', '当前core'),
                ('rule_version', 'old-model', '当前core'),
                ('temporal_scope', 'day', '当前core'),
                ('missing_pillars', ['hour'], '缺柱记录冲突')):
            with self.subTest(key=key):
                mixed = copy.deepcopy(natal)
                mixed['qiong_xin_zi_model'][key] = value
                with self.assertRaisesRegex(ValueError, error):
                    qiong.evaluate_periods(mixed, [])

    def test_normal_cli_continuation_checks_natal_components_beside_pillar_labels(self):
        before = self._cli_snapshot('16:59')['bazi_core_reading']
        after = self._cli_snapshot('17:00')['bazi_core_reading']
        self.assertEqual(before['facts']['hour']['pillar'], '丙申')
        self.assertEqual(after['facts']['hour']['pillar'], '丁酉')
        for analysis, direction in ((before, 'development_configuration_relatively_favorable'),
                                    (after, 'ordinary_positive_not_established')):
            native = qiong.evaluate_periods(analysis, [])['natal']
            self.assertEqual(native, analysis['qiong_xin_zi_model'])
            self.assertEqual(native['conditional_model_direction'], direction)
        for field in ('stem', 'branch', 'ten_god', 'hidden'):
            with self.subTest(field=field):
                mixed = copy.deepcopy(after)
                mixed['facts']['hour'][field] = before['facts']['hour'][field]
                with self.assertRaisesRegex(ValueError, '干支分解、十神或藏干与引擎不一致.*hour'):
                    qiong.evaluate_periods(mixed, [])
        missing_component = copy.deepcopy(after)
        del missing_component['facts']['hour']['stem']
        with self.assertRaisesRegex(ValueError, '干支分解、十神或藏干与引擎不一致.*hour'):
            qiong.evaluate_periods(missing_component, [])
        annotated = copy.deepcopy(after)
        annotated['facts']['hour']['hidden'][0]['pointer'] = 'supplemental source pointer'
        self.assertEqual(qiong.evaluate_periods(annotated, [])['natal'], after['qiong_xin_zi_model'])

    def test_normal_cli_continuation_uses_current_natal_relations_and_groups(self):
        snapshot = self._cli_snapshot('08:00')
        natal = snapshot['bazi_core_reading']
        foreign = self._cli_snapshot('16:59')['bazi_core_reading']
        self.assertEqual([row['symbols'] for row in natal['groups']], ['申子辰'])
        self.assertNotEqual(natal['relations'], foreign['relations'])
        self.assertNotEqual(natal['groups'], foreign['groups'])
        age_window = next(row for row in snapshot['bazi']['dayun_age_windows']['windows']
                          if row['start_months_inclusive'] <= 310 < row['end_months_exclusive'])
        start, end = '2006-11-11T00:00:00+08:00', '2006-11-11T01:00:00+08:00'
        segment, = period_facts.period_facts(datetime.fromisoformat(start),
                                             datetime.fromisoformat(end), 'day')['segments']
        rows = [period('luck', age_window['pillar']), *segment['facts']]
        window = f'[{start}, {end})'
        expected = qiong.evaluate_periods(natal, rows, expected_window=window)
        self.assertEqual(expected['natal'], natal['qiong_xin_zi_model'])
        for relations, groups in ((foreign['relations'], foreign['groups']), ([], []),
                                  (natal['relations'], [])):
            with self.subTest(relations=relations, groups=groups):
                mixed = dict(natal, relations=relations, groups=groups)
                before = copy.deepcopy(mixed)
                self.assertEqual(qiong.evaluate_periods(mixed, rows, expected_window=window), expected)
                self.assertEqual(mixed, before)

    def test_date_only_native_core_still_preserves_unknown_hour_in_continuation(self):
        result = json.loads(subprocess.check_output([
            sys.executable, '-B', str(ROOT / 'scripts/bazi_scenario_reading.py'),
            '--birth-date', '1980-12-24', '--sex', '男',
        ]))
        analysis = result['candidates'][0]['analysis']
        panels = qiong.evaluate_periods(analysis, [period('luck', None)])
        self.assertEqual(panels['natal'], analysis['qiong_xin_zi_model'])
        self.assertEqual(panels['luck']['missing_pillars'], ['hour'])
        self.assertEqual(panels['luck']['unknown_temporal_layers'], ['luck'])
        self.assertEqual(panels['luck']['conditional_model_direction'], 'withheld')

    def test_disjoint_native_windows_cannot_move_countercondition_to_another_day(self):
        natal = engine.compute(date(1980, 12, 24), 16, 59, sex='男')
        analysis = core.analyze(natal)
        luck = period('luck', natal['dayun_rows'][1][2])
        earlier = period_facts.period_facts(
            datetime.fromisoformat('1988-05-10T00:00+08:00'),
            datetime.fromisoformat('1988-05-10T23:00+08:00'), 'day')['segments'][0]['facts']
        later = period_facts.period_facts(
            datetime.fromisoformat('1988-05-17T23:00+08:00'),
            datetime.fromisoformat('1988-05-18T23:00+08:00'), 'day')['segments'][0]['facts']
        a = qiong.evaluate_periods(analysis, [luck, *earlier])['day']
        b = qiong.evaluate_periods(analysis, [luck, *later])['day']
        self.assertEqual(a['conditional_model_direction'], 'development_configuration_relatively_favorable')
        self.assertEqual(b['conditional_model_direction'], 'development_support_restricted')
        with self.assertRaisesRegex(ValueError, '没有共同有效时段'):
            qiong.evaluate_periods(analysis, [luck, *earlier[:2], later[-1]])
        same_instant = dict(earlier[-1], window='[1988-05-09T16:00:00Z, 1988-05-10T15:00:00+00:00)')
        compatible = qiong.evaluate_periods(analysis, [luck, *earlier[:2], same_instant])['day']
        self.assertEqual(compatible['conditional_model_direction'], a['conditional_model_direction'])
        self.assertFalse(compatible['full_interval_coverage'])

    def test_empty_reversed_and_only_touching_half_open_windows_are_rejected(self):
        natal = self.analyze('丙寅 戊子 辛巳 己亥')
        start = '2026-11-10T00:00+08:00'
        end = '2026-11-10T23:00+08:00'
        for label in (f'[{start}, {start})', f'[{end}, {start})'):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, '没有共同有效时段'):
                qiong.evaluate_periods(natal, [dict(period('luck', '丙戌'), window=label)])
        left = dict(period('luck', '丙戌'), window=f'[{start}, {end})')
        right = dict(period('year', '丙午'), window=f'[{end}, 2026-11-11T23:00+08:00)')
        with self.assertRaisesRegex(ValueError, '没有共同有效时段'):
            qiong.evaluate_periods(natal, [left, right])

    def test_expected_query_rejects_complete_stale_cache_and_wrong_civil_clock(self):
        natal = self.analyze('乙酉 戊子 辛巳 己亥')
        luck = period('luck', '丙戌')

        def actual(start, end):
            return period_facts.period_facts(datetime.fromisoformat(start),
                                             datetime.fromisoformat(end), 'day')['segments'][0]['facts']

        start, end = '2026-11-11T00:00+08:00', '2026-11-11T01:00+08:00'
        window = f'[{start}, {end})'
        correct = actual(start, end)
        stale = actual('2026-11-15T00:00+08:00', '2026-11-15T01:00+08:00')
        utc = actual('2026-11-10T16:00+00:00', '2026-11-10T17:00+00:00')
        self.assertEqual((correct[-1]['pillar'], stale[-1]['pillar'], utc[-1]['pillar']),
                         ('己丑', '癸巳', '戊子'))
        self.assertEqual(qiong.evaluate_periods(natal, [luck, *stale])['day']['conditional_model_direction'],
                         'development_support_restricted')
        self.assertEqual(qiong.evaluate_periods(natal, [luck, *correct], expected_window=window),
                         qiong.evaluate_periods(natal, [luck, *correct]))
        for rows, message in (
                (stale, '不覆盖本次查询分段'),
                (utc, '本次查询的固定民用偏移'),
                ([*correct[:2], period('day', '己丑')], '已知年月日层须提供可核的 ISO 窗口')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                qiong.evaluate_periods(natal, [luck, *rows], expected_window=window)
        with self.assertRaisesRegex(ValueError, '不覆盖本次查询分段'):
            qiong.evaluate_periods(natal, [luck, *correct],
                                   expected_window=f'[{start}, 2026-11-11T02:00+08:00)')
        with self.assertRaisesRegex(ValueError, '正长度'):
            qiong.evaluate_periods(natal, [luck, *correct], expected_window=f'[{start}, {start})')

    def test_bound_query_rechecks_native_month_and_day_after_relabeling(self):
        snapshot = self._cli_snapshot('16:59')
        for layer, start, end, age_months, expected_pillars in (
                ('month', '2006-06-01T00:00+08:00', '2006-07-01T00:00+08:00', 305, ('癸巳', '甲午')),
                ('day', '2006-11-10T22:00+08:00', '2006-11-11T00:00+08:00', 310, ('癸卯', '甲辰'))):
            with self.subTest(layer=layer):
                context, = scenarios.luck_contexts_at_age(snapshot, age_months)['contexts']
                natal, luck = context['analysis'], context['luck']
                self.assertEqual(luck['pillar'], '辛卯')
                left, right = period_facts.period_facts(datetime.fromisoformat(start),
                                                        datetime.fromisoformat(end), layer)['segments']
                for segment, pillar, direction in zip((left, right), expected_pillars, (
                        'development_support_restricted', 'development_configuration_relatively_favorable')):
                    self.assertEqual(segment['facts'][-1]['pillar'], pillar)
                    window = f"[{segment['start']}, {segment['end']})"
                    panels = qiong.evaluate_periods(natal, [luck, *segment['facts']], expected_window=window)
                    self.assertEqual(panels[layer]['conditional_model_direction'], direction)
                combined = f"[{left['start']}, {right['end']})"
                relabeled = [dict(fact, window=combined) for fact in right['facts']]
                with self.assertRaisesRegex(ValueError, '干支换界：' + layer):
                    qiong.evaluate_periods(natal, [luck, *relabeled], expected_window=combined)
                stale_window = f"[{right['start']}, {right['end']})"
                stale = [dict(fact, window=stale_window) for fact in left['facts']]
                with self.assertRaisesRegex(ValueError, '干支与原引擎不一致：' + layer):
                    qiong.evaluate_periods(natal, [luck, *stale], expected_window=stale_window)

    def test_bound_luck_preserves_both_birth_age_segments_for_same_month_and_day(self):
        birth = scenarios.analyze_birth_date(date(1982, 12, 14), '男', shichen='未')
        contexts = scenarios.luck_contexts_at_age(birth, 450)['contexts']
        self.assertEqual([c['luck']['pillar'] for c in contexts], ['乙卯', '丙辰'])
        self.assertEqual(contexts[0]['witness']['scenario_id'], contexts[1]['witness']['scenario_id'])
        self.assertNotEqual(contexts[0]['birth_segment'], contexts[1]['birth_segment'])
        start = datetime.fromisoformat('2020-06-20T09:00+08:00')
        end = datetime.fromisoformat('2020-06-20T17:00+08:00')
        for layer in ('month', 'day'):
            query, = period_facts.period_facts(start, end, layer)['segments']
            window = f"[{query['start']}, {query['end']})"
            directions = [qiong.evaluate_periods(c['analysis'], [c['luck'], *query['facts']],
                                                 expected_window=window)[layer]['conditional_model_direction']
                          for c in contexts]
            self.assertEqual(directions, ['ordinary_positive_not_established',
                                         'development_configuration_relatively_favorable'])
        for age, expected in ((0, 'before_major_luck'), (1051, 'outside_luck_windows'), (None, 'age_unknown')):
            actual = scenarios.luck_contexts_at_age(birth, age)['contexts']
            self.assertTrue(all(c['status'] == expected and c['luck']['pillar'] is None for c in actual))

    def test_bound_luck_rejects_table_or_witness_from_other_segment_with_same_four_pillars(self):
        birth = scenarios.analyze_birth_date(date(1982, 12, 14), '男', shichen='未')
        for field, error in (('age_windows', '原生折月不一致'),
                             ('birth_witnesses', '见证不在对应出生区间')):
            mixed = copy.deepcopy(birth)
            first, second = mixed['dayun_age_comparison']['segments']
            first[field] = second[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                scenarios.luck_contexts_at_age(mixed, 450)

    def test_bound_luck_rejects_omitted_age_segment_even_with_continuous_declared_range(self):
        birth = scenarios.analyze_birth_date(date(1982, 12, 14), '男', shichen='未')
        segments = birth['dayun_age_comparison']['segments']
        omitted = segments.pop(0)
        with self.assertRaisesRegex(ValueError, '折月段、出生候选或见证与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 450)
        segments[0]['start_utc'] = omitted['start_utc']
        with self.assertRaisesRegex(ValueError, '折月段、出生候选或见证与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 450)

    def test_bound_luck_rejects_incomplete_enumerated_birth_candidates(self):
        birth = self._cli_snapshot('17:00', '--uncertainty-minutes', '1', '--enumerate-scenarios')
        raw = birth['scenarios']
        segment, = raw['dayun_age_comparison']['segments']
        segment['birth_witnesses'].pop()
        with self.assertRaisesRegex(ValueError, '折月段、出生候选或见证与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 292)
        birth['bazi_scenario_comparison']['candidates'].pop()
        raw['variants'].pop()
        raw['variants'][0]['intervals'][-1].update(end_utc=raw['end_utc'], end_inclusive=True)
        with self.assertRaisesRegex(ValueError, '枚举候选与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 292)
        del raw['dayun_age_comparison']
        with self.assertRaisesRegex(ValueError, '枚举候选与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 292)

    def test_original_birth_and_luck_survive_omitted_derived_natal_core(self):
        exact = self._cli_snapshot('16:59', '--timezone', 'Asia/Shanghai')
        estimated = self._cli_snapshot('16:59', '--timezone', 'Asia/Shanghai',
                                       '--uncertainty-minutes', '2', '--enumerate-scenarios')
        band = scenarios.analyze_birth_date(date(1980, 12, 24), '男', zone='Asia/Shanghai',
                                             clock_band=('16:58', '17:02'))
        old_exact, old_estimated, old_band = copy.deepcopy((exact, estimated, band))
        del old_exact['bazi_core_reading']
        for candidate in old_estimated['bazi_scenario_comparison']['candidates'] + old_band['candidates']:
            del candidate['analysis']

        start = datetime.fromisoformat('2005-05-15T09:00+08:00')
        end = datetime.fromisoformat('2005-05-15T17:00+08:00')
        for birth, archive in ((exact, old_exact), (estimated, old_estimated), (band, old_band)):
            self.assertEqual(scenarios.birth_luck_tables(archive), scenarios.birth_luck_tables(birth))
            for layer in ('month', 'day'):
                plan = period_facts.period_facts(start, end, layer)
                segment, = plan['segments']
                original = qiong.evaluate_query_segment(birth, segment, 292)
                recovered = qiong.evaluate_query_segment(archive, segment, 292)
                self.assertEqual(recovered, original)
                self.assertEqual(qiong.audit_query_range(plan, [original], snapshot=archive)['unread_windows'], [])
                self.assertEqual(recovered['readings'][0]['panels'][layer]['conditional_model_direction'],
                                 'development_configuration_relatively_favorable')

        wrong_exact = copy.deepcopy(old_exact)
        second = estimated['bazi_scenario_comparison']['candidates'][1]['pillars']
        wrong_exact['bazi']['pillars']['hour'] = scenarios.canonical_pillars(
            {'bazi.' + key: value for key, value in second.items()})['hour']
        with self.assertRaisesRegex(ValueError, '日柱或时柱与见证钟面不一致'):
            scenarios.birth_luck_tables(wrong_exact)
        wrong_estimated = copy.deepcopy(old_estimated)
        wrong_estimated['bazi_scenario_comparison']['candidates'][0]['pillars']['hour'] = '丁酉'
        with self.assertRaisesRegex(ValueError, '存档八字候选与原出生输入重算不一致'):
            scenarios.birth_luck_tables(wrong_estimated)
        wrong_band = copy.deepcopy(old_band)
        wrong_band['dayun_age_comparison']['segments'][0]['age_windows'][1]['pillar'] = '甲子'
        with self.assertRaisesRegex(ValueError, '原生折月不一致'):
            scenarios.birth_luck_tables(wrong_band)

    def test_omitted_total_control_comparison_replays_original_birth_witnesses(self):
        birth = self._cli_snapshot('11:00', '--timezone', 'Asia/Shanghai', '--uncertainty-minutes', '2',
                                   '--enumerate-scenarios', birthday='1987-01-02')
        archive = copy.deepcopy(birth)
        del archive['bazi_scenario_comparison']
        tables = scenarios.birth_luck_tables(birth)
        self.assertEqual(scenarios.birth_luck_tables(archive), tables)
        late = tables['tables'][-1]['witness']
        for layer in ('day', 'month'):
            with self.subTest(layer=layer):
                plan = period_facts.query_period_facts('2026-12-06T14:00', '2026-12-06T14:40', layer,
                                                       'Asia/Shanghai')
                segment, = plan['segments']
                original = qiong.evaluate_query_segment(birth, segment, 479)
                recovered = qiong.evaluate_query_segment(archive, segment, 479)
                self.assertEqual(recovered, original)
                self.assertEqual([row['panels'][layer]['conditional_model_direction']
                                  for row in recovered['readings']],
                                 ['development_support_restricted', 'development_configuration_relatively_favorable'])
                selected = qiong.evaluate_query_segment(archive, segment, 479, expected_birth_witness=late)
                self.assertEqual(selected['readings'], original['readings'][-1:])
                audit = qiong.audit_query_range(plan, [selected], snapshot=archive, expected_birth_witness=late)
                self.assertEqual(audit['unread_by_birth'], [dict(late, unread_windows=[])])
        self.assertNotIn('bazi_scenario_comparison', archive)

        for malformed in (None, {'candidates': []}):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, '缺少折月段或八字候选'):
                scenarios.birth_luck_tables(dict(archive, bazi_scenario_comparison=malformed))
        damaged = copy.deepcopy(archive)
        damaged['scenarios']['variants'].pop()
        with self.assertRaisesRegex(ValueError, '枚举候选与原出生输入重算不一致'):
            scenarios.birth_luck_tables(damaged)
        damaged = copy.deepcopy(archive)
        damaged['scenarios']['dayun_age_comparison']['segments'][0]['start_age_months'] += 1
        with self.assertRaisesRegex(ValueError, '折月段、出生候选或见证与原出生输入重算不一致'):
            scenarios.birth_luck_tables(damaged)
        damaged = copy.deepcopy(archive)
        damaged['scenarios']['interval_semantics'] = 'start_inclusive_end_exclusive'
        with self.assertRaisesRegex(ValueError, '枚举的区间口径与原输入重算不一致'):
            scenarios.birth_luck_tables(damaged)
        for bad_clock, error in (('1987-01-02T10:59:00', '出生钟面与原出生瞬间不一致'),
                                 (None, '出生钟面格式无效')):
            damaged = copy.deepcopy(archive)
            damaged['time']['chart_clock'] = bad_clock
            with self.subTest(clock=bad_clock), self.assertRaisesRegex(ValueError, error):
                scenarios.birth_luck_tables(damaged)
        damaged = copy.deepcopy(archive)
        damaged['scenarios']['scope'] = 'unsupported_scope'
        with self.assertRaisesRegex(ValueError, '枚举的范围声明与原输入重算不一致'):
            scenarios.birth_luck_tables(damaged)
        damaged = copy.deepcopy(archive)
        damaged['input']['enumerate_scenarios'] = False
        with self.assertRaisesRegex(ValueError, '误差枚举标记与存档候选不一致'):
            scenarios.birth_luck_tables(damaged)
        legacy = copy.deepcopy(archive)
        del legacy['time']['chart_clock'], legacy['scenarios']['scope'], legacy['input']['enumerate_scenarios']
        self.assertEqual(scenarios.birth_luck_tables(legacy), tables)

    def test_bound_luck_retains_replayed_total_control_candidates_without_age_table(self):
        birth = self._cli_snapshot('17:00', '--uncertainty-minutes', '1', '--enumerate-scenarios')
        original = birth['scenarios']
        del original['dayun_age_comparison']
        result = scenarios.birth_luck_tables(birth)
        candidates = result['natal_candidates']
        archived = copy.deepcopy(birth)
        for candidate in archived['bazi_scenario_comparison']['candidates']:
            del candidate['analysis']
        self.assertEqual(scenarios.birth_luck_tables(archived), result)
        del archived['bazi_scenario_comparison']
        self.assertEqual(scenarios.birth_luck_tables(archived), result)
        self.assertEqual(result['coverage'], original['coverage'])
        self.assertEqual(result['tables'], [])
        self.assertEqual([candidate['pillars']['hour'] for candidate in candidates], ['丙申', '丁酉'])
        self.assertEqual([candidate['birth_segments'] for candidate in candidates],
                         [variant['intervals'] for variant in original['variants']])
        for layer in ('day', 'month'):
            plan = period_facts.period_facts(datetime.fromisoformat('2026-11-25T14:00+08:00'),
                                             datetime.fromisoformat('2026-11-25T14:40+08:00'), layer)
            segment, = plan['segments']
            reads = qiong.evaluate_query_segment(birth, segment, 551)
            self.assertEqual(reads['natal_candidate_coverage'], dict(read=['candidate-1', 'candidate-2'], unread=[]))
            self.assertTrue(all(row['witness'] is None and row['age_window'] is None and
                                row['luck_status'] == 'birth_luck_unverified' and
                                row['panels'][layer]['status'] == 'withheld' for row in reads['readings']))
            audited = qiong.audit_query_range(plan, [reads], snapshot=birth)
            self.assertEqual(audited['unread_by_birth'], [
                dict(scenario_id=candidate['id'], witness_utc=None, unread_windows=[]) for candidate in candidates])
            verified_cores = [candidates[0]['analysis']]
            selected = qiong.evaluate_query_segment(birth, segment, 551, verified_natal_cores=verified_cores)
            selected_audit = qiong.audit_query_range(plan, [selected], snapshot=birth,
                                                     verified_natal_cores=verified_cores)
            self.assertEqual(selected_audit['unread_by_birth'][1]['unread_windows'], [selected['window']])

        corrupted = copy.deepcopy(birth)
        corrupted['bazi_scenario_comparison']['candidates'][0]['analysis']['facts']['hour']['pillar'] = '丁酉'
        with self.assertRaisesRegex(ValueError, '本命核心的四柱与原出生输入重算不一致'):
            scenarios.birth_luck_tables(corrupted)
        corrupted = copy.deepcopy(birth)
        corrupted['scenarios']['variants'][0]['intervals'][-1]['end_inclusive'] = True
        with self.assertRaisesRegex(ValueError, '枚举候选与原出生输入重算不一致'):
            scenarios.birth_luck_tables(corrupted)
        with self.assertRaisesRegex(ValueError, '缺少折月段或八字候选'):
            scenarios.birth_luck_tables(dict(birth, scenarios=dict(original, dayun_age_comparison=None)))

        apparent = self._cli_snapshot('17:00', '--time-basis', 'apparent-solar',
                                      '--uncertainty-minutes', '4', '--enumerate-scenarios')
        del apparent['scenarios']['dayun_age_comparison']
        apparent_natal = scenarios.birth_luck_tables(apparent)
        self.assertEqual(apparent_natal['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertTrue(all(row['witness_utc'] and not row['birth_segments']
                            for row in apparent_natal['natal_candidates']))
        segment, = period_facts.period_facts(datetime.fromisoformat('1980-12-24T17:00+08:00'),
                                             datetime.fromisoformat('1980-12-24T17:02+08:00'), 'day')['segments']
        with self.assertRaisesRegex(ValueError, '查询时段与原出生范围相交'):
            qiong.evaluate_query_segment(apparent, segment, None)

    def test_bound_luck_rechecks_apparent_solar_samples_without_promoting_coverage(self):
        birth = self._cli_snapshot('17:00', '--time-basis', 'apparent-solar',
                                   '--uncertainty-minutes', '4', '--enumerate-scenarios')
        result = scenarios.luck_contexts_at_age(birth, 292)
        self.assertEqual(result['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertEqual([c['analysis']['facts']['hour']['pillar'] for c in result['contexts']],
                         ['丙申', '丁酉'])
        archive = copy.deepcopy(birth)
        del archive['bazi_scenario_comparison']
        del archive['input']['dut1_seconds']
        self.assertEqual(scenarios.luck_contexts_at_age(archive, 292), result)
        del archive['qizheng']['horizon_contract']['dut1_seconds']
        self.assertEqual(scenarios.luck_contexts_at_age(archive, 292), result)
        segment, = birth['scenarios']['dayun_age_comparison']['segments']
        segment['birth_witnesses'].pop()
        with self.assertRaisesRegex(ValueError, '折月段、出生候选或见证与原出生输入重算不一致'):
            scenarios.luck_contexts_at_age(birth, 292)

    def test_missing_original_error_cannot_make_a_nonzero_enumeration_exact(self):
        birth = self._cli_snapshot('16:59', '--uncertainty-minutes', '2', '--enumerate-scenarios')
        start = datetime.fromisoformat('2005-05-15T09:00+08:00')
        end = datetime.fromisoformat('2005-05-15T17:00+08:00')
        segment, = period_facts.period_facts(start, end, 'day')['segments']
        result = qiong.evaluate_query_segment(birth, segment, 292)
        self.assertEqual([row['panels']['day']['conditional_model_direction'] for row in result['readings']],
                         ['development_configuration_relatively_favorable', 'ordinary_positive_not_established'])
        exact = self._cli_snapshot('16:59')
        exact_core = exact['bazi_core_reading']
        exact['scenarios'] = birth['scenarios']
        self.assertEqual(scenarios.birth_luck_tables(exact)['coverage'], 'single_birth_input')

        for error, minutes in (('原出生误差分钟缺失', None), ('与原输入的误差分钟不一致', 0)):
            with self.subTest(minutes=minutes):
                archive = copy.deepcopy(birth)
                if minutes is None:
                    del archive['input']['uncertainty_minutes']
                else:
                    archive['input']['uncertainty_minutes'] = minutes
                for key in ('qiong_xin_zi_model', 'primary_spouse'):
                    del archive['bazi_core_reading'][key]
                with self.assertRaisesRegex(ValueError, error):
                    scenarios.birth_luck_tables(archive)
                del archive['bazi']['dayun_age_windows']
                with self.assertRaisesRegex(ValueError, error):
                    scenarios.recorded_birth_context(archive, verified_natal_cores=[exact_core])
                with self.assertRaisesRegex(ValueError, error):
                    qiong.evaluate_query_segment(archive, segment, None, verified_natal_cores=[exact_core])

    def test_enumerated_luck_replays_original_clock_when_derived_clock_is_missing(self):
        start = datetime.fromisoformat('2005-05-15T09:00+08:00')
        end = datetime.fromisoformat('2005-05-15T17:00+08:00')
        plan = period_facts.period_facts(start, end, 'day')
        segment, = plan['segments']
        for flags in (('--utc-offset', '8'), ('--timezone', 'Asia/Shanghai')):
            birth = self._cli_snapshot('17:00', '--uncertainty-minutes', '1', '--enumerate-scenarios', *flags)
            original_tables = scenarios.birth_luck_tables(birth)
            original = qiong.evaluate_query_segment(birth, segment, 292)
            self.assertEqual([row['panels']['day']['conditional_model_direction'] for row in original['readings']],
                             ['development_configuration_relatively_favorable', 'ordinary_positive_not_established'])
            for missing in ('time', 'civil'):
                with self.subTest(flags=flags, missing=missing):
                    old = copy.deepcopy(birth)
                    del (old if missing == 'time' else old['time'])[missing]
                    self.assertEqual(scenarios.birth_luck_tables(old), original_tables)
                    actual = qiong.evaluate_query_segment(old, segment, 292)
                    self.assertEqual(actual, original)
                    coverage = qiong.audit_query_range(plan, [actual], snapshot=old)
                    self.assertEqual(coverage['unread_windows'], [])
                    self.assertTrue(all(not row['unread_windows'] for row in coverage['unread_by_birth']))
            birth['time']['civil'] = '1980-12-24T17:01:00+08:00'
            with self.assertRaisesRegex(ValueError, '民用出生钟面'):
                scenarios.birth_luck_tables(birth)

    def test_retained_birth_comparison_cannot_override_original_uncertainty(self):
        birth = self._cli_snapshot('11:00', '--timezone', 'Asia/Shanghai', '--uncertainty-minutes', '2',
                                   '--enumerate-scenarios', birthday='1987-01-02')
        start, end = (datetime.fromisoformat(f'2026-12-06T{clock}+08:00') for clock in ('14:00', '14:40'))
        for layer in ('month', 'day'):
            with self.subTest(layer=layer):
                plan = period_facts.period_facts(start, end, layer)
                segment, = plan['segments']
                original = qiong.evaluate_query_segment(birth, segment, 479)
                self.assertEqual([row['panels'][layer]['conditional_model_direction'] for row in original['readings']],
                                 ['development_support_restricted', 'development_configuration_relatively_favorable'])
                old = copy.deepcopy(birth)
                del old['input']['enumerate_scenarios'], old['bazi_core_reading']
                self.assertEqual(qiong.evaluate_query_segment(old, segment, 479), original)
                for minutes, error in ((None, '原出生误差分钟缺失'), (0, '与原输入的误差分钟不一致')):
                    archive = copy.deepcopy(old)
                    if minutes is None:
                        del archive['input']['uncertainty_minutes']
                    else:
                        archive['input'].update(uncertainty_minutes=0, enumerate_scenarios=False)
                    with self.subTest(minutes=minutes), self.assertRaisesRegex(ValueError, error):
                        qiong.evaluate_query_segment(archive, segment, 479)
                    with self.subTest(minutes=minutes), self.assertRaisesRegex(ValueError, error):
                        qiong.audit_query_range(plan, [original], snapshot=archive)
                age_only = copy.deepcopy(old)
                del age_only['input']['uncertainty_minutes'], age_only['bazi_scenario_comparison']
                del age_only['scenarios']['start_utc'], age_only['scenarios']['end_utc']
                for inputs in (age_only['input'], dict(age_only['input'], enumerate_scenarios=False)):
                    with self.assertRaisesRegex(ValueError, '原出生误差分钟缺失'):
                        qiong.evaluate_query_segment(dict(age_only, input=inputs), segment, 479)
                raw_only = dict(old, input=dict(age_only['input'], enumerate_scenarios=False),
                                scenarios=dict(old['scenarios']))
                del raw_only['scenarios']['dayun_age_comparison'], raw_only['bazi_scenario_comparison']
                with self.assertRaisesRegex(ValueError, '原出生误差分钟缺失'):
                    qiong.evaluate_query_segment(raw_only, segment, 479)

        for path, value, error in (
                (('input', 'enumerate_scenarios'), False, '误差枚举标记'),
                (('scenarios', 'scope'), 'unsupported_scope', '范围声明'),
                (('scenarios', 'interval_semantics'), 'start_inclusive_end_exclusive', '区间口径'),
                (('bazi_scenario_comparison', 'coverage'), 'numerical_witnesses_not_exhaustive', '覆盖口径'),
                (('bazi_scenario_comparison', 'context', 'end_utc'), birth['scenarios']['start_utc'], '实际范围'),
                (('time', 'chart_clock'), '1987-01-02T10:58:00', '出生钟面与原出生瞬间不一致')):
            archive = copy.deepcopy(birth)
            owner = archive
            for key in path[:-1]:
                owner = owner[key]
            owner[path[-1]] = value
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, error):
                scenarios.birth_luck_tables(archive)
        archive = copy.deepcopy(birth)
        archive['bazi_scenario_comparison']['candidates'][0]['intervals'].clear()
        with self.assertRaisesRegex(ValueError, '候选与原出生输入重算不一致'):
            scenarios.birth_luck_tables(archive)

    def test_bound_luck_replays_hour_at_each_witness_even_with_one_age_table(self):
        birth = self._cli_snapshot('17:00', '--uncertainty-minutes', '1', '--enumerate-scenarios')
        contexts = scenarios.luck_contexts_at_age(birth, 292)['contexts']
        self.assertEqual([c['analysis']['facts']['hour']['pillar'] for c in contexts], ['丙申', '丁酉'])
        self.assertEqual(contexts[0]['luck'], contexts[1]['luck'])
        start = datetime.fromisoformat('2005-05-15T09:00+08:00')
        end = datetime.fromisoformat('2005-05-15T17:00+08:00')
        query, = period_facts.period_facts(start, end, 'day')['segments']
        window = f"[{query['start']}, {query['end']})"
        directions = [qiong.evaluate_periods(c['analysis'], [c['luck'], *query['facts']],
                                             expected_window=window)['day']['conditional_model_direction']
                      for c in contexts]
        self.assertEqual(directions, ['development_configuration_relatively_favorable',
                                     'ordinary_positive_not_established'])

        wrong = copy.deepcopy(birth)
        segment, = wrong['scenarios']['dayun_age_comparison']['segments']
        first, second = segment['birth_witnesses']
        second['scenario_id'] = first['scenario_id']
        with self.assertRaisesRegex(ValueError, '日柱或时柱与见证钟面不一致'):
            scenarios.luck_contexts_at_age(wrong, 292)
        exact = self._cli_snapshot('16:59')
        exact['bazi_core_reading'] = contexts[1]['analysis']
        with self.assertRaisesRegex(ValueError, '日柱或时柱与见证钟面不一致'):
            scenarios.luck_contexts_at_age(exact, 292)
        exact['time']['chart_clock'] = birth['time']['chart_clock']
        with self.assertRaisesRegex(ValueError, '所选口径的出生钟面与原出生瞬间不一致'):
            scenarios.luck_contexts_at_age(exact, 292)

    def test_exact_luck_replays_original_dut1_without_using_cached_eot(self):
        jd = jd_from_utc(datetime(1980, 12, 24, 9, tzinfo=timezone.utc))
        lon = 120 - (equation_of_time_minutes(jd) + equation_of_time_minutes(jd + 0.9 / 86400)) / 8
        flags = ('--time-basis', 'apparent-solar', '--lon', str(lon), '--dut1-seconds')
        original, other = (self._cli_snapshot('17:00', *flags, value) for value in ('0', '0.9'))

        def contexts(snapshot):
            return scenarios.luck_contexts_at_age(snapshot, 292)['contexts']

        first, = contexts(original)
        second, = contexts(other)
        self.assertEqual([c['analysis']['facts']['hour']['pillar'] for c in (first, second)], ['丁酉', '丙申'])
        recovered = copy.deepcopy(original)
        del recovered['qizheng']['eot_minutes']
        self.assertEqual(contexts(recovered), [first])
        del recovered['input']['dut1_seconds']
        self.assertEqual(contexts(recovered), [first])
        del recovered['time']
        self.assertEqual(contexts(recovered), [first])
        del recovered['qizheng']['horizon_contract']['dut1_seconds']
        self.assertEqual(scenarios.birth_luck_tables(recovered),
                         {'coverage': 'birth_luck_unverified', 'tables': []})
        wrong_profile = copy.deepcopy(other)
        wrong_profile['input']['qizheng_profile'] = 'legacy-v1'
        with self.assertRaisesRegex(ValueError, 'DUT1与legacy-v1'):
            contexts(wrong_profile)

        original['bazi_core_reading'] = other['bazi_core_reading']
        original['time']['chart_clock'] = other['time']['chart_clock']
        original['qizheng']['eot_minutes'] = other['qizheng']['eot_minutes']
        with self.assertRaisesRegex(ValueError, '所选口径的出生钟面与原出生瞬间不一致'):
            contexts(original)

    def test_exact_luck_rejects_changed_original_time_and_sex_before_reusing_cache(self):
        birth = self._cli_snapshot('17:00')
        shifted = copy.deepcopy(birth)
        for key in ('civil', 'instant_bj', 'chart_clock'):
            shifted['time'][key] = (datetime.fromisoformat(shifted['time'][key]) + timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, '民用出生钟面或UTC偏移'):
            scenarios.birth_luck_tables(shifted)
        changed_offset = copy.deepcopy(birth)
        changed_offset['input']['utc_offset'] = 9
        with self.assertRaisesRegex(ValueError, '民用出生钟面或UTC偏移'):
            scenarios.birth_luck_tables(changed_offset)
        for sex in ('女', '未确认'):
            with self.subTest(sex=sex):
                wrong = copy.deepcopy(birth)
                wrong['bazi_core_reading']['primary_spouse']['sex'] = sex
                with self.assertRaisesRegex(ValueError, '八字出生性别'):
                    scenarios.birth_luck_tables(wrong)
        unknown = copy.deepcopy(birth)
        unknown['input']['sex'] = '未确认'
        unknown['bazi']['sex'] = '未确认'
        unknown['bazi_core_reading']['primary_spouse']['sex'] = '未确认'
        with self.assertRaisesRegex(ValueError, '八字出生性别无效'):
            scenarios.birth_luck_tables(unknown)

    def test_exact_luck_rejects_native_tables_from_other_iana_fold(self):
        cmd = [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'), '--solar', '2024-11-03',
               '--hour', '01:30', '--sex', '女', '--lat', '40', '--lon', '-75', '--analysis-year', '2026',
               '--timezone', 'America/New_York', '--time-basis', 'apparent-solar', '--format', 'json', '--fold']
        first, second = [json.loads(subprocess.check_output([*cmd, fold])) for fold in ('0', '1')]
        for snapshot in (first, second):
            self.assertEqual(scenarios.birth_luck_tables(snapshot)['coverage'], 'single_birth_input')
        for key in ('time', 'qizheng', 'bazi', 'bazi_core_reading'):
            first[key] = second[key]
        with self.assertRaisesRegex(ValueError, '民用出生钟面或UTC偏移'):
            scenarios.birth_luck_tables(first)

    def test_known_birth_band_cannot_be_promoted_to_an_exact_model_input(self):
        birthday = date(1980, 12, 24)
        band = scenarios.analyze_birth_date(birthday, '男', utc_offset=8, clock_band=('16:58', '17:02'))
        estimated = self._cli_snapshot('16:59', '--uncertainty-minutes', '3', '--enumerate-scenarios')
        for snapshot, candidates in ((band, band['candidates']),
                                     (estimated, estimated['bazi_scenario_comparison']['candidates'])):
            with self.subTest(kind=snapshot.get('kind', 'estimated')):
                tables = scenarios.birth_luck_tables(snapshot)['tables']
                self.assertEqual(len(tables), 2)
                for table in tables:
                    model = qiong.evaluate_periods(table['analysis'], [])['natal']
                    self.assertTrue(model['temporal_uncertainty'])
                    self.assertFalse(model['unique_input_result'])
                for name in ('qiong_xin_zi_model', 'primary_spouse'):
                    candidates[0]['analysis'][name]['temporal_uncertainty'] = False
                with self.assertRaisesRegex(ValueError, '出生时间场景与原出生范围不一致'):
                    scenarios.birth_luck_tables(snapshot)

    def test_malformed_saved_luck_table_reports_table_damage(self):
        birth = self._cli_snapshot('16:59')
        raw = birth['bazi']
        del raw['dayun_age_windows']['windows']
        with self.assertRaisesRegex(ValueError, '原折月大运表缺少有效运段'):
            scenarios.birth_luck_tables(birth)
        raw['dayun_age_windows'] = []
        with self.assertRaisesRegex(ValueError, '原折月大运表须为对象'):
            scenarios.birth_luck_tables(birth)
        del raw['dayun_age_windows']
        recovered = scenarios.birth_luck_tables(birth)
        self.assertEqual((recovered['coverage'], recovered['tables']), ('birth_luck_unverified', []))
        self.assertEqual(recovered['natal_core'], birth['bazi_core_reading'])

    def test_query_segment_selects_the_current_age_window_at_and_after_native_endpoints(self):
        birth = self._cli_snapshot('16:59')
        for day, layer, earlier_age, next_age, earlier_luck, next_luck, next_direction in (
                ('2014-12-24', 'day', 407, 408, '辛卯', '壬辰', 'ordinary_positive_not_established'),
                ('2064-12-24', 'month', 1007, 1008, '丙申', None, 'withheld')):
            with self.subTest(day=day):
                def read(start, end, age):
                    segment, = period_facts.period_facts(
                        datetime.fromisoformat(f'{day}T{start}+08:00'),
                        datetime.fromisoformat(f'{day}T{end}+08:00'), layer)['segments']
                    result = qiong.evaluate_query_segment(birth, segment, age)
                    self.assertEqual(result['folded_age_months'], age)
                    self.assertEqual(result['window'], f"[{segment['start']}, {segment['end']})")
                    reading, = result['readings']
                    return reading

                earlier = read('16:30', '17:00', earlier_age)
                later = read('17:00', '18:00', next_age)
                self.assertEqual(earlier['age_window']['end_months_exclusive'], next_age)
                self.assertEqual(earlier['panels']['luck']['temporal_facts'][0]['pillar'], earlier_luck)
                self.assertEqual(later['panels']['luck']['temporal_facts'][0]['pillar'], next_luck)
                self.assertEqual(earlier['panels'][layer]['conditional_model_direction'],
                                 'development_configuration_relatively_favorable')
                self.assertEqual(later['panels'][layer]['conditional_model_direction'], next_direction)
                if next_luck is None:
                    self.assertEqual(later['luck_status'], 'outside_luck_windows')
                    self.assertIsNone(later['age_window'])
                    self.assertEqual(later['age_table_range'], {'start_months_inclusive': 0,
                                                                'end_months_exclusive': next_age})
                else:
                    self.assertEqual(later['age_window']['start_months_inclusive'], next_age)

    def test_query_segment_binds_clock_band_reading_to_independent_window_and_layer(self):
        birth = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8,
                                             clock_band=('16:58', '17:02'))
        witness = scenarios.birth_luck_tables(birth)['tables'][0]['witness']

        def facts(start, end, layer):
            segment, = period_facts.period_facts(datetime.fromisoformat(start),
                                                datetime.fromisoformat(end), layer)['segments']
            return segment

        late_start, late_end = '2006-11-10T23:15+08:00', '2006-11-10T23:45+08:00'
        earlier_start, earlier_end = '2006-11-10T22:15+08:00', '2006-11-10T22:45+08:00'
        late_window = f'[{late_start}, {late_end})'
        earlier_window = f'[{earlier_start}, {earlier_end})'
        correct = facts(late_start, late_end, 'day')
        earlier = facts(earlier_start, earlier_end, 'day')
        same_utc = facts('2006-11-10T15:15+00:00', '2006-11-10T15:45+00:00', 'day')
        self.assertEqual([segment['facts'][-1]['pillar'] for segment in (correct, earlier, same_utc)],
                         ['甲辰', '癸卯', '癸卯'])
        later_reading, = qiong.evaluate_query_segment(
            birth, correct, 310, expected_window=late_window, expected_layer='day',
            expected_birth_witness=witness)['readings']
        self.assertEqual(later_reading['witness'], witness)
        self.assertEqual(later_reading['panels']['day']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')
        earlier_reading, = qiong.evaluate_query_segment(
            birth, earlier, 310, expected_window=earlier_window, expected_layer='day',
            expected_birth_witness=witness)['readings']
        self.assertEqual(earlier_reading['panels']['day']['conditional_model_direction'],
                         'development_support_restricted')
        for stale, reason in ((earlier, '查询起止不一致'), (same_utc, '固定民用偏移')):
            with self.assertRaisesRegex(ValueError, reason):
                qiong.evaluate_query_segment(birth, stale, 310, expected_window=late_window, expected_layer='day',
                                             expected_birth_witness=witness)

        with self.assertRaisesRegex(ValueError, '查询层不一致'):
            qiong.evaluate_query_segment(birth, facts(earlier_start, earlier_end, 'month'), 310,
                                         expected_window=earlier_window, expected_layer='day',
                                         expected_birth_witness=witness)
        utc_month = facts('2006-11-10T14:15+00:00', '2006-11-10T14:45+00:00', 'month')
        month = qiong.evaluate_query_segment(birth, utc_month, 310, expected_window=earlier_window,
                                             expected_layer='month', expected_birth_witness=witness)
        self.assertEqual(month['window'], earlier_window)
        self.assertEqual(month['readings'][0]['panels']['month']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')

    def test_query_range_detects_missing_restricted_day_window(self):
        birth = self._cli_snapshot('17:02')
        day = date(2006, 11, 10)
        plan = period_facts.regional_date_facts(day, day + timedelta(days=1), 'day', 'Asia/Shanghai')
        before, after = plan['segments']
        earlier = qiong.evaluate_query_segment(birth, before, 310)
        later = qiong.evaluate_query_segment(birth, after, 310)
        self.assertEqual(earlier['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_support_restricted')
        self.assertEqual(later['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')
        audit = qiong.audit_query_range
        self.assertEqual(audit(plan, [later])['unread_windows'], [earlier['window']])
        self.assertEqual(audit(plan, [later, earlier])['unread_windows'], [])
        self.assertEqual(audit(dict(plan, segments=[after]), [later], snapshot=birth)['unread_windows'],
                         [earlier['window']])
        self.assertEqual(audit(plan, [later, dict(earlier, readings=[])])['unread_windows'], [earlier['window']])
        relabeled = dict(later, window=earlier['window'])
        with self.assertRaisesRegex(ValueError, '干支与原查询分段不一致'):
            audit(plan, [later, relabeled])
        detached = copy.deepcopy(earlier)
        detached['readings'][0]['panels']['day']['temporal_facts'][-1]['window'] = later['window']
        with self.assertRaisesRegex(ValueError, '历法事实窗口不覆盖'):
            audit(plan, [later, detached])


        start, end = [datetime.fromisoformat(before[key]) for key in ('start', 'end')]
        split = start + timedelta(hours=7)
        pieces = [period_facts.period_facts(left, right, 'day')['segments'][0]
                  for left, right in ((start, split), (split, end))]
        parts = [qiong.evaluate_query_segment(birth, piece, 310) for piece in pieces]
        self.assertEqual(audit(plan, [later, *parts])['unread_windows'], [])
        self.assertEqual(audit(plan, [later, parts[1]])['unread_windows'], [parts[0]['window']])
        with self.assertRaisesRegex(ValueError, '原查询的单个历法分段'):
            audit(plan, [dict(earlier, window=f"[{before['start']}, {after['end']})")])

        wrong_layer, = period_facts.period_facts(start, end, 'month')['segments']
        month_result = qiong.evaluate_query_segment(birth, wrong_layer, 310)
        with self.assertRaisesRegex(ValueError, '模型层与原查询层不一致'):
            audit(plan, [month_result])
        wrong_clock, = period_facts.period_facts(split.astimezone(timezone.utc), end.astimezone(timezone.utc),
                                                  'day')['segments']
        utc_result = qiong.evaluate_query_segment(birth, wrong_clock, 310)
        with self.assertRaisesRegex(ValueError, '原查询的固定民用偏移'):
            audit(plan, [utc_result])

    def test_temporal_query_cannot_admit_an_interval_before_or_straddling_birth(self):
        birth = self._cli_snapshot('17:02')
        known_day = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8)
        band = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8,
                                             clock_band=('16:58', '17:03'))

        def read(snapshot, start, end, layer, age):
            left, right = (datetime.fromisoformat(value + '+08:00') for value in (start, end))
            segment, = period_facts.period_facts(left, right, layer)['segments']
            return qiong.evaluate_query_segment(snapshot, segment, age)

        with self.assertRaisesRegex(ValueError, '早于原出生'):
            read(birth, '1946-11-11T10:00', '1946-11-12T10:00', 'month', 310)
        after = read(birth, '2006-11-11T10:00', '2006-11-12T10:00', 'month', 310)
        self.assertEqual(after['readings'][0]['panels']['month']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')

        with self.assertRaisesRegex(ValueError, '早于原出生'):
            read(known_day, '1980-12-23T10:00', '1980-12-23T12:00', 'day', None)
        for snapshot, within, later in ((birth, '17:01', '17:02'), (band, '17:02', '17:03')):
            with self.subTest(within=within):
                with self.assertRaisesRegex(ValueError, '与原出生范围相交'):
                    read(snapshot, '1980-12-24T' + within, '1980-12-24T17:04', 'day', None)
                self.assertTrue(read(snapshot, '1980-12-24T' + later, '1980-12-24T17:04', 'day', None)['readings'])

    def test_query_range_replays_same_birth_and_rejects_adjacent_hour_cache(self):
        birth = self._cli_snapshot('16:59')
        adjacent = self._cli_snapshot('17:02')
        start, split, end = (datetime.fromisoformat(f'2005-05-15T{hour}:00+08:00')
                             for hour in ('09:00', '13:00', '17:00'))
        plan = period_facts.period_facts(start, end, 'day')
        before, = period_facts.period_facts(start, split, 'day')['segments']
        after, = period_facts.period_facts(split, end, 'day')['segments']
        earlier = qiong.evaluate_query_segment(birth, before, 292)
        same = qiong.evaluate_query_segment(birth, after, 292)
        stale = qiong.evaluate_query_segment(adjacent, after, 292)
        unknown = qiong.evaluate_query_segment(birth, after, None)
        self.assertEqual(earlier['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')
        self.assertEqual(stale['readings'][0]['panels']['day']['conditional_model_direction'],
                         'ordinary_positive_not_established')
        for result in (same, unknown):
            self.assertEqual(qiong.audit_query_range(plan, [earlier, result], snapshot=birth)['unread_windows'], [])
        self.assertEqual(qiong.audit_query_range(plan, [earlier, stale])['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '与本次原出生快照'):
            qiong.audit_query_range(plan, [earlier, stale], snapshot=birth)
        with self.assertRaisesRegex(ValueError, '该见证的大运事实不一致'):
            qiong.audit_query_range(plan, [earlier, dict(same, folded_age_months=None)], snapshot=birth)

    def test_query_range_binds_exact_birth_minute_when_pillars_and_luck_table_match(self):
        original = self._cli_snapshot('16:59')
        corrected = self._cli_snapshot('16:57')
        self.assertEqual(original['bazi']['pillars'], corrected['bazi']['pillars'])
        self.assertEqual(original['bazi']['dayun_age_windows'], corrected['bazi']['dayun_age_windows'])
        request = dict(start='2014-12-24T16:58', end='2014-12-24T16:59',
                       layer='month', timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        segment, = plan['segments']
        old = qiong.evaluate_query_segment(original, segment, 407)
        new = qiong.evaluate_query_segment(corrected, segment, 408)
        self.assertEqual(old['birth_instant_utc'], '1980-12-24T08:59:00+00:00')
        self.assertEqual(new['birth_instant_utc'], '1980-12-24T08:57:00+00:00')
        for result, expected in ((old, 'development_configuration_relatively_favorable'),
                                 (new, 'ordinary_positive_not_established')):
            self.assertEqual(result['readings'][0]['panels']['month']['conditional_model_direction'], expected)

        window = tuple(datetime.fromisoformat(segment[key]) for key in ('start', 'end'))
        old_ages = {(*window, None, None): 407}
        new_ages = {(*window, None, None): 408}
        for ages in (None, old_ages, new_ages):
            with self.subTest(ages=ages), self.assertRaisesRegex(ValueError, '精确出生时刻不一致'):
                qiong.audit_query_range(plan, [old], snapshot=corrected, expected_request=request,
                                        verified_folded_ages=ages)
        self.assertEqual(qiong.audit_query_range(plan, [old], snapshot=original,
                                                 verified_folded_ages=old_ages)['unread_windows'], [])
        self.assertEqual(qiong.audit_query_range(plan, [new], snapshot=corrected,
                                                 verified_folded_ages=new_ages)['unread_windows'], [])

        legacy = old.copy()
        del legacy['birth_instant_utc']
        self.assertEqual(qiong.audit_query_range(plan, [legacy])['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '旧面板缺少精确出生时刻'):
            qiong.audit_query_range(plan, [legacy], snapshot=corrected, verified_folded_ages=old_ages)
        unknown_age = qiong.evaluate_query_segment(original, segment, None)
        del unknown_age['birth_instant_utc']
        self.assertEqual(qiong.audit_query_range(plan, [unknown_age],
                                                 snapshot=corrected)['unread_windows'], [])

    def test_fallback_rechecks_birth_even_without_luck_table(self):
        birth = self._cli_snapshot('17:02')
        adjacent = self._cli_snapshot('16:59')
        del birth['bazi']['dayun_age_windows']
        core = birth['bazi_core_reading']

        def read(snapshot, start, end, natal=core):
            left, right = (datetime.fromisoformat(f'1980-12-24T{clock}+08:00')
                           for clock in (start, end))
            plan = period_facts.period_facts(left, right, 'day')
            result = qiong.evaluate_query_segment(snapshot, plan['segments'][0], None,
                                                  verified_natal_cores=[natal])
            audit = qiong.audit_query_range(plan, [result], snapshot=snapshot, verified_natal_cores=[natal])
            self.assertEqual(qiong.audit_query_range(plan, [result]), audit)
            return result, audit

        with self.assertRaisesRegex(ValueError, '早于原出生'):
            read(birth, '16:57', '17:02')
        with self.assertRaisesRegex(ValueError, '与原出生范围相交'):
            read(birth, '17:01', '17:04')
        with self.assertRaisesRegex(ValueError, '四柱与原出生输入'):
            read(birth, '17:02', '17:04', adjacent['bazi_core_reading'])
        different_sex = copy.deepcopy(core)
        different_sex['primary_spouse']['sex'] = '女'
        with self.assertRaisesRegex(ValueError, '八字出生性别与已存核心不一致'):
            read(birth, '17:02', '17:04', different_sex)
        conflict = copy.deepcopy(birth)
        conflict['time']['civil'] = adjacent['time']['civil']
        with self.assertRaisesRegex(ValueError, '保存的民用出生钟面'):
            read(conflict, '17:02', '17:04')

        for snapshot in (birth, {key: value for key, value in birth.items() if key != 'time'}):
            result, audit = read(snapshot, '17:02', '17:04')
            self.assertEqual(result['readings'][0]['luck_status'], 'birth_luck_unverified')
            self.assertEqual(audit['unread_windows'], [])
        result, audit = read({'input': {}, 'bazi': {}}, '17:02', '17:04')
        self.assertEqual(result['birth_time_status'], 'birth_time_unverified')
        self.assertEqual(audit['unread_windows'], [result['window']])

    def test_exact_missing_age_table_recovers_natal_and_calendar_without_caller_core(self):
        birth = self._cli_snapshot('16:59', '--timezone', 'Asia/Shanghai')
        archive = copy.deepcopy(birth)
        del archive['bazi']['dayun_age_windows']
        older = copy.deepcopy(archive)
        del older['bazi_core_reading']
        original_core = birth['bazi_core_reading']
        self.assertEqual(scenarios.birth_luck_tables(archive), scenarios.birth_luck_tables(older))
        context = scenarios.luck_contexts_at_age(older, 1008)
        self.assertEqual(context['contexts'], [])
        self.assertEqual(context['natal_core'], original_core)
        for layer, start_label, end_label, age, gui_node, full_status in (
                ('day', '2064-12-24T23:00', '2064-12-24T23:30', 1008, 'temporal.day.stem', 'outside_luck_windows'),
                ('month', '2026-05-10T14:00', '2026-05-10T14:40', 544, 'temporal.month.stem', 'active')):
            with self.subTest(layer=layer):
                request = dict(start=start_label, end=end_label, layer=layer, timezone='Asia/Shanghai')
                plan = period_facts.query_period_facts(start_label, end_label, layer, request['timezone'])
                segment, = plan['segments']
                self.assertEqual(qiong.evaluate_query_segment(birth, segment, age)['readings'][0]['luck_status'],
                                 full_status)
                panel = qiong.evaluate_query_segment(older, segment, age)
                self.assertEqual(panel, qiong.evaluate_query_segment(archive, segment, age))
                self.assertEqual(panel, qiong.evaluate_query_segment(older, segment, age,
                                                                    verified_natal_cores=[original_core]))
                reading, = panel['readings']
                self.assertEqual(reading['luck_status'], 'birth_luck_unverified')
                self.assertIsNone(reading['age_window'])
                self.assertEqual(reading['panels']['natal']['conditional_model_direction'],
                                 'development_configuration_relatively_favorable')
                self.assertEqual(reading['panels'][layer]['conditional_model_direction'], 'withheld')
                counter = reading['panels'][layer]['specific_gui_countercondition']
                self.assertEqual(counter['status'], 'present')
                self.assertIn(gui_node, counter['fact_ids'])
                audit = qiong.audit_query_range(plan, [panel], snapshot=older, expected_request=request)
                self.assertEqual(audit['unread_windows'], [])

        stale = copy.deepcopy(older)
        pillars = {key: '丁酉' if key == 'hour' else fact['pillar']
                   for key, fact in original_core['facts'].items()}
        stale['bazi']['pillars'] = scenarios.canonical_pillars({'bazi.' + k: v for k, v in pillars.items()})
        with self.assertRaisesRegex(ValueError, '四柱与原出生输入'):
            scenarios.birth_luck_tables(stale)
        stale = copy.deepcopy(archive)
        stale['bazi_core_reading']['facts']['hour']['pillar'] = '丁酉'
        with self.assertRaisesRegex(ValueError, '四柱与原出生输入'):
            scenarios.birth_luck_tables(stale)
        missing_clock = copy.deepcopy(older)
        del missing_clock['input']['time_basis']
        self.assertNotIn('natal_core', scenarios.birth_luck_tables(missing_clock))
        reference = copy.deepcopy(older)
        for marker in (True, 0, 1, 'false', 'true', None):
            with self.subTest(hour_unknown=marker):
                reference['bazi']['hour_unknown'] = marker
                self.assertNotIn('natal_core', scenarios.birth_luck_tables(reference))
        del reference['bazi']['hour_unknown']
        self.assertEqual(scenarios.birth_luck_tables(reference)['natal_core'], original_core)
        prebirth, = period_facts.query_period_facts('1980-12-24T16:30', '1980-12-24T16:59', 'day',
                                                    'Asia/Shanghai')['segments']
        with self.assertRaisesRegex(ValueError, '早于原出生'):
            qiong.evaluate_query_segment(older, prebirth, None)

    def test_exact_archive_with_no_age_rows_keeps_verified_core_when_native_duplicates_are_missing(self):
        birth = self._cli_snapshot('16:59', '--timezone', 'Asia/Shanghai')
        archive = copy.deepcopy(birth)
        del archive['bazi']['dayun_age_windows']
        request = dict(start='2026-05-10T14:00', end='2026-05-10T14:40', layer='month',
                       timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        segment, = plan['segments']
        expected = qiong.evaluate_query_segment(archive, segment, 544)
        reading, = expected['readings']
        self.assertEqual(reading['panels']['natal']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')
        self.assertEqual(reading['panels']['month']['conditional_model_direction'], 'withheld')
        self.assertEqual(reading['panels']['month']['specific_gui_countercondition']['status'], 'present')

        for missing in ('empty_age_object', 'raw_hour', 'all_raw_pillars', 'both_pillar_records',
                        'raw_bazi_block', 'birth_input_only'):
            with self.subTest(missing=missing):
                legacy = copy.deepcopy(archive)
                if missing == 'empty_age_object':
                    legacy['bazi']['dayun_age_windows'] = {}
                elif missing == 'raw_hour':
                    del legacy['bazi']['pillars']['hour']
                elif missing == 'raw_bazi_block':
                    del legacy['bazi']
                elif missing == 'birth_input_only':
                    legacy = {'input': legacy['input']}
                else:
                    del legacy['bazi']['pillars']
                    if missing == 'both_pillar_records':
                        del legacy['bazi_core_reading']
                lifetime = scenarios.birth_luck_tables(legacy)
                self.assertEqual(lifetime['natal_core'], birth['bazi_core_reading'])
                self.assertEqual(lifetime['tables'], [])
                result = qiong.evaluate_query_segment(legacy, segment, 544)
                self.assertEqual(result, expected)
                audit = qiong.audit_query_range(plan, [result], snapshot=legacy, expected_request=request)
                self.assertEqual(audit['unread_windows'], [])

        no_duplicate = copy.deepcopy(archive)
        del no_duplicate['bazi']['pillars']['hour']
        wrong_core = copy.deepcopy(no_duplicate)
        wrong_core['bazi_core_reading']['facts']['hour']['pillar'] = '丁酉'
        no_raw_wrong_core = {key: value for key, value in wrong_core.items() if key != 'bazi'}
        for stored in (wrong_core, no_raw_wrong_core):
            with self.assertRaisesRegex(ValueError, '四柱与原出生输入'):
                scenarios.birth_luck_tables(stored)
        bad_raw = {'input': birth['input'], 'bazi': []}
        with self.assertRaisesRegex(ValueError, '保存的八字原盘须为对象'):
            scenarios.birth_luck_tables(bad_raw)
        wrong_native = copy.deepcopy(no_duplicate)
        wrong_native['bazi']['pillars']['year'][0] = '乙'
        with self.assertRaisesRegex(ValueError, '原四柱与原出生输入'):
            scenarios.birth_luck_tables(wrong_native)
        unknown = copy.deepcopy(no_duplicate)
        unknown['bazi']['hour_unknown'] = True
        self.assertNotIn('natal_core', scenarios.birth_luck_tables(unknown))
        del no_duplicate['bazi_core_reading']
        del no_duplicate['input']['time_basis']
        self.assertNotIn('natal_core', scenarios.birth_luck_tables(no_duplicate))

    def test_exact_saved_luck_survives_missing_natal_duplicates(self):
        birth = self._cli_snapshot('16:59', '--timezone', 'Asia/Shanghai')
        plan = period_facts.query_period_facts('2026-05-10T14:00', '2026-05-10T14:40',
                                              'month', 'Asia/Shanghai')
        segment, = plan['segments']
        expected = qiong.evaluate_query_segment(birth, segment, 544)
        self.assertEqual(expected['readings'][0]['luck_status'], 'active')
        for missing in ('hour', 'pillars'):
            archive = copy.deepcopy(birth)
            del archive['bazi_core_reading']
            if missing == 'hour':
                del archive['bazi']['pillars']['hour']
            else:
                del archive['bazi']['pillars']
            without_marker = copy.deepcopy(archive)
            del without_marker['bazi']['dayun_age_windows']['birth_time_is_reference']
            for marker_missing, saved in ((False, archive), (True, without_marker)):
                with self.subTest(missing=missing, marker_missing=marker_missing):
                    self.assertEqual(scenarios.birth_luck_tables(saved), scenarios.birth_luck_tables(birth))
                    self.assertEqual(qiong.evaluate_query_segment(saved, segment, 544), expected)
                    self.assertEqual(qiong.audit_query_range(plan, [expected], snapshot=saved)['unread_windows'], [])

        partial = copy.deepcopy(birth)
        del partial['bazi_core_reading']
        del partial['bazi']['pillars']['day']
        partial['bazi']['pillars']['hour'][0] = '丁'
        with self.assertRaisesRegex(ValueError, '八字原四柱与原出生输入重排不一致：hour'):
            scenarios.birth_luck_tables(partial)

    def test_exact_luck_rechecks_old_archive_without_derived_birth_clock(self):
        birth = self._cli_snapshot('17:02')
        lifetime = scenarios.birth_luck_tables(birth)
        start = datetime.fromisoformat('2006-11-11T10:00+08:00')
        end = datetime.fromisoformat('2006-11-11T12:00+08:00')
        for layer in ('month', 'day'):
            plan = period_facts.period_facts(start, end, layer)
            segment, = plan['segments']
            expected = qiong.evaluate_query_segment(birth, segment, 310)
            reading, = expected['readings']
            self.assertEqual(reading['panels'][layer]['conditional_model_direction'],
                             'development_configuration_relatively_favorable')
            for key in ('time', 'civil', 'chart_clock'):
                with self.subTest(layer=layer, missing=key):
                    archive = copy.deepcopy(birth)
                    saved = archive if key == 'time' else archive['time']
                    del saved[key]
                    self.assertEqual(scenarios.birth_luck_tables(archive), lifetime)
                    actual = qiong.evaluate_query_segment(archive, segment, 310)
                    self.assertEqual(actual, expected)
                    self.assertEqual(qiong.audit_query_range(plan, [actual], snapshot=archive)['unread_windows'], [])

        archive = copy.deepcopy(birth)
        del archive['time']['civil']
        archive['time']['chart_clock'] = '1980-12-24T16:59:00'
        with self.assertRaisesRegex(ValueError, '所选口径的出生钟面与原出生瞬间不一致'):
            scenarios.birth_luck_tables(archive)
        del archive['time']
        archive['bazi']['dayun_age_windows']['windows'][0]['end_months_exclusive'] += 1
        with self.assertRaisesRegex(ValueError, '大运表与出生见证的原生折月不一致'):
            scenarios.birth_luck_tables(archive)

    def test_exact_old_archive_rechecks_selected_solar_clock_even_without_chart_clock(self):
        plan = period_facts.query_period_facts('2005-05-15T09:00+08:00', '2005-05-15T17:00+08:00', 'day')
        segment, = plan['segments']
        for basis, selected, unselected in (
                ('mean-solar', 'mean_solar', 'apparent_solar'),
                ('apparent-solar', 'apparent_solar', 'mean_solar')):
            with self.subTest(basis=basis):
                birth = self._cli_snapshot('16:59', '--time-basis', basis)
                next_minute = self._cli_snapshot('17:00', '--time-basis', basis)
                baseline = qiong.evaluate_query_segment(birth, segment, 292)
                saved = copy.deepcopy(birth)
                saved['time'][unselected] = next_minute['time'][unselected]
                self.assertEqual(qiong.evaluate_query_segment(saved, segment, 292), baseline)
                saved['time'][selected] = next_minute['time'][selected]
                error = r'所选口径的出生钟面与原出生瞬间不一致：time\.' + selected
                with self.assertRaisesRegex(ValueError, error):
                    scenarios.birth_luck_tables(saved)
                del saved['time']['chart_clock']
                with self.assertRaisesRegex(ValueError, error):
                    qiong.evaluate_query_segment(saved, segment, 292)
                del saved['bazi']['dayun_age_windows']
                with self.assertRaisesRegex(ValueError, error):
                    qiong.evaluate_query_segment(saved, segment, 292,
                                                 verified_natal_cores=(birth['bazi_core_reading'],))
                saved['time'][selected] = birth['time'][selected]
                replayed = qiong.evaluate_query_segment(saved, segment, 292,
                                                       verified_natal_cores=(birth['bazi_core_reading'],))
                self.assertEqual(replayed['readings'][0]['luck_status'], 'birth_luck_unverified')
                self.assertNotIn('birth_time_status', replayed)

    def test_exact_old_archive_rejects_changed_fold_even_if_pillars_and_ages_match(self):
        first, second = (self._cli_snapshot('01:30', '--timezone', 'America/New_York', '--fold', fold,
                                            birthday='1990-10-28') for fold in ('0', '1'))
        self.assertEqual(first['bazi_core_reading']['facts'], second['bazi_core_reading']['facts'])
        self.assertEqual(first['bazi']['dayun_age_windows'], second['bazi']['dayun_age_windows'])
        self.assertNotEqual(first['bazi']['birth_dt'], second['bazi']['birth_dt'])
        lifetime = scenarios.birth_luck_tables(first)
        del first['time']
        self.assertEqual(scenarios.birth_luck_tables(first), lifetime)
        start = datetime.fromisoformat('1990-10-28T01:00-05:00')
        end = datetime.fromisoformat('1990-10-28T01:15-05:00')
        plan = period_facts.period_facts(start, end, 'day')
        segment, = plan['segments']
        with self.assertRaisesRegex(ValueError, '早于原出生'):
            qiong.evaluate_query_segment(second, segment, None)
        early = qiong.evaluate_query_segment(first, segment, None)
        self.assertEqual(qiong.audit_query_range(plan, [early], snapshot=first)['unread_windows'], [])

        del second['time']
        second['input']['fold'] = 0
        conflict = '保存的八字出生瞬间与原民用出生输入不一致'
        with self.assertRaisesRegex(ValueError, conflict):
            scenarios.birth_luck_tables(second)
        for archive in (first, second):
            del archive['bazi']['dayun_age_windows']
        first_cores = [first['bazi_core_reading']]
        read = qiong.evaluate_query_segment(first, segment, None, verified_natal_cores=first_cores)
        self.assertEqual(qiong.audit_query_range(plan, [read], snapshot=first,
                                                 verified_natal_cores=first_cores)['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, conflict):
            qiong.evaluate_query_segment(second, segment, None, verified_natal_cores=[second['bazi_core_reading']])

    def test_fallback_checks_whole_unenumerated_birth_range(self):
        birth = self._cli_snapshot('17:02', '--uncertainty-minutes', '125')

        def read(start, end, core=None, snapshot=birth):
            left, right = (datetime.fromisoformat(f'1980-12-24T{clock}+08:00')
                           for clock in (start, end))
            plan = period_facts.period_facts(left, right, 'day')
            cores = [core or snapshot['bazi_core_reading']]
            result = qiong.evaluate_query_segment(snapshot, plan['segments'][0], None, verified_natal_cores=cores)
            return result, qiong.audit_query_range(plan, [result], snapshot=snapshot, verified_natal_cores=cores)

        with self.assertRaisesRegex(ValueError, '与原出生范围相交'):
            read('19:06', '19:08')
        result, audit = read('19:07', '19:08')
        self.assertEqual(result['readings'][0]['luck_status'], 'birth_luck_unverified')
        self.assertEqual(audit['unread_windows'], [])
        exact = self._cli_snapshot('17:02')['bazi_core_reading']
        with self.assertRaisesRegex(ValueError, '出生时间场景'):
            read('19:07', '19:08', exact)

        foreign = self._cli_snapshot('17:02', '--uncertainty-minutes', '5', '--enumerate-scenarios',
                                     birthday='1981-01-24')['bazi_scenario_comparison']['candidates'][0]['analysis']
        unknown_basis = copy.deepcopy(birth)
        del unknown_basis['input']['time_basis']
        for snapshot, core in ((birth, foreign), (unknown_basis, None)):
            result, audit = read('19:07', '19:08', core, snapshot)
            self.assertEqual(result['birth_time_status'], 'birth_core_unverified')
            self.assertEqual(audit['unread_windows'], [result['window']])

    def test_query_range_reports_missing_half_day_for_each_birth_witness(self):
        birth = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8,
                                             clock_band=('16:58', '17:02'))
        first, second = [row['witness'] for row in scenarios.birth_luck_tables(birth)['tables']]
        start, split, end = [datetime.fromisoformat(f'2005-05-15T{hour}:00+08:00')
                             for hour in ('09:00', '13:00', '17:00')]
        plan = period_facts.period_facts(start, end, 'day')
        before, = period_facts.period_facts(start, split, 'day')['segments']
        after, = period_facts.period_facts(split, end, 'day')['segments']
        a_before = qiong.evaluate_query_segment(birth, before, 292, expected_birth_witness=first)
        b_after = qiong.evaluate_query_segment(birth, after, 292, expected_birth_witness=second)
        mixed = qiong.audit_query_range(plan, [a_before, b_after], snapshot=birth)
        self.assertEqual(mixed['unread_windows'], [])
        self.assertEqual(mixed['unread_by_birth'], [
            dict(first, unread_windows=[b_after['window']]),
            dict(second, unread_windows=[a_before['window']]),
        ])
        a_after = qiong.evaluate_query_segment(birth, after, 292, expected_birth_witness=first)
        b_before = qiong.evaluate_query_segment(birth, before, 292, expected_birth_witness=second)

        def direction(row):
            return row['readings'][0]['panels']['day']['conditional_model_direction']

        self.assertNotEqual(direction(a_before), direction(b_after))
        self.assertEqual(direction(a_before), direction(a_after))
        self.assertEqual(direction(b_before), direction(b_after))
        complete = qiong.audit_query_range(plan, [a_before, b_after, a_after, b_before], snapshot=birth)
        self.assertEqual(complete['unread_by_birth'], [dict(first, unread_windows=[]), dict(second, unread_windows=[])])
        empty = qiong.audit_query_range(plan, [], snapshot=birth)
        self.assertEqual(empty['unread_by_birth'], [dict(w, unread_windows=empty['unread_windows'])
                                                   for w in (first, second)])

    def test_followup_range_audit_counts_only_independently_selected_birth_witness(self):
        birth = scenarios.analyze_birth_date(date(1987, 1, 2), '男', zone='Asia/Shanghai',
                                             clock_band=('10:58', '11:02'))
        early, late = [row['witness'] for row in scenarios.birth_luck_tables(birth)['tables']]
        start, end = [datetime.fromisoformat(f'2026-12-06T{time}:00+08:00') for time in ('14:00', '14:40')]
        age = 479
        selected_age = {(start, end, late['scenario_id'], late['witness_utc']): age}
        for layer in ('month', 'day'):
            with self.subTest(layer=layer):
                plan = period_facts.period_facts(start, end, layer)
                segment, = plan['segments']
                early_read, late_read, combined = [
                    qiong.evaluate_query_segment(birth, segment, age, expected_birth_witness=witness)
                    for witness in (early, late, None)]
                directions = [row['panels'][layer]['conditional_model_direction'] for row in combined['readings']]
                self.assertEqual(directions, ['development_support_restricted',
                                              'development_configuration_relatively_favorable'])
                options = dict(snapshot=birth, expected_birth_witness=late, verified_folded_ages=selected_age)
                missing = qiong.audit_query_range(plan, [early_read], **options)
                self.assertEqual(missing['unread_windows'], [late_read['window']])
                self.assertEqual(missing['unread_by_birth'], [dict(late, unread_windows=missing['unread_windows'])])
                for evaluations in ([late_read], [combined], [early_read, late_read]):
                    report = qiong.audit_query_range(plan, evaluations, **options)
                    self.assertEqual(report['unread_windows'], [])
                    self.assertEqual(report['unread_by_birth'], [dict(late, unread_windows=[])])

                with self.assertRaisesRegex(ValueError, '年龄不一致'):
                    qiong.audit_query_range(plan, [combined], snapshot=birth, expected_birth_witness=late,
                                            verified_folded_ages={key: age - 1 for key in selected_age})
                with self.assertRaisesRegex(ValueError, '指定出生见证不存在'):
                    qiong.audit_query_range(plan, [], snapshot=birth,
                                            expected_birth_witness=dict(late, witness_utc=early['witness_utc']))
                with self.assertRaisesRegex(ValueError, '须同时指定'):
                    qiong.audit_query_range(plan, [], snapshot=birth,
                                            expected_birth_witness={'scenario_id': late['scenario_id']})
                with self.assertRaisesRegex(ValueError, '须提供原出生快照'):
                    qiong.audit_query_range(plan, [], expected_birth_witness=late)

    def test_range_audit_binds_the_plan_to_the_independent_request(self):
        birth = self._cli_snapshot('17:02')
        request = dict(start='2006-06-01T00:00+08:00', end='2006-06-15T00:00+08:00', layer='month')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'])
        earlier, later = plan['segments']
        reads = [qiong.evaluate_query_segment(birth, segment, 305) for segment in (earlier, later)]
        self.assertEqual([row['readings'][0]['panels']['month']['conditional_model_direction'] for row in reads], [
            'development_support_restricted', 'development_configuration_relatively_favorable',
        ])
        shortened = period_facts.query_period_facts(later['start'], request['end'], 'month')
        audit = qiong.audit_query_range
        self.assertEqual(audit(shortened, reads[1:], snapshot=birth)['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '原查询请求不一致'):
            audit(shortened, reads[1:], snapshot=birth, expected_request=request)
        self.assertEqual(audit(dict(plan, segments=[later]), reads[1:], snapshot=birth,
                               expected_request=request)['unread_windows'], [reads[0]['window']])
        self.assertEqual(audit(plan, reads, snapshot=birth, expected_request=request)['unread_windows'], [])

        old = dict(plan, segments=[later])
        del old['time_basis']
        for expected in (None, request):
            self.assertEqual(audit(old, reads[1:], snapshot=birth, expected_request=expected)['unread_windows'],
                             [reads[0]['window']])
        legacy = dict(layer=plan['layer'], segments=[later])
        self.assertEqual(audit(legacy, reads[1:], snapshot=birth)['unread_windows'], [])

        repeated = dict(start='2006-10-29T01:15', end='2006-10-29T02:15',
                        layer='day', timezone='America/New_York', start_fold=0)
        first_fold, second_fold = [
            period_facts.query_period_facts(repeated['start'], repeated['end'], repeated['layer'],
                                           repeated['timezone'], start_fold=fold)
            for fold in (0, 1)
        ]
        self.assertEqual(audit(first_fold, [], expected_request=repeated)['planned_segments'], 2)
        with self.assertRaisesRegex(ValueError, '原查询请求不一致'):
            audit(second_fold, [], expected_request=repeated)
        with self.assertRaisesRegex(ValueError, '无法按原查询请求重建.*fold'):
            audit(first_fold, [], expected_request=dict(repeated, start_fold=None))
        del first_fold['time_basis']
        del second_fold['time_basis']
        self.assertEqual(audit(first_fold, [], expected_request=repeated)['planned_segments'], 2)
        with self.assertRaisesRegex(ValueError, '原查询请求不一致'):
            audit(second_fold, [], expected_request=repeated)

    def test_query_range_rebuilds_known_iana_window_when_archived_basis_is_missing(self):
        birth = self._cli_snapshot('17:02')
        request = dict(start='2006-11-10T22:30', end='2006-11-10T23:30', layer='day', timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        earlier, later = plan['segments']
        reads = [qiong.evaluate_query_segment(birth, segment, 310) for segment in (earlier, later)]
        self.assertEqual([row['readings'][0]['panels']['day']['conditional_model_direction'] for row in reads], [
            'development_support_restricted', 'development_configuration_relatively_favorable',
        ])
        old = dict(plan, segments=[earlier])
        del old['time_basis']
        for expected in (None, request):
            report = qiong.audit_query_range(old, reads[:1], snapshot=birth, expected_request=expected)
            self.assertEqual(report['planned_segments'], 2)
            self.assertEqual(report['unread_windows'], [reads[1]['window']])
            complete = qiong.audit_query_range(old, reads, snapshot=birth, expected_request=expected)
            self.assertEqual(complete['unread_windows'], [])

        conflicts = [
            (dict(old, time_basis=None), '民用时间口径无法复核'),
            (dict(old, timezone=None), '保存的时区来源'),
            (dict(old, timezone_source=dict(old['timezone_source'], zone='Asia/Tokyo')), '保存的时区来源'),
            (dict(old, timezone=''), '民用时区无法复核'),
            (dict(old, end=None), '缺少可复核的起止'),
        ]
        for snapshot, error in conflicts:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                qiong.audit_query_range(snapshot, reads[:1], snapshot=birth)
        with self.assertRaisesRegex(ValueError, '原查询请求不一致'):
            qiong.audit_query_range(dict(old, time_basis='civil_fixed_offset'), reads[:1],
                                    snapshot=birth, expected_request=request)

    def test_same_date_iana_clock_plan_checks_saved_zone_before_counting_a_day_flip(self):
        birth = self._cli_snapshot('06:35', '--timezone', 'Asia/Shanghai', birthday='1982-12-14')
        request = dict(start='2027-03-05T22:50', end='2027-03-05T23:50',
                       layer='day', timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        reads = [qiong.evaluate_query_segment(birth, segment, 530) for segment in plan['segments']]
        self.assertEqual([row['readings'][0]['panels']['day']['conditional_model_direction'] for row in reads], [
            'development_support_restricted', 'development_configuration_relatively_favorable',
        ])
        conflicting = dict(plan, timezone_source=dict(plan['timezone_source'], zone='Asia/Tokyo'))
        older = dict(plan)
        del older['timezone_source']
        for expected in (None, request):
            with self.subTest(expected=expected):
                audit = qiong.audit_query_range
                for usable in (plan, older):
                    self.assertEqual(audit(usable, reads, snapshot=birth, expected_request=expected)['unread_windows'], [])
                with self.assertRaisesRegex(ValueError, '保存的时区来源'):
                    audit(conflicting, reads, snapshot=birth, expected_request=expected)

    def test_fixed_offset_archive_rejects_conflicting_regional_timezone_metadata(self):
        birth = self._cli_snapshot('17:02')
        request = dict(start='2006-11-10T22:30:00+08:00', end='2006-11-10T23:30:00+08:00',
                       layer='day', timezone=None)
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'])
        reads = [qiong.evaluate_query_segment(birth, segment, 310) for segment in plan['segments']]
        self.assertEqual([read['readings'][0]['panels']['day']['conditional_model_direction'] for read in reads],
                         ['development_support_restricted', 'development_configuration_relatively_favorable'])
        fixed_source = dict(kind='fixed_offset', tzif_sha256=None)
        regional_source = period_facts.query_period_facts(
            request['start'], request['end'], request['layer'], 'Asia/Shanghai')['timezone_source']
        for expected in (None, request):
            with self.subTest(expected=expected):
                audit = qiong.audit_query_range
                for usable in (plan, dict(plan, timezone_source=fixed_source)):
                    self.assertEqual(audit(usable, reads, snapshot=birth, expected_request=expected)['unread_windows'], [])
                for conflict in (dict(plan, timezone='Asia/Shanghai'), dict(plan, timezone_source=regional_source),
                                 dict(plan, timezone_source=None)):
                    with self.assertRaisesRegex(ValueError, '时区|原查询请求不一致'):
                        audit(conflict, reads, snapshot=birth, expected_request=expected)

    def test_independent_ages_cannot_disagree_on_overlapping_windows(self):
        birth = self._cli_snapshot('16:59')
        start, middle, overlap_end, end = (
            datetime.fromisoformat(f'2005-05-15T{clock}:00+08:00') for clock in ('09:00', '13:00', '14:00', '17:00'))
        plan = period_facts.period_facts(start, end, 'day')

        def evaluate(left, right, age):
            segment, = period_facts.period_facts(left, right, 'day')['segments']
            return qiong.evaluate_query_segment(birth, segment, age)

        second = evaluate(middle, end, 532)
        self.assertEqual(second['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_support_restricted')
        for age in (292, None):
            with self.subTest(age=age):
                earlier = evaluate(start, overlap_end, age)
                verified = {(start, overlap_end, None, None): age, (middle, end, None, None): 532}
                with self.assertRaisesRegex(ValueError, '重叠实际窗口有冲突'):
                    qiong.audit_query_range(plan, [earlier, second], snapshot=birth, verified_folded_ages=verified)
                with self.assertRaisesRegex(ValueError, '重叠实际窗口有冲突的已读面板折月年龄'):
                    qiong.audit_query_range(plan, [earlier, second], snapshot=birth)
        for first_end, age in ((middle, 531), (overlap_end, 532)):
            earlier = evaluate(start, first_end, age)
            verified = {(start, first_end, None, None): age, (middle, end, None, None): 532}
            result = qiong.audit_query_range(plan, [earlier, second], snapshot=birth, verified_folded_ages=verified)
            self.assertEqual(result['unread_windows'], [])
            self.assertEqual(qiong.audit_query_range(plan, [second, earlier], snapshot=birth)['unread_windows'], [])

    def test_one_calendar_window_must_be_split_at_an_independent_luck_cut(self):
        birth = self._cli_snapshot('11:01', '--timezone', 'Asia/Shanghai', birthday='1987-01-02')
        start, cut, end = (datetime.fromisoformat(f'2008-04-02T{clock}+08:00')
                           for clock in ('10:54', '11:01', '11:25'))
        ages = {(start, cut, None, None): 254, (cut, end, None, None): 255}
        for layer in ('day', 'month'):
            with self.subTest(layer=layer):
                plan = period_facts.period_facts(start, end, layer)
                segment, = plan['segments']
                whole = qiong.evaluate_query_segment(birth, segment, 254)
                unbound = qiong.audit_query_range(plan, [whole], snapshot=birth)
                self.assertEqual(unbound['unread_windows'], [])
                self.assertFalse(unbound['folded_age_evidence_checked'])
                self.assertFalse(qiong.audit_query_range(
                    plan, [], snapshot=birth, verified_folded_ages=ages)['folded_age_evidence_checked'])
                with self.assertRaisesRegex(ValueError, r'跨折月年龄切点.*2008-04-02T11:01:00\+08:00'):
                    qiong.audit_query_range(plan, [whole], snapshot=birth, verified_folded_ages=ages)
                if layer == 'month':
                    utc_segment, = period_facts.period_facts(
                        start.astimezone(timezone.utc), end.astimezone(timezone.utc), layer)['segments']
                    utc_read = qiong.evaluate_query_segment(birth, utc_segment, 254)
                    with self.assertRaisesRegex(ValueError, r'跨折月年龄切点.*2008-04-02T11:01:00\+08:00'):
                        qiong.audit_query_range(plan, [utc_read], snapshot=birth, verified_folded_ages=ages)

                split = [qiong.evaluate_query_segment(birth, dict(segment, start=left.isoformat(),
                         end=right.isoformat()), age) for (left, right, _, _), age in ages.items()]
                directions = [row['readings'][0]['panels'][layer]['conditional_model_direction'] for row in split]
                self.assertEqual(directions, ['ordinary_positive_not_established', 'development_support_restricted'])
                result = qiong.audit_query_range(plan, split, snapshot=birth, verified_folded_ages=ages)
                self.assertEqual(result['unread_windows'], [])
                self.assertTrue(result['folded_age_evidence_checked'])

    def test_independent_ages_cannot_go_backwards_across_actual_windows(self):
        birth = self._cli_snapshot('16:59')
        start, first_cut, second_cut, end = (
            datetime.fromisoformat(f'2014-12-24T{clock}:00+08:00')
            for clock in ('16:30', '17:00', '17:30', '18:00'))
        plan = period_facts.period_facts(start, end, 'day')

        def read_and_verify(windows, ages):
            readings, verified = [], {}
            for (left, right), age in zip(windows, ages):
                segment, = period_facts.period_facts(left, right, 'day')['segments']
                readings.append(qiong.evaluate_query_segment(birth, segment, age))
                verified[(left.astimezone(timezone.utc), right.astimezone(timezone.utc), None, None)] = age
            return readings, dict(reversed(tuple(verified.items())))

        def audit(readings, verified):
            return qiong.audit_query_range(plan, readings, snapshot=birth, verified_folded_ages=verified)

        for windows, ages in (
                ([(start, first_cut), (first_cut, end)], [408, 407]),
                ([(start, first_cut), (first_cut, second_cut), (second_cut, end)], [408, None, 407])):
            with self.subTest(ages=ages):
                readings, verified = read_and_verify(windows, ages)
                directions = [row['readings'][0]['panels']['day']['conditional_model_direction']
                              for row in readings]
                self.assertEqual(directions[0], 'ordinary_positive_not_established')
                self.assertEqual(directions[-1], 'development_configuration_relatively_favorable')
                with self.assertRaisesRegex(ValueError, '独立折月年龄随实际时间倒退'):
                    audit(readings, verified)
                with self.assertRaisesRegex(ValueError, '已读面板折月年龄随实际时间倒退'):
                    audit(readings, None)
                increasing, increasing_verified = read_and_verify(windows, list(reversed(ages)))
                self.assertEqual(audit(increasing, increasing_verified)['unread_windows'], [])

    def test_nearby_known_ages_cannot_skip_folded_months(self):
        birth = self._cli_snapshot('16:59')
        start, cut, late_zi, end = (datetime.fromisoformat(clock) for clock in (
            '2014-12-24T16:30:00+08:00', '2014-12-24T16:59:00+08:00',
            '2014-12-24T23:00:00+08:00', '2014-12-25T00:30:00+08:00'))

        def read(left, right, layer, age):
            segment, = period_facts.period_facts(left, right, layer)['segments']
            return qiong.evaluate_query_segment(birth, segment, age)

        for layer, windows in (('day', [(start, cut), (cut, late_zi), (late_zi, end)]),
                               ('month', [(start, cut), (cut, end)])):
            plan = period_facts.period_facts(start, end, layer)
            for next_age, expected_direction in (
                    (408, 'ordinary_positive_not_established'), (528, 'development_support_restricted')):
                with self.subTest(layer=layer, next_age=next_age):
                    ages = [407, *([next_age] * (len(windows) - 1))]
                    readings = [read(left, right, layer, age) for (left, right), age in zip(windows, ages)]
                    self.assertEqual(readings[0]['readings'][0]['panels'][layer]['conditional_model_direction'],
                                     'development_configuration_relatively_favorable')
                    self.assertEqual(readings[1]['readings'][0]['panels'][layer]['conditional_model_direction'],
                                     expected_direction)
                    verified = {(left, right, None, None): age for (left, right), age in zip(windows, ages)}
                    first_key = (start.astimezone(timezone.utc), cut.astimezone(timezone.utc), None, None)
                    verified[first_key] = verified.pop((start, cut, None, None))
                    for independent in (None, verified):
                        if next_age == 408:
                            self.assertEqual(qiong.audit_query_range(
                                plan, readings, snapshot=birth, verified_folded_ages=independent)['unread_windows'], [])
                        else:
                            with self.assertRaisesRegex(ValueError, '相邻实际窗口之间.*一次跳过超过一个月'):
                                qiong.audit_query_range(plan, readings, snapshot=birth, verified_folded_ages=independent)

        day_plan = period_facts.period_facts(start, end, 'day')
        unknown_bridge = [read(start, cut, 'day', 407), read(cut, late_zi, 'day', None),
                          read(late_zi, end, 'day', 408)]
        self.assertEqual(qiong.audit_query_range(day_plan, unknown_bridge, snapshot=birth)['unread_windows'], [])
        self.assertEqual(qiong.audit_query_range(
            day_plan, [unknown_bridge[0], unknown_bridge[-1]], snapshot=birth)['unread_windows'],
            [unknown_bridge[1]['window']])
        stale = read(late_zi, end, 'day', 528)
        for bridge in ([], [unknown_bridge[1]]):
            verified = {(start, cut, None, None): 407, (late_zi, end, None, None): 528}
            if bridge:
                verified[cut, late_zi, None, None] = None
            for independent in (None, verified):
                with self.subTest(bridge=bool(bridge), independent=independent is not None):
                    with self.assertRaisesRegex(ValueError, '实际窗口相隔不足一天.*一次跳过超过一个月'):
                        qiong.audit_query_range(day_plan, [unknown_bridge[0], *bridge, stale], snapshot=birth,
                                                verified_folded_ages=independent)
        successive = [unknown_bridge[0], read(cut, late_zi, 'day', 408), read(late_zi, end, 'day', 409)]
        verified = {(start, cut, None, None): 407, (cut, late_zi, None, None): 408,
                    (late_zi, end, None, None): 409}
        for independent in (None, verified):
            with self.subTest(successive=True, independent=independent is not None):
                with self.assertRaisesRegex(ValueError, '实际窗口相隔不足一天.*一次跳过超过一个月'):
                    qiong.audit_query_range(day_plan, successive, snapshot=birth, verified_folded_ages=independent)

        later, later_end = (datetime.fromisoformat(clock) for clock in (
            '2024-12-24T17:00:00+08:00', '2024-12-24T17:30:00+08:00'))
        long_plan = period_facts.period_facts(start, later_end, 'month')
        separated = [read(start, cut, 'month', 407), read(later, later_end, 'month', 528)]
        report = qiong.audit_query_range(long_plan, separated, snapshot=birth)
        self.assertTrue(report['unread_windows'])

    def test_query_range_rechecks_cached_age_against_independent_window_and_witness(self):
        birth = self._cli_snapshot('16:59')
        start, end = [datetime.fromisoformat(f'2005-05-15T{hour}:00+08:00') for hour in ('09:00', '17:00')]
        plan = period_facts.period_facts(start, end, 'day')
        segment, = plan['segments']
        positive, restricted, unknown = [qiong.evaluate_query_segment(birth, segment, age) for age in (292, 532, None)]
        self.assertEqual(positive['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_configuration_relatively_favorable')
        self.assertEqual(restricted['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_support_restricted')
        audit = qiong.audit_query_range
        self.assertEqual(audit(plan, [restricted], snapshot=birth)['unread_windows'], [])
        self.assertEqual(audit(plan, [positive, positive], snapshot=birth)['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '重叠实际窗口有冲突的已读面板折月年龄'):
            audit(plan, [positive, restricted], snapshot=birth)
        exact_key = (start, end, None, None)
        self.assertEqual(audit(plan, [positive], snapshot=birth, verified_folded_ages={exact_key: 292})['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '年龄不一致'):
            audit(plan, [restricted], snapshot=birth, verified_folded_ages={exact_key: 292})
        with self.assertRaisesRegex(ValueError, '年龄不一致'):
            audit(plan, [positive, restricted], snapshot=birth, verified_folded_ages={exact_key: 292})
        with self.assertRaisesRegex(ValueError, '年龄不一致'):
            audit(plan, [positive], snapshot=birth, verified_folded_ages={exact_key: None})
        self.assertEqual(audit(plan, [unknown], snapshot=birth, verified_folded_ages={exact_key: None})['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '非负整数'):
            audit(plan, [positive], snapshot=birth, verified_folded_ages={exact_key: True})
        with self.assertRaisesRegex(ValueError, '须提供原出生快照'):
            audit(plan, [positive], verified_folded_ages={exact_key: 292})

        band = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8, clock_band=('16:58', '17:02'))
        a, b = [row['witness'] for row in scenarios.birth_luck_tables(band)['tables']]
        age_plan = {(start, end, w['scenario_id'], w['witness_utc']): age for w, age in ((a, 292), (b, None))}
        selected = [qiong.evaluate_query_segment(band, segment, age, expected_birth_witness=w)
                    for w, age in ((a, 292), (b, None))]
        result = audit(plan, selected, snapshot=band, verified_folded_ages=age_plan)
        self.assertTrue(all(not row['unread_windows'] for row in result['unread_by_birth']))
        combined = qiong.evaluate_query_segment(band, segment, 292)
        with self.assertRaisesRegex(ValueError, '年龄不一致'):
            audit(plan, [combined], snapshot=band, verified_folded_ages=age_plan)
        del age_plan[(start, end, b['scenario_id'], b['witness_utc'])]
        with self.assertRaisesRegex(ValueError, '缺少本次独立核对'):
            audit(plan, selected, snapshot=band, verified_folded_ages=age_plan)

        from zoneinfo import ZoneInfo

        zone = ZoneInfo('America/New_York')
        left, right = (datetime(2006, 10, 29, 1, minute, tzinfo=zone, fold=1) for minute in (15, 30))
        fixed = [datetime.fromisoformat(point.isoformat()) for point in (left, right)]
        repeated = period_facts.period_facts(*fixed, 'day')
        repeated_read = qiong.evaluate_query_segment(birth, repeated['segments'][0], 310)
        zoned_key, fixed_key = (left, right, None, None), (*fixed, None, None)
        self.assertEqual(audit(repeated, [repeated_read], snapshot=birth,
                               verified_folded_ages={zoned_key: 310})['unread_windows'], [])
        self.assertEqual(audit(repeated, [repeated_read], snapshot=birth,
                               verified_folded_ages={zoned_key: 310, fixed_key: 310})['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '冲突的独立折月年龄'):
            audit(repeated, [repeated_read], snapshot=birth,
                  verified_folded_ages={zoned_key: 310, fixed_key: 311})

    def test_independent_folded_age_span_covers_subwindows_created_by_calendar_cutpoints(self):
        birth = self._cli_snapshot('11:01', birthday='1987-01-02')
        start, middle, end = [datetime.fromisoformat(value + '+08:00')
                              for value in ('2004-02-04T00:00', '2004-02-04T10:00', '2004-02-05T00:00')]
        whole_key = (start, end, None, None)
        for layer, count in (('year', 2), ('month', 2), ('day', 3)):
            plan = period_facts.period_facts(start, end, layer)
            readings = [qiong.evaluate_query_segment(birth, segment, 205) for segment in plan['segments']]
            first, last = (row['readings'][0]['panels'][layer] for row in (readings[0], readings[-1]))
            with self.subTest(layer=layer):
                self.assertEqual(len(readings), count)
                self.assertEqual(first['conditional_model_direction'], 'development_support_restricted')
                self.assertEqual(last['conditional_model_direction'], 'development_configuration_relatively_favorable')
                self.assertEqual(qiong.audit_query_range(plan, readings, snapshot=birth,
                                  verified_folded_ages={whole_key: 205})['unread_windows'], [])

        # Keep the day panels and evidence windows independently partitioned.
        before, after = (start, middle, None, None), (middle, end, None, None)
        self.assertEqual(qiong.audit_query_range(plan, readings, snapshot=birth,
                          verified_folded_ages={before: 205, after: 205})['unread_windows'], [])
        gap = (middle + timedelta(seconds=1), end, None, None)
        for evidence in ({before: 205, gap: 205}, {before: 205, after: 206}, {before: None, after: 205}):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValueError, '缺少本次独立核对'):
                qiong.audit_query_range(plan, readings, snapshot=birth, verified_folded_ages=evidence)
        stale = qiong.evaluate_query_segment(birth, plan['segments'][-1], 255)
        self.assertEqual(stale['readings'][0]['panels']['day']['conditional_model_direction'],
                         'development_support_restricted')
        with self.assertRaisesRegex(ValueError, '年龄不一致'):
            qiong.audit_query_range(plan, [*readings[:-1], stale], snapshot=birth,
                                   verified_folded_ages={whole_key: 205})

    def test_query_range_preserves_real_gap_in_civil_date_membership(self):
        birth = self._cli_snapshot('17:02')
        plan = period_facts.regional_date_facts(date(1988, 10, 29), date(1988, 10, 30), 'month',
                                                'America/Goose_Bay')
        first, second = plan['segments']
        self.assertLess(datetime.fromisoformat(first['end']), datetime.fromisoformat(second['start']))
        results = [qiong.evaluate_query_segment(birth, segment, 94) for segment in (first, second)]
        self.assertEqual(qiong.audit_query_range(plan, results)['unread_windows'], [])
        self.assertEqual(qiong.audit_query_range(plan, results[:1])['unread_windows'], [results[1]['window']])
        old = dict(plan, segments=[first])
        del old['time_basis']
        request = dict(start='1988-10-29', end='1988-10-30', layer='month', timezone='America/Goose_Bay')
        for expected in (None, request):
            self.assertEqual(qiong.audit_query_range(old, results[:1], expected_request=expected)['unread_windows'],
                             [results[1]['window']])
        clock_plan = period_facts.query_period_facts(plan['start'], plan['end'], 'month', plan['timezone'])
        self.assertEqual([clock_plan[key] for key in ('start', 'end')], [plan[key] for key in ('start', 'end')])
        for expected in (None, request):
            mixed = dict(plan, segments=clock_plan['segments'])
            with self.assertRaisesRegex(ValueError, '存档分段与重算的日期成员范围不一致'):
                qiong.audit_query_range(mixed, results, expected_request=expected)
        del old['civil_dates']
        for expected in (None, request):
            self.assertEqual(qiong.audit_query_range(old, results[:1], expected_request=expected)['unread_windows'],
                             [results[1]['window']])

    def test_explicit_date_archive_cannot_replace_the_original_window(self):
        birth = self._cli_snapshot('17:02')
        request = dict(start='2006-11-10', end='2006-11-11', layer='day', timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        next_day = period_facts.query_period_facts('2006-11-11', '2006-11-12', 'day', request['timezone'])
        read = [qiong.evaluate_query_segment(birth, segment, 310) for segment in plan['segments']]
        next_read = [qiong.evaluate_query_segment(birth, segment, 310) for segment in next_day['segments']]

        def directions(readings):
            return [row['readings'][0]['panels']['day']['conditional_model_direction'] for row in readings]

        self.assertEqual(directions(read), [
            'development_support_restricted', 'development_configuration_relatively_favorable',
        ])
        self.assertEqual(directions(next_read), ['development_configuration_relatively_favorable'] * 2)

        audit = qiong.audit_query_range
        changed_dates = dict(plan, civil_dates=next_day['civil_dates'])
        with self.assertRaisesRegex(ValueError, '日期起止.*原查询重算不一致'):
            audit(changed_dates, next_read, snapshot=birth)
        with self.assertRaisesRegex(ValueError, '原查询请求不一致'):
            audit(changed_dates, next_read, snapshot=birth, expected_request=request)

        wrong_boundary = dict(plan, boundaries=next_day['boundaries'])
        wrong_segment = dict(plan, segments=[*plan['segments'], *next_day['segments']])
        wrong_zone = dict(plan, timezone_source=dict(plan['timezone_source'], zone='Asia/Tokyo'))
        wrong_basis = dict(plan, time_basis='civil_fixed_offset')
        partial = dict(plan, segments=plan['segments'][:1])
        del partial['time_basis'], partial['boundaries']
        for expected in (None, request):
            options = dict(snapshot=birth, expected_request=expected)
            for archive, error in ((wrong_boundary, '日期成员间隙与原查询重算不一致'),
                                   (wrong_segment, '存档分段与重算的日期成员范围不一致'),
                                   (wrong_zone, '保存的时区来源'),
                                   (wrong_basis, '存档民用日期范围须使用原 IANA 时区口径')):
                with self.subTest(expected=expected, error=error), self.assertRaisesRegex(ValueError, error):
                    audit(archive, read, **options)
            self.assertEqual(audit(partial, read[:1], **options)['unread_windows'], [read[-1]['window']])
            self.assertEqual(audit(partial, read, **options)['unread_windows'], [])

    def test_missing_date_membership_metadata_does_not_expand_repeated_date_scope(self):
        birth = self._cli_snapshot('16:59')
        zone = 'America/Goose_Bay'
        for layer in ('day', 'month'):
            with self.subTest(layer=layer):
                request = dict(start='1988-10-30', end='1988-10-31', layer=layer, timezone=zone)
                date_plan = period_facts.query_period_facts(request['start'], request['end'], layer, zone)
                clock_plan = period_facts.query_period_facts(date_plan['start'], date_plan['end'], layer, zone)
                other_date = period_facts.query_period_facts('1988-10-29T22:01-04:00',
                                                            '1988-10-30T00:00-04:00', layer, zone)
                valid = [qiong.evaluate_query_segment(birth, segment, 94) for segment in date_plan['segments']]
                extra = [qiong.evaluate_query_segment(birth, segment, 94) for segment in other_date['segments']]
                if layer == 'day':
                    self.assertEqual(other_date['segments'][0]['facts'][-1]['pillar'], '丁巳')
                archive = dict(date_plan)
                del archive['civil_dates']
                audit = qiong.audit_query_range
                for expected in (None, request):
                    options = dict(snapshot=birth, expected_request=expected)
                    self.assertEqual(audit(archive, valid, **options), audit(date_plan, valid, **options))
                    with self.assertRaisesRegex(ValueError, '已读窗口不属于原查询'):
                        audit(archive, [*valid, *extra], **options)
                stripped = dict(archive)
                del stripped['boundaries']
                self.assertEqual(audit(stripped, valid, snapshot=birth, expected_request=request)['unread_windows'],
                                 [])
                wrong_rows = dict(stripped, segments=[*stripped['segments'], *other_date['segments']])
                with self.assertRaisesRegex(ValueError, '存档分段与重算的日期成员范围不一致'):
                    audit(wrong_rows, valid, snapshot=birth, expected_request=request)

                clock_request = dict(request, start=clock_plan['start'], end=clock_plan['end'])
                self.assertEqual(audit(clock_plan, [*valid, *extra], snapshot=birth,
                                       expected_request=clock_request)['unread_windows'], [])
                for expected in (None, clock_request):
                    with self.assertRaisesRegex(ValueError, '存档分段或边界与连续钟面范围不一致'):
                        audit(stripped, [*valid, *extra], snapshot=birth, expected_request=expected)
                ambiguous = dict(stripped, segments=stripped['segments'][:1])
                with self.assertRaisesRegex(ValueError, '无法区分日期成员范围与连续钟面范围'):
                    audit(ambiguous, valid, snapshot=birth)
                self.assertEqual(audit(ambiguous, valid, snapshot=birth,
                                       expected_request=request)['unread_windows'], [])
                self.assertEqual(audit(ambiguous, [*valid, *extra], snapshot=birth,
                                       expected_request=clock_request)['unread_windows'], [])
                with self.assertRaisesRegex(ValueError, '日期成员间隙与原查询重算不一致'):
                    audit(clock_plan, valid, snapshot=birth, expected_request=request)
                with self.assertRaisesRegex(ValueError, '日期成员间隙与原查询重算不一致'):
                    audit(archive, valid, snapshot=birth, expected_request=clock_request)
                with self.assertRaisesRegex(ValueError, '存档分段与重算的日期成员范围不一致'):
                    audit(dict(clock_plan, boundaries=date_plan['boundaries']), valid, snapshot=birth)
                source = dict(archive['timezone_source'], zone='America/St_Johns')
                with self.assertRaisesRegex(ValueError, '保存的时区来源'):
                    audit(dict(archive, timezone_source=source), valid, snapshot=birth)

    def test_query_segment_binds_separate_ages_to_actual_witnesses_of_one_candidate(self):
        birthday = date(1982, 12, 14)
        birth = scenarios.analyze_birth_date(birthday, '男', utc_offset=8, shichen='未')
        self.assertEqual(len(birth['candidates']), 1)
        early, late = [row['birth_witnesses'][0] for row in birth['dayun_age_comparison']['segments']]
        self.assertEqual(early['scenario_id'], late['scenario_id'])
        self.assertNotEqual(early['witness_utc'], late['witness_utc'])
        start = datetime.fromisoformat('2020-07-14T13:30+08:00')
        end = datetime.fromisoformat('2020-07-14T14:00+08:00')
        for layer in ('month', 'day'):
            with self.subTest(layer=layer):
                segment, = period_facts.period_facts(start, end, layer)['segments']
                shared = qiong.evaluate_query_segment(birth, segment, 450)['readings']
                self.assertEqual([reading['witness'] for reading in shared], [early, late])
                self.assertEqual(shared[0]['panels'][layer]['conditional_model_direction'],
                                 'ordinary_positive_not_established')
                for age, witness in ((451, early), (450, late)):
                    reading, = qiong.evaluate_query_segment(
                        birth, segment, age, expected_birth_witness=witness)['readings']
                    self.assertEqual(reading['witness'], witness)
                    panel = reading['panels'][layer]
                    self.assertEqual(panel['temporal_facts'][0]['pillar'], '丙辰')
                    self.assertEqual(panel['conditional_model_direction'], 'development_support_restricted')

        wrong_pair = dict(early, scenario_id='birth-shichen-candidate-2')
        with self.assertRaisesRegex(ValueError, '指定出生见证不存在'):
            qiong.evaluate_query_segment(birth, segment, 451, expected_birth_witness=wrong_pair)
        ambiguous = copy.deepcopy(birth)
        ambiguous['dayun_age_comparison']['segments'][0]['birth_witnesses'].append(early)
        with self.assertRaisesRegex(ValueError, '见证.*不一致'):
            qiong.evaluate_query_segment(ambiguous, segment, 451, expected_birth_witness=early)
        no_table = scenarios.analyze_birth_date(birthday, '男', utc_offset=8)
        with self.assertRaisesRegex(ValueError, '没有指定出生见证的可核大运来源'):
            qiong.evaluate_query_segment(no_table, segment, 451, expected_birth_witness=early,
                                         verified_natal_cores=[birth['candidates'][0]['analysis']])

        verified = [no_table['candidates'][0]['analysis']]
        result = qiong.evaluate_query_segment(no_table, segment, None, verified_natal_cores=verified)
        self.assertEqual(result['readings'][0]['luck_status'], 'birth_luck_unverified')
        plan = period_facts.period_facts(start, end, 'day')
        self.assertEqual(qiong.audit_query_range(plan, [result], snapshot=no_table,
                                                verified_natal_cores=verified)['unread_windows'], [])
        with self.assertRaisesRegex(ValueError, '与本次原出生快照'):
            qiong.audit_query_range(plan, [result], snapshot=no_table)

    def test_date_only_followup_replays_all_reachable_three_pillar_candidates(self):
        birth = scenarios.analyze_birth_date(date(1980, 12, 24), '男', utc_offset=8)
        other = scenarios.analyze_birth_date(date(1980, 12, 23), '男', utc_offset=8)
        ids = [row['id'] for row in birth['candidates']]
        start = datetime.fromisoformat('2006-11-10T10:00:00+08:00')
        end = datetime.fromisoformat('2006-11-10T11:00:00+08:00')
        for layer in ('day', 'month'):
            with self.subTest(layer=layer):
                plan = period_facts.period_facts(start, end, layer)
                segment, = plan['segments']
                result = qiong.evaluate_query_segment(birth, segment, None)
                self.assertEqual(result['natal_candidate_coverage'], dict(read=ids, unread=[]))
                before, after = result['readings']
                for row in (before, after):
                    self.assertIsNone(row['witness'])
                    self.assertEqual(row['luck_status'], 'birth_luck_unverified')
                    self.assertEqual(row['panels'][layer]['missing_pillars'], ['hour'])
                self.assertEqual(before['birth_segments'][0]['end_utc'], '1980-12-24T15:00:00+00:00')
                self.assertEqual(after['birth_segments'][0]['start_utc'], '1980-12-24T15:00:00+00:00')
                self.assertEqual(before['panels'][layer]['conditional_model_direction'], 'withheld')
                self.assertEqual(after['panels'][layer]['conditional_model_direction'], 'outside_scope')
                if layer == 'day':
                    self.assertEqual(before['panels']['day']['specific_gui_countercondition']['status'], 'present')
                audit = qiong.audit_query_range(plan, [result], snapshot=birth)
                self.assertEqual(audit['unread_windows'], [])
                self.assertEqual(audit['unread_by_birth'], [dict(scenario_id=i, witness_utc=None, unread_windows=[])
                                                          for i in ids])

        selected = [birth['candidates'][0]['analysis']]
        result = qiong.evaluate_query_segment(birth, segment, None, verified_natal_cores=selected)
        self.assertEqual(result['natal_candidate_coverage'], dict(read=ids[:1], unread=ids[1:]))
        with self.assertRaisesRegex(ValueError, '不属于本次原民用生日候选'):
            qiong.evaluate_query_segment(birth, segment, None,
                                         verified_natal_cores=[other['candidates'][0]['analysis']])
        incomplete = dict(birth, candidates=birth['candidates'][:1])
        with self.assertRaisesRegex(ValueError, '六字候选或实际区间与原民用生日重算不一致'):
            qiong.evaluate_query_segment(incomplete, segment, None)

    def test_civil_birth_archive_without_age_table_keeps_natal_and_period_evidence(self):
        request = dict(start='2026-06-08T14:00', end='2026-06-09T14:40', layer='day', timezone='Asia/Shanghai')
        plan = period_facts.query_period_facts(request['start'], request['end'], request['layer'], request['timezone'])
        for precision in (dict(shichen='亥'), dict(clock_band=('21:15', '21:45'))):
            with self.subTest(precision=precision):
                birth = scenarios.analyze_birth_date(date(1986, 12, 23), '男', zone='Asia/Shanghai', **precision)
                native = [qiong.evaluate_query_segment(birth, segment, 473)['readings'][0]['panels']['day']
                          for segment in plan['segments']]
                self.assertEqual([panel['conditional_model_direction'] for panel in native],
                                 ['development_support_restricted', 'development_configuration_relatively_favorable'])
                witness = scenarios.birth_luck_tables(birth)['tables'][0]['witness']
                archive = copy.deepcopy(birth)
                del archive['dayun_age_comparison']
                self.assertEqual(scenarios.luck_contexts_at_age(archive, 473)['contexts'], [])
                recovery = scenarios.birth_luck_tables(archive)
                self.assertEqual((recovery['coverage'], recovery['tables']), ('birth_luck_unverified', []))
                candidate, = recovery['natal_candidates']
                self.assertEqual(candidate['pillars'], birth['candidates'][0]['pillars'])
                self.assertEqual(qiong.evaluate_periods(candidate['analysis'], [])['natal']['conditional_model_direction'],
                                 'development_configuration_relatively_favorable')
                with self.assertRaisesRegex(ValueError, '没有指定出生见证的可核大运来源'):
                    qiong.evaluate_query_segment(archive, plan['segments'][0], 473, expected_birth_witness=witness)
                with self.assertRaisesRegex(ValueError, '与本次原出生快照'):
                    qiong.audit_query_range(plan, [qiong.evaluate_query_segment(birth, plan['segments'][0], 473)],
                                            snapshot=archive, expected_request=request)

                reads = [qiong.evaluate_query_segment(archive, segment, 473) for segment in plan['segments']]
                for reading, pillar, counter in zip(reads, ('癸丑', '甲寅'), ('present', 'unknown')):
                    row, = reading['readings']
                    panel = row['panels']['day']
                    self.assertEqual(row['luck_status'], 'birth_luck_unverified')
                    self.assertIsNone(row['witness'])
                    self.assertEqual(row['birth_segments'], candidate['birth_segments'])
                    self.assertEqual(panel['conditional_model_direction'], 'withheld')
                    self.assertEqual(panel['temporal_facts'][-1]['pillar'], pillar)
                    self.assertEqual(panel['specific_gui_countercondition']['status'], counter)
                    self.assertEqual(panel['unknown_temporal_layers'], ['luck'])
                ages = {(*[datetime.fromisoformat(s[key]) for key in ('start', 'end')], candidate['id'], None): 473
                        for s in plan['segments']}
                audit = qiong.audit_query_range(plan, reads, snapshot=archive, expected_request=request,
                                                verified_folded_ages=ages)
                self.assertEqual(audit['unread_windows'], [])
                self.assertEqual(audit['unread_by_birth'],
                                 [dict(scenario_id=candidate['id'], witness_utc=None, unread_windows=[])])
                partial = qiong.audit_query_range(plan, reads[1:], snapshot=archive, expected_request=request)
                self.assertEqual(partial['unread_by_birth'][0]['unread_windows'], [reads[0]['window']])

                malformed = dict(birth, dayun_age_comparison=None)
                with self.assertRaisesRegex(ValueError, '折月表无有效运段'):
                    scenarios.birth_luck_tables(malformed)
                wrong = copy.deepcopy(birth)
                wrong['dayun_age_comparison']['segments'][0]['age_windows'][1]['start_months_inclusive'] += 1
                with self.assertRaisesRegex(ValueError, '原生折月不一致'):
                    scenarios.birth_luck_tables(wrong)
                archive['windows'][0]['end'] = archive['windows'][0]['start']
                with self.assertRaisesRegex(ValueError, '区间与原出生输入重算不一致'):
                    qiong.evaluate_query_segment(archive, plan['segments'][0], 473)

    def test_civil_birth_archive_without_age_table_retains_each_birth_branch(self):
        birth = scenarios.analyze_birth_date(date(1986, 12, 23), '男', utc_offset=8, clock_band=('22:30', '23:30'))
        del birth['dayun_age_comparison']
        plan = period_facts.query_period_facts('2026-06-08T14:00+08:00', '2026-06-08T14:40+08:00', 'day')
        segment, = plan['segments']
        reading = qiong.evaluate_query_segment(birth, segment, None)
        first, second = reading['readings']
        self.assertEqual(first['panels']['day']['conditional_model_direction'], 'withheld')
        self.assertEqual(second['panels']['day']['conditional_model_direction'], 'outside_scope')
        ids = [candidate['id'] for candidate in birth['candidates']]
        self.assertEqual(reading['natal_candidate_coverage'], dict(read=ids, unread=[]))

        cores = [birth['candidates'][0]['analysis']]
        selected = qiong.evaluate_query_segment(birth, segment, None, verified_natal_cores=cores)
        self.assertEqual(selected['natal_candidate_coverage'], dict(read=ids[:1], unread=ids[1:]))
        audit = qiong.audit_query_range(plan, [selected], snapshot=birth, verified_natal_cores=cores)
        self.assertEqual(audit['unread_windows'], [])
        self.assertEqual(audit['unread_by_birth'], [
            dict(scenario_id=ids[0], witness_utc=None, unread_windows=[]),
            dict(scenario_id=ids[1], witness_utc=None, unread_windows=[selected['window']]),
        ])

        near_birth = period_facts.query_period_facts('1986-12-23T23:15+08:00', '1986-12-23T23:40+08:00', 'day')
        with self.assertRaisesRegex(ValueError, '与原出生范围相交'):
            qiong.evaluate_query_segment(birth, near_birth['segments'][0], None)
        self.assertEqual(qiong.evaluate_query_segment(birth, near_birth['segments'][0], None,
                                                     verified_natal_cores=cores)['natal_candidate_coverage'],
                         dict(read=ids[:1], unread=ids[1:]))

    def test_query_range_replays_independently_read_natal_candidate_subsets(self):
        birth = scenarios.analyze_birth_date(date(1986, 12, 23), '男', zone='Asia/Shanghai',
                                             clock_band=('22:30', '23:30'))
        del birth['dayun_age_comparison']
        plan = period_facts.query_period_facts('2026-06-08T22:40', '2026-06-08T23:20',
                                              'day', 'Asia/Shanghai')
        a, b = birth['candidates']
        cores = [a['analysis'], b['analysis']]
        by_segment = [[qiong.evaluate_query_segment(birth, segment, None, verified_natal_cores=[core])
                       for core in cores] for segment in plan['segments']]
        early_a, early_b = by_segment[0]
        late_a, late_b = by_segment[1]
        audit = qiong.audit_query_range
        mixed = audit(plan, [early_a, late_b], snapshot=birth, verified_natal_cores=cores)
        self.assertEqual(mixed['unread_windows'], [])
        self.assertEqual(mixed['unread_by_birth'], [
            dict(scenario_id=a['id'], witness_utc=None, unread_windows=[late_a['window']]),
            dict(scenario_id=b['id'], witness_utc=None, unread_windows=[early_b['window']]),
        ])
        complete = audit(plan, [early_a, early_b, late_a, late_b], snapshot=birth, verified_natal_cores=cores)
        self.assertTrue(all(not row['unread_windows'] for row in complete['unread_by_birth']))
        with self.assertRaisesRegex(ValueError, '本次未独立核对'):
            audit(plan, [late_b], snapshot=birth, verified_natal_cores=cores[:1])
        foreign = copy.deepcopy(b['analysis'])
        foreign['facts']['hour']['pillar'] = '己亥'
        with self.assertRaisesRegex(ValueError, '不属于本次原民用生日候选'):
            audit(plan, [early_a], snapshot=birth, verified_natal_cores=[a['analysis'], foreign])
        mislabeled = copy.deepcopy(late_b)
        mislabeled['natal_candidate_coverage'] = early_a['natal_candidate_coverage']
        with self.assertRaisesRegex(ValueError, '与本次原出生快照'):
            audit(plan, [mislabeled], snapshot=birth, verified_natal_cores=cores)

    def test_query_segment_reports_unread_witnesses_with_same_apparent_birth_candidate(self):
        birth = self._cli_snapshot('14:00', '--time-basis', 'apparent-solar', '--dut1-seconds', '0.6',
                                   '--uncertainty-minutes', '60', '--enumerate-scenarios',
                                   birthday='1982-12-14', longitude='117')
        other, early, late = [row['witness'] for row in scenarios.birth_luck_tables(birth)['tables']]
        self.assertEqual(early['scenario_id'], late['scenario_id'])
        self.assertNotEqual(early['witness_utc'], late['witness_utc'])
        start = datetime.fromisoformat('2020-06-20T09:00+08:00')
        end = datetime.fromisoformat('2020-06-20T17:00+08:00')
        segment, = period_facts.period_facts(start, end, 'day')['segments']
        full = qiong.evaluate_query_segment(birth, segment, 450)
        self.assertEqual(full['witness_coverage'],
                         dict(scope='all_available_witnesses', read=[other, early, late], unread=[]))
        self.assertEqual([r['panels']['day']['conditional_model_direction'] for r in full['readings']],
                         ['ordinary_positive_not_established', 'ordinary_positive_not_established',
                          'development_configuration_relatively_favorable'])
        selected = qiong.evaluate_query_segment(birth, segment, 450, expected_birth_witness=late)
        self.assertEqual(selected['witness_coverage'],
                         dict(scope='selected_birth_witness', read=[late], unread=[other, early]))
        self.assertEqual(selected['coverage'], full['coverage'])
        self.assertEqual(selected['coverage'], 'numerical_witnesses_not_exhaustive')
        self.assertEqual(selected['readings'], full['readings'][-1:])

        unknown = qiong.evaluate_query_segment(birth, segment, None, expected_birth_witness=early)
        self.assertEqual(unknown['witness_coverage']['read'], [early])
        self.assertEqual(unknown['witness_coverage']['unread'], [other, late])
        reading, = unknown['readings']
        self.assertEqual(reading['luck_status'], 'age_unknown')

        plan = period_facts.period_facts(start, end, 'day')
        audit = qiong.audit_query_range(plan, [selected], snapshot=birth)
        self.assertEqual(audit['unread_windows'], [])
        self.assertEqual(audit['unread_by_birth'], [
            dict(other, unread_windows=[selected['window']]),
            dict(early, unread_windows=[selected['window']]),
            dict(late, unread_windows=[]),
        ])
        late_only = qiong.audit_query_range(plan, [unknown], snapshot=birth, expected_birth_witness=late)
        self.assertEqual(late_only['unread_windows'], [selected['window']])
        self.assertEqual(late_only['unread_by_birth'], [dict(late, unread_windows=[selected['window']])])
        mismatched = dict(selected, witness_coverage=dict(selected['witness_coverage'], read=[early]))
        with self.assertRaisesRegex(ValueError, '与本次原出生快照'):
            qiong.audit_query_range(plan, [mismatched], snapshot=birth)

    def test_bound_luck_preserves_separate_midnight_candidates_with_identical_four_pillars(self):
        birth = json.loads(subprocess.check_output(
            [sys.executable, '-B', str(ROOT / 'scripts/build_chart.py'), '--solar', '1991-12-07',
             '--hour', '23:00', '--sex', '男', '--analysis-year', '2026', '--format', 'json',
             '--uncertainty-minutes', '75', '--enumerate-scenarios'], text=True))
        tables = scenarios.birth_luck_tables(birth)['tables']
        late, next_day = tables[-2:]
        self.assertEqual(late['analysis']['facts'], next_day['analysis']['facts'])
        self.assertNotEqual(late['witness']['scenario_id'], next_day['witness']['scenario_id'])
        witnesses = birth['scenarios']['dayun_age_comparison']['segments'][-1]['birth_witnesses']
        self.assertEqual(witnesses[-1], next_day['witness'])
        witnesses[-1]['scenario_id'] = late['witness']['scenario_id']
        with self.assertRaisesRegex(ValueError, '原枚举候选的日期或时辰不一致'):
            scenarios.birth_luck_tables(birth)

    def test_bound_upper_layers_can_span_lower_boundaries_and_keep_unknown(self):
        natal = self.analyze('乙酉 戊子 辛巳 己亥')
        luck = period('luck', '丙戌')
        for layer, start, end, lower in (
                ('year', '2006-06-01T00:00+08:00', '2006-07-01T00:00+08:00', 'month'),
                ('month', '2006-11-10T22:00+08:00', '2006-11-11T00:00+08:00', 'day')):
            with self.subTest(layer=layer):
                start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
                self.assertEqual(len(period_facts.period_facts(start, end, lower)['segments']), 2)
                segment, = period_facts.period_facts(start, end, layer)['segments']
                window = f'[{start.isoformat()}, {end.isoformat()})'
                rows = [luck, *segment['facts']]
                panels = qiong.evaluate_periods(natal, [*rows, period(lower, None)], expected_window=window)
                self.assertEqual(panels[layer], qiong.evaluate_periods(natal, rows)[layer])
                self.assertEqual(panels[lower]['status'], 'withheld')
                self.assertEqual(panels[lower]['unknown_temporal_layers'], [lower])

    def test_source_failure_withholds_detached_new_panel_without_input_mutation(self):
        a = self.analyze('丙寅 戊子 辛巳 己亥')
        frozen = copy.deepcopy(a)
        with patch('reviewed_knowledge.load_profile', side_effect=ValueError('hash mismatch')):
            p = qiong.evaluate(a['facts'], a['relations'], a['groups'], a['missing_pillars'])
            periods = qiong.evaluate_periods(a, [period('luck', '丙戌')])
        self.assertEqual(a, frozen)
        self.assertEqual(p['source_errors'], ['hash mismatch'])
        self.assertEqual(p['cards'], [])
        self.assertTrue(all(p['conditional_model_direction'] == 'withheld' for p in periods.values()))

    def test_new_core_field_does_not_replace_old_pattern_and_strength_states(self):
        a = self.analyze('乙酉 戊子 辛巳 己亥')
        self.assertEqual(a['pattern_reasoning']['decision'], 'no_candidate_on_route')
        self.assertEqual(a['strength_reasoning']['status'], 'withheld')
        self.assertEqual(a['qiong_xin_zi_model']['temporal_scope'], 'natal')
        self.assertIn('十一月辛完整条件模型', '\n'.join(core.render(a)))


if __name__ == '__main__':
    unittest.main()
