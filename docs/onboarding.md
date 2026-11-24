# 建档流程（Onboarding）

> 个人命盘档案默认保存在 `~/.claude/fortune-telling/chart.md`（Windows 为 `%USERPROFILE%\.claude\fortune-telling\chart.md`），同一命主的后续追问直接复用。**请勿将个人出生档案提交到技能公开仓库。**

## 1. 收集出生信息

最少先确认：**公历生日（YYYY-MM-DD）或明确标明闰月的农历生日、出生时间（精确到分/时辰/未知）、性别（男/女，影响八字大运顺逆与紫微大限/六亲）、出生地（城市及经纬度，七政命度与真太阳时需要）**。

- 如在夏令时年代或海外出生，优先使用 IANA 时区（`--timezone`）并说明是否涉及夏令时或重复时刻（`--fold 0|1`）。
- 若出生时间存在区间误差（如只记得「下午两三点」），不要强行拍一个单点定死，记录误差范围并在排盘时打开 `--uncertainty-minutes` 对比边界。

## 2. 运行确定性排盘引擎

1. **三盘齐排（公历日期 + 已知具体时间）**：
   ```bash
   python3 scripts/build_chart.py \
     --solar YYYY-MM-DD --hour HH:MM --sex 男 \
     --lat <纬度> --lon <经度> --place "<出生地>" \
     --analysis-year YYYY --format json
   ```
   如需同时生成文本版保存到 `~/.claude/fortune-telling/chart.md`，去掉 `--format json` 重跑一次或同步写入；缺经纬度时去掉 `--lat`/`--lon`（七政命度/立命宫留缺，八字与紫微民用时正常排出）。
2. **仅知大致时间误差区间**：加传 `--uncertainty-minutes <N> --enumerate-scenarios`（≤ 120 分钟），先看四柱、起运与紫微是否跨时辰或跨交节临界。
3. **只知出生日期、完全不知时辰**：先只排八字六字（不编造时辰硬排紫微与七政安命），运行：
   ```bash
   python3 scripts/pai_pan_bazi.py --solar YYYY-MM-DD --sex 男 --place "<出生地>"
   ```
   若出生在立春、节气或近午夜临界附近，加 `--uncertainty-minutes` 或核对当日换日节点，保留待定分支。

## 3. 建档与关联原典

- 用 `templates/chart.template.md` 的格式将排盘结果整理存入 `~/.claude/fortune-telling/chart.md`，并将引擎原始 `--format json` 快照保存在同一私有目录（如 `snapshot.json`），方便后续直接使用 `chart-lookup`。
- 若用户同意保存个人沟通背景与过往印证反馈，另建 `~/.claude/fortune-telling/memory.md`（模板见 `templates/memory.template.md`）。
- 建档后顺手跑一次原典检索，即可开始三盘互参解读：
  ```bash
  python3 scripts/mingli_query.py chart-lookup --chart-json ~/.claude/fortune-telling/snapshot.json --topic general
  ```
