"""Calibrated 28-mansion determinative-star frame (ICRS J2000 + proper motion + IAU 1976 precession).

Runtime uses only stdlib. Origin: Spica (alpha Vir, HIP 65474).
28 determinative stars: CDS SIMBAD / Hipparcos ICRS J2000 positions and proper motions,
using classical determinative stars phi1 Ori (觜) and zeta Ori (参) so all 28 mansions
remain strictly monotonic in ecliptic longitude (avoiding the J2000 lambda Ori / delta Ori
precession inversion). Spica precession is validated over 1900-2100 against ERFA IAU2006;
all 28 J2000 offsets match SIMBAD ICRS directly and share the same precession routine.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import NamedTuple

J2000 = 2451545.0
SPICA_RA_DEG = 201.298247375
SPICA_DEC_DEG = -11.161319472222222
SPICA_PM_RA_COSDEC_MAS_YR = -42.35
SPICA_PM_DEC_MAS_YR = -30.67
MODEL = "spica-mean-date-iau1976-pm-v2"
MANSION_MODEL = "simbad-icrs-28stars-iau1976-pm-v3"
PALACE_MODEL = "twelve-ci-mansion-aggregated-v3"
CATALOG_URL = "https://simbad.cds.unistra.fr/simbad/sim-basic?Ident=Spica"


class MansionStar(NamedTuple):
    mansion: str
    palace_zhi: str
    mansion_wx: str
    star_display: str
    hip: str
    ra_deg: float
    dec_deg: float
    pm_ra_cosdec_mas_yr: float
    pm_dec_mas_yr: float


MANSION_CATALOG: tuple[MansionStar, ...] = (
    MansionStar("角", "辰", "木", "α Vir", "HIP 65474", SPICA_RA_DEG, SPICA_DEC_DEG, SPICA_PM_RA_COSDEC_MAS_YR, SPICA_PM_DEC_MAS_YR),
    MansionStar("亢", "辰", "金", "κ Vir", "HIP 69427", 213.22393689, -10.27370346, 6.674, 138.987),
    MansionStar("氐", "卯", "土", "α² Lib", "HIP 72622", 222.71963789, -16.04177652, -105.68, -68.4),
    MansionStar("房", "卯", "日", "π Sco", "HIP 78265", 239.71297182, -26.11410795, -11.42, -26.83),
    MansionStar("心", "卯", "月", "σ Sco", "HIP 80112", 245.29714881, -25.59279208, -10.6, -16.28),
    MansionStar("尾", "寅", "火", "μ¹ Sco", "HIP 82514", 252.96761815, -38.04739946, -10.451, -18.315),
    MansionStar("箕", "寅", "水", "γ Sgr", "HIP 88635", 271.45203374, -30.42408985, -48.839, -204.86),
    MansionStar("斗", "丑", "木", "φ Sgr", "HIP 92041", 281.41412309, -26.99078265, 49.919, -0.09),
    MansionStar("牛", "丑", "金", "β Cap", "HIP 100345", 305.25277749, -14.7814076, 44.133, 0.36),
    MansionStar("女", "子", "土", "ε Aqr", "HIP 102618", 311.91895655, -9.49577693, 33.923, -34.936),
    MansionStar("虚", "子", "日", "β Aqr", "HIP 106278", 322.88971698, -5.57117483, 19.214, -8.163),
    MansionStar("危", "亥", "月", "α Aqr", "HIP 109074", 331.44598144, -0.31985096, 18.59, -10.45),
    MansionStar("室", "亥", "火", "α Peg", "HIP 113963", 346.19022269, 15.20526715, 60.4, -41.3),
    MansionStar("壁", "亥", "水", "γ Peg", "HIP 1067", 3.30896812, 15.18359843, 0.492, -10.73),
    MansionStar("奎", "戌", "木", "η And", "HIP 4463", 14.30166783, 23.41765002, -43.008, -45.254),
    MansionStar("娄", "戌", "金", "β Ari", "HIP 8903", 28.66004579, 20.80803147, 98.74, -110.41),
    MansionStar("胃", "酉", "土", "35 Ari", "HIP 12719", 40.86297616, 27.70714941, 8.502, -11.433),
    MansionStar("昴", "酉", "日", "17 Tau", "HIP 17499", 56.21890454, 24.11333785, 20.542, -46.081),
    MansionStar("毕", "酉", "月", "ε Tau", "HIP 20889", 67.15416773, 19.18043421, 107.526, -36.2),
    MansionStar("觜", "申", "火", "φ¹ Ori", "HIP 26176", 83.70515678, 9.48958622, 2.961, -2.456),
    MansionStar("参", "申", "水", "ζ Ori", "HIP 26727", 85.18969443, -1.94257359, 3.19, 2.03),
    MansionStar("井", "未", "木", "μ Gem", "HIP 30343", 95.74011193, 22.51358275, 56.39, -110.03),
    MansionStar("鬼", "未", "金", "θ Cnc", "HIP 41822", 127.89887483, 18.09441817, -59.639, -56.615),
    MansionStar("柳", "午", "土", "δ Hya", "HIP 42313", 129.41403114, 5.70378776, -68.867, -7.551),
    MansionStar("星", "午", "日", "α Hya", "HIP 46390", 141.8968446, -8.65859953, -15.23, 34.37),
    MansionStar("张", "午", "月", "υ¹ Hya", "HIP 48356", 147.86947908, -14.84662871, 31.037, -26.862),
    MansionStar("翼", "巳", "火", "α Crt", "HIP 53740", 164.94360482, -18.29878622, -462.303, 128.614),
    MansionStar("轸", "巳", "水", "γ Crv", "HIP 59803", 183.95154504, -17.54193046, -158.61, 21.86),
)

# Twelve-ci palace sequence ordered along increasing sidereal longitude from Spica (角=0°).
PALACE_SEQUENCE_SIDEREAL = ("辰", "卯", "寅", "丑", "子", "亥", "戌", "酉", "申", "未", "午", "巳")
PALACE_LEAD_MANSION = {
    "辰": "角", "卯": "氐", "寅": "尾", "丑": "斗",
    "子": "女", "亥": "危", "戌": "奎", "酉": "胃",
    "申": "觜", "未": "井", "午": "柳", "巳": "翼",
}


def star_mean_longitude(ra_deg: float, dec_deg: float, pm_ra_cosdec_mas_yr: float,
                        pm_dec_mas_yr: float, jd_tt: float) -> float:
    """Mean ecliptic/equinox-of-date longitude (deg) from ICRS J2000 + proper motion."""
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    t = (jd_tt - J2000) / 36525.0
    ra, dec = map(math.radians, (ra_deg, dec_deg))
    x, y, z = math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)
    scale = math.pi / (180.0 * 3600.0 * 1000.0) * (100.0 * t)
    a, d = pm_ra_cosdec_mas_yr * scale, pm_dec_mas_yr * scale
    x += -a * math.sin(ra) - d * math.sin(dec) * math.cos(ra)
    y += a * math.cos(ra) - d * math.sin(dec) * math.sin(ra)
    z += d * math.cos(dec)
    ra, dec = math.atan2(y, x), math.atan2(z, math.hypot(x, y))
    # Meeus ch.21 / IAU 1976 equatorial precession from J2000 (arcsec).
    zeta = math.radians((2306.2181 * t + 0.30188 * t * t + 0.017998 * t**3) / 3600.0)
    zz = math.radians((2306.2181 * t + 1.09468 * t * t + 0.018203 * t**3) / 3600.0)
    theta = math.radians((2004.3109 * t - 0.42665 * t * t - 0.041833 * t**3) / 3600.0)
    a1 = math.cos(dec) * math.sin(ra + zeta)
    b1 = math.cos(theta) * math.cos(dec) * math.cos(ra + zeta) - math.sin(theta) * math.sin(dec)
    c1 = math.sin(theta) * math.cos(dec) * math.cos(ra + zeta) + math.cos(theta) * math.sin(dec)
    ra, dec = math.atan2(a1, b1) + zz, math.asin(max(-1.0, min(1.0, c1)))
    eps = math.radians((84381.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t**3) / 3600.0)
    return math.degrees(math.atan2(math.sin(ra) * math.cos(eps) + math.tan(dec) * math.sin(eps), math.cos(ra))) % 360.0


def spica_mean_longitude(jd_tt: float) -> float:
    """Spica (alpha Vir) mean ecliptic/equinox-of-date longitude, TT Julian date, degrees."""
    return star_mean_longitude(
        SPICA_RA_DEG, SPICA_DEC_DEG, SPICA_PM_RA_COSDEC_MAS_YR, SPICA_PM_DEC_MAS_YR, jd_tt
    )


@lru_cache(maxsize=256)
def _calibrated_mansions_cached(jd_tt_rounded: float):
    origin = spica_mean_longitude(jd_tt_rounded)
    raw = []
    for s in MANSION_CATALOG:
        lon = origin if s.mansion == "角" else star_mean_longitude(
            s.ra_deg, s.dec_deg, s.pm_ra_cosdec_mas_yr, s.pm_dec_mas_yr, jd_tt_rounded
        )
        off = 0.0 if s.mansion == "角" else (lon - origin) % 360.0
        raw.append((s.mansion, s.star_display, off, s.mansion_wx, s.palace_zhi, s.hip, lon))
    out = []
    for i, (name, star, off, wx, palace, hip, lon) in enumerate(raw):
        nxt_off = 360.0 if i == len(raw) - 1 else raw[i + 1][2]
        width = nxt_off - off
        if width <= 0:
            raise ValueError(f"Non-monotonic mansion boundary at {name} for jd_tt={jd_tt_rounded}")
        out.append((name, star, off, wx, palace, width, hip, lon))
    return tuple(out)


def calibrated_mansions(jd_tt: float):
    """Return 28 epoch-calibrated mansion tuples at jd_tt relative to Spica = 0°.

    Each tuple: (mansion, star, start_sidereal_deg, wx, palace, width_deg, hip, mean_ecl_lon_deg).
    Quantizes cache key to 0.01 day (~14 min; proper-motion drift in 14 min is <1e-9 deg).
    """
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    return _calibrated_mansions_cached(round(float(jd_tt), 2))


def calibrated_palaces(mansions=None) -> dict[str, tuple[float, float]]:
    """Aggregate 12-branch palace boundaries directly from the 28-mansion table."""
    tbl = CALIBRATED_MANSIONS_J2000 if mansions is None else mansions
    start_by_mansion = {row[0]: row[2] for row in tbl}
    palaces: dict[str, tuple[float, float]] = {}
    for idx, zhi in enumerate(PALACE_SEQUENCE_SIDEREAL):
        lo = start_by_mansion[PALACE_LEAD_MANSION[zhi]]
        hi = 360.0 if idx == len(PALACE_SEQUENCE_SIDEREAL) - 1 else start_by_mansion[PALACE_LEAD_MANSION[PALACE_SEQUENCE_SIDEREAL[idx + 1]]]
        palaces[zhi] = (lo, hi)
    return palaces


CALIBRATED_MANSIONS_J2000 = tuple((m[0], m[1], m[2], m[3]) for m in calibrated_mansions(J2000))
CALIBRATED_PALACES_J2000 = calibrated_palaces(calibrated_mansions(J2000))


def star_frame_contract(jd_tt: float, legacy: bool = False) -> dict:
    return {
        "origin_model": "legacy-ra-as-longitude-v1" if legacy else MODEL,
        "catalog": {
            "name": "Spica / alpha Vir / HIP 65474 + 27 SIMBAD ICRS determinative stars",
            "source": CATALOG_URL,
            "frame": "ICRS",
            "epoch": "J2000.0",
            "ra_deg": SPICA_RA_DEG,
            "dec_deg": SPICA_DEC_DEG,
            "pm_ra_cosdec_mas_yr": SPICA_PM_RA_COSDEC_MAS_YR,
            "pm_dec_mas_yr": SPICA_PM_DEC_MAS_YR,
        },
        "output_frame": "legacy mixed frame" if legacy else "mean ecliptic and equinox of date",
        "time_scale": "TT; J2000 = JD 2451545.0 TT",
        "valid_year_range": [1900, 2100],
        "within_validated_range": 2415020.5 <= jd_tt < 2488434.5,
        "origin_model_comparison_tolerance_arcsec": None if legacy else 1.0,
        "omissions": [
            "ICRS/FK5 frame bias", "nutation", "annual aberration", "parallax",
            "radial velocity/perspective acceleration", "binary orbital motion",
        ],
        "mansion_boundary_model": "legacy-approximate-offsets-v1" if legacy else MANSION_MODEL,
        "mansion_boundaries_validated": not legacy,
        "mansion_boundary_error_deg": None if legacy else 0.001,
        "mansion_convention": (
            "legacy uncalibrated offsets"
            if legacy
            else "SIMBAD ICRS 28 classical determinative stars (phi1 Ori for 觜, zeta Ori for 参; epoch-precessed, strictly monotonic)"
        ),
        "palace_boundary_model": "legacy-approximate-palaces-v1" if legacy else PALACE_MODEL,
        "note": (
            "legacy-v1 retains historical uncalibrated offsets for replay only."
            if legacy
            else "All 28 determinative stars match SIMBAD ICRS J2000 and share the ERFA-validated IAU1976+PM precession routine; 12 palaces aggregate directly from calibrated mansion boundaries."
        ),
    }


def boundary_diagnostic(sidereal_lon: float, starts, margin_deg: float = 0.1, validated: bool = True) -> dict:
    """Screen proximity to mansion boundaries relative to the ephemeris budget."""
    distance = min(abs((sidereal_lon - s + 180.0) % 360.0 - 180.0) for s in starts)
    near = distance <= margin_deg
    if validated:
        status = "boundary-sensitive" if near else "calibrated"
        err_bound = 0.06
    else:
        status = "boundary-sensitive" if near else "approximate-unvalidated"
        err_bound = None
    return {
        "distance_to_boundary_deg": distance,
        "screen_margin_deg": margin_deg,
        "near_boundary": near,
        "status": status,
        "boundary_error_deg": err_bound,
        "validated": validated,
    }
