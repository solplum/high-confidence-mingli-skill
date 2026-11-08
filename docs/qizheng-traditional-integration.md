# 七政传统解释接入：有条件结构，不是人生预测

核验记录日期：2026-11-07。底座是 e72ee617c98db428ee40a1456ebc4bac99f2dfea；原五卡来自 42ef6725、57acf2e1。新增的是原创 MIT 适配代码和工作流。五卡资料、其表达性派生输出继续独立采用 CC BY-SA 4.0，不被 MIT 重新授权。

## 真正运行了什么

`build_chart.py` 的 JSON 增加 `qizheng_traditional_reading`；明确传入 `--qizheng-tradition qianyuan-palace-v1` 后，文本详批也输出同一结构。默认不切换学派。独立七政 CLI 不依赖 Node，直接从当前 corrected `physical-v2` 引擎计算，再取 `/ming_gong/zhi`，以指定日月五星的固定五行比较宫主，调用受 hash 锁定的 QZT04。曜五行不是该曜所躔宿主五行。选择宫主法的结果不会被改叫度主法的恩用难仇。

这是对实际输入盘的条件性传统结构解释，而不是只装入一个无调用者的研究脚本。它仍不是个人事件论断规则：不生成健康、寿命、贵贱、婚财、职业或应期结论，不进入个人事件 ledger、不进入跨盘“多数一致”或命中率。`personal_ledger_authorized=false` 和 `classical_quote_authorized=false` 均保留，未放宽原知识来源门。要交付人生事件论断仍不能完成，不能借这个接入绕过证据门。

来源支持范围也很窄：《乾元秘旨》单版 PDF 第19页支持本命取宫与行限取度的参照区分，不证明所有宫主映射与日月折五行表已经影像核定。映射沿用明确标为项目约定/待校勘的既有表。QZT04 同时列出《星学大成》数字转录异说，保留未对该卷影像的状态。本轮没有重新下载或重新校勘古书；沿用锁定研究登记中的调查记录，扫描 SHA256 为 `1fffb642558dc78810446822a182c8550d811ed337f4e5835168500cf0674aa5`。五卡登记 SHA256 为 `3ded3449332df41b33c675d4b07373b5251c4078bd85f42f8fdd9091bb60f0e4`。更多页码、固定版本、贡献历史、许可见 `qizheng-traditional-study.md` 和登记文件，文本/JSON结果都保留这些归属信息。

QZT01仍为概念辨析；QZT02仍暂缓庙乐判断；QZT03不判断相会；QZT05不计算真实行限。四余没有被新入口启用。未核四卡/更多规则不能因一个入口可运行就称为已验证。

## 时间与拒绝条件

独立 CLI 的 `--hour` 是北京时间民用时（UTC+08），日期为公历。`build_chart.py` 继续沿用既有带时区转换契约，七政取同一物理瞬间与北京时间安命时辰，不把真太阳时再当北京时输入。DUT1 默认0是近似，TT来自既有多项式ΔT，不是实测EOP。宿宫区为近似模型；0.1°边界筛查不是误差上限，离界也不保证传统正确性。源代码/盘hash用于复现，不证明天文精度或命理预测。

缺坐标/命度、缺边界质量字段、边界敏感、日期超出模型核验范围、时间不确定、立命宫链冲突、研究登记或既有来源hash变化、legacy-v1旧计算、未明确学派都会 withheld。部分 gate 比单纯宫主计算更保守，这是有意的。API供本项目确定性引擎结果调用，不承诺能认证外部伪造盘；CLI不接受外部JSON冒充引擎事实。此处只做单场景，不能把中心时刻有输出解释成不确定时间已展开。

## 可复现的虚构输入

下列都是合成出生资料，不属于真实用户或预测验证样本：2000-01-01 12:00，北纬35°东经120°。此盘戌宫，宫主火；选金曜时相对为“我克”。这不是对现实中的人有任何断言。

```sh
python3 scripts/qizheng_traditional_reading.py --solar 2000-01-01 --hour 12:00 --lat 35 --lon 120 --tradition qianyuan-palace-v1 --format text
python3 scripts/qizheng_traditional_reading.py --solar 2000-01-01 --hour 12:00 --lat 35 --lon 120 --tradition qianyuan-palace-v1 --format json
# 两个应退出1并给出明确 withheld 的例子：
python3 scripts/qizheng_traditional_reading.py --solar 2000-01-01 --hour 12:00 --tradition qianyuan-palace-v1
python3 scripts/qizheng_traditional_reading.py --solar 2000-01-01 --hour 12:00 --lat 35 --lon 120 --tradition qianyuan-palace-v1 --uncertain-time
# 三盘实际详批入口，需先在 scripts/pai_pan_ziwei 中 npm ci：
python3 scripts/build_chart.py --solar 2000-01-01 --hour 12:00 --sex 男 --lat 35 --lon 120 --analysis-year 2026 --qizheng-tradition qianyuan-palace-v1 --format json
```

`examples/qizheng-traditional/reproduce.py` 生成同一输入的 valid / absent-location / uncertain-time 文本与JSON及文件hash清单，可重跑比较。日期不取系统当前年；engine部分包含完整计算版本及源码hash，解释另含adapter/registry/chart hash。JSON里的输出格式参数会反映实际生成命令。校验测试另外跑 `build_chart` 的真实 Node 路由，不用mock代替整合。

运行 `python3 scripts/knowledge_catalog.py validate`、`python3 scripts/qizheng_traditional_study.py validate`、两个基础测试和 scripts/tests 两套 unittest discovery。测试通过只说明软件与保守输入契约一致，不是传统规则或现实预测有效。

## 本次集成验证记录

2026-11-07，在独立 worktree 对接入后的完整代码运行：knowledge catalog 与传统登记校验均通过；八字基础11项、七政基础16项通过；scripts发现96项通过，其中2项可选Swiss对照因未安装而跳过；tests发现190项全部通过（含六项新的真实引擎/真实Node/文本JSON路由检查）。初次npm使用默认home缓存失败，改为工作许可范围内的 `/tmp` 缓存后 `npm ci` 成功，再跑全套；没有将缺依赖整合跳过当成功。

三组合成输入的六个输出可逐字节再生；hash清单重跑一致。检查完整 `git diff e72ee617c98db428ee40a1456ebc4bac99f2dfea HEAD --check`；既有41个 references 文件逐字节不变。没有推送。未复跑或宣称通过两项可选Swiss对照；单版影像/数字转录的语义范围仍按原研究登记，不以软件测试覆盖来扩张。

独立复审后收紧：空/缺失的比较曜、非有限黄经、缺安命时间契约、UTC瞬间与安命时辰不一致也暂不判。独立 CLI 文本保留引擎警告（例如南半球适用性未经验证），不只在JSON中显示。内部API的一致性检查不构成外部命盘真实性认证。
