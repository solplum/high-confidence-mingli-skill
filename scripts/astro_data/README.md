# Solar-series provenance

`solar_longitude.json` is a minimal, lossless coefficient extraction from the
already pinned dependency `lunar-javascript` **1.7.7**, `lunar.js`,
`ShouXingUtil.XL0` and `NUT_B`. Upstream:
https://github.com/6tail/lunar-javascript
The package version, lockfile and source file hash identify this copy.

Source file SHA-256:
`9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa`

License: MIT, copyright (c) 2018 6tail. Full notice is retained in
`LICENSE-lunar-javascript.txt`. The Python evaluation in `pai_pan_bazi.py` ports
only `eLon(t, -1)`, `nutationLon2`, `gxcSunLon` and `saLon`; it does not port the
upstream delta-T forecasts or calendar exception tables. No new package or
network access is required at runtime. Distribute this directory with scripts.

Extraction recipe: `scale = XL0[0]`; for each order i from 0 to 5 take triples
`XL0[j:j+3]` for j in `range(XL0[i+1], XL0[i+2], 3)`. Split `NUT_B` into groups
of five unchanged numbers. JSON stores all source precision. The snapshot
provenance hashes the JSON as well as engine code. Tests compare Python and
the pinned JavaScript series at seven epochs from 1901 to 2100; this checks
port fidelity, not independent astronomical accuracy.
