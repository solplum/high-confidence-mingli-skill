# 导入知识到实际排盘的最小示例

虚构输入，不是用户资料或预测案例。在仓库根目录运行：

```sh
(cd scripts/pai_pan_ziwei && npm ci)
python3 examples/imported-knowledge/generate.py
python3 scripts/validate_claim_ledger.py examples/imported-knowledge/ledger.json --root .
```

脚本实际执行三引擎 CLI，使用 Asia/Shanghai、默认 civil 和显式分析年2026，保存完整快照与命令。ledger 以 SHA-256 和 JSON pointer 绑定命宫三方四正四宫的实际字段，并直接引用已保留的 iztro-docs/learn/palace.md，不另复制一份上游资料。

规则标签为 Sylar Long / iztro-docs 现代说明，固定版本1beef80029cd3f1a40b769d3b1c911004ecb9789；原始许可见该 vendor 目录 LICENSE。这只是四宫关系的数字来源摘录，不是古籍认证，也没有作吉凶、成格或现实事件结论。快照 hash、原文、标签和结构通过不证明推断正确性。

没有覆盖：全部新资料的语义适用、自动详批、飞化、运限综合、完整时间候选枚举或现实预测质量。
