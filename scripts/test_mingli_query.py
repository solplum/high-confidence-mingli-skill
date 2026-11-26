#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression and integrity tests for references/corpus and scripts/mingli_query.py."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mingli_query as mq  # noqa: E402


class CorpusAndQueryTests(unittest.TestCase):
    def test_manifest_sha256_and_stats_cli(self):
        res = mq.verify_manifest()
        self.assertTrue(res["ok"], f"Manifest mismatch: {res['files']}")
        self.assertEqual(res["manifest"]["total_records"], 1508)
        self.assertEqual(res["manifest"]["systems"], {"bazi": 666, "ziwei": 405, "qizheng": 437})
        self.assertIn("qizheng_bianyao_shensha.jsonl", res["files"])
        self.assertIn("qizheng_dongwei_liunian.jsonl", res["files"])
        self.assertEqual(res["manifest"]["qiongtong_stem_month_coverage"], "120/120")

        proc = subprocess.run(
            [sys.executable, "-B", str(HERE / "mingli_query.py"), "stats", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        cli_res = json.loads(proc.stdout)
        self.assertTrue(cli_res["ok"])

    def test_zero_pollution_leaks_across_all_records(self):
        recs = mq.load_records("all", include_feixing=True)
        self.assertEqual(len(recs), 1508)
        bad_vue = re.compile(r"<script|:::|<Donate|<Badge")
        pua_re = re.compile(r"[\ue000-\uf8ff]")
        stub_re = re.compile(r"^见\s*\[")
        for r in recs:
            txt = r["text"].strip()
            self.assertGreaterEqual(len(txt), 20, r["id"])
            self.assertNotRegex(txt, bad_vue, r["id"])
            self.assertNotIn("<!--", txt, r["id"])
            self.assertNotIn("知识来源门", txt, r["id"])
            self.assertNotRegex(txt, pua_re, r["id"])
            self.assertNotRegex(txt, stub_re, r["id"])
            if r["id"].startswith(("qzbs-", "qzdl-")):
                self.assertNotIn("?", txt, r["id"])
            for fake in ("逆袭", "企业高管", "紫微化忌", "紫微星化忌"):
                self.assertNotIn(fake, txt, r["id"])

    def test_qiongtong_full_120_coverage_and_spot_checks(self):
        for stem in mq.STEMS:
            for branch in mq.BRANCHES:
                with self.subTest(stem=stem, branch=branch):
                    res = mq.lookup_bazi(stem, branch, limit=3)
                    self.assertTrue(res["qiongtong"], f"Missing Qiongtong for {stem}{branch}")
                    self.assertGreaterEqual(len(res["classics"]), 1)

        spot_gui_mao = mq.lookup_bazi("癸", "卯")
        self.assertTrue(
            any("卯" in r["tags"].get("month_branches", []) and "癸" in r["text"] for r in spot_gui_mao["qiongtong"])
        )
        spot_jia_yin = mq.lookup_bazi("甲", "寅")
        self.assertTrue(any("甲木" in r["text"] or "正月甲" in r["title"] for r in spot_jia_yin["qiongtong"]))
        spot_ding_you = mq.lookup_bazi("丁", "酉")
        self.assertTrue(any("丁" in r["tags"].get("day_stem", "") and "酉" in r["tags"].get("month_branches", []) for r in spot_ding_you["qiongtong"]))
        for winter_branch in ("子", "丑"):
            spot_yi = mq.lookup_bazi("乙", winter_branch)
            self.assertTrue(any(winter_branch in r["tags"].get("month_branches", []) for r in spot_yi["qiongtong"]))

    def test_ziwei_feixing_boundary_and_balanced_search(self):
        default_hits = mq.search_records("飞星", system="ziwei", include_feixing=False, limit=10)
        self.assertTrue(all(r["school"] != "feixing_reference" for r in default_hits))

        with_feixing = mq.search_records("飞星", system="ziwei", include_feixing=True, limit=10)
        self.assertTrue(any(r["school"] == "feixing_reference" for r in with_feixing))

        # Balanced search across multiple Bazi books
        bazi_hits = mq.search_records("用神 格局", system="bazi", limit=6)
        books = {r["book"] for r in bazi_hits}
        self.assertGreaterEqual(len(books), 2)

    def test_qizheng_search_stars_and_geju(self):
        star_hits = mq.search_records("太阳 昼生", system="qizheng", limit=6)
        self.assertGreaterEqual(len(star_hits), 2)
        self.assertTrue(any("太阳" in r["text"] for r in star_hits))

        geju_hits = mq.search_records("官禄 格局", system="qizheng", limit=6)
        self.assertGreaterEqual(len(geju_hits), 2)

        bianyao_hits = mq.search_records("变曜 天禄 管库", system="qizheng", layer="bianyao_shensha", limit=6)
        self.assertGreaterEqual(len(bianyao_hits), 2)
        self.assertTrue(any(r["id"].startswith("qzbs-") for r in bianyao_hits))

        dongwei_hits = mq.search_records("洞微 百六 限度", system="qizheng", layer="dongwei_liunian", limit=6)
        self.assertGreaterEqual(len(dongwei_hits), 2)
        self.assertTrue(any(r["id"].startswith("qzdl-") for r in dongwei_hits))

        liunian_hits = mq.search_records("流年 太岁 倒限", system="qizheng", layer="dongwei_liunian", limit=6)
        self.assertGreaterEqual(len(liunian_hits), 2)

    def test_e2e_build_chart_to_chart_lookup_pipe(self):
        build_proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HERE / "build_chart.py"),
                "--solar",
                "1990-05-15",
                "--hour",
                "14:00",
                "--sex",
                "男",
                "--lat",
                "31.23",
                "--lon",
                "121.47",
                "--place",
                "上海",
                "--analysis-year",
                "2026",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lookup_proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HERE / "mingli_query.py"),
                "chart-lookup",
                "--chart-json",
                "-",
                "--topic",
                "career",
                "--limit",
                "4",
                "--json",
            ],
            input=build_proc.stdout,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(lookup_proc.stdout)
        self.assertEqual(payload["bazi"]["day_stem"], "庚")
        self.assertEqual(payload["bazi"]["month_branch"], "巳")
        self.assertGreaterEqual(len(payload["bazi"]["qiongtong"]), 1)
        self.assertGreaterEqual(len(payload["bazi"]["classics"]), 2)
        self.assertGreaterEqual(len(payload["ziwei"]["records"]), 2)
        self.assertTrue(all(r["school"] != "feixing_reference" for r in payload["ziwei"]["records"]))
        self.assertGreaterEqual(len(payload["qizheng"]["records"]), 2)
        self.assertEqual(payload["qizheng"]["shen_gong"], "丑")
        self.assertEqual(payload["qizheng"]["shen_zhu"], "土")
        self.assertEqual(payload["qizheng"]["year_gz"], "庚午")
        self.assertEqual(payload["qizheng"]["active_dongwei"]["palace"], "官禄")
        self.assertEqual(payload["qizheng"]["active_dongwei"]["zhi"], "申")


if __name__ == "__main__":
    unittest.main(verbosity=2)
