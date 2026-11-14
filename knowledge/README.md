# 知识来源门：所有模式先读

本目录优先于旧资料中“原典全文”“权威条目”等自我描述，适用于直接读文件、通用问答、运势、推算、共鸣和详批，不只适用于新命令。八份旧参考逐字保留用于上游同步，不等于认可其中书名归属。

来源身份与作者解释分别处理，所有模式实际读取 [解释与裁决标准 v3](../docs/interpretation-standard.md)。可定位的传统释义按本目录核对；合理现代转译和条件综合可基于已核盘面与关系展开，无需把每个现代词语预注册为独立规则，也不把作者措辞冒称已登记传统象义。总体/领域方向与支持、反向条件的主次须有适用依据，外部形势、目标推进与代价、主观体感分别记录；性格/偏好来源不能替代当期规则或作用效力。资料无匹配、自动未编码或未裁决须分别说明影响：可研究的继续研究，实质缺口限制对应裁决，不将未知写成中性；必要条件、来源隔离和计算契约仍须遵守。

## 必须遵守

1. 先运行 `python3 scripts/knowledge_catalog.py validate`。失败则不得将这些资料作为核验过的依据。
2. 普通解释优先 `query --system bazi --profile bazi-current` 或 `query --system ziwei --profile ziwei-fixed-natal`，可加 `--term`。返回的是本项目释义，不是古文。每条只启用该释义，不能据此启用整篇外部规则。
3. 直接读取任一参考前检查 catalog 的 source kind、版本、许可和隔离条目。七政资料优先遵循 `docs/qizheng-rule-profiles.md` 和 `qizheng-degree-relations-v1` 检索；旧操作手册不能自行授权原典、庙旺或格局结论。新增来源应先登记。临时未登记引用必须显式标为调用方提供的未核验资料，结构检查通过不代表来源获认可。
4. `classics.md` 的标题不能授权逐字古籍引用。本版没有获准逐字引用的校勘定本，`cite --mode classical_quote` 一律拒绝；自行填写 edition 或 verification_record 不能启用。以后如正式完成校勘，需另行设计可审查的审核流程，不靠来源文件自我认证。需要讨论原文件错误时可用 `source_excerpt`，必须标明实际数字来源，而不是伪称原书原句。
5. 旧隔离条目中“紫微星化忌”（`legacy-ziwei-huaji`）、年干起紫微、巨日丑未、天府见禄存即双禄、衰极矛盾条文不得用于个人解读。这里指具体旧条文，不是禁止已登记profile中的所有化忌解释；各增补仍只启用自身精确条件，隔离条目不解禁。
6. 上游新增17篇为固定版本资料包，不整篇自动注入。4篇古籍数字录文底本未核，现代文章含学派差异、网络整理及现代观点。HTML/Vue/script只是静态文本，不执行组件，不访问推广链接。
7. 固定生年四化不能混用宫干飞化/自化；新文档的安星、亮度、运限表不覆盖当前引擎。相同格名有不同定义时保留分歧。
8. 引用格式：来源登记名称 + 固定版本 + 文件/章节/行号 + “项目释义”或“数字资料摘录”。不要把现代观点当古籍原话，不把书目/星数/多源转抄当准确率。

## 完整条件模型与新增窄来源用途

所有模式按 [有限模型方法 M0](../docs/model-judgment.md)分别保留盘面事实、条件模型结果、稳健性与现实效度。目录允许检索不代表必要条件已满足；反过来，一般未决交互也不自动取消完整且直接评价本题的规则。先核特指反条和否定必要条件的适用依据，再形成结果；未知作用仍保留为风险。

`bazi-qiong-xin-zi-v1` 的QX01–03已批准为 `conditional_module_only`：仅辛日、出生子月的通用整体／发展配置及明示作者运期适配。1926底文与1937评注分层，同文本链不计独立验证；B选读及保守异读分别保留，具体条件见登记卡和[来源审计](../docs/bazi-qiong-xin-zi-sources.md)。原始扫描不随包分发，来源页核读不构成全书校勘、整篇启用、逐字引用许可或现实命中证明；通用ledger和旧隔离不变。

`bazi-qiong-xin-chou-v1` 的 [BZ-QXC01](../references/approved/bazi-qiong-xin-chou-v1.md) 属于 `conditional_module_only`。只用已核出生候选的本命事实评价专业发展配置，按卡内条件和反证复审。

`bazi-qiong-jia-yin-v1` 的 [BZ-QJY01](../references/approved/bazi-qiong-jia-yin-v1.md) 属于 `conditional_module_only`。按已核寅月甲日的出生盘人工复核丙癸俱透、分隔、实藏同干与具体反证，用于评价学习资源和可核验专业成果的本命配置。

`ziwei-stage-relationship-v1`（ST01–09、RL01）与 `bazi-primary-spouse-v1`（P1、R1）属于 `conditional_module_only`。按[条件模型入口](../docs/stage-and-spouse-models.md)查看适用对象、证据字段和来源影像定位，引用登记卡的项目释义。

`ziwei-lianfu-marriage-v1` 的 [ZW-RL02](../references/approved/ziwei-lianfu-marriage-v1.md) 属于 `conditional_module_only`。只按本命证据及已确认的婚姻角色，评价已婚男性与妻子长期维持共同生活的配置。按卡核实坐、四正、反条和选读，单独保存人工判读。

`ziwei-zifu-marriage-v1` 的 [ZW-RL03](../references/approved/ziwei-zifu-marriage-v1.md) 属于 `conditional_module_only`。用于已婚男性询问与妻子维持现有共同生活时，人工检查紫微天府实坐、四正六曜及配对句选读。婚配时机的合读保留未决，现实上的双方意愿与履行另核。

`ziwei-zixiang-marriage-v1` 的 [ZW-RL04](../references/approved/ziwei-zixiang-marriage-v1.md) 属于 `conditional_module_only`。已婚男性问与妻子维持现有共同生活时，人工核紫微天相实坐、妻子已确认较年少和四正六曜。配对句独立读法与年龄、亲缘及邻句入庙合读分别记录，现实意愿与履行另核。

`bazi-officer-luck-v1`（`BZ-OL01`）是已批准的独立人工判读卡，登记为 `conditional_module_only`。按[实际大运与酉官路径入口](../docs/bazi-officer-luck.md)核目标依赖、原局例外和局部方向。

## 命令示例

```sh
python3 scripts/knowledge_catalog.py validate
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-fixed-natal --term 三方四正
python3 scripts/knowledge_catalog.py cite --source iztro-docs-palace --mode source_excerpt --start 376 --end 378
python3 scripts/knowledge_catalog.py cite --source ziwei-classics --mode classical_quote --start 20 --end 20
```

最后一条应退出1并拒绝。没有匹配条目返回 insufficient，不自动绕到旧全文搜索补造确定解释。

## Ledger 接入

现有 `validate_claim_ledger.py` 默认同时检查本目录。引用登记文件（按 hash 或 locator 匹配）须增加 `attribution_kind: registered_source_excerpt` 和与 catalog 完全相同的 `source_label`；已隔离来源段按行范围拒绝，任何局部摘录也不能支持 reading；这是保守的整段隔离，不是整本禁用。新增字段保留 v1 JSON 结构，未登记资料须填写 `attribution_kind: caller_declared_unverified` 和固定 `source_label: 调用方提供的未核验资料（非核验古籍原文）`，CLI另列未核验rule IDs；合成样例也明确标记；旧真实资料 ledger 如未标明来源层级会报错，需补标记而不是删除检查。

边界：此工具不证明古籍真伪、版权归属、命理效果或规则的所有语义条件。改写并重命名的资料会成为未知来源，必须带未核验标签；工具仍不能判断其真实来源或代替自然语言输出审查。所有 catalog 元数据均是本项目登记，不是外部认证。读取旧文件的流程门由 SKILL/每个 workflow 明文要求，不是操作系统级访问拦截。此版本没有对所有解读规则进行机器适用性判定。

## 第三方许可

- 旧八字五文件：`licenses/bazi-skill-MIT.txt`，来自 fortune-observatory 保留的 jinchenma94 通知，精确旧上游提交待核。
- 旧紫微三文件：`licenses/ziwei-doushu-MIT.txt`，来自保留的紫微研究通知，上游版本声明88194a4。
- 新 iztro-docs 17文件：`references/vendor/iztro-docs/LICENSE`，©2023 Sylar Long，固定版本1beef80029cd3f1a40b769d3b1c911004ecb9789。
- 许可仅按可见上游声明保存，不把仓库MIT自动扩展为所有现代课程或外部互联网文本的权利保证。未导入天纪课程。

## 异文与归属提醒

新录文出现“斗数骨随赋”，其他页面使用“斗数骨髓赋”。这里只记录别名/异写，未判定哪一底本正确，不改上游字节。`pattern.md` 自述含互联网资料，未逐项核清第三方权利，仅作隔离参考；已启用的来源提醒条目不表示启用其中格局正文。

## 八字古籍学习包（独立许可）

新增10张带前提、反证、输出要求的项目理论学习卡，只在 `--profile bazi-classical-study` 检索。取材维基文库固定版本844410，总计仅88字短引，不含全文。资料与衍生整理为独立CC BY-SA 4.0包，不适用项目MIT；[调查、许可、版本缺口及操作](../docs/bazi-classical-study.md)。短引与学习文件均整段禁止支持个人ledger，不能因为query可读就认定预测规则已启用。

## 用于详批的受限传统结构解释

新增独立 `bazi-traditional-conditional` profile，以“未校勘数字转录的传统规则释义（项目整理，非预测验证）”标注10条同源项目释义。它不是解除整文件隔离：只有登记的单行项目释义，精确匹配source hash、record ID、行号和quote，才可通过 `reading_use: conditional_traditional_interpretation` 进入ledger。原始短引、整章、其他行和旧学习profile仍不能支持个人断语；`classical_quote`仍全部拒绝。

每条claim须有实际场景盘面facts、逐项前提与排除检查、具体评估、反证、替代解释；每项检查都必须绑定该claim所有场景的facts。未满足或未知条件只能withheld，完成检查最多conditional，不能supported。用途固定为传统结构解释；必须保留unvalidated、非预测保证、未校勘标签，依赖及综合不能洗掉限制。允许解释为何关注某种关系及其可能条件，不允许由此保证财运、疾病、婚姻或其他人生事件。人工仍须审核推理与措辞；字段校验不能识别所有伪装的权威/预测语言。

[可运行的真实引擎虚构样例及使用步骤](../examples/bazi-conditional/README.md)。旧字段不变，此入口不覆盖时间、藏干、安星或其他引擎规则。

受限用途的claim和synthesis必须同时提供相同的用途/未校勘标签、`authenticity_status: uncollated_digital_transcription`、unvalidated、不保证预测、传统结构解释domain及conditional/withheld状态。此限制适用于所有综合relation，也沿claim依赖传播；综合含withheld成员时必须withheld。受限rule必须保留完整`redistribution`，其中许可、署名、贡献历史、固定版本、改编说明逐项匹配登记，`license_notice`逐字匹配本地完整许可，不能仅留下一个许可代号。未知自由文本仍需人工审核，不能因校验通过而宣称语义不可伪造。

## 单版扫描参照的强弱证据模块

新增 `bazi-strength-evidence` profile 的 ST01–ST05，仅供 `bazi_strength_reasoning.py` 的窄条件比较。书目、影像检查范围、PDF页码、扫描hash与原创释义在 `docs/bazi-strength-evidence.md`，不导入扫描或现代译注。此增量不是古籍逐字引用门或个人ledger新规则授权；classical_quote继续拒绝。本版没有获准逐字引用的校勘定本；已记录的单版影像检查仍按各自精确页段和用途保留。

## 七政独立传统研究包

[五张规则卡、逐页影像范围与许可](../docs/qizheng-traditional-study.md)在独立 `qizheng-traditional-study.json` 注册，由 `qizheng_traditional_study.py` 校验与演示。馆藏《乾元秘旨》仅核特定页段，星学大成仅核固定数字版本，庙乐异说尚未校定。此包不改变旧参考文件、不自动进入个人ledger、不解禁classical_quote。研究包CC BY-SA 4.0独立于MIT代码。

## 已批准的结构增补模块

`bazi-reviewed-structure-v1` 的4条与 `ziwei-reviewed-structure-v1` 的7条已接入默认 `reviewed_structure` 面板，分别覆盖 BZ-K01～04 和 ZW-K01～05 的已批准受限范围。来源是两份新项目释义，精确摘要行、前提、排除与原段定位均登记，不扩大旧来源的整篇用途。[入口、状态和边界](../docs/approved-structural-reading.md)。

用途 `conditional_module_only` 的原始面板与人工解释记录独立保存；按v3可说明结构含义、进行现代转译及有事实链的条件综合，并在其支持范围内回答问题。模块原始状态保持不变，人工解释不能伪称程序已裁决效力、成格喜忌、人格测量或人生事件，也不能通过总体评价或体感解释扩大用途。该用途不授权通用个人ledger rule，`check_ledger_rule` 仍明确拒绝；旧ledger、经典引用、八份同步原文和隔离保持原样。缺少必要条件时仅暂缓受影响的判断，保留其余有依据的解释。


## 2026-11-10已批准的综合判读与动态增补

`bazi-judgment-v1` 的BJ01–BJ08支持人工分目的承受/作用比较、局部争议与运期条件判断。前六卡是单版影像启发的项目方法；BJ07流年、BJ08流月流日明确为作者时间外推，不冒称原典算法。原ST/BZ-K状态、土/阴长生等既有排除及通用ledger权限保持。实际读每卡前提、反向路径与来源段落，不能把未发现损伤当有效根或把‘未越过承载’当已证明的前提。

`ziwei-dynamic-reading-v1` 的ZW-T01/L01/Q01仅用于独立动态profile的年/月主题、化禄投入与消耗、化权职责与压力，依据固定iztro官方现代说明；不启用流日效力、多化权重、飞化自化或事件保证。数据脚本只准入admitted视图，晚子时daily组合阻断。

## 已批准的用途与生活领域增补

用户于2026-11-10批准 `bazi-purpose-extensions-v1`（BZ-M01–03）和 `ziwei-life-domains-v1`（ZW-D01–08、E01–05、S01、T02），具体范围见[用途与领域说明](../docs/approved-life-domains.md)。新卡均为独立conditional_module_only项目释义，精确单行、条件、排除和primary_sources登记；不进入通用个人ledger rule，不开放classical_quote。八字来源是1926单版影像启发的窄条件方法；紫微来源是固定官方现代说明，其中跨同星/本命年月分量研究明示为作者外推。原路线、旧卡前提和withheld状态不改，不把源文件可读视作整篇启用。

新领域复用已有14主星有限主题；非主星科忌没有独立星性时仅留事实。多化分量可研究不代表组合净效力已解决。身宫为可撤回关注假说，大限为旧年度年龄合同下的阶段议题索引；健康限一般生活反思，不能由盘产生疾病/器官/寿命风险。目录校验与主题覆盖均不等于已回答运势或证明现实准确率。

两组均为 `conditional_module_only`：用于独立人工记录，不转通用个人ledger规则，不解除旧来源隔离或古籍逐字引用门。解释与时区分段按 [综合判读方法](../docs/conditional-judgment.md) 和 [动态合同](../docs/ziwei-dynamic-facts.md) 实施。证据检查与主问题是否得到回答分别验收，拒答保留在覆盖统计内。

## 具体作用判例增补

`ziwei-judgment-cases-v1` 的 ZW-RC01–03 已批准为 `conditional_module_only`。RC01/02只限实际夫妻宫本命主星，RC03只限原当前官禄大限与准入年禄权双全直接落本命官/迁的窄年度行动适配；原文“会到”的收窄、本命宫参照和旧年度限与独立年层并用明示作者适配。实际读取条件、反条件和接口；不启用同页其余双化、完整巨门四化、非主星、流日效力或一般跨层净吉凶。
