# Historical calendar discrepancy investigation

Astronomical baseline: `5599b3039975026d3cb0a548800a3a90bc901603`; the metadata/warning follow-up below does not modify its astronomical calculations. No push. Only synthetic astronomical dates. No retry or alternate retrieval of denied 2022–2032 HKO annual files.

## Primary-source finding

HKO's 3 May 2013 article explicitly attributes the 1916 first-month discrepancy to historical time standards: the conjunction is February 4 at 00:05 on the modern clock, February 3 at 23:51 under the old convention. It identifies longitude 116.383° E and a 14.468-minute difference from 120° E. Thus the 1916 mismatch is not evidence of an erroneous conjunction computation.

Source: https://www.hko.gov.hk/en/Observatorys-Blog/101741/Which-day-is-the-Tuen-Ng-Festival-for-this-year-2013

Caution: the English article uses “apparent solar time” while giving a constant longitude-only offset. A genuine apparent-solar clock additionally requires the date-dependent equation of time. Do not implement a new global historical clock from that terminology alone or invent a switch date. The article's numerical example establishes the relevant day shift, not a fully specified historical calendar algorithm.

Separately, HKO adopted GMT+8 in 1904. Hong Kong civil clock history is not automatically the time standard used to compile historical Chinese calendar dates. Do not infer this convention merely by selecting Asia/Hong_Kong or Asia/Shanghai.

Source: https://www.weather.gov.hk/en/gts/time/History_of_HK_Time_Service.htm

## Equations and method

Current engine: new moon is Meeus-style phase series JDE(TT), and solar terms solve apparent geocentric ecliptic longitude of date at 15° multiples. Before the verified UTC era the engine subtracts its ΔT = TT−UT1 model, then uses an 8-hour civil-day offset. This is proleptic UT1+8, not reconstruction of historical UTC.

Independent audit: Swiss Ephemeris 2.10.03 via pyswisseph, with official compressed DE441 files `sepl_18.se1` and `semo_18.se1` downloaded from Astrodienst's official GitHub. File headers identify DE441, created 2026-05-26; hashes are in results. Explicit SWIEPH flags are asserted on every call to prevent silent fallback to Moshier. No topocentric, sidereal, J2000, true-position, or no-nutation flags.

New moon: solve wrap180(λ_moon(TT)−λ_sun(TT)) = 0. Terms: solve wrap180(λ_sun(TT)−target) = 0. Bisection uses ±0.1 day around the engine seed and verifies a bracket; seeds do not supply the answer. Compare both results through the same engine TT-to-civil transform to isolate ephemeris errors from timescale choices. Swiss ΔT is also recorded independently for historical sensitivity. Known UTC uses TAI−UTC+32.184 seconds.

Longitude-only historical candidate: t_Beijing = t_120E − (120−116.383)×4 minutes = t_120E −14m28.08s. Local apparent time would be t_Beijing + EOT(date); the constant formula alone must not be labelled apparent-solar time.

Sources:
- https://www.astro.com/ftp/swisseph/ (links official repository)
- https://github.com/aloistr/swisseph/tree/master/ephe
- https://www.astro.com/swisseph/swisseph.htm

The downloaded ephemeris is audit evidence only. It has not been added as a runtime dependency or relicensed into the project. This is an independent numerical comparison, not proof of absolute astronomical accuracy.

## HKO caveat and classification policy

HKO says future conjunction/term calculations near midnight can shift a civil date because timing uncertainty can reach minutes. Its named cases include 2021 winter solstice, 2051 equinox, 2083 Lichun, 2084 equinox and three future new moons. This is not a blanket explanation of arbitrary historical discrepancies and must not excuse unexplained 1912/1913 rows.

Source: https://www.hko.gov.hk/en/gts/time/conversion.htm

## Recommended handling

Keep the current fixed-offset engine contract. Separate source agreement from astronomical correctness and historical convention. Do not insert date-key overrides to improve a benchmark ratio. A historical calendar profile requires authoritative switch rules and source-edition metadata, followed by independent complete regression. The remaining unexplained records should remain visible in the benchmark. Near-midnight astronomical ambiguity needs explicit metadata/warnings, not a silent daily override.

## Independent results

- 4,536 term instants in the same 189 cached HKO years: mean absolute difference 0.533371 s, maximum 2.834988 s (1914 longitude 210°). Every engine civil date agrees with the independent ephemeris under matched time conversion.
- 2,477 consecutive new moons from late 1900 through early 2101: mean absolute difference 3.611379 s, maximum 17.167197 s. These are observed comparisons, not universal error guarantees.
- The three historical conjunctions agree within 1.25 seconds: 1914-11-18 00:01:41.726, 1916-02-04 00:05:15.030, 1920-11-11 00:04:48.555 (independent DE441, same approximate UT1+8 transform). Their old-meridian candidates are respectively Nov 17 23:47:13.646, Feb 3 23:50:46.950, Nov 10 23:50:20.475. Independent historical ΔT differs by under half a second, too little to change any conclusion.

Six term discrepancies against HKO:

| Event | HKO date | Independent fixed +8 result | Assessment |
|---|---|---|---|
| 1912 Light Snow | Nov 23 | Nov 22 23:48:07.999 | Unexplained source/provenance discrepancy; historical longitude shift moves farther from HKO |
| 1913 Autumnal Equinox | Sep 24 | Sep 23 23:52:42.463 | Same unresolved direction; do not override |
| 1917 Heavy Snow | Dec 7 | Dec 8 00:00:59.588 | Historical meridian shift yields Dec 7, consistent with convention difference |
| 1927 White Dew | Sep 8 | Sep 9 00:05:25.765 | Historical meridian shift yields Sep 8 |
| 1928 Summer Solstice | Jun 21 | Jun 22 00:06:22.268 | Historical meridian shift yields Jun 21 |
| 1979 Severe Cold | Jan 21 | Jan 20 23:59:54.421 UTC+8 | Unresolved near-midnight source difference; neither historical meridian nor numerical accuracy explains it |

The 1979 independent instant uses known TT−UTC = 50.184 s, not the ΔT polynomial. Using TT−UT1 instead shifts it by only about 0.54 s, still Jan 20. Rounding to a whole minute can display midnight, but no evidence establishes that this explains HKO's date assignment. Do not state rounding as proven root cause.

### Newly exposed 2057 risk

The only new-moon civil-day disagreement in the independent sweep is k=714. Engine: 2057-09-28 23:59:57.510. Independent: 2057-09-29 00:00:04.448, under the same engine ΔT. The 6.937-second model difference crosses midnight. HKO explicitly warns about this new moon. Swiss and engine future ΔT predictions differ by approximately 32 seconds, and future UTC leap seconds are unknown. Therefore this is a genuine uncertainty case, not grounds to replace Sep 28 by Sep 29 as certain. HKO date agreement here does not certify the engine's astronomical day.

## Exact follow-up plan

1. Preserve default fixed +8 semantics and known/estimated timescale metadata. Keep 1916 explicitly classified as a documented convention difference; mark 1914/1920 and 1917/1927/1928 as strongly convention-supported, not universally proven historical source reconstruction.
2. Expose lunar calendar model and civil-day policy in public result metadata, distinct from a birth-location/time-input policy. Suggested fields: `calendar_civil_day_policy=fixed_utc_plus_08`, `historical_calendar_reconstruction=false`, `event_timescale=TT`, `civil_conversion=known_TT_minus_UTC_or_estimated_UT1`, and model/source versions. Integrate this only through the shared output schema and snapshot provenance, rather than modifying an isolated clock helper.
3. Add a boundary-risk warning for conjunctions and any term used to assign a calendar day near midnight, with a documented conservative trigger window and future ΔT caveat. The existing pillar-jie warning does not cover lunar month starts. A warning window is not an accuracy bound. The 2057 case must be in tests.
4. Do not implement a historical profile until its source editions, governing meridian, mean/apparent-time distinction, and adoption/switch rules are verified. Then apply the profile consistently to all conjunctions, winter-solstice anchors and major terms, and both conversion directions; never to just the three differing month starts.
5. Obtain primary HKO explanation or original historical calendar provenance for 1912/1913 and precise unrounded reference for 1979 before changing those classifications. No contact or external message has been sent.
6. Re-run all 69,012 scored daily conversions, both directions, 4,536 term dates, independent 2,477-moon and term sweeps, leap-month invariant tests and all schema/snapshot regressions for any eventual semantic change. Keep the denied 2022–2032 source gap explicit.

No astronomical algorithm patch is warranted by these observations. The follow-up adds metadata, scoped warning messages and independent fixtures without changing date assignment.


## Follow-up implementation: explicit policy and scoped risk

`compute()` now adds `calendar_policy`, also exposed as `bazi.calendar_policy` in combined JSON schema version 1. Existing keys are preserved. This describes the BaZi lunar conversion of `chart_clock_date`, **not the birth-location time-zone history or the separate Ziwei calendar**. A caller-provided display is marked `lunar_display_source=caller_provided`; the metadata still describes the model conversion, not authentication of that supplied text.

The policy records its version, fixed +08 civil-day assignment, TT conjunction model, known TT−UTC versus estimated TT−UT1 conversion, and the absence of historical reconstruction/transition rules. Every event explicitly labels `UTC+08:00` or `estimated_UT1+08:00`. ISO `+08:00` alone must not be read as proof of historical/future UTC.

The assessment examines **the start and next start of the current model lunar month**. A month-start uncertainty can affect day numbering throughout that month; the next boundary also affects the preceding month's length. Each event has its TT JD, lunation index, computed civil time/date, time-scale status, distance from midnight, and boolean `near_midnight`. A distance of **at most 120 seconds** triggers a warning. This is a conservative disclosure trigger, **not an error bound**, a probability, an assertion that the day is wrong, or an automatic date correction. Absence of this warning is not certification of accuracy. Current fields do not propagate solstice/principal-term or complete leap-month uncertainty.

For 2057-09-28 the engine retains September 28. The warning says the conjunction is midnight-sensitive and the UTC conversion is estimated; it does not choose September 29. The alternative independent result and future ΔT uncertainty are documented above. The previously unresolved 1912/1913/1979 reference disagreements remain unresolved.

### Reproduce without external dependencies

```sh
python3 scripts/test_historical_calendar_conventions.py -v
python3 scripts/build_chart.py --solar 2057-09-28 --hour 12:00 --sex 男 --lat 22.3 --lon 114.2 --analysis-year 2057 --format json
```

Inspect `bazi.calendar_policy.conjunctions` and top-level `warnings`. The focused tests include all six independently checked solar terms, the three historical conjunctions, the documented 1916 fixed-offset result, the 2057 risk, both adjacent months, ordinary known-UTC events, and start/middle/end month brackets across 1901–2100.

### Optional independent numerical reproduction

Install `pyswisseph==2.10.3.2` in an audit-only environment and download `sepl_18.se1` and `semo_18.se1` from the official Astrodienst repository linked above. Check their hashes and DE441 headers against the manifest below. Do not silently substitute another ephemeris version. No Swiss code/data is bundled as a runtime dependency or relicensed here.

```sh
python3 tests/tools/audit_calendar_ephemeris.py --ephemeris-dir /path/to/verified/ephemeris --output-dir /path/to/audit-output
```

This optional sweep checks all 4,800 terms in 1901–2100 plus 2,477 conjunctions. It uses no HKO download and does not close the missing HKO 2022–2032 data gap. The older 4,536-term figures above refer specifically to the 189-year HKO-covered subset. Known/estimated conversion is deliberately matched between calculations to isolate astronomical-model differences. Independent ΔT is also recorded, not substituted as a new calendar policy.

### Original DE441 file manifest

- semo_18.se1: `1ca07bd67c24374d77226180c20a4f9996cba013697894810518e7eb582ca4f7`
- sepl_18.se1: `ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66`

## Follow-up verification

- Standalone BaZi 11 and Qizheng 16 tests pass.
- Scripts discovery: 78 tests pass, zero skips (includes 11 new historical/policy tests). Tests discovery: 146 pass, zero skips. Counts overlap with standalone checks and are not additive unique-case counts.
- `knowledge_catalog.py validate` passes (integrity/metadata only); `git diff --check` passes.
- Unmodified 189-year HKO cache replay: 68,922 of 69,012 scored lunar dates and inverse conversions match, 4,530 of 4,536 term dates match. The 90 historical lunar disagreements, six term disagreements and 19 unscored initial dates are unchanged. The denied 2022–2032 files were not retried.
- Optional DE441 script was run with its verified file hashes: all 4,800 term civil dates agree, observed mean absolute timing difference 0.537708 s and max 2.834988 s. The 2,477-moon sweep retains the single 2057 day disagreement described above. No date correction was applied.
- Initial npm installation failed because the default cache directory was unavailable; rerunning with a writable workspace cache succeeded from the existing lockfile. Full suites above were rerun after installation, not reported from the earlier dependency-skipping run.

All inputs were synthetic. No real chart or personal data was added. No remote push was performed. Passing these checks does not validate divination predictions.
