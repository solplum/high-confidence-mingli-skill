#!/usr/bin/env python3
"""Deterministic corpus builder for 《张果星宗》 Vol 2/3 (变曜神煞) & Vol 16-17 (洞微大限/倒限/流年).

Reads daizhigev20 Public Domain 张果星宗.txt, cleans verified OCR '?' on 罗睺 and marks
unverifiable single missing glyphs as [缺字] (never guesses), chunks cleanly on classical
section headings (~350-650 chars per record, matching existing qizheng_*.jsonl granularity),
writes:
  - references/corpus/qizheng_bianyao_shensha.jsonl
  - references/corpus/qizheng_dongwei_liunian.jsonl
and updates references/corpus/manifest.json with exact record counts, byte sizes, and SHA-256.
Existing 7 JSONL files are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "references" / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

PUA_RE = re.compile(r"[\ue000-\uf8ff]")

VOL2_HEAD_RE = re.compile(
    r"^(诸星起例|变曜|天禄|天暗|天福|天耗|天荫|天贵|天刑|天印|天囚|天权|"
    r"科名|科甲|文星|魁星|官星|印星|催官|禄神|喜神|爵星|天马地驿|卦气|"
    r"天元禄|地元禄|人元禄|天经|地纬|职元|局主|斗标|注受|天乙|玉堂|文昌|天厨|"
    r"岁殿|岁驾|禄勋|阳刃|唐符|国印|天雄|地雌|年符|月符|大耗|天耗|地耗|"
    r"月廉|月煞|值难|的杀|咸池|大煞|空亡|孤虚|孤辰|寡宿|三刑|六害|劫杀|亡神|"
    r"天罗地网|反吟伏吟|驾前神杀歌|驾后神煞歌|羊刃详解例|马前诸杀例|"
    r"五行长生例|天干化曜星例|天干吉凶星例|地支吉凶星例|诸吉星捷法例|月建吉凶星例)"
)


def clean_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("罗?", "罗睺")
    text = text.replace("?", "[缺字]")
    out_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(out_lines)


def split_long_text(text: str, max_chars: int = 620) -> list[str]:
    """Split long classical text on sentence/newline boundaries into ~350-620 char chunks."""
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[。！？\n])", text)
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if not p:
            continue
        if len(buf) + len(p) <= max_chars:
            buf += p
        else:
            if buf.strip():
                chunks.append(buf.strip())
            if len(p) > max_chars:
                subparts = re.split(r"(?<=[，、；])", p)
                sub = ""
                for sp in subparts:
                    if len(sub) + len(sp) <= max_chars:
                        sub += sp
                    else:
                        if sub.strip():
                            chunks.append(sub.strip())
                        sub = sp
                buf = sub
            else:
                buf = p
    if buf.strip():
        chunks.append(buf.strip())
    if len(chunks) >= 2 and len(chunks[-1]) < 60:
        chunks[-2] = chunks[-2] + "\n" + chunks[-1]
        chunks.pop()
    return chunks


def extract_vol2_3_bianyao_shensha(lines: list[str]) -> list[dict]:
    """Extract Vol 2 (L327..L1027) and Vol 3 吉星/月建 (L1029..L1052)."""
    sections: list[tuple[str, str, list[str]]] = []
    cur_cat = "卷二·十干变曜与诸星起例"
    cur_title = "变曜（十干化曜总诀）"
    buf: list[str] = []

    def flush():
        nonlocal buf
        txt = clean_text("\n".join(buf))
        if len(txt) >= 25:
            sections.append((cur_cat, cur_title, [txt]))
        buf = []

    for idx in range(327, 1053):
        s = lines[idx - 1].strip()
        if not s or s in ("张果星宗二", "张果星宗三"):
            continue
        if idx >= 1029:
            cat = "卷三·诸吉星捷法与月建神煞"
        elif idx >= 869:
            cat = "卷二·马前诸杀与干支吉凶星表"
        elif idx >= 603:
            cat = "卷二·年干支地煞与驾前驾后神煞"
        elif idx >= 434:
            cat = "卷二·年干诸星（科名文魁官印禄喜）"
        else:
            cat = "卷二·十干变曜（管库星）"

        m = VOL2_HEAD_RE.match(s)
        is_heading = bool(
            m
            and len(s) <= 45
            and not s.endswith("，")
            and (m.group(0) == s or s[len(m.group(0)):].startswith(("、", "：", "（")))
        )
        if is_heading:
            flush()
            cur_cat = cat
            cur_title = s
            buf = [s]
        else:
            buf.append(s)
    flush()

    records: list[dict] = []
    seq = 1
    for cat, title, texts in sections:
        full_txt = "\n".join(texts)
        chunks = split_long_text(full_txt, max_chars=620)
        for ci, ch in enumerate(chunks):
            rec_title = title if ci == 0 else f"{title}（续{ci}）"
            tags = {}
            for kw in ("变曜", "天禄", "天暗", "天福", "天耗", "天荫", "天贵", "天刑", "天印", "天囚", "天权",
                       "科名", "科甲", "文星", "魁星", "官星", "印星", "催官", "禄神", "喜神",
                       "天乙", "玉堂", "文昌", "禄勋", "阳刃", "阴刃", "唐符", "国印", "劫杀", "亡神", "空亡", "驾前", "驾后"):
                if kw in ch or kw in rec_title:
                    tags.setdefault("topics", []).append(kw)
            records.append({
                "id": f"qzbs-{seq:04d}",
                "system": "qizheng",
                "book": "张果星宗·变曜神煞",
                "era": "唐宋明清",
                "layer": "bianyao_shensha",
                "category": cat,
                "title": rec_title,
                "tags": tags,
                "text": ch,
                "school": "classical",
                "note": "辑自 daizhigev20《张果星宗》卷二至卷三；已核 0 PUA，7 处罗? 校为罗睺，1 处孤字标 [缺字]",
                "source_id": "daizhigev20/易藏/术数/张果星宗.txt#vol2-3",
            })
            seq += 1
    return records


def extract_vol3_16_17_dongwei_liunian(lines: list[str]) -> list[dict]:
    """Extract Vol 3 定行限度法 (L1054..L1056) and Vol 16-17 (L1596..L1668)."""
    blocks: list[tuple[str, str, str]] = []

    v3_txt = clean_text("\n".join(lines[1053:1056]))
    blocks.append(("卷三·定行限度法", "定行限度法（十二宫洞微行限年限与岁行度数）", v3_txt))

    for vol_label, start_ln, end_ln in (
        ("卷十六·洞微百六限与倒限", 1596, 1639),
        ("卷十七·统论限说与流年论", 1640, 1668),
    ):
        raw_vol = "\n".join(lines[start_ln - 1:end_ln])
        raw_vol = re.sub(r"张果星宗十[六七]", "", raw_vol)
        parts = re.split(r"(?=【[^】]{1,40}】)", raw_vol)
        for p in parts:
            p_clean = clean_text(p)
            if len(p_clean) < 25:
                continue
            hm = re.match(r"^【([^】]{1,40})】", p_clean)
            title = hm.group(1) if hm else vol_label
            blocks.append((vol_label, title, p_clean))

    records: list[dict] = []
    seq = 1
    for cat, title, txt in blocks:
        chunks = split_long_text(txt, max_chars=620)
        for ci, ch in enumerate(chunks):
            rec_title = title if ci == 0 else f"{title}（续{ci}）"
            tags = {}
            for kw in ("洞微", "百六", "大限", "限度", "限宫", "倒限", "划度", "流年", "太岁", "小限",
                       "阳刃", "劫煞", "劫杀", "亡神", "余奴", "恩星", "难星", "身主", "命度"):
                if kw in ch or kw in rec_title:
                    tags.setdefault("topics", []).append(kw)
            records.append({
                "id": f"qzdl-{seq:04d}",
                "system": "qizheng",
                "book": "张果星宗·洞微限度与流年",
                "era": "唐宋明清",
                "layer": "dongwei_liunian",
                "category": cat,
                "title": rec_title,
                "tags": tags,
                "text": ch,
                "school": "classical",
                "note": "辑自 daizhigev20《张果星宗》卷三、卷十六、卷十七；已核 0 PUA，罗? 校为罗睺，1 处孤字标 [缺字]",
                "source_id": "daizhigev20/易藏/术数/张果星宗.txt#vol3,16-17",
            })
            seq += 1
    return records


def write_jsonl(path: Path, records: list[dict]) -> dict:
    for r in records:
        txt = r["text"].strip()
        assert len(txt) >= 20, f"Too short: {r['id']}"
        assert not PUA_RE.search(txt), f"PUA leak: {r['id']}"
        assert "?" not in txt, f"Raw '?' leak: {r['id']}"
        assert "<!--" not in txt and "<script" not in txt, f"HTML leak: {r['id']}"
    raw = ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return {
        "count": len(records),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def rebuild_manifest() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ordered_files = (
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
    files_meta: dict[str, dict] = {}
    systems: dict[str, int] = {"bazi": 0, "ziwei": 0, "qizheng": 0}
    books: dict[str, int] = {}
    total = 0

    for fname in ordered_files:
        fpath = CORPUS_DIR / fname
        raw = fpath.read_bytes()
        lines = [ln for ln in raw.decode("utf-8").splitlines() if ln.strip()]
        for ln in lines:
            rec = json.loads(ln)
            systems[rec["system"]] = systems.get(rec["system"], 0) + 1
            books[rec["book"]] = books.get(rec["book"], 0) + 1
            total += 1
        files_meta[fname] = {
            "count": len(lines),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    manifest["built_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["total_records"] = total
    manifest["systems"] = systems
    manifest["books"] = books
    manifest["files"] = files_meta
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build cleaned Qizheng Vol 2/3/16/17 JSONL corpora and update manifest.json")
    parser.add_argument("--source", type=Path, required=True, help="Path to daizhigev20 张果星宗.txt")
    args = parser.parse_args()

    lines = args.source.read_text(encoding="utf-8", errors="replace").splitlines()
    bs_recs = extract_vol2_3_bianyao_shensha(lines)
    dl_recs = extract_vol3_16_17_dongwei_liunian(lines)

    bs_meta = write_jsonl(CORPUS_DIR / "qizheng_bianyao_shensha.jsonl", bs_recs)
    dl_meta = write_jsonl(CORPUS_DIR / "qizheng_dongwei_liunian.jsonl", dl_recs)
    manifest = rebuild_manifest()
    print(json.dumps({
        "qizheng_bianyao_shensha": bs_meta,
        "qizheng_dongwei_liunian": dl_meta,
        "total_records": manifest["total_records"],
        "systems": manifest["systems"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
