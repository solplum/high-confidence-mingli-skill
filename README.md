# 高置信度命理 Skill · High-Confidence Mingli Skill

![Code license: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)

Third-party study packet: CC BY-SA 4.0; see the license exceptions below. / 第三方学习包另用CC BY-SA 4.0，见下方许可例外。
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Node.js](https://img.shields.io/badge/node-18.19%2B-green)
![Checks](https://img.shields.io/badge/checks-see_verification-blue)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**简体中文** | [English](#english)

---

## 简体中文

> 八字、紫微、七政先各自核查盘面与解释条件，
> 再对照一致、冲突与缺口；重要判断保留可核对的字段、来源和反向信号。
>
> 排盘用引擎算，不靠 AI 口算；跨盘一致不代表准确率；来源检查也不证明预测能力。

一个装进 agent CLI（Claude Code / Codex / Kimi Code 等任何读 SKILL.md 的环境）的
命理对话伴侣。提供传统文化解释：排盘由程序计算，重要判断可追溯来源，但不保证排盘无误或现实预测准确。

### 它是怎么做到的

| | 机制 | 一句话 |
|---|------|--------|
| 🔢 | **确定性排盘引擎** | 四柱/安星/躔度由三套引擎计算（Meeus 定气八字 / iztro 紫微 / 自研恒星制七政）；回归测试检查已覆盖的实现契约，大模型不口算替代引擎 |
| 📜 | **可追溯资料解读** | 先经来源门，再区分资料释义、作者现代转译与条件综合；实际依据可查，现代整理与数字录文不冒称核验古籍原文 |
| ⭐ | **跨盘对照，不是投票** | 星级仅为旧版关联展示；个人分析用证据记录、条件与限制，不输出可靠度星级 |
| 🔁 | **自愿反馈与版本记录** | 用户愿意时先冻结判断再记录反馈；旧事回顾不算盲测，不用命中反馈计算准确率 |

### 所有个人分析默认深入核查与充分解释

运势、具体问题、共鸣溯源和完整详批共用 [可复核分析流程](workflows/fortune-auditable-reading.md)。问题范围决定检查哪些领域；用户要求短答时只压缩正文，仍执行相同的核查标准。

[统一解释与裁决标准 v3](docs/interpretation-standard.md)区分盘面事实、可定位传统释义、作者现代转译与综合推论，先回答所问问题，再说明依据和建议。个人分析分别判断外部形势、目标推进与代价、主观体感；有依据时给总体及领域倾向，必要条件或时间层不足时明确暂不能定性，不把未知写成平稳或好坏相抵。性格与偏好注明自述或条件假设的来源，用于解释体验和适配，不补造外部机会。合理现代转译无需逐词预注册，作者解释保留自身身份。

1. 固定出生输入、时间口径、误差和分析范围，保存实际引擎快照；相关边界有候选比较或明确缺口。
2. 各盘分别核对事实，按来源门查询本次适用资料，再记录规则前提、支持与反向信号及竞争解释。程序输出的有限结构摘要是分析底稿，不是完整详批。
3. 按领域记录“已分析 / 已检查但暂不判 / 无数据 / 不适用”，覆盖本次问题需要的内容；不能用列出星曜、神煞或格名代替判断条件。
4. 单独复审字段、引文、规则适用性、推导、时间分支和遗漏，同时检查过度断言、解释不足及是否回答了实际问题；同一时间、领域、目标和评价对象的相反信号须说明主次或具体未决原因。有独立 agent 时可分工，无并行工具时顺序复审并保存结果，再进行跨盘对照。
5. 正文先给对象和范围清楚的结论，再按主题解释依据、代价、反向条件和边界。先冻结结构判断，再接入有来源的现实性格与目标作体感/适配解释；保留原判、反馈及修订理由。具体缺口只限制受影响部分，建议不替代判断。

本次证据保存在用户数据目录，通常包括实际命令与快照、来源索引、[分析工作记录](templates/reading-workpad.template.md)、适用的重要判断 ledger 或原生模块人工解释记录，以及复审/校验结果；无法生成的产物如实标缺。两种记录保留各自用途，不为通过校验创建假 claim。它们是可复核的依据摘要，不要求公开隐藏思维过程。以检查和解释完成情况验收，不规定最低耗时、篇幅或引用条数；结构校验通过也不证明预测准确。

已批准的[有限模型方法 M0](docs/model-judgment.md)先核完整条件及具体反条，再同时给条件模型结果和稳健性。一般未决生克关系不自动取消完整模型，也不作零影响；有依据阻断必要条件时仍须改判。模型有方向与现实有效是两项问题。

### 维护者的真实案例评测

维护者可以用外部赛事标签评估八字和紫微的答题覆盖与选项一致性。工具按命主分组、隔离答案并保留答错、拒答与信息不足，真实题目和出生资料存放在技能包之外。赛事标签与合成回归各有评估范围。日月运势、一生走势、婚姻和健康的现实预测准确率尚未建立。操作与限制见 [外部案例评测](docs/reading-benchmark.md) 和 [判势能力说明](docs/judgment-capabilities.md)。`proposals/` 保留增补审查稿，实际用途以知识登记为准。

已批准并接入的增补为 BZ-K01～04 与 ZW-K01～05，默认输出独立 `reviewed_structure`：包含八字方向/角色检查、紫微空宫/辅星/宫位/本命四化结构，以及三个条件受限的观察主题。原始盘面与旧解释层保持兼容，具体范围见 [已批准结构增补](docs/approved-structural-reading.md)。它们不提供人生事件预测或准确率保证。

### 可运行的端到端演示

当前可运行的端到端演示见 [examples/engine-reading/README.md](examples/engine-reading/README.md)。
使用虚构出生输入，实际生成三个引擎的快照、证据记录及易读报告，包含边界分支。
它验证工程管线与有限的条件式解释，不是命中率评测或真实用户详批。

### 安装与开始

```bash
# 1. 首次安装 GitHub 已发布的版本（以 Claude Code 为例）
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/high-confidence-mingli-skill

# 2. 启用紫微引擎（一次性；不装则紫微盘自动降级）
cd ~/.claude/skills/high-confidence-mingli-skill/scripts/pai_pan_ziwei && npm ci
```

然后在 CLI 里说 `/high-confidence-mingli-skill`，或直接开口："今日运势""帮我详批"。
首次运行引导建档：核对出生信息与时间口径 → 生成可用盘及快照 → 深入分析与复审 → 可选反馈。
完整总控只接收公历日期和明确钟表时间；未知时辰使用可支持的八字六字路径，不填假定时刻生成三盘。见 [建档流程](docs/onboarding.md)。
排盘脚本在本地运行；使用云端 agent 解读时，输入会依所选服务的数据政策处理。请勿把用户档案提交到公开仓库。

### 旧版升级

注册名、安装目录名和显式调用名均为 `high-confidence-mingli-skill`。若此前安装到了 `~/.claude/skills/fortune-telling/`，先备份本地改动，再将该安装目录重命名为 `~/.claude/skills/high-confidence-mingli-skill/`（目标已存在时先检查两份内容，不要覆盖）。在新目录更新代码，重启 CLI 后使用 `/high-confidence-mingli-skill`。不要同时保留两份可发现的安装。

用户资料继续使用 `~/.claude/fortune-telling/`，包括 `chart.md`、`memory.md` 和 `memory-archive/`；这是兼容数据路径，不是技能注册名，无需迁移或重新建档。

### 工作原理（给想深究的人）

- **排盘层** `scripts/`：八字引擎用 Meeus 定气定朔（纯标准库，1900-2100）；紫微用 iztro 2.6.1；七政采用自研恒星制及声明的果老安命口径，输出躔宿、躔宫等数据。计算版本、近似项和学派口径以引擎文件头及对应合同为准。基础和扩展回归覆盖若干参照值、时间边界、坐标与字段合同，不证明所有地点、年代或解释均准确。
- 紫微精确亮度请读取新增 `brightnessRaw`，缺失为 `null`；旧 `brightness` 仅为合并分组，不能据此细分庙旺。[字段口径](docs/ziwei-brightness.md)。
- **解读层**：先读 [知识来源门](knowledge/README.md)。八字/紫微八份旧资料逐字节保留，另有17篇固定版本 iztro-docs 资料与原许可。个人解读只使用各来源门明确允许的用途，不把数字录文或现代汇编当作已核古籍原文。七政旧资料的书名声明不代表完成原典校勘；后续独立研究包的影像核查仅限其明示页段和用途，不自动解禁旧材料。详见 [来源记录](references/README.md)。
- **管线**：固定输入与快照 → 单盘查证和领域分析 → 单独复审 → 跨盘证据对照 → 主题正文与现实建议。详见 [SKILL.md](SKILL.md) 和 [共享分析流程](workflows/fortune-auditable-reading.md)。

### 文档地图

| 文档 | 内容 |
|------|------|
| [SKILL.md](SKILL.md) | 技能入口：路由、共享分析标准和数据约定 |
| [docs/onboarding.md](docs/onboarding.md) | 建档流程（含历史事件校准） |
| [references/README.md](references/README.md) | 解读资料层溯源表 |
| [workflows/fortune-full-reading.md](workflows/fortune-full-reading.md) | 详批模式（长文批盘） |
| [workflows/fortune-auditable-reading.md](workflows/fortune-auditable-reading.md) | 所有个人分析的查证、覆盖、复审与交付标准 |
| [docs/model-judgment.md](docs/model-judgment.md) | M0：完整条件、反条、模型结果与稳健性 |
| [docs/interpretation-standard.md](docs/interpretation-standard.md) | v3：分层解释、总体/领域裁决与性格体感标准 |
| [templates/reading-workpad.template.md](templates/reading-workpad.template.md) | 本次分析记录、领域覆盖与复审底稿 |

### 限制与口径

1. 七政使用声明的恒星参考系与近似宿宫界；与其他软件的差异须逐项查坐标、边界和安命口径，不能统一归因于固定角差
2. 七政月限/小限（限度推算）不包含；洞微百六限等倒限内容不入典籍库、解读不断流年应期；
   变曜/化曜/神煞层（年干起例）同理不做
3. 紫微引擎需要 node（`npm ci` 一次），缺环境时该盘自动降级
4. 时代运等传统背景不能替代本盘条件、现实原因或具体时间证据
5. 运势为未经统计校准的传统解释框架，不提供预测概率——命理分析仅供参考，人生在于自身的努力和选择
6. 自动未编码或未裁决的部分，可在已有资料与获准解释方法范围内继续人工研究，原模块状态保持不变；必要字段、条件、来源隔离和计算契约仍约束判断，八字窄强弱、紫微四宫与七政受限模块不能包装成全体系自动详批
7. 引擎或依赖不可用时保留缺盘及不能校验的字段，不以口算替代正常深入分析

---

## English

> BaZi, Ziwei Doushu and Qizheng Siyu first check their own chart facts and rule conditions.
> Interpretations are then compared for agreement, conflict and missing evidence.
> Important claims retain inspectable fields, sources and contrary signals.
>
> Charts are computed by engines, not LLM mental arithmetic. Cross-chart agreement is not evidence of predictive accuracy.

A fortune-telling companion that lives inside your agent CLI (Claude Code /
Codex / Kimi Code — anything that reads SKILL.md). It provides traditional interpretations with traceable claims, explicit conditions and limitations. Computation and interpretation can both be wrong.

### How it works

| | Mechanism | In one line |
|---|-----------|-------------|
| 🔢 | **Deterministic chart engines** | Four Pillars / star-placing / planetary degrees are computed by three engines (Meeus-based BaZi / iztro Ziwei / self-built sidereal Qizheng); regressions check covered implementation contracts, and the LLM does not replace engines with mental arithmetic |
| 📜 | **Source-attributed reading** | Apply the provenance gate, then distinguish source interpretations, the author's modern translations and conditional synthesis; retain inspectable premises, and do not present modern compilations or digital transcriptions as authenticated classical quotations |
| ⭐ | **Cross-chart comparison, not voting** | Legacy stars are association labels only; personal readings record evidence and uncertainty, not accuracy ratings |
| 🔁 | **Optional feedback and versioning** | Freeze claims before feedback, retain misses, and never treat known events as blind validation or use feedback to compute accuracy |

### Thorough checks and substantive interpretation for every personal reading

Fortunes, specific questions, resonance tracing and full readings share the [auditable analysis workflow](workflows/fortune-auditable-reading.md). The question determines which domains need examination. A request for a short answer reduces presentation length while preserving the same checks.

The [shared interpretation and judgment standard v3](docs/interpretation-standard.md) distinguishes chart facts, locatable traditional interpretations, the author's modern translations and synthesis. Answer the question before explaining evidence and offering advice. Personal readings separate external conditions, goal progress and costs, and subjective experience. Give overall and domain directions where supported; disclose an undecidable judgment when necessary conditions or time layers are missing, rather than calling the unknown neutral or balanced. Attribute personality and preferences to self-report or a conditional hypothesis, using them to explain experience and fit rather than invent external opportunities. Reasonable modern wording need not be registered word by word; preserve the author's role.

1. Fix birth inputs, time conventions, uncertainty and scope, then save actual engine snapshots. Compare relevant boundary candidates or disclose what remains unchecked.
2. Check each chart separately, retrieve permitted material through the provenance gate, and record prerequisites, supporting and contrary signals, and competing interpretations. Limited engine summaries are analysis inputs, not complete readings.
3. Record domain coverage as analyzed, checked but withheld, missing data or not applicable. Listing stars, symbolic markers or pattern names does not check their conditions.
4. Separately review fields, quotations, rule applicability, inference, time branches and omissions, checking overstatement, insufficient explanation and whether the actual question is answered. Explain which opposing signals take precedence within the same time, domain, goal and evaluation object, or why the comparison remains unresolved. Use an independent agent when available; otherwise preserve a sequential review record before cross-chart comparison.
5. Lead with a judgment whose object and scope are clear, then explain evidence, costs, contrary conditions and boundaries by theme. Freeze structural judgments before adding sourced real-world personality and goals to discuss experience and fit. Retain the original judgment, feedback and revision reasons. Limit only the parts affected by a specific gap; advice does not replace judgment.

Evidence stays in the personal data directory and normally includes actual commands and snapshots, a source index, an [analysis workpad](templates/reading-workpad.template.md), an applicable claim ledger or native-module interpretation records, and review/validation results. Preserve each record's permissions rather than inventing claims to pass validation; disclose unavailable artifacts. These are concise auditable evidence summaries, not hidden reasoning transcripts. Completion depends on checks and substantive explanation, not minimum elapsed time, word count or citation count; structural validation does not establish predictive accuracy.

The approved [bounded-model method M0](docs/model-judgment.md) checks complete conditions and specific counterconditions before reporting a conditional model result together with robustness. Generic unresolved relationships do not automatically cancel a complete model or count as zero effect; supported defeat of a necessary condition still requires revision. A model direction does not establish real-world validity.

### Maintainer evaluation with real cases

Maintainers can use external competition labels to evaluate BaZi and Ziwei answer coverage and agreement with labeled choices. The tool splits cases by person, isolates answers, and retains errors and abstentions. Real questions and birth records stay outside the skill package. Competition labels and synthetic regressions have separate evaluation scopes. Real-world accuracy for daily or monthly fortune, lifetime trends, marriage and health remains unestablished. See [external case evaluation](docs/reading-benchmark.md) and [current capabilities](docs/judgment-capabilities.md). `proposals/` holds review drafts, and the registry defines active uses.

The approved BZ-K01–04 and ZW-K01–05 ranges are now available in a separate default `reviewed_structure` panel: BaZi direction and role checks, Ziwei empty-palace, adjunct, position and natal-transformation checks, plus three bounded observation themes. Raw charts and earlier reading layers remain compatible. See [approved structural additions](docs/approved-structural-reading.md) for scope. These additions do not predict life events or guarantee accuracy.

### Executable end-to-end example

See [the executable end-to-end demo](examples/engine-reading/README.md): fictional inputs, actual engine snapshots, a ledger and a readable conditional report, including boundary branches. It is not a predictive-accuracy evaluation.

### Install and begin

```bash
# 1. Install the published GitHub version (Claude Code shown)
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/high-confidence-mingli-skill

# 2. Enable the Ziwei engine (once; skipped gracefully if absent)
cd ~/.claude/skills/high-confidence-mingli-skill/scripts/pai_pan_ziwei && npm ci
```

Then say `/high-confidence-mingli-skill` in your CLI, or just talk: "today's fortune",
"full reading of my chart". First run checks birth inputs and time conventions, generates available charts and snapshots, and performs analysis and review before optional feedback. The combined builder accepts a Gregorian date and a known clock time; unknown birth time uses the supported BaZi six-character path rather than an assumed time for all three charts. See [onboarding](docs/onboarding.md). Engine scripts run locally. Cloud-agent interpretation is subject to your chosen provider’s data policy; never commit private charts to a public repository.

### Upgrading an older installation

The registered name, installation folder name and explicit invocation name are all `high-confidence-mingli-skill`. If you installed into `~/.claude/skills/fortune-telling/`, back up local changes, then rename that installation folder to `~/.claude/skills/high-confidence-mingli-skill/`. If the destination already exists, inspect both copies first; do not overwrite it. Update the code in the renamed folder, restart the CLI, and invoke `/high-confidence-mingli-skill`. Do not leave two discoverable installations.

Keep personal data in `~/.claude/fortune-telling/`, including `chart.md`, `memory.md` and `memory-archive/`. This is a compatible data path, not the registered skill name; no data migration or new onboarding is needed.

### Under the hood

- **Chart layer** `scripts/`: BaZi via Meeus solar-term/syzygy math (pure stdlib, 1900-2100); Ziwei via iztro 2.6.1; Qizheng uses the self-built sidereal engine and its declared traditional ascending convention. Engine headers and owning contracts define calculation versions, approximations and school conventions. Base and extended regressions cover selected reference values, time boundaries, coordinates and field contracts; they do not establish accuracy for every location, era or interpretation.
- Ziwei exact brightness is available in additive `brightnessRaw` (`null` when unavailable); legacy `brightness` remains a collapsed grouping. See [source fidelity](docs/ziwei-brightness.md).
- **Interpretation layer**: read [the provenance gate](knowledge/README.md) first. Eight legacy files remain byte-identical; 17 pinned iztro-docs files retain their source hashes and upstream license. Personal readings use only the purposes explicitly permitted by each source gate. Digital transcriptions and modern compilations are not authenticated classical editions. Legacy Qizheng book labels do not establish collation; image checks in later independent study packets apply only to their declared pages and uses, without unlocking old materials. See [source records](references/README.md).
- **Pipeline**: fixed inputs and snapshots → per-chart source checks and domain analysis → separate review → cross-chart evidence comparison → thematic explanation and practical suggestions. See [SKILL.md](SKILL.md) and the [shared analysis workflow](workflows/fortune-auditable-reading.md).

### Docs

| Doc | Content |
|-----|---------|
| [SKILL.md](SKILL.md) | Skill entry: routing, shared analysis standards and data conventions |
| [docs/onboarding.md](docs/onboarding.md) | Onboarding flow (incl. historical-event calibration) |
| [references/README.md](references/README.md) | Interpretation-layer provenance |
| [workflows/fortune-full-reading.md](workflows/fortune-full-reading.md) | Full-reading mode (long-form chart reading) |
| [workflows/fortune-auditable-reading.md](workflows/fortune-auditable-reading.md) | Source checks, coverage, review and delivery standards for all personal readings |
| [docs/model-judgment.md](docs/model-judgment.md) | M0: complete conditions, counterconditions, model result and robustness |
| [docs/interpretation-standard.md](docs/interpretation-standard.md) | v3: layered interpretation, overall/domain judgments, personality and subjective experience |
| [templates/reading-workpad.template.md](templates/reading-workpad.template.md) | Analysis, domain-coverage and review workpad |

### Limitations & conventions

1. Qizheng uses its declared stellar reference frame and approximate mansion/palace boundaries. Differences from other software need coordinate, boundary and ascending-convention checks rather than a universal fixed-angle explanation
2. Qizheng monthly/minor limits, other limit-degree timing, and year-stem transformation/symbolic-marker layers are not included in readings
3. The Ziwei engine needs Node.js (`npm ci` once); without it that chart
   degrades gracefully
4. Traditional period backgrounds do not replace chart conditions, real-world causes or specific timing evidence
5. Readings are uncalibrated traditional interpretations, not predictive probabilities or guidance for consequential decisions
6. Unencoded or undecided interpretations may be researched manually within available material and the approved method, preserving the original module status. Required fields and conditions, quarantined sources and calculation contracts still constrain judgments; bounded BaZi strength rules, Ziwei four-domain themes and restricted Qizheng rules do not form a fully automated reading of all three traditions
7. Unavailable engines or dependencies leave explicit missing charts and unchecked fields; mental arithmetic does not substitute for a normal thorough analysis

---

## License

MIT for project code — see [LICENSE](LICENSE). The independent Wikisource study packet and its identified catalog adaptations are CC BY-SA 4.0, not MIT; see [packet license](references/vendor/wikisource-ditiansui/LICENSE.md).


### 时间精度修复（兼容模式）

默认保留民用时间口径；`--time-basis apparent-solar` 显式选择太阳钟面，日期进位同步作用于八字日时柱和紫微。节气/起运仍用原始瞬间。`--utc-offset` 指定出生时实际 UTC 偏移，`--uncertainty-minutes` 标记非唯一候选，`--age-year` 控制紫微大限年度。详见 [时间契约与回归](docs/time-contract.md)。新增测试：`python3 scripts/test_time_contract.py`。紫微 Node 最低 18.19，依赖通过 `npm ci` 安装；总控不自动下载执行缺包。

### Time-contract fixes (backward-compatible mode)

Civil time remains the default. Select `--time-basis apparent-solar` explicitly to pass the corrected date and clock into BaZi day/hour pillars and Ziwei. Solar terms and luck-start intervals retain the original instant. `--utc-offset` supplies the actual birth-time offset; `--uncertainty-minutes` labels the center-time chart as a candidate; `--age-year` controls the Ziwei decadal year. See [time conventions and regression scope](docs/time-contract.md). Run `python3 scripts/test_time_contract.py`. Ziwei requires Node 18.19+ and `npm ci`; the orchestrator no longer downloads missing runners automatically. These tests do not establish predictive validity or independently calibrated astronomical precision.

### 可复核快照 / Auditable snapshots

`python3 scripts/build_chart.py --solar 2000-05-15 --hour 12:00 --sex 男 --lat 31.23 --lon 121.47 --analysis-year 2026 --format json`

默认文本不变；JSON 提供原始结构、实际时间口径、源文件摘要及缺盘原因。
Text remains the default. JSON preserves computed structures, time conventions, source hashes and explicit degradation.
所有个人分析共用深入核查流程；命令只生成快照及有限结构摘要，agent 仍须完成资料查询、领域分析和复审。
All personal readings share the thorough checking workflow. This command generates snapshots and limited structural summaries; the agent still performs source retrieval, domain analysis and review.

### 固定分析年 / Explicit analysis year

为跨年复现完整快照，使用 `--analysis-year 2026`：同时固定八字当前年/流年列表和紫微目标年；出生瞬间与本命计算不变。默认不指定时保持兼容。旧 `--age-year` 仍仅控制紫微；两者指定不同值会报错。
For cross-year reproducibility use `--analysis-year 2026` to pin both BaZi annual fields and Ziwei target year. Natal inputs remain unchanged. Omitting it preserves legacy defaults. The Ziwei-only `--age-year` stays compatible; conflicting values are rejected.

### 历史时区与误差候选 / Historical zones and bounded scenarios

可选 `--timezone Asia/Shanghai` 使用 IANA 历史偏移，拒绝不存在的民用时间，重复时间必须显式 `--fold 0/1`。`--time-basis mean-solar` 区分平太阳时。`--enumerate-scenarios --uncertainty-minutes 10` 比较可达四柱、紫微离散输入和八字折月起运，限 ±120 分钟、UTC 1901–2099 年。民用和平太阳时报告稳定与变化的排盘字段。真太阳时四柱只报告已算见证。折月起运按物理出生时刻另列年龄段与四柱配对。七政、完整紫微及天文误差按各自范围核查。IANA 模式需要 Python 3.9+ 和可用的时区数据库。[详见时间契约](docs/time-contract.md)。

Optional `--timezone Asia/Shanghai` resolves IANA historical offsets, rejects missing local times and requires explicit `--fold 0/1` for repeated times. `--time-basis mean-solar` distinguishes the mean solar clock. `--enumerate-scenarios --uncertainty-minutes 10` compares reachable BaZi pillars, discrete Ziwei inputs and rounded BaZi luck-start ages, capped at ±120 minutes within UTC years 1901–2099. Civil and mean-solar modes report stable and changing chart fields. Apparent-solar chart coverage is limited to evaluated witnesses. The rounded luck-start output gives age windows tied to physical birth instants and their chart candidates. Qizheng, full Ziwei output and astronomical model errors have separate scope limits. IANA mode needs Python 3.9+ and available time-zone data. [Time contract](docs/time-contract.md).

## 知识层升级 / Knowledge integration

新增资料与隔离规则见 [知识来源门](knowledge/README.md)，完整检查及未完成项见 [验证记录](docs/knowledge-verification.md)。[实际 CLI 示例](examples/imported-knowledge/README.md)把新导入的三方四正说明与虚构排盘四宫字段连接，不代表预测效力。旧八份来源不重复迁移、不改字节。

See the [provenance gate](knowledge/README.md), [verification and limits](docs/knowledge-verification.md), and [actual CLI imported-source example](examples/imported-knowledge/README.md). Sources and licenses remain pinned; classical-quotation mode is disabled for this release. Time-scenario defaults and known calendar discrepancies remain unchanged.

原先18条登记含13条可用项目释义（主要是基本概念和来源限制）与5条隔离记录，不是18条已校勘古籍规则，也不构成完整深度解读知识库。CLI示例只演示宫位关系及证据连接，未完成星曜组合、成格破格、运限综合或完整个人详批。

The original 18 records contain 13 enabled project paraphrases, mainly basic concepts and source limitations, plus 5 quarantined records. They are not 18 authenticated classical rules or a complete deep-reading knowledge base. The CLI example demonstrates palace relationships and evidence linkage only, not a full reading of star combinations, pattern conditions, timing cycles or a person’s life.

### 八字理论学习 / BaZi theory study

`bazi-classical-study` 提供 10 张理论学习卡与 88 字数字短引，含条件、反证和分析清单。学习入口和原始短引仍隔离于个人 ledger。可用于详批的项目释义走下一节的独立入口。 [来源调查与许可](docs/bazi-classical-study.md)

`bazi-classical-study` provides ten theory cards and 88 characters of digital excerpts for checking prerequisites and counterexamples. The study profile and original excerpts are excluded from personal ledgers. The next section describes the separate route for registered project paraphrases. This independent packet and its identified catalog adaptations carry CC BY-SA 4.0. See [sources and license](docs/bazi-classical-study.md).

### 可用于详批的条件式解释 / Conditional interpretation in readings

同一组10张卡现在另提供 `bazi-traditional-conditional` 入口：绑定本盘字段、逐项前提和反证，仅作为未校勘数字转录的项目释义解释结构；不保证预测、不升级supported，也不启用古籍原文模式。旧学习入口与原始短引隔离仍保留。[运行示例](examples/bazi-conditional/README.md)。

The same ten cards now have a separate conditional interpretation profile for chart-bound structural explanations with prerequisites and counterevidence. They remain uncollated project paraphrases, not validated predictions or authenticated classical quotations. Only exact registered paraphrase lines may pass this limited gate; the default study profile and raw excerpts stay restricted. New derivative records and generated explanation ledgers retain CC BY-SA 4.0; generator code remains MIT.

### 日主承受证据增量 / Bounded strength evidence

新增 ST01–ST05：逐位比较月令、同五行根、外部印比及克泄耗。只在公开的窄条件组合下输出偏强/偏弱趋势；争议、缺时和未建模情况保留待定。不计分、不从根数定强弱，不指定唯一喜忌。来源、阴长生乙午/丁酉口径冲突与限制见 [说明](docs/bazi-strength-evidence.md)。CLI 与原始引擎字段不变，JSON 新增 strength_reasoning。

ST01–ST05 now compare seasonal context, operational same-element roots, support and opposing paths. Strong/weak tendencies require explicit narrow conjunctions; conflicting evidence, missing time and source/model disputes remain unresolved. No score, universal classifier, favorable-element prescription or predictive validation is implied. Existing CLI and engine facts are unchanged; structured JSON adds strength_reasoning. See the [source and scope notes](docs/bazi-strength-evidence.md).

### 四宫联读增量 / Conditional four-domain reading

紫微 `rule_output.domain_reading` 负责命、财、官、迁的有限主星主题、亮度与反证。原始 `chart` 与旧 `patterns` 按各自范围保留。空宫借星的可核位置线索见[结构增补](docs/approved-structural-reading.md)。十二宫主题、获准年／月分量及旧年度大限另见[生活领域面板](docs/ziwei-life-reading.md)与[阶段条件](docs/stage-and-spouse-models.md)。借星继承效力、完整组合及运限净方向仍须各自核查。四宫模块的实现见[范围说明](docs/ziwei-domain-reading.md)。

Ziwei `rule_output.domain_reading` covers bounded major-star themes, brightness and counterchecks for Life, Wealth, Career and Travel. Native `chart` and legacy `patterns` retain their respective scopes. See [structural additions](docs/approved-structural-reading.md) for verifiable empty-palace borrowing locations. For twelve-palace topics, admitted year/month components and legacy decadal windows, see the [life-domain panel](docs/ziwei-life-reading.md) and [decadal conditions](docs/stage-and-spouse-models.md). Borrowed-star inheritance, complete combinations and net period directions still need their own evidence. The [four-domain contract](docs/ziwei-domain-reading.md) describes that panel.

### 农历历日政策 / Lunar calendar policy

八字 JSON 新增 `calendar_policy`，区分固定 +08 历日、已知 UTC 与估算 UT1；不重建未经确证的历史历法。当前农历月起讫朔距午夜不超过两分钟时提示风险，不判定日期错误、不自动改日，提示窗不是误差上界。详见 [历日政策与独立审计](docs/historical-calendar-audit.md)。

BaZi JSON now includes `calendar_policy`, distinguishing fixed +08 civil days, known UTC and estimated UT1 without reconstructing unverified historical calendars. Conjunctions bounding the current lunar month trigger a warning within two minutes of midnight. This is a risk disclosure, not an error finding, a date override or an accuracy bound. See the [policy and independent audit](docs/historical-calendar-audit.md).

### 七政有条件传统参照 / Conditional Qizheng tradition

详批可显式选择 `build_chart.py --qizheng-tradition qianyuan-palace-v1`，从真实引擎字段运行 QZT04 的宫主比较，并输出来源、反条件和许可；缺字段、时间不确定或边界不稳时暂不判。其余未核规则、四余取主与人生事件预测未启用。参见 [接入说明与端到端合成样例](docs/qizheng-traditional-integration.md)。

Opt into the chart-linked QZT04 palace-lord comparison with the flag above. Text and JSON share a guarded, conditional explanation with source attribution and separate CC BY-SA study-material licensing. Missing or unsafe inputs are withheld; this does not authorize event predictions or personal-event ledger claims. The original degree-lord route remains separate. See the [integration and reproducibility guide](docs/qizheng-traditional-integration.md).
### 七政出生时间敏感性 / Qizheng birth-time sensitivity

`build_chart.py --qizheng-sensitivity --uncertainty-minutes 120` 可独立比较七政候选，保留星体、命度、宫、昼夜与条件规则的实际见证及数值变化包围。只声明采样观察，不声明完整或稳定；主盘时间不确定规则仍暂缓。默认文本仅列有上限的白话摘要，完整证据使用 JSON 或 `--qizheng-sensitivity-evidence` 导出。它不改变 `--enumerate-scenarios` 的四柱/紫微输入契约。

The independent opt-in compares actual Qizheng candidate charts and rule outputs with bounded sampling and refined change brackets. It does not certify exhaustive coverage or stability, does not unlock uncertain-birth rule conclusions, and preserves the Bazi/Ziwei scenario contract. Default text gives a short plain-language overview. JSON retains complete evidence; add `--qizheng-sensitivity-evidence` to append the identical evidence to text. See [method, limitations and synthetic examples](docs/qizheng-time-sensitivity.md).

两入口可合用：已选择乾元宫主参照且有时间误差时，同时传入上述传统与敏感性选项，候选逐点保留 QZT04；中心结论仍暂缓。紫气、宿界和真太阳时误差仍未校准。

The two opt-ins compose: selected palace-lord tradition is evaluated at actual sensitivity witnesses, while uncertain center conclusions remain withheld. Ziqi, mansion boundaries and true-solar-time errors remain uncalibrated.


### 综合判读与独立动态事实 / Conditional judgment and separate dynamic facts

2026-11-10批准的[综合判读方法](docs/conditional-judgment.md)增加BJ01–BJ08人工工作假说、反向条件和运期比较；BJ07–BJ08的流年/月日是明确标注的作者时间外推。旧ST与结构面板原值不改。紫微[动态入口](docs/ziwei-dynamic-facts.md)接出锁定2.6.1的独立年/月/日事实，保留原年龄大限，晚子时日组合暂缓；已批准年/月主题和禄权条件解释，未启用日级效力、飞化自化或事件保证。完整正文默认在对话，内部证据保存；拒答和未回答不计作分析能力通过。

The approved [conditional judgment method](docs/conditional-judgment.md) adds BJ01–BJ08 manual hypotheses, counterconditions and period comparisons. BJ07–BJ08 yearly/monthly/daily projections are explicitly author-created extensions. Existing ST and structural outputs remain unchanged. The pinned 2.6.1 [Ziwei adapter](docs/ziwei-dynamic-facts.md) exposes separate year/month/day facts, preserves existing age/decadal fields and blocks late-Zi daily combinations. Year/month topics and Lu/Quan conditional readings are approved; daily potency, flying/self transformations and event guarantees remain outside scope. Full readings appear in chat by default. Evidence quality and whether the question was answered are assessed separately.

### 用途与生活领域增补 / Purpose and life-domain extensions

用户于2026-11-10批准[用途与生活领域增补](docs/approved-life-domains.md)：八字增加独立单藏月候选、食神具体用法与有限夏木季节分支；紫微扩展其余八域的主星条件主题、本命/准入年/月四化分量、身宫关注及旧年度年龄合同下的大限议题索引。旧输出与来源门保留。新模块整理事实和研究入口，不自动判成格、个人特征、净吉凶或事件；健康只作生活反思，不作疾病风险、病程或寿命预测。实际分析仍须回答原问题、比较主次并独立复审，未答继续保留。

The user-approved [purpose and life-domain extensions](docs/approved-life-domains.md) add an independent single-hidden-month BaZi candidate route, specific Food-God branches and a limited summer-Wood seasonal case. Ziwei gains bounded major-star themes for the remaining eight domains, natal/admitted year-month transformation components, Body-Palace attention hypotheses and decadal topic indexes under the existing calendar-year age convention. Original outputs and provenance gates remain intact. These panels organize facts and research entry points; they do not automatically establish patterns, personal traits, net fortune or events. Health remains general life reflection, without disease-risk, course or longevity predictions. Readings still require an actual answer to the original question, comparison of competing interpretations and separate review; unanswered items remain visible.

### 紫微具体作用判例 / Specific Ziwei judgment cases

已批准的 `ziwei-judgment-cases-v1` 在独立 `case_judgments` 中提供夫妻宫本命权忌的局部协商阻力、巨门忌遇实际同宫天同的表达反条件，以及原官禄大限与准入年禄权直接落官迁时的有限主动争取适配。来源是固定现代说明，三处年度合同适配明示作者身份；旧15卡与原自动状态保留，不推整年/月日净吉凶或事件。见[接口](docs/ziwei-case-judgments.md)。

The approved `ziwei-judgment-cases-v1` adds an independent `case_judgments` panel: local natal spouse-palace negotiation friction, the Giant-Gate Ji/Tian-Tong expression countercondition, and a narrow annual proactive-application fit under the original decadal-age contract. Source interpretation and the three annual-contract adaptations remain explicit. Existing panels are preserved; these cases do not establish net annual/monthly/daily fortune or events. See the [interface](docs/ziwei-case-judgments.md).


### 子月辛金完整条件用途 / Bounded Xin-Metal Zi-month model

`bazi-qiong-xin-zi-v1` 的QX01–03已批准用于辛日、出生子月的通用整体／发展配置评价；独立 `qiong_xin_zi_model` 保留本命、作者运期适配、B选读与保守异读。先查完整条件及特指反条，再给有边界的模型方向与稳健性；不改出生透藏、原自动状态、来源隔离或健康／事件边界。仅登记释义可用，原始扫描不随包分发，也不开放全书或逐字引用。见[接口](docs/bazi-qiong-xin-zi.md)与[来源审计](docs/bazi-qiong-xin-zi-sources.md)。

The approved QX01–03 cards in `bazi-qiong-xin-zi-v1` support bounded overall/development-configuration evaluation only for a Xin day master born in the Zi month. The separate `qiong_xin_zi_model` preserves natal facts, author-created period adaptations, the selected B reading and its conservative alternative. Complete conditions and specific counterconditions precede the model direction and robustness assessment. Natal exposure, original module statuses, source quarantine and health/event boundaries remain intact. Only registered paraphrases are enabled; scans are not bundled, and neither the whole books nor classical-quotation mode are opened. See the [interface](docs/bazi-qiong-xin-zi.md) and [source audit](docs/bazi-qiong-xin-zi-sources.md).

丑月辛金另有 [BZ-QXC01](references/approved/bazi-qiong-xin-chou-v1.md)，用于人工复核本命专业发展配置。所问运段和实际结果各查对应依据。

[BZ-QXC01](references/approved/bazi-qiong-xin-chou-v1.md) supports manual review of natal professional-development conditions for a Xin day master born in the Chou month. Period directions and real-world outcomes require their own evidence.

寅月甲木另有 [BZ-QJY01](references/approved/bazi-qiong-jia-yin-v1.md)，用于人工复核可用学习资源或反馈与可核验专业成果的本命配置。按卡核出生丙癸实透、分隔、同干实藏和反证。时段方向及实际结果各查依据。

[BZ-QJY01](references/approved/bazi-qiong-jia-yin-v1.md) covers the natal fit between usable learning resources or feedback and demonstrable professional work for a Jia day master born in the Yin solar month. It requires manual review of exposed, separated and supported Bing and Gui, and their counterconditions. Period directions and real-world outcomes require their own evidence.

### 大限推进与配偶条件 / Decadal progress and spouse-related conditions

[使用说明](docs/stage-and-spouse-models.md)覆盖紫微 ST01–09 的指定大限事务推进或受限分支、RL01 的本命婚姻稳定配置、RL02–04 对已婚男性长期维持与妻子共同生活的本命条件，以及八字 P1 的局部官印主兼与 R1 的配偶角色支持。紫微按原年度窗和所问目标取分支。R1 先由人工独立建立可反驳的官用假说，并核财星和反条。模型结果、稳健性及会使结论退出的条件一并交付。

The [usage guide](docs/stage-and-spouse-models.md) covers nine bounded Ziwei decadal models, RL01 natal marriage stability, RL02–04 natal conditions for a married man asking about maintaining long-term shared life with his wife, the local BaZi Officer–Resource priority model and the spouse-role support model. Ziwei readings select the original year window and the requested objective. The spouse-support reading requires an independently reasoned Officer-use hypothesis and a review of natal Wealth facts and counterconditions. Report the conditional direction with its robustness and withdrawal conditions.
