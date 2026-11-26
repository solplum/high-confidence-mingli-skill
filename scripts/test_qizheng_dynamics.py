#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for U4 Qizheng Dongwei Daxian, Xiaoxian, and yearly/monthly/daily transits."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pai_pan_qizheng as q  # noqa: E402
import qizheng_dynamics as qd  # noqa: E402


class QizhengDynamicsTests(unittest.TestCase):
    def test_dongwei_structure_continuity_and_bounds(self):
        """Verify 12 Dongwei stages cover all 12 palaces with contiguous boundaries and valid solar-degree duration."""
        res, _ = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47, analysis_year=2026)
        dw = res["dongwei_daxian"]
        self.assertIsNotNone(dw)
        self.assertGreaterEqual(dw["ming_gong_years"], 10.0)
        self.assertLessEqual(dw["ming_gong_years"], 20.0)
        stages = dw["stages"]
        self.assertEqual(len(stages), 12)
        # Verify house order & fixed durations for stages 2..12
        expected_durs = [10.0, 11.0, 15.0, 8.0, 7.0, 11.0, 4.5, 4.5, 4.5, 5.0, 5.0]
        self.assertEqual([s["duration_years"] for s in stages[1:]], expected_durs)
        self.assertEqual([s["house_name"] for s in stages], [x[0] for x in qd.DONGWEI_SEQUENCE])
        # Verify contiguous age intervals & contiguous sidereal boundaries (decreasing sidereal)
        for i in range(11):
            self.assertAlmostEqual(stages[i]["end_age"], stages[i + 1]["start_age"], places=3)
            # Stage i end_sidereal wraps modulo 360 to Stage i+1 start_sidereal (except 0<->360)
            self.assertAlmostEqual(
                (stages[i]["end_sidereal"] - stages[i + 1]["start_sidereal"]) % 360.0,
                0.0, places=2, msg=f"boundary {stages[i]['zhi']}->{stages[i+1]['zhi']}"
            )
        # Active stage in 2026 (age ~36.13y): Sample A ming=巳, Sun in 酉 at ~20% -> ming~12y -> 2026 should be in 官禄(申)
        act = dw["active"]
        self.assertIsNotNone(act)
        self.assertEqual(act["palace_limit"]["house_name"], "官禄")
        self.assertEqual(act["palace_limit"]["zhi"], "申")
        self.assertIn(act["degree_limit"]["mansion"], ("觜", "参"))

    def test_xiaoxian_classical_reverse_example(self):
        """《星学大成》L612: 1岁在命宫，满1周岁(2岁)逆退一宫，依次逆行."""
        birth = datetime(1990, 5, 15, 14, 0, tzinfo=q.BJ)
        res, _ = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47)
        dw = res["dongwei_daxian"]
        # Age 0.5 (1岁): 命宫 巳
        a1 = qd.evaluate_dongwei_at(birth, datetime(1990, 11, 15, 12, 0, tzinfo=q.BJ), res, dw)
        self.assertEqual(a1["xiaoxian"]["zhi"], "巳")
        self.assertEqual(a1["xiaoxian"]["house_name"], "命宫")
        self.assertTrue(a1["in_tongxian"])
        # Age 1.5 (2岁): 逆退一宫 -> 辰(财帛)
        a2 = qd.evaluate_dongwei_at(birth, datetime(1991, 11, 15, 12, 0, tzinfo=q.BJ), res, dw)
        self.assertEqual(a2["xiaoxian"]["zhi"], "辰")
        self.assertEqual(a2["xiaoxian"]["house_name"], "财帛")
        # Before birth raises ValueError (fail-fast, no silent clamp)
        with self.assertRaises(ValueError):
            qd.evaluate_dongwei_at(birth, datetime(1989, 5, 15, 12, 0, tzinfo=q.BJ), res, dw)
        with self.assertRaises(ValueError):
            q.compute((1990, 5, 15), 14, 0, 31.23, 121.47, analysis_year=1985)

    def test_exact_birthday_xiaoxian_and_centenarian_wraparound_and_descending_mansions(self):
        """Regression tests for audit findings: exact civil birthday Xiaoxian, >100y wraparound, descending mansions."""
        birth = datetime(1990, 5, 15, 14, 0, tzinfo=q.BJ)
        res, _ = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47)
        dw = res["dongwei_daxian"]
        # 午 palace stage traverses mansions in descending sidereal order: 张 → 星 → 柳
        wu_stage = next(s for s in dw["stages"] if s["zhi"] == "午")
        self.assertEqual(wu_stage["mansions_traversed"], ["张", "星", "柳"])
        # Exact birthday transition: 1 min before 1st birthday -> 1岁命宫; exact 1st birthday -> 2岁财帛
        before_bday = qd.evaluate_dongwei_at(birth, datetime(1991, 5, 15, 13, 59, tzinfo=q.BJ), res, dw)
        on_bday = qd.evaluate_dongwei_at(birth, datetime(1991, 5, 15, 14, 0, tzinfo=q.BJ), res, dw)
        self.assertEqual(before_bday["xiaoxian"]["house_name"], "命宫")
        self.assertEqual(on_bday["xiaoxian"]["house_name"], "财帛")
        self.assertEqual(before_bday["tongxian_house"], "命宫")
        self.assertEqual(on_bday["tongxian_house"], "财帛")
        # Centenarian wraparound (age ~102y > 97.51y cycle): limit_sid and age/date windows must match cycle 1
        cent = qd.evaluate_dongwei_at(birth, datetime(2092, 5, 15, 14, 0, tzinfo=q.BJ), res, dw)
        st1 = dw["stages"][0]
        self.assertEqual(cent["cycle_index"], 1)
        self.assertEqual(cent["palace_limit"]["step"], 1)
        self.assertFalse(cent["in_tongxian"])
        self.assertGreaterEqual(cent["degree_limit"]["sidereal"], st1["end_sidereal"])
        self.assertLessEqual(cent["degree_limit"]["sidereal"], st1["start_sidereal"])
        self.assertLessEqual(cent["palace_limit"]["start_age"], cent["exact_age_years"])
        self.assertGreater(cent["palace_limit"]["end_age"], cent["exact_age_years"])
        self.assertLessEqual(cent["palace_limit"]["start_date"], "2092-05-15")
        self.assertGreaterEqual(cent["palace_limit"]["end_date"], "2092-05-15")

    def test_blind_qa_regressions_noloc_polar_centenarian_and_midnight(self):
        """Regression tests for no-lat/lon Fail-Fast & report, polar report, centenarian CLI, and 23:59 ingress."""
        # 1. No-lat/lon must still Fail-Fast on pre-birth analysis_year & invalid target_instant (API + CLI)
        with self.assertRaises(ValueError):
            q.compute((1990, 5, 15), 14, 0, None, None, analysis_year=1985)
        with self.assertRaises(ValueError):
            q.compute((1990, 5, 15), 14, 0, None, None, target_instant=datetime(2026, 5, 19, 12, 0))
        with self.assertRaises(ValueError):
            q.compute((1990, 5, 15), 14, 0, None, None, target_instant=datetime(1985, 5, 15, 12, 0, tzinfo=q.BJ))
        bad_cli = subprocess.run(
            [sys.executable, "-B", str(HERE / "pai_pan_qizheng.py"),
             "--solar", "1990-05-15", "--hour", "14:00", "--analysis-year", "1985"],
            capture_output=True, text=True,
        )
        self.assertEqual(bad_cli.returncode, 2)
        self.assertIn("analysis_year", bad_cli.stderr)

        # 2. Centenarian cycle_index >= 1 on 1920-05-15 @ 2026-05-19 shows cycle-2 window in JSON & text CLI
        proc_cent = subprocess.run(
            [sys.executable, "-B", str(HERE / "qizheng_dynamic_facts.py"),
             "--solar", "1920-05-15", "--hour", "14:00", "--lat", "31.23", "--lon", "121.47",
             "--target-date", "2026-05-19", "--scope", "daily", "--format", "json"],
            capture_output=True, text=True, check=True,
        )
        cent_json = json.loads(proc_cent.stdout)
        pl = cent_json["dongwei_active"]["palace_limit"]
        self.assertEqual(cent_json["dongwei_active"]["cycle_index"], 1)
        self.assertLessEqual(pl["start_age"], cent_json["dongwei_active"]["exact_age_years"])
        self.assertGreater(pl["end_age"], cent_json["dongwei_active"]["exact_age_years"])
        self.assertLessEqual(pl["start_date"], "2026-05-19")
        self.assertGreaterEqual(pl["end_date"], "2026-05-19")
        self.assertNotEqual(pl["start_date"], "1920-05-15")

        proc_cent_txt = subprocess.run(
            [sys.executable, "-B", str(HERE / "qizheng_dynamic_facts.py"),
             "--solar", "1920-05-15", "--hour", "14:00", "--lat", "31.23", "--lon", "121.47",
             "--target-date", "2026-05-19", "--scope", "daily", "--format", "text"],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("第 2 周回绕", proc_cent_txt.stdout)
        self.assertNotIn("1920-05-15 ~ 1932", proc_cent_txt.stdout)

        # 3. Missing lat/lon & polar lat=90 reports must not drop full 神煞 / 十二人事宫 / 洞微大限
        r_noloc, w_noloc = q.compute((1990, 5, 15), 14, 0, None, None)
        rep_noloc = q.format_report(r_noloc, w_noloc, {"solar": "1990-05-15", "hour": 14, "minute": 0})
        self.assertIn("年干诸星", rep_noloc)
        self.assertIn("核心神煞", rep_noloc)
        self.assertIn("驾后神煞", rep_noloc)
        self.assertNotIn("只出十一曜躔度", rep_noloc)

        r_polar, w_polar = q.compute((1990, 5, 15), 14, 0, 90.0, 0.0, analysis_year=2026)
        rep_polar = q.format_report(
            r_polar, w_polar, {"solar": "1990-05-15", "hour": 14, "minute": 0, "lat": 90.0, "lon": 0.0}
        )
        self.assertIn("命度/恩用难仇：未计算或东方上升交点未定义", rep_polar)
        self.assertIn("## 十二人事宫", rep_polar)
        self.assertIn("核心神煞", rep_polar)
        self.assertIn("## 洞微大限", rep_polar)
        self.assertIn("目标时刻（2026-07-01", rep_polar)

        # 4. Midnight 23:59 boundary (real 2022-10-29T23:59 Moon 尾->箕) is captured on 10-29 and not duplicated on 10-30
        birth = datetime(1990, 5, 15, 14, 0, tzinfo=q.BJ)
        natal, _ = q.compute((1990, 5, 15), 14, 0, 31.23, 121.47)
        day29 = qd.compute_dynamic_layers(
            birth, natal, datetime(2022, 10, 29, 12, 0, tzinfo=q.BJ), scope="daily"
        )["layers"]["daily"]["moon_mansion_ingresses"]
        day30 = qd.compute_dynamic_layers(
            birth, natal, datetime(2022, 10, 30, 12, 0, tzinfo=q.BJ), scope="daily"
        )["layers"]["daily"]["moon_mansion_ingresses"]
        pairs29 = [(e["from"], e["to"], e["datetime_bj"]) for e in day29]
        pairs30 = [(e["from"], e["to"]) for e in day30]
        self.assertTrue(any(f == "尾" and t == "箕" and "2022-10-29T23:59" in ts for f, t, ts in pairs29))
        self.assertNotIn(("尾", "箕"), pairs30)

    def test_moon_narrow_mansion_zui_not_skipped_and_missing_lat_lon_report(self):
        """Regression tests for narrow 觜 (1.075°) double-crossing on 2026-05-19 and missing-lat/lon report."""
        ev = qd.scan_ingresses(
            datetime(2026, 5, 19, 0, 0, tzinfo=q.BJ),
            datetime(2026, 5, 19, 4, 0, tzinfo=q.BJ),
            bodies=("月",), mode="mansion",
        )
        pairs = [(e["from"], e["to"]) for e in ev]
        self.assertIn(("毕", "觜"), pairs)
        self.assertIn(("觜", "参"), pairs)
        # Missing lat/lon report must still surface computed 身宫, 星辰状态, and 年干变曜
        r_noloc, w_noloc = q.compute((1990, 5, 15), 14, 0, None, None)
        rep = q.format_report(r_noloc, w_noloc, {"solar": "1990-05-15", "hour": 14, "minute": 0})
        self.assertIn("身宫：丑宫", rep)
        self.assertIn("## 年干变曜与年干支神煞", rep)
        self.assertIn("## 星辰状态", rep)

    def test_yearly_monthly_daily_ingresses_and_cli_e2e(self):
        """End-to-end CLI test for yearly/monthly/daily transits & palace/mansion ingresses on Sample A."""
        proc = subprocess.run(
            [
                sys.executable, "-B", str(HERE / "qizheng_dynamic_facts.py"),
                "--solar", "1990-05-15", "--hour", "14:00",
                "--lat", "31.23", "--lon", "121.47",
                "--target-date", "2026-11-26", "--target-hour", "12:00",
                "--scope", "all", "--format", "json",
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["calculation_profile"], "calibrated-v3")
        self.assertEqual(data["natal_summary"]["ming_gong"], "巳")
        self.assertEqual(data["natal_summary"]["shen_gong"], "丑")
        self.assertEqual(data["layers"]["yearly"]["year_gz"]["year_gz"], "丙午")
        # Sun crosses 12 palaces in a year -> yearly ingresses must have >= 12 Sun events
        sun_yearly = [e for e in data["layers"]["yearly"]["palace_ingresses"] if e["body"] == "日"]
        self.assertEqual(len(sun_yearly), 12)
        # Every ingress event must show a genuine palace change
        for ev in data["layers"]["yearly"]["palace_ingresses"]:
            self.assertNotEqual(ev["from"], ev["to"])
            self.assertIsNotNone(ev["to_natal_house"])
        # Daily layer has all 11 transit bodies mapped to natal houses
        self.assertEqual(len(data["layers"]["daily"]["transit_bodies"]), 11)
        # Also verify text mode renders cleanly
        proc_txt = subprocess.run(
            [
                sys.executable, "-B", str(HERE / "qizheng_dynamic_facts.py"),
                "--solar", "1990-05-15", "--hour", "14:00",
                "--lat", "31.23", "--lon", "121.47",
                "--target-date", "2026-11-26", "--scope", "all", "--format", "text",
            ],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("当前洞微大限与小限", proc_txt.stdout)
        self.assertIn("流年太岁与行度过宫", proc_txt.stdout)
        self.assertIn("流日十一曜行度与原盘交汇", proc_txt.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
