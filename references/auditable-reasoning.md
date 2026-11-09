> **知识来源门（所有引用必读）**：先读 `knowledge/README.md` 并验证 `knowledge/catalog.json`。这条约束优先于下文旧的“原典/权威/书名章节”说法；旧摘要仅作有来源的现代整理，隔离条目不用于解读，未核版本不作逐字古籍引用。直接读旧 references 也必须过此门。

# Claim ledger v1：使用说明与验证边界

这是工程协议，不是古籍，不更改 `references/bazi`、`references/ziwei` 或 `references/qizheng` 原始资料。原排盘输出、chart.md、memory.md 与七节详批兼容。个人分析按 `workflows/fortune-auditable-reading.md` 保存证据与工作记录；符合现有用途的判断使用 ledger v1，module-only 等受限模块保存原始证据与人工解释记录，真实用户档案存放在 skill 仓库之外。通用知识问答不要求私有 ledger；涉及个人盘面对照时，该部分进入个人分析流程。无机器快照或无法运行校验时保留明确受限记录，不声称已完成机器校验。

解释内容遵循 [统一解释标准](../docs/interpretation-standard.md)，区分盘面事实、可定位传统释义、作者现代转译与条件综合。现代用语无需逐句注册，但作者转译须保留实际依据和推论身份；它不改变本协议的规则摘录、来源用途、依赖和状态检查。

## 文件结构

可运行的样例：`examples/claim-ledger.example.json`。它仅含合成规则和占位字段，不是完整命盘，也不是命理准确性的案例。验证：

```
python3 scripts/validate_claim_ledger.py examples/claim-ledger.example.json --root examples/ledger-fixture
python3 -m unittest discover -s tests -p 'test_claim_ledger.py' -v
```

真实使用时，将所用引擎 JSON 快照和实际引用资料副本放入本次私有证据目录，计算各文件 SHA-256。先运行 `python3 scripts/build_chart.py ... --format json` 获取三引擎快照（默认文本输出仍兼容），事实以 JSON pointer 连接。缺失紫微时值为 null 并附原因，不得补造事实。快照应另存运行命令、版本和口径说明，不能把这些元数据当排盘事实。不要把含个人资料的 ledger 或快照提交到公共仓库。

顶层：`schema_version: 1`、`purpose: reading | synthetic_test`，以及以下数组。每张表的 id 唯一。

- **sources**：id、kind（chart/reference）、path（相对 --root）、sha256。路径含符号链接时也必须仍在根目录内。只读普通文件，不执行其内容。chart 来源还必须声明 system、scenario_id、pointer_prefix（如 /bazi），事实须与绑定一致；同一路径不能重贴标签当成另一候选场景，同一文件的不同体系前缀不能重叠。每个场景分别保存快照，即使数值恰好相同。hash 只证明此次快照没有改变，不证明上游真实性。
- **scenarios**：id、label、time_basis、assumptions。每个实际生成的候选输入与口径一个场景；未检查的争议写入限制，不伪造候选。
- **facts**：id、system（bazi/ziwei/qizheng）、scenario_id、source_id、pointer、value。必须逐字段等于 chart JSON；支持字典和数组指针。计算结果也是在指定模型下的结果，不等于现实事件证据。
- **rules**：id、system、source_id、school、locator、start_line、end_line、quote。行号从 1 起；引文必须逐字存在于该行区间。locator 写原书/整理本/章节等真实定位；校验器不替你核实版本权威或规则是否适用。
- **claims**：id、system、domain、time_scope、statement、status、fact_ids、rule_ids、depends_on、scenario_ids、conditions、counterevidence、alternatives、boundary、explanation、limitations。无依赖仍填空数组。explanation 有 plain / technical / action 三段；在现有授权与状态允许的范围内，说明资料原意、作者现代转译和综合理由，规则quote仍保留实际来源文字，不为转译伪造引文。
- **syntheses**：id、claim_ids、relation（agreement/conflict/different_scope/insufficient）、explanation、shared_inputs、limits。至少两个不同体系，合参不可反过来充当单盘证据。agreement 需同领域、时间范围和场景集合。

`status`：supported = 在已核对的规则及场景内有支持；conditional = 有条件或缺口；withheld = 暂不作判断。三者都不是预测可靠度。

`boundary`：stable = 对所有已列候选都有事实链支持；conditional = 只在部分候选成立；unassessed = 尚未检查。非 stable 不能标 supported。声明 stable 仍需人工比较实际解释是否相同，脚本只能查场景覆盖。

`counterevidence` / `alternatives` 不可空。确无足够资料时明确“未能检查，因为缺少 X”，不得写成“没有反证所以成立”。这两个字段必须人工复核内容，不以非空就算研究完成。depends_on 仅限同体系判断，禁止循环；依赖须覆盖当前判断的场景并使用相同 time_scope，不得将 withheld 或 conditional 依赖偷偷升级。跨时间层的依据应作为原始 facts 引入并说明条件，不用不同时间范围的 claim 偷渡。

## 可以自动检查什么

重复与悬空 ID、字段引用值、引用文件 hash、行范围和引文、与显式来源绑定不符的体系/场景混入、依赖循环、声明的场景覆盖、范围不一致的合参，以及显式概率/星级字段。CLI 返回 JSON；通过退出码 0、校验失败 1、输入无法解析 2。无网络请求，无第三方运行依赖。

**不检查**：快照是否确由声称的命令执行生成（复制后重新命名的文件仍需人工核查）；来源的体系/场景/字段前缀声明本身是否真实；天文/历法计算本身是否正确；源文件真实性；所谓经典是否真的原典；规则前提是否语义满足；反证搜索是否充分；自然语言是否夸大；预测能力；健康、财务等建议是否合适。未知附加字段保留兼容性，不意味着它们经过验证。不能将“校验通过”宣传为“算得准”。这是一致性检查，不是抗恶意伪造的签名证明。除合成结构样例外，examples/engine-reading 包含实际引擎的虚构输入端到端演示；仍未完成真实个案的解读质量或命中率评测。

## 与 fortune-observatory 的对照与取舍

对照了该项目 `apps/api/reading_agent.py` 的 `build_reading_system` 和 `tests/verified/test_split_reading_contexts.py`。借鉴的是“单体系上下文隔离 + 测试防混入”这一设计模式，没有复制其运行代码、提示词或典籍文本。

不照搬其混合模式“紫微为主、八字印证”的默认优先级，也不沿用把 qizheng.chart 路由到紫微语境的分组。七政的星框、日月处理与用/仇口径需要按版本分别核查，不能因名字相同就当作可替换数据。后续如移植素材，应逐文件核对许可证、来源版本、语义与回归样例；本次新增实现完全独立。

## 个人分析入口与工作记录

详批、具体问题、运势及共鸣对照均先执行 `workflows/fortune-auditable-reading.md` 的共同流程；各分支仅决定本次问题和时间范围。可进入 ledger 的重要判断沿用 v1 连接实际字段、登记规则、条件、反证、替代解释和场景。用途受限的原生模块及其人工解释在工作记录中保存唯一ID、原始面板定位与同等依据摘要，不为凑齐文件创建假claim、伪造引文或改写模块状态。supported 始终只表示给定规则和场景内的支持，不表示现实预测可靠度。

按 `templates/reading-workpad.template.md` 保存本次执行记录、主题覆盖、检索结果与无匹配项、单盘初稿、现代转译与综合理由、独立复审发现及处理结果，并连接 ledger、原生模块、来源副本和最终正文。自动未编码或未裁决的内容可在获准方法与资料范围内继续人工研究，实际缺失字段、必要条件和来源限制仍约束相应解释。工作记录补充人的语义审查，不改变 v1 字段，也不把隐藏思维过程当交付要求。

跨盘对照可定位合法ledger claim或原生模块人工解释记录，并保留各自用途和共同依赖。v1 JSON的syntheses仍只引用本ledger合法claim_ids；涉及原生模块的对照保存在workpad或报告，不把模块记录伪装成ledger claim。七政已有的禁止个人事件claim、合参投票或校准命中等限制继续按对应模块执行。

完成按相关主题的检查充分性判断：有可查的字段和来源，条件与反向解释已检查，实际边界已比较或明确缺口，复审发现已处理，正文与最终证据一致。机器校验结果和未运行项如实记录；篇幅、引用条数及耗时都不能单独证明完成。中断时保存已完成项和待办，不将未检查项记为通过。

## 来源门升级

ledger 现在自动检查已登记来源的摘录标记与隔离片段。引用旧整理文件需 attribution_kind=registered_source_excerpt 及登记 source_label；仍不证明原书真实性或语义适用。见 knowledge/README.md。

来源门加强：隔离按已知来源的行范围而非完整短句匹配；未知引用必须显式标为 caller_declared_unverified，且CLI列出对应rule IDs。本版不存在可自填元数据升级的原典认证路径，classical_quote 暂不可用；普通资料摘录不受此限制。
