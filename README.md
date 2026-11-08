# 高置信度命理 Skill · High-Confidence Mingli Skill

![Code license: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)

Third-party study packet: CC BY-SA 4.0; see the license exceptions below. / 第三方学习包另用CC BY-SA 4.0，见下方许可例外。
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Node.js](https://img.shields.io/badge/node-18%2B-green)
![Checks](https://img.shields.io/badge/checks-see_verification-blue)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**简体中文** | [English](#english)

---

## 简体中文

> 好医生不会看一项指标就下诊断。
>
> 这个 skill 也一样：八字、紫微、七政三个体系**各自独立**分析你的命，
> 先独立解释，再对照一致、冲突与缺口；重要判断附可核对来源。
>
> 排盘用引擎算，不靠 AI 口算；跨盘一致不代表准确率；来源检查也不证明预测能力。

一个装进 agent CLI（Claude Code / Codex / Kimi Code 等任何读 SKILL.md 的环境）的
命理对话伴侣。提供传统文化解释：排盘由程序计算，重要判断可追溯来源，但不保证排盘无误或现实预测准确。

### 它是怎么做到的

| | 机制 | 一句话 |
|---|------|--------|
| 🔢 | **确定性排盘引擎** | 四柱/安星/躔度全部由三套引擎计算（Meeus 定气八字 / iztro 紫微 / 自研恒星制七政），27 项回归测试盯着，大模型只负责解读，不负责算数 |
| 📜 | **可追溯资料解读** | 先经 `knowledge/README.md` 来源门，再用已启用的项目释义；现代整理与数字录文不冒称核验古籍原文 |
| ⭐ | **跨盘对照，不是投票** | 星级仅为旧版关联展示；严格详批用证据记录、条件与限制，不输出可靠度星级 |
| 🔁 | **自愿反馈与版本记录** | 用户愿意时先冻结判断再记录反馈；旧事回顾不算盲测，不用命中反馈计算准确率 |

*普通 AI 算命 vs 本 Skill：*

| 普通 AI 算命 | 本 Skill |
|--------------|----------|
| 干支靠大模型口算，节气靠背日期，算错一位全盘皆错 | 排盘全部引擎计算，口算仅作离线降级并强制标注 |
| "你本月运势不错"——无出处无依据 | 每条主判断挂资料来源与限制；已隔离条文不作依据 |
| 吉凶好坏吓唬人 | 断语走斯多葛转写，每篇附「你可以把握的是」 |
| 每次都像第一次见你 | 校准闭环：越用越懂你 |
| 硬凑共鸣 | 共鸣溯源有硬门槛：全部命题不命中就直说"不匹配" |

### 可运行的端到端演示

当前可运行的端到端演示见 [examples/engine-reading/README.md](examples/engine-reading/README.md)。
使用虚构出生输入，实际生成三个引擎的快照、证据记录及易读报告，包含边界分支。
它验证工程管线与有限的条件式解释，不是命中率评测或真实用户详批。

### 30 秒上手

```bash
# 1. 克隆到 agent CLI 的 skills 目录（以 Claude Code 为例）
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/fortune-telling

# 2. 启用紫微引擎（一次性；不装则紫微盘自动降级）
cd ~/.claude/skills/fortune-telling/scripts/pai_pan_ziwei && npm ci
```

然后在 CLI 里说 `/fortune-telling`，或直接开口："今日运势""帮我详批"。
首次运行引导建档：出生信息 → 三引擎排盘 → 可选反馈，
排盘脚本在本地运行；使用云端 agent 解读时，输入会依所选服务的数据政策处理。请勿把用户档案提交到公开仓库。

### 工作原理（给想深究的人）

- **排盘层** `scripts/`：八字引擎用 Meeus 定气定朔（纯标准库，1900-2100）；紫微用 iztro 2.6.1；
  七政为自研恒星制引擎（角宿一=0°，Hipparcos 宿度表，果老安命法，输出躔宿+躔宫）——**全部学派口径在
  引擎文件头声明出处**。三引擎共 27 项回归测试：对拍 JPL DE441 校正级的开源参照黄金值 +
  古典安命三例 + 夜子时/立春边界用例 + 二十八宿落宫全表
- 紫微精确亮度请读取新增 `brightnessRaw`，缺失为 `null`；旧 `brightness` 仅为合并分组，不能据此细分庙旺。[字段口径](docs/ziwei-brightness.md)。
- **解读层**：先读 [知识来源门](knowledge/README.md)。八字/紫微八份旧资料逐字节保留，另有17篇固定版本 iztro-docs 资料与原许可。普通解读仅启用明确登记的项目释义，不把数字录文或现代汇编当作已核古籍原文。七政五份旧资料的来源声明指向殆知阁《张果星宗》《星学大成》《乾元秘旨》，本次未逐条核验其底本、篇章归属或准确性；不能称已完成原典校勘。详见 [来源记录](references/README.md)。
- **管线**：解读管线三段式（各盘分层注明来源的解读 → 跨盘证据对照 → 斯多葛收束），五个模式 +
  详批模式共用；规则全文见 [SKILL.md](SKILL.md)

### 文档地图

| 文档 | 内容 |
|------|------|
| [SKILL.md](SKILL.md) | 引擎主文件：路由 / 解读管线 / 置信度 / 语气 / 权重 |
| [docs/onboarding.md](docs/onboarding.md) | 建档流程（含历史事件校准） |
| [references/README.md](references/README.md) | 解读资料层溯源表 |
| [workflows/fortune-full-reading.md](workflows/fortune-full-reading.md) | 详批模式（长文批盘） |

### 限制与口径

1. 七政盘制为恒星制（角宿一=0°），与回归制排盘软件相差约 24°，属学派差异，口径全标注
2. 七政月限/小限（限度推算）不包含；洞微百六限等倒限内容不入典籍库、解读不断流年应期；
   变曜/化曜/神煞层（年干起例）同理不做
3. 紫微引擎需要 node（`npm ci` 一次），缺环境时该盘自动降级
4. 三元九运交接点存在学派争议（本 skill 统一用 2004/2024）
5. 运势为未经统计校准的传统解释框架，不提供预测概率——命理分析仅供参考，人生在于自身的努力和选择

---

## English

> A good doctor never diagnoses from a single lab result.
>
> Neither does this skill: BaZi, Ziwei Doushu, and Qizheng Siyu — three systems
> **independently** read your chart. Interpretations are compared for agreement, conflict and missing evidence.
> Important claims cite inspectable local sources.
>
> Charts are computed by engines, not LLM mental arithmetic. Cross-chart agreement is not evidence of predictive accuracy.

A fortune-telling companion that lives inside your agent CLI (Claude Code /
Codex / Kimi Code — anything that reads SKILL.md). **Not AI fortune-cookie
generation** — a traditional interpretation workflow with traceable claims, explicit conditions and limitations. Computation and interpretation can both be wrong.

### How it works

| | Mechanism | In one line |
|---|-----------|-------------|
| 🔢 | **Deterministic chart engines** | Four Pillars / star-placing / planetary degrees are computed by three engines (Meeus-based BaZi / iztro Ziwei / self-built sidereal Qizheng), guarded by 27 regression tests — the LLM only interprets, never calculates |
| 📜 | **Source-attributed reading** | Read `knowledge/README.md` first, then use explicitly enabled project paraphrases; modern compilations and digital transcriptions are not authenticated classical quotations |
| ⭐ | **Cross-chart comparison, not voting** | Legacy stars are association labels only; strict readings record evidence and uncertainty, not accuracy ratings |
| 🔁 | **Calibration loop** | Feedback is optional; freeze claims before evaluation, retain misses, and never treat known events as blind validation |

*Ordinary AI fortune-telling vs this skill:*

| Ordinary AI fortune-telling | This skill |
|------------------------------|------------|
| Stems and branches from LLM mental arithmetic; solar terms from memorized dates — one slip ruins the whole chart | All chart math from engines; mental fallback only offline, always flagged |
| "Your career looks great this month" — no source, no basis | Every main claim carries a citation line; cross-chart links state conditions and limits |
| Auspicious/inauspicious scare labels | Verdicts rendered Stoic; each reading ends with "what you can hold onto" |
| Starts from scratch every time | Calibration loop: knows you better the longer you use it |
| Forces resonance | Resonance tracing has a hard gate: if nothing matches, it says so |

### Executable end-to-end example

See [the executable end-to-end demo](examples/engine-reading/README.md): fictional inputs, actual engine snapshots, a ledger and a readable conditional report, including boundary branches. It is not a predictive-accuracy evaluation.

### 30-second start

```bash
# 1. Clone into your agent CLI's skills directory (Claude Code shown)
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/fortune-telling

# 2. Enable the Ziwei engine (once; skipped gracefully if absent)
cd ~/.claude/skills/fortune-telling/scripts/pai_pan_ziwei && npm ci
```

Then say `/fortune-telling` in your CLI, or just talk: "today's fortune",
"full reading of my chart". First run walks you through onboarding: birth data
→ three-engine charts → optional feedback. Engine scripts run locally. Cloud-agent interpretation is subject to your chosen provider’s data policy; never commit private charts to a public repository.

### Under the hood

- **Chart layer** `scripts/`: BaZi via Meeus solar-term/syzygy math (pure stdlib,
  1900-2100); Ziwei via iztro 2.6.1; Qizheng via a self-built sidereal engine
  (Spica = 0°, Hipparcos mansion table, Gulan ascending rule) — **every school
  convention is documented with sources in the engine file headers**. 27
  regression tests: golden values cross-checked against a JPL DE441-grade open
  reference, classical ascending-rule examples, and edge cases (late-Zi hour,
  spring-equinox boundary)
- Ziwei exact brightness is available in additive `brightnessRaw` (`null` when unavailable); legacy `brightness` remains a collapsed grouping. See [source fidelity](docs/ziwei-brightness.md).
- **Interpretation layer**: read [the provenance gate](knowledge/README.md) first. Eight legacy files remain byte-identical; 17 pinned iztro-docs files retain their source hashes and upstream license. Only explicitly enabled project paraphrases are ordinary reading rules. Digital transcriptions and modern compilations are not authenticated classical editions. Qizheng materials have not received edition-level verification in this upgrade. See [source records](references/README.md).
- **Pipeline**: three-stage reading (per-chart source-attributed interpretation →
  cross-chart evidence comparison → Stoic closing), shared by five modes plus
  full-reading; full rules in [SKILL.md](SKILL.md)

### Docs

| Doc | Content |
|-----|---------|
| [SKILL.md](SKILL.md) | Engine main file: routing / pipeline / confidence / voice / weights |
| [docs/onboarding.md](docs/onboarding.md) | Onboarding flow (incl. historical-event calibration) |
| [references/README.md](references/README.md) | Interpretation-layer provenance |
| [workflows/fortune-full-reading.md](workflows/fortune-full-reading.md) | Full-reading mode (long-form chart reading) |

### Limitations & conventions

1. The Qizheng chart is sidereal (Spica = 0°), ~24° apart from tropical
   software — a school difference, fully documented
2. Qizheng monthly/annual limits (limit-degree math) not included
3. The Ziwei engine needs Node.js (`npm ci` once); without it that chart
   degrades gracefully
4. The San Yuan Jiu Yun boundary is disputed across schools (this skill uses
   2004/2024)
5. Readings are uncalibrated traditional interpretations, not predictive probabilities or guidance for consequential decisions

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
The strict workflow is enabled for full readings; other modes remain legacy and have not received full semantic review.

### 固定分析年 / Explicit analysis year

为跨年复现完整快照，使用 `--analysis-year 2026`：同时固定八字当前年/流年列表和紫微目标年；出生瞬间与本命计算不变。默认不指定时保持兼容。旧 `--age-year` 仍仅控制紫微；两者指定不同值会报错。
For cross-year reproducibility use `--analysis-year 2026` to pin both BaZi annual fields and Ziwei target year. Natal inputs remain unchanged. Omitting it preserves legacy defaults. The Ziwei-only `--age-year` stays compatible; conflicting values are rejected.

### 历史时区与误差候选 / Historical zones and bounded scenarios

可选 `--timezone Asia/Shanghai` 使用 IANA 历史偏移，拒绝不存在的民用时间，重复时间必须显式 `--fold 0/1`。`--time-basis mean-solar` 区分平太阳时。`--enumerate-scenarios --uncertainty-minutes 10` 比较实际可达的四柱及紫微离散输入，限 ±120 分钟、UTC 1901–2099 年。民用/平太阳时输出该范围内稳定/变化字段；真太阳时仅给数值包围候选，明确未穷尽、不保证稳定。七政、起运、完整紫微及天文误差不在覆盖内。IANA 模式需要 Python 3.9+ 和可用的时区数据库。[详见时间契约](docs/time-contract.md)。

Optional `--timezone Asia/Shanghai` resolves IANA historical offsets, rejects missing local times and requires explicit `--fold 0/1` for repeated times. `--time-basis mean-solar` distinguishes the mean solar clock. `--enumerate-scenarios --uncertainty-minutes 10` compares reachable BaZi pillars and discrete Ziwei inputs, capped at ±120 minutes within UTC years 1901–2099. Civil/mean-solar modes report stable/changing fields within that scope. Apparent-solar mode returns numerical boundary-bracket witnesses only, explicitly non-exhaustive with no stability guarantee. Qizheng, luck-start ages, full Ziwei output and astronomical model errors are excluded. IANA mode needs Python 3.9+ and available time-zone data. [Time contract](docs/time-contract.md).

## 知识层升级 / Knowledge integration

新增资料与隔离规则见 [知识来源门](knowledge/README.md)，完整检查及未完成项见 [验证记录](docs/knowledge-verification.md)。[实际 CLI 示例](examples/imported-knowledge/README.md)把新导入的三方四正说明与虚构排盘四宫字段连接，不代表预测效力。旧八份来源不重复迁移、不改字节。

See the [provenance gate](knowledge/README.md), [verification and limits](docs/knowledge-verification.md), and [actual CLI imported-source example](examples/imported-knowledge/README.md). Sources and licenses remain pinned; classical-quotation mode is disabled for this release. Time-scenario defaults and known calendar discrepancies remain unchanged.

原先18条登记含13条可用项目释义（主要是基本概念和来源限制）与5条隔离记录，不是18条已校勘古籍规则，也不构成完整深度解读知识库。CLI示例只演示宫位关系及证据连接，未完成星曜组合、成格破格、运限综合或完整个人详批。

The original 18 records contain 13 enabled project paraphrases, mainly basic concepts and source limitations, plus 5 quarantined records. They are not 18 authenticated classical rules or a complete deep-reading knowledge base. The CLI example demonstrates palace relationships and evidence linkage only, not a full reading of star combinations, pattern conditions, timing cycles or a person’s life.

### 八字理论学习 / BaZi theory study

新增10张理论学习卡与88字数字短引，含条件、反证和可操作的分析清单，采用单独 `bazi-classical-study` profile，不启用个人预测。两项新增资料均隔离于个人ledger。不是古籍全文或校勘版，也没有改变现有引擎。[来源调查与许可](docs/bazi-classical-study.md)。

Ten new theory study cards and only 88 characters of short digital excerpts provide prerequisite, counterexample and analysis checklists. Their separate `bazi-classical-study` profile does not activate personal predictions; both new source files are blocked as reading evidence. No complete classical text, collated edition or engine change is claimed. This independent packet and its identified catalog adaptations are CC BY-SA 4.0, excluded from project MIT.

### 可用于详批的条件式解释 / Conditional interpretation in readings

同一组10张卡现在另提供 `bazi-traditional-conditional` 入口：绑定本盘字段、逐项前提和反证，仅作为未校勘数字转录的项目释义解释结构；不保证预测、不升级supported，也不启用古籍原文模式。旧学习入口与原始短引隔离仍保留。[运行示例](examples/bazi-conditional/README.md)。

The same ten cards now have a separate conditional interpretation profile for chart-bound structural explanations with prerequisites and counterevidence. They remain uncollated project paraphrases, not validated predictions or authenticated classical quotations. Only exact registered paraphrase lines may pass this limited gate; the default study profile and raw excerpts stay restricted. New derivative records and generated explanation ledgers retain CC BY-SA 4.0; generator code remains MIT.

### 日主承受证据增量 / Bounded strength evidence

新增 ST01–ST05：逐位比较月令、同五行根、外部印比及克泄耗。只在公开的窄条件组合下输出偏强/偏弱趋势；争议、缺时和未建模情况保留待定。不计分、不从根数定强弱，不指定唯一喜忌。来源、阴长生乙午/丁酉口径冲突与限制见 [说明](docs/bazi-strength-evidence.md)。CLI 与原始引擎字段不变，JSON 新增 strength_reasoning。

ST01–ST05 now compare seasonal context, operational same-element roots, support and opposing paths. Strong/weak tendencies require explicit narrow conjunctions; conflicting evidence, missing time and source/model disputes remain unresolved. No score, universal classifier, favorable-element prescription or predictive validation is implied. Existing CLI and engine facts are unchanged; structured JSON adds strength_reasoning. See the [source and scope notes](docs/bazi-strength-evidence.md).

### 四宫联读增量 / Conditional four-domain reading

紫微默认以实际命、财、官、迁位置展开主星主题、亮度差异、反证问题与领域之间的条件联系。JSON 增加 `rule_output.domain_reading`，原始 chart 与旧 patterns 不变。14颗主星和两项概念仅采用已核读现代资料的有限释义；两组组合讨论是项目综合，不是新认定古典格局。空宫借星、完整四化、辅煞组合与运限仍缺，不能称整盘完整详批。见[范围说明](docs/ziwei-domain-reading.md)及[联合验收](docs/deep-integration-qa.md)。

Ziwei now connects actual Life, Wealth, Career and Travel placements into conditional themes, brightness distinctions and counterchecks. JSON adds `rule_output.domain_reading`; chart facts and existing patterns remain unchanged. Fourteen star themes and two concepts are bounded modern-source paraphrases. Two thematic combinations are project syntheses, not classical patterns. Complete transformation rules, borrowed-star interpretation, supporting-star combinations and timing remain incomplete; this is not a comprehensive or predictively validated reading. See the scope and integrated QA notes above.

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
