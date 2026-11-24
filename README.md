# 高置信度命理 Skill · High-Confidence Mingli Skill

![Code license: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Node.js](https://img.shields.io/badge/node-18.19%2B-green)
![Corpus](https://img.shields.io/badge/corpus-1351_cleaned_records-orange)

**简体中文** | [English](#english)

---

## 简体中文

> **确定性排盘引擎算事实 + 清洗校验的古典原典库找依据 + 结合命主现实给可执行判断。**
>
> 八字（Meeus 定气定朔）、紫微斗数（锁定 `iztro 2.6.1`）、七政四余（自研恒星制＋二十八宿/果老安命）全由程序精确排盘；所有古籍引文均由统一检索工具 `scripts/mingli_query.py` 从清洗校验后的三盘语料库实查获取，绝不凭大模型记忆胡编典籍或“伪古文”。

### 核心架构

| 组件 | 作用 | 技术细节 |
|------|------|----------|
| 🔢 **三盘确定性引擎** (`scripts/`) | 八字、紫微、七政独立精确排盘与多时间候选对比 | Python 3 纯标准库 + Node 18.19+ (`iztro 2.6.1`)；覆盖真太阳时、IANA 历史夏令时、1901–2099 时间误差边界枚举、七档原始亮度 `brightnessRaw` |
| 📜 **三体系原典语料库** (`references/corpus/`) | 7 份 JSONL 共 **1,351** 条实录古籍与格局条文 + SHA-256 清单 | 收录《穷通宝鉴》（**120/120 全覆盖**）、《子平真诠》《滴天髓阐微》《渊海子平》《千里命稿》、《紫微斗数全书》卷一至三与《诸星问答论》、引擎 41 格局与星宫释义、《张果星宗》《星学大成》《乾元秘旨》 |
| 🔎 **统一原典检索引擎** (`scripts/mingli_query.py`) | 将任意命盘 JSON 一键关联三盘原典与主题断法 | 支持 `stats`（SHA-256 核验）、`bazi-lookup`（日干×月支精查）、`search`（近义词展开、均衡跨书选条、默认隔离飞星条目）、`chart-lookup`（对接 `build_chart.py`） |
| 🧭 **务实对话与场景流** (`workflows/`) | 覆盖全盘详批、具体决策、日/月/年运、网传说法核对、纯知识问答 | 先立单盘逻辑，再看三盘共鸣与分歧，最后落实到现实处境与行动选择；明确标注未知时辰与学派边界 |

---

### 安装与使用

```bash
# 1. 克隆到 agent skills 目录（以 Claude Code / Codex / Antigravity 为例）
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/high-confidence-mingli-skill

# 2. 初始化紫微引擎依赖（一次性；缺 Node 时紫微自动降级，八字与七政正常可用）
cd ~/.claude/skills/high-confidence-mingli-skill/scripts/pai_pan_ziwei && npm ci
```

在对话框中输入 `/high-confidence-mingli-skill`，或直接提问（如 `"帮我全盘详批"` `"2026年适合换工作吗"` `"今日运势如何"` `"庚金生巳月《穷通宝鉴》怎么说"`）。

#### 个人档案与数据隔离
- 个人排盘结果与反馈档案默认保存在技能目录之外的 `~/.claude/fortune-telling/`（含 `chart.md`、`snapshot.json`、`memory.md`、`memory-archive/`；Windows 为 `%USERPROFILE%\.claude\fortune-telling\`），旧版用户数据可无缝沿用。**切勿将个人隐私资料提交到 GitHub 仓库。**

---

### 快速命令行示例

```bash
# 1. 三盘合排并导出 JSON 快照
python3 scripts/build_chart.py \
  --solar 1990-05-15 --hour 14:00 --sex 男 \
  --lat 31.23 --lon 121.47 --place "上海" \
  --analysis-year 2026 --format json > snapshot.json

# 2. 依据命盘快照一键检索三盘原典（主题可选 general / career / love / wealth / health）
python3 scripts/mingli_query.py chart-lookup --chart-json snapshot.json --topic career

# 3. 精查八字《穷通宝鉴》与子平典籍
python3 scripts/mingli_query.py bazi-lookup --day-stem 庚 --month-branch 巳 --pattern 正官

# 4. 核验语料库 SHA-256 完整性与 120/120 覆盖率
python3 scripts/mingli_query.py stats
```

### 运行回归测试

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

### 主要文档

- [SKILL.md](SKILL.md) — 技能核心入口与四步分析工作流
- [docs/onboarding.md](docs/onboarding.md) — 建档与未知时辰处理指南
- [docs/time-contract.md](docs/time-contract.md) — 真太阳时、IANA 时区、误差候选枚举与双历法口径说明
- [docs/corpus-audit.md](docs/corpus-audit.md) — 原典来源、数据清洗修复与防回退核查记录
- [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) — 第三方开源语料与依赖库完整许可说明

### 重要边界说明
1. 传统命理是文化符号与经验结构模型，不提供统计学意义上的预测概率保证，重大现实决策应结合客观事实独立判断。
2. 七政四余采用声明的恒星制与近似二十八宿/十二宫边界（与回归制软件差约 24°）；本仓未实现七政洞微百六限/倒限及年干变曜，解读中不凭空补推流年应期。
3. 本仓紫微默认使用固定生年四化（《天纪》/三合口径）；若查阅飞星宫干四化，需显式传入 `--include-feixing` 仅作旁参。
4. 遇到急性躯体不适或心理危机信号时，优先提示现实就医与求助，不用命理推算替代医疗判断。

---

## English

> **Deterministic Astrological Calculation + Audited Classical Corpus + Grounded Practical Interpretation.**
>
> `high-confidence-mingli-skill` integrates three traditional Chinese astrological systems—**BaZi (Four Pillars)**, **Ziwei Doushu**, and **Qizheng Siyu (Seven Governors and Four Remainders)**—into coding agents via `/high-confidence-mingli-skill`. All chart math is executed deterministically by Python stdlib & pinned Node.js engines, and every classical citation is retrieved from an audited 1,351-record corpus (`references/corpus/`) using `scripts/mingli_query.py` instead of LLM memory.

### Architecture

- **Deterministic Three-Chart Engines (`scripts/`)**:
  - **BaZi** (`pai_pan_bazi.py`): Pure Python stdlib Meeus solar terms & lunations (1900–2100), dayun exact-month windows, Shensha tables.
  - **Ziwei Doushu** (`pai_pan_ziwei/pai_pan.ts` + `ziwei_dynamic_facts.mjs`): Pinned `iztro 2.6.1`, exact 7-level `brightnessRaw`, 41 pattern recognizers, and independent yearly/monthly/daily dynamic layers.
  - **Qizheng Siyu** (`pai_pan_qizheng.py`): Sidereal ecliptic ephemeris anchored to Spica (`physical-v2`), 28 mansions, Guolao Minggong, geometric solar-altitude day/night rule.
  - **Time Contract & Uncertainty Enumeration** (`build_chart.py`, `time_scenarios.py`): Supports `civil`, `mean-solar`, and `apparent-solar` clocks, IANA `--timezone` / `--fold`, and `--uncertainty-minutes N --enumerate-scenarios` over reachable UTC intervals.
- **Cleaned & Verified Classical Corpus (`references/corpus/`)**:
  - **1,351** audited entries across 7 JSONL files with SHA-256 `manifest.json`, covering *Qiongtong Baojian* (**120/120** stem × month coverage), *Ziping Zhenquan*, *Ditansui Chanwei*, *Yuanhai Ziping*, *Qianli Minggao*, *Ziwei Doushu Quanshu*, and *Zhangguo Xingzong* / *Xingxue Dacheng* / *Qianyuan Mizhi* (PUA glyphs & VitePress/HTML artifacts repaired).
- **Unified Query CLI (`scripts/mingli_query.py`)**:
  - Zero-dependency retrieval (`stats`, `search`, `bazi-lookup`, `chart-lookup`) with alias expansion, balanced multi-book selection, and explicit isolation of *Feixing* rules unless `--include-feixing` is passed.

### Installation & Usage

```bash
# 1. Clone the repository into your skills directory
git clone https://github.com/solplum/high-confidence-mingli-skill.git ~/.claude/skills/high-confidence-mingli-skill

# 2. Install locked Node dependencies for the Ziwei engine (one-time)
cd ~/.claude/skills/high-confidence-mingli-skill/scripts/pai_pan_ziwei && npm ci
```

Invoke `/high-confidence-mingli-skill` in your CLI agent or ask naturally in Chinese/English. User charts and voluntary feedback logs live outside the repository at `~/.claude/fortune-telling/` (`%USERPROFILE%\.claude\fortune-telling\` on Windows). Never commit personal birth data to public repositories.

### Verification

```bash
python3 scripts/mingli_query.py stats
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

### License

Code is released under the [MIT License](LICENSE). Third-party classical text sources and dependencies preserve their upstream MIT and Public Domain notices in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
