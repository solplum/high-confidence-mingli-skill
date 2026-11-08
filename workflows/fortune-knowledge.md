# Fortune-Knowledge — 通用知识 Workflow

> **知识来源门（所有引用必读）**：先读 `knowledge/README.md` 并验证 `knowledge/catalog.json`。这条约束优先于下文旧的“原典/权威/书名章节”说法；旧摘要仅作有来源的现代整理，隔离条目不用于解读，未核版本不作逐字古籍引用。直接读旧 references 也必须过此门。


> 由 SKILL.md §0 路由触发。处理脱离个人盘面的命理知识问答。
> 输入: concept
> 数据: SKILL.md 通用规则（§6/§7/§13）+ 可选对照 `~/.claude/fortune-telling/chart.md`

## 与共鸣溯源的边界

| | 共鸣溯源 | 通用知识(本workflow) |
|---|---|---|
| 用户绑定 | "我是不是……" | 无第一人称 |
| 分析锚点 | 个人命盘 | 通用命理体系 |
| 输出方向 | 溯源解释 | 知识解答 |

模糊边界: "偏印是什么？我是不是？" → 先本 workflow 解释概念，再走共鸣溯源对照，两段合一输出。

## Phase 1: 知识检索（references 查表优先）

从以下数据源提取与该概念相关的定义、规则、对照关系（**先查表，AI 记忆只补表里没有的**）:
- `references/ziwei/patterns.md` + `classics.md`: 格局类/星曜类概念的权威条目（带出处）
- `references/bazi/classical-texts.md`: 十神/格局/调候类概念的典籍摘要
- `references/qizheng/reading.md`: 恩用难仇/度主/昼夜取重条目
- SKILL.md §7 推算规则（降级路径）: 四化表、年上起月法、十神判定、藏干表等通用规则
- `references/domain-signals.md`: 该概念在各领域中的对应
- chart.md（仅用于可选对照，不作分析锚点）: 该概念在用户盘中的实例
- AI 自身命理知识: 仅用于查表无果时的补充，须标注「表外补充」

输出: { definitions: string[], rules: string[], citations: string[], cross_references: string[] }

## Phase 2: 三盘对照

有子 agent 工具时 parallel（无则顺序内联）:
- **八字**: 该概念在八字体系中的表现
  - 任务: 定义/特征/常见误解，定义引 `references/bazi/classical-texts.md` 条目并标注典籍
  - schema: `{ plate: "八字", manifestation: string, citation: string, key_features: string[], has_direct_match: boolean }`

- **紫微**: 该概念在紫微体系中的表现
  - 任务: 定义/特征/常见误解，定义引 `references/ziwei/classics.md` 或 `patterns.md` 条目并标注书名+章节
  - schema: 同上（含 citation）

- **七政**: 该概念在七政体系中的表现
  - 任务: 定义/特征/常见误解，引 `references/qizheng/reading.md` 条目并标注出处
  - schema: 同上（含 citation）

无直接对应的盘标注: "该概念在X盘中无直接对应"

## Phase 3: 输出格式化

按 SKILL.md §16 模板 + §9 斯多葛语气:

```
### [概念]是什么
[体系归属（八字/紫微/七政）+ 核心定义 + 常见误解澄清]

### 在各盘中的表现
| 盘 | 如何体现 | 关键特征 |
|----|---------|---------|
| 八字 | ... | ... |
| 紫微 | ... | ... |
| 七政 | ... | ... |

> 🏛 对照你的盘面：[有对应就对照，无对应就说明"无直接对应，但理解它有助于你更完整地认识命理体系"]
```

## 约束

- 不以个人盘为分析锚点（区别于共鸣溯源）
- 个人盘对照是可选附加，不强加
- 无第一人称绑定
