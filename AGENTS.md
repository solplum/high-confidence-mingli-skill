# AGENTS.md — high-confidence-mingli-skill

## 项目一句话

高置信度命理 skill：八字/紫微/七政三盘由确定性引擎排盘（大模型只解读不计算），解读查典籍资料层并挂出处，跨盘关联不代表准确率，斯多葛收束。

## 怎么跑起来

- 八字/七政引擎：`python3 scripts/pai_pan_bazi.py --solar YYYY-MM-DD --sex 男`、`python3 scripts/pai_pan_qizheng.py --solar ... --hour HH:MM --lat --lon`（纯标准库，无 pip 依赖）
- 紫微引擎：`cd scripts/pai_pan_ziwei && npm ci && npx tsx pai_pan.ts --solar ... --hour ... --sex ...`
- 一键建档：`python3 scripts/build_chart.py --solar ... --hour ... --sex ... --lat ... --lon ...`
- 测试：`python3 scripts/test_pai_pan_bazi.py`、`python3 scripts/test_pai_pan_qizheng.py`（基础引擎 27 项，另有时间契约和 ledger/快照测试；改引擎必跑全套）

## 技术栈

Python 3.8+（标准库）· Node.js 18+（仅紫微引擎）· 主体是 Markdown 指令（SKILL.md + workflows + references）

## 目录与约定

- `SKILL.md` 引擎主文件；`workflows/` 六个模式流程；`references/` 典籍资料层（bazi/ziwei 8 份**逐字节原样**移植，溯源表见 references/README.md——同步上游用整文件覆盖，不要就地改写）
- **排盘数字以 `scripts/` 引擎输出为准，禁止口算覆盖**；重要解释回指实际盘面与适用资料，作者转译及推论注明身份；⭐ 仅为旧展示关联标签，不表示可靠度
- 引擎文件头的「口径声明」是学派定版（恒星制/安命法/四余锚点），改动等于换学派，需重跑对拍
- `chart.md`/`memory.md` 用户数据永不入库（已 gitignore）；改 README 记得中英两份同步

## 当前状态与下一步

- v4 三引擎（058ca66）+ v5 典籍解读层（7b20b8f）+ v6 新 README（cdf355f）+ v7 七政四余典籍知识库（889add2：qizheng 五件原典库+引擎躔宫列+27 测试）均已推送 GitHub main
- 挂账：七政引擎与真实排盘 App 的同口径对拍样本；宿内分度、宫表级庙旺、乐旺制刑和升殿等按现行 `docs/qizheng-rule-profiles.md` 来源门保持未启用，旧表可读不代表获准个人解读。
- 注意：本仓在维护者的工作区大仓内是子目录，GitHub 独立仓为独立历史——推送走维护者的克隆同步流程，不要把工作区整仓当远端

## 可复核个人分析标准

所有个人分析入口先遵循 `workflows/fortune-auditable-reading.md`，按 `templates/reading-workpad.template.md` 保存实际覆盖、执行和复审处理；具体模式只改变问题范围。程序摘要不是完整分析，简短正文不降低核查要求。校准自愿，来源检查不证明预测能力。
解释方法统一读取 `docs/interpretation-standard.md`：区分事实、可定位传统释义、作者现代转译与条件综合，形成有实质内容的判断。合理现代转译无需逐词预注册，自动未编码的部分可继续人工研究；实际字段、必要条件、来源用途和计算契约保持约束。
修改现有分析标准、计算学派/口径、来源隔离或规则启用范围前，先列具体变化与影响并获得用户确认；按已经确认的标准执行无需重复确认。
真实赛事案例的维护评测遵循 `docs/reading-benchmark.md`：按命主分开发/保留集，分析与答案隔离，完整记录拒答和错误。数据与答案必须在仓库之外；`proposals/` 保留审查稿，实际启用以知识登记为准，不能把提案整篇当成可用知识。
已批准 BZ-K01～04 与 ZW-K01～05 的受限模块入口和边界见 `docs/approved-structural-reading.md`；原始输出及审阅记录独立保存，不扩展通用个人ledger用途，其他规则变更仍先确认。
运行所有 Python 检查：`python3 scripts/test_pai_pan_bazi.py`、`python3 scripts/test_pai_pan_qizheng.py`、
`python3 -m unittest discover -s scripts -p 'test_*.py' -v`、`python3 -m unittest discover -s tests -v`。
先在紫微子目录运行 `npm ci`，避免漏跑 Node 集成测试。

## 知识来源治理

所有模式先遵循 `knowledge/README.md`；八份同步原文保持不变，真实性和兼容性由来源登记与隔离层控制。不得以旧标题认定原典。修改知识库后跑 `python3 scripts/knowledge_catalog.py validate` 与 `python3 -m unittest discover -s tests -v`。
