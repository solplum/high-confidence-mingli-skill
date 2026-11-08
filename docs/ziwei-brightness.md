# 紫微亮度原值 / Ziwei brightness source fidelity

`chart.palaces[].stars[].brightnessRaw` 是增量字段，原样保留 iztro 2.6.1
在 `astro.bySolar(..., true, 'zh-CN')` 下给出的星曜 `brightness`。
非空字符串直接保留；空字符串、未提供或非字符串统一输出 `null`。
`null` 表示源未提供，不能写成「平」，不能由其他星、对宫或旧分组反推。
旧快照没有此字段时，同样不能反推精确等级。

已核对锁定依赖的实际实现（安装后可检查）：
- `iztro/lib/star/majorStar.js`、`minorStar.js`：调用 `getBrightness`。
- `iztro/lib/utils/index.js`：读取配置或 `STARS_INFO`，无表返回空字符串。
- `iztro/lib/data/stars.js`：库内宫位亮度表，不代表已对拍其他流派。
- `iztro/lib/i18n/locales/zh-CN/brightness.js`：庙、旺、得、利、平、不、陷。
- 上游项目：https://github.com/SylarLong/iztro （本仓版本以 package-lock.json 为准）。

所有主星、辅星、杂曜均保留原值（有些星源库没有亮度数据）。
旧 `brightness` 字段不改：主星仍为庙/旺→`bright`、不/陷→`dim`、
其余及未提供→`normal`；非主星不新增旧字段。旧格局检测逻辑不改，
因此其分组判断不是精确的庙旺细分证明。尤其 `dim` 不等于「陷」。
JSON schema_version 仍为 1，既有键与 CLI 参数保留。
文本 CLI 的主星标签改为精确原值，未提供时显示「亮度未提供」；
不再把「不」显示为「落陷」。读报告应引用原值字段及相应典籍，不能以
数据溯源或同源比较证明术数预测能力。

English: `brightnessRaw` is an additive, exact upstream nonempty label, or `null`
when unavailable. It applies to all star groups. Missing values (including absent
fields in older snapshots) are not neutral/平. Existing collapsed `brightness`
values, pattern logic, JSON keys, schema version, and CLI arguments are unchanged.
Main-star text labels now show the exact source label rather than conflating 不
with 陷. These are iztro's school/table values, not independent accuracy validation.

验证：`python3 -m unittest discover -s tests -p 'test_ziwei_brightness.py' -v`。
测试真实运行依赖和 wrapper，十二时辰覆盖七级、缺失值与辅星，另测 JSON、
文本 CLI 及三盘快照桥接。不能仅用 mocked 输出宣称真实引擎验证通过。

## 本次本地验证记录

四套检查全部通过：八字 11、七政 16、scripts discovery 41、tests discovery 43
（后两套包含前面或新增用例，并非四组互不重叠测试）。未跳过 Node 集成测试。
`npm ci --offline --ignore-scripts` 因 tsx 缓存缺失未能完成；本次复制已存在
的集成工作区 node_modules 运行，`npm ls --depth=0` 确认 iztro 2.6.1、
lunar-javascript 1.7.7、tsx 4.23.13。故本次证明实际运行与回归通过，
不宣称全新离线安装成功。
