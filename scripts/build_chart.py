#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建档总控：出生信息 → 三引擎 → chart.md 正文。

[来源] high-confidence-mingli-skill v4，2026-10-01。
调用本目录 pai_pan_bazi（八字）、pai_pan_qizheng（七政）与
scripts/pai_pan_ziwei/pai_pan.ts（紫微，需 node 环境，失败自动降级）。

【分工约定（S2）】确定性字段（四柱/藏干/十神/大运/紫微排布/七政位置/昼夜生）
= 脚本产出，禁止改动；判读字段（十神链/格局/调候/日主强弱/解释器种子）
= 结构版先列确定关系与未决前提，不自动判定格局成败或用神。

用法：
  python3 scripts/build_chart.py --solar 1990-05-15 --hour 14:00 --sex 男 \
      --lat 31.23 --lon 121.47 --place 上海 --name 某某
"""

import argparse
import json
import hashlib
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pai_pan_bazi as bazi  # noqa: E402
import bazi_core_reading as core_reading
import pai_pan_qizheng as qz  # noqa: E402
import qizheng_rule_profiles as qz_rules
import qizheng_traditional_reading as qz_tradition
import qizheng_sensitivity
import bazi_scenario_reading as scenario_reading
from time_scenarios import resolve_civil, enumerate_scenarios, timezone_provenance

ZIWEI_DIR = HERE / "pai_pan_ziwei"


def parse_iso(text):
    parts = [int(x) for x in text.split("-")]
    if len(parts) != 3:
        raise ValueError("--solar 需要 YYYY-MM-DD")
    date(*parts)  # reject impossible calendar dates before running engines
    return parts[0], parts[1], parts[2]


def parse_hour(text):
    hh, mm = (int(x) for x in text.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("--hour 需要 HH:MM")
    return hh, mm


def run_ziwei(y, m, d, hh, mm, sex, name, place, age_year=None, birth_year=None, output_format="text", explain_rules=False):
    """跑紫微引擎；无 node/依赖时返回降级说明。"""
    # Never let npx silently fetch and execute a missing dependency.
    runner = ZIWEI_DIR / "node_modules" / "tsx" / "dist" / "cli.mjs"
    if not runner.is_file():
        return None, "紫微数据缺失：请先在 scripts/pai_pan_ziwei 执行 npm ci。"
    cmd = ["node", "--import", "tsx", "pai_pan.ts", "--solar", "%04d-%02d-%02d" % (y, m, d),
           "--hour", "%02d:%02d" % (hh, mm), "--sex", sex]
    if output_format != "text":
        cmd += ["--format", output_format]
    if explain_rules:
        cmd += ["--explain-rules"]
    if name:
        cmd += ["--name", name]
    if place:
        cmd += ["--place", place]
    age_year = age_year if age_year is not None else date.today().year
    cmd += ["--age-year", str(age_year)]
    if birth_year is not None:
        cmd += ["--birth-year", str(birth_year)]
    try:
        proc = subprocess.run(cmd, cwd=str(ZIWEI_DIR), capture_output=True, text=True,
                              encoding="utf-8", timeout=120, shell=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:200])
        return proc.stdout.strip(), None
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return None, (
            "紫微数据缺失——内置紫微引擎需要 node 环境：`cd scripts/pai_pan_ziwei && npm ci` "
            "后重跑本脚本（当前失败原因：%s）。也可临时按旧流程从排盘 App 导入。" % exc
        )


def solar_clock(civil, lon, eot_minutes):
    """Naive solar clock label, NOT a timezone-aware physical instant."""
    if civil.utcoffset() is None:
        raise ValueError("太阳钟面转换需要明确 UTC 偏移")
    if not math.isfinite(lon) or not -180 <= lon <= 180 or not math.isfinite(eot_minutes):
        raise ValueError("经度或均时差无效")
    return civil.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=lon * 4 + eot_minutes)


def true_solar_time_text(hh, mm, lon, eot_minutes):
    """Legacy display helper; use floor via datetime for negative clock hours."""
    if lon is None:
        return "未校正（缺经度）"
    civil = datetime(2000, 1, 2, hh, mm, tzinfo=bazi.BJ)
    clock = solar_clock(civil, lon, eot_minutes)
    return clock.strftime("%H:%M") + "（当地真太阳时；均时差 %+.0f 分）" % eot_minutes


def bazi_section(bazi_res, temporal_uncertainty=False):
    p = bazi_res["pillars"]
    lines = ["## 八字", "", "| 柱 | 干支 | 十神 | 藏干 | 备注 |", "|----|------|------|------|------|"]
    labels = ("年", "月", "日", "时")
    for i, key in enumerate(("year", "month", "day", "hour")):
        gan, zhi, shishen, canggan = p[key]
        note = "时间不确定时标注置信度" if key == "hour" and gan == "未知" else ""
        lines.append("| %s | %s%s | %s | %s | %s |" % (labels[i], gan, zhi, shishen, canggan, note))
    lines += core_reading.render(core_reading.analyze(bazi_res, temporal_uncertainty=temporal_uncertainty))
    lines += ["", "### 神煞（脚本口径）"]
    if bazi_res["shensha_lines"]:
        lines += ["- " + s for s in bazi_res["shensha_lines"]]
    else:
        lines.append("- 无")
    return lines


def ziwei_section(ziwei_out, degrade_note):
    if ziwei_out is None:
        return ["## 紫微斗数", "", degrade_note, ""]
    return ["## 紫微斗数（内置 iztro 引擎 stdout 原文）", "", "```", ziwei_out, "```", ""]


def qizheng_section(qz_res):
    lines = ["## 七政四余", ""]
    lines.append("计算配置：%s；旧版命度/昼夜结果可能发生实质变化。" % qz_res.get("calculation_profile", "unspecified"))
    if qz_res.get("calculation_profile") == "physical-v2":
        lines.append("角宿一原点已改为日期平黄经；宿界/宫界仍是误差未知的近似表，命度、立命宫、度主和恩用难仇均为条件结果。")
    if qz_res["ming_du"] is None:
        lines.append("**命度**：东方上升交点未定义；恩用难仇不计算。")
    else:
        lines.append("**命度**：%s宿%.2f度（度主五行：%s，距星 %s，所在 %s宫）" % (
            qz_res["ming_du"]["mansion"], qz_res["ming_du"]["mansion_deg"],
            qz_res["ming_du"]["wuxing"], qz_res["ming_du"]["star"],
            qz.palace_of(qz_res["ming_du"]["sidereal"])))
    lines.append("**躔**：十一曜恒星黄经躔宿躔宫见下表")
    lines.append("")
    lines.append("| 星 | 黄道经度 | 恒星黄经 | 躔宿 | 入宿度 | 宿五行 | 躔宫 |")
    lines.append("|---|---|---|---|---|---|---|")
    for name in qz.LUMINARIES:
        b = qz_res["bodies"][name]
        lines.append("| %s | %.4f | %.4f | %s宿 | %.2f | %s | %s宫 |" % (
            name, b["tropical"], b["sidereal"], b["mansion"], b["mansion_deg"],
            b["mansion_wx"], qz.palace_of(b["sidereal"])))
    lines.append("")
    dn = qz_res["day_night"]
    if "solar_altitude_deg" in dn:
        lines.append("**昼生/夜生**：%s（太阳中心几何高度 %.4f°；阈值 %.3f°，非实测日出日落）" % (dn["type"], dn["solar_altitude_deg"], dn["threshold_deg"]))
    elif dn["type"] in ("极昼", "极夜"):
        lines.append("**昼生/夜生**：%s（%s）" % (dn["type"], dn.get("note", "")))
    else:
        lines.append("**昼生/夜生**：%s（日出 %.1f 时 / 日落 %.1f 时，当地平太阳时）" % (
            dn["type"], dn["sunrise_local"], dn["sunset_local"]))
    mg = qz_res["ming_gong"]
    lines.append("**立命宫**：%s宫（支五行 %s；果老安命法：太阳 %s 宫 + %s 时顺数至卯；宫主五行查 references/qizheng 宫分所属）" % (
        mg["zhi"], mg["wuxing"], mg["sun_palace"], mg["hour_zhi"]))
    lines.append("")
    if qz_res["en_yong"] is None:
        return lines
    lines.append("**难仇恩用**（以命度宿五行为我）：")
    lines.append("")
    lines.append("| 关系 | 五行 | 对应 | 含义 |")
    lines.append("|------|------|------|------|")
    meaning = {"恩": "生我", "用": "我生",
               "难": "克我", "仇": "我克", "同": "同我"}
    for key in ("恩", "用", "难", "仇"):
        members = qz_res["en_yong"].get(key, [])
        wxs = sorted({qz.LUMINARIES_WUXING[m2] for m2 in members})
        lines.append("| %s | %s | %s | %s |" % (
            key, "、".join(wxs) if wxs else "—", "、".join(members) if members else "—", meaning[key]))
    return lines


def dayun_section(bazi_res):
    lines = ["## 大运表", "", "- 方向：%s｜起运：%s" % (
        "顺排" if bazi_res["forward"] else "逆排", bazi_res["qiyun_text"]), "",
        "| 大运序 | 年龄范围 | 干支 |", "|---|---|---|"]
    for seq, ages, gz in bazi_res["dayun_rows"]:
        lines.append("| %s | %s | %s |" % (seq, ages, gz))
    lines.append("")
    lines.append("<!-- 紫微大限列：可由 agent 从紫微 stdout 的「大限」节补入（可缺） -->")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="三引擎建档 → chart.md 正文")
    parser.add_argument("--solar", required=True, help="公历 YYYY-MM-DD")
    parser.add_argument("--hour", required=True, help="HH:MM（民用钟表，UTC 偏移默认 +08）")
    parser.add_argument("--sex", required=True, choices=("男", "女"))
    parser.add_argument("--lat", type=float, required=True, help="纬度（北正）")
    parser.add_argument("--lon", type=float, required=True, help="经度（东正）")
    parser.add_argument("--qizheng-tradition", choices=(qz_tradition.SCHEME,))
    parser.add_argument("--qizheng-other-body", choices=qz_tradition.BODIES, default="金")
    parser.add_argument("--qizheng-profile", choices=("physical-v2", "legacy-v1"), default="physical-v2")
    parser.add_argument("--dut1-seconds", type=float, default=0.0, help="七政 UT1−UTC 秒，默认 0 为近似")
    parser.add_argument("--place", help="出生地")
    parser.add_argument("--name", help="称呼")
    parser.add_argument("--time-basis", choices=("civil", "mean-solar", "apparent-solar"), default="civil",
                        help="八字日时柱/紫微钟面，默认 civil 保持兼容")
    zone_group = parser.add_mutually_exclusive_group()
    zone_group.add_argument("--timezone", help="IANA 时区，例如 Asia/Shanghai；需要 Python 3.9+ 和时区数据库")
    parser.add_argument("--fold", type=int, choices=(0, 1), help="重复民用时间：0 较早，1 较晚；不默认选择")
    parser.add_argument("--enumerate-scenarios", action="store_true", help="枚举四柱与紫微离散输入，±120 分钟内；apparent-solar 仅数值候选，不证明穷尽")
    zone_group.add_argument("--utc-offset", type=float, default=8, help="出生钟表的固定 UTC 偏移小时；默认 +08，不自动推断历史夏令时")
    parser.add_argument("--qizheng-sensitivity-evidence", action="store_true", help="启用七政敏感性并在文本中附完整证据；JSON始终保留完整结构")
    parser.add_argument("--qizheng-sensitivity", action="store_true", help="独立七政时间敏感性：±120 分钟内采样并细化观察到的边界，不证明完整或稳定")
    parser.add_argument("--uncertainty-minutes", type=float, default=0, help="出生时刻正负误差分钟；未开启枚举时仅为中心候选")
    parser.add_argument("--age-year", type=int, help="紫微目标年份（默认当年）")
    parser.add_argument("--analysis-year", type=int, help="显式统一八字年度字段与紫微目标年；不指定时保留旧行为")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="JSON 快照供 ledger 引用；默认保留 chart.md")
    parser.add_argument("--explain-rules", action="store_true", help="展开紫微实现规则说明，不启用事件预测")
    args = parser.parse_args(argv)

    try:
        y, m, d = parse_iso(args.solar)
        hh, mm = parse_hour(args.hour)
        if not all(math.isfinite(x) for x in (args.lat, args.lon, args.utc_offset, args.uncertainty_minutes)):
            raise ValueError("坐标、UTC 偏移和误差必须为有限数值")
        if not -90 <= args.lat <= 90 or not -180 <= args.lon <= 180:
            raise ValueError("纬度/经度超出范围")
        if not -14 <= args.utc_offset <= 14 or args.utc_offset * 60 != int(args.utc_offset * 60):
            raise ValueError("UTC 偏移须在 -14 至 +14 小时内，精确到整分钟")
        if args.uncertainty_minutes < 0:
            raise ValueError("出生时刻误差不可为负")
        if args.age_year is not None and not y <= args.age_year <= 9999:
            raise ValueError("目标年份不能早于出生年或超出 9999")
        if args.analysis_year is not None and not y <= args.analysis_year <= 9999:
            raise ValueError("分析年份不能早于出生年或超出 9999")
        if args.analysis_year is not None and args.age_year is not None and args.analysis_year != args.age_year:
            raise ValueError("--analysis-year 与 --age-year 不可指定不同年份")
        civil = resolve_civil(datetime(y, m, d, hh, mm), args.utc_offset, args.timezone, args.fold)
        instant_bj = civil.astimezone(bazi.BJ)
        # Compute ephemerides from the original instant, never the corrected clock.
        qz_res, qz_warnings = qz.compute(
            (instant_bj.year, instant_bj.month, instant_bj.day), instant_bj.hour,
            instant_bj.minute, args.lat, args.lon, args.place, birth_instant=civil,
            profile=args.qizheng_profile, dut1_seconds=args.dut1_seconds)
        apparent = solar_clock(civil, args.lon, qz_res["eot_minutes"])
        mean = solar_clock(civil, args.lon, 0)
        clock = {"apparent-solar": apparent, "mean-solar": mean, "civil": civil.replace(tzinfo=None)}[args.time_basis]
        scenarios = enumerate_scenarios(civil, args.uncertainty_minutes, args.time_basis, args.lon, args.sex,
            datetime(args.analysis_year, 1, 1, tzinfo=bazi.BJ) if args.analysis_year else None) if args.enumerate_scenarios else None
        qz_comparison = qizheng_sensitivity.compare(civil, args.uncertainty_minutes, args.lat, args.lon,
            args.qizheng_profile, args.dut1_seconds, args.qizheng_tradition, args.qizheng_other_body) if (args.qizheng_sensitivity or args.qizheng_sensitivity_evidence) else None
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
        return 2

    scenario_comparison = scenario_reading.analyze(scenarios) if scenarios else None
    qz_traditional = qz_tradition.analyze(qz_res, args.qizheng_tradition, args.qizheng_other_body, bool(args.uncertainty_minutes))
    qz_reading = qz_rules.analyze(qz_res, temporal_uncertainty=bool(args.uncertainty_minutes))
    target_year = args.analysis_year if args.analysis_year is not None else args.age_year
    bazi_res = bazi.compute(
        solar_date=clock.date(), hour=clock.hour, minute=clock.minute,
        sex=args.sex, place=args.place, birth_instant=civil,
        **({"now": datetime(args.analysis_year, 1, 1, tzinfo=bazi.BJ)} if args.analysis_year is not None else {}))
    ziwei_out, ziwei_note = run_ziwei(
        clock.year, clock.month, clock.day, clock.hour, clock.minute,
        args.sex, args.name, args.place, target_year, civil.year,
        **({"output_format": "json"} if args.format == "json" else {}),
        **({"explain_rules": True} if args.explain_rules else {}))
    warnings = list(dict.fromkeys(bazi_res["warnings"] + qz_warnings))
    if clock.date() != civil.date():
        warnings.append("排盘钟面跨公历日期；八字日柱仍按原引擎 23:00 换日规则。")
    if args.uncertainty_minutes and not scenarios:
        warnings.append("出生时刻误差 ±%g 分钟：本盘仅中心时刻候选，未穷举误差区间；不得作为唯一确定命盘。" % args.uncertainty_minutes)
    if scenarios:
        warnings.append("误差候选范围仅四柱及紫微离散输入；未覆盖七政、起运、完整紫微或天文算法误差。晚子时仍沿用各引擎不同约定。")
        if args.time_basis == "apparent-solar":
            warnings.append("真太阳时候选采用数值边界包围；未证明穷尽，无稳定字段保证。1 毫秒求根容忍不是均时差或节气精度。")
    if clock.hour == 23:
        warnings.append("晚子时口径：八字 23:00 换日；紫微仍沿用原副本子时索引 0，未统一两盘换日约定。")

    if args.format == "json":
        # Preserve computed structures, encoding only date/datetime values as ISO strings.
        def encode_date(value):
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            raise TypeError("Unsupported snapshot type: " + type(value).__name__)
        snapshot = {"schema_version": 1, "input": vars(args),
                    "provenance": {"resolved_age_year": target_year if target_year is not None else date.today().year,
                        "timezone_source": timezone_provenance(args.timezone),
                        "analysis_year": args.analysis_year, "resolved_bazi_year": bazi_res["current_year"],
                        "source_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(list(HERE.glob("*.py")) + list((HERE / "astro_data").glob("*.json")) + list(ZIWEI_DIR.glob("*.ts")) + list((ZIWEI_DIR / "vendor").rglob("*.ts"))) if "node_modules" not in p.parts},
                        "ziwei_lock_sha256": hashlib.sha256((ZIWEI_DIR / "package-lock.json").read_bytes()).hexdigest(),
                        "conventions": "docs/time-contract.md; engine file headers; Qizheng ming-gong retains +08 clock"},
                    "time": {"civil": civil.isoformat(), "instant_bj": instant_bj.isoformat(),
                             "apparent_solar": apparent.isoformat(), "mean_solar": mean.isoformat(), "chart_clock": clock.isoformat(),
                             "iana_zone": args.timezone, "fold": civil.fold},
                    "scenarios": scenarios, "bazi_scenario_comparison": scenario_comparison,
                    "bazi": bazi_res, "bazi_core_reading": core_reading.analyze(bazi_res, temporal_uncertainty=bool(args.uncertainty_minutes)), "qizheng": qz_res, "qizheng_rule_reading": qz_reading, "qizheng_traditional_reading": qz_traditional, "qizheng_sensitivity": qz_comparison,
                    "ziwei": json.loads(ziwei_out) if ziwei_out else None,
                    "degradation": {"ziwei": ziwei_note}, "warnings": warnings}
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=encode_date, allow_nan=False))
        return

    out = []
    out.append("# 命盘数据（chart.md）")
    out.append("")
    out.append("> 本文件由 `scripts/build_chart.py` 生成（三引擎确定性排盘），存放于 `~/.claude/fortune-telling/chart.md`。")
    out.append("> 确定性字段以脚本输出为准；`<!-- agent: -->` 标记的判读字段由 agent 依脚本结果补全。")
    out.append("")
    out.append("## 基本信息")
    out.append("")
    out.append("| 项 | 值 | 备注 |")
    out.append("|----|----|------|")
    out.append("| 称呼 | %s | |" % (args.name or "（未提供）"))
    out.append("| 性别 | %s | 大运顺逆 + 十神感情映射必需 |" % args.sex)
    out.append("| 公历出生 | %s | 明确 UTC 偏移；IANA 解析仅在显式指定时启用 |" % civil.isoformat())
    out.append("| 真太阳时 | %s | 经度 %.2f |" % (
        apparent.isoformat(sep=" ", timespec="seconds"), args.lon))
    out.append("| 排盘钟面 | %s | %s；日时/紫微取整分钟，不四舍五入 |" % (clock.isoformat(sep=" ", timespec="seconds"), args.time_basis))
    out.append("| 时间口径 | 节气/起运/七政天体位置保留真实瞬间 | 七政立命宫仍用 +08 钟表时辰；未改变原学派规则 |")
    out.append("| 出生地 | %s | 纬 %.2f，经 %.2f |" % (args.place or "（未提供）", args.lat, args.lon))
    if args.analysis_year is not None:
        out.append("| 分析年份 | %d | 八字年度字段与紫微目标年统一；不是出生年份 |" % args.analysis_year)
    out.append("| 建档日期 | %s | |" % date.today().isoformat())
    out.append("| 数据来源 | 内置三引擎（八字 Meeus 定气 / 紫微 iztro / 七政 自研恒星制） | |")
    out.append("")
    if scenarios:
        out += ["## 时间误差候选（仅四柱与紫微输入）", "",
                "区间为已解析中心瞬间前后实际经过时间，端点包含。中心盘不是唯一候选。",
                "覆盖范围：" + scenarios["coverage"],
                "稳定字段：" + json.dumps(scenarios["stable_fields"], ensure_ascii=False),
                "变化字段：" + "、".join(scenarios["changing_fields"])]
        for index, variant in enumerate(scenarios["variants"], 1):
            out.append("- 候选 %d：%s；实际可达样本 UTC %s" % (index, json.dumps(variant["fields"], ensure_ascii=False), variant["witness_utc"]))
        out += scenario_reading.render(scenario_comparison)
        out.append("")
        out.append("以下三盘与大运数据为中心时刻；边界两侧的八字解释请以上述候选对照为准。")
    out += bazi_section(bazi_res, temporal_uncertainty=bool(args.uncertainty_minutes))
    out += ziwei_section(ziwei_out, ziwei_note)
    if qz_comparison:
        out += qizheng_sensitivity.render(qz_comparison, full_evidence=args.qizheng_sensitivity_evidence)
    out += qizheng_section(qz_res)
    out += ["", qz_rules.format_reading(qz_reading), ""]
    if args.qizheng_tradition:
        out += [qz_tradition.render(qz_traditional), ""]
    out += dayun_section(bazi_res)
    if warnings:
        out.append("## 警告")
        for w in warnings:
            out.append("- %s" % w)
        out.append("")
    out.append("## 解释器种子")
    out.append("")
    out.append("见 memory.md「运行时画像」。（agent 建档后按 SKILL.md §3 推导规则从上表提取写入 memory.md）")
    out.append("")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
