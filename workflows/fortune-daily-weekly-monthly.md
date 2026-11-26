# Fortune-Daily-Weekly-Monthly — 今日/近期/流年运势流程

> 适用于「今日运势 / 本周节律 / 本月留意什么 / 今年（某公历年）运势」。

## 一、明确时间段与三盘历法边界（务必先行核清）

在答复流年、流月、流日运势前，严格区分三盘不同的年界、月界与日界，**绝不把公历 1 月 1 日、立春节气、农历正月初一与实测行星过宫混为一谈**：
1. **八字岁运月日（`scripts/pai_pan_bazi.py`）**：
   - 流年以**立春交节瞬**切换；流月以**十二节（立春/惊蛰/清明……）**切换；日柱在 **23:00 晚子时**换次日。
   - 查询当日/当月准确干支直接调用 `pai_pan_bazi.py` 对目标日期时间排盘核对（不靠心算）。
2. **紫微动态流年/流月/流日（`scripts/ziwei_dynamic_facts.mjs`）**：
   - 动态流年以锁定 `iztro 2.6.1` **农历正月初一（春节）**切年，流月按农历月（闰月 16 日起属次月规则随原库），**与 `pai_pan.ts` 的“公历出生年减加一虚岁大限”分层处理，不互相覆盖**。
   - 目标日处在 **23:00–23:59 晚子时 (`--target-time-index 12`)** 时，`ziwei_dynamic_facts.mjs` 会标记 `daily` 为 `withheld`；此时只用年、月层与八字晚子时换日对照。
3. **七政四余动态大限与流年/流月/流日过宫（`scripts/qizheng_dynamic_facts.py`）**：
   - **洞微大限（限宫/限度）与小限**：以实测出生瞬间起算，小限依《星学大成》**生日后交过宫**。
   - **流年太岁与流年变曜**：与八字统一按**物理立春交节瞬**切换年干支。
   - **流年/流月/流日过宫过宿**：基于 `calibrated-v3`（SIMBAD 28 宿实时岁差 + VSOP87 太阳 + JPL 校验月五星）按真实物理时刻二分精确到分，覆盖全年慢星/日火过宫、当月太阳过宿与政余过宫（含逆行）、当日太阴过宫过宿及原流同宫/对冲/同度交汇。

## 二、执行三盘动态查询脚本

1. 本命原盘需已就绪（见 `docs/onboarding.md`）。先运行紫微动态坐标脚本：
   ```bash
   node scripts/ziwei_dynamic_facts.mjs \
     --solar <出生YYYY-MM-DD> --birth-year <民用出生年> \
     --shichen-index <出生0-11> --sex <男|女> \
     --target-date <目标YYYY-MM-DD> --target-time-index <目标0-12> \
     --source-label daily-reading
   ```
   只提取 `admitted_dynamic_facts.layers` 中 `yearly` / `monthly` / `daily`（`status="facts_only"`），不使用被禁用的 `age` / `decadal` / `hourly`。
2. 运行七政动态流运与过宫脚本（需出生地经纬度；若用户缺经纬度则明确说明七政动态项缺失，不编造替代）：
   ```bash
   python3 scripts/qizheng_dynamic_facts.py \
     --solar <出生YYYY-MM-DD> --hour <出生HH:MM> \
     --lat <出生纬> --lon <出生经> \
     --target-date <目标YYYY-MM-DD> --target-hour <目标HH:MM> \
     --scope all --format json
   ```
   提取 `dongwei_active`（限宫/限度/小限/行限提醒）与 `layers.{yearly,monthly,daily}`（太岁引动、流年变曜、过宫过宿事件、流日十一曜落本命宫与原流交汇）。
3. 同时查出目标公历日所在节气月与日柱干支（`python3 scripts/pai_pan_bazi.py --solar <目标YYYY-MM-DD> --hour <HH:MM> --sex <男|女>`），看其对原局日主与当前大运的生克合冲关系。
4. 用 `scripts/mingli_query.py search` 查核相关流年/流月十神作用、紫微动态四化星曜含义，及七政洞微/流年原典（`--system qizheng --layer dongwei_liunian`）。

## 三、输出结构（轻快、实用、不宿命）

1. **整体基调**：一句话定下今天/本周/本月/今年的大方向（顺畅窗口、磨合梳理、蓄力收敛还是防冲动决策）。
2. **三盘动态节律对照**：
   - 八字：流年/流月/流日干支与原局的生克冲合；
   - 紫微：流年/流月（及可用流日）四化重点落宫；
   - 七政：当前洞微大限限宫限度、小限、流年太岁引动，以及目标周期内关键政余过宫/太阴日过宿与原盘命度/身度/限度交汇。
3. **分类提醒（仅聚焦当前周期真正触动的部分）**：
   - 💼 **工作/财务动作**：宜推进之事 vs 易踩坑点；
   - 💬 **人际/感情沟通**：情绪敏感处或沟通盲区；
   - 🔋 **状态与作息**：精力分配建议（不过度制造焦虑；若有“冲”“忌”“难度/煞刃”，转译为需多留一手预案、谨言慎行或放慢节奏）。
