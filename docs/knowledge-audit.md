# 命理知识库审计与最小可行扩建方案

审计日期：2026-11-07。只读审计原仓；本报告不证明术数有预测效力。

## 已有语料，不应重复迁移

核对目录：mingli-time-scenarios、fortune-observatory-audit。
本地 Git HEAD 分别为 f575c1566ff9b880f28df95ee16b28d443599302、3ce1995e41b29e4ab2320323a969158f4e5b2214；工作树可能有后续未提交修改，文件 hash 才是本次审计标识。

八字五份、紫微三份资料与 observatory 的 skills 副本逐字节相同。逐文件尺寸、行数、SHA-256 见 corpus-manifest.json。八字 classical-texts.md 是175行九书知识摘要，不是九本书；紫微 classics.md 为154行汇编，patterns.md 为350行、41个程序规则目录。不能将文件数量/书名数量当成已读原典数量。

- 八字来源 README 指向 jinchenma94/bazi-skill，MIT，副本 LICENSE 为 Copyright (c) 2025 jinchenma94；未核出该八字副本的精确上游 commit。
- 紫微 README 指向 Renhuai123/ziwei-doushu@88194a404242bfe5c6d5cc512e4117e3e245cdd5，MIT，副本 LICENSE 为 Copyright (c) 2026 紫微研究。该 commit 是现有文档声明，本次未联网重新核验。
- observatory 的 scripts/dump_refs.ts 从 vendor/classics/data/{gusuifu,quanji,quanshu}.ts 生成所谓原典；生成路径可追溯不等于古文真实性可追溯。
- mingli 的 LICENSE 只含 solplum 通知，另有 lunar-javascript 通知。未找到上述两份 MIT 通知，应复制为第三方许可并建立文件映射。MIT 软件许可不能自动证明每条现代转引的授权。
- observatory 的 lore.py 把这些本地文档称作原文且整包注入；它不是新的独立证据来源。不要迁移其无条件权威提示词。
- 七政已有六份文件，其中 reading 为操作手册，其余为辑录索引；来源 README 声称殆知阁《张果星宗》《星学大成》《乾元秘旨》。本次没有逐条核验这部分，不能将它们标成已完成版本校勘。

## 应先修复的来源可信度

保留八份原文件不改，满足 AGENTS 的逐字节同步约定。用覆盖式来源登记、检索白名单和隔离记录改变使用权限，不悄悄篡改来源。

1. ziwei/classics.md 标题“古籍原典（全文）”不能成立为已验证事实：出现“企业高管”“能力变现”“逆袭”，qs-5-2 更直接提及倪师。文献定位只有自拟段号，没有版次、页码或影印图。全文件暂归“上游现代整理，原典归属未证”，禁止以《全书/全集/骨髓赋》逐字原文引用。可在历史审计中引用此文件本身。
2. classics.md:20 gsf-2-4 明言“紫微化忌”，不在当前十干四化表中，应隔离此命题。
3. classics.md:72 qj-1-2“先以年干起紫微”不足以描述当前以农历生日和五行局等参与的安星方法，不能作计算依据。
4. classics.md:84 qj-3-1 将天府见禄存称双禄朝垣；同文件43/108/152及 patterns.md:218 则要求化禄、禄存。存在内部规则冲突，不许合并成一个规则。
5. classics.md:87 qj-3-4 将巨日同宫写在丑未并称日月反背，疑混淆不同组合。暂隔离，待固定引擎穷举和原书核验。
6. classics.md:26“七杀逢化忌”是遇/会照还是自身化忌未写清，列语义含糊而不是断言必然错误。
7. bazi/classical-texts.md:71“衰极宜扶不宜帮”与随后“弱到极致反而不能再帮扶”内部矛盾，隔离。
8. bazi/classical-texts.md:62 把得令等同长生/帝旺，缺阴阳干十二长生与月令旺相休囚死区分，待考，不能机械用于强弱评分。
9. bazi/classical-texts.md 把调候首要、扶抑用神、月令格局用神塞入单一语义。分别建调候、扶抑、格局模块，不能替代同义词。
10. bazi/dayun-rules.md:62 的整数舍入与精细起运时刻不是同一精度，登记为旧展示说明，不可覆盖当前引擎。
11. domain-signals.md 感情紫微列写“四化飞入”，与固定生年四化口径可能冲突；区分四化落宫与宫干飞化，后者未实现则禁用。

## 详批缺口：优先添什么

八字：月令与透干/通根；旺衰不同判法的证据与限制；十干十二月调候的逐条定位；正格成败救应；合而不化/化气条件；刑冲合害的位置条件；大运流年如何引动而不保证事件；六亲取象作为历史术语而非现代性别和关系事实。
紫微：十四主星分宫位及组合条件；三方四正、夹拱、空宫借星的明确关系；原局/大限/流年层级；庙旺与四化所用表版本；逐格成立/破格的程序条件与书本论法分开；三合解释和飞星解释隔离。
两者：反例、例外、未覆盖组合、争议条目、解释的现代转写与实际可行建议。避免扩充成无条件吉凶句子集合。

## 最小模块结构

新增 knowledge/，不混入上游原文件：
- sources.json：书目与软件来源注册表。
- records/*.json：原子知识条目，按 bazi/ziwei/qizheng 分体系。
- profiles/*.json：已实现计算口径和可适用解释模块。
- quarantine.json：明确不能用于正式解释的旧条目及理由。
- migration-manifest.json：源文件/目标文件/hash/许可/动作。
- THIRD_PARTY_NOTICES.md + licenses/：保留原许可及适用文件。
- docs/knowledge-audit.md：读者能理解的版本、分歧和局限。

### sources 必填字段

source_id、title、kind（classical_edition / modern_commentary / software / project_method）、author_or_attribution、edition、editor、publication_or_repo、url、retrieved_at、revision、license_status、license_path、provenance_status、sha256、notes。
没有资料的字段用 null 加 reason，禁止填猜测。古籍作者“相传”不能写成确定作者。古籍公版地位、现代排印/OCR许可、软件许可分开记录。

### records 必填字段

id、system、topic、source_id、content_kind（verbatim / paraphrase / implementation_rule / project_guidance）、title、text、locator、quote_text、quote_span、source_hash、review_status、compatibility、requires、exclusions、conflicts_with、interpretation、limitations。
- locator 包含卷/章/页或稳定上游文件行范围；页码缺失不能伪造。
- verbatim 必须有逐字 quote_text 以及原始版本页/文件定位；不能把自己的释义填进去。
- paraphrase 的 text 是本项目写作，quote_text 可 null；不得显示成古书原句。
- compatibility 至少包含 calendar_profile、day_rollover、ziwei_sihua_profile、brightness_profile、luck_layer、school_module；不适用写 null，未知不是通配。
- requires 为可判断的事实条件（JSON pointer、operator、expected）；exclusions 为破格/冲突条件。语义前提未能自动表达时加 manual_review_required，不让校验器假称通过。
- review_status：candidate / source_checked / compatibility_checked / quarantined。两种 checked 是证据核验维度，绝非术数有效性评级；可以拆成独立字段避免被当成线性质量分。
- interpretation 分 traditional_meaning、modern_paraphrase、conditional_application、practical_reflection。最后一层不冒充古人观点。

## 检索与引用行为

1. 先选引擎快照和 profile，再取同体系同模块、时间层匹配条目；不先全文搜命中关键词就下结论。
2. 默认排除 candidate/quarantined。未知兼容性拒绝进入正式候选；允许单独展示为何未采用。
3. 条件缺失返回 insufficient，不将“文件中存在句子”当作“本盘满足句子前提”。
4. 每条论断给事实字段、规则条目 ID、适用条件、反证/例外、来源定位。出处仅能声称核实到的层级：上游摘要就是上游摘要。
5. 冲突条目并列保留，说明是异本/学派/实现/疑错，不投票合并。同一上游的三个复制库不算三个独立来源。
6. 原始古文和现代释义分开输出。医学、财富与具体人生结果不从术语直接升级为现实事实。
7. 现有 claim ledger v1 可继续用，但目前只核 hash、局部引文、字段和依赖，不核古籍真实性/规则适用。新增 knowledge validator 不应默默改变旧 v1；接入新的可选 catalog 校验参数，记录是否做了目录核验。

## 验收测试清单

- 八份原文 hash 不变；第三方版权通知存在且清单路径对应。
- source/record ID 无重复或悬空；缺版本定位不能声明 classical verbatim。
- hash、引用行、逐字文本不符必失败；现代释义无法作为古文引号输出。
- 默认检索不返回隔离条目（覆盖紫微化忌、巨日丑未、衰极矛盾）。
- 同关键词但不同体系、学派、时间层、四化表、庙旺表不串用。
- 固定生年四化 profile 不命中飞星/自化规则；没有对应字段拒绝精确规则，而非造字段。
- 条件不足、成立与破格同时出现、边界场景不同，分别产生 insufficient/conditional。
- 保留冲突关系；不能因多个复制源支持自动增加置信分。
- 所有当前已实现十干四化组合对表；十四星安置和宫位关系用确定性引擎样例核验。
- 不执行任何下载脚本或文本；路径不能越出 root，源内容不能作为工具指令。
- 原有 claim-ledger、快照、时间契约及三引擎测试全部继续通过。

## 实施顺序建议

先登记来源与隔离错误 + 补许可；再导入少量有明确版次的原典片段和本项目原创解释；随后实现检索过滤与校验；最后扩展详批模块。不上来整仓搬古籍。不能证明版本与权属的材料保留链接书目，不批量入库。
