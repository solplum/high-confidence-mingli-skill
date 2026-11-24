# Fortune-Knowledge — 命理概念与原典知识问答流程

> 适用于「《子平真诠》的用神和《滴天髓》的用神有什么区别？」「紫微里化忌一定坏吗？」「七政四余的命度和立命宫怎么看？」「《穷通宝鉴》怎么看庚金生巳月？」。

## 原则：纯知识讲解无需建档，绝不凭记忆编古文

1. **不要强行拉用户去建档排盘**：纯探讨命理概念、古籍原文或三术体系差异时，直接高质量解答；仅当用户追问“那我自己这个盘怎么算”时，再切入 `docs/onboarding.md` 建档流程。
2. **先用 `scripts/mingli_query.py` 检索再作答**：
   ```bash
   # 查八字特定日干月令原典
   python3 scripts/mingli_query.py bazi-lookup --day-stem 庚 --month-branch 巳

   # 跨三盘/单体系查原典原文（加 --full 可输出完整未截断原文）
   python3 scripts/mingli_query.py search --system bazi --query "用神 相神 格局" --full --limit 6
   python3 scripts/mingli_query.py search --system ziwei --query "化忌" --include-feixing
   python3 scripts/mingli_query.py search --system qizheng --query "命度 度主 宫主"
   ```
3. 辅助参考静态速查表：`references/bazi/classical-texts.md`、`references/bazi/dayun-rules.md`、`references/ziwei/sihua-tables.md`、`references/ziwei/patterns.md`、`references/qizheng/reading.md` 与 `references/qizheng/states-tables.md`。

## 回答结构

1. **一句话清晰界定概念**（用现代汉语讲透本质，不故弄玄虚）。
2. **原典出处与逐句解析**：附上 `mingli_query.py` 实际检索到的经典原句（注明书名与篇名）并白话疏通。
3. **实战使用边界与流派差异**：说明该概念在不同经典/流派中的分歧点（例如《子平真诠》重月令格神 vs《穷通宝鉴》重气候调候；《天纪》固定四化 vs 飞星四化；七政命度重度主 vs 乾元派重立命宫）及常见误区。
