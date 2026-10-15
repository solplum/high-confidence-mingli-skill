# 高置信度命理 Skill · High-Confidence Mingli Skill

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Node.js](https://img.shields.io/badge/node-18%2B-green)
![Engine Tests](https://img.shields.io/badge/engine_tests-27_passing-brightgreen)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**简体中文** | [English](#english)

---

## 简体中文

> 好医生不会看一项指标就下诊断。
>
> 这个 skill 也一样：八字、紫微、七政三个体系**各自独立**分析你的命，
> 结论一致才高置信地告诉你，每句话都能指回典籍原文。
>
> 排盘用引擎算，不靠 AI 口算；结论有多可靠，用 ⭐ 标给你看。

一个装进 agent CLI（Claude Code / Codex / Kimi Code 等任何读 SKILL.md 的环境）的
命理对话伴侣。**不是 AI 算命**——是一套排盘不出错、论断有出处、越用越准的解读引擎。

### 它是怎么做到的

| | 机制 | 一句话 |
|---|------|--------|
| 🔢 | **确定性排盘引擎** | 四柱/安星/躔度全部由三套引擎计算（Meeus 定气八字 / iztro 紫微 / 自研恒星制七政），27 项回归测试盯着，大模型只负责解读，不负责算数 |
| 📜 | **典籍考证式解读** | 解读先查 `references/` 资料层（穷通宝典、紫微全书、果老星宗……），每条论断挂典籍出处——引文原样，断语才转写 |
| ⭐ | **置信度只标在盘与盘之间** | 三盘结论一致才给 ⭐⭐⭐；单盘论断不标星，它的可信度来自典籍出处和引擎盘面 |
| 🔁 | **越用越准的校准闭环** | 建档时用你已发生的 3-5 件事校准解读模型，之后每次收束继续修正——校准只调解释器参数，永不改典籍 |

*普通 AI 算命 vs 本 Skill：*

| 普通 AI 算命 | 本 Skill |
|--------------|----------|
| 干支靠大模型口算，节气靠背日期，算错一位全盘皆错 | 排盘全部引擎计算，口算仅作离线降级并强制标注 |
| "你本月运势不错"——无出处无依据 | 每条主判断挂典籍依据行，跨盘关联标 ⭐ |
| 吉凶好坏吓唬人 | 断语走斯多葛转写，每篇附「你可以把握的是」 |
| 每次都像第一次见你 | 校准闭环：越用越懂你 |
| 硬凑共鸣 | 共鸣溯源有硬门槛：全部命题不命中就直说"不匹配" |

### 真实输出长什么样

以下为本月事业运的浓缩样例（干支与宫位为引擎真实输出；示例命造 2000-05-15 午时男）：

```markdown
### 本月事业运

**背景**：你的盘官印相生，做事要名分要章法——这不是 bureaucracy，是你的能量结构。

**本月能量**：流月丁酉（引擎排盘），偏财生官，原局时干正官得生扶。
跨盘关联：八字「财生官」 ⨯ 紫微「官禄宫天府坐守」
→ 同领域·同方向·同源 **⭐⭐⭐**

> 依据：《滴天髓》「何知其人贵，官星有理会」
> 依据：《紫微斗数全书》天府为南斗令星，财帛田宅之主

本月是练习「把章法亮出来」的窗口：立项、周报、向决策层要一次正式汇报。

> 🏛 你可以把握的是：把一件拖了很久的事，在月中前推到台面上。
```

### 30 秒上手

```bash
# 1. 克隆到 agent CLI 的 skills 目录（以 Claude Code 为例）
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/fortune-telling

# 2. 启用紫微引擎（一次性；不装则紫微盘自动降级）
cd ~/.claude/skills/fortune-telling/scripts/pai_pan_ziwei && npm install
```

然后在 CLI 里说 `/fortune-telling`，或直接开口："今日运势""帮我详批"。
首次运行引导建档：出生信息 → 三引擎排盘 → 历史事件校准，全程约 5 分钟，
数据只存本地 `~/.claude/fortune-telling/`，不上传不联网。

### 工作原理（给想深究的人）

- **排盘层** `scripts/`：八字引擎用 Meeus 定气定朔（纯标准库，1900-2100）；紫微用 iztro 2.6.1；
  七政为自研恒星制引擎（角宿一=0°，Hipparcos 宿度表，果老安命法，输出躔宿+躔宫）——**全部学派口径在
  引擎文件头声明出处**。三引擎共 27 项回归测试：对拍 JPL DE441 校正级的开源参照黄金值 +
  古典安命三例 + 夜子时/立春边界用例 + 二十八宿落宫全表
- **解读层** `references/`：bazi/紫微两套经过时间验证的 skill 资料逐字节移植 + 七政四余原典库
  （2026-10 起典籍化：五件库文件辑自殆知阁《张果星宗》《星学大成》《乾元秘旨》——读盘总纲四十诀、
  十一曜逐曜断（入宫化名/躔度断/照宫断）、十二宫体系、庙旺乐喜制刑与升殿查表、格局库），
  溯源表见 `references/README.md`
- **管线**：解读管线三段式（各盘典籍式解读 → 置信度跨盘联系 → 斯多葛收束），五个模式 +
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
3. 紫微引擎需要 node（`npm install` 一次），缺环境时该盘自动降级
4. 三元九运交接点存在学派争议（本 skill 统一用 2004/2024）
5. 运势是概率框架，不是预言——命理分析仅供参考，人生在于自身的努力和选择

---

## English

> A good doctor never diagnoses from a single lab result.
>
> Neither does this skill: BaZi, Ziwei Doushu, and Qizheng Siyu — three systems
> **independently** read your chart. Only when they agree does it tell you with
> high confidence, and every claim traces back to a classical text.
>
> Charts are computed by engines, not LLM mental arithmetic. How reliable a
> conclusion is — marked with ⭐.

A fortune-telling companion that lives inside your agent CLI (Claude Code /
Codex / Kimi Code — anything that reads SKILL.md). **Not AI fortune-cookie
generation** — a reading engine whose charts don't err, whose claims carry
citations, and which gets more accurate the longer you use it.

### How it works

| | Mechanism | In one line |
|---|-----------|-------------|
| 🔢 | **Deterministic chart engines** | Four Pillars / star-placing / planetary degrees are computed by three engines (Meeus-based BaZi / iztro Ziwei / self-built sidereal Qizheng), guarded by 27 regression tests — the LLM only interprets, never calculates |
| 📜 | **Classical-text-grounded reading** | Interpretations look up the `references/` knowledge layer (Qiongtong Baodian, Ziwei Quanshu, Guolao Xingzong…); every claim cites its source — quotes stay verbatim, only the agent's own verdicts are rewritten |
| ⭐ | **Confidence marks cross-chart links only** | ⭐⭐⭐ only when all three systems agree; single-chart claims carry no stars — their credibility comes from citations and engine-computed charts |
| 🔁 | **Calibration loop** | At onboarding, 3-5 of your past events verify the reading model; every session keeps refining it — calibration tunes the interpreter, never the classics |

*Ordinary AI fortune-telling vs this skill:*

| Ordinary AI fortune-telling | This skill |
|------------------------------|------------|
| Stems and branches from LLM mental arithmetic; solar terms from memorized dates — one slip ruins the whole chart | All chart math from engines; mental fallback only offline, always flagged |
| "Your career looks great this month" — no source, no basis | Every main claim carries a citation line; cross-chart links get ⭐ |
| Auspicious/inauspicious scare labels | Verdicts rendered Stoic; each reading ends with "what you can hold onto" |
| Starts from scratch every time | Calibration loop: knows you better the longer you use it |
| Forces resonance | Resonance tracing has a hard gate: if nothing matches, it says so |

### What real output looks like

A condensed sample of this month's career reading (stems and palaces are real
engine output; demo chart: male, 2000-05-15 12:00):

```markdown
### Career, this month

**Background**: Officer-and-Seal structure — you need proper form and process
to thrive; that's your energy architecture, not bureaucracy.

**This month**: Month pillar Ding-You (engine-computed); Wealth generates
Officer, energizing the natal Officer stem.
Cross-chart: BaZi "Wealth feeds Officer" ⨯ Ziwei "Tianfu seated in the
Career palace" → same domain · same direction · same source **⭐⭐⭐**

> Source: Di Tian Sui, "He who is noble — the Officer star finds its resonance"
> Source: Ziwei Quanshu, Tianfu — the commanding star of wealth and property

This month is a window for practicing "showing your form": kick off the
project, file the report, ask decision-makers for a formal review.

> 🏛 What you can hold onto: push one long-postponed item onto the table
> before mid-month.
```

### 30-second start

```bash
# 1. Clone into your agent CLI's skills directory (Claude Code shown)
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/fortune-telling

# 2. Enable the Ziwei engine (once; skipped gracefully if absent)
cd ~/.claude/skills/fortune-telling/scripts/pai_pan_ziwei && npm install
```

Then say `/fortune-telling` in your CLI, or just talk: "today's fortune",
"full reading of my chart". First run walks you through onboarding: birth data
→ three-engine charts → historical-event calibration, ~5 minutes. Data stays
local under `~/.claude/fortune-telling/`, never uploaded.

### Under the hood

- **Chart layer** `scripts/`: BaZi via Meeus solar-term/syzygy math (pure stdlib,
  1900-2100); Ziwei via iztro 2.6.1; Qizheng via a self-built sidereal engine
  (Spica = 0°, Hipparcos mansion table, Gulan ascending rule) — **every school
  convention is documented with sources in the engine file headers**. 25
  regression tests: golden values cross-checked against a JPL DE441-grade open
  reference, classical ascending-rule examples, and edge cases (late-Zi hour,
  spring-equinox boundary)
- **Interpretation layer** `references/`: two time-tested skill collections
  ported byte-for-byte, plus a classical Qizheng canon library (five files curated from
  the Daizhige corpus: Zhang Guo Xing Zong / Xing Xue Da Cheng / Qian Yuan Mi Zhi) — provenance in
  [references/README.md](references/README.md)
- **Pipeline**: three-stage reading (per-chart classical interpretation →
  cross-chart confidence linkage → Stoic closing), shared by five modes plus
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
3. The Ziwei engine needs Node.js (`npm install` once); without it that chart
   degrades gracefully
4. The San Yuan Jiu Yun boundary is disputed across schools (this skill uses
   2004/2024)
5. Fortune readings are a probabilistic frame, not prophecy — for reference
   only; life is your own effort and choices

---

## License

MIT — see [LICENSE](LICENSE).
