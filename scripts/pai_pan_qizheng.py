#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""七政四余排盘（纯标准库，无第三方依赖）。

[来源] high-confidence-mingli-skill v5 完整版引擎。
天文算法：
- 太阳：VSOP87 地球黄经级数（复用 scripts/astro_data/solar_longitude.json，去章动/光行差得日期平黄经，1900–2100 对 JPL Horizons 404 点误差 <0.0001°）；
- 月亮与五星：Meeus AA ch.47 + Schlyter 摄动日心修正（1900–2100 对 JPL Horizons 404 点误差 <0.055°）；
- 四余：罗睺=月亮平升交点（Meeus 47.7）；计都=罗睺对冲；月孛=月亮平远地点；紫气=二十八岁周天虚拟星。

═══ 口径声明（学派选择，全部标注出处）═══
1. 盘制：恒星制（sidereal）。恒星原点 = 角宿一（Spica，α Vir，HIP 65474）；
   calibrated-v3: SIMBAD ICRS J2000 RA/Dec + 自行 + IAU1976 岁差 → 实时日期平黄经（J2000≈203.84136°）。
   legacy-v1: 201.2983° 为赤经误作黄经，仅用于历史重放。
2. 二十八宿边界（calibrated-v3）：全 28 颗距星逐星取 SIMBAD ICRS J2000 坐标与自行，实时岁差至日期平黄经；
   觜宿取古距星 φ¹ Ori、参宿取古距星 ζ Ori，规避现代 λ Ori / δ Ori 岁差“觜参易位”，全 28 宿严格单调。
3. 十二支宫：按《汉书·律历志》经典十二次分野，直接由实时校准的 28 宿起点聚合——
   辰=角亢、卯=氐房心、寅=尾箕、丑=斗牛、子=女虚、亥=危室壁、
   戌=奎娄、酉=胃昴毕、申=觜参、未=井鬼、午=柳星张、巳=翼轸。
4. 安命宫：《果老星宗》法——「以生时加太阳之宫，顺数至卯，卯宫即命宫」。
5. 计都：罗睺对冲（交点说，主流口径）。
6. 紫气：无实象虚拟星，二十八岁一周天（沿用 Moira / 现仓通用锚点：1975-03-13 16:00 UT 黄经 230.5°，日行 +360/10227.1792°）。
7. 恩用难仇：以命度宿五行（度主）为我——生我=恩、我生=用、克我=难、我克=仇。
8. 命度：真升点（mean ecliptic & geometric horizon 东方上升交点，UT1 GMST 不加均时差）→ 换恒星黄经 → 落宿。
"""

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from qizheng_provenance import model_provenance
from qizheng_rules import (
    PALACE_RULER,
    PALACE_RULER_WUXING,
    build_twelve_houses,
    compute_bianyao_shensha,
    compute_shen_gong,
    compute_star_states,
    year_ganzhi_at_instant,
)
from qizheng_star_frame import (
    CALIBRATED_MANSIONS_J2000,
    CALIBRATED_PALACES_J2000,
    boundary_diagnostic,
    calibrated_mansions,
    calibrated_palaces,
    spica_mean_longitude,
    star_frame_contract,
)

BJ = timezone(timedelta(hours=8))
J2000 = 2451545.0
UNIX_JD = 2440587.5

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 十一曜与五行
LUMINARIES = ("日", "月", "木", "火", "土", "金", "水", "罗睺", "计都", "月孛", "紫气")
LUMINARIES_WUXING = {
    "日": "火", "月": "水", "木": "木", "火": "火", "土": "土",
    "金": "金", "水": "水", "罗睺": "火", "计都": "土", "月孛": "水", "紫气": "木",
}
WUXING_SHENGKE = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_SHENGWO = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}
WUXING_WOKE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}
WUXING_KEWO = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}

# 宿主五行 → 五行相位（日宿取火、月宿取水，与十一曜五行表同源）
MANSION_WX_TO_PHASE = {"木": "木", "火": "火", "土": "土", "金": "金", "水": "水",
                       "日": "火", "月": "水"}

# 历史未校准近似表（仅 legacy-v1 重放）
LEGACY_MANSIONS = (
    ("角", "α Vir", 0.0, "木"), ("亢", "κ Vir", 12.0, "金"), ("氐", "α Lib", 28.0, "土"),
    ("房", "π Sco", 33.0, "日"), ("心", "σ Sco", 38.0, "月"), ("尾", "μ Sco", 44.5, "火"),
    ("箕", "γ Sgr", 62.5, "水"), ("斗", "φ Sgr", 73.5, "木"), ("牛", "β Cap", 99.5, "金"),
    ("女", "ε Aqr", 107.0, "土"), ("虚", "β Aqr", 119.0, "日"), ("危", "α Aqr", 129.0, "月"),
    ("室", "α Peg", 145.5, "火"), ("壁", "γ Peg", 161.5, "水"), ("奎", "η And", 170.5, "木"),
    ("娄", "β Ari", 186.5, "金"), ("胃", "35 Ari", 198.5, "土"), ("昴", "17 Tau", 210.0, "日"),
    ("毕", "ε Tau", 221.0, "月"), ("觜", "λ Ori", 237.5, "火"), ("参", "δ Ori", 240.0, "水"),
    ("井", "μ Gem", 261.0, "木"), ("鬼", "θ Cnc", 294.0, "金"), ("柳", "δ Hya", 298.0, "土"),
    ("星", "α Hya", 313.0, "日"), ("张", "υ¹ Hya", 320.0, "月"), ("翼", "α Crt", 332.0, "火"),
    ("轸", "γ Crv", 350.0, "水"),
)
LEGACY_PALACES = {
    "辰": (0.0, 28.0), "卯": (28.0, 44.5), "寅": (44.5, 73.5), "丑": (73.5, 107.0),
    "子": (107.0, 129.0), "亥": (129.0, 170.5), "戌": (170.5, 198.5), "酉": (198.5, 237.5),
    "申": (237.5, 261.0), "未": (261.0, 298.0), "午": (298.0, 332.0), "巳": (332.0, 360.0),
}

# 默认二十八宿与十二支宫（SIMBAD ICRS J2000 校准表；compute() 另按实时 jd_tt 逐星岁差）
MANSIONS = CALIBRATED_MANSIONS_J2000
PALACES = CALIBRATED_PALACES_J2000
# 支宫五行（四正四库通行）
PALACE_WUXING = {"寅": "木", "卯": "木", "巳": "火", "午": "火", "申": "金", "酉": "金",
                 "亥": "水", "子": "水", "辰": "土", "戌": "土", "丑": "土", "未": "土"}

# 紫气锚点（口径声明第 6 条）
PURPLE_QI_ANCHOR_JD = 2442485.1666666665  # 1975-03-13 16:00 UT
PURPLE_QI_ANCHOR_LON = 230.5
PURPLE_QI_RATE = 360.0 / 10227.1792    # 二十八岁一周天


def norm_deg(x):
    return x % 360.0


def lon_delta(actual, target):
    return (actual - target + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------
# 时间
# ---------------------------------------------------------------------------

def delta_t_seconds(year):
    """TT−UTC 近似秒（Espenak/Meeus 分段）。与 pai_pan_bazi 同式。"""
    y = float(year)
    t = y - 2000.0
    if y < 1920:
        t1 = y - 1900.0
        return -2.79 + 1.494119 * t1 - 0.0598939 * t1**2 + 0.0061966 * t1**3 - 0.000197 * t1**4
    if y < 1941:
        t1 = y - 1920.0
        return 21.20 + 0.84493 * t1 - 0.076100 * t1**2 + 0.0020936 * t1**3
    if y < 1961:
        t1 = y - 1950.0
        return 29.07 + 0.407 * t1 - t1**2 / 233.0 + t1**3 / 2547.0
    if y < 1986:
        t1 = y - 1975.0
        return 45.45 + 1.067 * t1 - t1**2 / 260.0 - t1**3 / 718.0
    if y < 2005:
        t1 = y - 2000.0
        return (
            63.86 + 0.3345 * t1 - 0.060374 * t1**2 + 0.0017275 * t1**3
            + 0.000651814 * t1**4 + 0.00002373599 * t1**5
        )
    if y < 2050:
        return 62.92 + 0.32217 * t + 0.005589 * t * t
    return -20.0 + 32.0 * ((y - 1820.0) / 100.0) ** 2 - 0.5628 * (2150.0 - y)


def jd_from_utc(dt_utc):
    unix = (dt_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
    return UNIX_JD + unix / 86400.0


def julian_centuries_tt(jd_ut):
    """UT 时刻的力学时儒略世纪数。"""
    year = 2000.0 + (jd_ut - J2000) / 365.242189
    return (jd_ut + delta_t_seconds(year) / 86400.0 - J2000) / 36525.0


# ---------------------------------------------------------------------------
# 太阳 / 月亮 / 行星 黄经（黄道坐标，度）
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _solar_vsop87_series():
    path = Path(__file__).resolve().parent / "astro_data" / "solar_longitude.json"
    return json.loads(path.read_text(encoding="utf-8"))


def sun_geometric_longitude(jd_tt):
    """Geocentric geometric Sun longitude in mean ecliptic/equinox of date (deg).

    Uses vendored MIT VSOP87 Earth longitude series (scripts/astro_data/solar_longitude.json),
    omitting nutation and aberration to match the mean-ecliptic-of-date geometric frame.
    Validated across 404 JPL Horizons vectors (1900-2100) to <0.0001 deg (<0.4 arcsec).
    """
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    data = _solar_vsop87_series()
    t = (jd_tt - J2000) / 36525.0
    tau = t / 10.0
    sec_per_rad = 648000.0 / math.pi
    earth = sum(
        sum(a * math.cos(b + tau * c) for a, b, c in terms) * tau ** order
        for order, terms in enumerate(data["earth_longitude"])
    ) / data["scale"]
    earth += (-0.0728 - 2.7702 * tau - 1.1019 * tau**2 - 0.0996 * tau**3) / sec_per_rad
    return math.degrees(earth + math.pi) % 360.0


def sun_apparent_longitude(jd_tt):
    """太阳视黄经。Meeus AA ch.25（保留供 legacy-v1 与旧回归对拍，0.01° 级）。"""
    T = (jd_tt - J2000) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    mr = math.radians(M)
    C = (
        (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(mr)
        + (0.019993 - 0.000101 * T) * math.sin(2.0 * mr)
        + 0.000289 * math.sin(3.0 * mr)
    )
    omega = 125.04 - 1934.136 * T
    lam = L0 + C - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    return lam % 360.0


# Meeus AA ch.47 月亮黄经主要项（截断集，精度 ~0.05°）
MOON_TERMS = (
    # (系数, D 系数, M 系数, M' 系数, F 系数)
    (6.288774, 0, 0, 1, 0),
    (1.274027, 2, 0, -1, 0),
    (0.658314, 2, 0, 0, 0),
    (0.213618, 0, 0, 2, 0),
    (-0.185116, 0, 1, 0, 0),
    (-0.114332, 0, 0, 0, 2),
    (0.058793, 2, 0, -2, 0),
    (0.057066, 2, -1, -1, 0),
    (0.053322, 2, 0, 1, 0),
    (0.045758, 2, -1, 0, 0),
    (-0.040923, 0, 1, -1, 0),
    (-0.034720, 1, 0, 0, 0),
    (-0.030383, 0, 1, 1, 0),
    (0.015327, 2, 0, 0, -2),
    (-0.012528, 0, 0, 1, 2),
    (0.010980, 0, 0, 1, -2),
    (0.010675, 4, 0, -1, 0),
    (0.010034, 0, 0, 3, 0),
    (0.008548, 4, 0, -2, 0),
    (-0.007888, 2, 1, -1, 0),
    (-0.006766, 2, 1, 0, 0),
    (-0.005163, 1, 0, -1, 0),
    (0.004987, 1, 1, 0, 0),
    (0.004036, 2, -1, 1, 0),
    (0.003994, 2, 0, 2, 0),
    (0.003861, 4, 0, 0, 0),
    (0.003665, 2, 0, -3, 0),
    (-0.002689, 0, 1, -2, 0),
    (-0.002602, 2, 0, -1, 2),
    (0.002390, 2, -1, -2, 0),
    (-0.002348, 1, 0, 1, 0),
    (0.002236, 2, -2, 0, 0),
    (-0.002120, 0, 1, 2, 0),
    (0.002069, 2, 0, -2, 0),
    (-0.002048, 0, 2, 0, 0),
)


def moon_longitude(jd_tt, model="meeus-truncated-geometric-v2"):
    """Geocentric geometric longitude in mean ecliptic/equinox of date.

    Truncated Meeus AA ch.47, without nutation, light-time or aberration.
    legacy-v1 preserves the original table and omitted eccentricity factors.
    """
    if model not in ("meeus-truncated-geometric-v2", "legacy-v1"):
        raise ValueError("unknown Moon model: " + str(model))
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    T = (jd_tt - J2000) / 36525.0
    Lp = (
        218.3164477 + 481267.88123421 * T - 0.0015786 * T * T
        + T**3 / 538841.0 - T**4 / 65194000.0
    )
    D = (
        297.8501921 + 445267.1114034 * T - 0.0018819 * T * T
        + T**3 / 545868.0 - T**4 / 113065000.0
    )
    M = 357.5291092 + 35999.0502909 * T - 0.0001536 * T * T + T**3 / 24490000.0
    Mp = (
        134.9633964 + 477198.8675055 * T + 0.0087414 * T * T
        + T**3 / 69699.0 - T**4 / 14712000.0
    )
    F = (
        93.2720950 + 483202.0175233 * T - 0.0036539 * T * T
        - T**3 / 3526000.0 + T**4 / 863310000.0
    )
    A1 = 119.75 + 131.849 * T
    A2 = 53.09 + 479264.290 * T
    lam = Lp
    rad = math.radians
    terms = MOON_TERMS
    if model != "legacy-v1":
        # Meeus Table 47.A rows 34–35; v1 duplicated D/M' and reversed signs.
        terms = MOON_TERMS[:-2] + ((-0.002069, 0, 2, 0, 0),
                                  (0.002048, 2, -2, -1, 0))
    E = 1.0 - 0.002516 * T - 0.0000074 * T * T
    for coef, cd, cm, cmp_, cf in terms:
        if model != "legacy-v1":
            coef *= E ** abs(cm)
        arg = cd * D + cm * M + cmp_ * Mp + cf * F
        lam += coef * math.sin(rad(arg))
    lam += 0.003958 * math.sin(rad(A1))
    lam += 0.001962 * math.sin(rad(Lp - F))
    lam += 0.000318 * math.sin(rad(A2))
    return lam % 360.0


def _schlyter_elements(planet, d):
    """Schlyter 轨道要素（d = 自 2000-01-00 TT 起算的日数）。"""
    el = {
        "mercury": (48.3313, 3.24587e-5, 7.0047, 5.00e-8, 29.1241, 1.01444e-5,
                    0.387098, 0.205635, 5.59e-10, 168.6562, 4.0923344368),
        "venus": (76.6799, 2.46590e-5, 3.3946, 2.75e-8, 54.8910, 1.38374e-5,
                  0.723330, 0.006773, -1.302e-9, 48.0052, 1.6021302244),
        "mars": (49.5574, 2.11081e-5, 1.8497, -1.78e-8, 286.5016, 2.92961e-5,
                 1.523688, 0.093405, 2.516e-9, 18.6021, 0.5240207766),
        "jupiter": (100.4542, 2.76854e-5, 1.3030, -1.557e-7, 273.8777, 1.64505e-5,
                    5.20256, 0.048498, 4.469e-9, 19.8950, 0.0830853001),
        "saturn": (113.6634, 2.38980e-5, 2.4886, -1.081e-7, 339.3939, 2.97661e-5,
                   9.55475, 0.055546, -9.499e-9, 316.9670, 0.0334442282),
    }[planet]
    N0, dN, i0, di, w0, dw, a, e0, de, M0, dM = el
    return {
        "N": N0 + dN * d, "i": i0 + di * d, "w": w0 + dw * d,
        "a": a, "e": e0 + de * d, "M": M0 + dM * d,
    }


def _sun_elements(d):
    return {"w": 282.9404 + 4.70935e-5 * d, "e": 0.016709 - 1.151e-9 * d,
            "M": 356.0470 + 0.9856002585 * d}


def _kepler_E(M, e):
    M = M % 360.0
    E0 = M + math.degrees(e) * math.sin(math.radians(M)) * (1 + e * math.cos(math.radians(M)))
    E = E0
    for _ in range(30):
        dE = (E - math.degrees(e) * math.sin(math.radians(E)) - M) / (1 - e * math.cos(math.radians(E)))
        E -= dE
        if abs(dE) < 1e-8:
            break
    return E


def _helio_rect(el):
    """轨道要素 → 日心黄道直角坐标。"""
    N, i, w = math.radians(el["N"]), math.radians(el["i"]), math.radians(el["w"])
    E = _kepler_E(el["M"], el["e"])
    xv = el["a"] * (math.cos(math.radians(E)) - el["e"])
    yv = el["a"] * math.sqrt(1 - el["e"] ** 2) * math.sin(math.radians(E))
    xh = xv * (math.cos(N) * math.cos(w) - math.sin(N) * math.sin(w) * math.cos(i)) - yv * (
        math.cos(N) * math.sin(w) + math.sin(N) * math.cos(w) * math.cos(i))
    yh = xv * (math.sin(N) * math.cos(w) + math.cos(N) * math.sin(w) * math.cos(i)) - yv * (
        math.sin(N) * math.sin(w) - math.cos(N) * math.cos(w) * math.cos(i))
    zh = xv * math.sin(w) * math.sin(i) + yv * math.cos(w) * math.sin(i)
    return xh, yh, zh


def _days_since_2000(jd_ut):
    # Schlyter 的 d 自 2000-01-00（=1999-12-31 00:00 TT）起算，近似取 JD 差
    return jd_ut + delta_t_seconds(2000.0 + (jd_ut - J2000) / 365.242189) / 86400.0 - 2451543.5


def _planet_longitude_legacy(planet, jd_ut):
    """Frozen v1 numerics, including known sign/frame errors; replay only."""
    d = _days_since_2000(jd_ut)
    el = _schlyter_elements(planet, d)
    xh, yh, _ = _helio_rect(el)
    sun_el = _sun_elements(d)
    # 太阳直角坐标（= 地心看太阳的反向即地球日心坐标取反）
    ws, es, Ms = sun_el["w"], sun_el["e"], sun_el["M"]
    Es = _kepler_E(Ms, es)
    xvs = math.cos(math.radians(Es)) - es
    yvs = math.sqrt(1 - es * es) * math.sin(math.radians(Es))
    ws_rad = math.radians(ws)
    xg_sun = xvs * math.cos(ws_rad) - yvs * math.sin(ws_rad)
    yg_sun = xvs * math.sin(ws_rad) + yvs * math.cos(ws_rad)
    # 地心 = 行星日心 + 太阳直角（地球日心坐标 = −太阳直角，行星地心 = 行星日心 − 地球日心 = 行星日心 + 太阳直角）
    xg = xh + xg_sun
    yg = yh + yg_sun
    lon = math.degrees(math.atan2(yg, xg))
    # 木土互相摄动（Schlyter 摄动表）
    Mj = _schlyter_elements("jupiter", d)["M"] % 360.0
    Msat = _schlyter_elements("saturn", d)["M"] % 360.0
    rad = math.radians
    if planet == "jupiter":
        lon += (
            -0.332 * math.sin(rad(2 * Mj - 5 * Msat + 67.6))
            - 0.056 * math.sin(rad(2 * Mj - 2 * Msat + 21))
            + 0.042 * math.sin(rad(3 * Mj - 5 * Msat + 21))
            - 0.036 * math.sin(rad(Mj - 2 * Msat))
            + 0.022 * math.cos(rad(Mj - Msat))
            + 0.023 * math.sin(rad(2 * Mj - 3 * Msat + 52))
            - 0.016 * math.sin(rad(Mj - 5 * Msat - 69))
        )
    elif planet == "saturn":
        lon += (
            +0.812 * math.sin(rad(2 * Mj - 5 * Msat - 67.6))
            - 0.229 * math.cos(rad(2 * Mj - 4 * Msat - 2))
            + 0.119 * math.sin(rad(Mj - 2 * Msat - 3))
            + 0.046 * math.sin(rad(2 * Mj - 6 * Msat - 69))
            + 0.014 * math.sin(rad(Mj - 3 * Msat + 32))
        )
    # 光行差（~20.5″/距离，Schlyter 简式：内行星可略，统一加太阳方向光行差近似）
    return norm_deg(lon)


PLANET_MODEL = "schlyter-geometric-v2"


def _perturbed_helio_rect(planet, d):
    """Schlyter sections 7–9: perturb HELIOCENTRIC longitude/latitude first.

    Source: https://stjarnhimlen.se/comp/ppcomp.html (Paul Schlyter).
    Independent transcription of published formulae; no external runtime code.
    """
    x, y, z = _helio_rect(_schlyter_elements(planet, d))
    if planet not in ("jupiter", "saturn"):
        return x, y, z
    r = math.sqrt(x*x + y*y + z*z)
    lon = math.degrees(math.atan2(y, x))
    lat = math.degrees(math.atan2(z, math.hypot(x, y)))
    j = _schlyter_elements("jupiter", d)["M"] % 360.0
    s = _schlyter_elements("saturn", d)["M"] % 360.0
    sin = lambda a: math.sin(math.radians(a))
    cos = lambda a: math.cos(math.radians(a))
    if planet == "jupiter":
        lon += (-0.332*sin(2*j-5*s-67.6) - 0.056*sin(2*j-2*s+21)
                + 0.042*sin(3*j-5*s+21) - 0.036*sin(j-2*s)
                + 0.022*cos(j-s) + 0.023*sin(2*j-3*s+52)
                - 0.016*sin(j-5*s-69))
    else:
        lon += (0.812*sin(2*j-5*s-67.6) - 0.229*cos(2*j-4*s-2)
                + 0.119*sin(j-2*s-3) + 0.046*sin(2*j-6*s-69)
                + 0.014*sin(j-3*s+32))
        lat += -0.020*cos(2*j-4*s-2) + 0.018*sin(2*j-6*s-49)
    return r*cos(lon)*cos(lat), r*sin(lon)*cos(lat), r*sin(lat)


def planet_longitude_tt(planet, jd_tt):
    """V2 geocentric GEOMETRIC longitude, mean ecliptic/equinox of date.

    TT input; no light time, annual aberration, nutation, or topocentric parallax.
    Low-precision model, validated on a sparse 1900–2100 grid, not an accuracy
    guarantee near classification boundaries. See docs/qizheng-ephemeris.md.
    """
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    d = jd_tt - 2451543.5
    xh, yh, _ = _perturbed_helio_rect(planet, d)
    sun = _sun_elements(d)
    E = math.radians(_kepler_E(sun["M"], sun["e"]))
    w = math.radians(sun["w"])
    x = math.cos(E) - sun["e"]
    y = math.sqrt(1 - sun["e"]**2) * math.sin(E)
    return norm_deg(math.degrees(math.atan2(
        yh + x*math.sin(w) + y*math.cos(w),
        xh + x*math.cos(w) - y*math.sin(w))))


def planet_longitude(planet, jd_ut, model=PLANET_MODEL):
    """Compatibility UT≈UTC entrypoint; prefer explicit TT in physical-v2."""
    if not math.isfinite(jd_ut):
        raise ValueError("jd_ut must be finite")
    if model == "legacy-v1":
        return _planet_longitude_legacy(planet, jd_ut)
    if model != PLANET_MODEL:
        raise ValueError("unknown planet model: " + str(model))
    return planet_longitude_tt(planet, _days_since_2000(jd_ut) + 2451543.5)


# ---------------------------------------------------------------------------
# 四余
# ---------------------------------------------------------------------------

def rahu_longitude(jd_tt):
    """罗睺 = 月亮平升交点。Meeus AA ch.47.7。"""
    T = (jd_tt - J2000) / 36525.0
    return norm_deg(
        125.0445479 - 1934.1362891 * T + 0.0020754 * T * T
        + T**3 / 467441.0 - T**4 / 60616000.0
    )


def ketu_longitude(jd_tt):
    """计都 = 罗睺对冲（交点说，口径声明第 5 条）。"""
    return norm_deg(rahu_longitude(jd_tt) + 180.0)


def yuebei_longitude(jd_tt):
    """月孛 = 月亮平远地点（平近地点 + 180°）。"""
    T = (jd_tt - J2000) / 36525.0
    mean_perigee = (
        83.3532465 + 4069.0137287 * T - 0.0103200 * T * T
        - T**3 / 80053.0 + T**4 / 18999000.0
    )
    return norm_deg(mean_perigee + 180.0)


def purple_qi_longitude(jd_ut):
    """紫气 = 二十八岁周天虚拟星（口径声明第 6 条，锚点约定值）。"""
    return norm_deg(PURPLE_QI_ANCHOR_LON + (jd_ut - PURPLE_QI_ANCHOR_JD) * PURPLE_QI_RATE)


# ---------------------------------------------------------------------------
# 恒星制换算 / 宿度 / 支宫
# ---------------------------------------------------------------------------

def spica_ayanamsa(jd_tt, profile="legacy-v1"):
    """Explicit physical origin or historical RA-as-longitude replay."""
    if profile == "calibrated-v3":
        return spica_mean_longitude(jd_tt)
    if profile != "legacy-v1":
        raise ValueError("unknown star-frame profile: " + str(profile))
    T = (jd_tt - J2000) / 36525.0
    p_arcsec = 5028.796195 * T + 1.1054348 * T * T + 0.00007964 * T**3
    return 201.2983 + p_arcsec / 3600.0


def to_sidereal(lon_tropical, jd_tt, profile="legacy-v1"):
    return norm_deg(lon_tropical - spica_ayanamsa(jd_tt, profile=profile))


def mansions_for_epoch(jd_tt, profile="calibrated-v3"):
    """Return 28-mansion table for the requested calculation profile and epoch."""
    if profile == "calibrated-v3":
        return calibrated_mansions(jd_tt)
    if profile == "legacy-v1":
        return LEGACY_MANSIONS
    raise ValueError("unknown star-frame profile: " + str(profile))


def palaces_for_epoch(jd_tt, profile="calibrated-v3"):
    """Return 12-branch palace boundary table synchronized with the 28-mansion table."""
    if profile == "calibrated-v3":
        return calibrated_palaces(calibrated_mansions(jd_tt))
    if profile == "legacy-v1":
        return LEGACY_PALACES
    raise ValueError("unknown star-frame profile: " + str(profile))


def mansion_of(sidereal_lon, mansions=None):
    """恒星黄经 → (宿名, 入宿度, 宿五行, 距星)。"""
    tbl = MANSIONS if mansions is None else mansions
    lon = norm_deg(sidereal_lon)
    chosen = tbl[-1]
    for row in tbl:
        if lon >= row[2]:
            chosen = row
        else:
            break
    name, star, start, wx = chosen[0], chosen[1], chosen[2], chosen[3]
    return name, norm_deg(lon - start), wx, star


def palace_of(sidereal_lon, palaces=None):
    """恒星黄经 → 十二支宫（经典分野聚合，口径声明第 3 条）。"""
    tbl = PALACES if palaces is None else palaces
    lon = norm_deg(sidereal_lon)
    for zhi, (lo, hi) in tbl.items():
        if lo <= lon < hi:
            return zhi
    return "巳"  # lon 落最后一段兜底（巳=翼轸至360°）


# ---------------------------------------------------------------------------
# 升度（命度）/ 昼夜生
# ---------------------------------------------------------------------------

def gmst_degrees(jd_ut):
    T = (jd_ut - J2000) / 36525.0
    return norm_deg(
        280.46061837 + 360.98564736629 * (jd_ut - J2000)
        + 0.000387933 * T * T - T**3 / 38710000.0
    )


def mean_obliquity_deg(jd_tt):
    T = (jd_tt - J2000) / 36525.0
    return 23.43929111 - 0.0130041667 * T - 1.6388889e-7 * T * T + 5.036111e-7 * T**3


def equation_of_time_minutes(jd_ut):
    """均时差（真太阳时 − 平太阳时，分钟）。Meeus ch.28 简式。"""
    T = (jd_ut - J2000) / 36525.0
    L0 = norm_deg(280.46646 + 36000.76983 * T)
    M = math.radians(norm_deg(357.52911 + 35999.05029 * T))
    e = 0.016708634 - 0.000042037 * T
    C = (
        (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M)
        + (0.019993 - 0.000101 * T) * math.sin(2 * M)
        + 0.000289 * math.sin(3 * M)
    )
    sun_true_lon = L0 + C
    omega = math.radians(125.04 - 1934.136 * T)
    sun_app_lon = sun_true_lon - 0.00569 - 0.00478 * math.sin(omega)
    eps = math.radians(mean_obliquity_deg(jd_ut))
    y = math.tan(eps / 2) ** 2
    eot_minutes = math.degrees(
        y * math.sin(2 * math.radians(L0))
        - 2 * e * math.sin(M)
        + 4 * e * y * math.sin(M) * math.cos(2 * math.radians(L0))
        - 0.5 * y * y * math.sin(4 * math.radians(L0))
        - 1.25 * e * e * math.sin(2 * M)
    ) * 4.0
    return eot_minutes


def legacy_ascendant_tropical(jd_ut, jd_tt, lat_deg, lon_deg, eot_minutes):
    """真升点（tropical ascendant）。

    LST 用真太阳时口径（LST += 均时差），与古典「真太阳定时」一致（口径声明第 8 条）。
    """
    lst = norm_deg(gmst_degrees(jd_ut) + lon_deg + eot_minutes)
    eps = math.radians(mean_obliquity_deg(jd_tt))
    lst_rad = math.radians(lst)
    lat = math.radians(lat_deg)
    asc = math.atan2(
        -math.cos(lst_rad),
        math.sin(lst_rad) * math.cos(eps) + math.tan(lat) * math.sin(eps),
    )
    return norm_deg(math.degrees(asc))


def _validate_location(lat_deg, lon_deg, *, allow_missing=False):
    if ((lat_deg is not None or not allow_missing) and
            not (math.isfinite(lat_deg) and -90 <= lat_deg <= 90)):
        raise ValueError("latitude must be finite and in [-90, 90]")
    if ((lon_deg is not None or not allow_missing) and
            not (math.isfinite(lon_deg) and -180 <= lon_deg <= 180)):
        raise ValueError("longitude must be finite and in [-180, 180]")


def ascendant_tropical(jd_ut, jd_tt, lat_deg, lon_deg, eot_minutes=0.0):
    """Eastern rising intersection of mean ecliptic and geometric horizon.

    jd_ut is UT1, jd_tt is TT; longitude is east-positive. The retained
    eot_minutes argument is ignored: EOT belongs to solar clocks, not GMST.
    Return None where rising is undefined (pole, tangency, coincident planes).
    This is a mean-frame geometric quantity, not an apparent/refracted angle.
    """
    _validate_location(lat_deg, lon_deg)
    theta = math.radians(norm_deg(gmst_degrees(jd_ut) + lon_deg))
    eps = math.radians(mean_obliquity_deg(jd_tt))
    phi = math.radians(lat_deg)
    if abs(math.cos(phi)) < 1e-12:
        return None
    # Horizon normal dotted into (cos(lambda), cos(eps)*sin(lambda),
    # sin(eps)*sin(lambda)) gives A*cos(lambda)+B*sin(lambda)=0.
    a = math.cos(phi) * math.cos(theta)
    b = math.cos(phi) * math.sin(theta) * math.cos(eps) + math.sin(phi) * math.sin(eps)
    length = math.hypot(a, b)
    if length < 1e-12:
        return None
    x, y = b / length, -a / length
    east = -math.sin(theta) * x + math.cos(theta) * math.cos(eps) * y
    if abs(east) < 1e-12:
        return None
    if east < 0:
        x, y = -x, -y
    return norm_deg(math.degrees(math.atan2(y, x)))


def solar_altitude_deg(jd_ut, jd_tt, lat_deg, lon_deg):
    """Geometric geocentric solar-centre altitude in mean-equator-of-date frame, degrees.

    Uses VSOP87 mean-ecliptic-of-date Sun longitude paired with GMST.
    No atmospheric refraction, terrain, dip or parallax model.
    """
    _validate_location(lat_deg, lon_deg)
    lam = math.radians(sun_geometric_longitude(jd_tt))
    eps = math.radians(mean_obliquity_deg(jd_tt))
    theta = math.radians(norm_deg(gmst_degrees(jd_ut) + lon_deg))
    phi = math.radians(lat_deg)
    up = (math.cos(phi) * (math.cos(theta) * math.cos(lam) +
          math.sin(theta) * math.cos(eps) * math.sin(lam)) +
          math.sin(phi) * math.sin(eps) * math.sin(lam))
    return math.degrees(math.asin(max(-1.0, min(1.0, up))))


def sunrise_sunset_utc(jd_ut_noon, lat_deg, lon_deg):
    """日出日落 UTC 时刻（小时偏移自当日 UTC 0 点）。Meeus ch.15 简式。

    返回 (日出小时, 日落小时, 极昼/极夜标记)。
    """
    T = (jd_ut_noon - J2000) / 36525.0
    # 当日 UTC 0 点太阳平黄经与平近点角
    jd0 = math.floor(jd_ut_noon - 0.5) + 0.5
    T0 = (jd0 - J2000) / 36525.0
    L0 = norm_deg(280.46646 + 36000.76983 * T0)
    M = math.radians(norm_deg(357.52911 + 35999.05029 * T0))
    C = 1.914602 * math.sin(M) + 0.019993 * math.sin(2 * M) + 0.000289 * math.sin(3 * M)
    true_lon = norm_deg(L0 + C)
    eps = math.radians(mean_obliquity_deg(jd0))
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(math.radians(true_lon))))
    lat = math.radians(lat_deg)
    cos_h = (math.sin(math.radians(-0.833)) - math.sin(lat) * math.sin(math.radians(dec))) / (
        math.cos(lat) * math.cos(math.radians(dec)))
    if cos_h > 1:
        return None, None, "极夜"
    if cos_h < -1:
        return None, None, "极昼"
    h = math.degrees(math.acos(cos_h))
    solar_noon_ut = 12.0 - lon_deg / 15.0 - equation_of_time_minutes(jd0) / 60.0
    # 恒星时修正：太阳赤经日变化 ≈ 3.94 分钟/天，并入 noon 修正
    sunrise = solar_noon_ut - h / 15.0
    sunset = solar_noon_ut + h / 15.0
    return sunrise, sunset, None


# ---------------------------------------------------------------------------
# 安命宫
# ---------------------------------------------------------------------------

def ming_gong_zhi(sun_palace_zhi, hour_zhi):
    """安命宫：《果老星宗》「以生时加太阳之宫，顺数至卯」。

    命宫支 = 太阳宫支 + (卯 − 生时支) mod 12。
    古典例：太阳子宫+子时生→卯宫；太阳子宫+丑时生→寅宫；太阳酉宫+午时生→午宫。
    """
    offset = (3 - ZHI.index(hour_zhi)) % 12
    return ZHI[(ZHI.index(sun_palace_zhi) + offset) % 12]


# ---------------------------------------------------------------------------
# 恩用难仇
# ---------------------------------------------------------------------------

def en_yong_chou_nan(du_zhu_wuxing):
    """以命度宿五行（度主）为我，分十一曜入恩用仇难（口径声明第 7 条）。"""
    groups = {"恩": [], "用": [], "仇": [], "难": [], "同": []}
    for lum in LUMINARIES:
        wx = LUMINARIES_WUXING[lum]
        if wx == WUXING_SHENGWO[du_zhu_wuxing]:      # 生我 → 恩
            groups["恩"].append(lum)
        elif wx == WUXING_SHENGKE[du_zhu_wuxing]:    # 我生 → 用
            groups["用"].append(lum)
        elif wx == WUXING_KEWO[du_zhu_wuxing]:       # 克我 → 难
            groups["难"].append(lum)
        elif wx == WUXING_WOKE[du_zhu_wuxing]:       # 我克 → 仇
            groups["仇"].append(lum)
        else:
            groups["同"].append(lum)
    return groups


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def compute(solar_date, hour, minute, lat, lon, place=None, birth_instant=None,
            profile="calibrated-v3", dut1_seconds=0.0, analysis_year=None, target_instant=None):
    """排七政四余盘。solar_date=(y,m,d) 公历；hour/minute 北京钟表；lat/lon 度。

    缺 lat/lon 时不计命度/立命宫/昼夜生/恩用难仇/洞微大限，只出十一曜躔度、身宫与年干变曜神煞。
    指定 analysis_year 或 target_instant 时，同步计算目标年/时刻的洞微限宫限度与流年太岁交汇。
    """
    if profile not in ("calibrated-v3", "legacy-v1"):
        raise ValueError("unknown qizheng calculation profile: " + str(profile))
    if (type(dut1_seconds) not in (int, float)
            or not -0.9 <= dut1_seconds <= 0.9
            or not math.isfinite(dut1_seconds)):
        raise ValueError("dut1_seconds must be finite and within +/-0.9 s (modern UTC)")
    if profile == "legacy-v1" and dut1_seconds != 0:
        raise ValueError("legacy-v1 requires dut1_seconds=0 for reproducibility")
    _validate_location(lat, lon, allow_missing=True)
    is_legacy = profile == "legacy-v1"
    warnings = ["legacy-v1: known incorrect horizon, clock, and uncalibrated 28-mansion table retained for reproduction only"] if is_legacy else []
    dt_bj = datetime(solar_date[0], solar_date[1], solar_date[2], hour, minute, tzinfo=BJ)
    if birth_instant is not None:
        if birth_instant.utcoffset() is None:
            raise ValueError("birth_instant 必须带明确 UTC 偏移")
        dt_bj = birth_instant.astimezone(BJ)
        hour, minute = dt_bj.hour, dt_bj.minute
    resolved_target = None
    if target_instant is not None:
        if target_instant.utcoffset() is None:
            raise ValueError("target_instant 必须带明确 UTC 偏移")
        resolved_target = target_instant.astimezone(BJ)
        if resolved_target < dt_bj:
            raise ValueError("target_instant (%s) 不能早于出生时刻 (%s)" % (
                resolved_target.isoformat(), dt_bj.isoformat()))
    elif analysis_year is not None:
        ay = int(analysis_year)
        if ay < dt_bj.year:
            raise ValueError("analysis_year (%d) 不能早于出生年份 (%d)" % (ay, dt_bj.year))
        mid_year = datetime(ay, 7, 1, 12, 0, tzinfo=BJ)
        resolved_target = mid_year if mid_year >= dt_bj else dt_bj
    dt_utc = dt_bj.astimezone(timezone.utc)
    jd_utc = jd_from_utc(dt_utc)
    jd_ut = jd_utc + dut1_seconds / 86400.0
    jd_tt = jd_ut + delta_t_seconds(dt_utc.year) / 86400.0

    sun = sun_apparent_longitude(jd_tt) if is_legacy else sun_geometric_longitude(jd_tt)
    moon = moon_longitude(jd_tt, model="legacy-v1" if is_legacy else "meeus-truncated-geometric-v2")

    def planet_at_instant(name):
        return (planet_longitude(name, jd_ut, model="legacy-v1") if is_legacy
                else planet_longitude_tt(name, jd_tt))

    bodies_tropical = {
        "日": sun, "月": moon,
        "木": planet_at_instant("jupiter"),
        "火": planet_at_instant("mars"),
        "土": planet_at_instant("saturn"),
        "金": planet_at_instant("venus"),
        "水": planet_at_instant("mercury"),
        "罗睺": rahu_longitude(jd_tt),
        "计都": ketu_longitude(jd_tt),
        "月孛": yuebei_longitude(jd_tt),
        "紫气": purple_qi_longitude(jd_ut),
    }
    ayan = spica_ayanamsa(jd_tt, profile=profile)
    frame_contract = star_frame_contract(jd_tt, legacy=is_legacy)
    epoch_mansions = mansions_for_epoch(jd_tt, profile=profile)
    epoch_palaces = palaces_for_epoch(jd_tt, profile=profile)
    mansion_starts = [m[2] for m in epoch_mansions]
    if not is_legacy and not frame_contract["within_validated_range"]:
        warnings.append("日期超出 1900–2100 星历与岁差验证范围")

    bodies = {}
    for name, trop in bodies_tropical.items():
        sid = to_sidereal(trop, jd_tt, profile=profile)
        m_name, m_deg, m_wx, m_star = mansion_of(sid, mansions=epoch_mansions)
        palace = palace_of(sid, palaces=epoch_palaces)
        bodies[name] = {
            "tropical": trop, "sidereal": sid, "ayanamsa": ayan,
            "mansion": m_name, "mansion_deg": m_deg, "mansion_wx": m_wx, "star": m_star,
            "palace": palace,
        }
        if not is_legacy:
            bodies[name]["classification_quality"] = boundary_diagnostic(sid, mansion_starts, validated=True)
            if bodies[name]["classification_quality"]["near_boundary"]:
                warnings.append("%s接近校准宿界（距界 %.3f° ≤ 0.1°）；跨宿/跨宫判读需兼看邻宿" % (
                    name, bodies[name]["classification_quality"]["distance_to_boundary_deg"]))

    sun_palace = bodies["日"]["palace"]

    result = {
        "jd_ut": jd_ut,
        "jd_utc": jd_utc,
        "jd_tt": jd_tt,
        "calculation_profile": profile,
        "model_provenance": model_provenance(profile),
        "star_frame_contract": frame_contract,
        "ephemeris_contract": {
            "planets": "legacy-v1" if is_legacy else "schlyter-geometric-v2",
            "moon": "legacy-v1" if is_legacy else "meeus-truncated-geometric-v2",
            "sun": "Meeus low-order approximate apparent longitude" if is_legacy else "vsop87-geometric-mean-ecliptic-v3",
            "frame_note": "legacy mixed frame" if is_legacy else "mean ecliptic/equinox of date; VSOP87 Sun (<0.4 arcsec) + Schlyter/Meeus planets/Moon (<0.055 deg on 1900-2100 JPL grid); virtual points follow explicit conventions",
        },
        "horizon_contract": {
            "frame": "mean equator/ecliptic of date; geometric horizon",
            "sidereal_time": "legacy mixed units" if is_legacy else "GMST(UT1)+east longitude; no EOT",
            "dut1_seconds": dut1_seconds,
            "utc_is_ut1_approximation": dut1_seconds == 0.0,
            "tt_source": "UT1 + polynomial Delta T estimate (not measured EOP)",
            "day_night": "legacy mixed clocks" if is_legacy else "instant geometric solar-centre altitude >= -0.833 deg",
            "ming_gong_clock": "Beijing civil hour, independent traditional rule",
        },
        "ayanamsa": ayan,
        "bodies": bodies,
        "sun_palace_zhi": sun_palace,
        "eot_minutes": equation_of_time_minutes(jd_ut),
    }

    if lat is None or lon is None:
        if is_legacy:
            warnings.append("未提供经纬度（--lat --lon）：命度、立命宫、昼夜生、恩用难仇未计算，只出十一曜躔度")
        else:
            warnings.append("未提供经纬度（--lat --lon）：命度、立命宫、昼夜生、恩用难仇、洞微大限未计算；已保留十一曜躔度、身宫/身主/身度、星辰状态、年干变曜与神煞")
        result.update({"ming_du": None, "ming_gong": None, "day_night": None, "en_yong": None})
        if not is_legacy:
            year_gz_info = year_ganzhi_at_instant(dt_bj)
            result["year_gz"] = year_gz_info
            result["shen_gong"] = compute_shen_gong(bodies, twelve_houses=None)
            result["twelve_houses"] = None
            result["star_states"] = compute_star_states(bodies, day_night_type=None)
            result["bianyao_shensha"] = compute_bianyao_shensha(
                year_gz_info["year_gan"], year_gz_info["year_zhi"],
                ming_gong_zhi=None, day_night_type=None, bodies=bodies,
            )
        return result, warnings

    if lat < 0:
        warnings.append("南半球几何可计算；传统命理解读适用性未验证")

    asc_func = legacy_ascendant_tropical if is_legacy else ascendant_tropical
    asc_trop = asc_func(jd_ut, jd_tt, lat, lon, result["eot_minutes"])
    ming_du = None
    m_wx = None
    if asc_trop is not None:
        asc_sid = to_sidereal(asc_trop, jd_tt, profile=profile)
        m_name, m_deg, m_wx, m_star = mansion_of(asc_sid, mansions=epoch_mansions)
        ming_du = {
            "tropical": asc_trop, "sidereal": asc_sid,
            "mansion": m_name, "mansion_deg": m_deg, "wuxing": m_wx, "star": m_star,
            "palace": palace_of(asc_sid, palaces=epoch_palaces),
        }
        if not is_legacy:
            ming_du["classification_quality"] = boundary_diagnostic(asc_sid, mansion_starts, validated=True)
    else:
        warnings.append("东方上升交点在极点/相切/重合地平几何下未定义；不输出命度或恩用难仇")
    hour_zhi = _hour_to_shichen(hour, minute)
    ming_gong = ming_gong_zhi(sun_palace, hour_zhi)

    if not is_legacy:
        altitude = solar_altitude_deg(jd_ut, jd_tt, lat, lon)
        day_night = {"type": "昼生" if altitude >= -0.833 else "夜生",
                     "solar_altitude_deg": altitude, "threshold_deg": -0.833,
                     "method": "instant-geometric-solar-centre",
                     "note": "标准日出阈值近似，不含实测大气、地形或海拔；不据单个时刻宣称极昼极夜"}
    else:
        jd_noon = jd_ut
        sr, ss, polar = sunrise_sunset_utc(jd_noon, lat, lon)
        utc_hours = ((jd_ut + 0.5) % 1.0) * 24.0
        local_hours = utc_hours + lon / 15.0
        if polar:
            day_night = {"type": polar, "note": "极昼/极夜，昼夜生传统口径不适用"}
        else:
            local_apparent = local_hours + result["eot_minutes"] / 60.0
            sr_local = (sr + lon / 15.0) % 24.0
            ss_local = (ss + lon / 15.0) % 24.0
            if sr_local <= local_apparent < ss_local:
                day_night = {"type": "昼生", "sunrise_local": sr_local, "sunset_local": ss_local}
            else:
                day_night = {"type": "夜生", "sunrise_local": sr_local, "sunset_local": ss_local}

    result["ming_du"] = ming_du
    result["ming_gong"] = {
        "zhi": ming_gong, "wuxing": PALACE_WUXING[ming_gong],
        "ruler": PALACE_RULER[ming_gong], "ruler_wuxing": PALACE_RULER_WUXING[ming_gong],
        "sun_palace": sun_palace, "hour_zhi": hour_zhi,
    }
    result["day_night"] = day_night
    result["du_zhu_wuxing"] = MANSION_WX_TO_PHASE[m_wx] if m_wx is not None else None
    result["en_yong"] = en_yong_chou_nan(result["du_zhu_wuxing"]) if m_wx is not None else None
    if not is_legacy:
        year_gz_info = year_ganzhi_at_instant(dt_bj)
        twelve_houses = build_twelve_houses(ming_gong, bodies)
        shen_gong = compute_shen_gong(bodies, twelve_houses=twelve_houses)
        dn_type = day_night["type"] if day_night else None
        star_states = compute_star_states(bodies, day_night_type=dn_type)
        bianyao_shensha = compute_bianyao_shensha(
            year_gz_info["year_gan"], year_gz_info["year_zhi"],
            ming_gong_zhi=ming_gong, day_night_type=dn_type, bodies=bodies,
        )
        result["year_gz"] = year_gz_info
        result["twelve_houses"] = twelve_houses
        result["shen_gong"] = shen_gong
        result["star_states"] = star_states
        result["bianyao_shensha"] = bianyao_shensha
        import qizheng_dynamics as qd
        result["dongwei_daxian"] = qd.compute_dongwei_daxian(dt_bj, result, target_dt_bj=resolved_target)
        if resolved_target is not None:
            result["dynamic_overview"] = qd.compute_transit_snapshot(result, resolved_target, birth_dt_bj=dt_bj)
        else:
            result["dynamic_overview"] = None
        result["classification_contract"] = {
            "mansion_and_palace": "calibrated-simbad-icrs-epoch-v3",
            "ming_gong": "traditional Guolao rule using calibrated solar palace and Beijing civil hour",
            "shen_gong": "Guolao orthodox moon-palace rule (太阴所在宫=身宫，宫主=身主)",
            "bianyao_shensha": "Guolao Xingzong Vol. 2 ten-stem bianyao & year stem/branch shensha (Lichun year boundary)",
            "dongwei_daxian": "Xingxue Dacheng / Zhangguo Xingzong solar-degree Dongwei Bailiu (10+sun_norm_deg/3 + 10/11/15/8/7/11/4.5/4.5/4.5/5/5)",
            "en_yong": "derived from calibrated mansion element (度主)",
            "near_boundary": bool(ming_du and ming_du["classification_quality"]["near_boundary"]),
        }
        if result["classification_contract"]["near_boundary"]:
            warnings.append("命度接近校准宿界（≤ 0.1°）；度主与恩用难仇建议兼核邻宿")
    return result, warnings


def _hour_to_shichen(hour, minute):
    total = hour * 60 + minute
    if total >= 23 * 60 or total < 60:
        return "子"
    return ZHI[((hour + 1) // 2) % 12]


def format_report(result, warnings, meta):
    lines = []
    lines.append("## 输入")
    lines.append("- 阳历：%s %02d:%02d（北京时间）" % (meta["solar"], meta["hour"], meta["minute"]))
    place, lat, lon = (meta.get(key) for key in ("place", "lat", "lon"))
    if lat is not None and lon is not None:
        coordinates = "纬 %.2f，经 %.2f" % (lat, lon)
        lines.append("- 出生地：%s（%s）" % (place, coordinates) if place else "- 经纬度：" + coordinates)
    else:
        if place:
            lines.append("- 出生地：" + place)
        if lat is not None:
            lines.append("- 经纬度：纬 %.2f，经度未提供" % lat)
        elif lon is not None:
            lines.append("- 经纬度：纬度未提供，经 %.2f" % lon)
        else:
            lines.append("- 经纬度：未提供")
    lines.append("")
    lines.append("## 口径声明（详见文件头）")
    lines.append("- 恒星制，角宿一=0°，ayanamsa=%.4f°" % result["ayanamsa"])
    lines.append("- 计都=罗睺对冲；紫气=28岁周天锚点 1975-03-13 16:00 UT=230.5°")
    lines.append("- 计算配置：%s；几何/时间近似见 horizon_contract，不承诺统一角分精度" % result["calculation_profile"])
    lines.append("")
    lines.append("## 七政四余躔度")
    lines.append("| 星 | 黄道经度 | 恒星黄经 | 躔宿 | 入宿度 | 宿主 | 躔宫 |")
    lines.append("|---|---|---|---|---|---|---|")
    for name in LUMINARIES:
        b = result["bodies"][name]
        palace = b.get("palace") or palace_of(b["sidereal"])
        lines.append(
            "| %s | %.4f | %.4f | %s宿 | %.2f | %s | %s宫 |"
            % (name, b["tropical"], b["sidereal"], b["mansion"], b["mansion_deg"],
               b["mansion_wx"], palace)
        )
    lines.append("")
    md = result.get("ming_du")
    mg = result.get("ming_gong")
    if md is None:
        lines.append("## 命度")
        lines.append("- 命度/恩用难仇：未计算或东方上升交点未定义")
    else:
        if result["calculation_profile"] == "legacy-v1":
            lines.append("## 命度（旧版复现值，旧算法存在已知错误）")
        else:
            lines.append("## 命度（几何东方上升交点，恒星制）")
        lines.append("- 黄道经度：%.4f → 恒星 %.4f" % (md["tropical"], md["sidereal"]))
        lines.append("- 命躔：%s宿%.2f度（宿主：%s，度主五行：%s，距星 %s，所在 %s宫）" % (
            md["mansion"], md["mansion_deg"], md["wuxing"], result["du_zhu_wuxing"], md["star"],
            md.get("palace") or palace_of(md["sidereal"])))
    lines.append("")
    sg = result.get("shen_gong")
    if mg or sg:
        lines.append("## 立命宫与身宫（果老正宗）")
        if mg:
            lines.append("- 立命宫：%s宫（宫主 %s/%s，支五行 %s；太阳踞 %s 宫 + %s 时顺数至卯）" % (
                mg["zhi"], mg.get("ruler", ""), mg.get("ruler_wuxing", ""), mg["wuxing"],
                mg["sun_palace"], mg["hour_zhi"]))
        else:
            lines.append("- 立命宫：未提供经纬度，未计算")
        if sg:
            sd = sg["shen_du"]
            house_txt = ("（落%s）" % sg["house_name"]) if sg.get("house_name") else ""
            lines.append("- 身宫：%s宫%s｜身主：%s（五行 %s，落 %s宫 %s宿）｜身度：%s宿%.2f度（度主 %s）" % (
                sg["zhi"], house_txt, sg["shen_zhu"], sg["shen_zhu_wuxing"],
                sg.get("shen_zhu_palace") or "—", sg.get("shen_zhu_mansion") or "—",
                sd["mansion"], sd["mansion_deg"], sd["du_zhu_wuxing"]))
        lines.append("")
    if result.get("twelve_houses"):
        lines.append("## 十二人事宫（命宫起逆布）")
        lines.append("| 宫职 | 支宫 | 强弱 | 宫主 | 守曜 | 对宫照曜 |")
        lines.append("|---|---|---|---|---|---|")
        for h in result["twelve_houses"]:
            lines.append("| %s | %s(%s) | %s | %s(%s) | %s | %s(%s) |" % (
                h["name"], h["zhi"], h["constellation"], h["strength"],
                h["ruler"], h["ruler_wuxing"],
                "、".join(h["occupants"]) or "空",
                h["opposite_zhi"], "、".join(h["opposite_occupants"]) or "空",
            ))
        lines.append("")
    if result.get("star_states"):
        lines.append("## 星辰状态（升殿 / 喜宫歌 / 明晦）")
        lines.append("| 星 | 躔宿/宫 | 升殿 | 喜宫关系 | 入庙/乐宫 | 失陷 | 昼夜明晦 |")
        lines.append("|---|---|---|---|---|---|---|")
        for name in LUMINARIES:
            st = result["star_states"][name]
            tags = [t for t, ok in (("入庙", st["ru_miao"]), ("乐宫", st["le_gong"])) if ok]
            lines.append("| %s | %s宿·%s宫 | %s | %s | %s | %s | %s |" % (
                name, st["mansion"], st["palace"],
                "升殿" if st["shengdian"] else "—",
                st["xigong_relation"], "、".join(tags) or "—",
                st["shixian"] or "—", st.get("ming_hui") or "—",
            ))
        lines.append("")
    bs = result.get("bianyao_shensha")
    if bs:
        lines.append("## 年干变曜与年干支神煞（%s年 · 立春换年）" % bs["year_gz"])
        lines.append("| 化曜 | 管库宫 | 化星 | 落宫/躔宿 |")
        lines.append("|---|---|---|---|")
        for role, info in bs["bianyao"].items():
            loc = "%s宫 %s宿" % (info["palace"], info["mansion"]) if info["palace"] else "—"
            lines.append("| %s | %s | %s | %s |" % (role, info["managed_house"], info["star"], loc))
        ss = bs["stem_stars"]
        ps = bs["palace_shensha"]
        lines.append("- 年干诸星：科名=%s、科甲=%s、文星=%s、魁星=%s、官星=%s、印星=%s、催官=%s、禄神=%s、喜神=%s、爵星=%s、天马=%s、地驿=%s" % (
            ss["科名"]["star"], ss["科甲"]["star"] or "—", ss["文星"]["star"], ss["魁星"]["star"],
            ss["官星"]["star"], ss["印星"]["star"], ss["催官"]["star"],
            "/".join(x["star"] for x in ss["禄神"]), ss["喜神"]["star"],
            ss["爵星"]["star"], ss["天马"]["star"], ss["地驿"]["star"],
        ))
        ren_key = "阳刃" if "阳刃" in ps else "阴刃"
        lines.append("- 核心神煞：天乙=%s、玉堂=%s、文昌=%s、天厨=%s、岁驾=%s、岁殿=%s、禄勋=%s、%s=%s(刃星%s)、唐符=%s、国印=%s、劫杀=%s、亡神=%s、咸池=%s、孤辰=%s、寡宿=%s、空亡=%s" % (
            ps["天乙昼贵"], ps["玉堂夜贵"], ps["文昌"], ps["天厨"], ps["岁驾"], ps["岁殿"],
            ps["禄勋"], ren_key, ps[ren_key], ps["刃星"], ps["唐符飞刃"], ps["国印"],
            ps["劫杀"], ps["亡神"], ps["咸池"], ps["孤辰"], ps["寡宿"], "".join(ps["空亡"]),
        ))
        lines.append("- 驾后神煞：红鸾=%s、天喜=%s、血刃/解神=%s、天哭=%s、披头=%s" % (
            bs["jiahou"]["红鸾"], bs["jiahou"]["天喜"], bs["jiahou"]["血刃/浮沉/解神"],
            bs["jiahou"]["天哭"], bs["jiahou"]["披头"],
        ))
        lines.append("")
    dw = result.get("dongwei_daxian")
    if dw:
        lines.append("## 洞微大限（出童限折算法 · 总周 %.1f 年）" % dw["total_cycle_years"])
        lines.append("- 出童限：%.2f 岁（%s，太阳宫内归一化度 %.2f° → 命宫 %.2f 年；量天尺起度 %s宿%.2f°）" % (
            dw["chutongxian_age"], dw["chutongxian_date"], dw["sun_in_palace_norm_deg"],
            dw["ming_gong_years"], dw["liangtianchi_start"]["mansion"], dw["liangtianchi_start"]["mansion_deg"],
        ))
        lines.append("| 序 | 大限宫 | 支宫 | 限主 | 年限 | 岁数窗 | 公历窗 | 行经宿度 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        active_step = dw["active"]["palace_limit"]["step"] if dw.get("active") else None
        for st in dw["stages"]:
            mark = " ←目标" if st["step"] == active_step else ""
            lines.append("| %d | %s%s | %s | %s(%s) | %.2f年 | %.1f~%.1f | %s~%s | %s |" % (
                st["step"], st["house_name"], mark, st["zhi"], st["ruler"], st["ruler_wuxing"],
                st["duration_years"], st["start_age"], st["end_age"],
                st["start_date"], st["end_date"], "→".join(st["mansions_traversed"]),
            ))
        if dw.get("active"):
            act = dw["active"]
            pl, dl, xx = act["palace_limit"], act["degree_limit"], act["xiaoxian"]
            tongxian_txt = ("｜童限行%s" % act["tongxian_house"]) if act["in_tongxian"] else ""
            cycle_txt = (
                "｜第 %d 周回绕（%.1f~%.1f岁 / %s~%s）"
                % (act["cycle_index"] + 1, pl["start_age"], pl["end_age"], pl["start_date"], pl["end_date"])
                if act.get("cycle_index", 0) > 0
                else ""
            )
            lines.append("- 目标时刻（%s，实岁 %.2f）：限宫 %s(%s·%s)｜限度 %s宿%.2f°(度主%s，%s)｜小限 %s(%s宫)%s%s" % (
                act["target_bj"][:10], act["exact_age_years"], pl["house_name"], pl["zhi"],
                pl["relation_to_natal_duzhu"] or "—", dl["mansion"], dl["mansion_deg"],
                dl["du_zhu_wuxing"], dl["relation_to_natal_duzhu"] or "—", xx["house_name"], xx["zhi"],
                tongxian_txt, cycle_txt,
            ))
            if act["risk_signals"]:
                lines.append("- 行限提示：" + "；".join(act["risk_signals"]))
        lines.append("")
    dn = result.get("day_night")
    if dn:
        lines.append("## 昼夜生")
        if "solar_altitude_deg" in dn:
            lines.append("- %s；太阳中心几何高度 %.4f°，阈值 %.3f°；%s" % (dn["type"], dn["solar_altitude_deg"], dn["threshold_deg"], dn["note"]))
        elif dn["type"] in ("极昼", "极夜"):
            lines.append("- %s：%s" % (dn["type"], dn.get("note", "")))
        else:
            lines.append("- 日出（当地平太阳时）：%02d:%02d｜日落：%02d:%02d" % (
                int(dn["sunrise_local"]), int(round((dn["sunrise_local"] % 1) * 60)),
                int(dn["sunset_local"]), int(round((dn["sunset_local"] % 1) * 60))))
            lines.append("- 判定：%s" % dn["type"])
        lines.append("")
    lines.append("## 真太阳时副产品")
    lines.append("- 均时差：%.2f 分钟（真太阳时 = 平太阳时 %+d 分）" % (result["eot_minutes"], round(result["eot_minutes"])))
    lines.append("")
    lines.append("## 警告")
    if warnings:
        for w in warnings:
            lines.append("- %s" % w)
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(description="七政四余排盘（恒星制，无第三方依赖）")
    p.add_argument("--solar", required=True, help="阳历 YYYY-MM-DD")
    p.add_argument("--hour", required=True, help="出生钟点 HH:MM（北京时间）")
    p.add_argument("--lat", type=float, default=None, help="出生纬度（度，北正）")
    p.add_argument("--lon", type=float, default=None, help="出生经度（度，东正）")
    p.add_argument("--profile", choices=("calibrated-v3", "legacy-v1"), default="calibrated-v3")
    p.add_argument("--dut1-seconds", type=float, default=0.0, help="UT1−UTC 秒；默认 0 是近似，不是 EOP 实测")
    p.add_argument("--analysis-year", type=int, default=None, help="可选目标年份，用于标注洞微大限限宫/限度与流年太岁")
    p.add_argument("--place", help="出生地名称（仅展示）")
    return p


def run(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        y, m, d = (int(x) for x in args.solar.split("-"))
    except ValueError:
        parser.error("--solar 需要 YYYY-MM-DD")
        return 2
    try:
        hh, mm = (int(x) for x in args.hour.split(":"))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except ValueError:
        parser.error("--hour 需要 HH:MM")
        return 2

    try:
        result, warnings = compute(
            (y, m, d), hh, mm, args.lat, args.lon, args.place,
            profile=args.profile, dut1_seconds=args.dut1_seconds,
            analysis_year=args.analysis_year,
        )
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    report = format_report(result, warnings, {"solar": args.solar, "hour": hh, "minute": mm,
                                              "lat": args.lat, "lon": args.lon, "place": args.place})
    sys.stdout.write(report + "\n")
    return 0


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
