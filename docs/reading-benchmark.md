# 八字与紫微的外部案例评测

此流程用于维护者检查技能，不是日常论命入口。真实赛事案例与答案保存在技能仓库之外，不进入 `knowledge/`、`references/` 或用户画像。合成盘继续用于排盘、规则和边界回归；两种结果分别报告。

## 来源与可用性

当前适配 [fate-bench](https://github.com/shunshi-ai/fate-bench) 的 `data/hkjfma_qa.json`。使用固定 revision 和原始文件 SHA-256，保存编纂许可与底层来源说明。本地研究可读取公开编纂材料；本项目不随包分发原题、答案或出生记录。编纂者的许可不替代底层赛事材料授权。

`official` 表示编纂者登记为主办方公布答案，`third-party` 表示第三方转录，二者不合并为同一真值层级。主办方答案是赛事标签，不是本项目已经逐条取得出生凭证或外部人生事实证明。尚未回查的原题、出生时区、地点或时刻精度如实记录。

首先筛选明确主办方答案、出生日期和性别有效、出生时间有钟表记录或时辰的题。保留每项排除理由。仅有时辰、历史时区不明、地点不明、原题问反推时辰等边界继续影响是否能分析，不能以任意中点或默认地点生成唯一确定盘。结构筛选合格不代表已完成输入核实，也不自动授权事件解释。

## 创建外部评估目录

在已安装 Python 的技能根目录运行，下面占位路径须替换为仓库之外的真实路径：

```sh
python3 scripts/reading_benchmark.py prepare \
  --source /外部来源/hkjfma_qa.json \
  --output-dir /外部评估/一轮固定版本 \
  --source-repo https://github.com/shunshi-ai/fate-bench \
  --source-ref 固定提交SHA \
  --source-license 'fate-bench LICENSE-DATA及底层来源权利范围；见随存的许可副本'

(
  set -C
  python3 scripts/reading_benchmark.py export \
    --evaluation-dir /外部评估/一轮固定版本 \
    --expected-evaluation-sha256 准备回执中的evaluation_sha256 \
    --output /外部分析/bazi-development.json \
    --system bazi --case-limit 3 > /外部评估/一轮固定版本/bazi-export.json
)

(
  set -C
  python3 scripts/reading_benchmark.py export \
    --evaluation-dir /外部评估/一轮固定版本 \
    --expected-evaluation-sha256 准备回执中的evaluation_sha256 \
    --output /外部分析/ziwei-development.json \
    --system ziwei --case-limit 3 > /外部评估/一轮固定版本/ziwei-export.json
)
```

工具按题源的命主编号划分 development 和 holdout。同一编号的所有题都在同一组，固定 seed 与源版本可复现切分。默认仅导出 development，保留组需要显式选择，不在调试或补库时自动运行。

评估方保存准备回执 `preparation-report.json` 中的 `evaluation_sha256`，在导出时核对私有 `evaluation.json` 的原始字节。这个文件包含题源说明、准备工具指纹与派生题目。在分析开始前，评估方保存导出返回的题数、命主数以及 `pack_sha256`、`source_sha256`、`evaluation_sha256`。上述 `set -C` 保护已存导出记录。原样题包与回执留在评估方。题干和选项相同而官方答案版本有变时，题包指纹可以相同，原始题源指纹会拦住换用版本的评分。

导出与评分均校验原始来源 SHA-256，并用同一准备逻辑从固定来源与 seed 重建题目、资格、分组和答案。派生条目不一致时命令停止并报告错误，保留原有评测记录供核查。

题源使用顶层数组，或在对象内提供唯一一个 `questions`、`items` 或 `data` 题目数组。题源、准备记录、题包与答卷的 JSON 对象字段须唯一。多份题目数组或重复字段都会报错并停止。

外部评估目录保留来源、答案、映射和排除记录。题包去除了答案字段，但同一命主的另一道题干仍可能透露当前题所问的人生事实。评估方用导出回执逐题取出分析输入。

```sh
python3 scripts/reading_benchmark.py prompt \
  --pack /外部分析/bazi-development.json \
  --expected-pack-sha256 导出记录中的pack_sha256 \
  --item-id 题包中的中性题号
```

每题开独立上下文，只交付此命令输出的单题及对应技能资料。命题所需的必要背景若已由本题提供，可以照用。依赖同命主其他题或旧答才能补齐的背景，按本题信息不足记录。无盘基线也逐题隔离。题干与选项均作为待核查资料处理。既有整包试验按当时可见上下文记录。

这是流程上的答案隔离，不是文件系统安全沙箱。分析者不得主动查找评估目录或公开答案；公开题也可能已出现在模型训练中，因此称公开案例评测，不称前瞻盲测或已证明的预测效力。

## 分析与回答

八字与紫微分别运行，各自仅使用本体系盘面和获准资料。保持当前学派与来源门；只知时辰时保留其区间，只有必要条件明确的部分才可解释。实际排盘用既有引擎；不把数据集的派生盘当独立金标准，也不为运行总控捏造七政所需经纬度。

出生钟表时间及历史时区或偏移已核、采用民用钟面时，可在总控省略缺失的经纬度，读取八字或紫微对应字段。时区来源未核的题仍按输入缺口处理。

按 `workflows/fortune-auditable-reading.md` 保存实际证据、条件、反例与复审处理。来源和数据不足时交付受限结果并拒答对应题；不能为了比赛分数临时放开隔离、用神、组合或事件推断。

时间题须把公历年度标签与实际事件区间分开：`current_gz` 不替代事件瞬间的年柱。只有“一月2x日”时仍可实际检查20日至29日的区间；日期不精确不等于节气归属一定无法核对。题面使用“虚龄”而未明示口径时，项目的公历年度虚岁只是一个假设；出生农历年可能不同，所映射年份范围须保留口径差异，不能以默认公式宣称题意已确认。

评估方将独立答复按题号汇总到原始题包的答卷。顶层 `system` 取该题包的 `task.system`，`pack_sha256` 取该题包文件原始字节的 SHA-256。先与对应的导出回执对照，再冻结答卷。计算指纹时直接读取题包文件，例如运行 `python3 -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' /外部分析/bazi-development.json`。同一批八字和紫微题可能共用题号，必须按各自题包保存答卷。每道导出的题恰好给一条记录，包括错误与拒答。保存单题交付和原始答复的证据，评分校验本身无法复核分析者看到的上下文。

```json
{
  "system": "bazi",
  "pack_sha256": "替换为实际分析题包的64位十六进制指纹",
  "responses": [
    {"item_id": "pack中的中性题号", "answer": "A"},
    {"item_id": "另一中性题号", "abstain": true, "reason": "具体缺失或尚无获准解释规则"}
  ]
}
```

评测方在分析记录冻结后、评分前，用上面的同一方法读取收到的答卷文件，另存其原始字节的 SHA-256。评分时用这份回执核对答卷。答卷字节与回执不一致、声明的体系或题包指纹不匹配，以及缺题、重复题或未知题号都会使评分停止。纠正提交时保留原答卷与回执，给新版本单独保存回执，保持原题集。

```sh
python3 scripts/reading_benchmark.py score \
  --evaluation-dir /外部评估/一轮固定版本 \
  --pack /外部分析/bazi-development.json \
  --expected-pack-sha256 导出记录中的pack_sha256 \
  --expected-source-sha256 导出记录中的source_sha256 \
  --expected-evaluation-sha256 导出记录中的evaluation_sha256 \
  --responses /外部分析/bazi-responses.json \
  --expected-response-sha256 评分前另存的答卷指纹 \
  --output /外部评估/bazi-development-score.json
```

报告分别记录实际指纹及 `pack_sha256_verified`、`source_sha256_verified`、`evaluation_sha256_verified`。导出的 `evaluation_sha256_verified` 对应准备回执，评分中的同名字段对应导出回执。旧调用可以省略没有预存的指纹，对应状态为 `false`。校验只证明文件与回执一致，题源的实际出处和许可仍由评估方核查。

报告保存答卷文件的 `response_sha256`。与评分前另存的回执匹配时，`response_sha256_verified` 为 `true`，缺回执的旧调用该项为 `false`。`response_system_verified` 和 `response_pack_sha256_verified` 核对答卷声明与实际题包，分析过程仍由独立记录复审。旧数组和只有 `responses` 的旧答卷可加 `--allow-unbound-responses` 重放，两项题包绑定状态均为 `false`。此类分数只能核查历史计算，体系归因及当时所用题包仍未核实。部分填写或冲突的绑定字段在旧档模式也会报错。

## 结果与优化

同时报告题数、按源命主编号汇总的案例数、已答、答对、答错、拒答、覆盖率、全部题目得分及已答题得分。随机猜测参考按各题实际选项数计算。八字和紫微答同一人的同一批题时，两套分数共享样本。同一命主的多题也共享其人生背景。

私有准备和评分报告在 `cross_split_duplicates` 中列出开发组与保留组的完全重复题组数和各组受影响题数。按标准化出生字段、题干及原顺序的选项字母和文本精确比较，忽略题号、命主编号、答案和附带的不确定标记。评分报告另列本次涉及的 `scored_item_ids`。分组和计分照旧。报告独立未见题表现时单列受影响的题，命主身份和近似重题仍需人工核验。

`cross_split_rearranged_choices` 另报出生字段、题干及各选项文字与重复次数完全一致，但原选项顺序或字母改变的跨组重题。每道受影响题须在另一组有不同选项排法的对应题。若它还有原排法相同的对应题，可同时出现在两个报告中。报告独立未见题表现时把两处受影响题号取并集；题包、分组和分数保持原计算。

`cross_split_birth_matches` 供评估方排查跨组命主编号重合。比较同一历法类型、出生日期、性别、明确的钟面时分、地点和国家字段，略过时辰或时间区间与钟面冲突的记录。比较只使用已规范化的记载值，时区、农历闰月和真实身份仍须另核。报告列出重合组的匿名命主编号，以及这些编号下所有合格题的数量。评分报告另列本次涉及的题号，即使这些题各自的出生字段略有不同也纳入。同一钟面资料可能来自不同的人，先人工复核身份及题间信息，再评价保留组独立性。题包、分组和分数按原规则计算。

合成对话试用分别记录排盘证据重放和实际交付复审。冻结题面及交付的首答、追答，再按共享流程逐项核对原问、可给的条件方向和对应的退出条件。仅核机器材料的脚本只能证明证据重放，正文是否完整或越界以实际答复的复审为准。

先用 development 的错误、拒答与来源缺口准备规则候选。每条增补须有来源定位、盘面字段、必要条件、反例、用途和兼容性；候选保存在 `proposals/`，不进入运行时检索。实际新增或改变规则启用前，提交具体清单与影响让用户确认。

批准、实现并完成开发回归后，再用没有用于补库的 holdout 检查。保留全部结果、版本与未解决项；同一保留组被用于迭代后不得继续宣传为未见评估。评测改善只说明该版本在这批公开赛事标签上的表现，不自动推广为现实人生预测准确率。
