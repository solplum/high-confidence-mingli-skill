"""Classical Qizheng Siyu natal rules: 身宫/身主/身度, 十二人事宫, 年干变曜与神煞, 星辰状态.

All rule tables follow 《张果星宗》 (Guolao orthodox school: Vol. 1 宫分/入门看法,
Vol. 2 诸星起例/十干变曜/神煞, Vol. 15 喜宫歌/升殿/入庙/乐宫/忌躔) cross-checked against
《星学大成》 (daizhigev20 Public Domain editions). Pure functions; zero third-party deps.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pai_pan_bazi as bazi

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

LUMINARIES_WUXING: dict[str, str] = {
    "日": "火", "月": "水", "木": "木", "火": "火", "土": "土",
    "金": "金", "水": "水", "罗睺": "火", "计都": "土", "月孛": "水", "紫气": "木",
}
MANSION_WX_TO_PHASE: dict[str, str] = {
    "木": "木", "火": "火", "土": "土", "金": "金", "水": "水", "日": "火", "月": "水",
}
WUXING_SHENG: dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE: dict[str, str] = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}

# 《张果星宗》卷一「宫分所属」：十二支宫主星与宫主五行
PALACE_RULER: dict[str, str] = {
    "子": "土", "丑": "土", "寅": "木", "卯": "火", "辰": "金", "巳": "水",
    "午": "日", "未": "月", "申": "水", "酉": "金", "戌": "火", "亥": "木",
}
PALACE_RULER_WUXING: dict[str, str] = {
    zhi: LUMINARIES_WUXING[star] for zhi, star in PALACE_RULER.items()
}
PALACE_CONSTELLATION: dict[str, str] = {
    "子": "宝瓶", "丑": "磨羯", "寅": "人马", "卯": "天蝎", "辰": "天秤", "巳": "双女",
    "午": "狮子", "未": "巨蟹", "申": "阴阳", "酉": "金牛", "戌": "白羊", "亥": "双鱼",
}

# 《张果星宗》卷一 / 《星学大成》人事十二宫（自命宫起逆地支布列）
TWELVE_HOUSES: tuple[str, ...] = (
    "命宫", "财帛", "兄弟", "田宅", "男女", "奴仆",
    "妻妾", "疾厄", "迁移", "官禄", "福德", "相貌",
)
STRONG_HOUSES = frozenset({"命宫", "官禄", "田宅", "妻妾", "男女", "福德", "财帛"})
WEAK_HOUSES = frozenset({"兄弟", "奴仆", "疾厄", "相貌", "迁移"})

# 《张果星宗》卷五/卷十五：七政升殿宿表（四余无殿）
SHENGDIAN_MANSIONS: dict[str, frozenset[str]] = {
    "日": frozenset({"房", "虚", "昴", "星"}),
    "月": frozenset({"心", "危", "毕", "张"}),
    "木": frozenset({"角", "斗", "奎", "井"}),
    "火": frozenset({"尾", "室", "觜", "翼"}),
    "土": frozenset({"氐", "女", "胃", "柳"}),
    "金": frozenset({"亢", "牛", "娄", "鬼"}),
    "水": frozenset({"箕", "壁", "参", "轸"}),
}

# 《张果星宗》卷十五：入庙宫表、乐宫表、忌躔失陷表
RU_MIAO_PALACES: dict[str, frozenset[str]] = {
    "土": frozenset({"丑"}), "罗睺": frozenset({"寅", "午"}), "火": frozenset({"卯"}),
    "金": frozenset({"辰"}), "计都": frozenset({"巳", "亥"}), "水": frozenset({"午"}),
    "月孛": frozenset({"未"}), "紫气": frozenset({"申"}), "日": frozenset({"戌"}),
    "月": frozenset({"戌"}), "木": frozenset({"亥"}),
}
LE_GONG_PALACES: dict[str, frozenset[str]] = {
    "土": frozenset({"子", "丑"}), "木": frozenset({"寅", "亥"}),
    "火": frozenset({"卯", "戌"}), "金": frozenset({"辰", "酉"}),
    "水": frozenset({"巳", "申"}), "日": frozenset({"午"}), "月": frozenset({"未"}),
}
SHIXIAN_PALACE_LABELS: dict[tuple[str, str], str] = {
    ("火", "酉"): "火烧牛角（失陷）",
    ("水", "戌"): "水漂羊（失陷）",
    ("土", "巳"): "土埋双女（失陷）",
    ("木", "子"): "木打宝瓶（失陷）",
    ("金", "寅"): "金骑人马（失陷）",
}

# 《张果星宗》卷一「明晦」共同集（孛/计在传本明晦两条互倒，单独标注）
DAY_STARS_COMMON = frozenset({"日", "木", "土", "水", "紫气"})
NIGHT_STARS_COMMON = frozenset({"月", "火", "金", "罗睺"})

# 《张果星宗》卷二：十干变曜（甲火乙孛丙属木，丁金戊土己太阴，庚水辛气壬计癸罗；太阳不与）
BIANYAO_STAR_SEQ: tuple[str, ...] = ("火", "月孛", "木", "金", "土", "月", "水", "紫气", "计都", "罗睺")
BIANYAO_ROLE_SEQ: tuple[str, ...] = ("天禄", "天暗", "天福", "天耗", "天荫", "天贵", "天刑", "天印", "天囚", "天权")
BIANYAO_MANAGED_HOUSE: dict[str, str] = {
    "天禄": "官禄",
    "天暗": "相貌",
    "天福": "财帛/福德/迁移",
    "天耗": "兄弟",
    "天荫": "妻妾",
    "天贵": "男女",
    "天刑": "奴仆",
    "天印": "田宅",
    "天囚": "疾厄",
    "天权": "命宫",
}

# 《张果星宗》卷二 + 《星学大成》校勘后的年干诸星表
STEM_KEMING: dict[str, str] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
STEM_WENXING: dict[str, str] = {
    "甲": "罗睺", "乙": "计都", "丙": "金", "丁": "火", "戊": "金",
    "己": "紫气", "庚": "木", "辛": "土", "壬": "日", "癸": "月",
}
STEM_KUIXING: dict[str, str] = {
    "甲": "月", "乙": "日", "丙": "罗睺", "丁": "计都", "戊": "火",
    "己": "金", "庚": "木", "辛": "月孛", "壬": "紫气", "癸": "水",
}
STEM_GUANXING: dict[str, str] = {
    "甲": "紫气", "乙": "水", "丙": "罗睺", "丁": "计都", "戊": "月孛",
    "己": "火", "庚": "金", "辛": "木", "壬": "月", "癸": "土",
}
STEM_YINXING: dict[str, str] = {
    "甲": "木", "乙": "日", "丙": "火", "丁": "月", "戊": "土",
    "己": "罗睺", "庚": "金", "辛": "计都", "壬": "水", "癸": "月孛",
}
STEM_CUIGUAN: dict[str, str] = {
    "甲": "金", "乙": "水", "丙": "日", "丁": "罗睺", "戊": "木",
    "己": "紫气", "庚": "月孛", "辛": "土", "壬": "月", "癸": "计都",
}
STEM_LUSHEN: dict[str, tuple[str, ...]] = {
    "甲": ("木", "月孛"), "乙": ("水",), "丙": ("计都",), "丁": ("罗睺",), "戊": ("土",),
    "己": ("火",), "庚": ("金",), "辛": ("紫气",), "壬": ("日",), "癸": ("月",),
}
STEM_XISHEN: dict[str, str] = {
    "甲": "罗睺", "乙": "计都", "丙": "紫气", "丁": "水", "戊": "月",
    "己": "土", "庚": "金", "辛": "木", "壬": "月孛", "癸": "火",
}

STEM_TIANYI_DAY: dict[str, str] = {
    "甲": "未", "乙": "申", "丙": "酉", "丁": "亥", "戊": "丑",
    "己": "子", "庚": "丑", "辛": "寅", "壬": "卯", "癸": "巳",
}
STEM_YUTANG_NIGHT: dict[str, str] = {
    "甲": "丑", "乙": "子", "丙": "亥", "丁": "酉", "戊": "未",
    "己": "申", "庚": "未", "辛": "午", "壬": "巳", "癸": "卯",
}
STEM_WENCHANG: dict[str, str] = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "戌", "壬": "寅", "癸": "卯",
}
STEM_TIANCHU: dict[str, str] = {
    "甲": "巳", "乙": "午", "丙": "子", "丁": "巳", "戊": "午",
    "己": "申", "庚": "寅", "辛": "午", "壬": "酉", "癸": "亥",
}
STEM_LUXUN: dict[str, str] = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
    "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}

BRANCH_JUEXING: dict[str, str] = {
    "子": "土", "丑": "水", "寅": "木", "卯": "紫气", "辰": "月孛", "巳": "木",
    "午": "水", "未": "火", "申": "土", "酉": "金", "戌": "金", "亥": "火",
}
SANHE_TIANMA_DIYI: dict[str, tuple[str, str]] = {
    "申": ("火", "木"), "子": ("火", "木"), "辰": ("火", "木"),
    "寅": ("水", "金"), "午": ("水", "金"), "戌": ("水", "金"),
    "亥": ("木", "火"), "卯": ("木", "火"), "未": ("木", "火"),
    "巳": ("计都", "水"), "酉": ("计都", "水"), "丑": ("计都", "水"),
}
SANHE_XIANCHI: dict[str, str] = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "巳": "午", "酉": "午", "丑": "午",
    "亥": "子", "卯": "子", "未": "子",
}
SANHE_JIESHA: dict[str, str] = {
    "申": "巳", "子": "巳", "辰": "巳",
    "寅": "亥", "午": "亥", "戌": "亥",
    "巳": "寅", "酉": "寅", "丑": "寅",
    "亥": "申", "卯": "申", "未": "申",
}
SANHE_WANGSHEN: dict[str, str] = {
    "申": "亥", "子": "亥", "辰": "亥",
    "寅": "巳", "午": "巳", "戌": "巳",
    "巳": "申", "酉": "申", "丑": "申",
    "亥": "寅", "卯": "寅", "未": "寅",
}
BRANCH_DISHA_POSUI: dict[str, str] = {
    "子": "巳", "午": "巳", "卯": "巳", "酉": "巳",
    "寅": "酉", "申": "酉", "巳": "酉", "亥": "酉",
    "辰": "丑", "戌": "丑", "丑": "丑", "未": "丑",
}
BRANCH_DASHA_FEILIAN: dict[str, str] = {
    "子": "申", "丑": "酉", "寅": "戌", "卯": "巳", "辰": "午", "巳": "未",
    "午": "寅", "未": "卯", "申": "辰", "酉": "亥", "戌": "子", "亥": "丑",
}
BRANCH_GUCHEN_GUASU: dict[str, tuple[str, str]] = {
    "寅": ("巳", "丑"), "卯": ("巳", "丑"), "辰": ("巳", "丑"),
    "巳": ("申", "辰"), "午": ("申", "辰"), "未": ("申", "辰"),
    "申": ("亥", "未"), "酉": ("亥", "未"), "戌": ("亥", "未"),
    "亥": ("寅", "戌"), "子": ("寅", "戌"), "丑": ("寅", "戌"),
}

# 《张果星宗》卷二：驾前十二神煞歌（自岁驾宫顺数 0..11）
JIAQIAN_LABELS: tuple[str, ...] = (
    "岁驾/剑锋/伏尸",
    "天空",
    "丧门/地雌",
    "贯索/勾神",
    "官符/五鬼/飞符",
    "死符/小耗/月德",
    "岁破/大耗/阑干",
    "暴败/天厄",
    "白虎/天雄",
    "天德/绞杀/卷舌",
    "吊客/天狗",
    "病符/蓦越",
)


def year_ganzhi_at_instant(dt_bj: datetime) -> dict[str, Any]:
    """Return 立春-bounded year stem/branch using pai_pan_bazi's exact VSOP87 solar term."""
    lichun = bazi.solar_term_beijing(dt_bj.year, 315)
    eff_year = dt_bj.year - 1 if dt_bj < lichun else dt_bj.year
    gz_idx = bazi.year_gz_index(eff_year)
    gan = GAN[gz_idx % 10]
    zhi = ZHI[gz_idx % 12]
    return {
        "year_effective": eff_year,
        "year_gan": gan,
        "year_zhi": zhi,
        "year_gz": gan + zhi,
        "boundary": "lichun-instant",
        "lichun_bj": lichun.isoformat(),
    }


def build_twelve_houses(ming_gong_zhi: str, bodies: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build Guolao 12 human-affairs houses (命宫起逆地支布列)."""
    ming_idx = ZHI.index(ming_gong_zhi)
    occupants_by_zhi: dict[str, list[str]] = {z: [] for z in ZHI}
    for star, info in bodies.items():
        p = info.get("palace")
        if p in occupants_by_zhi:
            occupants_by_zhi[p].append(star)

    houses = []
    for offset, house_name in enumerate(TWELVE_HOUSES):
        zhi_idx = (ming_idx - offset) % 12
        zhi = ZHI[zhi_idx]
        opp_zhi = ZHI[(zhi_idx + 6) % 12]
        trines = (ZHI[(zhi_idx + 4) % 12], ZHI[(zhi_idx + 8) % 12])
        houses.append({
            "index": offset + 1,
            "name": house_name,
            "zhi": zhi,
            "constellation": PALACE_CONSTELLATION[zhi],
            "ruler": PALACE_RULER[zhi],
            "ruler_wuxing": PALACE_RULER_WUXING[zhi],
            "strength": "强宫" if house_name in STRONG_HOUSES else "弱宫",
            "occupants": occupants_by_zhi[zhi],
            "opposite_zhi": opp_zhi,
            "opposite_occupants": occupants_by_zhi[opp_zhi],
            "trine_zhis": list(trines),
        })
    return houses


def compute_shen_gong(
    bodies: dict[str, dict[str, Any]],
    twelve_houses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute Guolao orthodox 身宫/身主/身度 (太阴所在宫=身宫，该宫主=身主，太阴躔宿=身度)."""
    moon = bodies["月"]
    shen_zhi = moon["palace"]
    ruler = PALACE_RULER[shen_zhi]
    ruler_wx = PALACE_RULER_WUXING[shen_zhi]
    ruler_body = bodies.get(ruler)
    house_name = None
    if twelve_houses:
        for h in twelve_houses:
            if h["zhi"] == shen_zhi:
                house_name = h["name"]
                break
    return {
        "method": "guolao-moon-palace",
        "zhi": shen_zhi,
        "constellation": PALACE_CONSTELLATION[shen_zhi],
        "house_name": house_name,
        "shen_zhu": ruler,
        "shen_zhu_wuxing": ruler_wx,
        "shen_zhu_palace": ruler_body["palace"] if ruler_body else None,
        "shen_zhu_mansion": ruler_body["mansion"] if ruler_body else None,
        "shen_du": {
            "mansion": moon["mansion"],
            "mansion_deg": moon["mansion_deg"],
            "mansion_wx": moon["mansion_wx"],
            "du_zhu_wuxing": MANSION_WX_TO_PHASE[moon["mansion_wx"]],
            "star": moon["star"],
            "sidereal": moon["sidereal"],
        },
        "note": "果老正宗以太阴所躔宫为身宫、其宫主为身主、太阴躔宿为身度；夜生人重身度主",
    }


def _xigong_relation(star_wx: str, palace_wx: str) -> str:
    if star_wx == palace_wx:
        return "庙堂"
    if WUXING_SHENG[palace_wx] == star_wx:
        return "乐乡"
    if WUXING_SHENG[star_wx] == palace_wx:
        return "旺度"
    if WUXING_KE[star_wx] == palace_wx:
        return "入制"
    return "刑伤"


def compute_star_states(
    bodies: dict[str, dict[str, Any]],
    day_night_type: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute classical star dignity & day/night clarity from states-tables.md rules."""
    states: dict[str, dict[str, Any]] = {}
    for star, info in bodies.items():
        mansion = info["mansion"]
        palace = info["palace"]
        star_wx = LUMINARIES_WUXING[star]
        palace_wx = PALACE_RULER_WUXING[palace]
        shengdian = mansion in SHENGDIAN_MANSIONS.get(star, frozenset())
        xigong = _xigong_relation(star_wx, palace_wx)
        ru_miao = palace in RU_MIAO_PALACES.get(star, frozenset())
        le_gong = palace in LE_GONG_PALACES.get(star, frozenset())
        shixian = SHIXIAN_PALACE_LABELS.get((star, palace))

        ming_hui = None
        ming_hui_note = None
        if day_night_type in ("昼生", "夜生"):
            is_day = day_night_type == "昼生"
            if star in DAY_STARS_COMMON:
                ming_hui = "向明" if is_day else "背晦"
            elif star in NIGHT_STARS_COMMON:
                ming_hui = "向明" if not is_day else "背晦"
            else:
                ming_hui = "传本异文待参"
                ming_hui_note = "《张果星宗》明晦两条对孛/计互倒，按共同集标注"

        states[star] = {
            "wuxing": star_wx,
            "palace": palace,
            "palace_ruler": PALACE_RULER[palace],
            "palace_ruler_wuxing": palace_wx,
            "mansion": mansion,
            "shengdian": shengdian,
            "xigong_relation": xigong,
            "ru_miao": ru_miao,
            "le_gong": le_gong,
            "shixian": shixian,
            "ming_hui": ming_hui,
            **({"ming_hui_note": ming_hui_note} if ming_hui_note else {}),
        }
    return states


def compute_bianyao_shensha(
    year_gan: str,
    year_zhi: str,
    *,
    ming_gong_zhi: str | None = None,
    day_night_type: str | None = None,
    bodies: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute Guolao Vol. 2 ten-stem 变曜 (管库星) and full year stem/branch 神煞."""
    g_idx = GAN.index(year_gan)
    z_idx = ZHI.index(year_zhi)
    is_yang_stem = (g_idx % 2) == 0

    def star_loc(star_name: str) -> dict[str, Any]:
        if not bodies or star_name not in bodies:
            return {"star": star_name, "palace": None, "mansion": None}
        b = bodies[star_name]
        return {"star": star_name, "palace": b["palace"], "mansion": b["mansion"]}

    bianyao: dict[str, dict[str, Any]] = {}
    by_star: dict[str, str] = {}
    for r_idx, role in enumerate(BIANYAO_ROLE_SEQ):
        star_name = BIANYAO_STAR_SEQ[(g_idx + r_idx) % 10]
        loc = star_loc(star_name)
        bianyao[role] = {
            "star": star_name,
            "managed_house": BIANYAO_MANAGED_HOUSE[role],
            "palace": loc["palace"],
            "mansion": loc["mansion"],
        }
        by_star[star_name] = role

    kejia_star = None
    if ming_gong_zhi is not None:
        opp_ming = ZHI[(ZHI.index(ming_gong_zhi) + 6) % 12]
        kejia_star = PALACE_RULER[opp_ming]
    stem_stars = {
        "科名": star_loc(STEM_KEMING[year_gan]),
        "科甲": star_loc(kejia_star) if kejia_star else {"star": None, "palace": None, "mansion": None},
        "文星": star_loc(STEM_WENXING[year_gan]),
        "魁星": star_loc(STEM_KUIXING[year_gan]),
        "官星": star_loc(STEM_GUANXING[year_gan]),
        "印星": star_loc(STEM_YINXING[year_gan]),
        "催官": star_loc(STEM_CUIGUAN[year_gan]),
        "禄神": [star_loc(s) for s in STEM_LUSHEN[year_gan]],
        "喜神": star_loc(STEM_XISHEN[year_gan]),
        "爵星": star_loc(BRANCH_JUEXING[year_zhi]),
        "天马": star_loc(SANHE_TIANMA_DIYI[year_zhi][0]),
        "地驿": star_loc(SANHE_TIANMA_DIYI[year_zhi][1]),
    }

    luxun = STEM_LUXUN[year_gan]
    luxun_idx = ZHI.index(luxun)
    ren_zhi = ZHI[(luxun_idx + 1) % 12]
    ren_name = "阳刃" if is_yang_stem else "阴刃"
    tangfu_feiren = ZHI[(luxun_idx + 7) % 12]  # 禄前八位（含禄起1，即 +7）= 刃之对宫
    guoyin = ZHI[(luxun_idx + 8) % 12]         # 禄前九位（含禄起1，即 +8）
    suidian = ZHI[(z_idx + g_idx) % 12]        # 岁驾宫起甲顺数至生年干

    xun_start_zhi = (z_idx - g_idx) % 12
    kongwang = [ZHI[(xun_start_zhi - 2) % 12], ZHI[(xun_start_zhi - 1) % 12]]
    guxu = [ZHI[(ZHI.index(k) + 6) % 12] for k in kongwang]
    guchen, guasu = BRANCH_GUCHEN_GUASU[year_zhi]

    jiaqian_12 = {
        ZHI[(z_idx + step) % 12]: JIAQIAN_LABELS[step]
        for step in range(12)
    }
    hongluan = ZHI[(ZHI.index("卯") - z_idx) % 12]
    tianxi = ZHI[(ZHI.index(hongluan) + 6) % 12]
    xueren_jieshen = ZHI[(ZHI.index("戌") - z_idx) % 12]
    tianku = ZHI[(ZHI.index("午") - z_idx) % 12]
    pitou = ZHI[(ZHI.index("辰") - z_idx) % 12]
    jiahou = {
        "红鸾": hongluan,
        "天喜": tianxi,
        "血刃/浮沉/解神": xueren_jieshen,
        "天哭": tianku,
        "披头": pitou,
    }

    tianyi_day = STEM_TIANYI_DAY[year_gan]
    yutang_night = STEM_YUTANG_NIGHT[year_gan]
    primary_guiren = None
    if day_night_type == "昼生":
        primary_guiren = {"type": "天乙（昼贵）", "zhi": tianyi_day}
    elif day_night_type == "夜生":
        primary_guiren = {"type": "玉堂（夜贵）", "zhi": yutang_night}

    palace_shensha = {
        "天乙昼贵": tianyi_day,
        "玉堂夜贵": yutang_night,
        "当值贵人": primary_guiren,
        "文昌": STEM_WENCHANG[year_gan],
        "天厨": STEM_TIANCHU[year_gan],
        "岁驾": year_zhi,
        "岁殿": suidian,
        "禄勋": luxun,
        ren_name: ren_zhi,
        "刃星": PALACE_RULER[ren_zhi],
        "唐符飞刃": tangfu_feiren,
        "国印": guoyin,
        "地雌丧门": ZHI[(z_idx + 2) % 12],
        "年符官符": ZHI[(z_idx + 4) % 12],
        "小耗": ZHI[(z_idx + 5) % 12],
        "大耗岁破": ZHI[(z_idx + 6) % 12],
        "天雄白虎": ZHI[(z_idx + 8) % 12],
        "咸池": SANHE_XIANCHI[year_zhi],
        "劫杀": SANHE_JIESHA[year_zhi],
        "亡神": SANHE_WANGSHEN[year_zhi],
        "的杀破碎": BRANCH_DISHA_POSUI[year_zhi],
        "大煞飞廉": BRANCH_DASHA_FEILIAN[year_zhi],
        "孤辰": guchen,
        "寡宿": guasu,
        "空亡": kongwang,
        "孤虚": guxu,
        "天罗地网": {"天罗": "辰（忌乙年）", "地网": "戌（忌辛年）", "命中": year_gan in ("乙", "辛")},
    }

    return {
        "school": "guolao-xingzong-vol2",
        "year_gz": year_gan + year_zhi,
        "year_gan": year_gan,
        "year_zhi": year_zhi,
        "bianyao": bianyao,
        "by_star": by_star,
        "stem_stars": stem_stars,
        "palace_shensha": palace_shensha,
        "jiaqian_12": jiaqian_12,
        "jiahou": jiahou,
    }
