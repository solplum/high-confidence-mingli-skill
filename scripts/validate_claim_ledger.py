#!/usr/bin/env python3
"""Validate evidence provenance, not the truth/predictive validity of divination.

Python 3.8+ with standard library only. Modern Ziwei birth-chart evidence also
replays the bundled engine. Never executes user-supplied evidence files.
Exit 0: mechanically consistent; 1: validation errors; 2: input error.
"""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock
import importlib.util

# Load sibling explicitly: this module is also imported by path in tests.
_KSPEC = importlib.util.spec_from_file_location("mingli_knowledge_catalog", Path(__file__).with_name("knowledge_catalog.py"))
_KNOWLEDGE = importlib.util.module_from_spec(_KSPEC)
_KSPEC.loader.exec_module(_KNOWLEDGE)

SYSTEMS = {"bazi", "ziwei", "qizheng"}
SNAPSHOT_HEADER = SYSTEMS | {"input"}
QIZHENG_PROFILES = ("physical-v2", "legacy-v1")
QIZHENG_CIVIL_SAMPLING = ("qizheng-civil-band-sensitivity-v1", "qizheng-civil-shichen-sensitivity-v1")
BAZI_BIRTH_KINDS = ("birth_date_unknown_hour", "birth_date_known_shichen", "birth_date_known_clock_band")
ZIWEI_BIRTH_BAND = "ziwei-birth-time-candidates-v1"
ZIWEI_LIFE_PROFILE = "ziwei-life-domains-v1"
_REPLAY_IMPORT_LOCK = Lock()
SNAPSHOT_SYSTEMS = {
    "bazi": "bazi", "bazi_core_reading": "bazi", "bazi_scenario_comparison": "bazi",
    "ziwei": "ziwei", "ziwei_scenario_comparison": "ziwei",
    "qizheng": "qizheng", "qizheng_rule_reading": "qizheng",
    "qizheng_traditional_reading": "qizheng", "qizheng_sensitivity": "qizheng",
}


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: %r" % key)
        result[key] = value
    return result


def _decode_json(raw):
    return json.loads(raw, object_pairs_hook=_unique_json_object)


def _json_equal(left, right):
    """JSON equality without Python's nested bool/int coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def _pointer(document, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(document, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError("invalid array index")
            document = document[int(part)]
        else:
            document = document[part]
    return document


def _combined_snapshot(document):
    return (isinstance(document, dict) and type(document.get("schema_version")) is int
            and document["schema_version"] == 1 and SNAPSHOT_HEADER <= document.keys())


def _standalone_qizheng_snapshot(document):
    if not isinstance(document, dict) or not isinstance(document.get("input"), dict):
        return False
    chart = document.get("chart")
    return (isinstance(chart, dict) and chart.get("calculation_profile") in QIZHENG_PROFILES
            and type(chart.get("jd_utc")) in (int, float) and isinstance(chart.get("bodies"), dict)
            and isinstance(document.get("traditional_reading"), dict))


def _qizheng_sample_collection(document):
    return (isinstance(document, dict) and document.get("version") == "qizheng-time-sensitivity-v1"
            and document.get("status") == "sampled_conditional" and isinstance(document.get("candidates"), list))


def _standalone_qizheng_sampling(document):
    return _qizheng_sample_collection(document) or (
            isinstance(document, dict) and document.get("version") in QIZHENG_CIVIL_SAMPLING
            and document.get("status") == "sampled_conditional"
            and isinstance(document.get("input"), dict) and isinstance(document.get("sampled_sections"), list))


def _standalone_bazi_birth_snapshot(document):
    return (isinstance(document, dict) and document.get("kind") in BAZI_BIRTH_KINDS
            and isinstance(document.get("solar_date"), str) and isinstance(document.get("candidates"), list))


def _standalone_ziwei_birth_band(document):
    return (isinstance(document, dict) and document.get("schema_version") == ZIWEI_BIRTH_BAND
            and isinstance(document.get("input"), dict) and isinstance(document.get("candidates"), list))


def _standalone_ziwei_life_panel(document):
    return (isinstance(document, dict) and document.get("profile") == ZIWEI_LIFE_PROFILE
            and document.get("version") == ZIWEI_LIFE_PROFILE
            and document.get("reading_use") == "conditional_module_only" and isinstance(document.get("domains"), list))


def _standalone_ziwei_native_chart(document):
    if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
            or document["schema_version"] != 1 or document.get("engine") != "iztro 2.6.1 / vendored wrapper"
            or not isinstance(document.get("input"), dict)):
        return False
    chart = document.get("chart")
    return isinstance(chart, dict) and isinstance(chart.get("birthInfo"), dict) and isinstance(chart.get("palaces"), list)


def _standalone_ziwei_dynamic_facts(document):
    if not isinstance(document, dict) or document.get("schema_version") != "ziwei-dynamic-facts-v1":
        return False
    admitted = document.get("admitted_dynamic_facts")
    return isinstance(admitted, dict) and (
        admitted.get("profile") == "iztro-2.6.1-lunar-year-month-v1" or _modern_ziwei_dynamic_facts(document))


def _snapshot_system(document, pointer):
    if _combined_snapshot(document):
        return SNAPSHOT_SYSTEMS.get(pointer.split("/", 2)[1])
    if _standalone_bazi_birth_snapshot(document):
        return "bazi"
    if (_standalone_ziwei_birth_band(document) or _standalone_ziwei_life_panel(document)
            or _standalone_ziwei_native_chart(document) or _standalone_ziwei_dynamic_facts(document)):
        return "ziwei"
    if _standalone_qizheng_sampling(document) or (
            _standalone_qizheng_snapshot(document) and pointer.split("/", 2)[1] in ("chart", "traditional_reading")):
        return "qizheng"
    return None


def _birth_clock(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(field + " is not an offset-bearing clock")
    clock = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if clock.utcoffset() is None:
        raise ValueError(field + " is not an offset-bearing clock")
    return clock


def _birth_span(row, start_key, end_key, *, civil=False, end_inclusive=False):
    if not isinstance(row, dict):
        raise ValueError("saved birth window must be an object")
    start = _birth_clock(row.get(start_key), start_key)
    end = _birth_clock(row.get(end_key), end_key)
    if start is None or end is None or start > end or (start == end and not end_inclusive):
        raise ValueError("saved birth window must have ordered, nonempty offset-bearing bounds")
    if civil and start.utcoffset() != end.utcoffset():
        raise ValueError("saved civil birth window must have a fixed effective UTC offset")
    offset = start.utcoffset() if civil else None
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc), offset, end_inclusive


@contextmanager
def _skill_scripts_path():
    # Direct path imports do not add the skill scripts directory to sys.path.
    scripts = str(Path(__file__).resolve().parent)
    with _REPLAY_IMPORT_LOCK:
        added = scripts not in sys.path
        if added:
            sys.path.insert(0, scripts)
        try:
            yield
        finally:
            if added:
                sys.path.remove(scripts)


def _replayed_bazi_birth_analyses(document):
    if (document.get("time_basis") != "civil" or document.get("windows") is None
            or document.get("sex") not in ("男", "女")
            or (document.get("timezone") is None and document.get("utc_offset") is None)):
        return None
    try:
        with _skill_scripts_path():
            import bazi_scenario_reading as native

            kind = document["kind"]
            if kind == native.UNKNOWN_HOUR:
                return {row["id"]: row["analysis"] for row in native.verified_date_candidates(document)}
            precision_key = {native.KNOWN_SHICHEN: "shichen", native.KNOWN_CLOCK_BAND: "clock_band"}.get(kind)
            if precision_key in document:
                ids = {row["id"] for row in document["candidates"]}
                if len(ids) != len(document["candidates"]):
                    raise ValueError("saved BaZi birth candidate IDs must be distinct")
                replayed = native._verify_candidate_coverage(
                    document, document.get("dayun_age_comparison"), ids, civil=None,
                    verify_ages="dayun_age_comparison" in document,
                )
                return {row["id"]: row["analysis"] for row in replayed["candidates"]}
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError("saved BaZi birth candidates lack inputs required for replay") from exc
    return None


def _check_replayed_bazi_candidate(candidate, replayed_analyses, relative=None):
    analysis = candidate.get("analysis")
    if relative is None:
        # A candidate-only archive may retain the original pillars without its derived core.
        if not isinstance(analysis, dict) or "facts" not in analysis:
            return
        relative = "/facts"
    try:
        actual = _pointer(analysis, relative)
        expected = _pointer(replayed_analyses[candidate["id"]], relative)
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("saved BaZi candidate fact is absent from the replayed birth") from exc
    if not _json_equal(actual, expected):
        raise ValueError("saved BaZi candidate fact disagrees with the replayed birth")


def _bazi_birth_spans(document, pointer, replayed_analyses):
    windows = document.get("windows")
    if (document.get("time_basis") != "civil"
            or document.get("interval_semantics") != "start_inclusive_end_exclusive" or windows is None):
        return None
    if not isinstance(windows, list) or not windows or not all(isinstance(row, dict) for row in windows):
        raise ValueError("saved BaZi birth windows must be a nonempty array of objects")
    parts = pointer.split("/", 4)
    if len(parts) >= 3 and parts[1] == "candidates":
        candidate = _pointer(document, "/".join(parts[:3]))
        candidate_id = candidate.get("id") if isinstance(candidate, dict) else None
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("saved BaZi birth candidate must have an ID")
        if replayed_analyses is not None:
            analysis_item = parts[4].partition("/")[0] if len(parts) == 5 and parts[3] == "analysis" else None
            if len(parts) == 3 or parts[3:] == ["analysis"]:
                _check_replayed_bazi_candidate(candidate, replayed_analyses)
                _check_replayed_bazi_spouse(candidate, replayed_analyses)
                _check_replayed_bazi_qiong(candidate, replayed_analyses)
            elif analysis_item == "facts":
                _check_replayed_bazi_candidate(candidate, replayed_analyses, "/" + parts[4])
            elif analysis_item == "primary_spouse":
                _check_replayed_bazi_spouse(candidate, replayed_analyses)
            elif analysis_item == "qiong_xin_zi_model":
                _check_replayed_bazi_qiong(candidate, replayed_analyses)
        windows = [row for row in windows if row.get("candidate_id") == candidate_id]
        if not windows:
            raise ValueError("saved BaZi birth candidate has no matching window")
    elif parts[1:] == ["candidates"] and replayed_analyses is not None:
        for candidate in document["candidates"]:
            _check_replayed_bazi_candidate(candidate, replayed_analyses)
            _check_replayed_bazi_spouse(candidate, replayed_analyses)
            _check_replayed_bazi_qiong(candidate, replayed_analyses)
    elif len(parts) >= 3 and parts[1] == "windows":
        windows = [_pointer(document, "/".join(parts[:3]))]
    elif len(parts) >= 4 and parts[1:3] == ["dayun_age_comparison", "segments"]:
        segment = _pointer(document, "/".join(parts[:4]))
        if not isinstance(segment, dict) or segment.get("end_inclusive") is not False:
            raise ValueError("saved BaZi age segment must have a half-open birth window")
        # Age segments store physical bounds in UTC. The corresponding
        # windows still determine the effective civil clock at each instant.
        spans = _common_birth_spans(
            [_birth_span(row, "start", "end", civil=True) for row in windows],
            [_birth_span(segment, "start_utc", "end_utc")],
        )
        if not spans:
            raise ValueError("saved BaZi age segment has no matching birth window")
        return spans
    return [_birth_span(row, "start", "end", civil=True) for row in windows]


def _ziwei_civil_span(record):
    span = _birth_span(record, "start_inclusive", "end_exclusive", civil=True)
    for field, expected in zip(("start_utc", "end_exclusive_utc"), span[:2]):
        if field in record and _birth_clock(record[field], field) != expected:
            raise ValueError("saved Ziwei civil and UTC birth bounds disagree")
    return span


def _enumerated_birth_span(row, offset=None):
    if not isinstance(row, dict) or type(row.get("end_inclusive")) is not bool:
        raise ValueError("saved birth interval must declare whether its end is included")
    start, end, _, inclusive = _birth_span(
        row, "start_utc", "end_utc", end_inclusive=row["end_inclusive"],
    )
    return start, end, offset, inclusive


def _ziwei_replayed_birth_spans(context, parts, basis):
    # Earlier continuation panels retain only an envelope for query ordering.
    if "reachable_utc_intervals" not in context:
        return None
    intervals = context["reachable_utc_intervals"]
    if (context.get("coverage") != "complete_for_modeled_boundaries_not_astronomical_error"
            or basis not in ("civil", "mean-solar")
            or not isinstance(intervals, list) or not intervals):
        raise ValueError("saved Ziwei reachable UTC intervals require complete modeled coverage")
    if len(parts) >= 4 and parts[1:3] == ["birth_scenario", "reachable_utc_intervals"]:
        intervals = [_pointer(context, "/" + "/".join(parts[2:4]))]
    spans = []
    for row in intervals:
        offset = None
        if basis == "civil":
            seconds = row.get("civil_offset_seconds") if isinstance(row, dict) else None
            if type(seconds) is not int or not -86400 < seconds < 86400:
                raise ValueError("saved Ziwei civil UTC interval must have a valid effective UTC offset")
            offset = timedelta(seconds=seconds)
        spans.append(_enumerated_birth_span(row, offset))
    return spans


def _ziwei_dynamic_birth_scope(document):
    """Compare the adapter's birth headers without using the query clock."""
    inputs = document.get("inputs")
    declared = inputs.get("birth") if isinstance(inputs, dict) else None
    wrapper = document.get("native_wrapper_snapshot")
    if not isinstance(declared, dict) or not _standalone_ziwei_native_chart(wrapper):
        return {}
    native = wrapper["input"]
    chart_birth = wrapper["chart"]["birthInfo"]
    keys = ("solar", "shichen_index", "original_civil_birth_year", "sex")
    if (not all(key in declared for key in keys)
            or not {"solar", "shichenIndex", "birthYear", "gender"} <= native.keys()
            or not {"year", "month", "day", "hour", "gender"} <= chart_birth.keys()):
        return {}
    solar, shichen, birth_year, sex = (declared[key] for key in keys)
    if (not isinstance(solar, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", solar)
            or type(shichen) is not int or not 0 <= shichen <= 11
            or type(birth_year) is not int or not 1 <= birth_year <= 9999
            or sex not in ("男", "女")):
        raise ValueError("invalid Ziwei dynamic birth identity")
    day = date.fromisoformat(solar)
    gender = "male" if sex == "男" else "female"
    expected_input = dict(solar=solar, shichenIndex=shichen, birthYear=birth_year, gender=gender)
    expected_birth = dict(year=day.year, month=day.month, day=day.day, hour=shichen, gender=gender)
    if (abs(birth_year - day.year) > 1
            or any(not _json_equal(native[key], value) for key, value in expected_input.items())
            or any(not _json_equal(chart_birth[key], value) for key, value in expected_birth.items())):
        raise ValueError("Ziwei dynamic birth identity disagrees with its native wrapper")
    return {"selected chart date and shichen": (solar, shichen),
            "Ziwei civil birth year": birth_year, "birth sex for BaZi/Ziwei": sex}


def _modern_ziwei_dynamic_facts(document):
    inputs = document.get("inputs")
    target = inputs.get("target") if isinstance(inputs, dict) else None
    return (document.get("status") == "facts_only_separate_lunar_time_profile"
            or "research_dynamic_iztro" in document
            or (isinstance(target, dict) and "time_index" in target))


def _replay_ziwei_dynamic_facts(document, birth_scope):
    inputs = document.get("inputs")
    target = inputs.get("target") if isinstance(inputs, dict) else None
    if (not birth_scope or not isinstance(target, dict) or not isinstance(target.get("solar_date"), str)
            or type(target.get("time_index")) is not int):
        raise ValueError("saved Ziwei dynamic facts lack the original birth or query point required for replay")
    solar, index = birth_scope["selected chart date and shichen"]
    birth_year = birth_scope["Ziwei civil birth year"]
    target_date = date.fromisoformat(target["solar_date"])
    age_year = document["native_wrapper_snapshot"]["input"].get("ageYear")
    if type(age_year) is not int or age_year != max(birth_year, target_date.year):
        raise ValueError("saved Ziwei dynamic native reference year disagrees with the recorded query point")
    research = document.get("research_dynamic_iztro")
    if isinstance(research, dict):
        raw = research.get("raw_horoscope")
        source_date = raw.get("solarDate") if isinstance(raw, dict) else None
        try:
            same_date = isinstance(source_date, str) and date(*map(int, source_date.split("-"))) == target_date
        except (TypeError, ValueError):
            same_date = False
        if not same_date:
            raise ValueError("saved Ziwei dynamic native date disagrees with the recorded query point")
    script = Path(__file__).resolve().with_name("ziwei_dynamic_facts.mjs")
    command = ["node", str(script), "--solar", solar, "--birth-year", str(birth_year),
               "--shichen-index", str(index), "--sex", birth_scope["birth sex for BaZi/Ziwei"],
               "--target-date", target["solar_date"], "--target-time-index", str(target["time_index"]),
               "--source-label", "claim-ledger-replay"]
    if "civil_time" in target:
        if not isinstance(target["civil_time"], str):
            raise ValueError("saved Ziwei dynamic facts lack a valid offset-bearing query clock")
        command.extend(("--target-civil", target["civil_time"]))
    try:
        proc = subprocess.run(command, check=True, capture_output=True, encoding="utf-8", timeout=45)
        return _decode_json(proc.stdout)["admitted_dynamic_facts"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise ValueError("saved Ziwei dynamic facts could not be replayed at the recorded query point") from exc


def _matching_ziwei_dynamic_layer(saved, expected):
    if not isinstance(saved, dict):
        return False
    if "transformations" not in expected:
        return _json_equal(saved, expected)
    rows = saved.get("transformations")
    if (not isinstance(rows, list) or len(rows) != len(expected["transformations"])
            or not all(isinstance(row, dict) and isinstance(row.get("kind"), str) for row in rows)):
        return False
    # Stored paths use that archive's array order. The raw mutagen path within
    # each row stays fixed by its kind and is part of the replay comparison.
    return _json_equal({**saved, "transformations": sorted(rows, key=lambda row: row["kind"])},
                       {**expected, "transformations": sorted(expected["transformations"], key=lambda row: row["kind"])})


def _check_ziwei_dynamic_facts(document, pointer, birth_scope, verified):
    prefix = "/admitted_dynamic_facts"
    if pointer != prefix and not pointer.startswith(prefix + "/"):
        return
    if not _modern_ziwei_dynamic_facts(document):
        return  # Sparse older evidence has birth headers but no replayable query point.
    saved = document["admitted_dynamic_facts"]
    key = id(document)
    if key not in verified:
        try:
            verified[key] = _replay_ziwei_dynamic_facts(document, birth_scope)
        except ValueError as exc:
            verified[key] = str(exc)
    replayed = verified[key]
    if isinstance(replayed, str):
        raise ValueError(replayed)
    layer_prefix = prefix + "/layers"
    metadata_error = "saved Ziwei dynamic admission metadata disagrees with the recorded query point"
    if pointer == prefix:
        if not _json_equal({k: v for k, v in saved.items() if k != "layers"},
                           {k: v for k, v in replayed.items() if k != "layers"}):
            raise ValueError(metadata_error)
    elif pointer != layer_prefix and not pointer.startswith(layer_prefix + "/"):
        field = pointer[len(prefix) + 1:].split("/", 1)[0]
        if field not in replayed or not _json_equal(saved[field], replayed[field]):
            raise ValueError(metadata_error)
        return

    layers = saved.get("layers")
    if not isinstance(layers, dict):
        raise ValueError("saved Ziwei dynamic facts lack their admitted layers")
    replayed_layers = replayed["layers"]
    if pointer.startswith(layer_prefix + "/"):
        selected = [pointer[len(layer_prefix) + 1:].split("/", 1)[0]]
    else:
        if layers.keys() != replayed_layers.keys():
            raise ValueError("saved Ziwei dynamic facts do not contain exactly the replayed layers")
        selected = layers
    for layer in selected:
        if layer not in replayed_layers or not _matching_ziwei_dynamic_layer(layers.get(layer), replayed_layers[layer]):
            raise ValueError("saved Ziwei " + layer + " dynamic facts disagree with the recorded query point")


def _ziwei_birth_scope(document, pointer, verified_band_candidates=None):
    """Read comparable inputs and reachable bounds from standalone Ziwei evidence."""
    if _standalone_ziwei_dynamic_facts(document):
        return _ziwei_dynamic_birth_scope(document), None
    parts = pointer.split("/")
    identity = {}
    scope = {}
    replayed_spans = None
    if _standalone_ziwei_birth_band(document):
        original = document["input"]
        day = original.get("birth_date")
        civil_year = int(day[:4]) if isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else None
        sex = original.get("sex")
        civil = original.get("time_basis") == "civil"
        candidate_path = parts[3:]
        if len(parts) >= 3 and parts[1] == "candidates":
            candidate = _pointer(document, "/".join(parts[:3]))
            candidates = [candidate]
            if isinstance(candidate, dict):
                identity = candidate.get("input", {})
            span_path = parts[:5] if len(parts) >= 5 and parts[3] == "civil_spans" else None
        else:
            candidates = document["candidates"]
            span_path = None
        if any(not isinstance(candidate, dict) for candidate in candidates):
            raise ValueError("saved Ziwei birth candidates must be objects")
        if parts[1] == "candidates":
            if not candidate_path or candidate_path[0] == "life_reading":
                for candidate in candidates:
                    _check_ziwei_band_projection(candidate, candidate_path[1:], civil_year, original.get("analysis_year"))
            if not candidate_path or candidate_path[0] in ("native", "life_reading"):
                _check_ziwei_band_charts(document, candidates, verified_band_candidates)
        spans = ([candidate.get("civil_spans") for candidate in candidates]
                 if document.get("interval_semantics") == "confirmed_civil_clock_membership_start_inclusive_end_exclusive"
                 else [None])
    elif _standalone_ziwei_native_chart(document):
        native = document["input"]
        gender = native.get("gender")
        sex = "男" if gender == "male" else "女" if gender == "female" else None
        identity = dict(solar_date=native.get("solar"), shichen_index=native.get("shichenIndex"))
        civil_year = native.get("birthYear")
        civil, spans, span_path = False, [None], None
    else:
        context = document.get("birth_scenario")
        if not isinstance(context, dict):
            context = {}
        identity = context.get("input", {})
        civil_year = document.get("natal_civil_birth_year")
        basis = document.get("natal_stage_basis")
        gender = basis.get("gender") if isinstance(basis, dict) else None
        sex = "男" if gender == "male" else "女" if gender == "female" else None
        civil = context.get("scope") in ("selected_reachable_civil_band_candidate_only", "confirmed_civil_shichen_only")
        spans = [context.get("civil_spans")] if civil else [None]
        span_path = (parts[:4] if civil and len(parts) >= 4 and parts[1:3] == ["birth_scenario", "civil_spans"]
                     else None)
        if context.get("scope") == "selected_birth_witness_only":
            basis = context.get("time_basis")
            if basis in ("civil", "mean-solar", "apparent-solar"):
                scope["selected chart time basis"] = basis
            replayed_spans = _ziwei_replayed_birth_spans(context, parts, basis)
    if civil:
        scope["selected chart time basis"] = "civil"
    if isinstance(identity, dict):
        year = identity.get("birth_year")
        if type(year) is int:
            if civil_year is not None and year != civil_year:
                raise ValueError("saved Ziwei civil birth years disagree")
            civil_year = year
        native_sex = identity.get("sex")
        if native_sex in ("男", "女"):
            if sex in ("男", "女") and sex != native_sex:
                raise ValueError("saved Ziwei birth sex values disagree")
            sex = native_sex
        day, shichen = identity.get("solar_date"), identity.get("shichen_index")
        if (isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
                and type(shichen) is int and 0 <= shichen <= 11):
            scope["selected chart date and shichen"] = (day, shichen)
    if type(civil_year) is int and 1 <= civil_year <= 9999:
        scope["Ziwei civil birth year"] = civil_year
    if sex in ("男", "女"):
        scope["birth sex for BaZi/Ziwei"] = sex
    if replayed_spans is not None:
        return scope, replayed_spans
    if not spans or any(rows is None for rows in spans):
        return scope, None
    if any(not isinstance(rows, list) or not rows for rows in spans):
        raise ValueError("saved Ziwei civil birth spans must be a nonempty array")
    if span_path:
        return scope, [_ziwei_civil_span(_pointer(document, "/".join(span_path)))]
    return scope, [_ziwei_civil_span(row) for rows in spans for row in rows]


def _check_ziwei_band_charts(document, candidates, verified):
    with _skill_scripts_path():
        from ziwei_birth_time_candidates import select_birth_band_candidate

    for candidate in candidates:
        # Older interval-only records have no chart to attribute to a shichen.
        if candidate.get("native") is None and candidate.get("life_reading") is None:
            continue
        key = id(candidate)
        if verified is None or key not in verified:
            select_birth_band_candidate(document, candidate.get("id"))
            if verified is not None:
                verified.add(key)


def _ziwei_unlocated_civil_windows(document):
    """Read the local clock bounds of a confirmed shichen without a UTC span."""
    if not _standalone_ziwei_life_panel(document):
        return None
    context = document.get("birth_scenario")
    if (not isinstance(context, dict) or context.get("scope") != "confirmed_civil_shichen_only"
            or context.get("civil_spans") is not None or "clock_intervals" not in context):
        return None
    identity, intervals = context.get("input"), context["clock_intervals"]
    day = identity.get("solar_date") if isinstance(identity, dict) else None
    if (not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
            or not isinstance(intervals, list) or not intervals):
        raise ValueError("confirmed Ziwei civil clock requires its recorded date and windows")
    midnight = datetime.fromisoformat(day)
    pattern = r"(?:[01][0-9]|2[0-3]):[0-5][0-9]"
    windows = []
    for row in intervals:
        start = row.get("start_inclusive") if isinstance(row, dict) else None
        end = row.get("end_exclusive") if isinstance(row, dict) else None
        if (not isinstance(start, str) or not re.fullmatch(pattern, start)
                or not isinstance(end, str) or (end != "24:00" and not re.fullmatch(pattern, end))
                or start >= end):
            raise ValueError("confirmed Ziwei civil clock windows must have ordered half-open bounds")
        left, right = (midnight + timedelta(hours=int(value[:2]), minutes=int(value[3:]))
                       for value in (start, end))
        windows.append((left, right))
    return windows


def _check_candidate_fields(saved, expected, error):
    if not isinstance(saved, dict) or any(
            key in saved and not _json_equal(saved[key], value) for key, value in expected.items()):
        raise ValueError(error)


def _check_bazi_spouse_panel(saved, expected, origin):
    error = "saved BaZi spouse panel disagrees with " + origin
    keys = ("profile", "rule_version", "sex", "scenario_id", "temporal_scope", "temporal_uncertainty")
    _check_candidate_fields(saved, {key: expected[key] for key in keys}, error)
    source_errors = saved.get("source_errors", [])
    if not isinstance(source_errors, list) or any(not isinstance(message, str) or not message.strip()
                                                  for message in source_errors):
        raise ValueError(error)
    keys = ("status", "missing_pillars", "nodes", "natal_relations",
            "original_candidate_decision", "original_selected_candidate")
    if source_errors:
        _check_candidate_fields(saved, {"status": "withheld", "nodes": [], "natal_relations": [],
                                        "original_candidate_decision": None, "original_selected_candidate": None}, error)
    elif expected["source_errors"]:
        raise ValueError("saved BaZi spouse panel requires its approved source for replay")
    else:
        _check_candidate_fields(saved, {key: expected[key] for key in keys}, error)
    if "cards" in saved:
        cards = saved["cards"]
        if not isinstance(cards, list) or len(cards) > len(expected["cards"]):
            raise ValueError(error)
        keys = ("id", "status", "conditions", "observations", "countercondition_checks",
                "conditional_model_result", "manual_review_completed", "effect_assessment")
        for row, actual in zip(cards, expected["cards"]):
            evidence = {key: actual[key] for key in keys if key in actual}
            if source_errors:
                evidence.update(status="withheld", conditions=[], observations={}, countercondition_checks=[],
                                conditional_model_result=None, manual_review_completed=False)
            _check_candidate_fields(row, evidence, error)


def _check_replayed_bazi_spouse(candidate, replayed_analyses):
    analysis = candidate.get("analysis")
    if isinstance(analysis, dict) and "primary_spouse" in analysis:
        _check_bazi_spouse_panel(analysis["primary_spouse"],
                                replayed_analyses[candidate["id"]]["primary_spouse"], "the replayed birth candidate")


def _check_bazi_qiong_panel(saved, expected, origin):
    error = "saved BaZi natal development model disagrees with " + origin
    keys = ("profile", "rule_version", "scenario_id", "temporal_scope", "temporal_uncertainty",
            "missing_pillars", "temporal_facts", "result_scope", "full_interval_coverage",
            "interval_stability_assessed", "predictive_validity", "prediction_guarantee")
    _check_candidate_fields(saved, {key: expected[key] for key in keys}, error)
    if "natal_pillars" in saved:
        _check_candidate_fields(saved["natal_pillars"], expected["natal_pillars"], error)
    source_errors = saved.get("source_errors", [])
    if not isinstance(source_errors, list) or any(
            not isinstance(message, str) or not message.strip() for message in source_errors):
        raise ValueError(error)
    if source_errors:
        _check_candidate_fields(saved, dict(status="withheld", conditional_model_direction="withheld",
                                            matched_branch=None, cards=[], manual_review_completed=False), error)
        if any(key in saved for key in ("source_direction", "specific_gui_countercondition",
                                        "observed", "nodes", "condition_facts")):
            raise ValueError(error)
        return
    if expected["source_errors"]:
        raise ValueError("saved BaZi natal development model requires its approved sources for replay")
    keys = ("status", "conditional_model_direction", "matched_branch", "source_direction", "observed",
            "condition_facts", "specific_gui_countercondition", "alternative_conservative_reading",
            "unique_input_result", "manual_review_completed", "effect_assessment", "nodes", "natal_relations",
            "cards", "required_manual_review", "robustness", "incomplete_reasons", "unknown_temporal_layers",
            "temporal_adaptations")
    _check_candidate_fields(saved, {key: expected.get(key) for key in keys}, error)


def _check_replayed_bazi_qiong(candidate, replayed_analyses):
    analysis = candidate.get("analysis")
    key = "qiong_xin_zi_model"
    if isinstance(analysis, dict) and key in analysis:
        _check_bazi_qiong_panel(analysis[key], replayed_analyses[candidate["id"]][key], "the replayed birth candidate")


def _check_bazi_analysis_identity(analysis, pillars, scenario_id, item, origin, *, central_reference=False,
                                  candidate_uncertainty=False, sex=None):
    if not isinstance(analysis, dict):
        return
    if "facts" in analysis:
        facts = analysis["facts"]
        error = "saved BaZi analysis facts disagree with " + origin
        if not isinstance(facts, dict):
            raise ValueError(error)
        for key, pillar in pillars.items():
            if key in facts:
                _check_candidate_fields(facts[key], dict(pillar=pillar, stem=pillar[:1], branch=pillar[1:]), error)
    for key in ("qiong_xin_zi_model", "primary_spouse"):
        if item in ("", key) and isinstance(analysis.get(key), dict):
            model = analysis[key]
            error = "saved BaZi model disagrees with " + origin
            expected = {"scenario_id": scenario_id}
            if key == "qiong_xin_zi_model":
                expected["temporal_scope"] = "natal"
            else:
                if sex in ("男", "女"):
                    expected["sex"] = sex
                if central_reference is True:
                    expected.update(temporal_scope="central_reference_only", status="withheld")
                elif central_reference is False:
                    expected["temporal_scope"] = "single_natal_input_candidate"
            _check_candidate_fields(model, expected, error)
            if "natal_pillars" in model:
                _check_candidate_fields(model["natal_pillars"], pillars, error)
    checks = {"qiong_xin_zi_model": _check_bazi_qiong_panel, "primary_spouse": _check_bazi_spouse_panel}
    selected = [key for key in checks if item in ("", key) and key in analysis]
    if selected and sex in ("男", "女") and central_reference is not None and candidate_uncertainty is not None:
        with _skill_scripts_path():
            import bazi_scenario_reading as native

            core = native.core
            keys = tuple(key for key in core.KEYS if key in pillars and len(pillars[key]) == 2
                         and pillars[key][0] in core.engine.GAN and pillars[key][1] in core.engine.ZHI)
            if all(key in keys for key in core.KEYS[:3]) and ("hour" in keys or pillars.get("hour") == "未知未知"):
                canonical = native.canonical_pillars({"bazi." + key: pillars[key] for key in keys}, keys)
                canonical.setdefault("hour", ("未知",) * 4)
                rebuilt = core.analyze(dict(pillars=canonical, sex=sex, scenario_id=scenario_id),
                                       temporal_uncertainty=central_reference,
                                       candidate_temporal_uncertainty=candidate_uncertainty)
                for key in selected:
                    checks[key](analysis[key], rebuilt[key], origin)


def _check_exact_bazi_luck(document, item):
    raw = document.get("bazi")
    if not isinstance(raw, dict):
        return
    table = raw.get("dayun_age_windows")
    fields = {"forward", "qiyun_years", "qiyun_months", "qiyun_text", "dayun_rows"}
    check_windows = item in ("", "dayun_age_windows") and isinstance(table, dict) and "windows" in table
    check_start = (raw.keys() if not item else {item}) & fields
    if not (check_windows or check_start):
        return
    sex = document["input"].get("sex")
    instant = _exact_birth_instant(document)
    if instant is None or sex not in ("男", "女"):
        return
    hour_unknown = raw.get("hour_unknown")
    reference = table.get("birth_time_is_reference") if isinstance(table, dict) else None
    if (("hour_unknown" in raw and type(hour_unknown) is not bool) or
            (isinstance(table, dict) and "birth_time_is_reference" in table and type(reference) is not bool)):
        raise ValueError("saved BaZi luck reference time flags must be boolean")
    if hour_unknown is True:
        pillars = raw.get("pillars")
        hour = pillars.get("hour") if isinstance(pillars, dict) else None
        if (reference is False or (isinstance(hour, list) and len(hour) >= 2 and
                                    all(isinstance(value, str) and len(value) == 1 for value in hour[:2]))):
            raise ValueError("saved BaZi luck reference time disagrees with the exact birth input")
        return
    if reference is True:
        if hour_unknown is False:
            raise ValueError("saved BaZi luck reference time disagrees with the exact birth input")
        return
    with _skill_scripts_path():
        from pai_pan_bazi import build_dayun
        from time_scenarios import dayun_age_segments

    _, _, rebuilt, _ = dayun_age_segments(instant, instant, (), sex)[0]
    if table is None and isinstance(raw.get("pillars"), dict):
        # Older display-only charts can retain the year/month and luck from a
        # different solar-term implementation. Keep that archived display.
        for key in ("year", "month"):
            pair = raw["pillars"].get(key)
            if (isinstance(pair, list) and len(pair) >= 2 and all(isinstance(value, str) for value in pair[:2])
                    and "".join(pair[:2]) != rebuilt[key + "_pillar"]):
                return
    years, months = divmod(rebuilt["start_age_months"], 12)
    expected = dict(forward=rebuilt["forward"], qiyun_years=years, qiyun_months=months)
    if "qiyun_text" in check_start:
        expected["qiyun_text"] = f"{years}岁{months}个月" if months else f"{years}岁"
    if "dayun_rows" in check_start:
        rows = build_dayun(*rebuilt["month_pillar"], rebuilt["forward"], years, months)
        expected["dayun_rows"] = [list(row) for row in rows]
    error = "saved BaZi luck ages disagree with the original birth instant"
    _check_candidate_fields(raw, {key: expected[key] for key in check_start}, error)
    if check_windows and not _json_equal(table["windows"], rebuilt["age_windows"]):
        raise ValueError(error)


def _bazi_center_uncertainty(document, minutes):
    comparison = document.get("bazi_scenario_comparison")
    context = comparison.get("context") if isinstance(comparison, dict) else None
    scenarios = document.get("scenarios")
    if not isinstance(context, dict) and (minutes is None or document["input"].get("enumerate_scenarios") is True):
        context = scenarios
    if isinstance(context, dict):
        start, end = (_birth_clock(context.get(key), key) for key in ("start_utc", "end_utc"))
        if start is not None and end is not None and start <= end:
            if type(minutes) in (int, float) and minutes >= 0:
                # Native endpoints round to microseconds; the input flag still marks the center uncertain.
                if bool(timedelta(minutes=minutes)) != (start < end):
                    raise ValueError("saved BaZi center uncertainty disagrees with its selected birth range")
                return bool(minutes)
            return start < end
    if type(minutes) in (int, float) and minutes >= 0:
        return bool(minutes)
    return None


def _check_ziwei_domain_palaces(domains, chart, error):
    palaces = chart.get("palaces")
    if not isinstance(palaces, list) or not isinstance(domains, list):
        return
    names = {row["branch"]: re.sub("宫$", "", row["name"]) for row in palaces
             if isinstance(row, dict) and type(row.get("branch")) is int and isinstance(row.get("name"), str)}
    for row in domains:
        if isinstance(row, dict) and type(row.get("branch")) is int and isinstance(row.get("domain"), str):
            name = names.get(row["branch"])
            if name is not None and name != re.sub("宫$", "", row["domain"]):
                raise ValueError(error)


def _check_ziwei_case_palaces(panel, chart):
    facts = panel.get("facts") if isinstance(panel, dict) else None
    if isinstance(facts, dict):
        _check_ziwei_domain_palaces(facts.get("domains"), chart,
                                   "saved Ziwei case domains disagree with the selected birth chart")


def _check_ziwei_case_model(saved, rebuilt, tail):
    error = "saved Ziwei interaction case disagrees with the native birth chart or its static scope"
    _check_candidate_fields(saved, {"profile": rebuilt["profile"], "version": rebuilt["version"]}, error)
    fields = tail.split("/")
    section = fields[0]
    if section not in ("", "status", "facts", "modules"):
        return
    if saved.get("source_errors"):
        if not isinstance(saved["source_errors"], list) or any(
                not isinstance(message, str) or not message.strip() for message in saved["source_errors"]):
            raise ValueError(error)
        _check_candidate_fields(saved, {"status": "withheld"}, error)
        if section in ("", "facts") and saved.get("facts"):
            raise ValueError(error)
        expected = {rule: dict(status="withheld", fact_match=None, selected_branch=None,
                               checks=[], direction_branches=[]) for rule in rebuilt["modules"]}
    else:
        if rebuilt["source_errors"]:
            raise ValueError("saved Ziwei interaction case requires its approved sources for replay")
        expected = rebuilt["modules"]
        if section in ("", "status"):
            _check_candidate_fields(saved, {"status": rebuilt["status"]}, error)
        if section in ("", "facts") and "facts" in saved:
            _check_candidate_fields(saved["facts"], rebuilt.get("facts", {}), error)
    if section in ("", "modules") and "modules" in saved:
        modules = saved["modules"]
        if not isinstance(modules, dict):
            raise ValueError(error)
        for rule, row in expected.items():
            if rule in modules and (len(fields) < 2 or fields[1] == rule):
                _check_candidate_fields(modules[rule], row, error)


def _check_ziwei_stage_years(contract, chart, birth_year, analysis_year, origin):
    years = {}
    if type(birth_year) is int:
        years["birth_year"] = birth_year
    if type(analysis_year) is int:
        years["analysis_year"] = analysis_year
    if type(birth_year) is int and type(analysis_year) is int and analysis_year >= birth_year:
        age = analysis_year - birth_year + 1
        years["current_age"] = age
        if isinstance(chart, dict):
            _check_candidate_fields(chart, {"currentAge": age},
                                    "saved Ziwei chart age disagrees with the selected civil birth year")
    if isinstance(contract, dict):
        _check_candidate_fields(contract, years, "saved Ziwei stage years disagree with " + origin)


def _replay_ziwei_static(chart, birth_year, analysis_year, uncertainty, *, recover_current_fields=True,
                        brightness_conflicts=(), replayed_chart=None, year_errors=()):
    if recover_current_fields and type(birth_year) is int and type(analysis_year) is int and analysis_year >= birth_year:
        chart = dict(chart)
        chart.setdefault("currentAge", analysis_year - birth_year + 1)
        ages = chart.get("daXians")
        if "currentDaXianIndex" not in chart and isinstance(ages, list) and all(
                isinstance(row, dict) and type(row.get("startAge")) is int and type(row.get("endAge")) is int
                for row in ages):
            age = chart["currentAge"]
            if type(age) is int:
                current = [i for i, row in enumerate(ages) if row["startAge"] <= age <= row["endAge"]]
                if len(current) <= 1:
                    chart["currentDaXianIndex"] = current[0] if current else -1
    with _skill_scripts_path():
        import ziwei_life_reading as life

        stage_rows = replayed_chart["daXians"] if replayed_chart is not None else None
        if (replayed_chart is not None and chart.get("wuxingJu") is not None
                and not _json_equal(chart["wuxingJu"], replayed_chart["wuxingJu"])):
            year_errors = [*year_errors, "原生大限五行局与复盘不一致"]
        return life.analyze(chart, birth_year, analysis_year, temporal_uncertainty=uncertainty,
                            brightness_conflicts=brightness_conflicts, replayed_stage_rows=stage_rows,
                            year_errors=year_errors)


def _check_ziwei_stage_model(saved, rebuilt, tail, origin):
    section = tail.split("/", 1)[0]
    if section not in ("", "status", "relationship", "stage_status", "stage_contract", "stages"):
        return
    if saved.get("source_errors"):
        relation = saved.get("relationship", {})
        if (not isinstance(saved["source_errors"], list) or saved.get("status") != "withheld"
                or saved.get("stages") or not isinstance(relation, dict)
                or relation.get("status") not in (None, "withheld")
                or relation.get("selected_branch") is not None or relation.get("direction_branches")):
            raise ValueError("saved Ziwei source failure contains active stage or relationship readings")
        _check_candidate_fields(saved, {"stage_status": "withheld", "stage_contract": None},
                                "saved Ziwei source failure contains active stage or relationship readings")
        return
    if rebuilt["source_errors"]:
        raise ValueError("saved Ziwei stage and relationship models require their approved sources for replay")
    error = "saved Ziwei stage or relationship model disagrees with " + origin
    if section in ("", "status"):
        _check_candidate_fields(saved, {"status": rebuilt["status"]}, error)
    if section in ("", "relationship") and "relationship" in saved:
        _check_candidate_fields(saved["relationship"], rebuilt["relationship"], error)
    if section in ("", "stage_status", "stage_contract"):
        _check_candidate_fields(saved, {"stage_status": rebuilt["stage_status"]}, error)
        if isinstance(saved.get("stage_contract"), dict) and isinstance(rebuilt["stage_contract"], dict):
            _check_candidate_fields(saved["stage_contract"], rebuilt["stage_contract"], error)
        elif "stage_contract" in saved:
            _check_candidate_fields(saved, {"stage_contract": rebuilt["stage_contract"]}, error)
    if section not in ("", "stages") or "stages" not in saved:
        return
    actual, expected = saved["stages"], rebuilt["stages"]
    if not isinstance(actual, list):
        raise ValueError(error)
    parts = tail.split("/")
    try:
        indices = [int(parts[1])] if len(parts) > 1 else range(len(actual))
        for index in indices:
            row, replayed = actual[index], expected[index]
            keys = ("legacy_stage", "context", "status", "overall_direction")
            _check_candidate_fields(row, {key: replayed[key] for key in keys}, error)
            if "modules" in row and (len(parts) < 3 or parts[2] == "modules"):
                modules = replayed["modules"]
                selected = {parts[3]: modules[parts[3]]} if len(parts) > 3 else modules
                _check_candidate_fields(row["modules"], selected, error)
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError(error) from exc


def _ziwei_domain_projection_requested(panel, item, tail):
    return (isinstance(panel, dict) and panel.get("profile") == panel.get("version") == ZIWEI_LIFE_PROFILE
            and panel.get("reading_use") == "conditional_module_only"
            and (item in ("", "domains") or (item == "modules" and
                 (not tail or re.fullmatch(r"ZW-D0[1-8]", tail.partition("/")[0])))))


def _check_ziwei_domain_projection(panel, rebuilt, item, tail, origin):
    error = "saved Ziwei domain evidence disagrees with " + origin

    def check_row(saved, expected, path):
        if path:
            if not _json_equal(_pointer(saved, "/" + path), _pointer(expected, "/" + path)):
                raise ValueError(error)
        else:
            _check_candidate_fields(saved, expected, error)

    try:
        if item in ("", "domains") and "domains" in panel:
            saved, expected = panel["domains"], rebuilt["domains"]
            if tail:
                index, _, path = tail.partition("/")
                row, replayed = _pointer(saved, "/" + index), _pointer(expected, "/" + index)
                _check_candidate_fields(row, {key: replayed[key] for key in ("domain", "branch")}, error)
                check_row(row, replayed, path)
            elif saved or not panel.get("source_errors"):
                if not isinstance(saved, list) or len(saved) != len(expected):
                    raise ValueError(error)
                for row, replayed in zip(saved, expected):
                    check_row(row, replayed, "")
        if item in ("", "modules") and "modules" in panel:
            saved, expected = panel["modules"], rebuilt["modules"]
            if not isinstance(saved, dict):
                raise ValueError(error)
            if tail:
                rule, _, path = tail.partition("/")
                check_row(saved[rule], expected[rule], path)
            else:
                for rule in saved:
                    if re.fullmatch(r"ZW-D0[1-8]", rule):
                        check_row(saved[rule], expected[rule], "")
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError(error) from exc


def _ziwei_t02_projection_requested(panel, item, tail):
    return (_standalone_ziwei_life_panel(panel) and isinstance(panel.get("modules"), dict) and
            "ZW-T02" in panel["modules"] and
            (item == "" or (item == "modules" and tail.partition("/")[0] in ("", "ZW-T02"))))


def _check_ziwei_t02_projection(panel, rebuilt, item, tail, origin):
    error = "saved Ziwei T02 stage facts disagree with " + origin
    saved = panel["modules"]["ZW-T02"]
    expected = rebuilt["modules"].get("ZW-T02")
    if not isinstance(expected, dict):
        if isinstance(saved, dict) and saved.get("status") == "withheld" and not saved.get("rows"):
            return
        raise ValueError(error)
    try:
        path = tail.partition("/")[2] if item == "modules" else ""
        if path:
            if not _json_equal(_pointer(saved, "/" + path), _pointer(expected, "/" + path)):
                raise ValueError(error)
        else:
            _check_candidate_fields(saved, expected, error)
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError(error) from exc


def _check_ziwei_band_projection(candidate, parts, birth_year, analysis_year):
    item, tail = (parts[0], "/".join(parts[1:])) if parts else ("", "")
    panel, native = candidate.get("life_reading"), candidate.get("native")
    if not isinstance(panel, dict) or not _standalone_ziwei_native_chart(native):
        return
    check_domains = _ziwei_domain_projection_requested(panel, item, tail)
    check_t02 = _ziwei_t02_projection_requested(panel, item, tail)
    cases = panel.get("case_judgments")
    check_cases = _standalone_ziwei_life_panel(panel) and isinstance(cases, dict) and item in ("", "case_judgments")
    stage = panel.get("stage_relationship")
    stage_model = (_standalone_ziwei_life_panel(panel) and isinstance(stage, dict) and
                   stage.get("profile") == "ziwei-stage-relationship-v1")
    stage_item = tail.partition("/")[0] if item == "stage_relationship" else None
    check_stage = stage_model and (item == "" or stage_item in ("", "status", "stage_status", "stage_contract", "stages"))
    check_relationship = stage_model and stage_item == "relationship"
    if not (check_domains or check_stage or check_relationship or check_t02 or check_cases):
        return
    origin = "the selected Ziwei birth-band chart"
    original, chart = native["input"], native["chart"]
    native_birth_year, native_analysis_year = original.get("birthYear"), original.get("ageYear")
    if check_stage or check_t02:
        expected_years = {key: year for key, year in (("birthYear", birth_year), ("ageYear", analysis_year))
                          if type(year) is int}
        _check_candidate_fields(original, expected_years, "saved Ziwei native stage years disagree with the birth band")
        birth_year = expected_years.get("birthYear", native_birth_year)
        analysis_year = expected_years.get("ageYear", native_analysis_year)
        contract = stage.get("stage_contract") if check_stage else None
        _check_ziwei_stage_years(contract, chart, birth_year, analysis_year, origin)
    else:
        birth_year, analysis_year = native_birth_year, native_analysis_year
    # The embedded band panel is an archived static reading. Its ordinary
    # reread does not recover missing current-age fields without a new year request.
    rebuilt = _replay_ziwei_static(chart, birth_year, analysis_year, False, recover_current_fields=False)
    if check_domains:
        _check_ziwei_domain_projection(panel, rebuilt, item, tail, origin)
    if check_t02:
        _check_ziwei_t02_projection(panel, rebuilt, item, tail, origin)
    if check_stage or check_relationship:
        _check_ziwei_stage_model(stage, rebuilt["stage_relationship"], tail, origin)
    if check_cases:
        _check_ziwei_case_model(cases, rebuilt["case_judgments"], tail)


def _check_ziwei_static_models(panel, chart, birth_year, analysis_year, item, tail, origin, *, uncertainty=False,
                               brightness_conflicts=(), replayed_chart=None, year_errors=()):
    if not isinstance(chart, dict) or type(uncertainty) is not bool:
        return
    relevant = [key for key in ("stage_relationship", "case_judgments") if item in ("", key)
                and isinstance(panel.get(key), dict)]
    check_domains = _ziwei_domain_projection_requested(panel, item, tail)
    check_t02 = _ziwei_t02_projection_requested(panel, item, tail)
    if not (relevant or check_domains or check_t02):
        return
    rebuilt = _replay_ziwei_static(chart, birth_year, analysis_year, uncertainty,
                                  recover_current_fields=bool(relevant), brightness_conflicts=brightness_conflicts,
                                  replayed_chart=replayed_chart, year_errors=year_errors)
    if check_domains:
        _check_ziwei_domain_projection(panel, rebuilt, item, tail, origin)
    if check_t02:
        missing_current = "currentAge" not in chart or "currentDaXianIndex" not in chart
        t02 = (_replay_ziwei_static(chart, birth_year, analysis_year, uncertainty, recover_current_fields=False,
                                   brightness_conflicts=brightness_conflicts, replayed_chart=replayed_chart,
                                   year_errors=year_errors)
               if relevant and missing_current else rebuilt)
        _check_ziwei_t02_projection(panel, t02, item, tail, origin)
    for key in relevant:
        if key == "case_judgments":
            _check_ziwei_case_model(panel[key], rebuilt[key], tail)
        elif panel[key].get("profile") == "ziwei-stage-relationship-v1":
            _check_ziwei_stage_model(panel[key], rebuilt[key], tail, origin)


def _replayed_combined_ziwei_chart(document, wrapper, chart, verified):
    inputs = document["input"]
    native_inputs = wrapper.get("input")
    native_inputs = native_inputs if isinstance(native_inputs, dict) else {}
    if not isinstance(inputs, dict) or (
            "enumerate_scenarios" not in inputs and "temporalUncertainty" not in native_inputs):
        return None, ()  # Older chart archives may lack the original calculation inputs.
    key = id(wrapper)
    if verified is not None and key in verified:
        return verified[key]
    time_info, provenance = document.get("time"), document.get("provenance")
    time_info = time_info if isinstance(time_info, dict) else {}
    timezone_source = provenance.get("timezone_source") if isinstance(provenance, dict) else None
    qizheng = document.get("qizheng")
    with _skill_scripts_path():
        from time_scenarios import parse_birth_date
        from ziwei_life_reading import _replay_snapshot_chart, _snapshot_birth_conflicts, _solar_input_conflicts

        birth_date = parse_birth_date(inputs.get("solar"))
        conflicts = _snapshot_birth_conflicts(inputs, time_info, native_inputs, chart, birth_date)
        conflicts.extend(_solar_input_conflicts(inputs, time_info, timezone_source, qizheng))
        if conflicts:
            raise ValueError("saved Ziwei chart disagrees with the original birth input: " + "；".join(conflicts))
        try:
            replayed = _replay_snapshot_chart(chart, inputs, time_info, native_inputs, birth_date, qizheng)
        except TypeError as exc:
            raise ValueError("saved Ziwei chart cannot be replayed from the original birth input") from exc
    if verified is not None:
        verified[key] = replayed
    return replayed


def _check_combined_ziwei_brightness(pointer, conflicts):
    for path in conflicts:
        native = "/ziwei/" + re.sub(r"\[([0-9]+)\]", r"/\1", path).replace(".", "/")
        if any(pointer == field or field.startswith(pointer + "/")
               for field in (native + "/brightnessRaw", native + "/brightness")):
            raise ValueError("saved Ziwei brightness disagrees with the original birth chart: " + path)


def _check_combined_ziwei_native_stage(pointer, chart, replayed, birth_year, analysis_year, year_errors):
    if replayed is None:
        return
    base = "/ziwei/chart"
    error = "saved Ziwei stage evidence disagrees with the original birth chart"
    checked = {key: replayed[key] for key in ("wuxingJu", "wuxingJuName")}
    expected = replayed["daXians"]
    current = None
    if not year_errors and type(birth_year) is int and type(analysis_year) is int and analysis_year >= birth_year:
        age = analysis_year - birth_year + 1
        index = next((i for i, row in enumerate(expected) if row["startAge"] <= age <= row["endAge"]), -1)
        current = expected[index]["palaceBranch"] if index >= 0 else -1
        checked.update(currentAge=age, currentDaXianIndex=index)
    if year_errors:
        for key in ("currentAge", "currentDaXianIndex"):
            field = base + "/" + key
            if chart.get(key) is not None and (pointer == field or field.startswith(pointer + "/")):
                raise ValueError(error + ": " + "；".join(year_errors))
    for key, expected_value in checked.items():
        field = base + "/" + key
        if pointer == field or field.startswith(pointer + "/"):
            value = chart.get(key)
            if value is not None and not _json_equal(value, expected_value):
                raise ValueError(error)

    palace_scope = base + "/palaces"
    if pointer == palace_scope or pointer.startswith(palace_scope + "/") or palace_scope.startswith(pointer + "/"):
        palace_path = pointer[len(palace_scope) + 1:].split("/") if pointer.startswith(palace_scope + "/") else []
        names = ("daXianAge", "isCurrentDaXian")
        fields = names if len(palace_path) < 2 else tuple(key for key in names if key == palace_path[1])
        if fields:
            by_branch = {row["palaceBranch"]: [row["startAge"], row["endAge"]] for row in expected}
            palaces = chart["palaces"]
            indices = [int(palace_path[0])] if palace_path else range(len(palaces))
            for i in indices:
                palace = palaces[i]
                values = {"daXianAge": by_branch[palace["branch"]]}
                if year_errors and "isCurrentDaXian" in fields and palace.get("isCurrentDaXian") is not None:
                    raise ValueError(error + ": " + "；".join(year_errors))
                if current is not None:
                    values["isCurrentDaXian"] = palace["branch"] == current
                if any(key in values and palace.get(key) is not None and
                       not _json_equal(palace[key], values[key]) for key in fields):
                    raise ValueError(error)

    table = base + "/daXians"
    if not (pointer == table or pointer.startswith(table + "/") or table.startswith(pointer + "/")):
        return
    rows = chart.get("daXians")
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError(error)
    path = pointer[len(table) + 1:].split("/") if pointer.startswith(table + "/") else []
    if len(path) > 1 and path[1] not in ("startAge", "endAge", "palaceBranch", "palaceName"):
        return
    with _skill_scripts_path():
        from ziwei_life_reading import _native_stage_placement

        indices = [int(path[0])] if path else range(len(rows))
        if any(_native_stage_placement(rows[i]) != _native_stage_placement(expected[i]) for i in indices):
            raise ValueError(error)


def _check_combined_projection(document, pointer, system, verified_ziwei_charts=None):
    parts = pointer.split("/", 4)
    uncertainty = document["input"].get("uncertainty_minutes") if isinstance(document["input"], dict) else None
    if system == "bazi" and parts[1] == "bazi" and isinstance(document["input"], dict):
        _check_exact_bazi_luck(document, parts[2] if len(parts) > 2 else "")
        return
    if system == "bazi" and parts[1] == "bazi_core_reading":
        native = document.get("bazi")
        raw = native.get("pillars") if isinstance(native, dict) else None
        if isinstance(raw, dict):
            pillars = {key: "".join(pair[:2]) for key, pair in raw.items() if key in ("year", "month", "day", "hour")
                       and isinstance(pair, list) and len(pair) >= 2
                       and all(isinstance(value, str) for value in pair[:2])}
            item = parts[2] if len(parts) > 2 else ""
            center = None
            if isinstance(document["input"], dict) and item in ("", "qiong_xin_zi_model", "primary_spouse"):
                center = _bazi_center_uncertainty(document, uncertainty)
            _check_bazi_analysis_identity(document["bazi_core_reading"], pillars, None, item,
                                          "the native birth chart", central_reference=center,
                                          sex=document["input"].get("sex") if isinstance(document["input"], dict) else None)
        return
    if system != "ziwei" or parts[1] != "ziwei" or (len(parts) > 2 and parts[2] not in ("chart", "life_reading")):
        return
    wrapper = document.get("ziwei")
    if not isinstance(wrapper, dict):
        return
    chart, panel = wrapper.get("chart"), wrapper.get("life_reading")
    if not isinstance(chart, dict):
        return
    replayed, brightness_conflicts = _replayed_combined_ziwei_chart(document, wrapper, chart, verified_ziwei_charts)
    _check_combined_ziwei_brightness(pointer, brightness_conflicts)
    native_input = wrapper.get("input")
    birth_year = native_input.get("birthYear") if isinstance(native_input, dict) else None
    analysis_year = native_input.get("ageYear") if isinstance(native_input, dict) else None
    year_errors = ()
    if replayed is not None:
        provenance = document.get("provenance")
        with _skill_scripts_path():
            from ziwei_life_reading import _saved_snapshot_analysis_year

            analysis_year, year_errors = _saved_snapshot_analysis_year(
                document["input"], provenance if isinstance(provenance, dict) else {},
                native_input if isinstance(native_input, dict) else {})
    _check_combined_ziwei_native_stage(pointer, chart, replayed, birth_year, analysis_year, year_errors)
    if parts[1:3] == ["ziwei", "chart"] or not isinstance(panel, dict):
        return
    expected = {}
    if type(birth_year) is int:
        expected["natal_civil_birth_year"] = birth_year
    if isinstance(native_input, dict) and isinstance(native_input.get("solar"), str):
        expected["natal_solar_date"] = native_input["solar"]
    if type(chart.get("shenGongBranch")) is int:
        expected["natal_body_branch"] = chart["shenGongBranch"]
    _check_candidate_fields(panel, expected, "saved Ziwei life inputs disagree with the native birth chart")
    _check_ziwei_domain_palaces(panel.get("domains"), chart,
                               "saved Ziwei life domains disagree with the native birth chart")
    item = parts[3] if len(parts) > 3 else ""
    if type(uncertainty) in (int, float) and uncertainty >= 0:
        _check_candidate_fields(panel, {"temporal_uncertainty": bool(uncertainty)},
                                "saved Ziwei life uncertainty disagrees with the native birth input")
        bounds = panel.get("birth_time_bounds")
        if item in ("", "birth_time_bounds") and isinstance(bounds, dict):
            center = _exact_birth_instant(document, allow_qizheng_reference=True)
            if center is not None:
                delta = timedelta(minutes=uncertainty)
                for key, expected_point in (("earliest_utc", center - delta), ("latest_utc", center + delta)):
                    saved_point = _birth_clock(bounds.get(key), key)
                    if saved_point is not None and saved_point != expected_point:
                        raise ValueError("saved Ziwei life birth bounds disagree with the native birth input")
    if item in ("", "case_judgments"):
        _check_ziwei_case_palaces(panel.get("case_judgments"), chart)
    subitem = parts[4].partition("/")[0] if len(parts) > 4 else ""
    tail = parts[4] if len(parts) > 4 else ""
    if not year_errors and (
            item == "" or (item == "stage_relationship" and subitem in ("", "stage_status", "stage_contract", "stages"))
            or _ziwei_t02_projection_requested(panel, item, tail)):
        stage = panel.get("stage_relationship")
        contract = stage.get("stage_contract") if isinstance(stage, dict) and item != "modules" else None
        _check_ziwei_stage_years(contract, chart, birth_year, analysis_year, "the native chart years")
    declared_uncertainty = native_input.get("temporalUncertainty") if isinstance(native_input, dict) else None
    birth_uncertain = (bool(uncertainty) if type(uncertainty) in (int, float) and uncertainty >= 0
                       else declared_uncertainty if type(declared_uncertainty) is bool
                       else panel.get("temporal_uncertainty"))
    _check_ziwei_static_models(panel, chart, birth_year, analysis_year, item,
                               tail, "the native birth chart",
                               uncertainty=birth_uncertain, brightness_conflicts=brightness_conflicts,
                               replayed_chart=replayed, year_errors=year_errors)


def _check_combined_candidate_identity(candidate, fields, system, relative, sex, analysis_year, birth_uncertainty):
    section, _, rest = relative.partition("/")
    item = rest.split("/", 1)[0]
    if system == "bazi":
        pillars = {}
        for key in ("year", "month", "day", "hour"):
            pair = fields.get("bazi." + key)
            if isinstance(pair, list) and len(pair) == 2 and all(isinstance(value, str) for value in pair):
                pillars[key] = "".join(pair)
        if "pillars" in candidate:
            _check_candidate_fields(candidate["pillars"], pillars,
                                    "saved BaZi pillars disagree with the selected birth variant")
        if section in ("", "analysis", "evidence", "text"):
            _check_bazi_analysis_identity(candidate.get("analysis"), pillars, candidate["id"],
                                          item if section in ("", "analysis") else section,
                                          "the selected birth variant", sex=sex,
                                          candidate_uncertainty=birth_uncertainty)
        return

    expected = {key: fields["ziwei." + key] for key in ("solar_date", "shichen_index", "birth_year")
                if "ziwei." + key in fields}
    if "input" in candidate:
        _check_candidate_fields(candidate["input"], expected,
                                "saved Ziwei candidate inputs disagree with the selected birth variant")
    chart = candidate.get("chart")
    if section in ("", "chart", "stage_relationship", "case_judgments") and isinstance(chart, dict) and "birthInfo" in chart:
        native = {}
        if "solar_date" in expected:
            day = date.fromisoformat(expected["solar_date"])
            native.update(year=day.year, month=day.month, day=day.day)
        if "shichen_index" in expected:
            native["hour"] = expected["shichen_index"]
        if sex in ("男", "女"):
            native["gender"] = "male" if sex == "男" else "female"
        _check_candidate_fields(chart["birthInfo"], native,
                                "saved Ziwei chart birth inputs disagree with the selected birth variant")
    if section in ("", "case_judgments") and isinstance(chart, dict):
        _check_ziwei_case_palaces(candidate.get("case_judgments"), chart)

    stage = section == "" or (section == "stage_relationship" and item in ("", "stage_status", "stage_contract", "stages"))
    current_chart = section == "chart" and item in ("", "currentAge", "currentDaXianIndex")
    if stage or current_chart:
        panel = candidate.get("stage_relationship") if stage else None
        contract = panel.get("stage_contract") if isinstance(panel, dict) else None
        _check_ziwei_stage_years(contract, chart, expected.get("birth_year"), analysis_year, "the selected birth variant")
    _check_ziwei_static_models(candidate, chart, expected.get("birth_year"), analysis_year, section,
                               rest, "the selected birth variant")


def _check_combined_ziwei_candidate_chart(document, candidate, relative, verified):
    section = relative.partition("/")[0]
    if section not in ("", "chart", "stage_relationship", "case_judgments"):
        return
    if all(candidate.get(key) is None for key in ("chart", "stage_relationship", "case_judgments")):
        return
    inputs = document["input"]
    # Legacy comparison records may lack the original enumeration request.
    if "enumerate_scenarios" not in inputs:
        return
    key = id(candidate)
    if verified is not None and key in verified:
        return
    with _skill_scripts_path():
        from time_scenarios import parse_birth_date
        from ziwei_life_reading import _select_birth_candidate

        _select_birth_candidate(document, candidate.get("id"), inputs, parse_birth_date(inputs.get("solar")))
    if verified is not None:
        verified.add(key)


def _combined_candidate_birth_scope(document, pointer, system, verified_ziwei_candidates=None):
    parts = pointer.split("/", 4)
    comparison = system + "_scenario_comparison"
    if parts[1:] == [comparison] and isinstance(document.get(comparison), dict) and "candidates" in document[comparison]:
        return _combined_candidate_birth_scope(document, pointer + "/candidates", system, verified_ziwei_candidates)
    if parts[1:3] != [comparison, "candidates"]:
        return {}, None
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, dict):
        return {}, None
    coverage = scenarios.get("coverage")
    if coverage not in ("complete_for_modeled_boundaries_not_astronomical_error",
                        "numerical_witnesses_not_exhaustive"):
        return {}, None
    if len(parts) == 3:
        # Check each saved candidate without treating mutually exclusive rows
        # as one birth or combining their intervals into a single witness.
        candidates = _pointer(document, pointer)
        if not isinstance(candidates, list):
            raise ValueError("saved comparison candidates must be an array")
        for index in range(len(candidates)):
            _combined_candidate_birth_scope(document, pointer + "/" + str(index), system, verified_ziwei_candidates)
        return {}, None
    candidate = _pointer(document, "/".join(parts[:4]))
    variants = scenarios.get("variants")
    if not isinstance(candidate, dict) or not isinstance(variants, list):
        raise ValueError("saved comparison candidate must link to the enumerated birth variants")
    ids = [candidate.get("id")] if system == "bazi" else candidate.get("scenario_ids")
    if not isinstance(ids, list) or not ids:
        raise ValueError("saved comparison candidate must link to at least one birth variant")

    inputs = document["input"]
    if not isinstance(inputs, dict):
        raise ValueError("saved comparison must contain its original birth inputs")
    scope, spans = {}, []
    relative = parts[4] if len(parts) == 5 else ""
    analysis_year = document[comparison].get("analysis_year") if system == "ziwei" else None
    start, end = scenarios.get("start_utc"), scenarios.get("end_utc")
    birth_uncertainty = start != end if isinstance(start, str) and isinstance(end, str) else None
    basis, sex = inputs.get("time_basis"), inputs.get("sex")
    if basis in ("civil", "mean-solar", "apparent-solar"):
        scope["selected chart time basis"] = basis
    if sex in ("男", "女"):
        scope["birth sex for BaZi/Ziwei"] = sex
    # A single witness cannot establish an IANA offset across a grouped
    # interval. A recorded fixed-offset civil clock applies to the entire band.
    offset = None
    provenance, recorded = document.get("provenance"), document.get("time")
    timezone_source = provenance.get("timezone_source") if isinstance(provenance, dict) else None
    if (basis == "civil" and isinstance(timezone_source, dict) and timezone_source.get("kind") == "fixed_offset"
            and isinstance(recorded, dict)):
        civil = _birth_clock(recorded.get("civil"), "civil")
        if civil is not None:
            offset = civil.utcoffset()

    for variant_id in ids:
        match = re.fullmatch(r"candidate-([1-9][0-9]*)", variant_id) if isinstance(variant_id, str) else None
        if match is None or int(match[1]) > len(variants):
            raise ValueError("saved comparison candidate refers to an unknown birth variant")
        variant = variants[int(match[1]) - 1]
        if not isinstance(variant, dict) or not isinstance(variant.get("fields"), dict):
            raise ValueError("saved birth variant must contain its chart inputs")
        fields = variant["fields"]
        _check_combined_candidate_identity(candidate, fields, system, relative, sex, analysis_year, birth_uncertainty)
        day, shichen = fields.get("ziwei.solar_date"), fields.get("ziwei.shichen_index")
        year = fields.get("ziwei.birth_year")
        if (isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
                and type(shichen) is int and 0 <= shichen <= 11):
            key = "selected chart date and shichen"
            if scope.setdefault(key, (day, shichen)) != (day, shichen):
                raise ValueError("saved comparison candidate mixes different chart dates or shichen")
        if type(year) is int and 1 <= year <= 9999:
            if scope.setdefault("Ziwei civil birth year", year) != year:
                raise ValueError("saved comparison candidate mixes different civil birth years")
        if coverage == "numerical_witnesses_not_exhaustive":
            continue
        intervals = variant.get("intervals")
        if not isinstance(intervals, list) or not intervals:
            raise ValueError("saved birth variant must have reachable intervals")
        spans.extend(_enumerated_birth_span(row, offset) for row in intervals)
    if system == "ziwei":
        _check_combined_ziwei_candidate_chart(document, candidate, relative, verified_ziwei_candidates)
    return scope, spans or None


def _common_birth_spans(left, right):
    common = set()
    for a_start, a_end, a_offset, a_inclusive in left:
        for b_start, b_end, b_offset, b_inclusive in right:
            if a_offset is not None and b_offset is not None and a_offset != b_offset:
                continue
            start, end = max(a_start, b_start), min(a_end, b_end)
            inclusive = (end < a_end or a_inclusive) and (end < b_end or b_inclusive)
            if start < end or (start == end and inclusive):
                offset = a_offset if a_offset is not None else b_offset
                common.add((start, end, offset, inclusive))
    return list(common)


def _restrict_to_civil_clock(spans, windows):
    """Apply local clock windows only where a physical span has a known offset."""
    common = []
    for span in spans:
        offset = span[2]
        if offset is None:
            common.append(span)
            continue
        zone = timezone(offset)
        aligned = [(left.replace(tzinfo=zone).astimezone(timezone.utc),
                    right.replace(tzinfo=zone).astimezone(timezone.utc), offset, False)
                   for left, right in windows]
        common.extend(_common_birth_spans([span], aligned))
    return common


def _original_civil_clock(inputs):
    year, month, day = map(int, inputs["solar"].split("-"))
    hour, minute = map(int, inputs["hour"].split(":"))
    return datetime(year, month, day, hour, minute)


def _check_iana_birth_source(original, instant, source, folds):
    if not isinstance(source, dict):
        return
    zone, saved_digest = source.get("zone"), source.get("tzif_sha256")
    if not isinstance(zone, str) or not isinstance(saved_digest, str) or not saved_digest:
        return
    try:
        from zoneinfo import ZoneInfo

        # Path-based callers need the local TZif reader without changing sys.path.
        spec = importlib.util.spec_from_file_location("mingli_tzif", Path(__file__).with_name("tzif_transitions.py"))
        tzif = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tzif)
        payload = tzif.read_tzif(zone)
        if payload is None or tzif.source_provenance(zone, payload)["tzif_sha256"] != saved_digest:
            return
        resolved = ZoneInfo.from_file(BytesIO(payload[0]), key=zone)
    except (ImportError, OSError, OverflowError, ValueError):
        return
    effective = instant.astimezone(resolved)
    if (effective.replace(tzinfo=None) != original or
            any(fold is not None and not _json_equal(fold, effective.fold) for fold in folds)):
        raise ValueError("original birth clock or fold disagrees with the saved IANA rules")


def _exact_birth_instant(document, *, allow_qizheng_reference=False):
    if _standalone_ziwei_life_panel(document):
        bounds = document.get("birth_time_bounds")
        if not isinstance(bounds, dict) or document.get("temporal_uncertainty") is not False:
            return None
        start = _birth_clock(bounds.get("earliest_utc"), "earliest_utc")
        end = _birth_clock(bounds.get("latest_utc"), "latest_utc")
        if start is not None and start == end:
            return start.astimezone(timezone.utc)
        return None
    combined = _combined_snapshot(document)
    if not combined and not _standalone_qizheng_snapshot(document):
        return None
    inputs = document["input"]
    if not isinstance(inputs, dict):
        return None
    uncertainty = inputs.get("uncertainty_minutes") if combined else None
    if not allow_qizheng_reference:
        if combined and (type(uncertainty) not in (int, float) or uncertainty != 0):
            return None
        if not combined and inputs.get("uncertain_time") is not False:
            return None
    try:
        original = _original_civil_clock(inputs)
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
        return None
    if not combined:
        # The standalone adapter takes the original Beijing clock.
        return original.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
    recorded = document.get("time")
    if recorded is None:
        recorded = {}
    if not isinstance(recorded, dict):
        raise ValueError("saved time must be an object")
    civil = _birth_clock(recorded.get("civil"), "time.civil")
    beijing = _birth_clock(recorded.get("instant_bj"), "time.instant_bj")
    native = document["bazi"]
    native_birth = None
    if isinstance(native, dict):
        age_table = native.get("dayun_age_windows")
        reference_clock = (isinstance(age_table, dict) and age_table.get("birth_time_is_reference") is True)
        if native.get("hour_unknown") is not True and not reference_clock:
            native_birth = _birth_clock(native.get("birth_dt"), "bazi.birth_dt")
    clocks = [clock.astimezone(timezone.utc) for clock in (civil, beijing, native_birth) if clock is not None]
    if not clocks:
        return None
    instant = clocks[0]
    if any(clock != instant for clock in clocks[1:]):
        raise ValueError("saved clocks and native birth instant disagree")
    if civil is not None and civil.replace(tzinfo=None) != original:
        raise ValueError("saved civil clock disagrees with original birth input")
    zones = [fields[key] for fields, key in ((inputs, "timezone"), (recorded, "iana_zone"))
             if key in fields]
    provenance = document.get("provenance")
    timezone_source = provenance.get("timezone_source") if isinstance(provenance, dict) else None
    if isinstance(timezone_source, dict):
        if "zone" in timezone_source:
            zones.append(timezone_source["zone"])
        elif timezone_source.get("kind") == "fixed_offset":
            zones.append(None)
    fold = inputs.get("fold")
    if (any(not _json_equal(zone, zones[0]) for zone in zones[1:])
            or fold is not None and "fold" in recorded and not _json_equal(recorded["fold"], fold)):
        raise ValueError("saved timezone or fold disagrees with original birth input")
    _check_iana_birth_source(original, instant, timezone_source, (fold, recorded.get("fold")))
    # IANA snapshots also store the parser's default utc_offset. It is
    # authoritative only if the archive actually identifies a fixed offset.
    offset = inputs.get("utc_offset")
    if zones and zones[0] is None and offset is not None:
        actual_seconds = (original - instant.replace(tzinfo=None)).total_seconds()
        if (type(offset) not in (int, float) or not -14 <= offset <= 14
                or abs(actual_seconds - offset * 3600) > 1e-8):
            raise ValueError("fixed UTC offset disagrees with original birth input")
    return instant


def _selected_chart_scope(document, system):
    """Read comparable BaZi/Ziwei inputs from an exact combined snapshot."""
    inputs = document['input']
    basis = inputs.get('time_basis')
    scope = {}
    ziwei = document.get('ziwei')
    native = ziwei.get('input') if isinstance(ziwei, dict) else None
    if system == 'bazi':
        bazi = document.get('bazi')
        native_sex = bazi.get('sex') if isinstance(bazi, dict) else None
    else:
        gender = native.get('gender') if isinstance(native, dict) else None
        native_sex = '男' if gender == 'male' else '女' if gender == 'female' else None
        # A solar-time chart can use the prior calendar date while its
        # legacy age windows still start from the original civil birth year.
        year = int(inputs['solar'].split('-', 1)[0])
        native_year = native.get('birthYear') if isinstance(native, dict) else None
        if native_year is not None and (type(native_year) is not int or native_year != year):
            raise ValueError('saved Ziwei civil birth year disagrees with the original birth input')
        scope['Ziwei civil birth year'] = year
    sex = inputs.get('sex')
    if sex in ('男', '女') and native_sex in ('男', '女') and sex != native_sex:
        raise ValueError('saved birth sex disagrees with the native chart input')
    if native_sex in ('男', '女') or sex in ('男', '女'):
        scope['birth sex for BaZi/Ziwei'] = native_sex if native_sex in ('男', '女') else sex
    if basis not in ('civil', 'mean-solar', 'apparent-solar'):
        return scope
    scope['selected chart time basis'] = basis
    if isinstance(native, dict):
        day, shichen = native.get('solar'), native.get('shichenIndex')
        if (isinstance(day, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)
                and type(shichen) is int and 0 <= shichen <= 11):
            # The native input survives loss of derived time metadata and
            # is independent of how the physical instant was formatted.
            scope['selected chart date and shichen'] = (day, shichen)
    recorded = document.get('time') or {}
    clock = recorded.get('chart_clock')
    if clock is None and basis != 'civil':
        clock = recorded.get(basis.replace('-', '_'))
    if isinstance(clock, str) and len(clock) > 10:
        try:
            point = datetime.fromisoformat(clock[:-1] + '+00:00' if clock.endswith('Z') else clock)
        except ValueError:
            return scope
        scope['selected chart minute'] = point.replace(tzinfo=None, second=0, microsecond=0)
    return scope


def _qizheng_reference_scope(document, pointer):
    """Locate the calculation point of a native chart saved with an uncertain birth."""
    inputs = document.get("input")
    if not isinstance(inputs, dict):
        return {}, None
    section = pointer.split("/", 2)[1]
    if section == "qizheng" and _combined_snapshot(document):
        uncertainty = inputs.get("uncertainty_minutes")
        if type(uncertainty) in (int, float) and uncertainty == 0:
            return {}, None
    elif section == "chart" and _standalone_qizheng_snapshot(document):
        if inputs.get("uncertain_time") is False:
            return {}, None
    else:
        return {}, None
    chart = document[section]
    if not isinstance(chart, dict) or "jd_utc" not in chart:
        return {}, None
    instant = _exact_birth_instant(document, allow_qizheng_reference=True)
    if instant is None:
        return {}, None
    # This point locates the referenced native facts. It is not registered as
    # an exact birth and does not apply to aggregate or withheld status facts.
    return _qizheng_chart_scope(document, instant), [(instant, instant, None, True)]


def _check_qizheng_combined_sampling_range(document, interval, start, end):
    center = _exact_birth_instant(document, allow_qizheng_reference=True)
    if center is None:
        return
    recorded = _birth_clock(interval.get("center_utc"), "center_utc")
    if ((recorded is not None and recorded != center) or
            start > center or center - start != end - center):
        raise ValueError("saved Qizheng sampling range disagrees with the original birth center")
    minutes = document["input"].get("uncertainty_minutes")
    if minutes is not None and (type(minutes) not in (int, float) or not 0 <= minutes <= 120 or
                                center - start != timedelta(minutes=minutes)):
        raise ValueError("saved Qizheng sampling range disagrees with the original birth uncertainty")


def _check_qizheng_civil_sampling_range(document, section, start, end):
    from time_scenarios import (
        TICK, civil_clock_band_shichen_spans, civil_shichen_spans, parse_birth_date, parse_civil_clock_band,
    )

    stop = end + TICK
    if "start_utc" in section or "end_exclusive_utc" in section:
        first, last, _, _ = _birth_span(section, "start_utc", "end_exclusive_utc")
        if (start, stop) != (first, last):
            raise ValueError("saved Qizheng sampling range disagrees with its civil section")
    inputs = document["input"]
    day = inputs.get("birth_date")
    zone, offset = inputs.get("timezone"), inputs.get("utc_offset_hours")
    if day is None or (zone is None and offset is None):
        return
    try:
        day = parse_birth_date(day)
        if document["version"] == "qizheng-civil-shichen-sensitivity-v1":
            spans = civil_shichen_spans(day, inputs["shichen"], utc_offset=offset, zone=zone)
        else:
            left, right = parse_civil_clock_band(inputs["start_inclusive"], inputs["end_exclusive"])
            spans = civil_clock_band_shichen_spans(day, left, right, utc_offset=offset, zone=zone)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("saved Qizheng original civil sampling inputs are invalid") from exc
    if not any(row[0] <= start and stop <= row[1] for row in spans):
        raise ValueError("saved Qizheng sampling section is outside the original civil birth range")


def _check_qizheng_witness_clock(inputs, instant, civil, row, offset_key):
    from time_scenarios import fixed_utc_offset, iana_zone

    region, offset = inputs.get("timezone"), inputs.get(offset_key)
    if region is None and offset is None:
        return
    zone = iana_zone(region) if region is not None else fixed_utc_offset(offset)
    local = instant.astimezone(zone)
    if (civil.utcoffset() != local.utcoffset() or
            ("fold" in row and not _json_equal(row["fold"], local.fold))):
        raise ValueError("saved Qizheng witness civil clock or fold disagrees with its birth timezone")


def _check_qizheng_replayed_fields(saved, expected, error):
    if expected is None and saved is None:
        return
    if not isinstance(saved, dict) or not isinstance(expected, dict):
        raise ValueError(error)
    for key in saved.keys() & expected.keys():
        value = expected[key]
        if isinstance(value, dict):
            _check_qizheng_replayed_fields(saved[key], value, error)
        elif type(value) is float and type(saved[key]) in (int, float):
            # Allow floating-point replay roundoff in degrees or hours.
            if not math.isclose(saved[key], value, rel_tol=0, abs_tol=1e-9):
                raise ValueError(error)
        elif not _json_equal(saved[key], value):
            raise ValueError(error)


def _check_qizheng_witness_chart(row, scope, instant, tail):
    import pai_pan_qizheng as engine
    from qizheng_sensitivity import fields as sensitivity_fields

    chart = row["chart"]
    lat, lon = scope.get("Qizheng birth latitude"), scope.get("Qizheng birth longitude")
    profile = chart["calculation_profile"]
    dut1 = scope.get("Qizheng DUT1", 0.0 if profile == "legacy-v1" else None)
    if dut1 is None:
        return
    horizon_fields = {
        "ming_du": ("tropical", "sidereal", "mansion", "mansion_deg", "wuxing", "star"),
        "day_night": ("type", "solar_altitude_deg", "sunrise_local", "sunset_local"),
    }
    projected = row.get("fields")
    section, field = (*tail, "", "")[:2]
    check_bodies = section == "" or (section == "chart" and field in ("", "bodies"))
    body_fields = []
    if isinstance(projected, dict) and section in ("", "fields"):
        body_fields = [key for key in projected if key.startswith("bodies.") and field in ("", key)]
    check_horizon = lat is not None and lon is not None and (
        horizon_fields.keys() & chart.keys() or isinstance(projected, dict))
    if not (check_horizon or (check_bodies and "bodies" in chart) or body_fields):
        return
    beijing = instant.astimezone(engine.BJ)
    replayed, _ = engine.compute(
        (beijing.year, beijing.month, beijing.day), beijing.hour, beijing.minute,
        lat, scope.get("Qizheng legacy longitude", lon), birth_instant=instant,
        profile=profile, dut1_seconds=dut1,
    )
    if check_horizon:
        for name, keys in horizon_fields.items():
            if name not in chart:
                continue
            actual = replayed[name]
            selected = {key: actual.get(key) for key in keys} if isinstance(actual, dict) else actual
            _check_qizheng_replayed_fields(chart[name], selected,
                                          "saved Qizheng witness " + name + " disagrees with its birth coordinates")
    if check_bodies and "bodies" in chart:
        saved, actual = chart["bodies"], replayed["bodies"]
        body = tail[2] if len(tail) > 2 else None
        error = "saved Qizheng witness body disagrees with its replayed birth instant"
        if not isinstance(saved, dict):
            raise ValueError(error)
        for name in (saved if body is None else (body,)):
            if name not in actual or name not in saved or not isinstance(saved[name], dict):
                raise ValueError(error)
            _check_qizheng_replayed_fields(saved[name], actual[name], error)
    if isinstance(projected, dict) and (check_horizon or body_fields):
        expected = sensitivity_fields(replayed, {})
        for key in body_fields:
            if key not in expected or not _json_equal(projected[key], expected[key]):
                raise ValueError("saved Qizheng witness body disagrees with its replayed sky summary")
        for key, value in expected.items():
            if (check_horizon and key in projected and (key.startswith("ascendant.") or key in ("day_night", "en_yong"))
                    and not _json_equal(projected[key], value)):
                raise ValueError("saved Qizheng witness " + key + " disagrees with its replayed horizon summary")


def _check_qizheng_reading(chart, reading, *, traditional=False, uncertain=False, selection=None, tail=()):
    if not isinstance(chart, dict) or not isinstance(reading, dict):
        return
    error = "saved Qizheng reading disagrees with its native chart"
    if isinstance(chart.get("calculation_profile"), str):
        _check_candidate_fields(reading, {"calculation_profile": chart["calculation_profile"]}, error)
    claims = reading.get("claims")
    conditional = ([claim for claim in claims if isinstance(claim, dict) and claim.get("status") == "conditional"]
                   if isinstance(claims, list) else [])
    if uncertain and (reading.get("status") == "conditional" or conditional):
        raise ValueError("saved Qizheng reading promotes an uncertain birth reference")
    if traditional and conditional and selection is not None and "scheme" in selection:
        _check_candidate_fields(reading, {"scheme": selection["scheme"]},
                                "saved Qizheng traditional scheme disagrees with its recorded selection")
    if traditional and "chart_sha256" in reading:
        raw = json.dumps(chart, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if reading["chart_sha256"] != hashlib.sha256(raw).hexdigest():
            raise ValueError("saved Qizheng traditional reading refers to a different native chart digest")
    selected = claims if isinstance(claims, list) else []
    if len(tail) > 1 and tail[0] == "claims":
        selected = [_pointer(reading, "/claims/" + tail[1])]
    known_rules = ("QZT04",) if traditional else ("QZ01", "QZ02")
    for claim in selected:
        if not isinstance(claim, dict):
            raise ValueError("saved Qizheng claim must be an object")
        if claim.get("status") == "conditional" and claim.get("rule_id") not in known_rules:
            raise ValueError("saved Qizheng reading uses an unrecognized conditional rule")
        if claim.get("status") == "withheld" and any(
                key in claim for key in ("facts", "groups", "relation_to_degree_lord", "input_facts", "calculation")):
            raise ValueError("saved Qizheng withheld claim contains a conditional reading")
    selected = [claim for claim in selected if claim.get("status") == "conditional"]
    if not selected:
        return
    with _skill_scripts_path():
        import qizheng_rule_profiles as profiles
        from qizheng_traditional_reading import BODIES
        from qizheng_traditional_study import RELATIONS

    ascendant = chart.get("ming_du")
    phase = chart.get("du_zhu_wuxing")
    if isinstance(ascendant, dict) and isinstance(ascendant.get("wuxing"), str):
        derived = profiles.engine.MANSION_WX_TO_PHASE.get(ascendant["wuxing"])
        if derived is not None and phase not in (None, derived) and not traditional:
            raise ValueError(error)
        phase = derived if derived is not None else phase
    for claim in selected:
        rule = claim.get("rule_id")
        if rule == "QZ01" and not traditional:
            if "ming_du" in chart and not isinstance(ascendant, dict):
                raise ValueError(error)
            facts = claim.get("facts")
            if isinstance(facts, dict):
                expected = {}
                if isinstance(ascendant, dict) and "mansion" in ascendant:
                    expected["mansion"] = ascendant["mansion"]
                if phase is not None:
                    expected["reference_element"] = phase
                _check_candidate_fields(facts, expected, error)
            if isinstance(chart.get("en_yong"), dict):
                _check_candidate_fields(claim, {"groups": chart["en_yong"]}, error)
        elif (rule == "QZ02" and not traditional) or (rule == "QZT04" and traditional):
            palace = chart.get("ming_gong")
            if "ming_gong" in chart and not isinstance(palace, dict):
                raise ValueError(error)
            identity = profiles.palace_identity(palace["zhi"]) if isinstance(palace, dict) and "zhi" in palace else None
            if traditional:
                body = claim.get("other_body")
                if selection is not None and "other_body" in selection:
                    body = selection["other_body"]
                    _check_candidate_fields(claim, {"other_body": body},
                                            "saved Qizheng traditional body disagrees with its recorded selection")
                if body not in BODIES:
                    raise ValueError("saved Qizheng traditional reading lacks an admitted selected body")
                if "bodies" in chart and (not isinstance(chart["bodies"], dict) or body not in chart["bodies"]):
                    raise ValueError(error)
                element = profiles.engine.LUMINARIES_WUXING[body]
                for field in ("input_facts", "calculation"):
                    if field in claim:
                        _check_candidate_fields(claim[field], {"other_element": element},
                                                "saved Qizheng traditional element disagrees with its selected body")
                scope = {"context": "natal", "reference_basis": "palace_lord"}
                if "input_facts" in claim:
                    if identity:
                        scope["branch"] = identity["zhi"]
                    _check_candidate_fields(claim["input_facts"], scope, error)
                if identity and "calculation" in claim:
                    lord = identity["palace_lord_element"]
                    expected = dict(identity, context="natal", reference_basis="palace_lord", reference_element=lord,
                                    relation=RELATIONS[profiles.relation(lord, element)])
                    _check_candidate_fields(claim["calculation"], expected, error)
            elif identity:
                _check_candidate_fields(palace, {"wuxing": identity["branch_element"]}, error)
                if "facts" in claim:
                    _check_candidate_fields(claim["facts"], identity, error)
                if phase is not None:
                    relation = profiles.relation(phase, identity["palace_lord_element"])
                    _check_candidate_fields(claim, {"relation_to_degree_lord": relation}, error)


def _check_qizheng_archive_reading(document, section, tail=()):
    if _combined_snapshot(document) and section in ("qizheng_rule_reading", "qizheng_traditional_reading"):
        inputs = document["input"]
        minutes = inputs.get("uncertainty_minutes") if isinstance(inputs, dict) else None
        selection = {key: inputs[flag] for key, flag in (("scheme", "qizheng_tradition"),
                                                         ("other_body", "qizheng_other_body"))
                     if isinstance(inputs, dict) and flag in inputs}
        _check_qizheng_reading(document["qizheng"], document.get(section),
                               traditional=section == "qizheng_traditional_reading",
                               uncertain=type(minutes) in (int, float) and minutes > 0, selection=selection, tail=tail)
    elif section == "traditional_reading" and _standalone_qizheng_snapshot(document):
        inputs = document["input"]
        selection = {key: inputs[flag] for key, flag in (("scheme", "tradition"), ("other_body", "other_body"))
                     if flag in inputs}
        _check_qizheng_reading(document["chart"], document.get(section), traditional=True,
                               uncertain=inputs.get("uncertain_time") is True, selection=selection, tail=tail)


def _check_qizheng_sample_reading(row, chart, tail, sample, outer_selection=None):
    section = tail[0] if tail else ""
    selected_field = tail[1] if len(tail) > 1 else ""
    selection = {key: sample[field] for key, field in (("scheme", "traditional_scheme"),
                                                       ("other_body", "traditional_other_body"))
                 if field in sample}
    for reading_key, field_key in (("rule_reading", "rule_output"), ("traditional_reading", "traditional_rule_output")):
        projected = section == "fields" and selected_field in ("", field_key)
        if section not in ("", reading_key) and not projected:
            continue
        reading = row.get(reading_key)
        traditional = reading_key == "traditional_reading"
        if traditional and isinstance(reading, dict) and outer_selection:
            _check_candidate_fields(selection, outer_selection,
                                    "saved Qizheng traditional sample disagrees with its enclosing selection")
            selection = dict(outer_selection, **selection)
        reading_tail = tail[2:] if projected else tail[1:]
        _check_qizheng_reading(chart, reading, traditional=traditional, selection=selection, tail=reading_tail)
        fields = row.get("fields")
        if (section == "" or projected) and isinstance(fields, dict) and field_key in fields:
            if not isinstance(reading, dict):
                raise ValueError("saved Qizheng witness rule summary lacks its reading")
            saved_summary = fields[field_key]
            error = "saved Qizheng witness rule summary disagrees with its reading"
            if projected and len(reading_tail) > 1 and reading_tail[0] == "claims":
                claim_pointer = "/claims/" + reading_tail[1]
                try:
                    matches = _json_equal(_pointer(saved_summary, claim_pointer), _pointer(reading, claim_pointer))
                except (IndexError, KeyError, TypeError) as exc:
                    raise ValueError(error) from exc
                if not matches:
                    raise ValueError(error)
            else:
                summary = {key: reading.get(key) for key in ("status", "reason", "claims")}
                _check_candidate_fields(saved_summary, summary, error)


def _qizheng_sampling_scope(document, pointer):
    """Bind selected Qizheng facts to their physical calculation point."""
    parts = pointer.split("/")
    section = None
    combined_sample = (len(parts) >= 4 and parts[1:3] == ["qizheng_sensitivity", "candidates"]
                       and _combined_snapshot(document))
    if combined_sample:
        sample = document["qizheng_sensitivity"]
        index = parts[3]
        tail = parts[4:]
    elif len(parts) >= 3 and parts[1] == "candidates" and _qizheng_sample_collection(document):
        sample, index = document, parts[2]
        tail = parts[3:]
    elif (len(parts) >= 6 and parts[1] == "sampled_sections" and parts[3:5] == ["sample", "candidates"]
          and _standalone_qizheng_sampling(document)):
        section = _pointer(document, "/".join(parts[:3]))
        sample = _pointer(document, "/".join(parts[:4]))
        index = parts[5]
        tail = parts[6:]
    else:
        _check_qizheng_archive_reading(document, parts[1], parts[2:])
        return _qizheng_reference_scope(document, pointer)
    if not _qizheng_sample_collection(sample):
        raise ValueError("saved Qizheng witness lacks its sampling record")
    row = _pointer(sample, "/candidates/" + index)
    if not isinstance(row, dict):
        raise ValueError("saved Qizheng witness must be an object")
    chart = row.get("chart")
    instant = _birth_clock(row.get("witness_utc"), "witness_utc")
    civil = _birth_clock(row.get("witness_civil"), "witness_civil")
    if (instant is None or civil is None or instant != civil or not isinstance(chart, dict)
            or "jd_utc" not in chart or chart.get("calculation_profile") not in QIZHENG_PROFILES):
        raise ValueError("saved Qizheng witness lacks a consistent clock and native chart")
    instant = instant.astimezone(timezone.utc)
    start, end, _, _ = _birth_span(sample.get("interval"), "start_utc", "end_utc", end_inclusive=True)
    if not start <= instant <= end:
        raise ValueError("saved Qizheng witness is outside its recorded sample range")
    outer_selection = {}
    if combined_sample:
        _check_qizheng_combined_sampling_range(document, sample["interval"], start, end)
        if "timezone" in document["input"]:
            _check_qizheng_witness_clock(document["input"], instant, civil, row, "utc_offset")
        outer_selection = {key: document["input"][flag] for key, flag in (
            ("scheme", "qizheng_tradition"), ("other_body", "qizheng_other_body")) if flag in document["input"]}
    if section is not None:
        _check_qizheng_civil_sampling_range(document, section, start, end)
        _check_qizheng_witness_clock(document["input"], instant, civil, row, "utc_offset_hours")
        outer_selection = {key: document["input"][flag] for key, flag in (
            ("scheme", "traditional_scheme"), ("other_body", "traditional_other_body")) if flag in document["input"]}
    scope = _qizheng_chart_scope(document, instant, witness_chart=chart)
    if "input" in sample:
        from qizheng_sensitivity import _validate_sampling_inputs

        inputs = sample["input"]
        if not isinstance(inputs, dict):
            raise ValueError("saved Qizheng sample inputs must be an object")
        _validate_sampling_inputs(inputs.get("lat"), inputs.get("lon"), inputs.get("dut1_seconds"))
        if (inputs.get("profile") not in QIZHENG_PROFILES or
                (inputs.get("timezone") is not None and inputs.get("utc_offset_hours") is not None)):
            raise ValueError("saved Qizheng sample profile or timezone is invalid")
        _check_qizheng_witness_clock(inputs, instant, civil, row, "utc_offset_hours")
        if sample is not document:
            embedded_scope = _qizheng_chart_scope(sample, instant, witness_chart=chart)
            for key, value in embedded_scope.items():
                if key in scope and scope[key] != value:
                    raise ValueError("saved Qizheng sample disagrees with its enclosing record on " + key)
            scope.update(embedded_scope)
    _check_qizheng_witness_chart(row, scope, instant, tail)
    _check_qizheng_sample_reading(row, chart, tail, sample, outer_selection)
    return scope, [(instant, instant, None, True)]


def _qizheng_chart_scope(document, instant, *, witness_chart=None):
    """Compare the inputs that determine a Qizheng chart, independent of the other systems' clock."""
    inputs = document.get('input')
    if not isinstance(inputs, dict):
        inputs = {}
    combined = _combined_snapshot(document)
    chart = witness_chart if witness_chart is not None else document.get('qizheng' if combined else 'chart')
    if not isinstance(chart, dict):
        return {}
    if 'jd_utc' in chart:
        julian_day = chart['jd_utc']
        expected = 2440587.5 + (instant - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400
        # The epoch conversion is compared within a millisecond to allow
        # roundoff in a Julian day stored as a double.
        if type(julian_day) not in (int, float) or not abs(julian_day - expected) <= 0.001 / 86400:
            raise ValueError('Qizheng native UTC Julian day disagrees with original birth instant')
    scope = {}
    profile = inputs.get('qizheng_profile' if combined else 'profile')
    native_profile = chart.get('calculation_profile')
    horizon = chart.get('horizon_contract')
    native_dut1 = horizon.get('dut1_seconds') if isinstance(horizon, dict) else None
    for field, values in (
        ('Qizheng calculation profile', [v for v in (profile, native_profile) if v in QIZHENG_PROFILES]),
        ('Qizheng DUT1', [v for v in (inputs.get('dut1_seconds'), native_dut1)
                         if type(v) in (int, float) and -0.9 <= v <= 0.9]),
    ):
        if values:
            if values[0] != values[-1]:
                raise ValueError('saved ' + field + ' disagrees with the native chart')
            scope[field] = values[0]
    latitude, longitude = inputs.get('lat'), inputs.get('lon')
    if type(latitude) in (int, float) and -90 <= latitude <= 90:
        scope['Qizheng birth latitude'] = latitude
    if type(longitude) in (int, float) and -180 <= longitude <= 180:
        scope['Qizheng birth longitude'] = 180 if longitude == -180 else longitude
        # The old day/night algorithm can give different results on the
        # same meridian when written as +180 and -180.
        if abs(longitude) == 180 and scope.get('Qizheng calculation profile') == 'legacy-v1':
            scope['Qizheng legacy longitude'] = longitude
    return scope


def validate(ledger, root):
    errors = []
    root = Path(root).resolve()
    catalog_root = Path(__file__).resolve().parents[1]
    try:
        catalog = json.loads((catalog_root / "knowledge/catalog.json").read_text(encoding="utf-8"))
        catalog_errors = _KNOWLEDGE.validate(catalog, catalog_root)
        if catalog_errors:
            return ["knowledge catalog: " + e for e in catalog_errors]
    except (OSError, ValueError) as exc:
        return ["knowledge catalog unavailable: " + str(exc)]

    def require(ok, message):
        if not ok:
            errors.append(message)
        return bool(ok)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def table(name):
        result = {}
        rows = ledger.get(name)
        if not require(isinstance(rows, list), name + " must be an array"):
            return result
        for row in rows:
            if not require(isinstance(row, dict) and text(row.get("id")), name + ": invalid record/id"):
                continue
            require(row["id"] not in result, name + ": duplicate id " + row["id"])
            result[row["id"]] = row
        return result

    def refs(row, key, target, nonempty=False):
        values = row.get(key)
        if not require(isinstance(values, list) and all(text(v) for v in values), row["id"] + ": invalid " + key):
            return []
        require(len(set(values)) == len(values), row["id"] + ": duplicate " + key)
        if nonempty:
            require(bool(values), row["id"] + ": empty " + key)
        for value in values:
            require(value in target, row["id"] + ": unknown " + key + " " + value)
        return [target[v] for v in values if v in target]

    if not isinstance(ledger, dict):
        return ["ledger must be an object"]
    require(type(ledger.get("schema_version")) is int and ledger.get("schema_version") == 1, "schema_version must be 1")
    require(ledger.get("purpose") in ("reading", "synthetic_test"), "invalid purpose")
    sources, scenarios, facts, rules, claims, links = [table(n) for n in
        ("sources", "scenarios", "facts", "rules", "claims", "syntheses")]
    # Reject malformed container/scalar types before graph traversal.
    for rows in (sources, scenarios, facts, rules, claims, links):
        for rid, row in rows.items():
            for key in ("system", "source_id", "scenario_id", "kind", "status", "boundary", "relation", "domain", "time_scope"):
                if key in row:
                    require(isinstance(row[key], str), rid + ": invalid type for " + key)
            for key in ("fact_ids", "rule_ids", "depends_on", "scenario_ids", "claim_ids"):
                if key in row:
                    require(isinstance(row[key], list) and all(text(v) for v in row[key]), rid + ": invalid type for " + key)
    if errors:
        return errors
    require(bool(scenarios), "at least one scenario required")
    require(bool(claims), "at least one claim required")
    content = {}
    chart_documents = {}
    chart_paths = {}
    for sid, source in sources.items():
        require(source.get("kind") in {"chart", "reference"}, sid + ": invalid source kind")
        try:
            if not text(source.get("path")):
                raise ValueError("missing source path")
            if Path(source["path"]).is_absolute():
                raise ValueError("source path must be relative")
            path = (root / source["path"]).resolve()
            path.relative_to(root)
            if not path.is_file():
                raise ValueError("source must be a regular file")
            if source.get("kind") == "chart":
                require(source.get("system") in SYSTEMS, sid + ": chart source requires system binding")
                require(source.get("scenario_id") in scenarios, sid + ": chart source requires scenario binding")
                prefix = source.get("pointer_prefix")
                require(text(prefix) and prefix.startswith("/"), sid + ": chart source requires pointer_prefix")
                prior = chart_paths.setdefault(path, [])
                for other in prior:
                    require(other.get("scenario_id") == source.get("scenario_id"), sid + ": chart path reused across scenarios")
                    a, b = other.get("pointer_prefix"), prefix
                    if text(a) and text(b) and (a == b or a.startswith(b + "/") or b.startswith(a + "/")):
                        require(other.get("system") == source.get("system"), sid + ": overlapping system scopes")
                prior.append(source)
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == source.get("sha256"), sid + ": source hash mismatch")
            if source.get("kind") == "chart":
                try:
                    chart_documents[sid] = _decode_json(raw.decode("utf-8"))
                except ValueError as exc:
                    errors.append(sid + ": invalid chart JSON: " + str(exc))
            else:
                content[sid] = raw.decode("utf-8")
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(sid + ": unreadable/out-of-root source: " + str(exc))
    for sid, scenario in scenarios.items():
        for key in ("label", "time_basis", "assumptions"):
            require(text(scenario.get(key)), sid + ": missing " + key)
    known_births = {}
    known_birth_spans = {}
    known_civil_offsets = {}
    known_civil_clock_windows = {}
    known_chart_scopes = {}
    checked_chart_sources = set()
    replayed_bazi_birth_analyses = {}
    verified_ziwei_candidates = set()
    verified_ziwei_charts = {}
    verified_ziwei_dynamic_facts = {}

    def record_chart_scope(scenario_id, evidence_id, scope):
        if not scope:
            return
        known = known_chart_scopes.setdefault(scenario_id, {})
        for key, value in scope.items():
            previous_id, previous_value = known.setdefault(key, (evidence_id, value))
            require(value == previous_value, evidence_id + ": conflicts with " + previous_id
                    + " on " + key + " for scenario " + scenario_id)

    for fid, fact in facts.items():
        require(fact.get("system") in SYSTEMS, fid + ": invalid system")
        require(fact.get("scenario_id") in scenarios, fid + ": unknown scenario")
        source = sources.get(fact.get("source_id", ""), {})
        require(source.get("kind") == "chart", fid + ": fact requires chart source")
        require(source.get("system") == fact.get("system"), fid + ": source system binding mismatch")
        require(source.get("scenario_id") == fact.get("scenario_id"), fid + ": source scenario binding mismatch")
        prefix, pointer = source.get("pointer_prefix"), fact.get("pointer")
        require(text(prefix) and text(pointer) and (pointer == prefix or pointer.startswith(prefix + "/")), fid + ": pointer outside system scope")
        try:
            if source.get("kind") == "chart" and fact["source_id"] not in chart_documents:
                continue
            document = chart_documents[fact["source_id"]]
            actual = _pointer(document, pointer)
            system = _snapshot_system(document, pointer)
            if system is not None:
                snapshot_kind = "combined snapshot" if _combined_snapshot(document) else "standalone snapshot"
                require(fact.get("system") == system, fid + ": " + snapshot_kind + " section belongs to " + system)
            require("value" in fact and _json_equal(actual, fact["value"]), fid + ": chart value mismatch")
            source_id = fact["source_id"]
            scenario_id = source.get("scenario_id")
            combined = _combined_snapshot(document)
            standalone_bazi = system == "bazi" and _standalone_bazi_birth_snapshot(document)
            standalone_ziwei = system == "ziwei" and not combined
            if system in SYSTEMS and source.get("system") == system and scenario_id in scenarios:
                label = {"bazi": "BaZi", "ziwei": "Ziwei", "qizheng": "Qizheng"}[system]
                try:
                    scope, spans = {}, None
                    if standalone_bazi:
                        if source_id not in replayed_bazi_birth_analyses:
                            replayed_bazi_birth_analyses[source_id] = _replayed_bazi_birth_analyses(document)
                        spans = _bazi_birth_spans(document, pointer, replayed_bazi_birth_analyses[source_id])
                    elif standalone_ziwei:
                        scope, spans = _ziwei_birth_scope(document, pointer, verified_ziwei_candidates)
                        if _standalone_ziwei_dynamic_facts(document):
                            _check_ziwei_dynamic_facts(document, pointer, scope, verified_ziwei_dynamic_facts)
                    elif system == "qizheng":
                        scope, spans = _qizheng_sampling_scope(document, pointer)
                    elif combined:
                        _check_combined_projection(document, pointer, system, verified_ziwei_charts)
                        scope, spans = _combined_candidate_birth_scope(document, pointer, system, verified_ziwei_candidates)
                    record_chart_scope(scenario_id, fid, scope)
                except (ValueError, OverflowError) as exc:
                    errors.append(fid + ": inconsistent " + label + " birth interval evidence: " + str(exc))
                    continue
                if spans is not None:
                    previous, sources_used = known_birth_spans.get(scenario_id, (None, set()))
                    labels = sources_used | {label}
                    common = spans if previous is None else _common_birth_spans(previous, spans)
                    if require(common, fid + ": no common " + "/".join(sorted(labels))
                               + " birth interval for scenario " + scenario_id):
                        known_birth_spans[scenario_id] = common, labels
            if (source.get("kind") == "chart" and scenario_id in scenarios and source_id not in checked_chart_sources
                    and (not standalone_ziwei or source.get("system") == "ziwei")):
                checked_chart_sources.add(source_id)
                if standalone_ziwei:
                    try:
                        windows = _ziwei_unlocated_civil_windows(document)
                    except (ValueError, OverflowError) as exc:
                        errors.append(source_id + ": inconsistent Ziwei civil clock evidence: " + str(exc))
                        continue
                    if windows is not None:
                        known_civil_clock_windows.setdefault(scenario_id, {})[source_id] = windows
                try:
                    instant = _exact_birth_instant(document)
                    scope = {}
                    if instant is not None:
                        if source.get('system') == 'qizheng':
                            scope = _qizheng_chart_scope(document, instant)
                        elif combined and source.get('system') in ('bazi', 'ziwei'):
                            scope = _selected_chart_scope(document, source['system'])
                    elif standalone_bazi and source.get("system") == "bazi":
                        if document.get("sex") in ("男", "女"):
                            scope["birth sex for BaZi/Ziwei"] = document["sex"]
                        if document.get("time_basis") == "civil":
                            scope["selected chart time basis"] = "civil"
                except (ValueError, OverflowError) as exc:
                    errors.append(source_id + ": inconsistent exact birth evidence: " + str(exc))
                    continue
                same_instant = True
                if instant is not None:
                    first_source, first_instant = known_births.setdefault(scenario_id, (source_id, instant))
                    same_instant = require(instant == first_instant, source_id + ": conflicts with " + first_source
                                           + " on exact birth instant for scenario " + scenario_id)
                    if same_instant and scope.get("selected chart time basis") == "civil":
                        original = _original_civil_clock(document["input"])
                        known_civil_offsets.setdefault(scenario_id, {})[source_id] = original - instant.replace(tzinfo=None)
                if same_instant:
                    record_chart_scope(scenario_id, source_id, scope)
        except (KeyError, IndexError, ValueError, TypeError):
            errors.append(fid + ": unresolved chart pointer")
    for scenario_id, sources_windows in known_civil_clock_windows.items():
        spans, labels = known_birth_spans.get(scenario_id, (None, set()))
        for clock_source, windows in sources_windows.items():
            if spans is not None:
                narrowed = _restrict_to_civil_clock(spans, windows)
                if require(narrowed, clock_source + ": confirmed Ziwei civil clock has no common birth interval for scenario "
                           + scenario_id):
                    spans = narrowed
                    known_birth_spans[scenario_id] = spans, labels | {"Ziwei"}
            for exact_source, offset in known_civil_offsets.get(scenario_id, {}).items():
                instant = known_births[scenario_id][1]
                exact = (instant, instant, offset, True)
                require(_restrict_to_civil_clock([exact], windows),
                        exact_source + ": exact civil birth instant outside the confirmed Ziwei clock windows of "
                        + clock_source + " for scenario " + scenario_id)
    for scenario_id, (spans, labels) in known_birth_spans.items():
        if scenario_id in known_births:
            source_id, instant = known_births[scenario_id]
            subject = "/".join(sorted(labels)) + " birth intervals"
            at_birth = {offset for start, end, offset, inclusive in spans
                        if start <= instant and (instant < end or (instant == end and inclusive))}
            if require(at_birth, source_id + ": exact birth instant outside the reachable " + subject + " "
                       "for scenario " + scenario_id):
                for civil_source, offset in known_civil_offsets.get(scenario_id, {}).items():
                    require(None in at_birth or offset in at_birth, civil_source + ": effective civil UTC offset disagrees with the "
                            + subject + " for scenario " + scenario_id)
    for rid, rule in rules.items():
        source = sources.get(rule.get("source_id", ""), {})
        require(source.get("kind") == "reference", rid + ": rule requires reference source")
        errors.extend(rid + ": " + e for e in _KNOWLEDGE.check_ledger_rule(rule, source, catalog))
        require(rule.get("system") in SYSTEMS, rid + ": invalid system")
        for key in ("school", "locator", "quote"):
            require(text(rule.get(key)), rid + ": missing " + key)
        start, end = rule.get("start_line"), rule.get("end_line")
        lines = content.get(rule.get("source_id"), "").splitlines()
        if require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), rid + ": invalid source line range"):
            require(text(rule.get("quote")) and rule["quote"] in "\n".join(lines[start-1:end]), rid + ": quote not found at source lines")
    for cid, claim in claims.items():
        require(claim.get("system") in SYSTEMS, cid + ": invalid system")
        require(claim.get("status") in {"supported", "conditional", "withheld"}, cid + ": invalid status")
        require(claim.get("boundary") in {"stable", "conditional", "unassessed"}, cid + ": invalid boundary")
        for key in ("statement", "domain", "time_scope", "conditions", "counterevidence", "alternatives", "limitations"):
            require(text(claim.get(key)), cid + ": missing " + key)
        explanation = claim.get("explanation", {})
        if require(isinstance(explanation, dict), cid + ": invalid explanation"):
            for key in ("plain", "technical", "action"):
                require(text(explanation.get(key)), cid + ": missing explanation." + key)
        active = claim.get("status") != "withheld"
        evidence = refs(claim, "fact_ids", facts, active)
        citations = refs(claim, "rule_ids", rules, active)
        dependencies = refs(claim, "depends_on", claims)
        covered = refs(claim, "scenario_ids", scenarios, True)
        for row in evidence + citations + dependencies:
            require(row.get("system") == claim.get("system"), cid + ": cross-system evidence/dependency")
        for row in evidence:
            require(row.get("scenario_id") in claim.get("scenario_ids", []), cid + ": fact outside claim scenarios")
        if claim.get("boundary") == "stable":
            require(len(covered) == len(scenarios), cid + ": stable claim must cover every scenario")
            require(set(f.get("scenario_id") for f in evidence) == set(scenarios), cid + ": stable claim lacks evidence for a scenario")
        if claim.get("boundary") != "stable":
            require(claim.get("status") != "supported", cid + ": unassessed/conditional boundary cannot be supported")
        for dependency in dependencies:
            require(set(claim.get("scenario_ids", [])) <= set(dependency.get("scenario_ids", [])), cid + ": dependency does not cover claim scenarios")
            require(claim.get("time_scope") == dependency.get("time_scope"), cid + ": dependency time_scope mismatch")
            require(dependency.get("status") != "withheld" or not active, cid + ": depends on withheld claim")
            require(dependency.get("status") != "conditional" or claim.get("status") != "supported", cid + ": cannot strengthen conditional dependency")
    # A narrow opt-in for explanations, not promotion of quarantined text to predictions.
    restricted_rules = {}
    for rid, rule in rules.items():
        rec = _KNOWLEDGE.interpretation_record(rule, sources.get(rule.get('source_id'), {}), catalog)
        if rec is not None:
            restricted_rules[rid] = rec
            registered = next(s for s in catalog['sources'] if s['id'] == rec['source_id'])
            expected_notice = _KNOWLEDGE.local_file(catalog_root, registered['license_path']).read_text(encoding='utf-8')
            metadata = rule.get('redistribution')
            require(isinstance(metadata, dict) and metadata.get('license_notice') == expected_notice,
                    rid + ': redistribution license_notice must preserve the complete registered license')

    def restricted_declarations(row, rid):
        require(row.get('reading_use') == _KNOWLEDGE.TRADITIONAL_USE, rid + ': restricted interpretation reading_use required')
        require(row.get('interpretation_label') == _KNOWLEDGE.TRADITIONAL_LABEL, rid + ': uncollated interpretation label required')
        require(row.get('authenticity_status') == 'uncollated_digital_transcription', rid + ': verified authority claim forbidden')
        require(row.get('predictive_status') == 'unvalidated', rid + ': interpretation is not predictively validated')
        require(row.get('guaranteed_prediction') is False, rid + ': guaranteed prediction forbidden')
        require(row.get('domain') == '传统结构解释', rid + ': restricted to traditional structural explanation')
        require(row.get('status') in ('conditional', 'withheld'), rid + ': interpretation cannot become supported')

    restricted_claims = {cid for cid, claim in claims.items()
                         if any(rid in restricted_rules for rid in claim.get('rule_ids', []))}
    # Preserve the limit transitively so another claim cannot launder the interpretation.
    changed = True
    while changed:
        before = len(restricted_claims)
        restricted_claims.update(cid for cid, claim in claims.items()
                                 if any(dep in restricted_claims for dep in claim.get('depends_on', [])))
        changed = before != len(restricted_claims)
    for cid in restricted_claims:
        claim = claims[cid]
        restricted_declarations(claim, cid)
        checks = claim.get('application_checks')
        if not require(isinstance(checks, list), cid + ': application_checks required'):
            continue
        expected = {rid for rid in claim.get('rule_ids', []) if rid in restricted_rules}
        ids = [row.get('rule_id') for row in checks if isinstance(row, dict)]
        if not require(len(ids) == len(checks) and len(set(str(v) for v in ids)) == len(ids)
                       and set(str(v) for v in ids) == expected, cid + ': checks must cover each restricted rule once'):
            continue
        for check in checks:
            rec = restricted_rules[check['rule_id']]
            for field, terms in [('conditions', rec['conditions']), ('exclusions', rec['exclusions'])]:
                rows = check.get(field)
                if not require(isinstance(rows, list) and len(rows) == len(terms), cid + ': complete ' + field + ' checklist required'):
                    continue
                for row, term in zip(rows, terms):
                    if not require(isinstance(row, dict), cid + ': invalid checklist item'):
                        continue
                    require(row.get('criterion') == term, cid + ': criterion must match registered card')
                    require(text(row.get('assessment')), cid + ': checklist assessment required')
                    allowed = {'met', 'not_met', 'unknown'} if field == 'conditions' else {'reviewed', 'unresolved'}
                    require(isinstance(row.get('result'), str) and row.get('result') in allowed, cid + ': invalid checklist result')
                    if claim.get('status') != 'withheld':
                        require(row.get('result') == ('met' if field == 'conditions' else 'reviewed'),
                                cid + ': unmet or unresolved criteria require withholding')
                    bound = row.get('fact_ids')
                    require(isinstance(bound, list) and bool(bound) and all(isinstance(v, str) and v in claim.get('fact_ids', []) for v in bound),
                            cid + ': each checklist item needs bound chart facts')
                    if isinstance(bound, list):
                        scenarios_seen = {facts[v]['scenario_id'] for v in bound if isinstance(v, str) and v in facts}
                        require(set(claim.get('scenario_ids', [])) <= scenarios_seen,
                                cid + ': checklist missing scenario evidence')
    for lid, link in links.items():
        if any(cid in restricted_claims for cid in link.get('claim_ids', [])):
            restricted_declarations(link, lid)
            if any(claims[cid].get('status') == 'withheld' for cid in link.get('claim_ids', []) if cid in claims):
                require(link.get('status') == 'withheld', lid + ': synthesis cannot strengthen a withheld member')
    visiting, visited = set(), set()
    def walk(cid):
        if cid in visiting:
            errors.append(cid + ": cyclic claim dependency")
            return
        if cid in visited:
            return
        visiting.add(cid)
        dependencies = claims[cid].get("depends_on", [])
        if isinstance(dependencies, list):
            for dep in dependencies:
                if isinstance(dep, str) and dep in claims:
                    walk(dep)
        visiting.remove(cid)
        visited.add(cid)
    for cid in claims:
        walk(cid)
    for lid, link in links.items():
        members = refs(link, "claim_ids", claims, True)
        require(len({c.get("system") for c in members}) >= 2, lid + ": synthesis requires independent systems")
        require(link.get("relation") in {"agreement", "conflict", "different_scope", "insufficient"}, lid + ": invalid relation")
        for key in ("explanation", "shared_inputs", "limits"):
            require(text(link.get(key)), lid + ": missing " + key)
        relation = link.get("relation")
        if relation in ("agreement", "conflict"):
            require(all(c.get("status") != "withheld" for c in members), lid + ": " + relation + " uses withheld claim")
            for key in ("domain", "time_scope"):
                require(len({c.get(key) for c in members}) == 1, lid + ": " + relation + " has mismatched " + key)
            require(len({tuple(sorted(c.get("scenario_ids", []))) for c in members}) == 1, lid + ": " + relation + " has mismatched scenarios")
    # This field check is deliberately narrow, not a claim to detect unsafe prose.
    for rows in (claims, links):
        for cid, row in rows.items():
            require(not ({"probability", "confidence_percent", "accuracy_percent", "stars"} & set(row)), cid + ": unsupported numeric/star confidence field")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--root", type=Path, required=True, help="Private evidence directory; sources cannot escape it")
    args = parser.parse_args()
    try:
        data = _decode_json(args.ledger.read_text(encoding="utf-8"))
        errors = validate(data, args.root)
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"ok": False, "input_error": str(exc)}, ensure_ascii=False))
        return 2
    unverified = [r.get("id") for r in data.get("rules", []) if isinstance(r, dict) and r.get("attribution_kind") == "caller_declared_unverified"] if isinstance(data, dict) and isinstance(data.get("rules"), list) else []
    print(json.dumps({"ok": not errors, "errors": errors,
        "caller_declared_unverified_rule_ids": unverified,
        "provenance_notice": "未知资料即使标签齐全仍未验证来源；通过只表示结构与标签一致，不是原典认证",
        "scope": "结构、引用和文件一致性；不验证推断正确性或预测能力"}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
