# Structural reading integration QA

Integration baseline: `382ce416`. Integrated BaZi commit `5cb68193` and Ziwei commits `33f05e64`, `a7c50c34` without changing the calendar, BaZi/Qizheng engines, Ziwei vendor code, synchronized references, or source registry. `build_chart.py` merged cleanly: BaZi structural text/JSON and the Ziwei `--explain-rules` passthrough are both retained. No push or deployment is part of this work.

## Reproduction and checks

Install pinned dependencies with `cd scripts/pai_pan_ziwei && npm ci`. The integration used an actual directory, not a dependency symlink. Run:

- `python3 scripts/test_pai_pan_bazi.py`
- `python3 scripts/test_pai_pan_qizheng.py`
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
- `python3 -m unittest discover -s tests -v`
- `python3 scripts/knowledge_catalog.py validate`
- `git diff --check`

Final full suites passed: 67 script tests and 103 tests under `tests/`, with no skips. The separately requested BaZi 11 and Qizheng 16 are included in the 67, not additional distinct tests. The final expanded alias regression suite also passed all six checks. Catalog validation passed (27 sources, 40 records); `git diff --check` passed. Independent review accepted both integration fixes and reproduced the double-sha evidence case (1965-03-15 22:00 male).

The script suite includes HKO-backed lunar-boundary and 2014/2026 solar-term minute samples. Those regression samples are not a rerun of the older 189-year HKO comparison and do not eliminate its documented historical mismatches. Source SHA-256 values in the combined snapshot were independently recomputed, including the new BaZi module and Ziwei adapter. Knowledge provenance/quarantine and conditional-claim gates remain covered by tests. A passing hash or gate does not authenticate a classical text or demonstrate prediction accuracy.

The first integrated test run exposed an overly broad Ziwei forbidden-phrase assertion: it scanned BaZi's explicit negation “不是官非、疾病或必然压力”. The assertion now examines only Ziwei output, in both formats, preserving the actual no-unqualified-prediction test. Independent review identified omitted evidence for condition aliases “坐煞” and “双煞”; these now resolve to the four-sha star set, with a real-chart regression for 1960-06-15 04:00 male. No recognizer conditions or chart calculations were changed.

## Five synthetic cases: substantive before/after

Each case was rerun against baseline and integration with analysis year 2026, UTC+08, civil time, scenario enumeration, the original coordinates, and the original uncertainty interval. For each: BaZi data, Qizheng data, the complete Ziwei `chart`, and boundary scenarios were identical. Integrated normal/explain text and JSON agreed on BaZi sections and Ziwei descriptions; every explain field appeared in explain text. These are synthetic inputs, not real people or predictive-validation samples.

- S1, 1988-03-18 10:20 female, 30.57/104.07: five empty BaZi comment slots now identify 辰卯害 and 申巳合, 壬水-relative stem relations, 卯中乙透月/时, spring fire/water positions, and same-element root locations. Two Ziwei matches retain their conditions without personal predictions.
- S2, 2001-08-22 16:40 male, 31.23/121.47: five position-specific pairs (including repeated 巳申 and 辛丙) are retained rather than deduplicated. 申中戊透时 is distinct from 庚/壬 not exposed. Three Ziwei matches have implementation-only explanations.
- S3, 1975-12-11 06:30 female, 39.90/116.40: three position-specific 子卯刑 pairs, 癸未透, winter water/fire inventory, and no same-element hidden-stem root location are stated without diagnosing weakness or prescribing fire. Five Ziwei matches no longer print upstream personality/event prose.
- S4, 1998-06-30 23:00 male, 23.13/113.26, ±2 minutes: central chart identifies 午子冲 and 己甲配对, with summer/root evidence. Four Ziwei matches retain chart-specific evidence. Existing late-Zi convention differences and candidate uncertainty remain; central prose is not a reading of every candidate.
- S5, 1992-02-04 21:48 female, 31.23/121.47, ±2 minutes: central chart identifies 丑未冲 plus 丑戌未三刑齐字, 辛透年/月 and winter/root evidence. Five Ziwei matches are conditional implementation descriptions. LiChun candidates remain distinct; this output does not extend the center's reading across the boundary.

Before: BaZi core interpretation slots were comments awaiting an agent, while Ziwei printed vendor descriptions and personality statements. After: BaZi provides five chart-specific structural explanations with prerequisites and limits; Ziwei exposes matched conditions and optional actual palace/star/brightness/transformation evidence rather than reinstating the vendor predictions.

## Exact remaining depth gaps

This is a structural inventory and explanation layer, not a completed detailed personal reading. It does not determine effective seasonal strength, 分日司令, valid 格局/成败/救应, effective 合化/制化, weighted 通根, or a justified unique 喜忌/用神. Ziwei recognizers retain known simplifications (including legacy brightness groups and some name-based transformation checks); their evidence descriptions are not a corrected full traditional interpretation or event-timing engine. There is no new deep Qizheng reading, context-specific life advice, complete cross-system synthesis, or outcome validation. Candidate scenarios are enumerated but not each supplied with a complete reading. Classical citations and redistribution restrictions remain subject to the existing knowledge gate.
