# 七政物理模型与独立参考核验

本页只验证天文数值，不验证命理预测能力。离线标准库引擎仍为低精度模型，不能替代 JPL 星历；不得根据输出小数位数声称相同精度。

## 明确定义与版本

- `planet_longitude_tt(planet, jd_tt)`：TT 儒略日，`schlyter-geometric-v2`。地心、几何、日期平黄道/平春分点黄经，不含光行时、周年光行差、章动或站心视差。
- `planet_longitude(planet, jd_ut, model=...)`：旧调用兼容入口，以既有 ΔT 多项式换算 TT；UTC≈UT1。新物理管线应直接传已定义的 TT 给上一入口，不能重复加 ΔT。
- `moon_longitude(jd_tt, model='meeus-truncated-geometric-v2')`：Meeus 35 项截断月球几何黄经，日期平黄道/平春分点。非视黄经，非站心位置。
- `model='legacy-v1'`：保留旧函数数值用于复盘，包括已知错误；不作为正确性标准。
- physical-v2 太阳为 Meeus 低精度几何日期平黄经；legacy-v1 仍保留旧近似视黄经。不能把整个输出统一标成“视黄经”。四余中交点/远地点是平均轨道量，紫气是约定虚拟量。

## 来源修正

Paul Schlyter 原文 [Computing planetary positions](https://stjarnhimlen.se/comp/ppcomp.html)，摄动节：木星首项为 −0.332 sin(2Mj−5Ms−67.6°)，旧实现误作 +67.6°；这些项首先用于**日心**黄经，不能直接叠加到地心黄经。v2 还加入原文土星纬度摄动，再还原直角坐标并减去地球位置。

Meeus《Astronomical Algorithms》第 47 章表 A：月球第 34 项应为 −0.002069 sin(2M)，第 35 项应为 +0.002048 sin(2D−2M−M′)。旧表存在错项/错号。v2 还补上太阳平近点角系数所需的 E^|m| 因子。
表值交叉检查使用 [PyMeeus Moon.py](https://github.com/architest/pymeeus/blob/master/pymeeus/Moon.py) 的公开表 47.A 转录；没有复制其实现或引入 PyMeeus 依赖。现有仓库及上游许可/署名不变。运行时及分发不使用 Swiss Ephemeris；可选开发测试可调用独立安装的 Swiss/Moshier 作升点与太阳高度参考，不分发其代码或星历二进制。

## 可重放独立参考

`tests/fixtures/qizheng/` 保存 NASA/JPL Horizons API 原始文本、几何向量、精确查询 URL、SHA-256 和获取时间。无用户数据，所有历元均为合成公开日期。原始文本含所用星历标识（DE441 等）；以原始响应为准。

- 地心 `CENTER=500@399`，目标 199/299/499/599/699/301。
- `EPHEM_TYPE=VECTORS`, `VEC_CORR=NONE`, `REF_PLANE=ECLIPTIC`, `REF_SYSTEM=ICRF`, `VEC_TABLE=1`, `OUT_UNITS=AU-D`。
- 1900-01-01 至 2101-01-01 开区间，182 日步长，每体 404 个历元，共 2,424 对比点，覆盖至 2100 年。不是逐日穷举，也不是极值搜索。
- Horizons 时间是 TDB；这里将其视为 TT（周期差 <2 毫秒），对当前精度预算可忽略。测试直接给 TT 入口，因此不以 ΔT/UTC 假设污染轨道验证。
- J2000 ecliptic 向量通过独立 IAU 1976 岁差/平均黄赤交角适配到日期平黄道；ICRF/FK5 偏置和现代岁差差异在此区间远小于本预算。不能把此适配宣称为高精度 IAU 2006 实现。
- 残差使用 `(actual−reference+180)%360−180`，跨 0° 不出现假大误差。

最大绝对误差 / RMS（度）：

| 天体 | v2 最大 | v2 RMS | 固定测试阈值 |
|---|---:|---:|---:|
| 水星 | 0.015528 | 0.003278 | 0.10 |
| 金星 | 0.029212 | 0.004398 | 0.10 |
| 火星 | 0.052148 | 0.009626 | 0.15 |
| 木星 | 0.031859 | 0.008358 | 0.15 |
| 土星 | 0.045091 | 0.016582 | 0.25 |
| 月亮 | 0.009393 | 0.002769 | 0.05 |

同网格旧木星最大误差 0.527079°、RMS 0.267260°；旧土星最大 0.116520°、RMS 0.031588°。模型变更必须重跑，不得更新参考值来掩盖失败。阈值是在读取结果前固定的工程验收预算，**不是全日期误差上界、置信区间或边界分类保证**。宿界本身还是近似星表，靠近宿/宫边界必须保留不确定性，不能用此表给庙旺细分盖章。

复核：`python tests/test_qizheng_ephemeris.py`，完全离线。
开发者如需刷新公开参考：`python scripts/fetch_qizheng_reference.py`，明确联网并人工审查变更；正常运行/测试不联网。
