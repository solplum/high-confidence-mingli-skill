# 紫微生活领域研究面板接口

`scripts/ziwei_life_reading.py` 使用标准库，输出 `ziwei-life-domains-v1` 的独立 `conditional_module_only` 底稿。它组织十二宫实际星表、现有十四主星有限主题、固定本命及已准入年月四化、身宫关注假说和旧年度大限议题，不判人格、事件、净吉凶或医学风险。卡片条件、排除、来源身份与引用随 JSON 保存。

`build_chart.py --format json` 在有紫微数据时仅新增 `ziwei.life_reading`。既有 `ziwei.chart`、`rule_output` 和无紫微时的 `ziwei: null` / `degradation.ziwei` 契约保持。该接入不改旧默认文字输出；独立面板可用完整 JSON 快照读取。

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/chart.json
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/chart.json --dynamic /absolute/path/dynamic.json \
  --expected-target-date 2026-11-09 --expected-target-time-index 0
```

快照缺少 `provenance.resolved_age_year` 时，须有 `input.analysis_year`、`input.age_year` 或 `provenance.analysis_year` 的明确记录，且所有已记录的分析年均与原生 `ziwei.input.ageYear` 一致，才可恢复旧大限年度索引。原民用出生年及原生当前年龄与大限索引照常核对。

证据账本引用含原排盘输入的总控原盘或派生字段时，用同一出生资料独立复盘。实际命身宫或星表与出生资料冲突时，相应紫微证据拒用。个别原始亮度或大限表与复盘冲突时，拒用相应原生字段，并按普通续算的范围核对依赖它的领域、关系和大限判断。仍可引用经独立复核的其他事实。缺少现代复盘元数据的旧档继续按留存证据核对。

使用静态太阳时快照时，核对已保存的出生时区、fold、固定偏移和出生瞬间，再用原经度与可用均时差核对排盘钟面。保存的 TZif 摘要与当前文件一致且有明确 fold 时，按该份时区规则复核实际 UTC 偏移。明确冲突时暂缓紫微个人判读，按修正的出生输入重新排盘。旧档仅缺辅助字段时使用实际留存的证据。明确采用民用时的旧档即使未保存派生钟面，也直接核对原 `input.solar` 与 `input.hour` 所对应的原盘日期和时辰。若明确保存的时区来源有冲突，仍可读取独立复盘的民用本命及公历阶段，实际出生瞬间和依赖其核查的动态续算须等原资料核实。

总控存档原来开启出生误差枚举时，续算会将已存 UTC 区间与原民用中心及误差分钟核对。留存非零区间但缺原误差分钟，或两份记录明确冲突时，中心星表可读，个人化主题与实际出生范围暂缓。请核实原误差分钟或按确认后的原资料重建，选读候选仍需完整的原始输入。嵌入的领域解读和候选对照副本不用于确认精度。

动态文件须为现有 `ziwei_dynamic_facts.mjs` 的完整输出。未传时为 `not_requested`，不会补查。解释事实仅消费 `admitted_dynamic_facts.layers.yearly/monthly`；日层、研究层、raw年龄、大限与小时均不进入解释。年月分别验证 schema/profile、实际同一本命星表、完整宫位关系、固定四化及实际本命附着，并绑定该层和各四化的 `raw_pointer`、流年地支与命坐标。错身份限制整个动态输入，错单层只拒用该层。目标农历年用于两层，农历月、日和闰月标记只用于月层。只缺这些月层字段时，能独立复核的流年和依赖该流年的已准判断继续核对。晚子时日层阻断不影响年月。结果只覆盖显式查询点，`full_interval_coverage: false`。

分析某一时点或分段时，将本次解析得到的公历日期与时辰索引一起传入两个 `--expected-target-*` 参数。日期采用 `YYYY-MM-DD`，索引取 0 至 12。期望值来自当前请求或本段选定的见证点，独立于待核的动态文件。日期或索引不一致时，`dynamic` 拒用该文件并列出实际值与期望值，本命与阶段底稿照常生成。两个参数都省略时，旧调用仍执行动态文件内部的一致性检查。单传一项或缺少动态输入是参数错误。

如果日期和索引代表的可能时刻无法证明全部在出生后，另传本次独立核实的带偏移钟面。动态适配器用 `--target-civil`，面板用同一查询的 `--expected-target-civil`。靠近出生边界的裸点保留本命与静态阶段表，动态和该查询点的当前大限标为出生时间未核。先核本次独立查询点的出生先后，再读动态文件内容；文件缺字段也不能让这个查询点的当前大限被当作已核。旧档缺出生时区时，可按已核日期与时辰的保守上界证明明显更晚的查询已经出生，近界仍保留缺口。

更正出生时间后，先用新静态面板和原查询区间重新核对出生先后。显式 `--expected-target-civil` 早于已核出生范围最晚边界时，单点命令报错且不输出面板。需要本命与静态阶段表时，省略动态文件及查询点参数单独运行。区间内确定出生后的部分用新起点续算，出生前或先后未核的部分只保留历法事实。见[区间复核](ziwei-dynamic-facts.md#晚子时和区间覆盖)。

为核对查询点与年／月来源的一致性，审计核对 `native_wrapper_snapshot.input` 的出生日期、时辰索引、性别、原民用出生年与目标公历年，再读取 `research_dynamic_iztro.raw_horoscope.solarDate`、`research_dynamic_iztro.calendar_observation.target_lunar/birth_lunar`、`research_dynamic_iztro.selected_fact_views.yearly/monthly`。核对原目标公历年／日期、农历年月与闰月十五／十六边界下的标签和落点，以及来源派生视图与准入事实的一致性。再将年、月的准入事实分别对照其指针所指原生层的命宫索引、干支、宫名和四化星名。查询日的农历边界由锁定版本的历法独立核对。原生字段用于核对，解释继续从 `admitted` 取事实；缺少查询身份元数据时拒用动态，单层来源缺失或冲突仅拒用该层，本命继续保留。raw 年龄、大限、流时、流日及流曜不参与审计或解释。

## 只确认民用日期和时辰

已核原公历民用生日及单个民用时辰时，用原生 `--shichen` 直接保存紫微离散输入。分钟未知，原记录仍写实际时辰及其范围。若日期、钟面口径或时辰归属有歧义，继续核对可达候选。

只知子时且出生日期已独立确认为按午夜划分的公历民用日期时，核对该日 00:00 至 01:00 前和 23:00 至次日 00:00 前的可达部分。现有紫微出生盘对同一民用日期的两段均用索引 0，可以直接用 `--shichen 子` 读共用的本命和年／月条件。只知道传统记法的日期和子时、尚未确认实际民用日期时，按可达日期分别核盘。八字在 23:00 另有换日，出生瞬间依赖的判断仍按各体系分别核查。

历史 IANA 时区或固定偏移已知时，在续算入口传入 `--timezone` 或 `--utc-offset`，核对该时辰的实际可达区间。时区尚未确认时，按已确认的民用日期与时辰读离散盘，UTC 区间保持未知。该日期或时辰无可达时段时，先核对原始记录与时区。

从技能根目录执行。示例为已确认公历生日、民用申时和分析年 2026 的合成盘。

```sh
(cd scripts/pai_pan_ziwei && node --import tsx pai_pan.ts \
  --solar 1987-05-27 --shichen 申 --sex 男 --age-year 2026 --format json) \
  > /absolute/path/ziwei-branch.json
```

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/ziwei-branch.json \
  --native-shichen 申 --birth-date 1987-05-27 --sex 男 --timezone Asia/Shanghai
```

续算参数取命主独立确认的资料。面板复核原生输入、实际星表和阶段表，输出 `birth_scenario` 记录已核时辰及范围。子时的两段民用钟面仍在 `clock_intervals`，已核时区时另给实际 `civil_spans`。出生时刻保持时辰精度。原始亮度、固定四化或大限局部冲突时，按各自证据暂缓依赖字段的判读。读本命、长期关系和公历年度大限可直接使用该命令。

需要年／月条件时，按[查询分段](ziwei-dynamic-facts.md#晚子时和区间覆盖)运行原动态入口。出生参数使用已核原生 `input.solar`、`shichenIndex`、`birthYear` 和已确认性别。给上述续算命令增加 `--dynamic` 及本段独立选定的 `--expected-target-date`、`--expected-target-time-index`。追问其他公历年的旧大限时，再传本次独立指定的 `--analysis-year`。八字另核区间内的四柱和起运，七政按其要求核出生瞬间精度。

## 已知民用出生钟面区间

同一公历民用出生日期和当天的钟面上下界已确认时，用本入口核对实际可达的紫微候选。区间仅落在一个时辰内时，仍保留已知的实际上下界，按一个候选继续核查。此入口支持 1901–2099 年的民用出生日期。起点包含，终点排除，`24:00` 只可作终点。先确认原始记录的边界含义。提供出生地 IANA 时区或当时明确的固定 UTC 偏移小时。日期或时段仍未知时按[建档入口](onboarding.md#时间不确定或未知)继续核实。

```sh
python3 scripts/ziwei_birth_time_candidates.py --birth-date 1988-10-18 \
  --start 13:00 --end 19:00 --sex 男 --analysis-year 2026 --timezone Asia/Shanghai \
  > /absolute/path/ziwei-birth-band.json
```

示例得到未、申、酉三个候选。每个 `candidates[]` 包含离散输入 `input`、可达 `civil_spans`、原生 `native` 和同一候选的 `life_reading`。 `life_reading.birth_scenario` 记录同一候选的区间和原盘位置。刚生成的本命面板可直接作为该候选的[区间复核参照](ziwei-dynamic-facts.md#晚子时和区间覆盖)。已有存档若缺这项身份记录，先通过下方的续算入口重新读取所选候选的静态面板。重叠钟面保留实际偏移和 fold，跳过的钟面无候选跨度。跨时区偏移的边界以 UTC 比较。两段子时落入同一民用日期和时辰索引时共用一个原生盘，各自跨度仍保留。出生时刻维持区间精度。阅读时按候选分别检查本命、长期关系和实际年度大限。只有完整覆盖全部可达候选，且逐一复核适用规则、必要条件和反向依据后仍得到相同方向时，才给共同判断。

问指定年／月的关系或劳逸时，按[查询分段](ziwei-dynamic-facts.md#晚子时和区间覆盖)取每段实际查询点。用同一候选 `input.solar_date`、`input.birth_year`、`input.shichen_index` 和 `input.sex` 生成动态文件。以下命令使用上例的未时候选和 11 月 9 日见证。

```sh
node scripts/ziwei_dynamic_facts.mjs --solar 1988-10-18 --birth-year 1988 \
  --shichen-index 7 --sex 男 --target-date 2026-11-09 --target-time-index 0 \
  --source-label confirmed-civil-band > /absolute/path/ziwei-band-7-dynamic.json
```

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/ziwei-birth-band.json \
  --ziwei-candidate ziwei-band-7 --dynamic /absolute/path/ziwei-band-7-dynamic.json \
  --expected-target-date 2026-11-09 --expected-target-time-index 0
```

先核存档顶层 `input` 与命主原确认的出生日期、钟面上下界、出生时区和分析年相符。已存的时区来源也须与原输入相容。旧档没有该来源时，仍按原输入复盘。面板从该输入重算全部可达候选的身份和区间，并用锁定引擎复盘所选原盘。输出 `birth_scenario` 保存所选 ID、实际跨度及原盘位置。动态文件的出生身份或查询点不符时，暂缓动态，保留已复盘的本命及阶段。只读本命和阶段时，省略动态文件和查询点参数即可。Python 使用同一 `analyze_snapshot(..., ziwei_candidate_id=...)` 入口。

旧区间档只缺身宫地支、农历注项、个别原始星曜亮度或固定本命四化标记时，按同一候选的完整复盘核对其余原生输入和原盘。已核大限及独立验证的年／月仍可使用，`dynamic.unverified_static_fields` 记录本次缺项。本命面板继续读取原档，依赖所缺字段的判断暂缓。静态参照若是缺少 `natal_stage_basis` 的旧面板，先用续算入口从原档重读静态面板，再核对个别亮度或本命四化缺项。若保存值与复盘明确冲突，或实际星位、大限、候选身份有差异，先重建原区间档。

所选旧区间候选只缺 `currentAge` 或 `currentDaXianIndex` 时，依同一候选的完整原生复盘继续读取本命和独立年／月。指定 `--analysis-year` 后，按[续算指定公历年](#续算指定公历年)在内存复核所缺重复字段，并核完整大限表和原有值。省略分析年时，该候选的当前阶段继续待核。原存档的缺项保留。

所选旧区间候选的 `daXians` 缺键或为 null 时，继续复核原出生身份、实际星表及独立年／月。原大限表未保存，T02 和依赖大限的 RC03 继续暂缓。已保存的表须完整并与同一候选的原生复盘相符。

用户确认缩窄整个出生区间后，若前后各自复盘到同一候选，且该候选的出生资料和实际跨度逐项一致，可继续用原候选的静态面板核查新点面板。两个 `chart_path` 分别指向各自档案中所选原盘的位置。所选候选的实际跨度变更时，用新范围重读静态和点面板。

按同样方式逐候选逐段执行。存档的候选集合、实际区间或所选原盘冲突时，按命主原确认的出生区间重跑。判断依赖旧当前大限时，使用该段公历年的原生盘。若某候选排盘或查询失败，保留它及相应缺口。八字和七政分别按自己的出生精度与计算合同处理。

## 出生误差候选

已用 `build_chart.py --enumerate-scenarios --uncertainty-minutes N --format json` 生成完整快照时，可以用 `--ziwei-candidate` 读取某个实际枚举候选。候选 ID 来自 `ziwei_scenario_comparison.candidates[].id`。本命领域主题、亲密协商的本命判例和旧大限用静态命令，读取该候选的 `domains`、`case_judgments` 与 `stage_relationship`。

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/chart.json \
  --ziwei-candidate ziwei-candidate-1
```

感情互动、劳逸等问题涉及具体年或月时，按[查询分段](ziwei-dynamic-facts.md#晚子时和区间覆盖)运行同一候选的动态入口。用该候选的 `input.solar_date`、`input.shichen_index`、`input.birth_year` 和原输入性别生成对应动态文件，再同时传入本段见证的日期与时辰索引。按 `transformations` 核与所问目标相关的准入年／月主星分量，另读本命主题。只存事实的分量按原状态保留。

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/chart.json \
  --ziwei-candidate ziwei-candidate-1 --dynamic /absolute/path/candidate-1-dynamic.json \
  --expected-target-date 2026-11-09 --expected-target-time-index 0
```

程序从原出生输入重跑枚举，核对全部见证、分段和候选编号。旧档缺派生 `time` 或 `time.civil` 时，原民用日期、时分、时区或固定偏移及必要的 fold 齐全才从原输入重算。仍保存的民用钟面、北京时间、时区、fold、命名时区来源或可核的太阳钟面如有冲突，须先核对原资料。民用时和平太阳时检查连续覆盖与闭合终点，并复核各段的紫微日期、时辰和原民用出生年。真太阳时复核原算法取得的数值见证，覆盖仍为非穷尽。所选见证另用锁定的本地紫微引擎复盘，核对农历记录、命身宫、实际星表及已存的五行局和紫微位置。旧盘缺失的亮度或四化依既有证据规则保留缺项。未知 ID、可达候选或分段缺失、身份或原盘内容冲突、无法复盘时，所选候选报错；先按原输入重建或补齐引擎。动态出生身份或查询点错配时，动态层暂缓，已复核的本命与阶段仍可读。输出的 `birth_scenario` 保存候选、证据位置与覆盖标记，所有判断限这个出生见证。

证据账本引用留有原枚举请求的候选原盘、阶段或关系字段时，也按原出生输入复盘所引候选。只引钟面见证时仍按其自身证据核对；排盘失败的候选保留降级记录。

旧原盘的重复字段 `chart.birthInfo.hour` 省略或为 null 时，先核所选见证的可达钟面，再用独立原生复盘核实同一时辰和实际星表。两者一致即可继续读取该候选的关系、大限及独立通过校验的年／月。动态面板记录该缺项，原存档仍保留原值。已存时辰与见证冲突、字段类型无效或缺少可核见证时，候选仍拒用。结论维持原候选的时间精度。

与同一建档的八字候选对照时，用 `birth_scenario.scenario_ids` 回指原枚举候选及见证。多个原候选可落入同一紫微盘，同一四柱也可能在午夜前后对应不同紫微日期。若八字结论依赖折月运段，另核原枚举候选区间与该折月段的实际交集。真太阳时按对应的已核见证说明。同组紫微盘可用于已核离散输入相同的其他见证，结论仍标明实际见证及数值覆盖。

民用时和平太阳时的总控候选另存为领域面板后，`birth_scenario.reachable_utc_intervals` 保存重算确认的各个实际出生窗，保留间隙、右端包含状态和单点，民用时另存每窗的有效 UTC 偏移。真太阳时只记录已核见证及非穷尽覆盖。旧面板的 `birth_time_bounds` 仅供出生与查询的先后排序。需要核对候选的实际覆盖时，从原档重新续算。区间复核所用的静态和逐点动态面板须从同一原档重生成，保留同一份出生候选记录。

## 续算指定公历年

追问某个公历年的大限时，传入本次独立确认的 `--analysis-year`。精确出生存档直接使用该参数。已确认民用时辰的原生盘同时传该入口所需出生参数。已确认出生钟面区间及已枚举误差的存档，同时指定所核候选 ID。以下命令用于只问大限的情况。

```sh
python3 scripts/ziwei_life_reading.py --snapshot /absolute/path/ziwei-birth-band.json \
  --ziwei-candidate ziwei-band-7 --analysis-year 2029
```

面板先核原出生与已存大限表，再用同一已核出生身份重排所问公历年。复盘核对原盘星位及大限表一致后，使用原生的目标年年龄、当前索引及标记。原存档可继续用于其他年份。按 `stage_query_scope` 核 `snapshot_analysis_year`、`requested_analysis_year` 和 `panel_analysis_year`。状态为 `verified` 时，再读 `current_status` 确认本次分析年处于哪步大限或已排范围之外。状态为 `withheld` 时，先核对所列原因，存档阶段只按自己的年份读取。

同时询问年／月时，使用 `--dynamic` 须成对传入本次独立确认的 `--expected-target-date` 和 `--expected-target-time-index`。预期日期与存档分析年相同时，已复核的原生当前大限可按该年使用，`stage_query_scope` 保留 `requested_analysis_year: null`。追问另一公历年或需要补核旧档缺失的当前大限重复字段时，须明确传入 `--analysis-year`。独立预期查询日期与面板分析年不一致时，`stage_query_scope.status` 标记 `analysis_year_mismatch`，`legacy_stage.current` 仍按面板分析年读取。按原年度窗查询的其他阶段、已核本命及各自通过校验的年月事实可继续使用。RC03 按本次查询的公历年与所用大限年核对。

Python API：

```python
analyze(native_chart, birth_year, analysis_year, dynamic_facts=None,
        temporal_uncertainty=False, root=None, *,
        expected_target_date=None, expected_target_time_index=None)
analyze_native_shichen(native_snapshot, birth_date, shichen, sex, dynamic_facts=None, root=None, *,
                       zone=None, utc_offset=None, expected_target_date=None,
                       expected_target_time_index=None, expected_target_civil=None, requested_analysis_year=None)
analyze_snapshot(complete_build_chart_json, dynamic_facts=None, root=None, *,
                 expected_target_date=None, expected_target_time_index=None, expected_target_civil=None,
                 ziwei_candidate_id=None, requested_analysis_year=None)
```

`native_chart` 指原 `ziwei.chart`，两个年份须显式给出；缺失值用 `None`。默认 `analyze_snapshot` 从原 `input.solar` 取民用出生年，并核对 `time.civil` 和原紫微输入年份。指定候选时取同一枚举的候选民用年。T02 核对原 `currentAge/currentDaXianIndex/daXians`，映射 `[出生年 + startAge - 1 年1月1日, 出生年 + endAge 年1月1日)` 半开年度窗，不生成生日或春节精确交限，不推补缺失 `siHua/stemName`。相关年缺失或冲突仅限制阶段/身份相关层，已有本命领域保留。

原 `input.solar` 沿用建档的公历日期解析。月份或日期省略前导零的已存记录，也按实际日历日期进行同一套核对。

重读精确钟点的快照时，从原输入重放所选出生钟面并用内置紫微引擎复盘。真太阳时有原 DUT1 时重算均时差。较旧记录缺换算依据时，可按保存的排盘钟面或原紫微日期、时辰索引和性别核盘，民用出生年仍以独立的原输入为准。复盘核对命身宫、实际星曜位置和已存农历字段，缺失的亮度、四化与大限重复字段沿用各自的处理。已存主星的原始亮度与复盘冲突时保留原值，标出冲突并暂缓依赖这项亮度的解释。原盘位置不一致、缺少可复盘的输入或本地引擎不可用时，暂缓该紫微面板并给出原因。只有大限五行局冲突时，单独暂缓依赖大限的判读。

原盘缺少身宫或部分农历字段时，如原出生身份和星位已独立复盘核实、动态附带的本命也与该复盘一致，可继续核验独立年／月层。缺项列在 `dynamic.unverified_static_fields`，原存档字段不回填。缺身宫只暂缓依赖身宫的主题，缺农历年干时本命固定四化继续暂缓，相应判例仍按各自条件处理。已存字段存在明确冲突，或动态附带本命与独立复盘不符时，动态仍拒用。

精确钟点、已确认民用时辰、已确认民用钟面区间或已核出生见证的旧原盘，若只缺重复标头 `chart.birthInfo` 或其中的年、月、日、时辰、性别，可按已核原出生输入及独立原生复盘补核。在内存用核实的标头继续处理本命条件判例、大限及独立准入的年／月，原档保留缺项。现有分量逐项与复盘比较，格式无效或任何明确冲突均须先重建原档。读取动态时，缺项仍列入 `dynamic.unverified_static_fields`。排盘钟面的日期与原民用出生年分别复核，大限仍沿用原民用年份。

宫位原盘保存了 `daXianAge` 或 `isCurrentDaXian` 时，T02 逐宫与 `daXians` 的年龄段及当前索引核对。再核原生十二个连续十年段是否从命宫开始，首段年龄是否符合已记录五行局，宫位顺序是否符合已记录的性别与出生农历年支。重读已存快照时，逐段核对保存的年龄范围和宫位是否与原生复盘一致，旧档缺少五行局或逐宫重复字段也照此复核。任一明确冲突均暂缓阶段与依赖当前大限的 RC03，已核本命领域、关系模型和独立年／月事实仍可使用。重读民用钟面区间候选时，逐宫大限重复字段也依此单独复核。缺少重复字段时读已经复核的原生大限表。重复字段冲突时暂缓阶段与 RC03，保留同一候选的已核本命和独立年／月。

核实的 T02 通过 `covered_window` 给出原表首末范围，`current_status` 区分当前在窗、尚未进入首窗、已超过末窗及未核。只有已验证的当前大限才能承担依赖当前阶段的判断。已核到窗外时保留现有各步及其范围，正文只在相应年龄内解释各阶段。

明确指定本次 `--analysis-year`，且原出生资料、原分析年及完整的十二步大限表均通过独立复核时，续算可在内存中重算旧档未保存的 `currentAge` 或 `currentDaXianIndex`。`stage_query_scope.replayed_current_fields` 列出这次重算的字段。原有值、逐宫年龄和当前标记仍逐项核对，原存档保持原值。大限表缺失或存有冲突时，阶段继续暂缓。

主要输出：

- `domains`：十二宫完整实际星表、领域角色、十四主星有限主题及反证问题；八个新域绑定 D 卡，旧四域复用原 profile。空宫无借星主题、亮度或四化。复用存档点面板时，按[分段复核](ziwei-dynamic-facts.md#晚子时和区间覆盖)检查原四宫的 `natal_four_palace_topic_status`。
- `modules`：15张 D/E/S/T 卡与其适用状态、来源条件、排除及引用。复用存档点面板时，按[分段复核](ziwei-dynamic-facts.md#晚子时和区间覆盖)检查所用 D 卡的 `natal_domain_topic_status`。状态说明材料可研究，不替代本题的人工比较与单独复审。
- `transformations`：本命及通过校验的年月四化分列。本命逐类核固定表和实际星表的唯一附着，`natal_transform_errors` 记录未核类别。有效分量可继续使用，缺失、重复或错附的类别保持未知。原星表中的四化标记保留作对照。非主星四化仅事实，E05 只对已核分量分组，并保留未知交互。年月仍按各自完整层准入。
- `dynamic`：未请求、准入、部分准入或拒用及具体原因；不读取日层证明其它时间范围。

`conditional` 表示可用的条件研究材料；`partial` 表示局部层有明确缺口；`withheld` 表示当前面板或节点暂缓。无紫微或来源门失败时不生成主题结论。CLI对完整暂缓输出退出1，格式/文件错误退出2，其余退出0；调用方应同时检查 JSON 中各节点的状态，退出0不表示个人问题已回答。所有函数均返回新对象，不修改原始面板或旧 K05 状态。

嵌套输入类型也按对应边界处理：`chart.lunarInfo`不是对象时仅暂缓本命四化，保留已核宫位星表；`snapshot.degradation`不是对象时API给出明确`ValueError`，CLI作为格式错误退出2，不输出异常堆栈。

验证：`python3 -m unittest discover -s tests -p 'test_ziwei_life_reading.py' -v`。测试验证数据、入口及边界，不验证现实预测效力。
