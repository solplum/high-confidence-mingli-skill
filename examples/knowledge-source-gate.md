# 可运行的知识引用示例

这是通用知识示例，没有个人出生资料，不是命中率案例。

## 问：三方四正是什么，是否等于一条格局结论？

运行：

```sh
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-fixed-natal --term 三方四正
```

预期返回 `ziwei-three-four`，来源 `iztro-docs-palace`。

可用的普通解释：三方四正是本宫、对宫及两个三合宫的组合关系。详批先列出这四宫的实际星曜，再看相应格局是否满足条件。知道四宫关系本身，并不能推出某个现实结果。

出处应写：本项目释义，依据 Sylar Long / iztro-docs 现代说明，固定版本1beef80029cd3f1a40b769d3b1c911004ecb9789，learn/palace.md“三方四正”节。不能改写成“《紫微斗数全书》原文曰”。

查看数字来源的短摘录：

```sh
python3 scripts/knowledge_catalog.py cite --source iztro-docs-palace --mode source_excerpt --start 376 --end 378
```

输出包含真正的来源标签、固定URL、hash、行号和“不是经过核验的古籍原文”警告。

## 问：旧文件写了“紫微化忌”，能直接引用吗？

```sh
python3 scripts/knowledge_catalog.py cite --source ziwei-classics --mode classical_quote --start 20 --end 20
```

预期退出1。这个旧整理条文没有核定原典版本，且该组合不在当前十干四化表内。不得在个人解读中引用它来支持结论。若任务就是审计旧文件，可用 `source_excerpt` 展示缺陷，但必须明确它是有疑点的上游整理，并非得到认可的规则。

## 问：当前固定生年四化能用飞星规则吗？

```sh
python3 scripts/knowledge_catalog.py query --system ziwei --profile ziwei-flying --term 四化
```

预期 status 为 insufficient，没有普通解释条目。当前知识门只启用明确列入 `ziwei-fixed-natal` 的释义，不把检索不到理解为可以绕去全文套用。

## 旧 ledger 的真实接入

```sh
python3 scripts/validate_claim_ledger.py examples/engine-reading/ledger.json --root examples/engine-reading
```

该虚构输入的已有实例增加了 `attribution_kind` 和 `source_label`，说明摘的是本地整理资料。删除标签、谎称古文或引用已隔离条文，会使已知来源检查失败。通过仍不证明命理判断正确。

## 隔离与未知来源负例

已隔离原文第20行即使只摘“紫微化忌”，ledger仍拒绝。同段的其他片段也暂不用于正式解读，直至人工拆分复核。复制并改名的未知文件不能宣称已核古籍，必须使用 caller_declared_unverified 标签；CLI结果明确列出其未核验rule IDs。自行填写版次与验证文件不能开启本版的 classical_quote 模式。
