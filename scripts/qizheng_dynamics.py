"""Qizheng Siyu dynamic luck & transit engine: 洞微大限 (宫限+度限), 小限/童限, 流年/流月/流日过宫.

Classical basis:
- 《张果星宗》卷三「定行限度法」& 卷十六「洞微百六限说」「限步之说」「限度主论」
- 《星学大成》「起大限【琴堂洞微皆同】」「起小限」
- 《张果星宗》卷十七「流年论」「太岁轮宫十二神煞」

Pure Python stdlib; zero third-party dependencies.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any

import pai_pan_qizheng as qz
import qizheng_rules as qr

TROPICAL_YEAR_DAYS = 365.242189

DONGWEI_SEQUENCE: tuple[tuple[str, float], ...] = (
    ("命宫", 15.0),
    ("相貌", 10.0),
    ("福德", 11.0),
    ("官禄", 15.0),
    ("迁移", 8.0),
    ("疾厄", 7.0),
    ("妻妾", 11.0),
    ("奴仆", 4.5),
    ("男女", 4.5),
    ("田宅", 4.5),
    ("兄弟", 5.0),
    ("财帛", 5.0),
)

# 童限十岁前逐年行宫（传统口诀：一命二财三疾四妻五福六官七相八迁九奴，十岁上本生度起行）
TONGXIAN_HOUSES: tuple[str, ...] = (
    "命宫", "财帛", "疾厄", "妻妾", "福德", "官禄", "相貌", "迁移", "奴仆", "命宫"
)

# 《张果星宗》卷十七「流年论」太岁轮宫十二神煞
TAISUI_12_LABELS: tuple[str, ...] = (
    "太岁", "天空", "丧门", "勾神", "官符", "死符",
    "岁破", "暴败", "白虎", "天德", "吊客", "病符",
)

PALACE_INGRESS_STEP_HOURS: dict[str, float] = {
    "月": 2.0,
    "日": 12.0,
    "水": 6.0,
    "金": 12.0,
    "火": 24.0,
    "木": 48.0,
    "土": 48.0,
    "罗睺": 48.0,
    "计都": 48.0,
    "月孛": 48.0,
    "紫气": 48.0,
}

# Moon traverses narrowest mansion 觜 (1.075°) in ~1.7h; 0.5h step prevents skipping across 觜.
MANSION_INGRESS_STEP_HOURS: dict[str, float] = {
    "月": 0.5,
    "日": 6.0,
}


def _add_years(dt_bj: datetime, years: float) -> datetime:
    return dt_bj + timedelta(days=years * TROPICAL_YEAR_DAYS)


def _completed_birthday_years(birth_dt_bj: datetime, target_dt_bj: datetime) -> int:
    had_birthday = (
        target_dt_bj.month, target_dt_bj.day, target_dt_bj.hour, target_dt_bj.minute, target_dt_bj.second
    ) >= (
        birth_dt_bj.month, birth_dt_bj.day, birth_dt_bj.hour, birth_dt_bj.minute, birth_dt_bj.second
    )
    return target_dt_bj.year - birth_dt_bj.year - (0 if had_birthday else 1)


def _wx_relation(target_wx: str | None, self_wx: str | None) -> str | None:
    if not target_wx or not self_wx:
        return None
    if target_wx == self_wx:
        return "同"
    if qr.WUXING_SHENG[target_wx] == self_wx:
        return "恩（生我）"
    if qr.WUXING_SHENG[self_wx] == target_wx:
        return "用（我生）"
    if qr.WUXING_KE[target_wx] == self_wx:
        return "难（克我）"
    return "仇（我克）"


def _mansions_in_span_descending(lo: float, hi: float, mansions) -> list[str]:
    """Return mansions overlapping [lo, hi) ordered along decreasing sidereal longitude (Dongwei traversal)."""
    names = []
    for row in mansions:
        s = row[2]
        w = row[5] if len(row) > 5 else 10.0
        e = s + w
        if e > lo + 1e-6 and s < hi - 1e-6:
            names.append(row[0])
    names.reverse()
    return names


def compute_dongwei_daxian(
    birth_dt_bj: datetime,
    natal_res: dict[str, Any],
    target_dt_bj: datetime | None = None,
) -> dict[str, Any] | None:
    """Compute full 12-stage Dongwei Daxian (出童限折算法) + exact degree limit at target_dt_bj.

    Returns None if ming_gong is absent (missing lat/lon).
    """
    mg = natal_res.get("ming_gong")
    if not mg:
        return None
    profile = natal_res.get("calculation_profile", "calibrated-v3")
    jd_tt = natal_res["jd_tt"]
    epoch_mansions = qz.mansions_for_epoch(jd_tt, profile=profile)
    epoch_palaces = qz.palaces_for_epoch(jd_tt, profile=profile)

    sun_body = natal_res["bodies"]["日"]
    sun_palace = sun_body["palace"]
    sun_lo, sun_hi = epoch_palaces[sun_palace]
    sun_span = sun_hi - sun_lo
    sun_frac = max(0.0, min(1.0, (sun_body["sidereal"] - sun_lo) / sun_span))
    # 《星学大成》起大限：三度起一岁，太阳宫中度(15°/30°)对应命宫15年 → 10 + (sun_frac * 30)/3
    sun_norm_deg = sun_frac * 30.0
    ming_years = round(10.0 + sun_norm_deg / 3.0, 6)

    ming_zhi = mg["zhi"]
    ming_idx = qr.ZHI.index(ming_zhi)
    ming_lo, ming_hi = epoch_palaces[ming_zhi]
    # 量天尺对度：按太阳在太阳宫的相对比例定立命宫本生起点（向相貌宫低黄经界退行）
    natal_scale_sid = ming_lo + sun_frac * (ming_hi - ming_lo)
    scale_mansion, scale_mdeg, scale_mwx, scale_star = qz.mansion_of(natal_scale_sid, mansions=epoch_mansions)

    stages: list[dict[str, Any]] = []
    cursor_age = 0.0
    for step, (house_name, default_yrs) in enumerate(DONGWEI_SEQUENCE):
        dur = ming_years if step == 0 else default_yrs
        zhi = qr.ZHI[(ming_idx + step) % 12]
        lo, hi = epoch_palaces[zhi]
        start_sid = natal_scale_sid if step == 0 else hi
        end_sid = lo
        span_deg = start_sid - end_sid
        active_span_years = (dur - 10.0) if step == 0 else dur
        deg_per_yr = (span_deg / active_span_years) if active_span_years > 1e-9 else 0.0
        stages.append({
            "step": step + 1,
            "house_name": house_name,
            "zhi": zhi,
            "constellation": qr.PALACE_CONSTELLATION[zhi],
            "ruler": qr.PALACE_RULER[zhi],
            "ruler_wuxing": qr.PALACE_RULER_WUXING[zhi],
            "duration_years": round(dur, 4),
            "start_age": round(cursor_age, 4),
            "end_age": round(cursor_age + dur, 4),
            "start_date": _add_years(birth_dt_bj, cursor_age).date().isoformat(),
            "end_date": _add_years(birth_dt_bj, cursor_age + dur).date().isoformat(),
            "start_sidereal": round(start_sid, 4),
            "end_sidereal": round(end_sid, 4),
            "deg_per_year": round(deg_per_yr, 4),
            "mansions_traversed": _mansions_in_span_descending(end_sid, start_sid, epoch_mansions),
        })
        cursor_age += dur

    out: dict[str, Any] = {
        "method": "dongwei-bailiu-solar-degree-v3",
        "formula_note": "《星学大成》出童限折算法：命宫时长=10+(太阳入宫归一化度/3)，范围[10,20]年；余十一宫按10/11/15/8/7/11/4.5/4.5/4.5/5/5年顺地支(逆黄经)行宫度",
        "sun_in_palace_norm_deg": round(sun_norm_deg, 4),
        "ming_gong_years": round(ming_years, 4),
        "chutongxian_age": round(ming_years, 4),
        "chutongxian_date": _add_years(birth_dt_bj, ming_years).date().isoformat(),
        "total_cycle_years": round(cursor_age, 4),
        "liangtianchi_start": {
            "sidereal": round(natal_scale_sid, 4),
            "mansion": scale_mansion,
            "mansion_deg": round(scale_mdeg, 2),
            "mansion_wx": scale_mwx,
            "du_zhu_wuxing": qr.MANSION_WX_TO_PHASE[scale_mwx],
            "star": scale_star,
        },
        "stages": stages,
        "active": None,
    }

    if target_dt_bj is not None:
        out["active"] = evaluate_dongwei_at(birth_dt_bj, target_dt_bj, natal_res, out)
    return out


def evaluate_dongwei_at(
    birth_dt_bj: datetime,
    target_dt_bj: datetime,
    natal_res: dict[str, Any],
    dongwei: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate exact palace-limit (限宫), degree-limit (限度), 童限/小限, and 倒限 risks at target_dt_bj."""
    elapsed_days = (target_dt_bj - birth_dt_bj).total_seconds() / 86400.0
    age_exact = elapsed_days / TROPICAL_YEAR_DAYS
    if age_exact < 0:
        raise ValueError("目标时刻早于出生时刻，无法推算洞微大限")

    profile = natal_res.get("calculation_profile", "calibrated-v3")
    epoch_mansions = qz.mansions_for_epoch(natal_res["jd_tt"], profile=profile)
    natal_du_wx = natal_res.get("du_zhu_wuxing")
    stages = dongwei["stages"]
    total_years = dongwei["total_cycle_years"]
    cycle_index = int(age_exact // total_years)
    cycle_age = age_exact % total_years

    active_stage = stages[-1]
    for st in stages:
        if st["start_age"] <= cycle_age < st["end_age"]:
            active_stage = st
            break

    in_tongxian = age_exact < 10.0
    if active_stage["step"] == 1:
        if in_tongxian:
            limit_sid = active_stage["start_sidereal"]
        elif cycle_index == 0:
            frac_in_active = max(0.0, min(1.0, (cycle_age - 10.0) / max(1e-9, active_stage["duration_years"] - 10.0)))
            limit_sid = active_stage["start_sidereal"] - frac_in_active * (
                active_stage["start_sidereal"] - active_stage["end_sidereal"]
            )
        else:
            frac_in_cycle2 = max(0.0, min(1.0, cycle_age / active_stage["duration_years"]))
            limit_sid = active_stage["start_sidereal"] - frac_in_cycle2 * (
                active_stage["start_sidereal"] - active_stage["end_sidereal"]
            )
    else:
        frac_in_stage = max(0.0, min(1.0, (cycle_age - active_stage["start_age"]) / active_stage["duration_years"]))
        limit_sid = active_stage["start_sidereal"] - frac_in_stage * (
            active_stage["start_sidereal"] - active_stage["end_sidereal"]
        )
    limit_sid = qz.norm_deg(limit_sid)
    lm_name, lm_deg, lm_wx, lm_star = qz.mansion_of(limit_sid, mansions=epoch_mansions)
    lm_phase = qr.MANSION_WX_TO_PHASE[lm_wx]

    completed_years = _completed_birthday_years(birth_dt_bj, target_dt_bj)
    nominal_age_birthday = completed_years + 1
    ming_idx = qr.ZHI.index(natal_res["ming_gong"]["zhi"])
    xiaoxian_zhi = qr.ZHI[(ming_idx - completed_years) % 12]
    xiaoxian_house = qr.TWELVE_HOUSES[completed_years % 12]

    tongxian_house = TONGXIAN_HOUSES[min(max(completed_years, 0), 9)] if in_tongxian else None

    risk_signals: list[str] = []
    limit_palace_rel = _wx_relation(active_stage["ruler_wuxing"], natal_du_wx)
    limit_du_rel = _wx_relation(lm_phase, natal_du_wx)
    if limit_du_rel == "难（克我）":
        risk_signals.append(f"限度主({lm_name}宿·{lm_phase})克命度主({natal_du_wx})，行难度须防阻力与承压")
    if limit_palace_rel == "难（克我）":
        risk_signals.append(f"限宫主({active_stage['ruler']}·{active_stage['ruler_wuxing']})克命度主({natal_du_wx})")

    bs = natal_res.get("bianyao_shensha") or {}
    ps = bs.get("palace_shensha") or {}
    ren_key = "阳刃" if "阳刃" in ps else "阴刃"
    if ps.get(ren_key) == active_stage["zhi"]:
        risk_signals.append(f"大限宫({active_stage['zhi']})临本命{ren_key}，卷十七提醒防刚猛冲克")
    for sha_name in ("劫杀", "亡神", "大耗岁破", "天雄白虎", "地雌丧门"):
        if ps.get(sha_name) == active_stage["zhi"]:
            risk_signals.append(f"大限宫({active_stage['zhi']})会本命{sha_name}")
    if active_stage["zhi"] in (ps.get("空亡") or []):
        risk_signals.append(f"大限宫({active_stage['zhi']})入本命旬空")

    en_yong = natal_res.get("en_yong") or {}
    nan_stars = set(en_yong.get("难", []))
    opp_zhi = qr.ZHI[(qr.ZHI.index(active_stage["zhi"]) + 6) % 12]
    for s in nan_stars:
        b = natal_res["bodies"].get(s)
        if not b:
            continue
        if b["palace"] == active_stage["zhi"]:
            risk_signals.append(f"原盘难星「{s}」守当前大限{active_stage['house_name']}({active_stage['zhi']}宫)")
        elif b["palace"] == opp_zhi:
            risk_signals.append(f"原盘难星「{s}」居对宫({opp_zhi})冲当前大限{active_stage['house_name']}")

    if cycle_index == 0:
        stage_start_age = active_stage["start_age"]
        stage_end_age = active_stage["end_age"]
        stage_start_date = active_stage["start_date"]
        stage_end_date = active_stage["end_date"]
    else:
        cycle_offset = cycle_index * total_years
        stage_start_age = round(active_stage["start_age"] + cycle_offset, 4)
        stage_end_age = round(active_stage["end_age"] + cycle_offset, 4)
        stage_start_date = (birth_dt_bj + timedelta(days=stage_start_age * TROPICAL_YEAR_DAYS)).date().isoformat()
        stage_end_date = (birth_dt_bj + timedelta(days=stage_end_age * TROPICAL_YEAR_DAYS)).date().isoformat()

    return {
        "target_bj": target_dt_bj.isoformat(),
        "exact_age_years": round(age_exact, 4),
        "nominal_age_birthday_rule": nominal_age_birthday,
        "cycle_index": cycle_index,
        "in_tongxian": in_tongxian,
        "tongxian_house": tongxian_house,
        "palace_limit": {
            "step": active_stage["step"],
            "house_name": active_stage["house_name"],
            "zhi": active_stage["zhi"],
            "constellation": active_stage["constellation"],
            "ruler": active_stage["ruler"],
            "ruler_wuxing": active_stage["ruler_wuxing"],
            "relation_to_natal_duzhu": limit_palace_rel,
            "start_age": stage_start_age,
            "end_age": stage_end_age,
            "start_date": stage_start_date,
            "end_date": stage_end_date,
        },
        "degree_limit": {
            "sidereal": round(limit_sid, 4),
            "mansion": lm_name,
            "mansion_deg": round(lm_deg, 2),
            "mansion_wx": lm_wx,
            "du_zhu_wuxing": lm_phase,
            "star": lm_star,
            "relation_to_natal_duzhu": limit_du_rel,
        },
        "xiaoxian": {
            "rule": "《星学大成》生日后交过宫，1岁在命宫逆地支行",
            "nominal_age": nominal_age_birthday,
            "zhi": xiaoxian_zhi,
            "house_name": xiaoxian_house,
            "ruler": qr.PALACE_RULER[xiaoxian_zhi],
            "ruler_wuxing": qr.PALACE_RULER_WUXING[xiaoxian_zhi],
        },
        "risk_signals": risk_signals,
    }


def _body_sidereal_at(dt_bj: datetime, body_name: str, profile: str = "calibrated-v3") -> tuple[float, str, str, float]:
    """Fast single-body sidereal longitude, palace, mansion, mansion_deg at dt_bj."""
    dt_utc = dt_bj.astimezone(timezone.utc)
    jd_ut = qz.jd_from_utc(dt_utc)
    jd_tt = jd_ut + qz.delta_t_seconds(dt_utc.year) / 86400.0
    if body_name == "日":
        trop = qz.sun_geometric_longitude(jd_tt)
    elif body_name == "月":
        trop = qz.moon_longitude(jd_tt)
    elif body_name == "水":
        trop = qz.planet_longitude_tt("mercury", jd_tt)
    elif body_name == "金":
        trop = qz.planet_longitude_tt("venus", jd_tt)
    elif body_name == "火":
        trop = qz.planet_longitude_tt("mars", jd_tt)
    elif body_name == "木":
        trop = qz.planet_longitude_tt("jupiter", jd_tt)
    elif body_name == "土":
        trop = qz.planet_longitude_tt("saturn", jd_tt)
    elif body_name == "罗睺":
        trop = qz.rahu_longitude(jd_tt)
    elif body_name == "计都":
        trop = qz.ketu_longitude(jd_tt)
    elif body_name == "月孛":
        trop = qz.yuebei_longitude(jd_tt)
    elif body_name == "紫气":
        trop = qz.purple_qi_longitude(jd_ut)
    else:
        raise ValueError("Unknown luminary: " + str(body_name))

    sid = qz.to_sidereal(trop, jd_tt, profile=profile)
    mansions = qz.mansions_for_epoch(jd_tt, profile=profile)
    palaces = qz.palaces_for_epoch(jd_tt, profile=profile)
    m_name, m_deg, _, _ = qz.mansion_of(sid, mansions=mansions)
    p_zhi = qz.palace_of(sid, palaces=palaces)
    return sid, p_zhi, m_name, m_deg


def scan_ingresses(
    start_dt_bj: datetime,
    end_dt_bj: datetime,
    *,
    bodies: tuple[str, ...] = qz.LUMINARIES,
    mode: str = "palace",
    natal_house_by_zhi: dict[str, str] | None = None,
    profile: str = "calibrated-v3",
    end_exclusive: bool = False,
) -> list[dict[str, Any]]:
    """Scan exact palace (过宫) or mansion (过宿) ingresses in (start_dt_bj, end_dt_bj] via bisection."""
    if mode not in ("palace", "mansion"):
        raise ValueError("mode must be 'palace' or 'mansion'")
    events: list[dict[str, Any]] = []
    idx_slot = 1 if mode == "palace" else 2

    for body in bodies:
        if mode == "mansion":
            step_h = MANSION_INGRESS_STEP_HOURS.get(body, 6.0)
        else:
            step_h = PALACE_INGRESS_STEP_HOURS.get(body, 24.0)
        step = timedelta(hours=step_h)
        cur_dt = start_dt_bj
        prev_val = _body_sidereal_at(cur_dt, body, profile=profile)
        while cur_dt < end_dt_bj:
            nxt_dt = min(end_dt_bj, cur_dt + step)
            nxt_val = _body_sidereal_at(nxt_dt, body, profile=profile)
            if nxt_val[idx_slot] != prev_val[idx_slot]:
                lo_dt, hi_dt = cur_dt, nxt_dt
                lo_val, hi_val = prev_val, nxt_val
                while (hi_dt - lo_dt).total_seconds() > 1.0:
                    mid_dt = lo_dt + (hi_dt - lo_dt) / 2
                    mid_val = _body_sidereal_at(mid_dt, body, profile=profile)
                    if mid_val[idx_slot] == lo_val[idx_slot]:
                        lo_dt, lo_val = mid_dt, mid_val
                    else:
                        hi_dt, hi_val = mid_dt, mid_val
                delta_lon = qz.lon_delta(hi_val[0], lo_val[0])
                motion = "顺行度" if delta_lon >= 0 else "逆行度"
                ev_dt = lo_dt if (end_exclusive and hi_dt >= end_dt_bj) else hi_dt
                ev: dict[str, Any] = {
                    "datetime_bj": ev_dt.replace(second=0, microsecond=0).isoformat(),
                    "body": body,
                    "type": "过宫" if mode == "palace" else "过宿",
                    "from": lo_val[idx_slot],
                    "to": hi_val[idx_slot],
                    "to_palace": hi_val[1],
                    "to_mansion": hi_val[2],
                    "sidereal_deg": round(hi_val[0], 3),
                    "motion": motion,
                }
                if natal_house_by_zhi:
                    ev["from_natal_house"] = natal_house_by_zhi.get(lo_val[1])
                    ev["to_natal_house"] = natal_house_by_zhi.get(hi_val[1])
                events.append(ev)
                # Advance to crossing instant hi_dt (not nxt_dt) so a second crossing inside [hi_dt, nxt_dt] is never skipped.
                cur_dt = hi_dt if hi_dt > cur_dt else nxt_dt
                prev_val = hi_val if cur_dt == hi_dt else nxt_val
            else:
                cur_dt, prev_val = nxt_dt, nxt_val

    events.sort(key=lambda e: (e["datetime_bj"], qz.LUMINARIES.index(e["body"])))
    return events


def compute_transit_snapshot(
    natal_res: dict[str, Any],
    target_dt_bj: datetime,
    *,
    birth_dt_bj: datetime | None = None,
    orb_deg: float = 3.0,
) -> dict[str, Any]:
    """Compute full 11-luminary transit snapshot, natal-house overlay, Tai Sui 12 shensha, and natal/limit interactions."""
    profile = natal_res.get("calculation_profile", "calibrated-v3")
    transit_res, _ = qz.compute(
        (target_dt_bj.year, target_dt_bj.month, target_dt_bj.day),
        target_dt_bj.hour, target_dt_bj.minute,
        lat=None, lon=None, birth_instant=target_dt_bj, profile=profile,
    )
    natal_houses = natal_res.get("twelve_houses") or []
    house_by_zhi = {h["zhi"]: h["name"] for h in natal_houses}
    en_yong = natal_res.get("en_yong") or {}
    rel_by_star = {}
    for rel, stars in en_yong.items():
        for s in stars:
            rel_by_star[s] = rel

    t_ygz = qr.year_ganzhi_at_instant(target_dt_bj)
    ts_idx = qr.ZHI.index(t_ygz["year_zhi"])
    taisui_12 = {}
    for step, label in enumerate(TAISUI_12_LABELS):
        z = qr.ZHI[(ts_idx + step) % 12]
        taisui_12[label] = {
            "zhi": z,
            "natal_house": house_by_zhi.get(z),
        }
    transit_bianyao = qr.compute_bianyao_shensha(
        t_ygz["year_gan"], t_ygz["year_zhi"],
        ming_gong_zhi=natal_res["ming_gong"]["zhi"] if natal_res.get("ming_gong") else None,
        day_night_type=natal_res["day_night"]["type"] if natal_res.get("day_night") else None,
        bodies=transit_res["bodies"],
    )

    dongwei_active = None
    if birth_dt_bj is not None and natal_res.get("ming_gong"):
        dw = compute_dongwei_daxian(birth_dt_bj, natal_res, target_dt_bj=target_dt_bj)
        dongwei_active = dw["active"] if dw else None

    limit_zhi = dongwei_active["palace_limit"]["zhi"] if dongwei_active else None
    limit_sid = dongwei_active["degree_limit"]["sidereal"] if dongwei_active else None
    ming_zhi = natal_res["ming_gong"]["zhi"] if natal_res.get("ming_gong") else None
    shen_zhi = natal_res["shen_gong"]["zhi"] if natal_res.get("shen_gong") else None
    ming_sid = natal_res["ming_du"]["sidereal"] if natal_res.get("ming_du") else None
    shen_sid = natal_res["shen_gong"]["shen_du"]["sidereal"] if natal_res.get("shen_gong") else None

    transit_bodies: dict[str, Any] = {}
    triggers: list[dict[str, Any]] = []
    for star in qz.LUMINARIES:
        tb = transit_res["bodies"][star]
        t_pal = tb["palace"]
        t_sid = tb["sidereal"]
        star_rel = rel_by_star.get(star)
        transit_bodies[star] = {
            "tropical": round(tb["tropical"], 4),
            "sidereal": round(t_sid, 4),
            "mansion": tb["mansion"],
            "mansion_deg": round(tb["mansion_deg"], 2),
            "mansion_wx": tb["mansion_wx"],
            "palace": t_pal,
            "natal_house": house_by_zhi.get(t_pal),
            "en_yong_role": star_rel,
            "transit_bianyao": transit_bianyao["by_star"].get(star),
        }

        for anchor_label, anchor_zhi in (("本命命宫", ming_zhi), ("本命身宫", shen_zhi), ("当前洞微大限宫", limit_zhi)):
            if not anchor_zhi:
                continue
            diff_pal = (qr.ZHI.index(t_pal) - qr.ZHI.index(anchor_zhi)) % 12
            if diff_pal == 0:
                triggers.append({
                    "transit_body": star, "en_yong_role": star_rel,
                    "target": anchor_label, "relation": "同宫守临", "palace": t_pal,
                })
            elif diff_pal == 6:
                triggers.append({
                    "transit_body": star, "en_yong_role": star_rel,
                    "target": anchor_label, "relation": "对宫冲照", "palace": t_pal,
                })

        for deg_label, deg_val in (("本命命度", ming_sid), ("本命身度", shen_sid), ("当前洞微限度", limit_sid)):
            if deg_val is None:
                continue
            d_conj = abs(qz.lon_delta(t_sid, deg_val))
            d_opp = abs(qz.lon_delta(t_sid, (deg_val + 180.0) % 360.0))
            if d_conj <= orb_deg:
                triggers.append({
                    "transit_body": star, "en_yong_role": star_rel,
                    "target": deg_label, "relation": "同度合相", "orb_deg": round(d_conj, 3),
                })
            elif d_opp <= orb_deg:
                triggers.append({
                    "transit_body": star, "en_yong_role": star_rel,
                    "target": deg_label, "relation": "对度冲克", "orb_deg": round(d_opp, 3),
                })

    taisui_alerts: list[str] = []
    for sha_label in ("太岁", "岁破", "白虎", "丧门", "官符", "吊客", "病符"):
        info = taisui_12[sha_label]
        if info["zhi"] == ming_zhi:
            taisui_alerts.append(f"流年{sha_label}({info['zhi']})临本命命宫")
        if info["zhi"] == limit_zhi:
            taisui_alerts.append(f"流年{sha_label}({info['zhi']})临当前大限{dongwei_active['palace_limit']['house_name']}")
        if info["zhi"] == shen_zhi:
            taisui_alerts.append(f"流年{sha_label}({info['zhi']})临本命身宫")

    return {
        "target_bj": target_dt_bj.isoformat(),
        "year_gz": t_ygz,
        "transit_bodies": transit_bodies,
        "taisui_12": taisui_12,
        "transit_bianyao": transit_bianyao["bianyao"],
        "dongwei_active": dongwei_active,
        "triggers": triggers,
        "taisui_alerts": taisui_alerts,
    }


def compute_dynamic_layers(
    birth_dt_bj: datetime,
    natal_res: dict[str, Any],
    target_dt_bj: datetime,
    *,
    scope: str = "all",
    natal_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Compute unified yearly/monthly/daily Qizheng dynamic transits and ingresses."""
    if scope not in ("yearly", "monthly", "daily", "all"):
        raise ValueError("scope must be one of yearly|monthly|daily|all")
    profile = natal_res.get("calculation_profile", "calibrated-v3")
    natal_houses = natal_res.get("twelve_houses") or []
    house_by_zhi = {h["zhi"]: h["name"] for h in natal_houses}

    snapshot = compute_transit_snapshot(natal_res, target_dt_bj, birth_dt_bj=birth_dt_bj)
    layers: dict[str, Any] = {}

    if scope in ("yearly", "all"):
        y_start = datetime(target_dt_bj.year, 1, 1, 0, 0, tzinfo=qz.BJ)
        y_end = datetime(target_dt_bj.year + 1, 1, 1, 0, 0, tzinfo=qz.BJ)
        yearly_bodies = ("木", "土", "火", "金", "水", "日", "罗睺", "计都", "月孛", "紫气")
        layers["yearly"] = {
            "year": target_dt_bj.year,
            "year_gz": snapshot["year_gz"],
            "taisui_12": snapshot["taisui_12"],
            "taisui_alerts": snapshot["taisui_alerts"],
            "transit_bianyao": snapshot["transit_bianyao"],
            "palace_ingresses": scan_ingresses(
                y_start, y_end, bodies=yearly_bodies, mode="palace",
                natal_house_by_zhi=house_by_zhi, profile=profile, end_exclusive=True,
            ),
        }

    if scope in ("monthly", "all"):
        m_start = datetime(target_dt_bj.year, target_dt_bj.month, 1, 0, 0, tzinfo=qz.BJ)
        if target_dt_bj.month == 12:
            m_end = datetime(target_dt_bj.year + 1, 1, 1, 0, 0, tzinfo=qz.BJ)
        else:
            m_end = datetime(target_dt_bj.year, target_dt_bj.month + 1, 1, 0, 0, tzinfo=qz.BJ)
        monthly_bodies = ("日", "金", "水", "火", "木", "土", "罗睺", "计都", "月孛", "紫气")
        layers["monthly"] = {
            "year_month": f"{target_dt_bj.year:04d}-{target_dt_bj.month:02d}",
            "palace_ingresses": scan_ingresses(
                m_start, m_end, bodies=monthly_bodies, mode="palace",
                natal_house_by_zhi=house_by_zhi, profile=profile, end_exclusive=True,
            ),
            "sun_mansion_ingresses": scan_ingresses(
                m_start, m_end, bodies=("日",), mode="mansion",
                natal_house_by_zhi=house_by_zhi, profile=profile, end_exclusive=True,
            ),
        }

    if scope in ("daily", "all"):
        d_start = datetime(target_dt_bj.year, target_dt_bj.month, target_dt_bj.day, 0, 0, tzinfo=qz.BJ)
        d_end = d_start + timedelta(days=1)
        layers["daily"] = {
            "date": target_dt_bj.date().isoformat(),
            "target_bj": target_dt_bj.isoformat(),
            "transit_bodies": snapshot["transit_bodies"],
            "triggers": snapshot["triggers"],
            "moon_palace_ingresses": scan_ingresses(
                d_start, d_end, bodies=("月",), mode="palace",
                natal_house_by_zhi=house_by_zhi, profile=profile, end_exclusive=True,
            ),
            "moon_mansion_ingresses": scan_ingresses(
                d_start, d_end, bodies=("月",), mode="mansion",
                natal_house_by_zhi=house_by_zhi, profile=profile, end_exclusive=True,
            ),
        }

    return {
        "schema_version": 1,
        "calculation_profile": profile,
        "birth_bj": birth_dt_bj.isoformat(),
        "target_bj": target_dt_bj.isoformat(),
        "scope": scope,
        "natal_summary": {
            "year_gz": natal_res.get("year_gz", {}).get("year_gz"),
            "day_night": natal_res["day_night"]["type"] if natal_res.get("day_night") else None,
            "ming_gong": natal_res["ming_gong"]["zhi"] if natal_res.get("ming_gong") else None,
            "ming_du": (
                f"{natal_res['ming_du']['mansion']}{natal_res['ming_du']['mansion_deg']:.2f}°"
                if natal_res.get("ming_du") else None
            ),
            "du_zhu_wuxing": natal_res.get("du_zhu_wuxing"),
            "shen_gong": natal_res["shen_gong"]["zhi"] if natal_res.get("shen_gong") else None,
            "shen_zhu": natal_res["shen_gong"]["shen_zhu"] if natal_res.get("shen_gong") else None,
            "en_yong": natal_res.get("en_yong"),
        },
        "dongwei_active": snapshot["dongwei_active"],
        "layers": layers,
        "warnings": list(natal_warnings or []),
    }
