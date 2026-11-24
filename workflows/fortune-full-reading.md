# Fortune-Full-Reading — 个人命局详批流程

> 适用于「帮我看看一生命盘 / 全盘详批 / 大运走势 / 深度解读」。

## 一、输入与排盘准备

1. 核对 `~/.claude/fortune-telling/chart.md` 与 `snapshot.json`；缺失时先按 [建档流程](../docs/onboarding.md) 收集出生时间、出生地经纬与性别，运行：
   ```bash
   python3 scripts/build_chart.py --solar YYYY-MM-DD --hour HH:MM --sex <男|女> \
     --lat <纬> --lon <经> --place "<地名>" --analysis-year <当年> --format json
   ```
2. 存在出生时刻不确定性时，增跑 `--uncertainty-minutes <N> --enumerate-scenarios` 检查四柱、起运与紫微是否跨时辰或交节边界；**不知时辰**则只用 `scripts/pai_pan_bazi.py` 走六字详批。
3. 运行统一原典检索获取各系统底稿：
   ```bash
   python3 scripts/mingli_query.py chart-lookup --chart-json ~/.claude/fortune-telling/snapshot.json --topic general --limit 5
   python3 scripts/mingli_query.py bazi-lookup --day-stem <日干> --month-branch <月支> --limit 6
   ```
   针对命主重点关切领域，追加 `--topic career|love|wealth|health`。

## 二、三盘各自深读骨架

1. **八字篇（定气象、格局、旺衰与大运主线）**
   - 原局骨架：日干气象 → 《穷通宝鉴》寒暖燥湿调候 → 月令格局与透干用神/相神（《子平真诠》）→ 全局流通与旺衰喜忌（《滴天髓》）。
   - 大运脉络：按 `pai_pan_bazi.py` 的 `qiyun_years / qiyun_months` 与 `dayun_age_windows` 逐运梳理重点转折窗口（重点看前中晚三段：早年学业根基、当前运＋下一步运的顺阻与用神进退、晚运安顿），注意折月区间与虚岁区别。
2. **紫微篇（定性格机制、宫位联动与十年大限）**
   - 本命结构：命宫＋身宫所在，主星原始亮度 `brightnessRaw`、三方四正辅煞搭配、固定生年四化落宫（`sihua-tables.md`）及引擎命中的传统格局条件（先看成格条件，再看是否被煞忌破格）。
   - 宫位联看：分别按命主现状要点出事业（官禄/迁移）、财禄（财帛/田宅）、感情（夫妻/福德）、身心（疾厄）之间的联动逻辑，再按 `daXians` 公历年度窗说明当前大限与下一大限的课题切换。
3. **七政四余篇（定昼夜、命度与恩用难仇）**
   - 如无经纬度缺命度/立命，保留行星躔宿与十二宫分布并如实注明未算项。
   - 若完整排出：先依 `day_night` 定昼日/夜月取重；看 `ming_du`（度主五行）与难仇恩用分布；再看 `ming_gong` 立命宫与官福田财妻诸强宫守曜及 `references/qizheng/states-tables.md` 升殿/庙乐旺制刑状态。不补算引擎未做的洞微倒限。

## 三、交付报告结构

1. **核心命局画像与一句话定调**：先用平实白话概括整体格局特征、人生主舞台（适合专业纵深、管理组织、自主创业还是稳健蓄积）与核心优势/短板。
2. **分领域三盘交叉精读**（结合 `references/domain-signals.md`）：
   - **性格与行事底色**：说明外在表现、压力反应与长期内耗来源（附实盘依据，不贴死板标签）。
   - **事业与财富路线**：指出契合的工作模式、合作/管理重心、现金流 vs 长期资产倾向。
   - **感情与人际关系**：剖析亲密关系模式、双方节奏差异与常见摩擦点。
   - **健康节律提醒**：从寒暖失衡、疾厄星曜与过劳窗口给出作息调养方向（如涉具体不适，提示优先就医）。
3. **大运与近 3–5 年行动节奏**：明晰当前大运/大限在做什么功课、何时该攻、何时该守。
4. **原典依据与口径边界清单**：集中列出本次所引用的古籍出处 ID、时间误差假设与三盘分歧点，让读者看得见推论从何而来。
