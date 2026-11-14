# 领域与资料检索

> 按实际引擎快照定位领域字段，再经[知识来源门](../knowledge/README.md)核查允许的用途与条件。七政以当前所选口径的实际字段为准。

| 领域 | 八字信号 | 紫微信号 | 七政信号 |
|------|----------|----------|----------|
| 感情 | 日支及本命实际关系。问配偶对发展目标的支持时核 [R1](../docs/stage-and-spouse-models.md#八字主兼与局部配偶支持) | [D02/S01](../docs/approved-life-domains.md) 的本命夫妻宫与身宫主题。按问题核 [RC01/02](../docs/ziwei-case-judgments.md) 的沟通条件，或 [RL01–04](../docs/stage-and-spouse-models.md#紫微大限与本命关系) 各自适用的长期婚姻条件 | 按[实际获准面板](../docs/qizheng-rule-profiles.md)核相关事实及用途 |
| 父母与同住 | 按实际关系、居住目标和已准入条件核对 | 「爸妈」「长辈」涉及父母角色时用「父母」检索 D08，核本人如何接受支持和协商边界。「同住」「搬家」用「居住」检索 D06，核实际空间与安排。也问本人收束休息时另核 D07 | 按实际目标核已准入范围 |
| 事业与学习 | 依 [BJ01、BJ04、BJ06–08](../docs/conditional-judgment.md) 核实际目标需要的官印、表达或其他路径，以及所问运期 | 先读官禄实坐主星与做事方式。涉及对外接洽另核迁移。按实际目标与时间层核阶段规则、准入四化和[年度 RC03](../docs/ziwei-case-judgments.md) | 按[已登记的度主与宫主规则](../docs/qizheng-rule-profiles.md)核本命结构。该范围没有职业或近期成败判读 |
| 财务与资源安排 | 查实际财的透藏和生克对象，按 [BJ04](../docs/conditional-judgment.md) 比较它对同一目标的支持和成本。有实际食神候选时另查 [BZ-M02](../docs/approved-life-domains.md) | 财帛看资源安排，田宅按积累和实际居住目标查 D06。判断时期条件时按各自规则核实际阶段和年月分量。化禄可查投入与消耗 | 按[已登记的度主与宫主规则](../docs/qizheng-rule-profiles.md)核本命结构。该范围没有收支、借款或资产结果判读 |
| 健康与劳逸 | 依据用户提供的现实安排讨论劳逸 | 从 `ziwei.life_reading.domains` 查实际疾厄宫的 ZW-D04 身体管理主题。本人目标包含收束或休息时，查实际福德宫的 ZW-D07，核持续投入的代价 | 依据用户提供的现实安排讨论劳逸 |

健康走势与现实症状按[健康与现实症状](../docs/approved-life-domains.md#健康与现实症状)处理。疾厄或福德缺实际主星时，保留对应主题的缺口，继续按本题目标核其余适用依据及用户的任务、作息和恢复条件。

问指定年、月的感情互动或劳逸安排时，也按[紫微生活领域面板](../docs/ziwei-life-reading.md)逐候选、逐段核对与目标相关的主星四化分量。感情限本人互动和投入，劳逸限身体管理及收束休息。年／月分量用于日问时只作上层背景。

## 从口语问题定位登记词

保留用户原问，先确定关系角色和要完成的任务，再用下表的登记词查来源。口语词未命中时继续按对应的登记词和面板核查。

| 用户描述的实际任务 | 查询 profile 与登记词 | 核查范围 |
| --- | --- | --- |
| 事业、学习、做事方式、对外接洽 | `bazi-judgment-v1` 按 `BJ01`、`BJ04` 及对应运期的 `BJ06`、`BJ07` 或 `BJ08`。紫微 `ziwei-domain-conditional` 查 `官禄` 或 `迁移`，再查实际主星名 | 先核可用的本命条件。问明确年份的主动申请时，再查 `ziwei-judgment-cases-v1` 的 `ZW-RC03`。该判例退出后，继续查本题实际时间层及可用的做事方式、投入与代价 |
| 和工作搭档分工、复核或共同定稿 | 紫微 `ziwei-life-domains-v1` 查 `工作合作`（ZW-D03）。涉及本人日常沟通和交往边界时另查 `交友`（ZW-D05） | 按 D03 已登记的作者延伸，核本人在实际合作角色中的投入与代价。分别确认谁负责准备、复核、采纳及定稿。对方同时是伴侣时，按各项事务的实际角色分别核查 |
| 财运、钱和人手够不够、积累资源 | `bazi-judgment-v1` 查 `BJ04`，有食神候选时另在 `bazi-purpose-extensions-v1` 查 `BZ-M02`。紫微 `ziwei-domain-conditional` 查 `财帛`，涉及积累或居住时另在 `ziwei-life-domains-v1` 查 `ZW-D06` | 各自核所问的是如何调配资源、何处有代价，还是实际收支或融资结果。大限落财帛时，按该阶段分支的实际评价对象核对 |
| 和伴侣谈家务、照顾或睡前分工，或确认共同安排 | `ziwei-life-domains-v1` 查 `夫妻宫`（ZW-D02）。涉及年／月，再按夫妻宫准入的实际主星四化查 `化禄`、`化权`、`化科`、`化忌`。本命协商另查 `ziwei-judgment-cases-v1` 的 `协商` | RC01/02 分别核授权、共同认可及需求是否说清。实际主星的年／月分量可解释本人承担哪些已获授权的职责、何处增加投入或代价。协商判例未触发时，仍核适用的年／月分量。对方同意的事项和日期按实际约定。 |
| 已婚男性问和妻子能不能长久过日子、维持现有共同生活稳不稳 | `ziwei-stage-relationship-v1` 查 `ZW-RL01`。夫妻宫实坐廉贞天府、紫微天府或紫微天相时，按长期关系入口查对应人工条目 `ZW-RL02`、`ZW-RL03` 或 `ZW-RL04` | 按[长期关系入口](../docs/stage-and-spouse-models.md#紫微大限与本命关系)核实际星位、四正六曜和各自异读。紫微天相另核妻子较年少。RL01 未触发时继续查符合盘面的人工条目。共同安排是否可执行另核现实同意。 |
| 到点想收工、晚间想留休息时间、结束任务后还在反复想 | `ziwei-life-domains-v1`，`福德` | D07 核实际主星与持续投入对收束的成本。按本人明确的作息和偏好解释体感。 |
| 想安排活动量、休息间隔等一般身体管理 | `ziwei-life-domains-v1`，`疾厄` | D04 核实际宫位作一般生活反思。涉及实际症状时走[健康与现实症状](../docs/approved-life-domains.md#健康与现实症状)。 |

```sh
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-judgment-cases-v1 --term 协商
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-life-domains-v1 --term 夫妻宫
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-life-domains-v1 --term 化权
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-life-domains-v1 --term 福德
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-life-domains-v1 --term 疾厄
```

同一个问题同时涉及协商和休息时，分别说明表达或执行安排对共同认可的影响，以及继续投入对按时收束的代价。月度判断另核实际查询段的准入分量。出生候选的关系或休息证据不同，按各自成立范围回答。
