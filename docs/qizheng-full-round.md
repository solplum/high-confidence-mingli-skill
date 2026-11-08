# 七政独立整合轮 / Qizheng integrated round

本轮仅合并七政路径：corrected physical-v2、受来源门控制的 QZT04，以及显式时间敏感性。三盘默认排盘口径不切换；选择乾元宫主参照仍须明确 `--qizheng-tradition qianyuan-palace-v1`。误差已明确且支持时，详批工作流实际运行 `--qizheng-sensitivity --uncertainty-minutes N`，文本先给最多六项白话摘要，JSON保留全部见证。两项同时选择时每个见证实际运行 QZT04，主盘仍因时间不确定暂缓。

All options remain explicit. Traditional QZT04 and sensitivity now compose through real chart witnesses rather than unrelated code paths. The uncertain center is still withheld. Defaults do not select a traditional school or run additional sampling. Exact subsecond witness instants are checked against floating UTC Julian dates before palace-clock consistency checks; the 0.1 ms conversion tolerance is not an astronomical accuracy claim.

## 可复现

`python3 examples/qizheng-full-round/reproduce.py OUTPUT_DIRECTORY` 生成纯合成、无个人数据的 narrow / large / DST fold / undefined pole / 1901 / 2100 / no-Node 两种输出及hash清单；同时核查超范围敏感性拒绝，不偷偷裁短误差。Node缺失只使紫微降级，不阻断七政。2100主盘在既有1900–2100模型检查范围内，但1901–2099敏感性拒绝2100区间；两种范围不可混淆。输入选用明确年份，不依赖当前年份。

先 `cd scripts/pai_pan_ziwei && npm ci`，再跑 AGENTS.md 中两项基础测试、scripts/tests 全量 discovery、knowledge 与 study validate。可选Swiss未安装时应明报 skipped，不能当作通过。完整离线交付包括source、从 b7d61b5 的patch、c49e6a5基线与bundle、测试日志及合成证据；没有推送。

## 改善与缺口

改善是可实际调用的有条件传统结构、真实时间差异见证、可读摘要、来源/hash/许可与拒绝条件一致，不是预测准确度提升。采样不保证穷尽；未观察到变化不等于稳定。宿界表未逐星校准；紫气为未独立校准模型点；物理星历仍近似；DUT1/Delta T、地形大气与真太阳时均时差误差未被消除。数值包围时间不是物理精度。QZT01–05中仅QZT04接实际结构解释，其他未核规则、四余取主、行限及个人事件预测仍不启用。

Original project/adaptor/generator code is MIT. Study registry and expressive derived QZT04 outputs retain CC BY-SA 4.0, attribution and source limitations; do not relicense them as MIT. See knowledge/qizheng-traditional-study.json and docs/qizheng-traditional-study.md for exact source and license records. The source gate and ledger prohibition remain unchanged.

## 独立复审

独立检查确认 c49e6a5 的十个原始顶层字段在八组合成日期上由 legacy-v1 完全重现（含1901、2100）；physical-v2 的差异对应已记录的原点、星历、升点和昼夜修正。八份八字/紫微同步原文逐字节不变。e72 默认文本逐字节一致，既有JSON值未变（新增字段与源码hash除外）。复审发现并修复一个亚毫秒时辰边界的假暂缓；用72个跨时辰见证再次核验。此复审只验证软件行为，不证明传统预测能力。
