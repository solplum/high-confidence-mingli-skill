# 原典知识库清洗与审计记录（Corpus Audit）

> 本文档记录 `references/corpus/`（共 9 份 JSONL、1,508 条记录，索引见 `references/corpus/manifest.json`）的数据来源、许可、清洗修复与自动化防回退测试。

## 1. 上游来源与许可

| 语料文件 | 收录内容 | 上游来源 | 许可 |
|----------|----------|----------|------|
| `bazi_qiongtong.jsonl` (125 条) | 《穷通宝鉴》五行总论、四季分论及十天干十二月全篇 | `ycc77cn/skills` (`原文库/穷通宝鉴.txt`) | MIT |
| `bazi_classics.jsonl` (541 条) | 《子平真诠》《滴天髓阐微》《渊海子平》《千里命稿》 | `ycc77cn/skills` | MIT |
| `ziwei_quanshu.jsonl` (142 条) | 《紫微斗数全书》卷一至卷三、《诸星问答论》 | `SylarLong/iztro-docs` (`ancientBook-{1,2,3,qa}.md`) | MIT |
| `ziwei_stars_patterns.jsonl` (263 条) | 十四主星、辅煞杂曜、十二宫、四化、常见格局及引擎内置 41 格局 | `SylarLong/iztro-docs` + `scripts/pai_pan_ziwei/vendor/patterns.ts` | MIT |
| `qizheng_classics.jsonl` (83 条) | 《张果星宗》总纲/宫度主/生杀/性情/阴阳并明/躔次喜忌/星辰庙旺喜忌＋《星学大成·磨赋》 | `daizhigev20` 点校本 | Public Domain |
| `qizheng_stars.jsonl` (96 条) | 《张果星宗》卷九～十五十一曜逐曜断＋《星学大成》 | `daizhigev20` 点校本 | Public Domain |
| `qizheng_palaces_geju.jsonl` (101 条) | 《张果星宗》十二宫体系与格局库＋《乾元秘旨》 | `daizhigev20` 点校本 | Public Domain |
| `qizheng_bianyao_shensha.jsonl` (86 条) | 《张果星宗》卷二～三：十干变曜（天禄～天权管库星）、年干诸星与年干支/驾前驾后神煞 | `daizhigev20` 点校本 | Public Domain |
| `qizheng_dongwei_liunian.jsonl` (71 条) | 《张果星宗》卷三、卷十六～十七：定行限度法、洞微百六限、倒限直指与流年太岁论 | `daizhigev20` 点校本 | Public Domain |

完整版权文本见根目录 [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md)。

## 2. 清洗与修复清单

### A. 八字语料
1. **《穷通宝鉴》错字与合篇修复，达成 120/120 全覆盖**：
   - 修复原文笔误：`二月葵水` → `二月癸水`，确保 `癸` 日 `卯` 月精确命中。
   - 保留传统合篇原貌并显式加注 `tags.month_branches` 数组（例如 `八九月丁火` 同时标注 `["酉", "戌"]`；`十一月乙木` 合论子丑月标 `["子", "丑"]`），经实测验证全部 `10 天干 × 12 月支 = 120` 组合均可通过 `mingli_query.py bazi-lookup` 完整检索。
2. **摘要与原典解耦**：
   - 修复 `references/bazi/classical-texts.md` 中“得令仅长生帝旺”及“`衰极宜扶不宜帮`”的自相矛盾条目，明确区分**调候用神**（《穷通宝鉴》）、**格局用神**（《子平真诠》）与**扶抑/病药用神**（《滴天髓》《神峰通考》）。

### B. 紫微语料
1. **剥离伪古籍拼凑内容**：
   - 旧版 `references/ziwei/classics.md` 混入了无出处现代编造词（如「逆袭」「企业高管」「紫微化忌」「紫微星化忌」），已整文件移除，改用 MIT 开源 `iztro-docs` 录入的《紫微斗数全书》原书卷次录文。
2. **清除前端框架噪声与空链接**：
   - 彻底清除 `iztro-docs` 中的 `<script setup>`、`<style>`、`<Donate />`、`<Badge />`、`:::tip`、星盘 HTML `<table>` 及相对路径推广尾巴。
   - 剔除仅含「见 [XX](#XX)」的纯跳转占位段落及 `{主星}化忌入命／迁（警示）` 空模板头。
3. **学派边界默认隔离**：
   - 将明确讲宫干飞化四化的条目打标 `school="feixing_reference"`；`mingli_query.py` 默认排除，避免与本仓《天纪》口径的固定生年四化混用（加 `--include-feixing` 可旁参查看）。

### C. 七政四余语料
1. **Unicode 私用区（PUA）造字与 OCR 异体清理**：
   - 修复殆知阁点校本中的 PUA 乱码字符：

| PUA 码位 | 修复字 | 上下文示例 |
|----------|--------|------------|
| `U+EED5` | `蝎` | 磨蝎赋 |
| `U+E03D` | `冲` | 相冲 / 对冲 |
| `U+E16B` | `荦` | 卓荦动乾坤 |
| `U+EB8E` | `弦` | 上弦 / 下弦 |
| `U+EC93` | `淫` | 淫声 |
| `U+EA5B` | `驰` | 远驰声 |
| `U+E645` | `厚` | 夜生福厚昼生慢 |
| `U+EA20` | `玄` | 真玄妙 |

   - **孤字不猜**：`U+EF6E`（出《张果星宗》「土入\uef6e吴傍斗明」）因缺对照影印本无法百分之百确认原字，显式标为 `[缺字:U+EF6E]`，绝不臆造补字。
   - 底本偶有简体点校常见 OCR 异字（如 `會→防`），已在 `note` 字段透明标注，待后续对照古版影印进一步校勘。
2. **清理模板元注释与碎片**：
   - 剥离旧版 `<!-- 源：... -->` 注释、`> **知识来源门...` 废除横幅、目录导语及切块产生的孤立短行尾巴，所有条目均为实质内容。

## 3. 回归护栏

运行 `python3 -B -m unittest scripts/test_mingli_query.py -v` 每次自动核查：
- `manifest.json` 内 9 份 JSONL 的文件大小、条目数与 **SHA-256 哈希**一致；
- 全库 **1,508** 条记录 **0** 处 Vue/HTML 标签、**0** 处 `<!--` 注释、**0** 处 PUA 私用区码位、新增卷次 **0** 处未修复 `?`、**0** 处已知伪古籍污染词、**0** 处纯跳转空条目；
- 《穷通宝鉴》**120 / 120**（`日干 × 月支`）完整命中，飞星默认隔离，七政变曜/洞微/流年层检索与 `build_chart.py -> mingli_query.py chart-lookup` 端到端管道畅通。
