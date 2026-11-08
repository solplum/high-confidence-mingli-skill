#!/usr/bin/env python3
"""Explicit opt-in developer fetch of PUBLIC synthetic JPL reference fixtures.

No user inputs/locations are transmitted. Network is not used in normal tests.
Run from any directory: python scripts/fetch_qizheng_reference.py
A refreshed ephemeris must be reviewed, not silently accepted as new truth.
"""
import urllib.request,urllib.parse,json,datetime,concurrent.futures,pathlib,hashlib
out=pathlib.Path(__file__).resolve().parents[1] / 'tests/fixtures/qizheng'
out.mkdir(parents=True, exist_ok=True)

def get(item):
 name,code=item
 params=dict(format='json',COMMAND=str(code),CENTER='500@399',EPHEM_TYPE='VECTORS',START_TIME='1900-01-01',STOP_TIME='2101-01-01',STEP_SIZE='182d',REF_PLANE='ECLIPTIC',REF_SYSTEM='ICRF',VEC_CORR='NONE',OUT_UNITS='AU-D',CSV_FORMAT='YES',VEC_TABLE='1')
 # no quoting needed for these single-token parameters
 url='https://ssd.jpl.nasa.gov/api/horizons.api?'+urllib.parse.urlencode(params)
 data=json.load(urllib.request.urlopen(url,timeout=120));raw=data['result']
 if '$$SOE' not in raw: raise RuntimeError(raw)
 rows=[]
 for line in raw.split('$$SOE')[1].split('$$EOE')[0].strip().splitlines():
  fields=[x.strip() for x in line.split(',')]; rows.append([float(fields[0])]+[float(x) for x in fields[2:5]])
 (out/(name+'-horizons.txt')).write_text(raw)
 return name,dict(target=code,request_url=url,sha256=hashlib.sha256(raw.encode()).hexdigest(),vectors=rows)
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
 data=dict(pool.map(get,[('mercury',199),('venus',299),('mars',499),('jupiter',599),('saturn',699),('moon',301)]))
(out/'geometric-vectors.json').write_text(json.dumps(dict(source='NASA/JPL Horizons API',retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frame='geocentric ICRF J2000 ecliptic',time_scale='TDB; treated as TT within <2 ms for this low-precision comparison',bodies=data),indent=2)+'\n')
print({k:len(v['vectors']) for k,v in data.items()})
