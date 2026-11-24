# Third-Party Licenses & Provenance

This repository (`high-confidence-mingli-skill`, MIT License) builds upon the following verified open-source and public-domain works:

## 1. Calculation Engines & Astronomical Data
- **bazi-skill** (MIT License, Copyright (c) 2025 jinchenma94) — reference tables and initial Bazi calendar conventions.
- **ziwei-doushu** (MIT License, Copyright (c) 2026 紫微研究) — base Ziwei Dou Shu chart layout and pattern algorithms (`scripts/pai_pan_ziwei/vendor/`).
- **lunar-javascript** (MIT License, Copyright (c) 2018 6tail) — solar-term / lunar calendar reference tables (`scripts/astro_data/`).

## 2. Classical Corpus Sources (`references/corpus/`)
- **Bazi Classical Texts** (`穷通宝鉴`, `子平真诠`, `滴天髓阐微`, `渊海子平`, `千里命稿`): sourced from `ycc77cn/skills` (MIT License) — cleaned, chapter/month-tagged, and indexed in `bazi_qiongtong.jsonl` and `bazi_classics.jsonl`.
- **Ziwei Classical Texts & Star/Pattern Docs** (`紫微斗数全书` 卷一至三, `诸星问答论`, 十四主星/辅煞/十二宫/四化/格局说明): sourced from `SylarLong/iztro-docs` (MIT License, Copyright (c) 2023 Sylar Long) — stripped of VitePress/Vue UI tags, tagged by school (`feixing_reference` isolated from fixed natal four-transformations), and indexed in `ziwei_quanshu.jsonl` and `ziwei_stars_patterns.jsonl`.
- **Qizheng Siyu Classical Texts** (`张果星宗`, `星学大成`, `乾元秘旨`): sourced from Public Domain texts via `daizhigev20` (`references/qizheng/`) — Unicode PUA characters verified and repaired, indexed in `qizheng_classics.jsonl`, `qizheng_stars.jsonl`, and `qizheng_palaces_geju.jsonl`.

Note: Historical texts themselves are in the Public Domain; modern digital compilations, annotations, and software wrappers retain their respective MIT licenses above.
