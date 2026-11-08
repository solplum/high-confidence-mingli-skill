# Fortune-Specific — 推算查询 Workflow

> **知识来源门（所有引用必读）**：先读 `knowledge/README.md` 并验证 `knowledge/catalog.json`。这条约束优先于下文旧的“原典/权威/书名章节”说法；旧摘要仅作有来源的现代整理，隔离条目不用于解读，未核版本不作逐字古籍引用。直接读旧 references 也必须过此门。


> 由 SKILL.md §0 路由触发。处理具体问题的深度推演。
> 输入: question
> 数据: `~/.claude/fortune-telling/chart.md` + `~/.claude/fortune-telling/memory.md`

## Phase 1: 问题解构

1. **拆解子问题**: 将用户问题拆为可量化子问题
   - "姻缘怎么样" → ①盘面姻缘结构(references/domain-signals.md 感情信号) ②大运推动(chart.md 大运表) ③流年引动(引擎或 §6+§7 降级) ④时间窗口
   - "该不该去X城市" → ①迁移宫+八字驿马信号 ②原局是否适合变动 ③当前时段变动能量 ④变动对核心矛盾的增强/削弱
   - "适合创业还是打工" → ①官禄宫结构 ②财帛宫模式 ③食伤配印程度 ④当前大运推力方向

2. **判断问题类型**: 选择展开重点，不设置百分比权重
   - 结构性: 姻缘结构/事业方向/天赋，先解释相关原局条件，再列运段条件
   - 时机性: 先确认所问时间范围，分别列原局与当期条件，不保证最佳时点
   - 关系性: 区分双方资料与现实互动；不能凭单人命盘断言他人想法或关系结果
   - 方向选择型: 并入结构性，提供有条件的方向对比，不代替现实选择

输出: { sub_questions: [{ topic: string, aspects: string[] }], question_type: "结构性"|"时机性"|"关系性", focus_layers: string[] }
兼容：旧消费者需要 weights 时保留空对象并标注 deprecated，不填造数值，不用于合成。

## Phase 2: 并行典籍式解读（SKILL.md §9.5 段一）

有子 agent 工具时 parallel（无则顺序内联执行，schema 不变）。缺盘时跳过对应盘并按降级规则处理。
**每盘按其体系框架解读，先查对应 references，论断挂典籍出处**：

- **八字**: 针对每个子问题按十神/干支/冲合角度解读
  - 输入: 原局八字(chart.md) + 问题子项 + 相关干支
  - 知识源: `references/bazi/`（classical-texts / wuxing-tables / dayun-rules）
  - schema: `{ sub_question: string, assertions: [{ statement, citation, domain, direction }] }`（citation=典籍名·章节）

- **紫微**（有数据时）: 针对每个子问题按宫位/星曜/四化角度解读
  - 输入: 原局紫微(chart.md) + 相关宫位 + 四化
  - 知识源: `references/ziwei/`（classics / patterns / sihua-tables）
  - schema: 同上

- **七政**（有数据时）: 针对每个子问题按命度/躔/恩用难仇角度解读
  - 输入: 原局七政(chart.md) + 躔度/相位
  - 知识源: `references/qizheng/reading.md`
  - schema: 同上

## Phase 3: 跨盘对照 + 综合分析（§9.5 段二）

1. **跨盘对照**: 走 §10 三道检查，列一致 / 冲突 / 范围不同 / 信息不足及共同依赖
2. **分层解释**: 按问题相关性、字段完整性与规则条件展开，不加权投票
3. **方向对比**: 方向选择型问题 → 提供条件、反向信号与现实核查问题
4. **时间窗口**: 只讨论有规则支持的条件式窗口；资料不足则暂不判，不宣称最佳窗口

输出: { analysis: [{ sub_question: string, synthesis: string, citations: string[], confidence: string }], direction_comparison: optional, time_window: optional, core_tension: string, practice_advice: string }

## Phase 4: 斯多葛收束（§9.5 段三）

按 SKILL.md §14 模板 + §9 语气（引用密度=轻引用：主判断挂 1-2 条依据行）:

```
### [问题]的能量格局
[多盘 assertion 合述，列条件、冲突与缺口]

### 关键张力
[核心矛盾如何作用在这个问题上——原局结构性张力从什么角度影响这个具体问题]

> 依据：<典籍名·章节>「原文」

### 方向对比（仅方向选择型展开）
| 方向A | 盘面支撑 | 盘面阻力 | 当前时段推力 |
|-------|---------|---------|------------|
| ... | ... | ... | ... |

### 时间窗口（仅时机性）
[窗口的适用条件与限制]

> 🏛 这些传统解释可以作为反思视角。你可以把握的是：[现实可核查、低风险的最小行动]。
```

## 约束

- 旧 confidence 字段若保留只填写条件与信息限制，不填写概率或可靠度星级
- 不按固定比例分配叙事或将缺失层转移到其他层
- 禁止替用户做决定——提供框架和工具，不替选择
