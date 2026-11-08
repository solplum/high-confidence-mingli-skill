# 八字 / 紫微上游语料审查（2026-11-07）

## 结论

高星用于找到值得审查的工程，不代表文字可信或预测有效。首批实际迁入 iztro 官方文档仓 17 篇、515,538 bytes；原始许可、固定 revision、文件 hash 和审查限制见 `references/vendor/iztro-docs/`。没有覆盖已有 8 份同步材料，没有更改引擎规则或把任何原文自动认作普通解读证据。

## 可复查快照

stars 来自本次 GitHub REST `GET /repos/{owner}/{repo}`，revision 来自默认分支 commits / tree。数值是读取时快照，不代表未来数值。官方引擎仓与独立文档仓分别列出。

| 仓库 | stars | revision | 根仓许可 |
|---|---:|---|---|
| [Renhuai123/ziwei-doushu](https://github.com/Renhuai123/ziwei-doushu) | 16,562 | `a600484a49255039d0725f1ba9e11ca81a948f97` | MIT |
| [SylarLong/iztro](https://github.com/SylarLong/iztro) | 4,354 | `d7df0a54c9f98f916a33ad4b025001a6b0235275` | MIT |
| [SylarLong/iztro-docs](https://github.com/SylarLong/iztro-docs) | 9 | `1beef80029cd3f1a40b769d3b1c911004ecb9789` | MIT |
| [jinchenma94/bazi-skill](https://github.com/jinchenma94/bazi-skill) | 3,827 | `112a5d84cd1a001a0038cafca3be68d93e4c0cc9` | MIT |
| [china-testing/bazi](https://github.com/china-testing/bazi) | 1,558 | `33b18354d5407727640e545c3aaec0efb4bf5282` | 未检测到根仓许可 |
| [6tail/lunar-javascript](https://github.com/6tail/lunar-javascript) | 1,739 | `5c92e62c904ba5cc0b62f032796aeef433702268` | MIT |
| [6tail/lunar-python](https://github.com/6tail/lunar-python) | 692 | `1645ad3b3653635e5cb31b0c6df22b5e4298f8ce` | MIT |
| [garychowcmu/daizhigev20](https://github.com/garychowcmu/daizhigev20) | 3,569 | `4a6d6f2088825f132521d848c2ea86cf9c9a7620` | 未检测到根仓许可 |
| [solplum/fortune-observatory](https://github.com/solplum/fortune-observatory) | 2 | `3ce1995e41b29e4ab2320323a969158f4e5b2214` | 未检测到根仓许可 |

## 优先级、增量与缺陷

### 1. iztro / iztro-docs：本次导入

`learn/` 对现库最有价值的增量是十二宫、14 主星及双星、辅星/杂曜/神煞、四化与运限的成段解释，以及《紫微斗数全书》三卷和诸星问答数字录文。不是再搬一套天干表。文档仓 MIT 原文明确含 associated documentation，署名 ©2023 Sylar Long；卷一另有校对知秋署名，全部保留。

限制：没有明确影印底本或页码，不能称校勘原典；现代格局页明说收录互联网资料，不是全数古籍。四化页含飞化，不能混入本仓固定学派。图示和 Vue Donate 组件未移植、未执行，原文包含相对链接；检索层应排除广告/组件文本。文本中命理断语是传统解释，没有被星数或该项目的工程测试验证。

### 2. jinchenma94/bazi-skill：已有摘要，不重复引入

根 MIT。现有五份八字参考与其同源，`classical-texts.md` 仅九书核心摘要而非九部原书，不足以支持细到月令、干支组合、例外与异说的出处。适合保留术语/入门索引，不能把它当大规模经典库。后续应对原书篇章建立独立来源记录，而不是重复增加同一摘要。

### 3. Renhuai123/ziwei-doushu：工程可参考，所谓古籍必须隔离

16,562 stars 仍不解决内容错误。固定版本 `lib/classics/data/quanshu.ts` 的 qs-1-2 出现“逆袭”，`gusuifu.ts` 的 gsf-2-4 出现“紫微化忌”，与把内容称古籍原文的声明冲突。现有紫微经典材料与它重叠，不能靠再次迁入改善来源。

其许可不只有 MIT：根 LICENSE 是代码 MIT；DATASET-LICENSE 对 release 样本 v3.0/解读 v4.0 指定 CC BY 4.0，且排除倪海厦引文；`docs/tianji-ziwei/LICENSE.md` 单独 CC BY-NC-SA 4.0，并承认原课程版权归原权利人。不能把讲义按 MIT 批量移植。数据集是引擎生成的样本，不是验证预测准确性的观察样本。

### 4. garychowcmu/daizhigev20：八字原书候选，版本和权利待核

已有七政材料引用此库。实际八字路径含 `易藏/术数/三命通会.txt`、`渊海子平.txt`、`神峰通考.txt`、`穷通宝鉴.txt`，还含 `滴天髓阐微.txt`、`子平真诠评注.txt`、`千里命稿.txt`。没有根仓许可证，不能把整库当开源授权包。古代作品可能进入公版，但现代点校、注解、校订需分别核验，不能因总标题是古籍就推定所有版本公版。

本轮未新增搬运。建议按具体底本、作者/注者、出版/死亡年份、影印馆藏和可引用章节逐本核验后导入。明清原典与民国/现代注评单独归类。

### 5. china-testing/bazi：只参考结构，暂不迁移

1,558 stars，有实际书籍/解释内容（如 `books/穷通宝鉴.md`），但根仓无许可证。公开可读不等于可整体重发。可比较其规则覆盖，未经权利确认不复制其代码/现代编排或全文材料。

### 6. 6tail/lunar-javascript / lunar-python：工程交叉检查，不是解释语料主源

均 MIT。适合节气、农历、八字基础历法 API 和边界差分样本，不提供可替代经典论命材料的完整解释知识库。两者同一生态，不应把它们的一致输出视为两个独立学派证据。

### 7. solplum/fortune-observatory：用户既有项目，避免重复灌库

本地与 GitHub revision 一致，2 stars；未检测到根仓许可证。其 `skills/bazi`、`skills/ziwei-doushu` 带子目录许可，数据规则与日历黄金样本可作为现有工程资产参考；不是独立于已用上游的第二份原典背书。不要将它包装为高星独立知识来源，也不要重新导入用户的个人命盘/记忆。

## 后续最值得补的具体内容

1. 八字：月令与格局的原书段落、用神术语跨书差异、透干/通根/合化的条件与反例。先核明确底本，按原文+现代注释分层。
2. 紫微：先用本次文档补宫位和星曜说明，逐段人工审核后加入可解释白名单；古籍录文只允许带版本不足标记的研究检索。
3. 将源层证据与引擎规则验证分开。任何“某格成立”都必须由引擎事实字段满足可审计条件，不从自然语言形容词推断。
4. 继续隔离旧版伪古籍和无出处断语；不能用“八字/紫微一致”取代预测验证。
