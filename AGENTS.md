# AGENTS.md — high-confidence-mingli-skill

八字、紫微斗数和七政四余的命理文化分析技能。由确定性引擎排盘，按登记来源给条件解释，单盘复审后再对照。

## 运行与验证

- 标准库脚本使用 Python 3.8+。IANA 历史时区需要 Python 3.9+ 和时区数据库。紫微使用 Node.js 18.19+，首次在 `scripts/pai_pan_ziwei` 执行 `npm ci`。
- 总控合成示例 `python3 scripts/build_chart.py --solar 1990-05-15 --hour 14:00 --sex 男 --lat 31.23 --lon 121.47 --utc-offset 8 --analysis-year 2026 --format json`。只确认出生日期或时辰时按[建档流程](docs/onboarding.md)选候选入口。
- 单跑紫微时在 `scripts/pai_pan_ziwei` 用 `node --import tsx pai_pan.ts --solar 1990-05-15 --hour 14:00 --sex 男 --age-year 2026`。独立七政入口使用北京时间，时区换算和各盘口径见[时间契约](docs/time-contract.md)。
- 改引擎跑 `python3 -m unittest discover -s scripts -p 'test_*.py' -v` 和 `python3 -m unittest discover -s tests -v`，先备齐锁定的紫微依赖。改知识库另跑 `python3 scripts/knowledge_catalog.py validate` 和仓库 `tests` 全套。记录跳过项。

## 目录与约定

- `SKILL.md` 路由到 `workflows/` 六个模式及共享流程。`scripts/` 负责排盘，`references/` 存放来源及登记释义，`knowledge/` 决定可用范围。维护人读 [README](README.md) 的使用文档，修改时同步中英文。
- 排盘数字取实际引擎输出。个人分析按[共享流程](workflows/fortune-auditable-reading.md)和[工作记录模板](templates/reading-workpad.template.md)保存范围、依据和复审。按原问先给有依据的结论与适用范围，完整正文默认发在对话。
- [v3](docs/interpretation-standard.md)、[M0](docs/model-judgment.md)和[综合判读方法](docs/conditional-judgment.md)定义现行解释、反条及时间适配。证据核查、原问题是否已答和现实预测效度分别验收。
- 所有模式遵循[知识来源门](knowledge/README.md)。八份同步参考按[来源记录](references/README.md)保留原字节。按登记的来源身份、许可和用途引用，受限模块另存人工记录。`proposals/` 只作审查材料。
- 修改既有分析标准、计算学派或口径、来源隔离或规则启用范围前，先列具体变化与影响并获得用户确认。计算口径获准变更后重跑对应对拍。已批准的标准可直接执行。
- 个人 `chart.md`、`memory.md` 和归档留在技能仓库之外。赛事资料和答案按[外部案例评测](docs/reading-benchmark.md)分组、隔离，完整保留答错和拒答。

## 当前能力与版本核对

- 现行用途及缺口查[判势能力说明](docs/judgment-capabilities.md)，七政同口径对拍和未启用规则查[七政来源与规则](docs/qizheng-rule-profiles.md)。
- 在技能独立 Git 仓库核对提交与工作树。本地工作树、全局安装和 GitHub 分支分别用实际文件、安装回执及远端引用核实，推送范围以用户当次授权为准。
