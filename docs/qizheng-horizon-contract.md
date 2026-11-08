# Qizheng physical horizon and time contract

## Breaking numerical change

Default `compute(..., profile="physical-v2", dut1_seconds=0.0)` fixes a western
intersection incorrectly labelled ascendant, EOT minutes added to degrees of
sidereal time, and day/night decisions using incompatible and unwrapped clocks.
It also selects corrected v2 planetary/lunar helpers. 命度 and derived 度主/恩用难仇
can change substantially. This is not evidence of predictive validity.

Use CLI `--profile legacy-v1` or build_chart `--qizheng-profile legacy-v1` only to
reproduce old results. Legacy retains the old astronomical bugs, not a certified
traditional school. No golden output is silently relabelled physical truth.

| Beijing input / location | Old ascendant | Physical ascendant | Old → physical day/night |
|---|---:|---:|---|
| 1990-05-15 14:00, 31.23 N 121.47 E | 358.157512° | 174.975213° | day → day |
| 2000-01-01 20:00, 39.90 N 116.40 E | 315.220992° | 137.818716° | night → night |
| 2024-06-21 06:00, 0 N 120 E | 267.984781° | 89.634686° | night → day |

## Explicit API scope

- `birth_instant` must be timezone-aware and denotes the physical instant, not
  a solar-clock reading. Without it, date/hour/minute retain Beijing (+08) meaning.
- `jd_utc` records the UTC Julian date. `jd_ut` means UT1: UTC plus supplied DUT1
  in seconds. Default zero is an approximation, not measured Earth orientation.
  DUT1 accepts ±0.9 s for modern UTC; historical civil/UT reconstructions need
  another contract, not arbitrary large DUT1 here. TT remains a polynomial
  Delta-T estimate added to UT1, not an IERS leap-second/EOP service.
- `ascendant_tropical(jd_ut, jd_tt, lat, lon, eot_minutes=0)` takes UT1 and TT.
  The retained EOT argument is ignored in the corrected function. GMST (the
  existing Meeus-style expression) plus east longitude defines the local mean
  sidereal angle. The mean obliquity defines the mean ecliptic of date.
- A unit vector on the ecliptic is intersected with the horizon plane. The
  positive local-east component chooses the point whose altitude increases
  with Earth rotation. No tangent of latitude or blind +180° rule is needed.
  At exact poles, tangency or coincident planes (tolerance 1e-12), the rising
  point is undefined: `ming_du`, `du_zhu_wuxing`, `en_yong` become null and a
  warning is emitted. Near singularities longitude is ill-conditioned, even
  if the returned vector satisfies the geometric invariants.
- Day/night is the instantaneous approximate geometric solar-centre altitude
  compared with -0.833°. This bundles nominal semidiameter/refraction in a
  standard sunrise threshold; it does not model actual weather, elevation,
  terrain, solar parallax, or observer dip. Corrected `day_night` deliberately
  has `solar_altitude_deg`, `threshold_deg`, `method`, `note`, **not** the old
  `sunrise_local`/`sunset_local` fields. No day-long polar status is inferred
  from a single instant. Both hemispheres use the same physical equations.
- `sunrise_sunset_utc` remains a legacy approximate helper, not used by v2.
  `legacy_ascendant_tropical` explicitly preserves the old formula.
- Traditional `ming_gong` still uses Beijing civil hour and its separate
  classical rule. This change does not equate physical rising longitude with
  every historical 安命 doctrine. Mansion widths and node/apogee/purple-qi conventions are unchanged.
  The subsequent star-frame correction changes physical-v2 Spica origin and
  normalizes the Sun to the mean frame; see [star-frame contract](qizheng-star-frame.md).
- Model metadata is explicit: corrected planets and Moon are geometric mean
  ecliptic-of-date approximations, including the physical-v2 Sun. Only legacy-v1
  preserves the old approximate apparent Sun. The solar altitude helper uses
  a geometric mean-frame Sun. These are not apparent astrometry. No global numerical accuracy is promised.

## Primary sources checked

- US Naval Observatory: [Computing Approximate Sidereal Time](https://aa.usno.navy.mil/faq/GAST)
  and [sidereal-time service](https://aa.usno.navy.mil/data/siderealtime): GMST vs
  GAST, UT1 and local sidereal angle. EOT is not added to GMST.
- NOAA: [General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)
  defines sunrise/sunset zenith 90.833°, combining nominal disk/refraction.
  [Calculation caveats](https://gml.noaa.gov/grad/solcalc/calcdetails.html) warn
  that observed sunrise can differ, especially for high latitudes/atmosphere.
- [Swiss Ephemeris programmer documentation](https://www.astro.com/swisseph/swephprg.htm):
  independent `houses_armc` and Moshier Sun are test-only external oracles.
  No Swiss code, ephemeris files or nonpermissive datasets are redistributed.

## Reproducible checks

`python3 scripts/test_qizheng_horizon.py` runs standard-library invariants.
If independently installed `pyswisseph` is available, two additional oracle
checks run; otherwise they explicitly skip. Runtime has no dependency on it.

- 1,232 horizon/rising tests: 1900/2000/2024/2100, 11 latitudes through
  ±89.999999°, 7 longitudes including ±180°, 4 UTC times. Horizon dot product
  checked within 1e-14 and positive finite-difference rising derivative.
- Undefined exact poles/coincident-plane geometry, EOT independence, invalid
  inputs, DUT1, offsets -12/-8/0/+5.5/+8/+14, dateline equivalence, UTC wrap,
  and both hemispheres' polar-season daylight are tested.
- Swiss 2.10.03 `houses_armc`, same mean ARMC/obliquity, 125 nonpolar cases:
  differences below 1e-9° test threshold. This isolates intersection algebra,
  not clock-model accuracy. Polar house conventions can differ; those cases
  are tested by physical geometry, not forced to agree with Swiss astrology.
- 400 geometric solar-altitude comparisons with Swiss Moshier, 1900–2100
  sampled equinox/solstice dates and five latitudes/longitudes: observed max
  0.00657714° (2000-09-21, equator, ±180°); test envelope 0.03°. This finite
  sample is **not** a bound on all times/places or observed sunrise.
