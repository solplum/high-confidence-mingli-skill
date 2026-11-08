"""Optional DE441 numerical audit, not a runtime dependency or HKO download.

Install pyswisseph separately; supply official sepl_18.se1/semo_18.se1 files.
Explicit Swiss flags reject silent Moshier fallback. Inputs are synthetic.
"""
import sys, json, hashlib
from pathlib import Path
from datetime import timedelta
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ephemeris-dir', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import swisseph as swe
import pai_pan_bazi as b
ROOT=args.output_dir
ROOT.mkdir(parents=True, exist_ok=True)
swe.set_ephe_path(str(args.ephemeris_dir))
EXPECTED_SHA256 = {'semo_18.se1': '1ca07bd67c24374d77226180c20a4f9996cba013697894810518e7eb582ca4f7', 'sepl_18.se1': 'ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66'}
for name, expected in EXPECTED_SHA256.items():
    path = args.ephemeris_dir / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Unverified ephemeris version/hash: " + name)
FLAGS=swe.FLG_SWIEPH

def lon(jd,body):
    v,flags=swe.calc(jd,body,FLAGS)
    if not flags & swe.FLG_SWIEPH or flags & swe.FLG_MOSEPH:
        raise RuntimeError("Independent audit requires Swiss data, flags=" + str(flags))
    return v[0]
def wrap(x): return (x+180)%360-180
def root(seed,angle=None):
    f=(lambda t:wrap(lon(t,swe.MOON)-lon(t,swe.SUN))) if angle is None else (lambda t:wrap(lon(t,swe.SUN)-angle))
    lo,hi=seed-.1,seed+.1
    if not f(lo) < 0 < f(hi):
        raise ValueError("No root bracket at seed=" + str(seed))
    for _ in range(35):
        m=(lo+hi)/2
        if f(m)<0:lo=m
        else:hi=m
    return (lo+hi)/2

def row(seed,t,**kw):
    dt=b.jd_tt_to_beijing(t)
    return dict(**kw,engine_jd_tt=seed,independent_jd_tt=t,engine=b.jd_tt_to_beijing(seed).isoformat(),independent_same_timescale=dt.isoformat(),engine_minus_independent_seconds=(seed-t)*86400,beijing_meridian_only=(dt-timedelta(minutes=14.468)).isoformat(),swiss_delta_t_seconds=swe.deltat_ex(t,FLAGS)*86400,engine_delta_t_seconds=b.delta_t_seconds(2000+(t-b.J2000)/365.242189))
moons=[]
for y,m,d in [(1914,11,18),(1916,2,4),(1920,11,11)]:
    seed=b.new_moon_jde(b._k_near(b.jd_from_datetime_utc(b.beijing(y,m,d))))
    moons.append(row(seed,root(seed),date=f'{y}-{m:02}-{d:02}'))
hko = {'term_date_mismatches': [
    {'expected_date': day, 'longitude': angle} for day, angle in (
        ('1912-11-23',240), ('1913-09-24',180), ('1917-12-07',255),
        ('1927-09-08',165), ('1928-06-21',90), ('1979-01-21',300))]}
terms=[]
for v in hko['term_date_mismatches']:
    y=int(v['expected_date'][:4]);seed=b.solar_term_jd(y,v['longitude'])
    terms.append(row(seed,root(seed,v['longitude']),**v))
res=dict(swiss_version=swe.version,flags=FLAGS,source='https://github.com/aloistr/swisseph/tree/master/ephe',files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.ephemeris_dir.glob('*.se1')},moons=moons,terms=terms)
(ROOT/'focused-results.json').write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))
# All 200 years; no HKO source files are fetched or supplied by this sweep.
years=range(1901, 2101)
allterms=[]
for y in years:
    for angle in range(0,360,15):
        seed=b.solar_term_jd(y,angle);t=root(seed,angle)
        allterms.append(row(seed,t,year=y,longitude=angle))
allmoons=[]
for k in range(b._k_near(b.jd_from_datetime_utc(b.beijing(1900,12,1))), b._k_near(b.jd_from_datetime_utc(b.beijing(2101,2,1)))+1):
    seed=b.new_moon_jde(k);t=root(seed)
    allmoons.append(row(seed,t,k=k))
summary={}
for name,rows in [('terms',allterms),('moons',allmoons)]:
    errors=[abs(r['engine_minus_independent_seconds']) for r in rows]
    summary[name]=dict(n=len(rows),mean_absolute_seconds=sum(errors)/len(errors),max_absolute_seconds=max(errors),date_disagreements=[r for r in rows if r['engine'][:10]!=r['independent_same_timescale'][:10]])
(ROOT/'wide-results.json').write_text(json.dumps(dict(summary=summary,terms=allterms,moons=allmoons),indent=2))
print('WIDE',json.dumps(summary,indent=2))
