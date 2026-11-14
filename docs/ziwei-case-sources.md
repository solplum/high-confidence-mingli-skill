# 紫微具体作用判例：来源与接口

用户于2026-11-10批准RC01–03的精确受限用途。语义卡在[ziwei-judgment-cases-v1.md](../references/approved/ziwei-judgment-cases-v1.md)，登记于`knowledge/catalog.json`的独立`ziwei-judgment-cases-v1` profile。本文件只说明定位与接口，不是另一套规则源，也不因此新增通用个人ledger权限。

来源卡的SHA-256为`ddfe8435f9a678dc2b34015a1c79fe6f5dee2c56b245836659b0b7fcc029ec7e`。三张record ID分别为`ziwei-cases-ZW-RC01`、`ziwei-cases-ZW-RC02`、`ziwei-cases-ZW-RC03`；source ID统一为`ziwei-judgment-cases-source`。项目释义精确单行分别为13、62、115，均为`conditional_module_only`。

| 卡 | 固定原料定位 | 此次新增的精确用途 |
| --- | --- | --- |
| RC01 | `mutagen.md:124–126`；同宫背景110；夫妻领域背景`palace.md:63–65` | 实际夫妻宫两颗14主星分别带本命权忌，在双方均有决定权的协商中研究要求升级的局部摩擦假说 |
| RC02 | `major-star.md:704`；夫妻领域背景`palace.md:63–65` | 夫妻宫实际巨门本命忌，按天同是否实际同宫选择表达反条件分支 |
| RC03 | `horoscope.md:59`；本命、大限三方四正与流年背景54–57 | 旧原native当前官禄大限，加同一查询点准入年禄、年权均直接附着本命官迁实际14主星的窄年度主动申请/接洽适配 |

原料均为Sylar Long / iztro-docs官方现代说明，固定提交`1beef80029cd3f1a40b769d3b1c911004ecb9789`。primary_sources逐项登记行号、固定提交和原文件hash，四个文件hash与现有来源登记一致。原MIT许可和署名保留于[原料许可](../references/vendor/iztro-docs/LICENSE)，项目条件释义与作者适配适用项目MIT；这不是古籍引文、校勘定本或预测验证。

RC03的三处作者适配分别是：把“会到”收窄为两化均直接附着实际14主星；官禄/迁移按本命宫名解释；旧公历年度年龄大限与独立农历年profile准入年层并用。三处均在卡与catalog的`author_adaptations`中保留，不能宣称源文已逐字定义这些实施条件或官方已完成同口径叠盘。

`reviewed_knowledge.load_profile`按完整record ID集合加载该profile，并从精确项目释义行生成citation。规则模块从卡读取`conditions`、`exclusions`、`direction_branches`、`author_adaptations`、`time_boundaries`和`counterexamples`，程序只匹配事实谓词，不测得现实任务状态。分支格式为`key`、`condition`、`direction`和`counterconditions`；RC01的key为`negotiation_friction`，RC02为`tiantong_copresent`/`tiantong_absent`，RC03为`proactive_application_fit`。

允许在来源、目标与条件明确时提出可撤回的前瞻工作假说，不要求先观察到对应行为。任务阶段需由实际背景或明确分支给出，实际表现相反时撤回个人化。事实谓词命中仍不等于现实条件成立、全年覆盖、整体关系/事业净方向或事件成功；RC03只核显式查询点，跨公历年、春节年界或旧大限年度窗须分别核查。

本增量不改旧37个source、106条record的内容，不解禁非主星性质、借星效力、多化相加抵消、raw新大限/年龄/流时、飞化自化或月日净判。`knowledge_catalog validate`只核文件完整性与元数据；`check_ledger_rule`仍拒绝本profile，`classical_quote`仍拒绝。
