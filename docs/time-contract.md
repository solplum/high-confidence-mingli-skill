# 时间口径与误差处理（Time Contract）

> 排盘出错往往不是排盘算法本身，而是**夏令时、时区偏移、真太阳时与晚子时换日**混淆。本仓三引擎全部按明确时间参数运行，不偷偷猜测或替用户改写时钟。

## 1. 四类时间参数（`build_chart.py`）

- `--time-basis civil`（默认）：直接使用输入的民用钟表时刻推八字日时柱与紫微时辰。节气交节、大运起运与七政行星星历始终基于真实的物理瞬时计算。
- `--time-basis mean-solar` / `apparent-solar`：需显式传入 `--lon <东正西负经度>`。将 `UTC + 经度 × 4分钟`（平太阳时）及均时差修正（真太阳时）后的钟面**同时进位日期与时辰**传入八字日时与紫微；向下取整到分钟，不四舍五入偷跨界。
- `--utc-offset <小时>`（默认 `+8`）与 `--timezone <IANA 时区>` 互斥：在实行过夏令时的历史年份（如中国 1986–1991 年、欧美多国）建议显式传入 `--timezone Asia/Shanghai`；遇跳时不存在时刻直接报错，遇重复时刻须显式指定 `--fold 0`（较早）或 `--fold 1`（较晚）。
- **七政特别口径**：默认 `physical-v2` 按太阳中心几何高度 `-0.833°` 判断昼生/夜生，角宿一原点随日期进动；**立命宫**仍按传统果老安命（+08 时辰推算），且二十八宿与十二宫边界为未校勘近似值，近边界点应在解读中提示误差。

## 2. 出生时间不准时的候选对比

不要在边界时刻用单盘“碰运气”。使用：
```bash
python3 scripts/build_chart.py --solar 1986-01-03 --hour 23:00 --sex 男 \
  --timezone Asia/Shanghai --uncertainty-minutes 30 --enumerate-scenarios \
  --analysis-year 2026 --format json
```
- `civil` 与 `mean-solar` 在真实可达的 UTC 闭区间内逐一检查午夜、奇数整点、交节瞬间与时区跳变，给出离散候选 `scenarios.variants`、`stable_fields`、`changing_fields` 与八字折月起运分界。
- `apparent-solar` 对均时差边界作数值包围寻找见证样本，**不声明穷尽所有短区间**（`coverage = numerical_witnesses_not_exhaustive`）。

## 3. 各盘换日、年龄与动态流年口径（不混用）

| 维度 | 八字（`pai_pan_bazi.py`） | 紫微（`pai_pan.ts` / `ziwei_dynamic_facts.mjs`） |
|------|----------------------------|---------------------------------------------------|
| 年界 | 严格按物理**立春**交节瞬间 | 静态表按公历出生年减加一虚岁；动态流年 (`ziwei_dynamic_facts.mjs`) 按锁定 `iztro 2.6.1` **春节**切年 |
| 换日 | 23:00 晚子时换次日日柱 | 默认保持原副本凌晨 00:00 换日、`shichenIndex = 0`；晚子时（23:00–23:59）输出警告提醒核查差异 |
| 大运/大限 | 按交节精确时距折月计算 `qiyun_years` + `qiyun_months` 及半开区间 `dayun_age_windows` | 按公历年度窗展示 `daXians`；**不把紫微虚岁直接套入八字折月起运** |
| 动态事实 | 出生四柱 + 大运流年干支标签 | `ziwei_dynamic_facts.mjs` 仅提取独立**流年 / 流月 / 流日**坐标；若目标在晚子时 (`index=12`)，日宫与日柱可能不同步，自动标记 `withheld` |

## 4. 历法近似提示

- 定气定朔基于内置 Meeus 算法（支持 1900–2100 年回归范围内主要民用日期）。若当前农历月朔点或节气交节落在距午夜 120 秒以内，`calendar_policy` / `warnings` 会主动提示边界风险；遇到此类提示时应兼看交界前后两种可能，并可与香港天文台（HKO）公开年表交叉核对。
- 回归测试：`python3 -B -m unittest scripts/test_time_scenarios.py scripts/test_time_contract.py scripts/test_solar_precision.py scripts/test_ziwei_dynamic_facts.py -v`。
