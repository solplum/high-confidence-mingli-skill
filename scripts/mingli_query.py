#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified classical Mingli corpus query CLI (Bazi / Ziwei / Qizheng).

Zero third-party dependencies (Python 3 stdlib only). Reads cleaned JSONL corpora
in references/corpus/ and verifies integrity against manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "references" / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

# Traditional Qiongtong seasonal groupings indexed by stem -> summary notes
CORPUS_FILES = (
    "bazi_qiongtong.jsonl",
    "bazi_classics.jsonl",
    "ziwei_quanshu.jsonl",
    "ziwei_stars_patterns.jsonl",
    "qizheng_classics.jsonl",
    "qizheng_stars.jsonl",
    "qizheng_palaces_geju.jsonl",
    "qizheng_bianyao_shensha.jsonl",
    "qizheng_dongwei_liunian.jsonl",
)

# Domain, synonym, and classical alias expansions used during retrieval
ALIASES: dict[str, tuple[str, ...]] = {
    "事业": ("官禄", "事业", "正官", "七杀", "官星", "功名", "富贵", "立业"),
    "工作": ("官禄", "事业", "正官", "七杀", "印绶"),
    "官禄": ("官禄", "正官", "七杀", "官星", "紫微", "太阳", "天相"),
    "感情": ("夫妻", "妻妾", "婚姻", "桃花", "配偶", "妻星", "夫星", "红鸾", "贪狼"),
    "婚姻": ("夫妻", "妻妾", "婚姻", "合婚", "配偶", "妻宫", "正财", "正官"),
    "夫妻": ("夫妻", "妻妾", "婚姻", "配偶", "妻宫"),
    "妻妾": ("夫妻", "妻妾", "婚姻", "配偶"),
    "财运": ("财帛", "财运", "财富", "正财", "偏财", "禄存", "武曲", "天府", "太阴", "田宅"),
    "财富": ("财帛", "田宅", "正财", "偏财", "禄存", "化禄", "武曲", "天府"),
    "财帛": ("财帛", "正财", "偏财", "禄存", "武曲", "天府"),
    "健康": ("疾厄", "疾病", "调候", "五行", "寿夭", "灾疾"),
    "疾厄": ("疾厄", "疾病", "灾厄", "伤病"),
    "调候": ("调候", "穷通宝鉴", "用神", "喜忌", "寒暖燥湿"),
    "用神": ("用神", "格", "调候", "扶抑", "通关", "病药"),
    "日": ("太阳", "日"),
    "月": ("太阴", "月"),
    "木": ("木星", "岁星", "木"),
    "火": ("火星", "荧惑", "火"),
    "土": ("土星", "镇星", "土"),
    "金": ("金星", "太白", "金"),
    "水": ("水星", "辰星", "水"),
    "木星": ("木星", "岁星"),
    "火星": ("火星", "荧惑"),
    "土星": ("土星", "镇星"),
    "金星": ("金星", "太白"),
    "水星": ("水星", "辰星"),
    "太阳": ("太阳", "日"),
    "太阴": ("太阴", "月"),
    "罗睺": ("罗睺", "罗计", "首"),
    "计都": ("计都", "罗计", "尾"),
    "月孛": ("月孛", "孛"),
    "紫气": ("紫气", "紫炁", "气"),
    "身宫": ("身宫", "身主", "太阴", "安身"),
    "身主": ("身主", "身宫", "太阴", "宫度主"),
    "变曜": ("变曜", "化曜", "十干化曜", "天禄", "天暗", "天福", "天耗", "天荫", "天贵", "天刑", "天印", "天囚", "天权", "管库"),
    "化曜": ("变曜", "化曜", "十干化曜", "天禄", "天权", "天囚"),
    "洞微": ("洞微", "百六", "大限", "限宫", "限度", "行限"),
    "大限": ("洞微", "百六", "大限", "限度", "倒限", "行限"),
    "倒限": ("倒限", "划度", "限度", "大限", "阳刃", "劫煞"),
    "流年": ("流年", "太岁", "小限", "行限", "过宫"),
    "太岁": ("太岁", "流年", "岁驾", "岁破", "丧门", "白虎"),
    "阳刃": ("阳刃", "阴刃", "飞刃", "唐符", "禄勋"),
    "禄勋": ("禄勋", "天禄", "禄神", "国印"),
}

EN_YONG_STAR_NAME: dict[str, str] = {
    "日": "太阳",
    "月": "太阴",
    "木": "木星",
    "火": "火星",
    "土": "土星",
    "金": "金星",
    "水": "水星",
    "紫气": "紫气",
    "罗睺": "罗睺",
    "计都": "计都",
    "月孛": "月孛",
}

TOPIC_MAP: dict[str, dict[str, Any]] = {
    "general": {
        "label": "综合命局",
        "bazi_terms": ("格局", "用神", "调候", "月令"),
        "ziwei_palace": "命宫",
        "qizheng_terms": ("命宫", "命度", "恩用", "入门"),
    },
    "career": {
        "label": "事业官禄",
        "bazi_terms": ("正官", "七杀", "伤官", "印", "格局", "功名"),
        "ziwei_palace": "官禄",
        "qizheng_terms": ("官禄", "官星", "禄", "功名"),
    },
    "love": {
        "label": "感情婚姻",
        "bazi_terms": ("妻", "夫", "婚姻", "正财", "正官", "桃花"),
        "ziwei_palace": "夫妻",
        "qizheng_terms": ("妻妾", "妻星", "夫妻", "男女"),
    },
    "wealth": {
        "label": "财运田宅",
        "bazi_terms": ("正财", "偏财", "食神", "生财", "富"),
        "ziwei_palace": "财帛",
        "qizheng_terms": ("财帛", "财星", "田宅", "禄"),
    },
    "health": {
        "label": "身心疾厄",
        "bazi_terms": ("疾", "寿", "病", "调候", "太过", "不及"),
        "ziwei_palace": "疾厄",
        "qizheng_terms": ("疾厄", "生杀", "恩难", "明晦"),
    },
}


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Corpus manifest not found: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_manifest() -> dict[str, Any]:
    manifest = load_manifest()
    results: dict[str, Any] = {}
    ok = True
    for fname, meta in manifest["files"].items():
        fpath = CORPUS_DIR / fname
        if not fpath.is_file():
            results[fname] = {"ok": False, "reason": "missing"}
            ok = False
            continue
        raw = fpath.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        line_count = sum(1 for ln in raw.decode("utf-8").splitlines() if ln.strip())
        match = sha == meta["sha256"] and line_count == meta["count"] and len(raw) == meta["bytes"]
        if not match:
            ok = False
        results[fname] = {
            "ok": match,
            "count": line_count,
            "expected_count": meta["count"],
            "sha256_match": sha == meta["sha256"],
        }
    return {"ok": ok, "manifest": manifest, "files": results}


def load_records(
    system: str = "all",
    *,
    include_feixing: bool = False,
) -> list[dict[str, Any]]:
    files: list[str]
    if system == "all":
        files = list(CORPUS_FILES)
    elif system == "bazi":
        files = ["bazi_qiongtong.jsonl", "bazi_classics.jsonl"]
    elif system == "ziwei":
        files = ["ziwei_quanshu.jsonl", "ziwei_stars_patterns.jsonl"]
    elif system == "qizheng":
        files = [
            "qizheng_classics.jsonl",
            "qizheng_stars.jsonl",
            "qizheng_palaces_geju.jsonl",
            "qizheng_bianyao_shensha.jsonl",
            "qizheng_dongwei_liunian.jsonl",
        ]
    else:
        raise ValueError(f"Unsupported system: {system}")

    records: list[dict[str, Any]] = []
    for fname in files:
        fpath = CORPUS_DIR / fname
        with fpath.open(encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if not s:
                    continue
                rec = json.loads(s)
                if not include_feixing and rec.get("school") == "feixing_reference":
                    continue
                records.append(rec)
    return records


def expand_terms(query: str) -> tuple[list[str], list[str]]:
    """Split user query into primary tokens and expanded aliases."""
    tokens = [t for t in re.split(r"[\s,，、/|；;+]+", query.strip()) if t]
    primary: list[str] = []
    expanded: list[str] = []
    seen_p: set[str] = set()
    seen_e: set[str] = set()

    def add_p(term: str) -> None:
        if term and term not in seen_p:
            seen_p.add(term)
            primary.append(term)

    def add_e(term: str) -> None:
        if term and term not in seen_p and term not in seen_e:
            seen_e.add(term)
            expanded.append(term)

    for tok in tokens:
        add_p(tok)
        clean = tok.rstrip("宫") if len(tok) >= 3 and tok.endswith("宫") else tok
        if clean != tok:
            add_e(clean)
        for key, vals in ALIASES.items():
            if tok == key or clean == key:
                for v in vals:
                    add_e(v)
    return primary, expanded


def score_record(rec: dict[str, Any], primary: list[str], expanded: list[str]) -> float:
    title = rec.get("title", "")
    category = rec.get("category", "")
    text = rec.get("text", "")
    tags_text = json.dumps(rec.get("tags", {}), ensure_ascii=False)
    score = 0.0

    for t in primary:
        if t in title or t in category:
            score += 8.0
        if t in tags_text:
            score += 6.0
        cnt = text.count(t)
        if cnt:
            score += min(cnt, 5) * 2.5

    for t in expanded:
        if t in title or t in category:
            score += 4.0
        if t in tags_text:
            score += 3.0
        cnt = text.count(t)
        if cnt:
            score += min(cnt, 4) * 1.2

    if score > 0:
        if rec.get("school") == "classical":
            score += 0.6
        if rec.get("layer") == "pattern_engine":
            score += 0.3
        # Slight penalty for continuation chunks so lead chunks appear first
        if "（续" in title:
            score -= 0.4
    return score


def select_balanced(
    scored: list[tuple[float, int, dict[str, Any]]],
    limit: int,
    *,
    per_book_cap: int | None = None,
) -> list[dict[str, Any]]:
    """Select top records with a soft per-book cap before backfilling."""
    if limit <= 0:
        return []
    ordered = [r for _, _, r in scored]
    if per_book_cap is None:
        per_book_cap = max(2, limit // 3)
    picked: list[dict[str, Any]] = []
    picked_ids: set[str] = set()
    book_counts: dict[str, int] = {}

    for rec in ordered:
        b = rec["book"]
        if book_counts.get(b, 0) < per_book_cap:
            picked.append(rec)
            picked_ids.add(rec["id"])
            book_counts[b] = book_counts.get(b, 0) + 1
            if len(picked) >= limit:
                return picked

    for rec in ordered:
        if rec["id"] not in picked_ids:
            picked.append(rec)
            picked_ids.add(rec["id"])
            if len(picked) >= limit:
                return picked
    return picked


def search_records(
    query: str,
    *,
    system: str = "all",
    book: str | None = None,
    layer: str | None = None,
    include_feixing: bool = False,
    limit: int = 8,
) -> list[dict[str, Any]]:
    recs = load_records(system, include_feixing=include_feixing)
    if book:
        recs = [r for r in recs if book in r["book"]]
    if layer:
        recs = [r for r in recs if r["layer"] == layer]

    primary, expanded = expand_terms(query)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, rec in enumerate(recs):
        sc = score_record(rec, primary, expanded)
        if sc > 0:
            scored.append((-sc, idx, rec))
    scored.sort(key=lambda item: (item[0], item[1]))
    cap = limit if book else max(2, limit // 3)
    return select_balanced(scored, limit, per_book_cap=cap)


def lookup_bazi(
    day_stem: str,
    month_branch: str,
    *,
    pattern: str | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    if day_stem not in STEMS:
        raise ValueError(f"Invalid day_stem: {day_stem!r} (expected one of {STEMS})")
    if month_branch not in BRANCHES:
        raise ValueError(f"Invalid month_branch: {month_branch!r} (expected one of {BRANCHES})")

    qt_all = load_records("bazi")
    qiongtong = [
        r
        for r in qt_all
        if r["book"] == "穷通宝鉴"
        and r["tags"].get("day_stem") == day_stem
        and month_branch in r["tags"].get("month_branches", [])
    ]
    # Include general element treatise for the day stem only as fallback if ever missing
    if not qiongtong:
        qiongtong = [
            r
            for r in qt_all
            if r["book"] == "穷通宝鉴" and r["tags"].get("day_stem") == day_stem
        ][:1]

    classics_pool = [r for r in qt_all if r["book"] != "穷通宝鉴"]
    pat_terms = []
    if pattern:
        pat_terms.extend([t for t in re.split(r"[\s,，、/|；;+]+", pattern) if t])
    primary = pat_terms + [day_stem + month_branch, f"{day_stem}日", day_stem]
    expanded = [month_branch, "月令", "用神", "格局"]
    if pat_terms:
        for p in pat_terms:
            _, exp = expand_terms(p)
            expanded.extend(exp)

    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, rec in enumerate(classics_pool):
        sc = score_record(rec, primary, expanded)
        if day_stem in rec["tags"].get("day_stems", []):
            sc += 3.5
        if pat_terms and any(p in rec["title"] or p in rec["text"] for p in pat_terms):
            sc += 6.0
        if sc > 0:
            scored.append((-sc, idx, rec))
    scored.sort(key=lambda item: (item[0], item[1]))
    classics = select_balanced(scored, limit, per_book_cap=max(2, limit // 2))
    return {
        "day_stem": day_stem,
        "month_branch": month_branch,
        "pattern": pattern,
        "qiongtong": qiongtong,
        "classics": classics,
    }


def _find_ziwei_palace(palaces: list[dict[str, Any]], target_name: str) -> dict[str, Any] | None:
    norm = target_name.rstrip("宫")
    for p in palaces:
        if p.get("name", "").rstrip("宫") == norm:
            return p
    return None


def _stars_in_palace(palace: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    if not palace:
        return [], []
    majors = [s["name"] for s in palace.get("stars", []) if s.get("type") == "major"]
    if not majors and palace.get("borrowedStars"):
        majors = list(palace["borrowedStars"])
    sihua = [f"{s['name']}化{s['siHua']}" for s in palace.get("stars", []) if s.get("siHua")]
    return majors, sihua


def lookup_chart(
    snapshot: dict[str, Any],
    *,
    topic: str = "general",
    include_feixing: bool = False,
    limit: int = 5,
) -> dict[str, Any]:
    if topic not in TOPIC_MAP:
        raise ValueError(f"Unsupported topic: {topic!r} (expected one of {tuple(TOPIC_MAP)})")
    cfg = TOPIC_MAP[topic]
    out: dict[str, Any] = {"topic": topic, "topic_label": cfg["label"]}

    # 1. Bazi lookup
    bz = snapshot.get("bazi")
    if bz and "pillars" in bz:
        pillars = bz["pillars"]
        day_stem = pillars["day"][0]
        month_branch = pillars["month"][1]
        shishens = [
            pillars[k][2]
            for k in ("year", "month", "hour")
            if k in pillars and len(pillars[k]) >= 3 and pillars[k][2] not in ("—", "未知", "")
        ]
        pat_query = " ".join(list(dict.fromkeys(shishens)) + list(cfg["bazi_terms"]))
        bz_res = lookup_bazi(day_stem, month_branch, pattern=pat_query, limit=limit)
        bz_res["shishens"] = shishens
        out["bazi"] = bz_res

    # 2. Ziwei lookup
    zw = snapshot.get("ziwei")
    if zw and "chart" in zw:
        chart = zw["chart"]
        palaces = chart.get("palaces", [])
        ming_palace = next((p for p in palaces if p.get("branch") == chart.get("mingGongBranch")), None)
        topic_palace = _find_ziwei_palace(palaces, cfg["ziwei_palace"])
        ming_majors, ming_sihua = _stars_in_palace(ming_palace)
        topic_majors, topic_sihua = _stars_in_palace(topic_palace)
        pat_names = [p.get("name", "") for p in zw.get("patterns", []) if p.get("name")]

        zw_terms = list(
            dict.fromkeys(
                pat_names
                + ming_majors
                + topic_majors
                + [cfg["ziwei_palace"]]
                + ming_sihua
                + topic_sihua
            )
        )
        zw_query = " ".join(zw_terms) if zw_terms else cfg["ziwei_palace"]
        zw_hits = search_records(
            zw_query,
            system="ziwei",
            include_feixing=include_feixing,
            limit=limit,
        )
        out["ziwei"] = {
            "ming_palace": ming_palace.get("name") if ming_palace else None,
            "ming_majors": ming_majors,
            "topic_palace": cfg["ziwei_palace"],
            "topic_majors": topic_majors,
            "matched_patterns": pat_names,
            "records": zw_hits,
        }

    # 3. Qizheng lookup
    qz = snapshot.get("qizheng")
    if qz:
        qz_terms: list[str] = list(cfg["qizheng_terms"])
        if qz.get("day_night"):
            qz_terms.append(qz["day_night"]["type"])
        if qz.get("ming_du"):
            qz_terms.append(f"{qz['ming_du']['mansion']}宿")
            wuxing = qz["ming_du"].get("wuxing")
            if wuxing in EN_YONG_STAR_NAME:
                qz_terms.append(EN_YONG_STAR_NAME[wuxing])
        sg = qz.get("shen_gong")
        if sg:
            qz_terms.append("身主")
            if sg.get("shen_zhu") in EN_YONG_STAR_NAME:
                qz_terms.append(EN_YONG_STAR_NAME[sg["shen_zhu"]])
            if sg.get("shen_du", {}).get("mansion"):
                qz_terms.append(f"{sg['shen_du']['mansion']}宿")
        bs = qz.get("bianyao_shensha")
        if bs and bs.get("bianyao"):
            topic_roles = {
                "general": ("天禄", "天权"),
                "career": ("天禄", "天权"),
                "wealth": ("天福", "天印"),
                "love": ("天荫",),
                "health": ("天囚", "天刑"),
            }.get(topic, ("天禄",))
            for role in topic_roles:
                qz_terms.append(role)
                st_name = bs["bianyao"].get(role, {}).get("star")
                if st_name in EN_YONG_STAR_NAME:
                    qz_terms.append(EN_YONG_STAR_NAME[st_name])
        dw = qz.get("dongwei_daxian") or {}
        dw_active = dw.get("active")
        if dw_active:
            qz_terms.extend(["洞微", "限度"])
            pl_house = dw_active.get("palace_limit", {}).get("house_name")
            if pl_house:
                qz_terms.append(pl_house)
            if dw_active.get("risk_signals"):
                qz_terms.append("倒限")
        en_yong = qz.get("en_yong") or {}
        for rel in ("恩", "难"):
            for m in en_yong.get(rel, []):
                if m in EN_YONG_STAR_NAME:
                    qz_terms.append(EN_YONG_STAR_NAME[m])
        qz_hits = search_records(
            " ".join(dict.fromkeys(qz_terms)),
            system="qizheng",
            limit=limit,
        )
        out["qizheng"] = {
            "ming_du": qz.get("ming_du", {}).get("mansion") if qz.get("ming_du") else None,
            "ming_gong": qz.get("ming_gong", {}).get("zhi") if qz.get("ming_gong") else None,
            "shen_gong": sg.get("zhi") if sg else None,
            "shen_zhu": sg.get("shen_zhu") if sg else None,
            "day_night": qz.get("day_night", {}).get("type") if qz.get("day_night") else None,
            "year_gz": (qz.get("year_gz") or {}).get("year_gz"),
            "active_dongwei": (
                {
                    "palace": dw_active["palace_limit"]["house_name"],
                    "zhi": dw_active["palace_limit"]["zhi"],
                    "degree_mansion": dw_active["degree_limit"]["mansion"],
                }
                if dw_active else None
            ),
            "query_terms": list(dict.fromkeys(qz_terms)),
            "records": qz_hits,
        }

    return out


def format_record(rec: dict[str, Any], *, full_text: bool = False) -> str:
    text = rec["text"].strip()
    if not full_text and len(text) > 360:
        text = text[:360].rstrip() + "……"
    school_note = " [飞星旁参]" if rec.get("school") == "feixing_reference" else ""
    header = f"[{rec['id']}] 《{rec['book']}》 · {rec['title']}{school_note} (source: {rec['source_id']})"
    return f"{header}\n{text}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="高置信命理三盘原典统一检索工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stats = sub.add_parser("stats", help="查看语料统计并校验 SHA-256")
    p_stats.add_argument("--json", action="store_true")

    p_search = sub.add_parser("search", help="跨库/分库检索原典与星曜格局条文")
    p_search.add_argument("--query", "-q", required=True, help="检索关键词（支持空格分隔多词与主题词展开）")
    p_search.add_argument("--system", choices=("all", "bazi", "ziwei", "qizheng"), default="all")
    p_search.add_argument("--book", help="按书名子串过滤")
    p_search.add_argument("--layer", help="按知识层过滤（如 tiaohou/geju/classic/stars/palaces）")
    p_search.add_argument("--include-feixing", action="store_true", help="包含标注为飞星旁参的条文（默认排除）")
    p_search.add_argument("--limit", type=int, default=8)
    p_search.add_argument("--full", action="store_true", help="输出完整条文不截断")
    p_search.add_argument("--json", action="store_true")

    p_bazi = sub.add_parser("bazi-lookup", help="按日干＋月支精查《穷通宝鉴》与子平典籍")
    p_bazi.add_argument("--day-stem", required=True, help="日干（甲~癸）")
    p_bazi.add_argument("--month-branch", required=True, help="月支（子~亥）")
    p_bazi.add_argument("--pattern", help="格局/十神关键词（可选，如 正官、伤官、七杀）")
    p_bazi.add_argument("--limit", type=int, default=6)
    p_bazi.add_argument("--json", action="store_true")

    p_chart = sub.add_parser("chart-lookup", help="读取 build_chart.py JSON 快照自动关联三盘原典")
    p_chart.add_argument("--chart-json", required=True, help="JSON 文件路径或 '-'（标准输入）")
    p_chart.add_argument("--topic", choices=tuple(TOPIC_MAP), default="general")
    p_chart.add_argument("--include-feixing", action="store_true")
    p_chart.add_argument("--limit", type=int, default=4)
    p_chart.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "stats":
        res = verify_manifest()
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res["ok"] else 1
        m = res["manifest"]
        print(f"Corpus total: {m['total_records']} records | Qiongtong coverage: {m['qiongtong_stem_month_coverage']}")
        print(f"Systems: {m['systems']}")
        print("SHA-256 verification:")
        for fname, info in res["files"].items():
            mark = "OK" if info["ok"] else "FAIL"
            print(f"  - {fname}: [{mark}] count={info['count']}/{info['expected_count']}")
        print("Books:")
        for b, cnt in m["books"].items():
            print(f"  - {b}: {cnt}")
        return 0 if res["ok"] else 1

    if args.cmd == "search":
        hits = search_records(
            args.query,
            system=args.system,
            book=args.book,
            layer=args.layer,
            include_feixing=args.include_feixing,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps({"query": args.query, "count": len(hits), "records": hits}, ensure_ascii=False, indent=2))
            return 0
        if not hits:
            print("（未命中相关条文，请换用更具体的星曜/十神/宫位/书名关键词）")
            return 0
        for i, rec in enumerate(hits, 1):
            print(f"--- [{i}] ---")
            print(format_record(rec, full_text=args.full))
        return 0

    if args.cmd == "bazi-lookup":
        res = lookup_bazi(args.day_stem, args.month_branch, pattern=args.pattern, limit=args.limit)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        print(f"## 八字原典检索：{args.day_stem}日 {args.month_branch}月" + (f"（{args.pattern}）" if args.pattern else ""))
        print("\n### 《穷通宝鉴》调候原文")
        for rec in res["qiongtong"]:
            print(format_record(rec, full_text=True))
            print()
        print("### 子平诸书相关条文")
        for rec in res["classics"]:
            print(format_record(rec, full_text=False))
            print()
        return 0

    if args.cmd == "chart-lookup":
        if args.chart_json == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.chart_json).read_text(encoding="utf-8")
        snapshot = json.loads(raw)
        res = lookup_chart(
            snapshot,
            topic=args.topic,
            include_feixing=args.include_feixing,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        print(f"## 三盘原典关联（主题：{res['topic_label']}）")
        if "bazi" in res:
            bz = res["bazi"]
            print(f"\n### 八字：{bz['day_stem']}日 {bz['month_branch']}月（十神：{'、'.join(bz['shishens']) or '无'}）")
            for rec in bz["qiongtong"]:
                print(format_record(rec, full_text=True))
                print()
            for rec in bz["classics"]:
                print(format_record(rec, full_text=False))
                print()
        if "ziwei" in res:
            zw = res["ziwei"]
            print(
                f"\n### 紫微：命宫({'、'.join(zw['ming_majors']) or '空'}) / {zw['topic_palace']}({'、'.join(zw['topic_majors']) or '空'})"
                + (f"｜格局：{'、'.join(zw['matched_patterns'])}" if zw["matched_patterns"] else "")
            )
            for rec in zw["records"]:
                print(format_record(rec, full_text=False))
                print()
        if "qizheng" in res:
            qz = res["qizheng"]
            dw_txt = ""
            if qz.get("active_dongwei"):
                adw = qz["active_dongwei"]
                dw_txt = f" / 大限 {adw['palace']}({adw['zhi']}·{adw['degree_mansion']}度)"
            sg_txt = f" / 身宫 {qz['shen_gong']}({qz['shen_zhu']}主)" if qz.get("shen_gong") else ""
            print(
                f"\n### 七政：命度 {qz['ming_du'] or '未算'} / 立命 {qz['ming_gong'] or '未算'}{sg_txt} / {qz['day_night'] or '未分昼夜'}{dw_txt}"
            )
            for rec in qz["records"]:
                print(format_record(rec, full_text=False))
                print()
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
