#!/usr/bin/env python3
"""CLI for Qizheng Siyu dynamic luck & transit queries (洞微大限 + 流年/流月/流日行度过宫).

Companion to scripts/ziwei_dynamic_facts.mjs for workflows/fortune-daily-weekly-monthly.md.
Pure Python stdlib; zero third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pai_pan_qizheng as qz  # noqa: E402
import qizheng_dynamics as qd  # noqa: E402


def _parse_date(text: str) -> tuple[int, int, int]:
    parts = [int(x) for x in text.split("-")]
    if len(parts) != 3:
        raise ValueError("日期需为 YYYY-MM-DD")
    datetime(parts[0], parts[1], parts[2])
    return parts[0], parts[1], parts[2]


def _parse_hour(text: str) -> tuple[int, int]:
    hh, mm = (int(x) for x in text.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("时刻需为 HH:MM")
    return hh, mm


def format_text(payload: dict) -> str:
    ns = payload["natal_summary"]
    lines = [
        "## 七政四余动态流运（%s）" % payload["target_bj"],
        "- 本命基准：%s年｜%s｜立命 %s宫｜命度 %s（度主 %s）｜身宫 %s宫（身主 %s）" % (
            ns["year_gz"] or "—", ns["day_night"] or "—", ns["ming_gong"] or "—",
            ns["ming_du"] or "—", ns["du_zhu_wuxing"] or "—",
            ns["shen_gong"] or "—", ns["shen_zhu"] or "—",
        ),
    ]
    dw = payload.get("dongwei_active")
    if dw:
        pl = dw["palace_limit"]
        dl = dw["degree_limit"]
        xx = dw["xiaoxian"]
        lines.append("")
        lines.append("### 当前洞微大限与小限（实岁 %.2f / 生日虚岁 %d）" % (dw["exact_age_years"], dw["nominal_age_birthday_rule"]))
        cycle_note = ("，第 %d 周回绕" % (dw["cycle_index"] + 1)) if dw.get("cycle_index", 0) > 0 else ""
        lines.append("- 大限限宫：%s（%s宫·宫主%s/%s，%s，%s ~ %s%s）" % (
            pl["house_name"], pl["zhi"], pl["ruler"], pl["ruler_wuxing"],
            pl["relation_to_natal_duzhu"] or "—", pl["start_date"], pl["end_date"], cycle_note,
        ))
        tongxian_note = ("；童限期内·当前童限行%s" % dw["tongxian_house"]) if dw["in_tongxian"] else ""
        lines.append("- 大限限度：%s宿%.2f度（度主 %s，%s%s）" % (
            dl["mansion"], dl["mansion_deg"], dl["du_zhu_wuxing"],
            dl["relation_to_natal_duzhu"] or "—", tongxian_note,
        ))
        lines.append("- 流年小限：%s（%s宫·宫主%s/%s）" % (
            xx["house_name"], xx["zhi"], xx["ruler"], xx["ruler_wuxing"],
        ))
        if dw["risk_signals"]:
            for r in dw["risk_signals"]:
                lines.append("- 行限提醒：%s" % r)

    layers = payload["layers"]
    if "yearly" in layers:
        yl = layers["yearly"]
        lines.append("")
        lines.append("### 流年太岁与行度过宫（%d 年 · %s年）" % (yl["year"], yl["year_gz"]["year_gz"]))
        if yl["taisui_alerts"]:
            lines.append("- 太岁引动：" + "；".join(yl["taisui_alerts"]))
        else:
            lines.append("- 太岁引动：流年太岁(%s)落本命%s" % (
                yl["taisui_12"]["太岁"]["zhi"], yl["taisui_12"]["太岁"]["natal_house"] or "—"))
        lines.append("- 流年变曜：天禄=%s、天权=%s、天福=%s、天刑=%s、天囚=%s" % (
            yl["transit_bianyao"]["天禄"]["star"], yl["transit_bianyao"]["天权"]["star"],
            yl["transit_bianyao"]["天福"]["star"], yl["transit_bianyao"]["天刑"]["star"],
            yl["transit_bianyao"]["天囚"]["star"],
        ))
        lines.append("- 全年过宫事件（共 %d 次，摘录慢星与太阳/火星过宫）：" % len(yl["palace_ingresses"]))
        for ev in yl["palace_ingresses"]:
            if ev["body"] in ("木", "土", "火", "罗睺", "计都", "月孛", "紫气", "日"):
                lines.append("  - %s %s %s→%s宫（入本命%s，%s宿，%s）" % (
                    ev["datetime_bj"][:16], ev["body"], ev["from"], ev["to"],
                    ev.get("to_natal_house") or "—", ev["to_mansion"], ev["motion"],
                ))

    if "monthly" in layers:
        ml = layers["monthly"]
        lines.append("")
        lines.append("### 流月行度过宫（%s）" % ml["year_month"])
        if ml["palace_ingresses"]:
            for ev in ml["palace_ingresses"]:
                lines.append("- %s %s %s→%s宫（入本命%s，%s宿，%s）" % (
                    ev["datetime_bj"][:16], ev["body"], ev["from"], ev["to"],
                    ev.get("to_natal_house") or "—", ev["to_mansion"], ev["motion"],
                ))
        else:
            lines.append("- 本月无政余过宫事件")
        if ml["sun_mansion_ingresses"]:
            for ev in ml["sun_mansion_ingresses"]:
                lines.append("- 太阳过宿：%s %s宿→%s宿（%s宫）" % (
                    ev["datetime_bj"][:16], ev["from"], ev["to"], ev["to_palace"],
                ))

    if "daily" in layers:
        dl = layers["daily"]
        lines.append("")
        lines.append("### 流日十一曜行度与原盘交汇（%s）" % dl["date"])
        lines.append("| 流曜 | 躔宿/入宿度 | 躔宫 | 落本命宫 | 恩难属性 | 流年化曜 |")
        lines.append("|---|---|---|---|---|---|")
        for s in qz.LUMINARIES:
            b = dl["transit_bodies"][s]
            lines.append("| %s | %s宿%.2f° | %s宫 | %s | %s | %s |" % (
                s, b["mansion"], b["mansion_deg"], b["palace"],
                b["natal_house"] or "—", b["en_yong_role"] or "—",
                b["transit_bianyao"] or "—",
            ))
        if dl["moon_mansion_ingresses"] or dl["moon_palace_ingresses"]:
            for ev in dl["moon_palace_ingresses"] + dl["moon_mansion_ingresses"]:
                lines.append("- 太阴当日%s：%s %s→%s（%s）" % (
                    ev["type"], ev["datetime_bj"][11:16], ev["from"], ev["to"], ev.get("to_natal_house") or ev["to_palace"],
                ))
        if dl["triggers"]:
            lines.append("- 原流交汇引动：")
            for tr in dl["triggers"]:
                orb_txt = ("（容差 %.2f°）" % tr["orb_deg"]) if "orb_deg" in tr else ""
                lines.append("  - 流%s(%s) %s %s%s" % (
                    tr["transit_body"], tr["en_yong_role"] or "—", tr["relation"], tr["target"], orb_txt,
                ))
    if payload.get("warnings"):
        lines.append("")
        lines.append("### 边界提醒")
        for w in payload["warnings"]:
            lines.append("- %s" % w)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="七政四余动态流运查询（洞微大限 + 流年/流月/流日过宫）")
    p.add_argument("--solar", required=True, help="出生公历 YYYY-MM-DD")
    p.add_argument("--hour", required=True, help="出生钟点 HH:MM（北京时间）")
    p.add_argument("--lat", type=float, required=True, help="出生纬度（北正）")
    p.add_argument("--lon", type=float, required=True, help="出生经度（东正）")
    p.add_argument("--target-date", required=True, help="目标公历日期 YYYY-MM-DD")
    p.add_argument("--target-hour", default="12:00", help="目标时刻 HH:MM（北京时间，默认 12:00）")
    p.add_argument("--scope", choices=("yearly", "monthly", "daily", "all"), default="all")
    p.add_argument("--format", choices=("text", "json"), default="json")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        by, bm, bd = _parse_date(args.solar)
        bhh, bmm = _parse_hour(args.hour)
        ty, tm, td = _parse_date(args.target_date)
        thh, tmm = _parse_hour(args.target_hour)
        birth_dt = datetime(by, bm, bd, bhh, bmm, tzinfo=qz.BJ)
        target_dt = datetime(ty, tm, td, thh, tmm, tzinfo=qz.BJ)
        natal_res, natal_warnings = qz.compute((by, bm, bd), bhh, bmm, args.lat, args.lon, birth_instant=birth_dt)
        payload = qd.compute_dynamic_layers(
            birth_dt, natal_res, target_dt, scope=args.scope, natal_warnings=natal_warnings
        )
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
        return 2
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
