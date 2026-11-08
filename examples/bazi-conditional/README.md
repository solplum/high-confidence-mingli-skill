# 条件式八字结构解释示例

本示例增强详批中“为什么这样解释、还有哪些条件未满足”的部分，不把知识层升级为预测验证。复用已有虚构summer.json排盘：巳月藏丙庚戊，年庚、时戊透出，从项目格局卡提出印、官两个候选，并保留旺衰、救应和其他学派的未决问题。不是新的真实用户算命，也没有宣称已完整判格。

运行（在仓库根目录）：

```sh
python3 examples/bazi-conditional/generate.py /tmp/bazi-conditional-ledger.json
python3 scripts/validate_claim_ledger.py /tmp/bazi-conditional-ledger.json --root .
python3 scripts/knowledge_catalog.py query --system bazi --profile bazi-traditional-conditional --term 格局
```

生成的ledger及解释改编采用CC BY-SA 4.0，见 references/vendor/wikisource-ditiansui/LICENSE.md；生成器代码为MIT。输出将规则署名、许可及贡献历史附在rule.redistribution中。此目录不增加古籍原文引文，取用的是本项目已有释义。

使用真实资料时必须重新生成其引擎快照，按场景绑定事实，不能把本例的柱位、条件判断或结果照搬。逐项criterion必须与登记卡一致，每项条件/排除均要具体assessment和该claim的fact_ids；facts的JSON指针和值由现有验证器核对。条件未满足或反证未解决时必须withheld；满足也最多conditional。该机制约束证据连接，不自动判断人的文字分析是否合理。

受限claim及综合还需明确`authenticity_status: uncollated_digital_transcription`。综合不能用supported、已校勘/权威标签或财富预测domain覆盖成员的限制；其成员若withheld，综合也须withheld。生成器提供完整许可元数据；删除/篡改rule.redistribution或截短license_notice将使验证失败。
