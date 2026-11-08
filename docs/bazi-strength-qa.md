# 日主承受增量验收

基线 e751aee；独立工作树实现，无网络发布，无个人数据。原始八字/紫微/七政引擎和旧上游参考文件未改。核心 JSON 新增 strength_reasoning，五段布局和 CLI 参数保持兼容；误差参数显式传至中心盘解释，不改引擎原始事实。

## 实测

- `python3 scripts/knowledge_catalog.py validate`：28 sources / 45 records，通过。
- `python3 scripts/test_pai_pan_bazi.py`：11通过。
- `python3 scripts/test_pai_pan_qizheng.py`：16通过。
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`：67通过，0跳过。
- `python3 -m unittest discover -s tests -v`：140通过，0跳过。
- 新增强弱16项含 CLI误差、场景正文出处与保留条件、得令非自动强、无根非从、同透干不同根、反证移入、合冲不删事实、乙午/丁酉争议、土月范围、来源失效即拒绝、刑害未评估披露。最终场景断言补充后重跑16项通过。
- `python3 examples/bazi-strength/generate.py`：四种不同结论均与真实引擎合成日期相符。
- `git diff --check`：通过。

Node 依赖用 `npm ci --offline --cache /workspace/scratch/10337929cf9d/npm-time-cache --prefix scripts/pai_pan_ziwei` 实际安装，未复制 node_modules。最初误选空缓存导致 ENOTCACHED；更正为既有有效缓存后成功，并完整运行集成测试。

## 独立审查与修复

独立审查发现中心 CLI 未传时间误差，以及场景摘要未保留未决效力/重算提醒；均修复并增加测试。第二审查指出刑害不在 ST05 合冲审查列表，已增加 unassessed_interactions 逐项披露，不伪造其效力或说所有关系已审查。文档明确增量子版本，不将既有结构版说明冒充新判断的完整规范。

## 演示与限制

- 偏强条件趋势：1987-07-07 10:00，北京时间钟面，丁卯/丙午/丁巳/乙巳。
- 偏弱条件趋势：1978-09-09 12:00，戊午/辛酉/甲戌/庚午。午午自刑与酉戌害明确为未评估关系，不能当完整强弱审查。
- 生扶与克泄耗竞争：1980-01-01 10:00。
- 条件未决：1980-01-08 10:00。

这些是为覆盖分支选择的合成日期，不是历史命例或任何人的资料。规则没有概率、准确率、数值权重、人生事件或唯一喜用神。强弱趋势是公开、极窄的项目条件组合；没有完整制化、司令、土月/土日主与特殊格算法。单版影像只提供可追溯传统语境，不证明预测能力，也不是所有异文的校勘定本。原有滴天髓衍生内容仍独立 CC BY-SA；新增代码与原创释义 MIT。
