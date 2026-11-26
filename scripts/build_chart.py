#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建档总控：出生信息 → 三引擎 → chart.md 正文。

[来源] high-confidence-mingli-skill v4，2026-10-01。
调用本目录 pai_pan_bazi（八字）、pai_pan_qizheng（七政）与
scripts/pai_pan_ziwei/pai_pan.ts（紫微，需 node 环境，失败自动降级）。

【分工约定（S2）】确定性字段（四柱/藏干/十神/大运/紫微排布/七政位置/昼夜生）
= 脚本产出，禁止改动；结构判读（十神链/格局/调候/日主强弱）
= 结构版先列确定关系与未决前提，不自动判定格局成败或用神。

用法：
  python3 scripts/build_chart.py --solar 1990-05-15 --hour 14:00 --sex 男 \
      --lat 31.23 --lon 121.47 --place 上海 --name 某某
"""

import argparse
import json
import hashlib
import sys
from datetime import date, datetime
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pai_pan_bazi as bazi  # noqa: E402
import pai_pan_qizheng as qz  # noqa: E402
from ziwei_native import ZIWEI_DIR, run_ziwei
from time_scenarios import (
    UnsupportedUtcInterval, enumerate_scenarios, parse_birth_date, resolve_civil,
    solar_clock, timezone_provenance,
)


def parse_hour(text):
    hh, mm = (int(x) for x in text.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("--hour 需要 HH:MM")
    return hh, mm


def ziwei_scenario_comparison(scenarios, sex, name, place, analysis_year):
    """Replay enumerated Ziwei inputs for time-uncertainty comparison."""
    candidates = {}
    for number, variant in enumerate(scenarios["variants"], 1):
        fields = variant["fields"]
        identity = (fields["ziwei.solar_date"], fields["ziwei.shichen_index"], fields["ziwei.birth_year"])
        scenario_id = "candidate-%d" % number
        if identity in candidates:
            candidates[identity]["scenario_ids"].append(scenario_id)
            continue
        solar_date, shichen_index, birth_year = identity
        candidate = {
            "id": "ziwei-candidate-%d" % (len(candidates) + 1), "scenario_ids": [scenario_id],
            "witness_utc": variant["witness_utc"], "chart_clock": variant["chart_clock"],
            "input": {"solar_date": solar_date, "shichen_index": shichen_index, "birth_year": birth_year},
            "chart": None, "degradation": None,
        }
        candidates[identity] = candidate
        if analysis_year < birth_year:
            candidate["degradation"] = "分析年份 %d 早于该候选公历出生年 %d，未排紫微流年" % (analysis_year, birth_year)
            continue
        clock = datetime.fromisoformat(variant["chart_clock"])
        output, note = run_ziwei(clock.year, clock.month, clock.day, clock.hour, clock.minute,
                                 sex, name, place, analysis_year, birth_year, output_format="json")
        candidate["degradation"] = note
        if output is None:
            continue
        candidate["chart"] = json.loads(output)["chart"]
    return {
        "scope": "candidate_charts", "coverage": scenarios["coverage"],
        "analysis_year": analysis_year, "candidates": list(candidates.values()),
    }


def true_solar_time_text(hh, mm, lon, eot_minutes):
    """Legacy display helper; use floor via datetime for negative clock hours."""
    if lon is None:
        return "未校正（缺经度）"
    civil = datetime(2000, 1, 2, hh, mm, tzinfo=bazi.BJ)
    clock = solar_clock(civil, lon, eot_minutes)
    return clock.strftime("%H:%M") + "（当地真太阳时；均时差 %+.0f 分）" % eot_minutes


def bazi_section(bazi_res, temporal_uncertainty=False):
    p = bazi_res["pillars"]
    day_gan, day_zhi, _, _ = p["day"]
    lines = [
        "## 八字",
        "",
        "- 公历：%s｜农历：%s｜真太阳/排盘：%s｜节气：%s" % (
            bazi_res.get("solar_text", ""), bazi_res.get("lunar_text", ""),
            bazi_res.get("shichen_text", ""), bazi_res.get("jie_name", "")),
        "- 日主：**%s**（月令：%s%s；%s）" % (
            day_gan, p["month"][0], p["month"][1],
            "时辰未知，时柱待定" if temporal_uncertainty or bazi_res.get("hour_unknown") else "四柱完整"),
        "",
        "| 柱 | 干支 | 十神 | 藏干 | 备注 |",
        "|----|------|------|------|------|",
    ]
    labels = ("年", "月", "日", "时")
    for i, key in enumerate(("year", "month", "day", "hour")):
        gan, zhi, shishen, canggan = p[key]
        note = "时间不确定时标注置信度" if key == "hour" and gan == "未知" else ""
        lines.append("| %s | %s%s | %s | %s | %s |" % (labels[i], gan, zhi, shishen, canggan, note))
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


def qizheng_section(qz_res, *, show_degree_relations=True):
    lines = ["## 七政四余", ""]
    profile = qz_res.get("calculation_profile", "unspecified")
    lines.append("计算配置：%s。" % profile)
    if profile == "legacy-v1":
        lines.append("下列数值仅用于旧版复现。旧算法的升点及昼夜计算存在已知错误。")
    elif profile == "calibrated-v3":
        lines.append("已启用 SIMBAD 28 宿逐星实时岁差校准、十二次分野同步宫界与 VSOP87 太阳星历（角宿一=0°，紫气沿用 1975-03-13 28 年通用锚点）。")
    if qz_res["day_night"] is None:
        lines.append("**命度**：缺经纬度，未计算。")
    elif qz_res["ming_du"] is None:
        lines.append("**命度**：东方上升交点未定义；恩用难仇不计算。")
    else:
        lines.append("**命度**：%s宿%.2f度（宿主：%s，度主五行：%s，距星 %s，所在 %s宫）" % (
            qz_res["ming_du"]["mansion"], qz_res["ming_du"]["mansion_deg"],
            qz_res["ming_du"]["wuxing"], qz_res["du_zhu_wuxing"], qz_res["ming_du"]["star"],
            qz_res["ming_du"].get("palace") or qz.palace_of(qz_res["ming_du"]["sidereal"])))
    lines.append("**躔**：十一曜恒星黄经躔宿躔宫与状态见下表")
    lines.append("")
    star_states = qz_res.get("star_states") or {}
    if star_states:
        lines.append("| 星 | 黄道经度 | 恒星黄经 | 躔宿 | 入宿度 | 宿主 | 躔宫 | 状态（升殿/喜宫/明晦） |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for name in qz.LUMINARIES:
            b = qz_res["bodies"][name]
            st = star_states.get(name, {})
            tags = []
            if st.get("shengdian"):
                tags.append("升殿")
            if st.get("xigong_relation"):
                tags.append(st["xigong_relation"])
            if st.get("ru_miao"):
                tags.append("入庙")
            if st.get("shixian"):
                tags.append(st["shixian"])
            if st.get("ming_hui"):
                tags.append(st["ming_hui"])
            lines.append("| %s | %.4f | %.4f | %s宿 | %.2f | %s | %s宫 | %s |" % (
                name, b["tropical"], b["sidereal"], b["mansion"], b["mansion_deg"],
                b["mansion_wx"], b.get("palace") or qz.palace_of(b["sidereal"]),
                "·".join(tags) or "—",
            ))
    else:
        lines.append("| 星 | 黄道经度 | 恒星黄经 | 躔宿 | 入宿度 | 宿主 | 躔宫 |")
        lines.append("|---|---|---|---|---|---|---|")
        for name in qz.LUMINARIES:
            b = qz_res["bodies"][name]
            lines.append("| %s | %.4f | %.4f | %s宿 | %.2f | %s | %s宫 |" % (
                name, b["tropical"], b["sidereal"], b["mansion"], b["mansion_deg"],
                b["mansion_wx"], b.get("palace") or qz.palace_of(b["sidereal"])))
    lines.append("")
    dn = qz_res["day_night"]
    if dn is None:
        lines.append("**昼生/夜生**：缺经纬度，未计算。")
    elif "solar_altitude_deg" in dn:
        lines.append("**昼生/夜生**：%s（太阳中心几何高度 %.4f°；阈值 %.3f°，非实测日出日落）" % (dn["type"], dn["solar_altitude_deg"], dn["threshold_deg"]))
    elif dn["type"] in ("极昼", "极夜"):
        lines.append("**昼生/夜生**：%s（%s）" % (dn["type"], dn.get("note", "")))
    else:
        lines.append("**昼生/夜生**：%s（日出 %.1f 时 / 日落 %.1f 时，当地平太阳时）" % (
            dn["type"], dn["sunrise_local"], dn["sunset_local"]))
    mg = qz_res["ming_gong"]
    if mg is None:
        lines.append("**立命宫**：缺经纬度，未计算。")
    else:
        ruler_txt = ("，宫主 %s/%s" % (mg["ruler"], mg["ruler_wuxing"])) if mg.get("ruler") else ""
        lines.append("**立命宫**：%s宫（支五行 %s%s；果老安命法：太阳 %s 宫 + %s 时顺数至卯）" % (
            mg["zhi"], mg["wuxing"], ruler_txt, mg["sun_palace"], mg["hour_zhi"]))
    sg = qz_res.get("shen_gong")
    if sg:
        sd = sg["shen_du"]
        house_txt = ("，落%s" % sg["house_name"]) if sg.get("house_name") else ""
        lines.append("**身宫/身主**：%s宫（身主 %s/%s%s；身度 %s宿%.2f度，度主 %s）" % (
            sg["zhi"], sg["shen_zhu"], sg["shen_zhu_wuxing"], house_txt,
            sd["mansion"], sd["mansion_deg"], sd["du_zhu_wuxing"]))
    lines.append("")
    if qz_res.get("en_yong") is not None and show_degree_relations:
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
        lines.append("")
    bs = qz_res.get("bianyao_shensha")
    if bs:
        ps = bs["palace_shensha"]
        ren_key = "阳刃" if "阳刃" in ps else "阴刃"
        by_pairs = "、".join("%s=%s(%s)" % (r, i["star"], i["palace"] or "—") for r, i in bs["bianyao"].items())
        lines.append("**年干变曜（%s年 · 果老卷二）**：%s" % (bs["year_gz"], by_pairs))
        ss = bs["stem_stars"]
        lines.append("**年干支核心神煞**：科名=%s、科甲=%s、文星=%s、官星=%s、印星=%s、天乙=%s、玉堂=%s、文昌=%s、禄勋=%s、%s=%s、唐符=%s、国印=%s、劫杀=%s、亡神=%s、红鸾=%s、空亡=%s" % (
            ss["科名"]["star"], ss["科甲"]["star"] or "—", ss["文星"]["star"], ss["官星"]["star"], ss["印星"]["star"],
            ps["天乙昼贵"], ps["玉堂夜贵"], ps["文昌"], ps["禄勋"], ren_key, ps[ren_key],
            ps["唐符飞刃"], ps["国印"], ps["劫杀"], ps["亡神"], bs["jiahou"]["红鸾"], "".join(ps["空亡"]),
        ))
        lines.append("")
    dw = qz_res.get("dongwei_daxian")
    if dw:
        lines.append("**洞微大限（出童限 %.2f 岁 / %s）**：" % (dw["chutongxian_age"], dw["chutongxian_date"]))
        lines.append("")
        lines.append("| 序 | 限宫 | 支宫 | 限主 | 岁数窗 | 公历窗 | 宿度 |")
        lines.append("|----|------|------|------|--------|--------|------|")
        active_step = dw["active"]["palace_limit"]["step"] if dw.get("active") else None
        for st in dw["stages"]:
            mark = " ←目标" if st["step"] == active_step else ""
            lines.append("| %d | %s%s | %s | %s(%s) | %.1f~%.1f | %s~%s | %s |" % (
                st["step"], st["house_name"], mark, st["zhi"], st["ruler"], st["ruler_wuxing"],
                st["start_age"], st["end_age"], st["start_date"], st["end_date"],
                "→".join(st["mansions_traversed"]),
            ))
        if dw.get("active"):
            act = dw["active"]
            pl, dl, xx = act["palace_limit"], act["degree_limit"], act["xiaoxian"]
            lines.append("")
            tongxian_txt = ("｜童限行%s" % act["tongxian_house"]) if act["in_tongxian"] else ""
            cycle_txt = (
                "｜第 %d 周回绕（%.1f~%.1f岁 / %s~%s）"
                % (act["cycle_index"] + 1, pl["start_age"], pl["end_age"], pl["start_date"], pl["end_date"])
                if act.get("cycle_index", 0) > 0
                else ""
            )
            lines.append("- 目标年限度（%s）：限宫 %s(%s)｜限度 %s宿%.2f°(%s·%s)｜小限 %s(%s)%s%s" % (
                act["target_bj"][:10], pl["house_name"], pl["zhi"],
                dl["mansion"], dl["mansion_deg"], dl["du_zhu_wuxing"],
                dl["relation_to_natal_duzhu"] or "—", xx["house_name"], xx["zhi"], tongxian_txt, cycle_txt,
            ))
            if act["risk_signals"]:
                lines.append("- 行限提示：" + "；".join(act["risk_signals"]))
        ov = qz_res.get("dynamic_overview")
        if ov and ov.get("taisui_alerts"):
            lines.append("- 流年太岁（%s年）：%s" % (ov["year_gz"]["year_gz"], "；".join(ov["taisui_alerts"])))
    return lines


def dayun_section(bazi_res, *, center_only=False):
    lines = ["## 大运表", ""]
    if center_only:
        lines.append("- 下表按中心时刻计算。")
    lines += ["- 方向：%s｜起运：%s" % (
        "顺排" if bazi_res["forward"] else "逆排", bazi_res["qiyun_text"]),
        bazi.dayun_age_note(bazi_res), ""]
    lines += bazi.render_dayun_age_windows(
        bazi_res["dayun_age_windows"]["windows"], bazi_res["dayun_rows"])
    lines.append("")
    lines.append("<!-- 紫微大限列：可由 agent 从紫微 stdout 的「大限」节补入（可缺） -->")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="三引擎建档 → chart.md 正文")
    parser.add_argument("--solar", required=True, help="公历 YYYY-MM-DD")
    parser.add_argument("--hour", required=True, help="HH:MM（民用钟表，UTC 偏移默认 +08）")
    parser.add_argument("--sex", required=True, choices=("男", "女"))
    parser.add_argument("--lat", type=float, help="纬度（北正，七政命度及昼夜等需经纬度）")
    parser.add_argument("--lon", type=float, help="经度（东正，太阳时及七政地平计算需要）")
    parser.add_argument("--qizheng-profile", choices=("calibrated-v3", "legacy-v1"), default="calibrated-v3")
    parser.add_argument("--dut1-seconds", type=float, default=0.0, help="七政及真太阳钟面的 UT1−UTC 秒，默认 0 为近似")
    parser.add_argument("--place", help="出生地")
    parser.add_argument("--name", help="称呼")
    parser.add_argument("--time-basis", choices=("civil", "mean-solar", "apparent-solar"), default="civil",
                        help="八字日时柱/紫微钟面，默认 civil 保持兼容")
    zone_group = parser.add_mutually_exclusive_group()
    zone_group.add_argument("--timezone", help="IANA 时区，例如 Asia/Shanghai；需要 Python 3.9+ 和时区数据库")
    parser.add_argument("--fold", type=int, choices=(0, 1), help="重复民用时间：0 较早，1 较晚；不默认选择")
    parser.add_argument("--enumerate-scenarios", action="store_true", help="枚举四柱与紫微离散输入，±120 分钟内；apparent-solar 仅数值候选，不证明穷尽")
    zone_group.add_argument("--utc-offset", type=float, default=8, help="出生钟表的固定 UTC 偏移小时；默认 +08，不自动推断历史夏令时")
    parser.add_argument("--uncertainty-minutes", type=float, default=0, help="出生时刻正负误差分钟；未开启枚举时仅为中心候选")
    parser.add_argument("--age-year", type=int, help="紫微目标年份（默认当年）")
    parser.add_argument("--analysis-year", type=int, help="显式统一八字年度字段与紫微目标年；不指定时保留旧行为")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="输出到标准输出，默认文本")
    parser.add_argument("--explain-rules", action="store_true", help="展开紫微内置格局匹配条件")
    args = parser.parse_args(argv)
    scenarios = None
    comparison_degradation = {}

    try:
        birthday = parse_birth_date(args.solar)
        y, m, d = birthday.year, birthday.month, birthday.day
        hh, mm = parse_hour(args.hour)
        if not all(math.isfinite(x) for x in (args.lat, args.lon, args.utc_offset, args.uncertainty_minutes)
                   if x is not None):
            raise ValueError("坐标、UTC 偏移和误差必须为有限数值")
        if ((args.lat is not None and not -90 <= args.lat <= 90) or
                (args.lon is not None and not -180 <= args.lon <= 180)):
            raise ValueError("纬度/经度超出范围")
        if args.time_basis != "civil" and args.lon is None:
            raise ValueError("平太阳时或真太阳时需要出生地经度 --lon")
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
        qz_target_year = args.analysis_year if args.analysis_year is not None else args.age_year
        qz_res, qz_warnings = qz.compute(
            (instant_bj.year, instant_bj.month, instant_bj.day), instant_bj.hour,
            instant_bj.minute, args.lat, args.lon, args.place, birth_instant=civil,
            profile=args.qizheng_profile, dut1_seconds=args.dut1_seconds,
            analysis_year=qz_target_year)
        apparent = solar_clock(civil, args.lon, qz_res["eot_minutes"]) if args.lon is not None else None
        mean = solar_clock(civil, args.lon, 0) if args.lon is not None else None
        clock = {"apparent-solar": apparent, "mean-solar": mean, "civil": civil.replace(tzinfo=None)}[args.time_basis]
        if args.enumerate_scenarios:
            try:
                scenario_now = datetime(args.analysis_year, 1, 1, tzinfo=bazi.BJ) if args.analysis_year else None
                scenarios = enumerate_scenarios(civil, args.uncertainty_minutes, args.time_basis, args.lon,
                                                args.sex, scenario_now, dut1_seconds=args.dut1_seconds)
            except UnsupportedUtcInterval as exc:
                comparison_degradation["scenarios"] = "未执行出生时刻候选枚举：" + str(exc)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
        return 2

    target_year = args.analysis_year if args.analysis_year is not None else args.age_year
    resolved_age_year = target_year if target_year is not None else date.today().year
    bazi_res = bazi.compute(
        solar_date=clock.date(), hour=clock.hour, minute=clock.minute,
        sex=args.sex, place=args.place, birth_instant=civil,
        **({"now": datetime(args.analysis_year, 1, 1, tzinfo=bazi.BJ)} if args.analysis_year is not None else {}))
    ziwei_out, ziwei_note = run_ziwei(
        clock.year, clock.month, clock.day, clock.hour, clock.minute,
        args.sex, args.name, args.place, resolved_age_year, civil.year,
        **({"output_format": "json"} if args.format == "json" else {}),
        **({"explain_rules": True} if args.explain_rules else {}),
        **({"temporal_uncertainty": True} if args.uncertainty_minutes else {}))
    warnings = list(dict.fromkeys(bazi_res["warnings"] + qz_warnings))
    warnings.extend(comparison_degradation.values())
    if clock.date() != civil.date():
        warnings.append("排盘钟面跨公历日期；八字日柱仍按原引擎 23:00 换日规则。")
    if args.uncertainty_minutes and not scenarios:
        warnings.append("出生时刻误差 ±%g 分钟：本盘仅中心时刻候选，未穷举误差区间；不得作为唯一确定命盘。" % args.uncertainty_minutes)
    if scenarios:
        warnings.append("误差范围比较四柱、紫微离散输入和八字折月起运；未覆盖七政、完整紫微或天文算法误差。晚子时仍沿用各引擎不同约定。")
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
                    "provenance": {"resolved_age_year": resolved_age_year,
                        "timezone_source": timezone_provenance(args.timezone),
                        "analysis_year": args.analysis_year, "resolved_bazi_year": bazi_res["current_year"],
                        "source_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(list(HERE.glob("*.py")) + list((HERE / "astro_data").glob("*.json")) + list(ZIWEI_DIR.glob("*.ts")) + list((ZIWEI_DIR / "vendor").rglob("*.ts"))) if "node_modules" not in p.parts},
                        "ziwei_lock_sha256": hashlib.sha256((ZIWEI_DIR / "package-lock.json").read_bytes()).hexdigest(),
                        "conventions": "docs/time-contract.md; engine file headers; Qizheng ming-gong retains +08 clock"},
                    "time": {"civil": civil.isoformat(), "instant_bj": instant_bj.isoformat(),
                             "apparent_solar": apparent.isoformat() if apparent is not None else None,
                             "mean_solar": mean.isoformat() if mean is not None else None, "chart_clock": clock.isoformat(),
                             "iana_zone": args.timezone, "fold": civil.fold},
                    "scenarios": scenarios,
                    "bazi": bazi_res, "qizheng": qz_res,
                    "ziwei": json.loads(ziwei_out) if ziwei_out else None,
                    "degradation": {"ziwei": ziwei_note, **comparison_degradation}, "warnings": warnings}
        if scenarios and args.uncertainty_minutes:
            snapshot["ziwei_scenario_comparison"] = ziwei_scenario_comparison(
                scenarios, args.sex, args.name, args.place, resolved_age_year)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=encode_date, allow_nan=False))
        return

    out = []
    out.append("# 命盘数据（chart.md）")
    out.append("")
    out.append("> 由 `scripts/build_chart.py` 将三引擎盘面输出到标准输出。")
    out.append("> 盘面字段以引擎输出为准。解释及其条件、反证和未决项见本次分析记录。")
    out.append("")
    out.append("## 基本信息")
    out.append("")
    out.append("| 项 | 值 | 备注 |")
    out.append("|----|----|------|")
    out.append("| 称呼 | %s | |" % (args.name or "（未提供）"))
    out.append("| 性别 | %s | 大运顺逆 + 十神感情映射必需 |" % args.sex)
    out.append("| 公历出生 | %s | 明确 UTC 偏移；IANA 解析仅在显式指定时启用 |" % civil.isoformat())
    if apparent is None:
        out.append("| 真太阳时 | 未计算 | 出生地经度未提供 |")
    else:
        out.append("| 真太阳时 | %s | 经度 %.2f |" % (
            apparent.isoformat(sep=" ", timespec="seconds"), args.lon))
    out.append("| 排盘钟面 | %s | %s；日时/紫微取整分钟，不四舍五入 |" % (clock.isoformat(sep=" ", timespec="seconds"), args.time_basis))
    out.append("| 时间口径 | 节气/起运/七政天体位置保留真实瞬间 | 七政立命宫仍用 +08 钟表时辰；未改变原学派规则 |")
    latitude = "纬 %.2f" % args.lat if args.lat is not None else "纬度未提供"
    longitude = "经 %.2f" % args.lon if args.lon is not None else "经度未提供"
    out.append("| 出生地 | %s | %s，%s |" % (args.place or "（未提供）", latitude, longitude))
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
        out += ["", "### 出生误差下的八字折月起运", "",
                "各表按原折月年龄选运，左含右不含。公历交运日期另核。"]
        if scenarios["coverage"] == "numerical_witnesses_not_exhaustive":
            out.append("真太阳时的四柱与折月窗仅按下列已找到的数值见证配对。")
        for row in scenarios["dayun_age_comparison"]["segments"]:
            years, months = divmod(row["start_age_months"], 12)
            end_mark = "]" if row["end_inclusive"] else ")"
            out.append("- 起运 %d 岁 %d 个月（%s）。出生 UTC [%s, %s%s" % (
                years, months, "顺排" if row["forward"] else "逆排",
                row["start_utc"], row["end_utc"], end_mark))
            witnesses = "、".join(
                "%s @ UTC %s" % (witness["scenario_id"], witness["witness_utc"])
                for witness in row["birth_witnesses"])
            out += ["- 四柱见证：" + witnesses, ""]
            out += bazi.render_dayun_age_windows(row["age_windows"])
            out.append("")
        out.append("")
        if args.uncertainty_minutes:
            out.append("以下三盘与大运数据为中心时刻；边界两侧的八字解释请以上述候选对照为准。")
    out += bazi_section(bazi_res, temporal_uncertainty=bool(args.uncertainty_minutes))
    out += ziwei_section(ziwei_out, ziwei_note)
    out += qizheng_section(qz_res, show_degree_relations=(qz_res.get("en_yong") is not None))
    out.append("")
    out += dayun_section(bazi_res, center_only=bool(args.uncertainty_minutes))
    if warnings:
        out.append("## 警告")
        for w in warnings:
            out.append("- %s" % w)
        out.append("")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
