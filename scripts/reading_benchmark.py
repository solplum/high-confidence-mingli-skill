#!/usr/bin/env python3
"""Prepare blind, case-separated reading evaluations; never call a chart engine.

All dataset-derived files must live outside this repository.  ``prepare`` keeps
the unmodified source and answer key in a private evaluation directory.  Only
``export`` output may be passed to an analyst.  A holdout export requires an
explicit flag; this program never runs an analyst or adds cases to knowledge/.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
VERSION = 1
DEFAULT_SEED = "mingli-reading-v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
TIME_UNCERTAINTY = re.compile(
    r"反推.{0,12}(?:时辰|時辰|生时|生時)|(?:时辰|時辰).{0,8}反推|"
    r"(?:时辰|時辰|生时|生時|出生时间|出生時間)[不未无無][详詳明知定]|"
    r"(?:未知|不知)(?:时辰|時辰|生时|生時)", re.I
)


class BenchmarkError(ValueError):
    """Invalid or incomplete evaluation input; no score should be emitted."""


def external_path(value):
    path = Path(value).expanduser().resolve()
    if path == REPOSITORY or REPOSITORY in path.parents:
        raise BenchmarkError("Dataset-derived files must be outside repository: %s" % path)
    return path


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    path = external_path(path)
    if path.exists():
        raise BenchmarkError("refusing to overwrite an existing file: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            created = True
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        # A writer may create the destination during serialization. Linking a
        # complete same-directory file publishes atomically without replacement.
        os.link(str(temporary), str(path))
    finally:
        if created and temporary.exists():
            temporary.unlink()


def digest(*parts):
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tool_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def split_for_case(case_id, seed):
    # A threshold, rather than ranking the current dataset, keeps membership
    # stable when additional subjects are added in a later source snapshot.
    value = int(digest(seed, "split", case_id), 16)
    return "holdout" if value < (1 << 256) // 4 else "development"


def integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


def present(value):
    return value is not None and value != ""


def normalize_birth(source):
    """Use structured birth fields only; raw/master prose is never exported."""
    reasons, flags, birth = [], ["timezone_unknown"], {}
    if not isinstance(source, dict):
        return birth, ["birth_info_not_object"], flags
    calendar_value = str(source.get("calendar_type") or "unknown").strip().lower()
    calendars = {
        "solar": "solar", "gregorian": "solar", "公历": "solar", "阳历": "solar",
        "陽曆": "solar", "公曆": "solar", "lunar": "lunar", "农历": "lunar",
        "農曆": "lunar", "阴历": "lunar", "陰曆": "lunar",
    }
    calendar_type = calendars.get(calendar_value, "unknown")
    birth["calendar_type"] = calendar_type
    if calendar_type == "unknown":
        flags.append("calendar_unknown")
    values = {}
    for key in ("year", "month", "day"):
        value = source.get(key)
        values[key] = integer(value)
        if not present(value):
            reasons.append("missing_birth_%s" % key)
        elif values[key] is None:
            reasons.append("invalid_birth_%s" % key)
        else:
            birth[key] = values[key]
    if all(values[key] is not None for key in values):
        year, month, day = (values[key] for key in ("year", "month", "day"))
        if calendar_type == "lunar":
            if not (1 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 30):
                reasons.append("invalid_birth_date")
            else:
                flags.append("lunar_date_requires_calendar_validation")
                flags.append("lunar_leap_month_unspecified")
        else:
            try:
                datetime.date(year, month, day)
            except ValueError:
                reasons.append("invalid_birth_date")
    sex = source.get("gender", source.get("sex"))
    normalized_sex = {
        "男": "male", "男性": "male", "male": "male", "m": "male",
        "女": "female", "女性": "female", "female": "female", "f": "female",
    }.get(str(sex).strip().lower())
    if normalized_sex is None:
        reasons.append("unrecognized_birth_sex")
    else:
        birth["sex"] = normalized_sex
    clock_hour = integer(source.get("clock_hour"))
    clock_minute = integer(source.get("clock_minute"))
    valid_clock = clock_hour is not None and 0 <= clock_hour <= 23
    if present(source.get("clock_hour")):
        if valid_clock:
            birth["clock_hour"] = clock_hour
        else:
            reasons.append("invalid_clock_hour")
    if present(source.get("clock_minute")):
        if clock_minute is None or not 0 <= clock_minute <= 59:
            reasons.append("invalid_clock_minute")
        else:
            birth["clock_minute"] = clock_minute
    elif valid_clock:
        flags.append("clock_minute_unspecified")
    shichen = str(source.get("shichen") or "").strip()
    branch = re.fullmatch("([%s])(?:时|時)?" % BRANCHES, shichen)
    if branch:
        birth["shichen"] = branch.group(1)
        flags.append("two_hour_branch_provided")
    start, end = integer(source.get("hour_start")), integer(source.get("hour_end"))
    valid_range = start is not None and end is not None and 0 <= start <= 23 and 0 <= end <= 24 and start != end
    if valid_range:
        birth["hour_start"], birth["hour_end"] = start, end
        flags.append("birth_time_is_range")
    elif present(source.get("hour_start")) or present(source.get("hour_end")):
        flags.append("incomplete_or_invalid_time_range")
    clock_branch = BRANCHES[((clock_hour + 1) // 2) % 12] if valid_clock else None
    contradictions = bool(branch and valid_clock and branch.group(1) != clock_branch)
    if valid_range:
        duration = (end - start) % 24 or 24
        covered_hours = {(start + offset) % 24 for offset in range(duration)}
        if valid_clock and clock_hour not in covered_hours:
            contradictions = True
        if branch and any(BRANCHES[((hour + 1) // 2) % 12] != branch.group(1) for hour in covered_hours):
            contradictions = True
    if contradictions:
        # This only detects inconsistent input labels. It does not select a
        # clock correction, true-solar conversion or a school-specific rollover.
        flags.append("contradictory_time_fields")
    uncertainty_prose = " ".join(str(source.get(key) or "") for key in ("raw", "reason", "shichen"))
    marker = TIME_UNCERTAINTY.search(uncertainty_prose)
    if marker:
        reasons.append("reverse_inferred_birth_time" if "反推" in marker.group() else "unknown_birth_time")
    if not (valid_clock or branch or valid_range):
        reasons.append("missing_usable_birth_time")
    if source.get("shichen_derived_from_clock") is True:
        flags.append("source_branch_derived_from_clock")
    for key in ("location", "country"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            birth[key] = value.strip()
    if "location" not in birth:
        flags.append("birth_location_missing")
    missing = source.get("missing")
    if missing:
        flags.append("source_declares_missing_birth_fields")
    return birth, list(dict.fromkeys(reasons)), list(dict.fromkeys(flags))


def normalize_options(value):
    if not isinstance(value, list) or len(value) < 2:
        raise BenchmarkError("options must contain at least two letter/text objects")
    options, letters = [], set()
    for option in value:
        if not isinstance(option, dict):
            raise BenchmarkError("option must be an object")
        letter, label = option.get("letter"), option.get("text")
        if not isinstance(letter, str) or not re.fullmatch(r"[A-Z]", letter):
            raise BenchmarkError("option letter must be one uppercase letter")
        if letter in letters:
            raise BenchmarkError("duplicate option letter")
        if not isinstance(label, str) or not label.strip():
            raise BenchmarkError("option text must be nonempty")
        letters.add(letter)
        options.append({"letter": letter, "text": label})
    return options


def source_records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("questions", "items", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise BenchmarkError("source must be a JSON array, or contain questions/items/data array")


def prepare(source_path, output_dir, source_repo, source_ref, source_license, seed=DEFAULT_SEED):
    source_path, output_dir = external_path(source_path), external_path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BenchmarkError("evaluation output directory must be empty")
    if not all(isinstance(value, str) and value.strip() for value in (source_repo, source_ref, source_license, seed)):
        raise BenchmarkError("source repo, ref, license citation and seed are required")
    source_bytes = source_path.read_bytes()
    payload = json.loads(source_bytes.decode("utf-8"))
    entries, seen = [], set()
    for index, record in enumerate(source_records(payload)):
        if not isinstance(record, dict):
            raise BenchmarkError("source record %d must be an object" % index)
        original_id = record.get("id")
        if not isinstance(original_id, (str, int)) or isinstance(original_id, bool) or str(original_id) == "":
            raise BenchmarkError("record %d has no usable id" % index)
        original_id = str(original_id)
        if original_id in seen:
            raise BenchmarkError("duplicate source id: %s" % original_id)
        seen.add(original_id)
        original_case = record.get("case_id")
        usable_case = isinstance(original_case, (str, int)) and not isinstance(original_case, bool) and str(original_case) != ""
        case_key = str(original_case) if usable_case else "missing-case-for-item:" + original_id
        reasons = [] if usable_case else ["missing_case_id"]
        if record.get("answer_provenance") != "official":
            reasons.append("answer_not_official")
        birth, birth_reasons, flags = normalize_birth(record.get("birth_info"))
        reasons.extend(birth_reasons)
        question = record.get("question")
        if not isinstance(question, str) or not question.strip():
            reasons.append("missing_question")
        options = []
        try:
            options = normalize_options(record.get("options"))
        except BenchmarkError as error:
            reasons.append("invalid_options: " + str(error))
        answer = record.get("answer")
        if not isinstance(answer, str) or answer not in {option["letter"] for option in options}:
            reasons.append("invalid_answer_letter")
        entries.append({
            "item_id": "item-" + digest(seed, "item", original_id)[:20],
            "case_id": "case-" + digest(seed, "case", case_key)[:20],
            "source_id": original_id, "source_case_id": original_case,
            "split": split_for_case(case_key, seed), "eligible": not reasons,
            "exclusion_reasons": reasons, "uncertainty_flags": flags,
            "birth": birth, "question": question, "options": options, "answer": answer,
        })
    metadata = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_repository": source_repo, "source_ref": source_ref,
        "source_license_notice_and_citation": source_license, "seed": seed,
        "preparation_tool_sha256": tool_sha256(),
        "filter_rule": "official answer; structured complete date with nominal calendar checks; recognizable sex; clock, branch or range; exclude unknown/reverse-inferred time; chart feasibility remains analyst judgment",
        "split_rule": "sha256(JSON([seed, 'split', source_case_id])) < 2^256 / 4 is holdout; all items of a case share split; stable when cases are added",
        "blind_rule": "structured birth whitelist only; no raw prose, stated pillars, answer provenance, source URL, master/method/outcome metadata or precomputed charts",
        "unit_notice": "questions are clustered within subjects; item count is not independent person count",
        "score_scope": "competition-label question scores; not real-world predictive accuracy",
        "calendar_notice": "lunar dates receive nominal month/day bounds only and require analyst calendar validation; unknown calendar is flagged",
    }
    evaluation = {"schema_version": VERSION, "metadata": metadata, "entries": entries}
    output_dir.mkdir(parents=True, exist_ok=True)
    # Keep exact bytes, including every excluded record and source field.
    with (output_dir / "source.json").open("xb") as handle:
        handle.write(source_bytes)
    write_json(output_dir / "evaluation.json", evaluation)
    report = preparation_report(evaluation)
    write_json(output_dir / "preparation-report.json", report)
    return report


def preparation_report(evaluation):
    entries = evaluation["entries"]
    eligible = [entry for entry in entries if entry["eligible"]]
    exclusions = {}
    for entry in entries:
        for reason in entry["exclusion_reasons"]:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    splits = {}
    for split in ("development", "holdout"):
        selected = [entry for entry in eligible if entry["split"] == split]
        splits[split] = {"items": len(selected), "cases": len({entry["case_id"] for entry in selected}),
                         "case_ids": sorted({entry["case_id"] for entry in selected})}
    return {"schema_version": VERSION, "metadata": evaluation["metadata"],
            "total_items": len(entries), "eligible_items": len(eligible),
            "excluded_items": len(entries) - len(eligible), "exclusion_reason_counts": exclusions,
            "splits": splits}


def load_evaluation(directory):
    directory = external_path(directory)
    evaluation = read_json(directory / "evaluation.json")
    actual_hash = hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()
    if evaluation.get("schema_version") != VERSION or actual_hash != evaluation["metadata"]["source_sha256"]:
        raise BenchmarkError("evaluation source checksum or schema mismatch")
    return evaluation


def blind_item(entry):
    return {"item_id": entry["item_id"], "case_id": entry["case_id"],
            "birth": dict(entry["birth"]), "uncertainty_flags": list(entry["uncertainty_flags"]),
            "question": entry["question"], "options": entry["options"]}


def make_pack(evaluation, system, split="development", case_limit=None, case_ids=None, allow_holdout=False):
    if system not in ("bazi", "ziwei"):
        raise BenchmarkError("system must be bazi or ziwei")
    if split not in ("development", "holdout"):
        raise BenchmarkError("unknown split")
    if split == "holdout" and not allow_holdout:
        raise BenchmarkError("holdout requires explicit --allow-holdout")
    entries = [entry for entry in evaluation["entries"] if entry["eligible"] and entry["split"] == split]
    available = sorted({entry["case_id"] for entry in entries})
    if case_ids:
        if len(case_ids) != len(set(case_ids)) or not set(case_ids) <= set(available):
            raise BenchmarkError("duplicate or unavailable case ID for requested split")
        available = sorted(case_ids)
    if case_limit is not None:
        if case_limit <= 0:
            raise BenchmarkError("case limit must be positive")
        available = available[:case_limit]
    chosen = set(available)
    entries = sorted((entry for entry in entries if entry["case_id"] in chosen), key=lambda entry: (entry["case_id"], entry["item_id"]))
    if not entries:
        raise BenchmarkError("no eligible cases for requested selection")
    return {"schema_version": VERSION,
            "task": {"system": system,
                     "instruction": "Use only the specified system and supplied structured birth facts. Decide whether birth uncertainty permits a reading. Return one response per item: answer letter, or abstain=true with a nonempty reason. Do not seek case identities or answer keys. No supplied chart is ground truth."},
            "items": [blind_item(entry) for entry in entries]}


def export_pack(evaluation_dir, output, system, split="development", case_limit=None, case_ids=None, allow_holdout=False):
    output = external_path(output)
    pack = make_pack(load_evaluation(evaluation_dir), system, split, case_limit, case_ids, allow_holdout)
    write_json(output, pack)
    return {"system": system, "split": split, "items": len(pack["items"]),
            "cases": len({item["case_id"] for item in pack["items"]}), "output": str(output)}


def score(evaluation_dir, pack_path, responses_path, output=None):
    evaluation = load_evaluation(evaluation_dir)
    pack = read_json(external_path(pack_path))
    if not isinstance(pack, dict) or pack.get("schema_version") != VERSION or not isinstance(pack.get("items"), list) or not pack["items"]:
        raise BenchmarkError("invalid or empty analyst pack")
    system = pack.get("task", {}).get("system")
    if system not in ("bazi", "ziwei"):
        raise BenchmarkError("invalid analyst system")
    known = {entry["item_id"]: entry for entry in evaluation["entries"] if entry["eligible"]}
    requested, splits = {}, set()
    for item in pack["items"]:
        if not isinstance(item, dict) or item.get("item_id") not in known:
            raise BenchmarkError("unknown item in analyst pack")
        item_id = item["item_id"]
        if item_id in requested:
            raise BenchmarkError("duplicate item in analyst pack")
        entry = known[item_id]
        if item != blind_item(entry):
            raise BenchmarkError("analyst pack does not match prepared source")
        requested[item_id] = entry
        splits.add(entry["split"])
    if len(splits) != 1:
        raise BenchmarkError("analyst pack mixes development and holdout")
    # A case selection always carries all its eligible questions. Dropping hard
    # questions from a pack must not improve the reported score.
    selected_cases = {entry["case_id"] for entry in requested.values()}
    complete_ids = {entry["item_id"] for entry in known.values() if entry["case_id"] in selected_cases}
    if set(requested) != complete_ids:
        raise BenchmarkError("analyst pack omits eligible questions from a selected case")
    responses = read_json(external_path(responses_path))
    if isinstance(responses, dict):
        responses = responses.get("responses")
    if not isinstance(responses, list):
        raise BenchmarkError("responses must be an array or {responses: [...]} object")
    received, results = set(), []
    for response in responses:
        if not isinstance(response, dict):
            raise BenchmarkError("each response must be an object")
        item_id = response.get("item_id")
        if not isinstance(item_id, str) or item_id not in requested:
            raise BenchmarkError("unknown response item ID")
        if item_id in received:
            raise BenchmarkError("duplicate response item ID: %s" % item_id)
        received.add(item_id)
        entry = requested[item_id]
        abstain = response.get("abstain", False)
        if not isinstance(abstain, bool):
            raise BenchmarkError("abstain must be boolean")
        if abstain:
            reason = response.get("reason")
            if present(response.get("answer")) or not isinstance(reason, str) or not reason.strip():
                raise BenchmarkError("abstention requires a reason and no answer")
            status, answer = "abstained", None
        else:
            answer = response.get("answer")
            if not isinstance(answer, str) or answer not in {option["letter"] for option in entry["options"]}:
                raise BenchmarkError("response requires a valid answer or abstention with reason")
            status = "correct" if answer == entry["answer"] else "wrong"
        results.append({"item_id": item_id, "case_id": entry["case_id"], "status": status,
                        "answer": answer, "expected_answer": entry["answer"],
                        "reason": response.get("reason", "")})
    missing = set(requested) - received
    if missing:
        raise BenchmarkError("missing responses for %d item(s): %s" % (len(missing), ", ".join(sorted(missing))))
    total = len(requested)
    correct = sum(result["status"] == "correct" for result in results)
    wrong = sum(result["status"] == "wrong" for result in results)
    abstained = sum(result["status"] == "abstained" for result in results)
    answered = correct + wrong
    expected = sum(1.0 / len(entry["options"]) for entry in requested.values())
    case_counts = {"total": len(selected_cases)}
    for name, statuses in (("answered", {"correct", "wrong"}), ("with_correct", {"correct"}),
                           ("with_wrong", {"wrong"}), ("with_abstention", {"abstained"})):
        case_counts[name] = len({result["case_id"] for result in results if result["status"] in statuses})
    case_counts["fully_answered"] = case_counts["total"] - case_counts["with_abstention"]
    report = {"schema_version": VERSION, "system": system, "split": next(iter(splits)),
              "total": total, "answered": answered, "correct": correct, "wrong": wrong,
              "abstained": abstained, "coverage": answered / total,
              "accuracy_all": correct / total,
              "accuracy_answered": correct / answered if answered else None,
              "random_guess_expectation": {"correct": expected, "accuracy": expected / total},
              "case_counts": case_counts,
              "metadata": dict(evaluation["metadata"], scoring_tool_sha256=tool_sha256()),
              "results": sorted(results, key=lambda result: result["item_id"])}
    if output is not None:
        write_json(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare", help="keep raw source/key externally and record every exclusion")
    command.add_argument("--source", required=True)
    command.add_argument("--output-dir", required=True)
    command.add_argument("--source-repo", required=True)
    command.add_argument("--source-ref", required=True)
    command.add_argument("--source-license", required=True)
    command.add_argument("--seed", default=DEFAULT_SEED)
    command = commands.add_parser("export", help="export a blind pack, development by default")
    command.add_argument("--evaluation-dir", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--system", choices=("bazi", "ziwei"), required=True)
    command.add_argument("--split", choices=("development", "holdout"), default="development")
    command.add_argument("--case-limit", type=int)
    command.add_argument("--case-id", action="append", dest="case_ids")
    command.add_argument("--allow-holdout", action="store_true")
    command = commands.add_parser("score", help="require one valid response per exported question")
    command.add_argument("--evaluation-dir", required=True)
    command.add_argument("--pack", required=True)
    command.add_argument("--responses", required=True)
    command.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.source, args.output_dir, args.source_repo, args.source_ref, args.source_license, args.seed)
        elif args.command == "export":
            result = export_pack(args.evaluation_dir, args.output, args.system, args.split, args.case_limit, args.case_ids, args.allow_holdout)
        else:
            result = score(args.evaluation_dir, args.pack, args.responses, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (BenchmarkError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, "reading_benchmark: %s\n" % error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
