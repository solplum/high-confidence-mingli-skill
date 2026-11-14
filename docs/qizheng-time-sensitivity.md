# 七政时间敏感性 / Qizheng time sensitivity

独立选项 `--qizheng-sensitivity` 使用 `--uncertainty-minutes`（0–120 分钟），不改变 `--enumerate-scenarios` 的四柱/紫微输入契约。可以单独或同时启用。支持完整 UTC 区间在 1901–2099 年，`physical-v2` 默认；`legacy-v1` 仅复现已知错误模型。

The opt-in compares actual Qizheng charts over elapsed UTC time around an already resolved birth instant. It does not change the Bazi/Ziwei scenario API. Time zone gaps/folds are resolved by the existing explicit policy before comparing; the unused fold is not silently included. The Qizheng palace clock remains Beijing civil time, independent of the Bazi time basis.

在总控中请求七政时间敏感性时，需要出生地经纬度。民用钟面缺少一项或两项坐标时，仍生成八字、紫微和七政十一曜。若同时请求且可执行出生候选枚举，也保留实际候选。七政命度、立命宫、昼夜等依赖坐标的字段留空，采样未执行的原因记入 `degradation.qizheng_sensitivity` 和文本警告。补齐坐标后按同一出生钟面及误差重跑。平太阳时或真太阳时仍需经度来解析排盘钟面。

The combined chart command records skipped Qizheng sampling in `degradation.qizheng_sensitivity` when either coordinate is missing and the chart clock can be resolved. The dedicated sampling command requires both coordinates.

## 只确认民用日期和时辰

原公历民用日期、时辰、出生时区和经纬度已确认，分钟未知时，用同一采样入口传 `--shichen`。以下使用合成出生输入。

```sh
python3 scripts/qizheng_sensitivity.py --birth-date 1987-09-04 --shichen 子 \
  --timezone Asia/Shanghai --lat 31.23 --lon 121.47 --format text
```

同一民用日期的子时可能有早晚两个分离部分，各段按出生当时实际偏移取得。重复钟面保留可达的各段，跳过的钟面无样本。日期或时辰口径仍有歧义时，先核实际输入再采样。原输出 `sampled_sections` 保留每段见证和排除终点，全部段共用计算上限。先比较各段实测结果，再检查单段内的变化。示例的早子见证立命在酉宫，晚子见证在戌宫，因此只能分别说明相应结构。整体规则继续暂缓。

时辰及同日钟面区间两种入口均可用 `--format text` 快速查看实际可达时段及至多六项重要差异。昼夜、命度所属宿和立命宫在各采样点一致时，正文也显示各自观测值。跨段差异列两个实际见证，区间空档不定位过界。段内差异使用实际包围。默认或显式 `--format json` 仍返回全部证据，按 `sampled_sections` 复核规则条件、其他变化及未覆盖范围。

规则摘要优先展示能否解释发生变化的见证及暂缓原因。例如相邻时段的立命宫不同，但两点都可给条件释义时，若另有实测点因靠近宿界而暂缓，规则行优先展示这一暂缓。该次暂缓的规则在后续实测点可再次解释时，另列一个实际见证及恢复可用的具体释义。立命宫变化仍可在自身字段行查看。若各采样点均有相同的部分或全部暂缓，也直接报告原因，适用范围仍限实测点。

所列见证已有条件解释时，摘要同时给出已核的度主和宫主关系。所有实测点的规则结果一致时，也列这项共同观察。明确选用乾元参照时，另显示指定曜相对宫主的分类。每个结果限实际采样见证。

The confirmed-shichen entry uses the actual reachable parts of the named civil branch and keeps the birth minute unknown. Both civil entries accept `--format text` for a bounded overview of reachable spans and representative differences. The summary also names any day/night, ascendant mansion or traditional rising palace classification shared by all sampled points. Differences between spans list two observed witnesses without locating a crossing in the gap. The rule summary prioritizes changes in whether a conditional interpretation is available and names reasons for partial or full withholding, including limitations shared by all sampled points. The default JSON retains all pointwise evidence and limits.

For displayed witnesses with an admitted interpretation, the overview also gives the checked degree lord and palace-lord relation. After a displayed withdrawal, it names one later sampled point where a withdrawn claim can be interpreted again, when available. If all sampled results agree, it reports that shared observation. When the Qianyuan comparison is selected, it names the specified body’s relation to the palace lord separately. These results apply to the sampled instants.

## 已确认同日出生钟面区间

已确认公历出生日期、民用钟面上下界、出生时区和经纬度时，可直接采样实际可达时段。使用同一出生记录核八字、紫微时，见[出生钟面区间](time-contract.md#已知民用出生钟面区间)。

```sh
python3 scripts/qizheng_sensitivity.py --birth-date 2000-01-01 --start 06:00 --end 13:00 \
  --utc-offset 8 --lat 35 --lon 120
```

出生时区也可用 `--timezone` 指定。起点包含，终点排除。重复钟面按各实际偏移保留，跳时空档无采样。全天未知继续按原建档处理。全部可达 UTC 时段须在 1901–2099 年内。

读取 `sampled_sections` 的实际半开范围和各 `sample` 中的见证。每段沿用 60 秒间距及 0.1 秒差异包围，在排除端点之前取最后一个可表示时刻。全次仍最多 4096 次完整求值，优先保留每段的基础采样，预算用尽时标明未细化差异。总体 `observed_changing_fields` 可含不同实测时段间的值差，变化定位以各自段内的包围为准。整个输入没有中心盘，`coverage_complete=false`、`stable_fields={}`，整体规则状态继续暂缓。只在明确选择乾元参照时传 `--qizheng-tradition qianyuan-palace-v1`，沿用见证级别的原有规则门。

For a confirmed wall-clock band, the CLI returns only samples inside the reachable half-open UTC sections. Repeated local times can produce separate sections. The entire request shares the existing evaluation cap, and the underlying ephemeris, rule gates and Beijing palace clock stay the same.

## 方法与输出 / Method and evidence

- 每 60 秒及采样端点实际重算十一曜、命度、立命宫、昼夜及条件规则。围绕已核时刻的误差入口也算中心。离散签名含星体躔宿/宿主/距星/躔宫/靠界筛查、命度定义性及分类、立命宫、恩用与完整规则结果。
- Adjacent differing signatures are bisected until their witnessed bracket is at most 0.1 seconds wide. Multiple differences may share a bracket. This is a numerical categorical-change bracket, not a proven unique root or continuous interpolation. Endpoints are real computed charts. No monotonicity, continuity, root-count or completeness proof is claimed.
- 最多 4096 次完整求值。预算用尽时保留未细化包围并标记 `budget_exhausted`。保留每种观察签名的一个实际见证、每个包围两端、中心和区间端点，包含完整坐标、模型版本/来源散列、规则输出及警告。
- `observed_changing_fields` means observed differences. `not_observed_changing_fields` means no observed difference, **not stability**. `stable_fields` is always empty and `coverage_complete` is always false. Brief excursions, tangent contacts, multiple crossings and polar singularities can evade the grid. No interpolated or Cartesian-combination candidates are fabricated.
- 0.1 秒不是天文或实际事件精度。未校准宿表、未知宿界误差、近似星历、UT1/Delta T 与日出阈值不随数值求解而变精确。高纬退化保留空命度，不强行补齐。legacy 不因采样而获验证。
- Per-candidate rules are pointwise conditional evidence, including all existing guards. When the birth time has uncertainty, the main `qizheng_rule_reading` remains withheld. The sampled comparison does not unlock an interval-wide interpretation.
- 默认文本显示输入时区时段、至多六项重要差异及每项一处 UTC 见证包围。昼夜、命度所属宿或立命宫在实测点一致时也显示对应值，适用范围仍限实测点。高纬无命度、重复民用时刻、计算预算耗尽均单列提醒。
- JSON `qizheng_sensitivity` retains all sampled evidence. Use `--qizheng-sensitivity-evidence` to enable the comparison and append the same evidence block to text output. When saving a block separately, keep its `input` with the location, calculation profile, DUT1 and known civil time zone or fixed offset. `--qizheng-sensitivity` alone gives a bounded plain-language overview. When the JSON field is null, check `degradation.qizheng_sensitivity` for the reason a requested comparison was skipped.
- 证据账本引用某一采样点的星曜原值或离散摘要时，按该点的 UTC 瞬间、计算版本和 DUT1 重算所引用的星曜。若旧 `physical-v2` 档缺 DUT1，先从原输入重算再把星位作为已复盘的事实。

## 合成案例 / Synthetic reproducible examples

No user birth information is used. A synthetic location 35°N, 120°E and these UTC windows exercise real model boundaries:

```
python3 scripts/build_chart.py --solar 2000-01-01 --hour 08:00 --sex 男 --lat 35 --lon 120 --uncertainty-minutes 120 --qizheng-sensitivity --analysis-year 2026 --format json
python3 scripts/build_chart.py --solar 2000-01-03 --hour 08:00 --sex 男 --lat 35 --lon 120 --uncertainty-minutes 120 --qizheng-sensitivity --analysis-year 2026 --format json
```

The first observes ascendant mansion, palace, day/night and rule differences. The second additionally observes a Moon mansion change. Tests replay witness charts directly through the engine, check both sides of refined brackets, verify exact optional evidence/JSON parity and bounded default summaries, UTC-equivalent folds, polar undefined ascendants, legacy routing, and a forced compute budget. These validate implementation behavior, not the underlying traditional boundaries or predictive validity.
