#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pai_pan_qizheng.py 回归：黄金值对拍 + 古典规则例。

黄金值来源（[来源] stem-branch 开源实现，JPL DE441 校正级，2026-10-01 由
golden-runner.ts 生成）：A/B/C 三个时刻的日月五星、罗计孛、升度。
容差：日月 0.05°（同阶公式）/ 行星 0.5°（Schlyter vs VSOP87+DE441 两代实现）。
"""

import math
import os
import sys
import unittest
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pai_pan_qizheng as q  # noqa: E402

BJ = __import__("datetime").timezone(__import__("datetime").timedelta(hours=8))

# stem-branch 黄金值（tropical，度）
GOLDEN = {
    "A": {  # 1990-05-15T06:00Z, 上海 31.23/121.47
        "jd_ut": None, "sun": 54.1550, "moon": 294.0806, "mercury": 38.0450,
        "venus": 12.5327, "mars": 348.1486, "jupiter": 99.4979, "saturn": 295.2507,
        "rahu": 311.3491, "yuebei": 231.4078, "asc_tropical": 355.1811,
    },
    "B": {  # 2000-01-01T12:00Z, 北京 39.90/116.40
        "sun": 280.3689, "moon": 223.3239, "mercury": 271.8895,
        "venus": 241.5654, "mars": 327.9651, "jupiter": 25.2510, "saturn": 40.3923,
        "rahu": 125.0445, "yuebei": 263.3533, "asc_tropical": 318.0287,
    },
    "C": {  # 2024-01-11T11:57Z 新月时刻, 成都 30.57/104.06
        "sun": 290.7400, "moon": 290.7361, "mercury": 267.3333,
        "venus": 255.4266, "mars": 275.1367, "jupiter": 35.8028, "saturn": 334.2356,
        "rahu": 20.3225, "yuebei": 161.0298,
    },
}


def jd_of(iso_utc):
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return q.jd_from_utc(dt)


class AstronomyTests(unittest.TestCase):
    def test_separate_solar_models_preserve_regressions(self):
        """七政旧模型保持原值；八字新级数对照既有黄金值，不再要求同式相等。"""
        import pai_pan_bazi as b
        cases = (("A", "1990-05-15T06:00:00Z", 54.15992048602038),
                 ("B", "2000-01-01T12:00:00Z", 280.37330822671),
                 ("C", "2024-01-11T11:57:00Z", 290.7425510553476))
        for key, iso, legacy in cases:
            jd = jd_of(iso)
            jd_tt = jd + b.delta_t_seconds(2000 + (jd - 2451545.0) / 365.242189) / 86400.0
            self.assertAlmostEqual(q.sun_apparent_longitude(jd_tt), legacy, places=6)
            self.assertAlmostEqual(b.sun_apparent_longitude(jd_tt), GOLDEN[key]["sun"], delta=0.0001)

    def test_golden_sun_moon(self):
        """日月黄经对 stem-branch（容差 0.05°）。"""
        for key, iso in (("A", "1990-05-15T06:00:00Z"), ("B", "2000-01-01T12:00:00Z"),
                         ("C", "2024-01-11T11:57:00Z")):
            jd = jd_of(iso)
            jd_tt = jd + q.delta_t_seconds(2000 + (jd - 2451545.0) / 365.242189) / 86400.0
            self.assertAlmostEqual(q.sun_apparent_longitude(jd_tt), GOLDEN[key]["sun"], delta=0.05, msg=key)
            self.assertAlmostEqual(q.moon_longitude(jd_tt), GOLDEN[key]["moon"], delta=0.05, msg=key)

    def test_golden_planets(self):
        """五星黄经对 stem-branch（Schlyter vs VSOP87，容差 0.5°）。"""
        planet_key = {"mercury": "mercury", "venus": "venus", "mars": "mars",
                      "jupiter": "jupiter", "saturn": "saturn"}
        for key, iso in (("A", "1990-05-15T06:00:00Z"), ("B", "2000-01-01T12:00:00Z"),
                         ("C", "2024-01-11T11:57:00Z")):
            jd = jd_of(iso)
            for pname, pkey in planet_key.items():
                self.assertAlmostEqual(
                    q.planet_longitude(pname, jd), GOLDEN[key][pkey], delta=0.5,
                    msg="%s/%s" % (key, pname))

    def test_golden_rahu_yuebei(self):
        """罗睺（平升交点）与月孛（平远地点）对 stem-branch（0.02°）。"""
        for key, iso in (("A", "1990-05-15T06:00:00Z"), ("B", "2000-01-01T12:00:00Z"),
                         ("C", "2024-01-11T11:57:00Z")):
            jd = jd_of(iso)
            jd_tt = jd + q.delta_t_seconds(2000 + (jd - 2451545.0) / 365.242189) / 86400.0
            self.assertAlmostEqual(q.rahu_longitude(jd_tt), GOLDEN[key]["rahu"], delta=0.02, msg=key)
            self.assertAlmostEqual(q.yuebei_longitude(jd_tt), GOLDEN[key]["yuebei"], delta=0.02, msg=key)

    def test_ketu_is_rahu_opposition(self):
        """计都 = 罗睺 + 180°（口径声明第 5 条）。"""
        jd = jd_of("2000-01-01T12:00:00Z")
        jd_tt = jd + q.delta_t_seconds(2000) / 86400.0
        self.assertAlmostEqual(q.ketu_longitude(jd_tt), (q.rahu_longitude(jd_tt) + 180) % 360, places=6)

    def test_purple_qi_anchor(self):
        """紫气锚点：1975-03-13 16:00 UT = 230.5°（口径声明第 6 条）。"""
        jd = q.jd_from_utc(datetime(1975, 3, 13, 16, 0, tzinfo=timezone.utc))
        self.assertAlmostEqual(q.purple_qi_longitude(jd), 230.5, places=4)

    def test_legacy_ascendant_regression(self):
        """旧错误公式回归；这些同源值不是物理升点准确性证据。"""
        cases = (("A", "1990-05-15T06:00:00Z", 31.23, 121.47), ("B", "2000-01-01T12:00:00Z", 39.90, 116.40))
        for key, iso, lat, lon in cases:
            jd = jd_of(iso)
            jd_tt = jd + q.delta_t_seconds(2000 + (jd - 2451545.0) / 365.242189) / 86400.0
            eot = q.equation_of_time_minutes(jd)
            # 同一升度公式；残差来自 GMST 公式变体（IAU82 vs 新式），实测 ≤0.21°
            self.assertAlmostEqual(
                q.legacy_ascendant_tropical(jd, jd_tt, lat, lon, 0.0), GOLDEN[key]["asc_tropical"],
                delta=0.35, msg=key)
            self.assertLess(abs(eot), 20.0, "均时差应在意料范围内")

    def test_obliquity_j2000(self):
        """黄赤交角 J2000 = 23.4393°（Meeus 22.2 校验点）。"""
        self.assertAlmostEqual(q.mean_obliquity_deg(2451545.0), 23.43929111, places=4)


class MansionPalaceTests(unittest.TestCase):
    def test_mansion_boundaries(self):
        """角宿起点 0°；昴宿起点 210°；宿度循环归一。"""
        self.assertEqual(q.mansion_of(0.0)[0], "角")
        self.assertEqual(q.mansion_of(210.0)[0], "昴")
        self.assertEqual(q.mansion_of(359.9)[0], "轸")
        name, deg, _, _ = q.mansion_of(365.0)
        self.assertEqual(name, "角")
        self.assertAlmostEqual(deg, 5.0, places=6)

    def test_palace_aggregation(self):
        """十二支宫分野：角亢=辰、氐房心=卯、井鬼=未、翼轸=巳。"""
        self.assertEqual(q.palace_of(5.0), "辰")     # 角
        self.assertEqual(q.palace_of(30.0), "卯")    # 氐
        self.assertEqual(q.palace_of(40.0), "卯")    # 心
        self.assertEqual(q.palace_of(270.0), "未")   # 井
        self.assertEqual(q.palace_of(340.0), "巳")   # 翼
        self.assertEqual(q.palace_of(359.0), "巳")

    def test_sidereal_conversion_j2000(self):
        """legacy-v1 回归：201.2983° 赤经误作黄经，不是物理角宿一黄经。"""
        self.assertAlmostEqual(q.spica_ayanamsa(2451545.0), 201.2983, places=4)


class ClassicalRuleTests(unittest.TestCase):
    def test_ming_gong_classical_examples(self):
        """安命宫古典三例（《果老星宗入门图示》）。"""
        self.assertEqual(q.ming_gong_zhi("子", "子"), "卯")
        self.assertEqual(q.ming_gong_zhi("子", "丑"), "寅")
        self.assertEqual(q.ming_gong_zhi("酉", "午"), "午")

    def test_en_yong_chou_nan_gold_example(self):
        """金星命度（度主=金）：恩=土计、用=水孛月、难=日罗火、仇=木炁（金星例出处见口径声明第 7 条）。"""
        g = q.en_yong_chou_nan("金")
        self.assertEqual(set(g["恩"]), {"计都", "土"})
        self.assertEqual(set(g["用"]), {"水", "月孛", "月"})
        self.assertEqual(set(g["难"]), {"日", "罗睺", "火"})
        self.assertEqual(set(g["仇"]), {"木", "紫气"})
        self.assertEqual(g["同"], ["金"])  # 金星本身与度主同五行，入「同」不入四类


class EndToEndTests(unittest.TestCase):
    def test_sample_a_sun_palace_you(self):
        """样本 A（1990-05-15 14:00 北京时，上海）：太阳恒星黄经落昴宿 → 酉宫。"""
        result, warnings = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47)
        self.assertEqual(result["sun_palace_zhi"], "酉")
        # 未时生，太阳酉宫 → 命宫 = 酉 + (卯−未) = 巳
        self.assertEqual(result["ming_gong"]["zhi"], "巳")
        # 夜/昼：14:00 当地约 13:2x，上海日落约 18:5x → 昼生
        self.assertEqual(result["day_night"]["type"], "昼生")
        self.assertNotIn("Traceback", str(warnings))

    def test_chan_gong_full_mansion_mapping(self):
        """躔宫（v7 新增列）：二十八宿逐宿落宫 == 引擎文件头口径 3 的十二次分野聚合。"""
        expect = {
            "角": "辰", "亢": "辰", "氐": "卯", "房": "卯", "心": "卯",
            "尾": "寅", "箕": "寅", "斗": "丑", "牛": "丑", "女": "子", "虚": "子",
            "危": "亥", "室": "亥", "壁": "亥", "奎": "戌", "娄": "戌",
            "胃": "酉", "昴": "酉", "毕": "酉", "觜": "申", "参": "申",
            "井": "未", "鬼": "未", "柳": "午", "星": "午", "张": "午",
            "翼": "巳", "轸": "巳",
        }
        for name, _star, start, _wx in q.MANSIONS:
            got = q.palace_of(start + 0.5)  # 宿内取点，避边界
            self.assertEqual(got, expect[name], msg=f"{name}宿起点 {start}°")

    def test_palace_boundaries_twelve_ci(self):
        """十二次宫界边界点（引擎口径 3，未校准的近似宿界表）。"""
        cases = ((0.0, "辰"), (27.9, "辰"), (28.0, "卯"), (44.4, "卯"), (44.5, "寅"),
                 (73.4, "寅"), (73.5, "丑"), (106.9, "丑"), (107.0, "子"),
                 (128.9, "子"), (129.0, "亥"), (170.4, "亥"), (170.5, "戌"),
                 (198.4, "戌"), (198.5, "酉"), (237.4, "酉"), (237.5, "申"),
                 (260.9, "申"), (261.0, "未"), (297.9, "未"), (298.0, "午"),
                 (331.9, "午"), (332.0, "巳"), (359.9, "巳"))
        for lon, zhi in cases:
            self.assertEqual(q.palace_of(lon), zhi, msg=f"palace_of({lon})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
