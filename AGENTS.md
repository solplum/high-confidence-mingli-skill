# AGENTS.md — high-confidence-mingli-skill 维护指南

> 八字、紫微斗数、七政四余三引擎排盘 + 清洗验证后的三体系古典原典库。

## 运行与验证

- **Python 环境**：Python 3.8+（全标准库，零第三方依赖；IANA 历史时区需 Python 3.9+ 及系统 `zoneinfo`）。
- **Node 环境（紫微引擎）**：Node.js 18.19+，首次在 `scripts/pai_pan_ziwei` 运行 `npm ci` 安装锁定依赖 `iztro 2.6.1`。
- **三盘合排入口**：
  `python3 scripts/build_chart.py --solar 1990-05-15 --hour 14:00 --sex 男 --lat 31.23 --lon 121.47 --place 上海 --analysis-year 2026 --format json`
- **原典检索入口**：
  `python3 scripts/mingli_query.py stats`
  `python3 scripts/mingli_query.py bazi-lookup --day-stem 庚 --month-branch 巳`
  `python3 scripts/mingli_query.py chart-lookup --chart-json - --topic career`
- **完整测试集**：
  `python3 -B -m unittest discover -s scripts -p 'test_*.py' -v`
  `python3 -B -m unittest discover -s tests -p 'test_*.py' -v`

## 目录结构

- `SKILL.md`：主入口与标准 4 步分析流，路由到 `workflows/` 六个具体场景文件。
- `scripts/`：确定性排盘引擎（`pai_pan_bazi.py`、`pai_pan_qizheng.py`、`pai_pan_ziwei/pai_pan.ts`、`ziwei_dynamic_facts.mjs`、`build_chart.py`、`time_scenarios.py`）＋ 原典检索引擎 `mingli_query.py` ＋ 回归测试。
- `references/corpus/`：7 份清洗完毕的结构化 JSONL 原典语料（1,351 条）与 `manifest.json`。修改语料须同步更新 `manifest.json` 的计数与 SHA-256，并通过 `scripts/test_mingli_query.py`。
- `references/` 其他文件：四领域信号指引与三盘静态速查表；开源归属见 `THIRD_PARTY_LICENSES.md`。
- `docs/`：`onboarding.md`（建档流程）、`time-contract.md`（时间/历法/边界契约）、`corpus-audit.md`（语料来源与清洗审计记录）。
- **隐私边界**：个人档案保存在 `~/.claude/fortune-telling/`（仓库外），切勿提交任何真实命主数据或隐私文件到仓库。
