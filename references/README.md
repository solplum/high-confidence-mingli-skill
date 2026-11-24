# references/ — 命理知识库与速查表索引

本仓采用 **「确定性排盘引擎 + 结构化古籍原典语料 + 轻量静态速查表」** 架构：

## 1. 结构化经典原典语料（`references/corpus/`）

共 **7 份清理加工后的 JSONL 语料 + `manifest.json`**（总计 **1,351 条**），通过 `scripts/mingli_query.py` 进行 SHA-256 校验、日干月支精查与三盘自动检索：

| 文件 | 条数 | 内容与许可 |
|------|------|------------|
| `bazi_qiongtong.jsonl` | 125 | 《穷通宝鉴》全文分篇（**10×12=120 组合 100% 覆盖**，修复 `二月葵水` 错字等）；MIT (`ycc77cn/skills`) |
| `bazi_classics.jsonl` | 541 | 《子平真诠》《滴天髓阐微》《渊海子平》《千里命稿》分段原典；MIT (`ycc77cn/skills`) |
| `ziwei_quanshu.jsonl` | 142 | 《紫微斗数全书》卷一至三与《诸星问答论》录文；MIT (`iztro-docs`) |
| `ziwei_stars_patterns.jsonl` | 263 | 十四主星/辅煞杂曜/十二宫/四化/格局与引擎 41 格局（已剥离 Vue/HTML 噪声与死链；飞星条目标记为 `feixing_reference` 默认旁参）；MIT |
| `qizheng_classics.jsonl` | 83 | 《张果星宗》《星学大成》总纲与星辰庙旺喜忌；Public Domain (`daizhigev20`) |
| `qizheng_stars.jsonl` | 96 | 《张果星宗》《星学大成》十一曜逐曜断（已修复 PUA 造字缺字，未考一字标 `[缺字:U+EF6E]`）；Public Domain |
| `qizheng_palaces_geju.jsonl` | 101 | 《张果星宗》《乾元秘旨》十二宫体系与格局库；Public Domain |

详细数据源、清洗修复与边界说明见 [docs/corpus-audit.md](../docs/corpus-audit.md) 与 [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md)。

## 2. 静态速查与操作手册

| 文件 | 用途 |
|------|------|
| `domain-signals.md` | 感情 / 事业 / 财运 / 健康四领域 × 三盘核心信号指引 |
| `bazi/classical-texts.md` | 八字调候/格局/旺衰三类用神口径辨析 |
| `bazi/wuxing-tables.md` | 五行、十干、十二支藏干、十神速查表 |
| `bazi/shichen-table.md` | 十二时辰与五鼠遁元表 |
| `bazi/dayun-rules.md` | 大运顺逆排与折月起运规则说明 |
| `bazi/shensha-table.md` | 常用神煞查法（与 `pai_pan_bazi.py` 同口径） |
| `ziwei/patterns.md` | 内置 41 格局条件与古籍出处速查表 |
| `ziwei/sihua-tables.md` | 倪海厦《天纪》口径生年十天干四化表与十四主星速查 |
| `qizheng/reading.md` | 七政盘字段 → 原典检索路由与学派边界注 |
| `qizheng/states-tables.md` | 七政喜宫歌关系律、二十八宿升殿、昼夜明晦查表 |
| `offline-calendar.md` | 无 Python/Node 环境时的离线历法降级参考表 |
