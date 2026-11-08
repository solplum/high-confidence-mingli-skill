# Qizheng Spica origin correction and boundary limits

## What is corrected

The legacy `201.2983°` constant is approximately Spica's **right ascension**, not
its ecliptic longitude. `physical-v2` uses a separate identifiable origin model,
`spica-mean-date-iau1976-pm-v2`. At J2000 its ecliptic longitude is
**203.8413578083478°**, a 2.5430578° change from legacy. This is Spica-relative
longitude, not a conventional roughly 24° zodiac ayanamsa.

Frozen catalog facts from [SIMBAD Spica](https://simbad.cds.unistra.fr/simbad/sim-basic?Ident=Spica),
checked 2026-11-07: ICRS position at epoch J2000, RA 13h25m11.57937s
(201.298247375°), Dec −11°09′40.7501″ (−11.161319472222222°),
μα cos δ = −42.35 mas/year and μδ = −30.67 mas/year; source bibcode
2007A&A...474..653V. This is the published unresolved catalog direction, not a
binary orbit model. SIMBAD also distinguishes its FK5 epoch/equinox J2000
coordinates; the ICRS numbers must not be advertised as exact FK5 values.
[NASA SkyView](https://skyview.gsfc.nasa.gov/blog/skyview.gsfc.nasa.gov/blog/index.php/2014/01/21/features-in-the-gallery-whos-the-culprit/index.html)
independently identifies (201.298, −11.161) as (RA, Dec).
Only these few factual catalog parameters are embedded, not a database or source
code copied from an astrometry package.

## Frame and time contract

1. Propagate the ICRS epoch-J2000 unit direction with tangent-vector proper motion.
   The RA catalog rate includes cos δ. No radial velocity, distance or binary
   orbit is assumed; perspective acceleration is omitted.
2. Treat ICRS as approximately FK5 J2000, apply IAU 1976 equatorial precession
   (Meeus ch.21), then rotate by IAU 1980 mean obliquity to mean ecliptic/equinox
   of date. The ICRS/FK5 bias is omitted, not asserted zero.
3. Argument is TT JD. [USNO TT](https://aa.usno.navy.mil/faq/TT) defines J2000
   as JD 2451545.0 TT. Engine TT comes from UT1 plus estimated ΔT, not an
   observed leap-second/EOP solution.
4. No nutation, annual aberration, parallax, gravitational deflection, atmospheric
   refraction or observer displacement is added. This is a mean catalog origin,
   not the apparent observed direction of the star.
5. Physical-v2 Sun removes its previous low-order apparent correction to use a
   geometric mean longitude, matching the planet/Moon and horizon mean-frame
   conventions. Virtual nodes/apogee/purple qi remain specified conventions.
   This does not turn approximate body algorithms into precision astrometry.

[USNO ICRS explanation](https://aa.usno.navy.mil/faq/ICRS_doc),
[USNO NOVAS](https://aa.usno.navy.mil/software/novas_info), and
[USNO Circular 179](https://aa.usno.navy.mil/downloads/Circular_179.pdf) distinguish
catalog directions, precession/nutation, aberration and apparent places. These
sources support the frame distinctions, not the traditional mansion table.

## Independent numerical check, 1900–2100

`tests/fixtures/spica_erfa_mean_date.json` contains 201 generated results at
integer Julian years 1900 through 2100. Independent reference uses pyerfa
2.0.1.5 / ERFA 2.0.1 `pmsafe` followed by `eqec06`, which includes the IAU 2006
bias/precession/obliquity matrix. RA proper motion is divided by cos δ before
`pmsafe`; zero radial velocity and zero parallax deliberately test direction-only
propagation. ERFA reports its documented “distance overridden” warning for this
zero-parallax use, not a measured star distance. This comparison is numerical
model agreement, not an observational confidence interval.

Maximum absolute longitude difference is **0.300523 arcsec** over that annual
grid; the regression threshold is **1 arcsec**. It does not bound the omitted
apparent-place effects, binary orbit, all dates between grid points, or traditional
boundary errors. Outside 1900–2100 a warning is emitted. Standard-library runtime
has no ERFA or other dependency. No third-party library is vendored.

Reproduce with an external validation-only install of `pyerfa==2.0.1.5`:

```python
import erfa, math
ra, dec = map(math.radians, (201.298247375, -11.161319472222222))
for year in range(1900, 2101):
    jd = 2451545.0 + (year - 2000) * 365.25
    r, d, *_ = erfa.pmsafe(ra, dec,
        math.radians(-42.35/3600000)/math.cos(dec),
        math.radians(-30.67/3600000), 0., 0., 2451545., 0., jd, 0.)
    lon, lat = erfa.eqec06(jd, 0., r, d)
    print(year, jd, math.degrees(lon) % 360)
```

## Mansion boundaries remain independent and unvalidated

The 28 legacy offsets are **not changed, shifted, re-fitted or silently presented
as corrected star positions**. Their epoch, coordinate definition, individual
star identifications and widths have not been independently reconstructed.
Correct Spica longitude alone cannot validate a mansion system, equatorial
right-ascension boundaries, ecliptic offsets or historical delineations.
The table is explicitly `legacy-approximate-offsets-v1`, with unknown angular
error and `mansion_boundaries_validated: false`.

A physical-v2 classification is a provisional application of that approximate
table to the corrected relative longitude. All body/ming-du classifications carry
`classification_quality`; a 0.1° proximity screen warns at boundaries (including
360° wrap). This is a heuristic, not an error bar: being farther away does **not**
certify the classification. Ming gong and en/yong remain conditional on those
approximate palace/mansion labels. Tests use only synthetic cases. For example,
at J2000 a synthetic tropical longitude of 230° changes from 氐/卯 under the
legacy origin to 亢/辰 under corrected origin. This demonstrates downstream
sensitivity, not which ancient-school classification is correct.

## Replay and API compatibility

`compute(..., profile="physical-v2")` explicitly selects the corrected model.
`profile="legacy-v1"` retains legacy Sun, bodies, origin and derived classification
numbers. Both emit identifiable frame metadata. Existing low-level
`spica_ayanamsa(jd)` / `to_sidereal(lon,jd)` defaults remain legacy for callers;
new physical callers must pass `profile="physical-v2"` explicitly. This deliberate
API compatibility choice prevents old consumers silently changing semantics.
The old profile replays known mistakes; it is not scientific validation.
