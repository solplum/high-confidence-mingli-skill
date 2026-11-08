"""Dynamic local implementation hashes, not proof of astronomical accuracy."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('scripts/pai_pan_qizheng.py', 'scripts/qizheng_star_frame.py',
         'scripts/qizheng_provenance.py', 'scripts/qizheng_rule_profiles.py',
         'knowledge/qizheng-rule-sources.json', 'docs/qizheng-ephemeris.md',
         'docs/qizheng-horizon-contract.md', 'docs/qizheng-star-frame.md',
         'docs/qizheng-rule-profiles.md')


def model_provenance(profile):
    if profile not in ('physical-v2', 'legacy-v1'):
        raise ValueError('Unknown calculation profile')
    return {'calculation_profile': profile,
            'hash_purpose': 'local implementation identity; not correctness or source-rights certification',
            'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES},
            'virtual_points': {'rahu': 'mean ascending lunar node', 'ketu': 'opposite mean node',
                               'yuebei': 'mean lunar apogee',
                               'ziqi': 'conventional cycle: 1975-03-13 16:00 UT = 230.5 deg; period 10227.1792 days'},
            'unresolved': ['28-mansion boundaries uncalibrated; error unknown',
                           'traditional high-latitude application unvalidated',
                           'sampled numerical agreement is not predictive validity']}
