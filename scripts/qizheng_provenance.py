"""Dynamic local implementation hashes for Qizheng engine provenance."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "scripts/pai_pan_qizheng.py",
    "scripts/qizheng_star_frame.py",
    "scripts/qizheng_rules.py",
    "scripts/qizheng_dynamics.py",
    "scripts/qizheng_provenance.py",
    "scripts/astro_data/solar_longitude.json",
    "references/qizheng/states-tables.md",
)


def model_provenance(profile: str) -> dict:
    if profile not in ("calibrated-v3", "legacy-v1"):
        raise ValueError("Unknown calculation profile: " + str(profile))
    hashes = {}
    unavailable = {}
    for path in FILES:
        try:
            hashes[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        except OSError as exc:
            hashes[path] = None
            unavailable[path] = type(exc).__name__
    unresolved = (
        [
            "legacy-v1 retains historical bugs and uncalibrated 28-mansion table for replay only",
            "traditional high-latitude application unvalidated",
        ]
        if profile == "legacy-v1"
        else [
            "traditional high-latitude (>66.5 deg) astrological application unvalidated",
            "virtual point Ziqi (purple qi) is a school convention (1975-03-13 16:00 UT = 230.5 deg, 28yr period), not a physical body",
            "astronomical precision is not predictive validity",
        ]
    )
    result = {
        "calculation_profile": profile,
        "hash_purpose": "local implementation identity; not source-rights certification",
        "source_sha256": hashes,
        "virtual_points": {
            "rahu": "mean ascending lunar node (Meeus AA ch.47)",
            "ketu": "opposite mean node (rahu + 180 deg)",
            "yuebei": "mean lunar apogee (Meeus AA ch.47)",
            "ziqi": "conventional cycle (Moira/IThome): 1975-03-13 16:00 UT = 230.5 deg tropical; +360/10227.1792 deg/day",
        },
        "unresolved": unresolved,
    }
    if unavailable:
        result["unavailable_sources"] = unavailable
    return result
