"""Invoke the pinned local Ziwei wrapper without downloading dependencies."""
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess


ZIWEI_DIR = Path(__file__).resolve().parent / "pai_pan_ziwei"


def lunar_calendar_at(day):
    """Check a civil date through the same pinned calendar as the window plan."""
    planner = ZIWEI_DIR.parent / 'ziwei_dynamic_windows.mjs'
    try:
        command = ['node', str(planner), '--start', day.isoformat(),
                   '--end', (day + timedelta(days=1)).isoformat(), '--layer', 'month']
        proc = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', timeout=30)
        return json.loads(proc.stdout)['segments'][0]['calendar_at_start']
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, OverflowError) as exc:
        raise ValueError('无法用锁定紫微历法复核动态查询日期') from exc


def run_ziwei(y, m, d, hh, mm, sex, name, place, age_year=None, birth_year=None, output_format="text", explain_rules=False, temporal_uncertainty=False, *, shichen=None):
    """跑紫微引擎；无 node/依赖时返回降级说明。"""
    # Never let npx silently fetch and execute a missing dependency.
    runner = ZIWEI_DIR / "node_modules" / "tsx" / "dist" / "cli.mjs"
    if not runner.is_file():
        return None, "紫微数据缺失：请先在 scripts/pai_pan_ziwei 执行 npm ci。"
    clock_args = ["--hour", "%02d:%02d" % (hh, mm)] if shichen is None else ["--shichen", shichen]
    cmd = ["node", "--import", "tsx", "pai_pan.ts", "--solar", "%04d-%02d-%02d" % (y, m, d),
           *clock_args, "--sex", sex]
    if output_format != "text":
        cmd += ["--format", output_format]
    if explain_rules:
        cmd += ["--explain-rules"]
    if temporal_uncertainty:
        cmd += ["--temporal-uncertainty"]
    if name:
        cmd += ["--name", name]
    if place:
        cmd += ["--place", place]
    age_year = age_year if age_year is not None else date.today().year
    cmd += ["--age-year", str(age_year)]
    if birth_year is not None:
        cmd += ["--birth-year", str(birth_year)]
    try:
        proc = subprocess.run(cmd, cwd=str(ZIWEI_DIR), capture_output=True, text=True,
                              encoding="utf-8", timeout=120, shell=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:200])
        return proc.stdout.strip(), None
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return None, (
            "紫微数据缺失——内置紫微引擎需要 node 环境：`cd scripts/pai_pan_ziwei && npm ci` "
            "后重跑本脚本（当前失败原因：%s）。也可临时按旧流程从排盘 App 导入。" % exc
        )
