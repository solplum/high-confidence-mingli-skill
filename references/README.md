> **知识来源门（所有引用必读）**：先读 `knowledge/README.md` 并验证 `knowledge/catalog.json`。这条约束优先于下文旧的“原典/权威/书名章节”说法；旧摘要仅作有来源的现代整理，隔离条目不用于解读，未核版本不作逐字古籍引用。直接读旧 references 也必须过此门。

# references/ — 解读资料层溯源

> 解读层知识源：bazi / 紫微斗数两个上游 skill 的参考资料**逐字节原样**拷入
> （2026-10-01），未裁剪未改写；七政解读册为本仓自建（七政无参照 skill）。
> **2026-10-07 七政典籍化（v2）**：新增七政四余原典库五件，原文辑自殆知阁 daizhigev20
> 《张果星宗》（简体点校本，十七卷）、《星学大成》（四库本）、《乾元秘旨》（清·舒继英），
> 断语条目原文照录、逐条标注书名·卷·小节；速查索引表由原文自动抽取＋人工补阙。
> 保持逐字节原样是为了将来上游更新时可整文件覆盖同步（cp + diff 即可审计）。
> 解读时先查对应文件，不靠模型记忆；排盘数字以 `scripts/` 引擎输出为准。

## 溯源表

| 文件 | 来源 | 说明 |
|------|------|------|
| `bazi/classical-texts.md` | bazi skill `references/classical-texts.md` | 九本典籍（穷通宝典/三命通会/滴天髓/渊海子平/千里命稿/协纪辨方书/子平真诠/神峰通考/果老星宗）核心论命规则摘要 |
| `bazi/wuxing-tables.md` | bazi skill `references/wuxing-tables.md` | 五行/天干地支/十神/藏干参考表（与八字引擎同口径） |
| `bazi/shichen-table.md` | bazi skill `references/shichen-table.md` | 时辰对照表、五鼠遁元日上起时 |
| `bazi/dayun-rules.md` | bazi skill `references/dayun-rules.md` | 大运顺逆排规则、起运年龄、流年分析规则 |
| `bazi/shensha-table.md` | bazi skill `references/shensha-table.md` | 神煞吉凶、查法与口诀（与八字引擎同口径） |
| `ziwei/classics.md` | ziwei-doushu skill `references/classics.md` | 《骨髓赋》《紫微斗数全书》《紫微斗数全集》条目原文（引用标注书名+章节） |
| `ziwei/patterns.md` | ziwei-doushu skill `references/patterns.md` | 41 格局全目录（含义/成立/加分/破格；由 ziwei vendor patterns.ts 自动提取） |
| `ziwei/sihua-tables.md` | ziwei-doushu skill `references/sihua-tables.md` | 十天干四化表 + 十四主星速查（与紫微引擎同口径） |
| `qizheng/reading.md` | **本仓自建**（v2 改版） | 判读操作手册：引擎字段→典籍查表路由、口径注（命度/立命宫两口径、明晦异文、不做层清单）、断语纪律、最小判读序 |
| `qizheng/classics.md` | 殆知阁《张果星宗》卷一/六/八/九/十/十一 ＋《星学大成》卷二十五 | 读盘总纲：入门看法四十诀、宫度主论（三主）、生杀星论、性情论、五星相生相克、阴阳并明说、躔次喜忌（逐曜）、恩用难仇原典（磨赋）、谈星奥论、看盘活法、星盘或问、果老歌赋 |
| `qizheng/stars.md` | 殆知阁《张果星宗》卷九~十五逐曜篇 ＋《星学大成》「X星在命」诸章 | 十一曜逐曜断：总论/歌断→在命→入宫·枢要歌（化名速查表）→躔度·玉关歌（断名速查表）→照宫·琅玕经；太阴另附专论九说 |
| `qizheng/palaces.md` | 殆知阁《张果星宗》卷一/八/十/十三 ＋《乾元秘旨》 | 十二宫体系：宫名目次序、宫分所属（分野/宫主）、十二宫命名与逐曜守宫断（拦驾经）、逐宫主论、观星要诀十二宫活断 |
| `qizheng/states-tables.md` | 殆知阁《张果星宗》卷一/五/十五 | 星辰状态查表：喜宫歌关系律（庙乐旺制刑）、星辰妙度歌、入庙/乘旺/乐宫/喜宫/殿垣、升殿宿表（引擎对照形）、合格会合、忌躔失陷、昼夜明晦、四时旺衰、掩蚀 |
| `qizheng/forms-geju.md` | 殆知阁《张果星宗》卷五/六 ＋《乾元秘旨》 | 格局库：十一曜定格（日月/五星/政余合格忌格）、十二宫定格（命主/田主/财星/禄主/福星/妻星/嗣星）、贵贱贫疾格、灵台星格、星格贵贱总赋、指迷/金箱/帘幕歌、八格赋、政余类聚/相照光度/经纬贯串 |
| `domain-signals.md` | **本仓自建**（自 SKILL.md §13 迁入） | 四领域（感情/事业/财运/健康）× 三盘信号映射索引 |

**不入库声明**：《张果星宗》卷十六十七（洞微百六限/倒限诸篇）与卷二至四（变曜/化曜/神煞起例）
不收——前者引擎未算行度且涉断寿，后者依赖年干起例引擎未实现；解读一律不引。

## 引用密度约定（详见 SKILL.md 解读管线节）

- 轻引用管线（运势查询/推算/共鸣/知识）：每篇主判断挂 1-2 条最贴典籍依据
- 详批模式（fortune-full-reading）：每节全出处
