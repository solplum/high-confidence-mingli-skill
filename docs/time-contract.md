# 时间契约与第一阶段回归

## 兼容与选择

`build_chart.py` 默认 `--time-basis civil --utc-offset 8`，保留旧版八字/紫微的民用钟面结果。选择 `--time-basis apparent-solar` 才将经度与均时差修正后的**日期和时间一起**传入八字日时柱及紫微。太阳钟面是无时区标签，不是第二个物理瞬间。节气、年/月柱、起运距离和七政天体位置始终基于输入的原始瞬间。

`--utc-offset` 是出生当时实际 UTC 偏移，不是时区名称，也不会自动校验历史夏令时。太阳钟面 = UTC 钟面 + 经度 × 4 分钟 + 原七政引擎均时差。显示到秒不表示秒级精度；此次仅修复数据流和日期进位，没有独立测定均时差误差。计算日时/紫微时向下取整到分钟，避免显示四舍五入造成偷偷越界。

- 八字保留原有 23:00 换日规则。
- 紫微保留原副本子时索引 0 的处理；晚子时与八字换日可能不同，输出警告，不擅自统一学派。
- 七政保持现有体系，包括安命用 +08 民用时辰；太阳模式不意味着七政所有规则已改为太阳时。
- `--uncertainty-minutes N` 表示 ±N 分钟输入误差。非零时结果明确标记为中心时刻候选，未开启 `--enumerate-scenarios` 时不枚举候选，不得把它当唯一确定命盘。
- `--age-year YYYY` 控制紫微所有当前大限标记，统一采用公历目标年减原始民用出生年加一的年度虚岁。不是生日周岁，也不是农历春节递增年龄。
- 紫微内部 `--birth-year` 仅传递太阳钟面跨年之前的原始民用出生年，不改变排盘日期。

## 运行

Python 3.8+；紫微使用 Node 18.19+（`--import tsx`）。先在 `scripts/pai_pan_ziwei` 运行 `npm ci`。总控只使用本地已安装依赖，不再通过 `npx` 在缺包时自动联网下载执行。依赖缺失则明确降级。

```
python3 scripts/build_chart.py --solar 2005-12-24 --hour 00:05 --sex 男 --lat 27.4 --lon 102.18 --utc-offset 8 --time-basis apparent-solar --age-year 2026
python3 scripts/test_pai_pan_bazi.py
python3 scripts/test_pai_pan_qizheng.py
python3 scripts/test_time_contract.py
```

测试样例使用固定的近似德昌坐标，不代表已核实某人的精确出生地点。按现有均时差实现，该钟面落在前一天约 22:54，回归测试验证日期和时辰传递，而不是验证命理解读或天文绝对精度。新增测试还覆盖立春瞬间不被太阳钟面平移、跨年、非法日期、误差提示、警告保留、目标年份大限及虚岁边界。紫微依赖缺失时其测试会显式 skip，不能宣称全套通过。

## 对照审查与未解决事项

对照了 `fortune-observatory@3ce1995e41b29e4ab2320323a969158f4e5b2214` 的时间服务、八字服务、节气测试和紫微限运接口，没有移植其实现：其 DE440s 数据与依赖更重、部分时间口径元数据与代码不一致，且七政体系不同。不将其差分测试数量当作独立金标准。

后续仍需独立历表/星历金标准、历史时区数据外部复核、完整三盘误差覆盖、明确跨流派子时配置、七政升度均时差公式专项审计。七政原有昼夜生计算在东西经极端位置未统一归一化到 24 小时，本次未修复；新增 UTC 偏移输入不代表七政已通过全球地点验证。此次测试通过只证明所列实现契约，不证明命理预测有效。

## 全局分析年份

总控新增 `--analysis-year YEAR`。显式提供时八字 `current_year/current_gz/liunian_years` 与紫微目标年共同固定，不更改出生瞬间、四柱或天体位置。年份须不早于出生民用年且不超过 9999；与 `--age-year` 同时提供必须同值。

未提供时保持旧接口：八字取运行当年，紫微由 `--age-year` 或运行当年控制。JSON `provenance` 分别记录 analysis_year、resolved_bazi_year、resolved_age_year；不会把未固定的年度伪装成统一。默认文本中的建档日期仍为实际运行日，不属于分析日期。完整 JSON 在相同代码、依赖和输入且显式固定分析年时可跨运行年份复现。

`current_gz` 是所选公历年份的年度标签（例如 2025 → 乙巳），不是该年 1 月 1 日按立春换年的即时年柱。内部传给八字 `now` 的 1 月 1 日仅用于传递年份，不是新增事件时刻；出生年/月柱仍按原始出生瞬间判节气。

## IANA 历史时区与有界误差候选

可选 `--timezone Asia/Shanghai` 使用标准库 `zoneinfo`；与显式 `--utc-offset` 互斥。不提供时仍为固定 +08。IANA 模式要求 Python 3.9+ 及系统时区数据库（或已安装的官方 tzdata 包）；不自动联网安装。JSON 记录区域名、实际偏移、fold 和可读取 TZif 数据的 SHA-256。历史数据库会更新，不是本仓固定数据；相同代码和分析年不足以保证不同数据库版本的结果相同。解析结果不证明出生地点记录或历史记载本身正确。

- gap（跳时导致民用时间不存在）报错，不平移到另一个时刻。
- fold（民用时间重复）必须显式 `--fold 0` 较早或 `--fold 1` 较晚；普通时间不接受无效的 fold=1。
- 历史 UTC 偏移可能包含秒，七政总控通过独立 `birth_instant` 保留秒，不再丢弃实际瞬间；排盘日时钟面仍向下取整分钟。
- 新增 `--time-basis mean-solar`：UTC + 经度 × 4 分钟，不含均时差。civil、mean-solar、apparent-solar 三者分开记录；节气判断始终用真实瞬间。

`--uncertainty-minutes N` 单独使用仍只提示中心盘非唯一。加 `--enumerate-scenarios` 开启候选：

```
python3 scripts/build_chart.py --solar 2005-12-24 --hour 23:00 --sex 男 --lat 30 --lon 120 --timezone Asia/Shanghai --uncertainty-minutes 10 --enumerate-scenarios --analysis-year 2026 --format json
```

区间定义为**已明确解析中心瞬间前后实际经过的 UTC 时间**，不是钟表上两端各减加 N 分钟（DST 跨越时二者不同）。范围是闭区间，N 最大 120 分钟，完整 UTC 区间须在 1901–2099 年内；超限直接拒绝，不截断。不是概率分布，不自动选最可能的候选。

仅比较四柱干支与紫微的公历日期、时辰索引、民用出生年份。civil/mean-solar 在模型内按午夜、各奇数整点、实际节气与时区偏移跳变划分，输出实际可达见证时刻和区间，以及该有限字段集合的 stable_fields/changing_fields。时区跳变逐个整数 UTC 秒检查（TZif 的转换时间是整数秒）；不靠粗粒度抽样推断无变化。端点包含；中间子区间右端不包含。只合并完全相同字段的可达候选，不做四柱逐项笛卡尔积。

apparent-solar 采用随瞬间重算的原均时差公式，对钟面边界数值二分包围至不超过 1 毫秒，计算包围两端的实际候选。**该模式未证明完整覆盖**，coverage 为 numerical_witnesses_not_exhaustive；stable_fields 始终为空，observed_constant_fields 只表示已计算样本未变化，不能当作稳定。不给这些候选附精确生效区间。1 毫秒仅为数值求根容忍，不是均时差模型或节气的天文精度。边界可非常接近，不以无变化样本排除未解析的短区间。

所有模式均不枚举连续七政天体位置、起运时距/大运年龄、完整紫微排布、不同晚子时学派或天文模型误差；中心盘的这些字段不得转称稳定字段。八字 23:00 换日、紫微午夜公历日期及其原子时索引保留，不擅自统一。节气近边界告警仍需权威历表复核。1901–2099 只是枚举工程范围，不是准确度证明。

### 官方实现参考

- [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html)：IANA 数据来源、Python 3.9 引入和 fold 行为。
- [PEP 495](https://peps.python.org/pep-0495/)：重复/不存在的民用时间、fold 的较早/较晚语义；本工具额外做 UTC 往返有效性校验。
- [RFC 8536 §3.2](https://www.rfc-editor.org/rfc/rfc8536.html#section-3.2)：TZif 整数转换时间；这里只用该表示契约，不声称历史时区记录完整无误。

测试：`python3 scripts/test_time_scenarios.py`。覆盖 DST gap/fold、正常区域、历史秒偏移、23:00/午夜、平太阳时亚秒边界、立春瞬间、真太阳时数值包围和范围拒绝。另包含 Lord Howe 半小时切换、Apia 跳过整天、Kwajalein 23 小时回拨、Amsterdam/Paris 历史秒偏移及 Kathmandu 15 分钟跳变的区间归属检查。测试是实现回归，不是预测能力验证。

## 农历历日政策与近午夜朔提示

八字结果新增 `calendar_policy`（总控 JSON 路径 `bazi.calendar_policy`）。它说明排盘钟面日期的农历转换，独立于出生地时区与紫微历法。固定 +08 历日包含朔的原规则不变；历史重建为 false，未经确证的历史切换规则为 null。逐朔标明 TT 与已知 UTC / 估算 UT1 转换。

当前农历月起点、下一月起点两次朔距午夜不超过 120 秒时显示风险警告，覆盖该月日期而不只出生瞬间。两分钟只是提示窗，不是误差上界；不代表历日已判错，不自动改日，无警告也不是准确度保证。尚不传播冬至、中气与完整闰月不确定性。2057-09-28 保留原日期并提示未来时标/近午夜敏感。[独立星历审计、字段与复现](historical-calendar-audit.md)。


## 已批准的紫微独立目标动态profile

2026-11-10批准新增 `iztro-2.6.1-lunar-year-month-v1`。调用 `scripts/ziwei_dynamic_facts.mjs` 时，出生日期/索引是上游已经解析的紫微钟面；目标日期/索引也显式提供，不默认取系统时区或出生地。新动态层按锁定2.6.1的春节年界、农历月及闰月16日起推进源规则；不改出生口径、公历目标年差加一年龄、大限与固定生年四化。

只有admitted的yearly/monthly/daily事实可用，raw.age/raw.decadal/hourly整层不可准入，不用两种年龄拼全套运限。目标晚子时index12，源日宫与日干支存在不同步风险，admitted daily只输出withheld与原因，不提供组合视图；年/月可继续。原始源值不改。单点输出不证明全天/整月覆盖，须按实际变化分段。年/月解释范围与日级效力边界见docs/ziwei-dynamic-facts.md。
