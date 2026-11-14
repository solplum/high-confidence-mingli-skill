# 紫微三项作用判例接口

`scripts/ziwei_case_judgments.py` 使用独立 profile `ziwei-judgment-cases-v1`、来源 `ziwei-judgment-cases-source`，只经 `reviewed_knowledge.load_profile` 加载 `ziwei-cases-ZW-RC01/02/03` 三张已批准卡。解释分支、条件、反条件、反例、时间边界和作者适配都从卡读取；不读取外部研究稿，也不把三项判例放进原有15张领域卡。

`ziwei_life_reading.analyze` 仅新增 `case_judgments`，既有 `profile/status/domains/modules/transformations/dynamic` 等键及原生字段逐值保持。`build_chart.py` 已有的 life 接入和独立 life CLI 因此自动包含新字段，无需新命令：

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/chart.json --dynamic /absolute/path/dynamic.json \
  --expected-target-date 2026-11-09 --expected-target-time-index 0
```

用本次请求的日期和时辰索引核对动态输入。错点缓存使依赖准入年层的 RC03 暂缓。参数说明见[生活领域面板接口](ziwei-life-reading.md)。

复用保存的点面板或汇总多个区间时，用[查询区间审计](ziwei-dynamic-facts.md#晚子时和区间覆盖)另核各段的 `annual_case_status`。只有该状态为 `verified` 且点面板的 RC03 实际命中时，才进入对应年度行动假说的人工复审。

查询区间审计另报 `annual_case_stage_precondition`。缺年层时，已核实走其他宫或尚未进入首限，均可说明本例的官禄前提未满足。已核正在官禄则只确认这一项前提，判例继续等待独立年层和本命背景复核。

`annual_case_yearly_precondition` 另核该点准入年禄、年权的实坐落点。任一未满足便可说明该假说为何退出。两项都满足时，仍要核实际官禄限、本命背景与现实申请条件。

Python接口：

```python
evaluate(existing_canonical_life_panel, root=None, input_errors=None)
```

输入是已生成的 `ziwei-life-domains-v1` 规范面板。调用入口用 `input_errors` 保存明确的出生时辰缺口或出生身份冲突。完整快照中已保存的民用输入、已解析排盘钟面及原生紫微输入如果明确冲突，先查看 `ziwei.life_reading.input_errors` 中的具体字段，再按更正后的输入重排。分析目标年冲突只限制相应时间层。helper复用已核十二宫事实、分层四化、准入年层及T02当前阶段，三方四正按实际本命地支列出。可用时间层和原始动态资料的权限见[准入合同](ziwei-dynamic-facts.md)。

## 精确谓词

| 判例 | 事实触发 | 条件方向的身份与边界 |
| --- | --- | --- |
| ZW-RC01 | 实际夫妻宫两颗实坐14主星分别附着固定本命权、忌 | 对双方有否决权、尚需形成共同认可安排的协商，研究要求升级带来局部摩擦的可撤回传统假说；已获共同认可或授权、实际表现相反可推翻个人化。 |
| ZW-RC02 | 实际夫妻宫巨门固定本命忌；再核天同是否实际同坐 | 天同同宫分支检查必要表达被压下的成本；无同宫天同不能启用该沉默机制。需求已经说清后少说可能减少重复争执，不能固定判阻。 |
| ZW-RC03 | 旧T02唯一实际当前大限为本命官禄；同一查询点的准入年禄、年权均直接附着本命官禄／迁移的实坐14主星 | 在实际申请对象存在、资格权限资源与可承受成本配套的分支中，研究主动申请或接洽的有限传统适配；不认定外部机会或成功已经增加。 |

RC01/02仅使用本命层，不用年/月权忌或别宫、对宫借星替代。RC03不从未来官禄阶段触发，不用只命中一化、月化或三方会照顶替严格直接落点；年层拒用或未请求时明确暂缓。查询点的公历年须与已核T02分析年及其当前半开年度窗一致，只做一致性比较，不重算年龄。

查询点、年层与 T02 年度均核对后，已确定尚未进入首个旧大限时，RC03 为 `not_triggered`，附首个年度窗起点。已超过最后一个已排年度窗时，RC03 为 `withheld`，附该窗的排除终点。时段与年度证据冲突时仍按各自缺口暂缓。

本命部分四化未核时，RC01 分别核实际权、忌，RC02 核实际巨门忌及天同实坐。确定的几何退出仍可报告。支持分支所需四化或原始亮度欠缺时只暂缓对应分支。RC03 需要保留完整本命四化背景，并通过独立年层门。

RC03保留三处作者适配：原文“会到”收窄为直接实坐，官／迁按本命宫名解释，旧公历年度大限合同与独立农历年层并用。旧年度窗不代表生日或春节精确交限。一个查询点不代表整年覆盖，跨公历年、春节年界或旧限窗口分别核查；年度行动例不扩到流月、流日或关系／健康方向。

## 输出与暂缓

`case_judgments.modules` 独立含三项：`checks/fact_match` 只表示事实谓词是否满足，`direction_branches` 保存有条件的传统方向研究材料，`selected_branch` 区分实际适用分支。`reality_status: not_observed_or_inferred` 明确没有从排盘观测实际行为。完整原始亮度、实际星表、各层四化、已批准主星主题和源路径保存在 `facts` 与相应 `context`；RC03还列出本命命宫及官禄宫三方四正、当前旧限年度窗及其合同身份。非主星仅保留既有事实，不新增性质或权重。

- `conditional`：事实满足，条件假说可研究；不表示个人行为已经发生、现实条件已经具备或整题已完成。
- `not_triggered`：已核事实不满足谓词；不倒推更顺、平稳或不利。
- `withheld`：来源、出生时辰、不确定时间、原输入错误或该项必要层存在缺口；保留具体原因。
- 顶层 `partial`：三项中部分明确暂缓，其他项仍按自身条件报告。

出生时间不确定、明确缺时和原输入错误限制新判例；缺年层只限制RC03，既有本命事实仍可保留。来源失败会明确列 `source_errors`；全目录来源校验仍沿用既有治理，新来源字节损坏也可能使旧life入口提前暂缓，不能声称此时仍有完整旧成功面板。对已经生成的规范面板，helper自身来源失败仅返回新组暂缓，不修改该输入面板。正常同输入下，新增字段之外的旧键逐值保持。所有结果都是独立对象。

出生误差已显式枚举时，按[出生误差候选接口](ziwei-life-reading.md#出生误差候选)逐候选运行静态命令，从结果的 `case_judgments` 比较 RC01/02。需要核 RC03 时，再为各候选提供相应的动态输入及本次查询点，核对准入年层、旧阶段年度窗与同一候选的全部事实条件。中心盘及无准入年层的候选继续暂缓。保存实际候选的 `birth_scenario` 与覆盖标记，结论随候选变化时分别交代。

全部条目的 `overall_direction` 保持 `withheld`：不相加、不抵消，不由两条局部阻力投票判关系净方向，也不由年禄权删除科忌或未核修饰。保留压力并存与现实约束的反条件，不给分合、升职、录用、收入等事件结论。这三项没有解决一般领域或跨层净方向能力。

验证使用明确合成A/B/C输入，重新调用原生包装器和现有动态适配器，测试精确正反谓词、缺时与不确定性、层身份、查询年绑定、来源失败、旧键逐值保持和CLI接入；产品测试不读外部研究或个人资料，也不验证现实预测能力：

```sh
python3 -m unittest discover -s tests -p 'test_ziwei_case_judgments.py' -v
python3 -m unittest discover -s tests -p 'test_ziwei_life_reading.py' -v
```
