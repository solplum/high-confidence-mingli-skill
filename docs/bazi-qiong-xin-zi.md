# 十一月辛完整条件模型：程序入口

用户于2026-11-10批准的范围见[规则卡](../references/approved/bazi-qiong-xin-zi-v1.md)、[原页审计](bazi-qiong-xin-zi-sources.md)及[M0方法](model-judgment.md)。这是辛日、出生子月的独立整体／发展条件模型，不改原有格局、强弱、BZ-K、BJ面板或来源门。模型结果不表示现实预测效度已知。

`bazi_core_reading.analyze`新增`qiong_xin_zi_model`。它保存实际节点、来源、A/B条件、癸透反条、所选B与保守继承读法的差异。丙的直接同干藏根与全部同五行火藏根分别列出；后者是沿用项目结构口径，不冒称原书全部根义或已证有效。壬既透又藏只能进入A核查，不能转B绕过A的无戊窄门。没有完整正支不自动判差。

程序先检查实际条件和已编码的癸透特指反条，再返回`conditional_model_direction`；此字段是**待人工作用复审的机械条件模型结果**。`manual_review_completed`始终为`false`，`required_manual_review`保留来源适配、已有适用依据否定必要用途与同等反证的核查要求。交付者须先做这些核查，才能形成主结论；有据的阻断必须撤回、缩限或分支化，并保留原程序输出及修订依据。程序没有判定戊实际困壬、破根、合去、已救或任何未编码效力，不能说所有反条件已经排除。一般作用未决列在稳健性层，既非零影响，也不自动否定已匹配规则。

## 核本次目标的适用性

先按 [M0 的适用范围](model-judgment.md#何时使用)核本次原问。把实际评价对象记为 `requested_goal`。原问直接评价这个模型内的整体／发展条件时，记 `goal_applicability='applicable'`。具体业务路径、他人决定或事件结果需要各自依据，记 `not_applicable` 并继续查本题所需证据。目标或规则适用性尚未核清时记 `unverified`，先完成不受影响的核查。改问目标时重新核适用性，即使出生、时间和机械面板都相同。混合追问逐个目标核对。

## 只问大运或比较多个大运

比较同一个发展目标时，先保留每个出生见证的本命方向，再逐一比较所问范围内的原折月年龄窗。以下示例在技能根目录读取整张原运表，`snapshot` 为本次已核的总控或八字出生候选 JSON。`verified_natal_cores` 只含与本次出生输入独立核对的本命核心，没有则传空列表。`birth_luck_tables` 从原快照读取实际折月表及对应的出生核心。限定范围时，先对照原表按每个见证选出全部相交运窗，包括首尾只覆盖一部分的运。不要按预设的运序编号截取。正文归纳前，对照这些运窗补齐漏读的结果。

```python
import sys
sys.path.insert(0, 'scripts')
from bazi_qiong_xin_zi import evaluate_periods
from bazi_scenario_reading import birth_luck_tables

if goal_applicability != 'applicable':
    raise ValueError('先核本题目标是否适用 QX：' + requested_goal)
print('本次评价目标', requested_goal)
result = birth_luck_tables(snapshot)
if result['tables']:
    print(result['coverage'])
else:
    print('大运未核', result['coverage'])
    if 'natal_candidates' in result:
        natal_inputs = [(row['analysis'], row['birth_segments']) for row in result['natal_candidates']]
    elif 'natal_core' in result:
        natal_inputs = [(result['natal_core'], [])]
    else:
        natal_inputs = [(core, []) for core in verified_natal_cores]
    for core, birth_segments in natal_inputs:
        natal = evaluate_periods(core, [])['natal']
        print('本命', natal['scenario_id'], birth_segments, natal['conditional_model_direction'])
for table in result['tables']:
    print(table['source'], table['witness'], table['birth_segments'])
    natal = evaluate_periods(table['analysis'], [])['natal']
    print('本命', natal['scenario_id'], natal['conditional_model_direction'])
    for index, age_window in enumerate(table['windows']):
        start = age_window['start_months_inclusive']
        end = age_window['end_months_exclusive']
        window = f'原折月年龄 [{start}, {end}) 个月'
        if age_window['sequence'] == '起运前':
            print(window, '起运前，保留本命条件')
            continue
        luck = dict(layer='luck', pillar=age_window['pillar'],
                    source=f"{table['source']}[{index}]", window=window)
        panel = evaluate_periods(table['analysis'], [luck])['luck']
        details = [panel['conditional_model_direction']]
        branch = panel['matched_branch']
        if branch:
            details.extend(('条件支', branch))
        if branch == 'B_selected_graded_positive':
            alternative = panel['alternative_conservative_reading']
            details.extend(('保守读法', alternative['ordinary_positive'], alternative['reason']))
            if panel['observed']['wu_visible_ids']:
                details.extend(('戊透事实', panel['observed']['wu_visible_ids']))
        counter = panel.get('specific_gui_countercondition', {})
        if counter.get('status') == 'present':
            details.extend(('反条事实', counter['fact_ids']))
        print(window, luck['pillar'], *details)
    end = table['windows'][-1]['end_months_exclusive']
    print(f'原折月年龄 {end} 个月起超出本表')
```

只知民用生日时，先用 `bazi_scenario_reading.verified_date_candidates(snapshot)` 从原日期、性别和时区重排六字候选。把返回各候选的 `analysis` 用于上例的本命部分。按各自实际可达区间说明差异。时柱、折月表及据此判断的大运方向仍待核。

目标适用且只问某个已核折月年龄时，调用 `bazi_scenario_reading.luck_contexts_at_age(snapshot, folded_age_months)`。逐个取 `contexts`，先按上例核同一 `analysis` 的本命。`status` 为 `active` 时，用该项的 `luck` 续算大运；起运前、年龄未核或超表时保留已核本命，按 `status` 和 `age_table_range` 写明大运缺口。`contexts` 为空时，按上例读取可核的本命核心。各出生候选的折月年龄独立核实，有差异时分别取相符的 `witness`，保持候选与年龄配对。

已确认民用时辰或钟面区间的旧档若只缺 `dayun_age_comparison` 字段，`birth_luck_tables` 与 `luck_contexts_at_age` 可从原输入重排四柱和可达出生区间，在 `natal_candidates` 保留核过的本命候选。大运仍未核。已有折月表无效、或与原出生输入冲突时，回原输入重新建档。

总控快照已枚举出生误差且只缺 `scenarios.dayun_age_comparison` 时，同样在 `natal_candidates` 保留独立重放核对的各候选。先查原出生误差、完整枚举和存档核心四柱，再按候选输出本命与实际出生区间。真太阳时仍只保留已找到的 `witness_utc`，出生区间不能据此穷尽。大运及需要大运的方向继续未核。

总控旧档省略派生 `bazi_scenario_comparison` 时，先从原出生输入独立复跑枚举，并核对已存枚举声明、排盘钟面、全部见证、区间和已存折月表，再重建候选核心。保留原表时可按同一见证继续读日月和大运。原折月表也缺失时，仍只读取已核本命和历法事实。真太阳旧档无两处原 DUT1 记录时，沿[时间合同](time-contract.md#iana-历史时区与有界误差候选)用 0 近似复核留存见证。原枚举缺项、已有候选对照无效或复核发现冲突时，从原出生资料重新建档。

旧档缺派生本命核心时，从可核的原四柱重建：精确总控使用 `bazi.pillars`，枚举总控和独立民用候选使用对应候选的 `pillars`。按原输入复核出生钟面、候选范围和已有折月表，再读长期或日月方向。发现原四柱、见证或已有折月表冲突时，按原资料重建快照。候选的折月表也缺失时，按上面对应入口只读可核的本命和历法事实。

读取精确钟点的总控快照时，从原民用日期、时分、固定偏移或 IANA 区域及 fold 重新解析出生瞬间。旧档只缺派生的 `time` 记录或其中的钟面时，从完整原输入复算，并逐项核对已存时间字段、原四柱、性别与折月表。已存字段若与原输入冲突，按原资料核实后重建快照。真太阳时按原 DUT1 重算均时差。旧档可使用七政原地平计算记录中的 DUT1，两个记录都缺时保留大运未核。

精确钟点旧档保留原折月表，但本命核心与重复四柱字段都有缺失时，从已核出生钟面重排四柱，逐项核对仍在档内的柱及原折月表。重放一致后可继续选运。已存四柱冲突、参考时刻或无法重建原盘钟面的情况仍按各自缺口处理。

精确总控旧档缺原折月表或只留空表对象时，若原出生时刻、排盘口径和性别完整，`birth_luck_tables` 和 `luck_contexts_at_age` 在 `natal_core` 返回按原输入重排的本命核心。交接记录只保留总控的 `input` 对象也可重排。若还有已存出生钟面、四柱或核心，须与原输入相符。时辰确实未知或原输入不足时暂缓，留存字段明确冲突时回原资料重建。长线仍可读已核本命方向。日月续算默认使用该核心，保留出生后的实际历法事实与已经见到的反条。大运、起运及表尾位置和依赖大运的完整时段方向仍待核。

### 出生时刻有误差时比较大运

总控旧档原来开启出生误差枚举且仍有非零区间时，原误差分钟缺失或明确冲突须回原资料核对后重建。即使中心四柱可以单独重算，续算和备用本命核心也不能据此按唯一出生点选择大运。

在支持范围内用 `--enumerate-scenarios --uncertainty-minutes N` 建档。旧档缺派生的 `time` 或 `time.civil` 时，按原民用日期、时分、时区或固定偏移和适用的 fold 重建出生钟面。再复核原枚举覆盖、每条出生见证及其折月运表。已存民用钟面、民用偏移或出生瞬间与原输入冲突时先核实原输入。只确认民用时辰时用[四柱与起运候选入口](time-contract.md#已知民用时辰时的四柱与起运候选)。确认同日民用钟面上下界时用[出生钟面区间入口](time-contract.md#已知民用出生钟面区间)，把其完整 JSON 用作 `snapshot`。上面的示例按每个折月段的出生见证配对，即使四柱候选只有一个，也逐个保留不同起运表。没有可核的折月表时，`tables` 为空，按本次证据保留未核原因并继续核本命。

总控旧档仍显示非零出生范围，但原误差分钟缺失或与范围冲突时，先核实原出生精度。枚举档须按原输入复核中心钟面、范围、区间口径和候选见证，已有派生候选表也要复核。

用各候选的起止折月对齐所问年龄。分别保留会改变方向的交界，以及经完整候选覆盖和复审支持的共同区间。例如两组已复审的正支窗分别为 `[450, 570)` 和 `[451, 571)` 个月，共同正支只在 `[451, 570)`，两端各一个月需分别看候选。缺见证的段仍待核。真太阳时只报告已核见证。

折月表可核时，`birth_segments` 是同一四柱候选与原起运折月出生段的实际 UTC 交集。列表可有多个不相连片段；按每段 `end_inclusive` 读取右端，起止相等且含右端时只覆盖该时刻。旧字段 `birth_segment` 仅在交集为单片时给出该片。精确输入和真太阳时数值枚举的交集列表为空；前者按确认出生时刻，后者按非穷尽的 `witness` 表述。缺原折月表而可重排民用出生候选时，`birth_segments` 仅表示各自四柱对应的可达区间。长期和日月判断共用这组出生覆盖。

所选 B 分支匹配时，用 `alternative_conservative_reading` 核对 B 的保守异读。A 按自身条件复审。比较相邻大运时，方向相同但命中的条件支、保守读法或实质反条不同，正文仍交代交界处的变化。例如所选 B 在换运前后都相对有利，而下一运因实际戊透使保守正支不再成立。方向可以共述，异读和翻转条件按实际折月窗分别说明。`ordinary_positive_not_established` 只表示普通正支尚未建立，有已核癸透反条时另查受限分支。起运前单列本命与适用缺口，超出已排出的折月窗也标明覆盖边界。需要具体公历段时再核下一节的时间事实。

## 运、年、月、日的分层适配

`bazi_qiong_xin_zi.evaluate_query_segment` 从原快照为本次查询即时选取大运。先按用户所问时间和层级冻结查询，用[事实入口](time-contract.md#八字查询时段事实)取得实际分段。每段单独传入本次确认的 `expected_window` 与 `expected_layer`，并核对 `request_segment` 属于该查询。期望起止从本次查询的分段计划取得，缓存事实另行传入。日层还核对相同物理时段下的民用偏移。若同一历法段内跨过已独立核实的大运年龄边界，按该边界再分段，每段分别传它实际适用的年龄。IANA 查询沿各段的实际偏移传入窗口。缺少可靠大运事实时保留未知，适用窗口与出生候选须和本命分析一致。 已核原出生范围时，个人时段续算只取各已选候选确定出生后的区间。若请求早于出生或跨进出生范围，按实际出生后的分段重读。出生前的历法事实可单独查询。

同一查询段内各出生见证的折月年龄不同时，逐见证传入年龄与 `expected_birth_witness`。见证取同一快照的 `birth_luck_tables(snapshot)['tables']` 中实际对应的 `witness`，完整保留 `scenario_id` 和 `witness_utc`。即使四柱候选 ID 相同，UTC 见证也可能不同。该见证年龄未核时传 `None`。指定的见证须唯一匹配已核原表。来源缺失或见证不匹配时按同一出生输入核查快照。

只有民用生日的六字快照时，续算入口默认复核并读取整日可达的三柱候选，保留各自的 `birth_segments`、未知时柱和未核大运。若只分析其中一个已核候选，可提供对应的 `verified_natal_cores`。检查 `natal_candidate_coverage` 的 `read` 与 `unread`。候选 ID 在不同快照可能相同，须同时核对应三柱。

已知民用时辰或钟面区间的旧档只缺折月表时，同样按各自可达出生区间读重排四柱，`luck_status` 为 `birth_luck_unverified`。年、月、日柱及其已见反条事实照常复核。依赖大运的完整时段方向暂缓。这里的 `unread_by_birth` 按候选 ID 列出，`witness_utc` 留空。

只问一条已经独立限定的出生见证时，可直接传 `expected_birth_witness`。`coverage` 仍记录原出生输入的覆盖方式，`witness_coverage` 列本次读过的 `read` 和其余实际可用的 `unread`。`scope` 分别标明选定见证、全部可用见证或本次无候选见证。已读见证仍要看各自的 `luck_status`，例如本次已读而折月年龄未核。只把已核判断用于对应见证。真太阳时即使已读全部实际数值见证，覆盖仍为非穷尽。

```python
from bazi_qiong_xin_zi import audit_query_range, evaluate_query_segment
from bazi_scenario_reading import birth_luck_tables

# expected_window 是本次独立确认的带偏移 [起点, 终点)；expected_layer 取用户所问的 year/month/day。
# request_segment 是历法事实入口输出的对应分段。
# witness_ages 由调用方传入本段已核的 {(scenario_id, witness_utc): age}。
# 精确出生或全部见证确实共用同一年龄时，调用方传 None，并设置 folded_age_months。
# 多个见证尚无独立年龄证据时传空字典；个别缺项的见证也按年龄未核读取。
if goal_applicability == 'applicable':
    if witness_ages is None:
        age_witness_pairs = [(folded_age_months, None)]
    else:
        witnesses = {}
        for table in birth_luck_tables(snapshot)['tables']:
            witness = table['witness']
            if witness is not None:
                witnesses[witness['scenario_id'], witness['witness_utc']] = witness
        if witness_ages.keys() - witnesses.keys():
            raise ValueError('折月年龄所用的出生见证与本次原快照不符')
        age_witness_pairs = [(witness_ages.get(key), witness) for key, witness in witnesses.items()]
        if not age_witness_pairs:
            age_witness_pairs = [(None, None)]
else:
    goal_notes = {
        'not_applicable': 'QX方向超出本题范围，核本题路径的独立依据',
        'unverified': 'QX适用性待核，先核本题目标及规则用途',
    }
    print(expected_window, requested_goal, goal_notes[goal_applicability])
    age_witness_pairs = []
# verified_natal_cores 只含本次已独立核对并与查询相符的本命候选；没有则传空列表。
background_layer = {'year': 'luck', 'month': 'year', 'day': 'month'}[expected_layer]
current_prefix = f'temporal.{expected_layer}.'
luck_notes = {
    'age_unknown': '本段折月年龄未核',
    'before_major_luck': '本段处于起运前',
    'outside_luck_windows': '本段超出原生大运表',
}
query_segment_evaluations = []
for age, witness in age_witness_pairs:
    result = evaluate_query_segment(snapshot, request_segment, age, expected_window=expected_window,
                                    expected_layer=expected_layer, expected_birth_witness=witness,
                                    verified_natal_cores=verified_natal_cores)
    query_segment_evaluations.append(result)
    window = result['window']
    if not result['readings'] or result['readings'][0]['luck_status'] == 'birth_luck_unverified':
        print(window, requested_goal, '大运未核', result['coverage'])
    for reading in result['readings']:
        panels = reading['panels']
        panel = panels[expected_layer]
        background = panels[background_layer]
        print(window, requested_goal, panel['scenario_id'], reading['witness'],
              reading['birth_segments'], panel['conditional_model_direction'])
        print('上层方向及分支', background_layer, background['conditional_model_direction'],
              background['matched_branch'])
        print('本层干支及分支', panel['temporal_facts'][-1]['pillar'], panel['matched_branch'])
        for condition, ids in panel.get('observed', {}).items():
            inherited = [fact_id for fact_id in ids if not fact_id.startswith(current_prefix)]
            added = [fact_id for fact_id in ids if fact_id.startswith(current_prefix)]
            if inherited or added:
                print('模型事实', condition, '本命及上层', inherited, '本层新增', added)
        if panel['matched_branch'] == 'B_selected_graded_positive':
            print('保守读法', panel['alternative_conservative_reading']['reason'])
        counter = panel.get('specific_gui_countercondition', {})
        if counter.get('status') == 'present':
            print('已见反条的事实条件', counter['source_rule'], counter['fact_ids'],
                  '上层反条状态', background.get('specific_gui_countercondition', {}).get('status'))
        note = luck_notes.get(reading['luck_status'])
        if note:
            bounds = reading['age_window'] or reading['age_table_range']
            print(note, f"原折月范围 [{bounds['start_months_inclusive']}, {bounds['end_months_exclusive']})")
        if panel['status'] == 'withheld':
            print('待核条件', panel.get('incomplete_reasons', []), panel.get('source_errors', []))
```

汇总整段时，把每次得到的 `query_segment_evaluations` 合入列表。用 `audit_query_range(calendar_plan, query_evaluations, snapshot=snapshot, expected_request=expected_request, verified_natal_cores=verified_natal_cores, verified_folded_ages=verified_folded_ages)` 核对本次原出生快照、已读时段和独立年龄证据。把本次独立确认的 `start`、`end`、`layer` 和适用的 `timezone`、`start_fold`、`end_fold` 保存为 `expected_request`，字段取原请求或按原请求解析的值。审计按事实命令的同一口径解析并核对存档的范围。旧计划起止、时间层或时区不符时，用原请求重建完整计划，再保留能通过复核的已读分段。`calendar_plan` 是按本次原请求的起止、时区与层级独立生成的完整 `bazi_period_facts.py` 输出。审计先从这些请求参数重建历法分段，按实际干支和证据窗核查每段。即使存档分段漏行，对应时窗仍会列在 `unread_windows`。按已核大运切出的子窗可合并检查，IANA 回拨造成的日期成员间隙按实际民用日期保留。缺少原快照的旧调用只能核时间覆盖。

旧计划只缺派生字段 `time_basis` 时，审计可用原起止与固定偏移或已知 IANA 时区重建完整历法分段。固定偏移、IANA 日期和 IANA 钟面计划都核对已存的时区来源，即使只是同日短窗。固定偏移计划若带有 IANA 时区名称或地区时区来源，须按原请求重建。原查询缺端点或已有口径字段无效时同样重建。只存分段的早期格式，覆盖结果限于实际传入的分段。

IANA 日期计划保留 `civil_dates` 时，按原日期和时区重算，核对顶层实际起止、已存时区来源、留存边界及分段范围。部分分段遗失时仍可重算，已存字段冲突时按原请求重建计划。

旧 IANA 日期计划遗失 `civil_dates` 时，按独立确认的原日期请求重建，并核对留存的起止、边界和分段。原请求无法独立确认时，留存的 `civil_date_membership_gap` 须与原时区重算的全部日期间隙相符，才能恢复日期成员范围。回拨穿插的其他民用日期仍在该查询范围之外。同一组起止同时对应有间隙的日期范围和连续钟面范围时，按已核原请求或能区分两者的留存边界与分段核查。留存证据还不足以区分范围时，先核原请求。

精确出生的续算记录保存 `birth_instant_utc`。更正出生分钟后，即使四柱和折月大运表相同，也按更正后的出生重核折月与交运切点，重跑受影响的续算。旧记录已用折月年龄查询精确大运表，但缺原出生瞬间时，按本次出生与独立核实的折月年龄重新续算。未用折月年龄查表的旧记录仍可核其可读事实。

首次续算或沿用旧结果，都把本次独立核对的折月年龄另外传给 `verified_folded_ages`。用 `(年龄证据起点, 年龄证据终点, 候选 ID, 见证 UTC)` 为键，起止用带偏移的 `datetime`，年龄用非负整数，未核用 `None`。精确出生且无候选编号时，后两项均用 `None`。只有三柱的日期候选使用其候选 ID，见证 UTC 用 `None`。遇到夏令时回拨，同名钟面用实际偏移或转成 UTC 后再作为字典键。对每个已读窗口，核同一出生见证的年龄证据能否用同一个年龄完整覆盖。节气或换日把原证据切成历法子段时，各子段可沿用完整覆盖它的年龄。相接或重叠且年龄相同的证据可合用。已核年龄变化时按实际界点分开读，跨已核切点的面板会指出需要重读的位置。证据有缺口时补核，未核证据只支持同范围内年龄未知的面板。

`folded_age_evidence_checked=true` 表示已读窗口经过本次独立年龄证据的比对，可能包含明确未核的 `None`。逐窗查实际年龄与 `luck_status` 才能知道大运是否可用。未传年龄证据或没有读到窗口时为 `false`，即使 `unread_windows` 为空也不能据此确认折月年龄。

同一见证的重叠物理时段须给出一致年龄或一致的未核状态。同一见证的已知年龄随实际时间不能倒退，中间有未核时段也分别保留并核对前后已知年龄。不同见证各自核对。交运界点未核时保留未知，并在单独的条件记录比较两步大运。发现缺项或冲突时按本次证据重算受影响的窗口。省略该参数仍可重放出生与历法事实，所用年龄则来自待核记录。

同一出生见证两边已核月龄，且前段终点到后段起点的 UTC 实际间隔不足一天时，月龄最多前进一个月。连续多个短段也要核对累计变化。中间未读或月龄未知的时段保持缺口；发现多月跳变时，回查是否带入了另一日期的月龄。准确的折月年龄和交运时刻仍须独立核实。

有原快照和多个出生候选时，未指定见证的 `unread_windows` 只列所有见证均未读的时段。另查 `unread_by_birth`，它按候选 ID 和 UTC 列出各见证尚未读取的时段，只有三柱的日期候选只按 ID。归纳早晚或月内变化前，核同一出生候选的相应时段。真太阳时仍只代表实际生成的见证。已读范围只表示有面板可查，规则适用性及结论仍须复审。无可读本命核心的时段列为未读。

缺折月表或只有三柱时，若不同窗口分别保存了所读的本命候选，可把本次独立核过的核心合在 `verified_natal_cores` 一并传入。审计按每份面板记录的候选范围逐窗重放，再从 `unread_by_birth` 看同一候选缺哪些时段。

追问已独立选定同一原快照中的一个出生见证时，把该见证的 `scenario_id` 和 `witness_utc` 作为 `expected_birth_witness` 同时传给续算和 `audit_query_range`。审计的 `unread_windows` 和 `unread_by_birth` 都按这一个见证计算。可复用通过原档复核的多见证旧结果，本次独立折月年龄可只提交该见证。若旧结果只读了其他见证，本次时段仍未读。只指定见证用于条件比较时，继续说明原出生时刻的不确定性。

有原出生快照但未传独立年龄表时，审计仍按上述时序核同一见证的已读面板年龄。发现冲突时，先核交运边界并重跑相关窗口。交运仍未核时，将相关时段的大运记为未知。各步大运的备选解读可在复审记录中分别保存。仅通过这项检查仍须独立确认实际年龄。

正文按实际分段说明能否判断所问方向。年龄未核、处于起运前、超过原表覆盖和出生运表本身缺证分别说明。大运未能用于完整判断时，已看见的反条事实仍可解释，例如某节气后出现本模型的癸透反条条件。该事实提示这一段须复核相应制约，完整模型结论继续待核。

复审本层归因时，逐见证比较相邻上层与本层的方向、`matched_branch` 和 `specific_gui_countercondition`，核本层新增事实是否补足必要条件、使正支条件退出或触发特指反条。若壬原先只藏、本层新增壬透，就改核 A。原局或上层已有戊透时，指出戊来自哪一层，以及 A 的无戊条件未满足。只有另有已核的受限依据时才给负向。上层已匹配、本层缺少独立方向依据时，写明累计方向沿用哪层背景，以及本层实际查到的事实和方向缺口。多个时段累计同向时，仍保留各段方向成立的条件。新增事实的出现仅用于定位复审，具体作用按已登记规则核对。

旧调用可省略期望窗口和层级，沿用传入事实的起止与层级自行核验。使用这种方式时，调用者须先确认事实属于本次查询。

入口按每个出生见证复核原生四柱、运表和起运顺逆，并从原出生输入重跑候选，检查折月段与见证是否齐全。同时核对十一月辛和主兼／配偶面板是否保留原输入的时间精度及候选身份。遇到缺段、漏候选、区间或时间场景不符，重新生成整份出生快照。真太阳时的复跑只核对原算法可取得的数值见证，覆盖仍为非穷尽。使用总控枚举时，也核对原枚举保存的紫微日期与时辰身份，以保留正确的场景回指。年龄未知、起运前和超出表各有独立状态，保持大运值未知。

非六字快照没有可核运表且未指定出生见证时，仍可用独立核对的 `verified_natal_cores` 按大运未知续算。入口仍用原民用出生时刻和已知误差核对查询是否全在出生后。能重建原排盘钟面时，核中心或精确核心的已知四柱。旧档缺少可核出生时刻时标记 `birth_time_unverified`。无法重建原排盘钟面，或外部候选没有与原出生范围配对的见证时，标记 `birth_core_unverified`。这两种情况的面板只供内部核对，个人时段留在 `unread_windows`，补齐原资料后按原见证重跑。既无法从原档独立核回本命核心，且无另行核对的核心时，`readings` 为空。

每行须有`layer/pillar/source/window`。`pillar=None`保留未知层，它会阻断依赖全集合“未透癸／壬”的正支。层重复、跳过、无来源窗口、非六十甲子干支均明确报错。标准的带偏移 ISO 半开窗口须存在共同时间，已有文字窗口由调用者按原方法核对。

底层 `evaluate_periods(core_analysis, rows, expected_window=...)`保留给手工已核的分层匹配。期望窗口用本次查询的带偏移 `[起点, 终点)`，缓存另行核对。已知年月日需覆盖整个分段，已知日层还须与查询采用同一民用偏移。即使对应同一物理瞬间，偏移不同也可能跨民用 23 时换日。底层的期望窗口只核对日历时段，大运折月窗须由调用者另核。普通查询使用上面的入口按本次年龄重新选运。

绑定查询后，程序复用原时段事实入口，确认每个已知年月日干支在整个查询分段内相同且与输入一致。遇到该层实际换界，按原分段重算。只核年层可跨换月或换日，只核月层可跨换日。原标记为未知的层继续未知。

输入核心须带当前本命模型及明确出生场景。续算前用原引擎核对已知柱的干支分解、十神和藏干，再核模型与核心的原四柱、缺柱及已有候选场景元数据。本次复审使用从已核四柱重建的本命冲合、刑害与齐字事实。已标明未知时柱的三柱核心可继续提供已知事实。出生候选发生错配时，取正确候选的完整核心再运行。调用者继续负责验证各层实际来源、窗口和所判区间的覆盖。

大运取[原折月年龄窗](time-contract.md#八字大运年龄)和同一出生候选的干支。出生误差已枚举时，按 `scenarios.dayun_age_comparison.segments[].birth_witnesses` 配对四柱和起运窗。同一四柱的多个折月候选分别续算。查询靠近模型交运而无法唯一定位时，分别运行相邻大运，保留各自结果；也可将大运设为未知，仍使用实际已核的年、月、日事实。

返回`natal/luck/year/month/day`中已提供的各层；每层都纳入本命和全部先前层。月层不读某个任意日干，日层不能删掉上层壬透来绕过A。各层的出生子月与原局透藏保持原样，来字另列`temporal_facts`、节点和BJ06/07/08作者时间适配身份。本命未匹配而运年补丙透，只能说动态适配分支匹配。

程序保留本命冲合事实，但不自动补出或裁决时间来字的全部交互；调用者仍须按实际来字、有效窗口核查关系和作用。`full_interval_coverage`始终为`false`：单点或调用者写入一个窗口，不代表已经遍历整个区间。今日需覆盖既定23时换日等实际边界，今月需覆盖节气换月；月层结论不代表每个流日均同向。任何窗口的必要事实、特指反条或有据阻断改变时须重新核查。

缺时或未标明具体见证候选的出生时间误差输入，只保留已知条件和反条，不输出全输入唯一模型方向。若四柱完整且以非空`scenario_id`明确标出当前候选，时间区间尚未唯一也可取得该候选的条件模型方向；`status=conditional_candidate_requires_manual_review`、`unique_input_result=false`、`interval_stability_assessed=false`明确限制其范围。逐候选仍可人工分析，不能把某候选结果提升为全区间稳定；原场景比较的`stable_evidence`合同不变。

文本底稿先说明暂缓的具体原因。当前已知字段若有足以命中癸透反条的丙透、火根和癸透，另列此事实及其候选范围，整体模型方向继续暂缓。

独立helper的来源失败显式`withheld`；正常入口仍执行全目录fail-closed来源门，不能跳过损坏新来源保住旧面板。无对应现实真值，不报告准确率；现实不符不能事后推定隐藏根失效来保住原判。
