#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for U3 Qizheng natal rules (身宫/身主, 十二人事宫, 年干变曜神煞, 星辰状态)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pai_pan_qizheng as q  # noqa: E402
import qizheng_rules as qr  # noqa: E402


class QizhengRulesTests(unittest.TestCase):
    def test_bianyao_classical_zhangguo_examples(self):
        """Verify 《张果星宗》卷二/十二/十五 classical examples of ten-stem 变曜."""
        # 甲生人: 天禄=火, 天贵(第6位)=月 (卷二 L340)
        jia = qr.compute_bianyao_shensha("甲", "子")
        self.assertEqual(jia["bianyao"]["天禄"]["star"], "火")
        self.assertEqual(jia["bianyao"]["天贵"]["star"], "月")
        self.assertEqual(jia["by_star"]["月"], "天贵")
        self.assertEqual(jia["bianyao"]["天权"]["star"], "罗睺")
        self.assertNotIn("日", jia["by_star"])  # 太阳不与变曜

        # 乙生人: 天禄=月孛, 天囚=罗睺 (卷十五 L1583: 六乙人为囚星)
        yi = qr.compute_bianyao_shensha("乙", "丑")
        self.assertEqual(yi["bianyao"]["天禄"]["star"], "月孛")
        self.assertEqual(yi["bianyao"]["天囚"]["star"], "罗睺")

        # 丙生人: 天禄=木 (卷十二 L1530: 六丙人为禄主星); 戊生人: 天囚=木 (六戊人为囚星)
        bing = qr.compute_bianyao_shensha("丙", "寅")
        wu = qr.compute_bianyao_shensha("戊", "辰")
        self.assertEqual(bing["bianyao"]["天禄"]["star"], "木")
        self.assertEqual(wu["bianyao"]["天囚"]["star"], "木")

        # 癸生人: 天禄=罗睺 (卷十五 L1583: 六癸人为天禄)
        gui = qr.compute_bianyao_shensha("癸", "亥")
        self.assertEqual(gui["bianyao"]["天禄"]["star"], "罗睺")

    def test_guanxing_matches_duilu_derivation_all_ten_stems(self):
        """Verify 卷二 L467: 官星 = 正官天干之天禄星 (甲以辛为官，辛以气为禄)."""
        zhengguan_stem = {
            "甲": "辛", "乙": "庚", "丙": "癸", "丁": "壬", "戊": "乙",
            "己": "甲", "庚": "丁", "辛": "丙", "壬": "己", "癸": "戊",
        }
        for stem, officer_stem in zhengguan_stem.items():
            expected_star = qr.compute_bianyao_shensha(officer_stem, "子")["bianyao"]["天禄"]["star"]
            actual_star = qr.compute_bianyao_shensha(stem, "子")["stem_stars"]["官星"]["star"]
            self.assertEqual(actual_star, expected_star, msg=f"{stem}官星应为{officer_stem}之禄({expected_star})")

    def test_shensha_classical_spot_checks(self):
        """Verify 卷二 天乙/玉堂/文昌/禄勋/刃/唐符/国印/空亡/驾前驾后."""
        gengwu = qr.compute_bianyao_shensha("庚", "午", ming_gong_zhi="巳", day_night_type="昼生")
        ps = gengwu["palace_shensha"]
        self.assertEqual(ps["天乙昼贵"], "丑")
        self.assertEqual(ps["玉堂夜贵"], "未")
        self.assertEqual(ps["当值贵人"]["zhi"], "丑")
        self.assertEqual(ps["文昌"], "亥")
        self.assertEqual(ps["禄勋"], "申")
        self.assertEqual(ps["阳刃"], "酉")
        self.assertEqual(ps["刃星"], "金")
        self.assertEqual(ps["唐符飞刃"], "卯")
        self.assertEqual(ps["国印"], "辰")
        self.assertEqual(ps["空亡"], ["戌", "亥"])
        self.assertEqual(ps["孤虚"], ["辰", "巳"])
        self.assertEqual(ps["劫杀"], "亥")
        self.assertEqual(ps["亡神"], "巳")
        self.assertEqual(ps["咸池"], "卯")
        self.assertEqual(gengwu["stem_stars"]["科甲"]["star"], "木")  # 巳对亥，亥宫主木
        self.assertEqual(gengwu["jiaqian_12"]["午"], "岁驾/剑锋/伏尸")
        self.assertEqual(gengwu["jiaqian_12"]["子"], "岁破/大耗/阑干")
        # 午(index 6): 红鸾 = (卯3 - 6)%12 = 酉9, 天喜 = 卯3
        self.assertEqual(gengwu["jiahou"]["红鸾"], "酉")
        self.assertEqual(gengwu["jiahou"]["天喜"], "卯")

    def test_twelve_houses_classical_mao_four_cardinals(self):
        """《张果星宗》卷十六: 命宫在卯时，田宅在子、妻妾在酉、官禄在午（四强居子午卯酉）."""
        dummy = {s: {"palace": "卯", "mansion": "房"} for s in q.LUMINARIES}
        houses = {h["name"]: h for h in qr.build_twelve_houses("卯", dummy)}
        self.assertEqual(houses["命宫"]["zhi"], "卯")
        self.assertEqual(houses["田宅"]["zhi"], "子")
        self.assertEqual(houses["妻妾"]["zhi"], "酉")
        self.assertEqual(houses["官禄"]["zhi"], "午")
        self.assertEqual(houses["相貌"]["zhi"], "辰")
        self.assertEqual(houses["福德"]["zhi"], "巳")
        self.assertEqual(houses["官禄"]["strength"], "强宫")
        self.assertEqual(houses["相貌"]["strength"], "弱宫")

    def test_sample_a_shen_gong_states_and_lichun_year_switch(self):
        """Sample A (1990-05-15 14:00 上海): 身宫丑(土主·斗木宿)、木星井宿升殿、庚午年变曜."""
        res, _ = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47)
        self.assertEqual(res["year_gz"]["year_gz"], "庚午")
        # Sample A Moon is in 斗宿 -> 丑宫; 命宫=巳 -> 丑 is 男女宫 (巳5->辰4->卯3->寅2->丑1 = index 5 男女)
        self.assertEqual(res["shen_gong"]["zhi"], "丑")
        self.assertEqual(res["shen_gong"]["shen_zhu"], "土")
        self.assertEqual(res["shen_gong"]["shen_du"]["mansion"], "斗")
        self.assertEqual(res["shen_gong"]["house_name"], "男女")
        # Jupiter in 井宿 -> 升殿!
        self.assertTrue(res["star_states"]["木"]["shengdian"])
        self.assertEqual(res["star_states"]["木"]["ming_hui"], "向明")  # 昼生木向明
        self.assertEqual(res["star_states"]["月"]["ming_hui"], "背晦")  # 昼生月背晦
        self.assertEqual(res["star_states"]["月孛"]["ming_hui"], "传本异文待参")
        # 庚年: 天禄=水
        self.assertEqual(res["bianyao_shensha"]["bianyao"]["天禄"]["star"], "水")

        # 立春边界：1990-02-03 10:00 仍是己巳年（天禄=月），1990-02-05 10:00 为庚午年（天禄=水）
        before_lc, _ = q.compute((1990, 2, 3), 10, 0, 31.23, 121.47)
        after_lc, _ = q.compute((1990, 2, 5), 10, 0, 31.23, 121.47)
        self.assertEqual(before_lc["year_gz"]["year_gz"], "己巳")
        self.assertEqual(before_lc["bianyao_shensha"]["bianyao"]["天禄"]["star"], "月")
        self.assertEqual(after_lc["year_gz"]["year_gz"], "庚午")
        self.assertEqual(after_lc["bianyao_shensha"]["bianyao"]["天禄"]["star"], "水")

    def test_shixian_and_xigong_relations(self):
        """Verify 忌躔失陷五格与喜宫歌五律."""
        bodies = {
            "火": {"mansion": "昴", "palace": "酉"},  # 火烧牛角, 火克酉金=入制
            "水": {"mansion": "奎", "palace": "戌"},  # 水漂羊, 戌火水克=入制
            "土": {"mansion": "翼", "palace": "巳"},  # 土埋双女, 土克巳水=入制
            "木": {"mansion": "女", "palace": "子"},  # 木打宝瓶, 木克子土=入制
            "金": {"mansion": "尾", "palace": "寅"},  # 金骑人马, 金克寅木=入制
            "日": {"mansion": "房", "palace": "卯"},  # 升殿, 卯火同气=庙堂
            "月": {"mansion": "心", "palace": "申"},  # 升殿, 申水同气=庙堂
            "罗睺": {"mansion": "尾", "palace": "寅"},
            "计都": {"mansion": "氐", "palace": "巳"},
            "月孛": {"mansion": "箕", "palace": "未"},
            "紫气": {"mansion": "角", "palace": "申"},
        }
        st = qr.compute_star_states(bodies, "夜生")
        self.assertIn("火烧牛角", st["火"]["shixian"])
        self.assertIn("水漂羊", st["水"]["shixian"])
        self.assertIn("土埋双女", st["土"]["shixian"])
        self.assertIn("木打宝瓶", st["木"]["shixian"])
        self.assertIn("金骑人马", st["金"]["shixian"])
        self.assertTrue(st["日"]["shengdian"])
        self.assertEqual(st["日"]["xigong_relation"], "庙堂")
        self.assertEqual(st["火"]["ming_hui"], "向明")  # 夜生火向明


if __name__ == "__main__":
    unittest.main(verbosity=2)
