# Bounded candidate and scenario integration verification

Synthetic fixtures only. These checks establish implementation consistency, not predictive validity or a comprehensive traditional reading.

## Integrated changes

Base a124a294 plus case-reasoner 92e4a905, 1f75d8d3, 13ae7800 and scenarios adb6cbe, 45a7ea8, 9377516. Duplicate 9c23cc8 was excluded. No engine or HKO fixture modifications were needed. An independent review identified missing explicit attribution in standalone comparison text; a shared attribution renderer now includes the source, revision, interpretation label, contributor history, adaptation and CC BY-SA 4.0 link once per distinct source, explicitly covering the comparison.

## Executed checks

Actual `npm ci --cache /workspace/scratch/10337929cf9d/npm-time-cache` installed 10 packages in this worktree. Initial default-cache attempt failed because /home/agent/.npm was unwritable; no node_modules copy was substituted. Pinned dependencies remain unchanged.

- Standalone BaZi: 11 passed. Standalone Qizheng: 16 passed.
- Scripts discovery: 67 passed, including retained HKO lunar-date and solar-term checks.
- Tests discovery: 124 passed, zero skips, including normal Node/Ziwei integrations.
- Knowledge catalog: 27 sources / 40 records, valid file integrity and metadata only.
- S1–S5: normal Ziwei enabled, both text/JSON, explanations off/on. Center engine facts, Ziwei chart and enumerated scenarios equal saved a124a294 outputs. All center section prose, candidate pattern prose, candidate comparison prose, applicable attribution URLs, Ziwei rule descriptions and enabled explanations appear in text.
- `git diff --check` passed. No push performed.

## Actual synthetic cases

All use civil UTC+8 and analysis year 2026. Locations/sex are fixtures, not user birth data.

| Case | Input | Result |
|---|---|---|
| S1 | 1988-03-18 10:20, 女, 30.57/104.07, ±0 min | One reachable chart; 伤官格候选 by the bounded route. |
| S2 | 2001-08-22 16:40, 男, 31.23/121.47, ±0 min | One reachable chart; 伤官格候选 by the bounded route. |
| S3 | 1975-12-11 06:30, 女, 39.9/116.4, ±0 min | No candidate on this route; `not_applicable_no_candidate`, not an absence-of-interactions claim. Three 子卯刑 pairs remain in core output. |
| S4 | 1998-06-30 23:00, 男, 23.13/113.26, ±2 min | Two reachable charts: 戊寅/戊午/戊申/癸亥 and 戊寅/戊午/己酉/甲子. Only season is common among listed evidence fields; neither chart has a candidate on this route. |
| S5 | 1992-02-04 21:48, 女, 31.23/121.47, ±2 min | Two charts around model LiChun 21:48:17.183146 UTC+8: 辛未/辛丑/庚戌/丁亥 and 壬申/壬寅/庚戌/丁亥. Only day-master is common among listed fields; neither has a candidate on this route. |

S5 is not the separate 1992-02-04 23:00 sample that selects 正印格候选. A ±0-minute fixture has only its single resolved instant, not a robust interval claim.

## Exact coverage semantics and limits

- `civil` and `mean-solar`: `complete_for_modeled_boundaries_not_astronomical_error`. `stable_evidence` is the intersection of the listed evidence across returned reachable charts within the current model; it is not an external accuracy claim.
- `apparent-solar`: `numerical_witnesses_not_exhaustive`. `stable_evidence` stays empty; common sample facts only enter `observed_constant_evidence`. No exhaustive guarantee or stable intervals.
- Interval domain: inclusive elapsed UTC minutes around resolved center; individual partitions use explicit `end_inclusive`, preserving boundary witnesses and the final endpoint.
- Excluded: qiyun, dayun ages, Qizheng, full Ziwei outputs, ephemeris error, alternative late-Zi conventions. Center Ziwei and Qizheng are not recomputed as complete charts for each BaZi scenario.
- Additional tests cover nested intervals, DST gap/fold, zero-common-evidence complete coverage, and no-candidate wording.
- Candidate logic only uses month-hidden identical-stem exposure for ordinary candidates. It does not establish 成格, strong/weak balance, 调候用神, 喜忌, special patterns, life events, probability, or scientific/predictive accuracy. S1/S2 selecting the same candidate is not a claim that their structures or lives are identical.

Historical component QA pages describe their own runs; this page records the final integrated acceptance run. Raw outputs, logs and the reproduction driver are supplied alongside the source archive and full binary-capable patch against b7d61b5.
