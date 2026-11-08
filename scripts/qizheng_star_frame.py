"""Approximate Spica origin, not a calibrated 28-mansion boundary catalogue.

Runtime uses only stdlib. Source and numerical validation: docs/qizheng-star-frame.md.
The mean-frame model intentionally excludes annual aberration, nutation, parallax,
radial velocity/perspective acceleration and binary orbital motion. ICRS is treated
as FK5 J2000 within the stated approximation, not as an exact frame identity.
"""
import math

J2000 = 2451545.0
SPICA_RA_DEG = 201.298247375
SPICA_DEC_DEG = -11.161319472222222
SPICA_PM_RA_COSDEC_MAS_YR = -42.35
SPICA_PM_DEC_MAS_YR = -30.67
MODEL = "spica-mean-date-iau1976-pm-v2"
CATALOG_URL = "https://simbad.cds.unistra.fr/simbad/sim-basic?Ident=Spica"


def spica_mean_longitude(jd_tt):
    """Mean ecliptic/equinox-of-date longitude, TT Julian date, degrees.

    Tangent-vector proper motion from epoch J2000, then IAU 1976 equatorial
    precession and IAU 1980 mean obliquity. Validated for 1900–2100 only.
    This is a barycentric direction in a mean frame, not apparent star position.
    """
    if not math.isfinite(jd_tt):
        raise ValueError("jd_tt must be finite")
    t = (jd_tt - J2000) / 36525.0
    ra, dec = map(math.radians, (SPICA_RA_DEG, SPICA_DEC_DEG))
    x, y, z = math.cos(dec)*math.cos(ra), math.cos(dec)*math.sin(ra), math.sin(dec)
    scale = math.pi / (180 * 3600 * 1000) * (100 * t)
    a, d = SPICA_PM_RA_COSDEC_MAS_YR * scale, SPICA_PM_DEC_MAS_YR * scale
    x += -a*math.sin(ra) - d*math.sin(dec)*math.cos(ra)
    y += a*math.cos(ra) - d*math.sin(dec)*math.sin(ra)
    z += d*math.cos(dec)
    ra, dec = math.atan2(y, x), math.atan2(z, math.hypot(x, y))
    # Meeus ch.21 / IAU 1976, precession from J2000, angles in arcseconds.
    zeta = math.radians((2306.2181*t + .30188*t*t + .017998*t**3)/3600)
    zz = math.radians((2306.2181*t + 1.09468*t*t + .018203*t**3)/3600)
    theta = math.radians((2004.3109*t - .42665*t*t - .041833*t**3)/3600)
    a = math.cos(dec)*math.sin(ra+zeta)
    b = math.cos(theta)*math.cos(dec)*math.cos(ra+zeta) - math.sin(theta)*math.sin(dec)
    c = math.sin(theta)*math.cos(dec)*math.cos(ra+zeta) + math.cos(theta)*math.sin(dec)
    ra, dec = math.atan2(a, b)+zz, math.asin(max(-1, min(1, c)))
    eps = math.radians((84381.448 - 46.8150*t - .00059*t*t + .001813*t**3)/3600)
    return math.degrees(math.atan2(math.sin(ra)*math.cos(eps)+math.tan(dec)*math.sin(eps), math.cos(ra))) % 360


def star_frame_contract(jd_tt, legacy=False):
    return {
        "origin_model": "legacy-ra-as-longitude-v1" if legacy else MODEL,
        "catalog": {"name": "Spica / alpha Vir / HIP 65474", "source": CATALOG_URL,
                    "frame": "ICRS", "epoch": "J2000.0", "ra_deg": SPICA_RA_DEG,
                    "dec_deg": SPICA_DEC_DEG, "pm_ra_cosdec_mas_yr": SPICA_PM_RA_COSDEC_MAS_YR,
                    "pm_dec_mas_yr": SPICA_PM_DEC_MAS_YR},
        "output_frame": "legacy mixed frame" if legacy else "mean ecliptic and equinox of date",
        "time_scale": "TT; J2000 = JD 2451545.0 TT",
        "valid_year_range": [1900, 2100],
        "within_validated_range": 2415020.5 <= jd_tt < 2488434.5,
        "origin_model_comparison_tolerance_arcsec": None if legacy else 1.0,
        "omissions": ["ICRS/FK5 frame bias", "nutation", "annual aberration", "parallax",
                      "radial velocity/perspective acceleration", "binary orbital motion"],
        "mansion_boundary_model": "legacy-approximate-offsets-v1",
        "mansion_boundaries_validated": False,
        "mansion_boundary_error_deg": None,
        "note": "Origin correction does not validate or reconstruct mansion stars, boundaries, widths or traditional delineations.",
    }


def boundary_diagnostic(sidereal_lon, starts, margin_deg=0.1):
    """Screen proximity to model boundaries, NOT a measured error/confidence.

    Unknown catalogue/definition uncertainty prevents certifying even far-away
    classifications. The margin is an explicit heuristic sensitivity screen.
    """
    distance = min(abs((sidereal_lon-s+180) % 360-180) for s in starts)
    return {"distance_to_boundary_deg": distance, "screen_margin_deg": margin_deg,
            "near_boundary": distance <= margin_deg,
            "status": "boundary-sensitive" if distance <= margin_deg else "approximate-unvalidated",
            "boundary_error_deg": None, "validated": False}
