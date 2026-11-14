# 大限推进、八字主兼与配偶条件

按所问对象使用已获准的具体分支。先核盘面、规则、反条与竞争解释，按 [M0](model-judgment.md) 同时报条件结果和稳健性。配偶支持、婚姻稳定、阶段事务推进各自需要相应条件。

## 紫微大限与本命关系

查询 `ziwei-stage-relationship-v1`，读取 `ziwei.life_reading.stage_relationship` 和[逐卡条件](../references/approved/ziwei-stage-relationship-v1.md)。记录只允许 `conditional_module_only`，来源是[馆藏明刊影像](ziwei-stage-relationship-sources.md)的项目释义。

- **大限**。按用户所问的公历年或区间，在 `stages[].legacy_stage.window` 选对应旧年度窗。问当前大限时另核 `legacy_stage.current`。`stage_status` 汇总可用分支的匹配状态，当前方向须从选定行的 `modules` 查。逐条核 `selected_branch`、`direction_branches`、`actual_major_facts`、`context` 与原宫星表，引用 `cards` 中对应规则的出处、选读及适用范围。对未匹配的阶段保留实际议题及方向缺口。
- **阶段方向**。天府基础事务进展、天梁求谋、天同筹办新安排等方向各自保留对象。贪狼实坐庙限提供事务协调分支，破军子午实坐原始庙且四正无指定四曜提供明确任务的资源支持分支。整首合读的异读及撤评条件见各卡。武曲权的正支只答非官务、非财务求谋，即使当前宫名是财帛也按实际目标审查。太阴丑庙仅给已核正支，反背未决时保留净方向缺口；巳陷同宫火星只留反因素。天相遇同宫擎羊可给一般阶段受扰，`overall_direction` 保留未裁表示仍未汇总该阶段所有领域或分支。
- **异读**。太阳的固定本命忌、武曲的固定本命权，以及天同亥庙句读和午陷冲限的时间选读，都在各卡附有会改变结果的异读。明确用户看到的条件性结果在哪一种读法下成立，以及换读法时正评或受限评会如何改变。
- **必要事实缺失时**。按具体分支检查实坐、原始亮度、所需本命四化，以及四正或指定宫位的实际煞曜。可独立核实的四化照常使用。缺原始亮度或待核煞曜会限制依赖它的判断，已有事实足以确定退出时仍报告退出。保留未核项及实际星表。
- **长期关系**。在 `relationship` 读取 RL01 本命夫妻宫实坐阳巨和四正星表。地空、地劫与其他空曜各按实际身份保存。此支给长期婚姻稳定配置，异读可能要求核相对年龄；匹配与否均独立于当前大限。遇反曜或两星不实坐时退出这条正支，回到其他已准关系证据。
- **范围**。继承旧公历年龄与年度窗。阶段宫名只作议题背景；完整年、月、日方向、婚期、外部机会和实际事件各需独立依据。

出生时刻有误差时，以 `--format json --enumerate-scenarios --uncertainty-minutes N` 获取 `ziwei_scenario_comparison`。按[出生误差候选接口](ziwei-life-reading.md#出生误差候选)逐候选运行静态命令，读取本候选的 `stage_relationship`，用 `birth_scenario` 回指原生盘及 `scenarios.variants` 的见证和区间。相同紫微日期、时辰及民用出生年只排一次。某候选未排出或缺适用规则时，说明哪一段或哪一场景待定。仅当已核候选的相关条件一致、离散输入覆盖完整时，才写这些场景下的共同判断。真太阳时候选仅为数值见证，中心盘也只代表中心输入。

已确认原民用生日和单个时辰时，按[时辰复盘入口](ziwei-life-reading.md#只确认民用日期和时辰)读取 `stage_relationship`。确认同日民用钟面区间时，按[区间候选入口](ziwei-life-reading.md#已知民用出生钟面区间)逐候选复盘。追问某年当前大限时，用本次的 `--analysis-year` 及 `stage_query_scope` 核对所用大限年。

已婚男性询问与妻子长期维持共同生活时，按实际夫妻宫实坐组合查相应人工条目。RL01 未触发时继续检查符合盘面的条目。

| 实坐组合 | 查询 profile | 需核条件与异读 |
| --- | --- | --- |
| [ZW-RL02 廉贞天府](../references/approved/ziwei-lianfu-marriage-v1.md) | `ziwei-lianfu-marriage-v1` | 核四正六曜，复审性情条异读。 |
| [ZW-RL03 紫微天府](../references/approved/ziwei-zifu-marriage-v1.md) | `ziwei-zifu-marriage-v1` | 核四正六曜，复审相邻婚配时机合读。 |
| [ZW-RL04 紫微天相](../references/approved/ziwei-zixiang-marriage-v1.md) | `ziwei-zixiang-marriage-v1` | 妻子较年少须有现实资料，核四正六曜，复审绝对年龄、年龄所指角色、亲缘与邻句入庙的合读。 |

逐出生候选核实坐、六曜实际位置及各条退出条件。关系角色、实际协商、同意与履行各按用户事实确认。

若问题是亲密关系中的协商或表达，按同一候选的 [`case_judgments`](ziwei-case-judgments.md#输出与暂缓) 核 RC01/02，和长期关系的本命配置分别答。

## 八字主兼与局部配偶支持

查询 `bazi-primary-spouse-v1`，核对[逐卡条件](../references/approved/bazi-primary-spouse-v1.md)。来源是[1926年固定影像](bazi-primary-spouse-sources.md)的项目释义，同样按 `conditional_module_only` 记录。按本次已核出生输入和钟面选择面板。

- **精确出生钟点**读取总控 JSON 的 `bazi_core_reading.primary_spouse`。
- **出生钟点有误差**用总控 `--enumerate-scenarios --uncertainty-minutes N --format json` 取得实际候选。逐个读取 `bazi_scenario_comparison.candidates[].analysis.primary_spouse`，用候选 ID 回指原出生枚举与见证。顶层 `bazi_core_reading.primary_spouse` 的 `central_reference_only` 范围只覆盖中心盘。例如中心有偏财而退出时，另核各候选是否也有该条件。候选未能生成时，保留已核稳定事实并说明哪些条件仍缺边界对照。
- **只确认民用生日**使用[六字候选入口](time-contract.md#只有民用出生日期时的六字候选)。另确认一个民用时辰时用[时辰候选入口](time-contract.md#已知民用时辰时的四柱与起运候选)。逐个读取 `candidates[].analysis.primary_spouse`。缺时柱的候选保留已见事实与反条，完整财星筛查按缺项处理。
- **确认同日民用钟面区间**使用[区间候选入口](time-contract.md#已知民用出生钟面区间)。逐个读取 `candidates[].analysis.primary_spouse`，把财星筛查和官用核查限定在各自可达的出生段。

- **P1 主兼**。乙日申月、壬戊实透且有现行庚官候选时，给源模型内的官主印兼、财参与生官。先保留全部原候选和原选中值，再复核实际生克、必要用途否定及稳健性。此结果只回答局部主兼；印还在参与，戊与壬的柱序不作为额外前提。
- **R1 配偶支持**。先明确男性命主所问的配偶角色和具体发展目标。用现行已准方法独立建立可反驳的普通官用 H1，再核本命唯一正财透、无偏财混透，以及印轻财露、食伤透杀逢财与其他必要用途反条。面板保留事实和人工核查要求；官候选、P1匹配和财星筛查均不能代替 H1。食伤反条不要求食伤本身外透；妻宫另证有用和日支无冲也不是此支必要条件。
- **交付**。H1与反条核齐后，给既定发展目标上的配偶支持配置，写明稳健性和撤回条件。H1撤回即重判下游。具体配偶行为、现实关系稳定和时期事件需要各自依据。候选时刻分开判断，除非各可达候选已逐一核对，否则不报告稳定。

同一 `build_chart.py --format json` 入口包含两盘证据。完整解读在对话交付，研究记录回指原生字段、登记卡、解释对象和复审结果。
