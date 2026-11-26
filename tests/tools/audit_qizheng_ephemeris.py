#!/usr/bin/env python3
"""Deterministic offline ephemeris, 28-mansion, horizon & day/night audit harness.

Compares scripts/pai_pan_qizheng.py and scripts/qizheng_star_frame.py against
committed NASA/JPL Horizons (404-point 1900-2100 vectors + 5 Observer benchmarks),
ERFA IAU2006 (201-year Spica series), and CDS SIMBAD ICRS J2000 28-star catalog.
Zero network calls at audit time; zero third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX_DIR = ROOT / "tests" / "fixtures"
QZ_FIX_DIR = FIX_DIR / "qizheng"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import pai_pan_qizheng as q  # noqa: E402
from qizheng_star_frame import spica_mean_longitude  # noqa: E402
from test_qizheng_ephemeris import mean_date_longitude  # noqa: E402


def _horizon_height(lon_deg: float, theta_deg: float, eps_deg: float, lat_deg: float) -> float:
    lam, ob, phi, st = map(math.radians, (lon_deg, eps_deg, lat_deg, theta_deg))
    ra = math.atan2(math.sin(lam) * math.cos(ob), math.cos(lam))
    dec = math.asin(max(-1.0, min(1.0, math.sin(lam) * math.sin(ob))))
    return math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(st - ra)


def run_audit(profile: str = "default") -> dict:
    if profile == "default":
        profile = inspect.signature(q.compute).parameters["profile"].default

    geom_data = json.loads((QZ_FIX_DIR / "geometric-vectors.json").read_text(encoding="utf-8"))
    sun_obs_data = json.loads((QZ_FIX_DIR / "sun-and-observer-reference.json").read_text(encoding="utf-8"))
    simbad_data = json.loads((QZ_FIX_DIR / "simbad-28-mansions.json").read_text(encoding="utf-8"))
    spica_erfa = json.loads((FIX_DIR / "spica_erfa_mean_date.json").read_text(encoding="utf-8"))

    sun_raw = (QZ_FIX_DIR / "sun-horizons.txt").read_bytes()
    sun_sha_ok = hashlib.sha256(sun_raw).hexdigest() == sun_obs_data["sun_vectors"]["sha256"]
    sun_errs = [
        abs(q.lon_delta(q.sun_geometric_longitude(jd), mean_date_longitude(jd, xyz)))
        for jd, *xyz in sun_obs_data["sun_vectors"]["vectors"]
    ]
    bodies_summary = {
        "sun": {
            "n": len(sun_errs),
            "sha256_ok": sun_sha_ok,
            "max_deg": max(sun_errs),
            "rms_deg": math.sqrt(sum(e * e for e in sun_errs) / len(sun_errs)),
            "max_arcsec": max(sun_errs) * 3600.0,
            "rms_arcsec": math.sqrt(sum(e * e for e in sun_errs) / len(sun_errs)) * 3600.0,
        }
    }

    for name, body in geom_data["bodies"].items():
        errs = []
        for jd, *xyz in body["vectors"]:
            actual = q.moon_longitude(jd) if name == "moon" else q.planet_longitude_tt(name, jd)
            errs.append(abs(q.lon_delta(actual, mean_date_longitude(jd, xyz))))
        bodies_summary[name] = {
            "n": len(errs),
            "max_deg": max(errs),
            "rms_deg": math.sqrt(sum(e * e for e in errs) / len(errs)),
            "max_arcsec": max(errs) * 3600.0,
            "rms_arcsec": math.sqrt(sum(e * e for e in errs) / len(errs)) * 3600.0,
        }

    jd_1975 = q.jd_from_utc(datetime(1975, 3, 13, 16, 0, tzinfo=timezone.utc))
    virtual_checks = {
        "ziqi_anchor_1975_err_deg": abs(q.lon_delta(q.purple_qi_longitude(jd_1975), 230.5)),
        "ketu_opposition_j2000_err_deg": abs(q.lon_delta(q.ketu_longitude(q.J2000), (q.rahu_longitude(q.J2000) + 180.0) % 360.0)),
        "rahu_j2000_deg": q.rahu_longitude(q.J2000),
        "yuebei_j2000_deg": q.yuebei_longitude(q.J2000),
    }

    spica_errs_arcsec = [abs(q.lon_delta(spica_mean_longitude(jd), exp)) * 3600.0 for _, jd, exp in spica_erfa["rows"]]

    # Non-circular J2000 comparison directly against SIMBAD fixture j2000_ecl_lon_deg;
    # other epochs verify monotonicity, 360° partition, and differential drift vs J2000.
    spica_j2000_ref = simbad_data["stars"][0]["j2000_ecl_lon_deg"]
    j2000_eng = q.mansions_for_epoch(2451545.0, profile=profile)
    j2000_diffs = []
    worst = (0.0, "")
    for ref_star, eng_row in zip(simbad_data["stars"], j2000_eng):
        ref_off = (ref_star["j2000_ecl_lon_deg"] - spica_j2000_ref) % 360.0
        d = abs(q.lon_delta(eng_row[2], ref_off))
        j2000_diffs.append(d)
        if d > worst[0]:
            worst = (d, f"{ref_star['mansion']} (engine={eng_row[2]:.6f}, simbad_j2000={ref_off:.6f})")

    epoch_invariants = {}
    for yr, jd_tt in ((1900, 2415020.5), (2000, 2451545.0), (2026, 2461041.5), (2100, 2488069.5)):
        tbl = q.mansions_for_epoch(jd_tt, profile=profile)
        widths = [((tbl[(i + 1) % 28][2] - tbl[i][2]) % 360.0) for i in range(28)]
        drifts = [abs(q.lon_delta(tbl[i][2], j2000_eng[i][2])) for i in range(28)]
        epoch_invariants[str(yr)] = {
            "strictly_monotonic": all(w > 0.0 for w in widths),
            "min_width_deg": min(widths),
            "sum_widths_deg": sum(widths),
            "max_differential_drift_vs_j2000_deg": max(drifts),
        }

    mansion_evals = {
        "j2000_vs_simbad_fixture": {
            "max_err_deg": max(j2000_diffs),
            "rms_err_deg": math.sqrt(sum(d * d for d in j2000_diffs) / len(j2000_diffs)),
            "max_err_arcsec": max(j2000_diffs) * 3600.0,
            "worst_mansion": worst[1],
            "note": "Non-circular direct comparison against SIMBAD ICRS J2000 fixture; non-J2000 precession is externally ERFA-validated on Spica (201 yr) and shared across all 28 stars.",
        },
        "epoch_invariants_1900_2100": epoch_invariants,
    }

    obs_checks = []
    for row in sun_obs_data["observer_sun_benchmarks"]:
        dt = datetime.fromisoformat(row["utc"].replace("Z", "+00:00"))
        dt_bj = dt.astimezone(q.BJ)
        res, _ = q.compute((dt_bj.year, dt_bj.month, dt_bj.day), dt_bj.hour, dt_bj.minute,
                           row["lat"], row["lon"], birth_instant=dt, profile=profile)
        jd_ut = res["jd_ut"]
        jd_tt = jd_ut + q.delta_t_seconds(dt.year) / 86400.0
        alt_err = res["day_night"]["solar_altitude_deg"] - row["jpl_airless_sun_alt_deg"]
        expected_dn = "昼生" if row["jpl_airless_sun_alt_deg"] >= -0.833 else "夜生"
        asc = res["ming_du"]["tropical"]
        theta = (q.gmst_degrees(jd_ut) + row["lon"]) % 360.0
        eps = q.mean_obliquity_deg(jd_tt)
        asc_h = abs(_horizon_height(asc, theta, eps, row["lat"]))
        obs_checks.append({
            "name": row["name"],
            "jpl_alt_deg": row["jpl_airless_sun_alt_deg"],
            "engine_alt_deg": res["day_night"]["solar_altitude_deg"],
            "alt_err_deg": alt_err,
            "day_night_match": res["day_night"]["type"] == expected_dn,
            "day_night": res["day_night"]["type"],
            "asc_tropical_deg": asc,
            "asc_horizon_residual": asc_h,
            "ming_du": f"{res['ming_du']['mansion']}{res['ming_du']['mansion_deg']:.2f}°",
            "sun_mansion": f"{res['bodies']['日']['mansion']}{res['bodies']['日']['mansion_deg']:.2f}°",
        })

    return {
        "profile": profile,
        "bodies_vs_jpl_horizons_1900_2100": bodies_summary,
        "spica_vs_erfa_iau2006_201yr_max_arcsec": max(spica_errs_arcsec),
        "virtual_points": virtual_checks,
        "mansions_vs_simbad_icrs": mansion_evals,
        "observer_day_night_and_ascendant": obs_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Qizheng ephemeris, 28 mansions, and horizon accuracy")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run_audit(profile=args.profile)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
