# 七政时间敏感性 / Qizheng time sensitivity

独立选项 `--qizheng-sensitivity` 使用 `--uncertainty-minutes`（0–120 分钟），不改变 `--enumerate-scenarios` 的四柱/紫微输入契约。可以单独或同时启用。支持完整 UTC 区间在 1901–2099 年，`physical-v2` 默认；`legacy-v1` 仅复现已知错误模型。

The opt-in compares actual Qizheng charts over elapsed UTC time around an already resolved birth instant. It does not change the Bazi/Ziwei scenario API. Time zone gaps/folds are resolved by the existing explicit policy before comparing; the unused fold is not silently included. The Qizheng palace clock remains Beijing civil time, independent of the Bazi time basis.

## 方法与输出 / Method and evidence

- 每 60 秒及区间端点、中心实际重算十一曜、命度、立命宫、昼夜及条件规则。离散签名含星体躔宿/宿主/距星/躔宫/靠界筛查、命度定义性及分类、立命宫、恩用与完整规则结果。
- Adjacent differing signatures are bisected until their witnessed bracket is at most 0.1 seconds wide. Multiple differences may share a bracket. This is a numerical categorical-change bracket, not a proven unique root or continuous interpolation. Endpoints are real computed charts. No monotonicity, continuity, root-count or completeness proof is claimed.
- 最多 4096 次完整求值。预算用尽时保留未细化包围并标记 `budget_exhausted`。保留每种观察签名的一个实际见证、每个包围两端、中心和区间端点，包含完整坐标、模型版本/来源散列、规则输出及警告。
- `observed_changing_fields` means observed differences. `not_observed_changing_fields` means no observed difference, **not stability**. `stable_fields` is always empty and `coverage_complete` is always false. Brief excursions, tangent contacts, multiple crossings and polar singularities can evade the grid. No interpolated or Cartesian-combination candidates are fabricated.
- 0.1 秒不是天文或实际事件精度。未校准宿表、未知宿界误差、近似星历、UT1/Delta T 与日出阈值不随数值求解而变精确。高纬退化保留空命度，不强行补齐。legacy 不因采样而获验证。
- Per-candidate rules are pointwise conditional evidence, including all existing guards. When the birth time has uncertainty, the main `qizheng_rule_reading` remains withheld. The sampled comparison does not unlock an interval-wide interpretation.
- 默认文本是简短白话摘要：输入时区时段、至多六项重要差异、每项一处 UTC 见证包围及不穷尽提示；不会把未观察到写成稳定。高纬无命度、重复民用时刻、计算预算耗尽均单列提醒。
- JSON `qizheng_sensitivity` always retains the complete existing payload. Use `--qizheng-sensitivity-evidence` to enable the comparison and append that identical full evidence block to text output. `--qizheng-sensitivity` alone now gives a bounded plain-language overview, without removing any JSON evidence. A null JSON field means not requested.

## 合成案例 / Synthetic reproducible examples

No user birth information is used. A synthetic location 35°N, 120°E and these UTC windows exercise real model boundaries:

```
python3 scripts/build_chart.py --solar 2000-01-01 --hour 08:00 --sex 男 --lat 35 --lon 120 --uncertainty-minutes 120 --qizheng-sensitivity --analysis-year 2026 --format json
python3 scripts/build_chart.py --solar 2000-01-03 --hour 08:00 --sex 男 --lat 35 --lon 120 --uncertainty-minutes 120 --qizheng-sensitivity --analysis-year 2026 --format json
```

The first observes ascendant mansion, palace, day/night and rule differences. The second additionally observes a Moon mansion change. Tests replay witness charts directly through the engine, check both sides of refined brackets, verify exact optional evidence/JSON parity and bounded default summaries, UTC-equivalent folds, polar undefined ascendants, legacy routing, and a forced compute budget. These validate implementation behavior, not the underlying traditional boundaries or predictive validity.
