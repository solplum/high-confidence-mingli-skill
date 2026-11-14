"""Synthetic fixtures exercise isolation and scoring; no real benchmark data."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reading_benchmark.py"
SPEC = importlib.util.spec_from_file_location("reading_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def synthetic_item(case_number=0, item_number=0, option_count=3):
    return {
        "id": "synthetic-source-master-%d-%d" % (case_number, item_number),
        "case_id": "synthetic-person-outcome-%d" % case_number,
        "year": 2099,
        "birth_info": {"year": 1988, "month": 2, "day": 29,
                       "calendar_type": "solar", "gender": "女",
                       "clock_hour": 9, "clock_minute": 12, "shichen": "巳",
                       "hour_start": 9, "hour_end": 11,
                       "location": "合成地点", "country": "合成国家",
                       "raw": "SECRET_RAW_EXPERIENCE_DO_NOT_EXPORT",
                       "pillars_stated_by_master": "SECRET_PRECOMPUTED_PILLARS",
                       "reason": "SECRET_SOURCE_NOTE", "missing": []},
        "question": "合成题目%d" % item_number,
        "options": [{"letter": chr(65 + index), "text": "合成选项%d" % index,
                     "outcome": "SECRET_OPTION_METADATA"} for index in range(option_count)],
        "answer": "A", "answer_provenance": "official",
        "source_url": "https://synthetic.invalid/SECRET_SOURCE_URL",
        "master": "SECRET_MASTER", "method": "SECRET_METHOD",
        "outcome": "SECRET_OUTCOME",
    }


class ReadingBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reading-benchmark-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "synthetic-source.json"
        self.evaluation = self.directory / "evaluation"

    def write(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def write_responses(self, name, pack_path, responses):
        pack_bytes = pack_path.read_bytes()
        return self.write(name, {
            "system": json.loads(pack_bytes)["task"]["system"],
            "pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
            "responses": responses,
        })

    def prepare(self, records):
        self.source.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        report = benchmark.prepare(self.source, self.evaluation,
                                   "https://synthetic.invalid/repository", "synthetic-ref",
                                   "Synthetic fixture license citation; not a real source")
        return benchmark.load_evaluation(self.evaluation), report

    def development_case(self):
        for number in range(100):
            if benchmark.split_for_case("synthetic-person-outcome-%d" % number,
                                        benchmark.DEFAULT_SEED) == "development":
                return number
        self.fail("test fixture could not choose a development case")

    def prepare_pack(self, option_counts=(2, 3, 5)):
        case = self.development_case()
        data, _ = self.prepare([synthetic_item(case, index, count) for index, count in enumerate(option_counts)])
        pack = benchmark.make_pack(data, "bazi")
        pack_path = self.write("pack.json", pack)
        return data, pack, pack_path

    def test_source_question_collections_must_be_unambiguous(self):
        question = synthetic_item(self.development_case())
        for key in ("questions", "items", "data"):
            with self.subTest(key=key):
                self.assertEqual(benchmark.source_records({key: [question]}), [question])
        self.assertEqual(benchmark.source_records([question]), [question])

        self.source.write_text(json.dumps({"questions": [question], "items": [dict(question, answer="B")]}))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "multiple supported question arrays"):
            benchmark.prepare(self.source, self.evaluation, "synthetic://source", "fixed", "Synthetic test only")
        self.assertFalse(self.evaluation.exists())

    def test_report_marks_identical_questions_across_splits_without_changing_scores(self):
        development = synthetic_item(self.development_case())
        holdout_case = next(number for number in range(100) if benchmark.split_for_case(
            "synthetic-person-outcome-%d" % number, benchmark.DEFAULT_SEED) == "holdout")
        duplicate = synthetic_item(holdout_case)
        duplicate["answer"] = "B"
        duplicate["birth_info"]["shichen_derived_from_clock"] = True
        other = synthetic_item(holdout_case, item_number=1)
        data, preparation = self.prepare([development, duplicate, other])

        summary = preparation["cross_split_duplicates"]
        self.assertEqual(summary["groups"], 1)
        self.assertEqual(summary["affected_items"], {"development": 1, "holdout": 1})
        pack_path = self.directory / "held-pack.json"
        receipt = benchmark.export_pack(self.evaluation, pack_path, "bazi", "holdout", allow_holdout=True)
        pack = benchmark.read_json(pack_path)
        self.assertEqual(pack, benchmark.make_pack(data, "bazi", "holdout", allow_holdout=True))
        self.assertEqual(set(pack), {"schema_version", "task", "items"})
        responses = self.write_responses("held-responses.json", pack_path,
                                         [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
        score = benchmark.score(self.evaluation, pack_path, responses,
                                expected_pack_sha256=receipt["pack_sha256"],
                                expected_source_sha256=receipt["source_sha256"])
        duplicate_id = next(item["item_id"] for item in pack["items"] if item["question"] == duplicate["question"])
        self.assertEqual(score["cross_split_duplicates"], dict(summary, scored_item_ids=[duplicate_id]))
        self.assertEqual((score["total"], score["correct"], score["wrong"]), (2, 1, 1))

    def test_rearranged_choices_are_flagged_without_changing_pack_or_score(self):
        development = synthetic_item(self.development_case())
        holdout_case = next(number for number in range(100) if benchmark.split_for_case(
            "synthetic-person-outcome-%d" % number, benchmark.DEFAULT_SEED) == "holdout")
        records = [synthetic_item(holdout_case, number) for number in range(7)]
        exact, reordered, relabeled, changed_text, changed_birth, duplicate_text, changed_question = records
        for repeated in (exact, reordered, relabeled, changed_text, changed_birth, duplicate_text):
            repeated["question"] = development["question"]
        reordered["options"].reverse()
        relabeled["options"][0]["letter"] = "C"
        relabeled["options"][2]["letter"] = "A"
        relabeled["answer"] = "C"
        changed_text["options"][0]["text"] += "变更"
        changed_birth["birth_info"]["clock_minute"] = 13
        duplicate_text["options"][0]["text"] = duplicate_text["options"][1]["text"]
        _, preparation = self.prepare([development, *records])
        self.assertEqual(preparation["cross_split_duplicates"]["groups"], 1)
        overlap = preparation["cross_split_rearranged_choices"]
        self.assertEqual(overlap["groups"], 1)
        self.assertEqual(overlap["affected_items"], {"development": 1, "holdout": 2})
        pack_path = self.directory / "held-pack.json"
        receipt = benchmark.export_pack(self.evaluation, pack_path, "bazi", "holdout", allow_holdout=True)
        pack = benchmark.read_json(pack_path)
        responses = self.write_responses("held-responses.json", pack_path,
                                         [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
        scored = benchmark.score(self.evaluation, pack_path, responses, expected_pack_sha256=receipt["pack_sha256"])
        affected = sorted(item["item_id"] for item in pack["items"] if
                          item["options"][0]["letter"] == "C")
        self.assertEqual(len(affected), 2)
        self.assertEqual(scored["cross_split_rearranged_choices"], dict(overlap, scored_item_ids=affected))
        self.assertEqual((scored["total"], scored["correct"], scored["wrong"]), (7, 6, 1))

    def test_birth_match_flags_all_questions_for_overlapping_case_ids(self):
        dev_case = self.development_case()
        held = [number for number in range(100) if benchmark.split_for_case(
            "synthetic-person-outcome-%d" % number, benchmark.DEFAULT_SEED) == "holdout"]
        development = synthetic_item(dev_case)
        alias = synthetic_item(held[0], 1)
        alias["birth_info"].pop("shichen")
        alias["birth_info"].pop("hour_start")
        alias["birth_info"].pop("hour_end")
        sibling = synthetic_item(held[0], 2)
        sibling["birth_info"].pop("clock_minute")
        different = synthetic_item(held[1], 3)
        different["birth_info"]["clock_minute"] += 1
        incomplete = synthetic_item(held[2], 4)
        incomplete["birth_info"].pop("clock_minute")
        contradictory = synthetic_item(held[3], 5)
        contradictory["birth_info"]["shichen"] = "午"
        _, prepared = self.prepare([development, alias, sibling, different, incomplete, contradictory])

        match = prepared["cross_split_birth_matches"]
        self.assertEqual(match["groups"], 1)
        self.assertEqual(match["affected_cases"], {"development": 1, "holdout": 1})
        self.assertEqual(match["affected_items"], {"development": 1, "holdout": 2})
        self.assertEqual(match["group_case_ids"][0]["development"], prepared["splits"]["development"]["case_ids"])
        pack_path = self.directory / "held-pack.json"
        receipt = benchmark.export_pack(self.evaluation, pack_path, "ziwei", "holdout", allow_holdout=True)
        pack = benchmark.read_json(pack_path)
        self.assertEqual(set(pack), {"schema_version", "task", "items"})
        expected = sorted(item["item_id"] for item in pack["items"] if item["question"] in
                          {alias["question"], sibling["question"]})
        response = self.write_responses("held-response.json", pack_path,
                                        [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
        scored = benchmark.score(self.evaluation, pack_path, response, expected_pack_sha256=receipt["pack_sha256"])
        self.assertEqual(scored["cross_split_birth_matches"], dict(match, scored_item_ids=expected))
        self.assertEqual((scored["cross_split_duplicates"]["groups"],
                          scored["cross_split_rearranged_choices"]["groups"]), (0, 0))
        self.assertEqual((scored["total"], scored["correct"]), (5, 5))

    def test_conflicting_json_keys_fail_before_evaluation_or_scoring(self):
        _, pack, pack_path = self.prepare_pack((2,))
        item_id = pack["items"][0]["item_id"]
        response_path = self.write_responses("responses.json", pack_path, [{"item_id": item_id, "answer": "A"}])
        clean_response = response_path.read_text()
        output = self.directory / "score.json"

        duplicate_source = self.directory / "duplicate-source.json"
        duplicate_source.write_text(self.source.read_text().replace('"answer": "A"', '"answer": "B", "answer": "A"', 1))
        rejected_evaluation = self.directory / "rejected-evaluation"
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate JSON object key"):
            benchmark.prepare(duplicate_source, rejected_evaluation, "https://synthetic.invalid/",
                              "synthetic-ref", "Synthetic fixture")
        self.assertFalse(rejected_evaluation.exists())

        response_path.write_text(clean_response.replace('"answer": "A"', '"answer": "B", "answer": "A"', 1))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate JSON object key"):
            benchmark.score(self.evaluation, pack_path, response_path, output)
        self.assertFalse(output.exists())

        duplicate_pack = self.directory / "duplicate-pack.json"
        duplicate_pack.write_text(pack_path.read_text().replace('"system": "bazi"', '"system": "ziwei", "system": "bazi"', 1))
        fingerprint = hashlib.sha256(duplicate_pack.read_bytes()).hexdigest()
        response_path.write_text(json.dumps({"system": "bazi", "pack_sha256": fingerprint,
                                             "responses": [{"item_id": item_id, "answer": "A"}]}))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate JSON object key"):
            benchmark.score(self.evaluation, duplicate_pack, response_path, output, expected_pack_sha256=fingerprint)
        self.assertFalse(output.exists())

        response_path.write_text(clean_response)
        prepared = self.evaluation / "evaluation.json"
        prepared.write_text(prepared.read_text().replace('"answer": "A"', '"answer": "B", "answer": "A"', 1))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate JSON object key"):
            benchmark.score(self.evaluation, pack_path, response_path, output)
        self.assertFalse(output.exists())

    def test_blind_export_whitelist_drops_raw_answer_and_source_metadata(self):
        data, _, _ = self.prepare_pack()
        for system in ("bazi", "ziwei"):
            pack = benchmark.make_pack(data, system)
            self.assertEqual(set(pack), {"schema_version", "task", "items"})
            self.assertEqual(pack["task"]["system"], system)
            text = json.dumps(pack, ensure_ascii=False)
            for secret in ("SECRET_", "synthetic-source-master", "synthetic-person-outcome",
                           "source_url", "answer_provenance", "pillars_stated_by_master", "2099"):
                self.assertNotIn(secret, text)
            for item in pack["items"]:
                self.assertEqual(set(item), {"item_id", "case_id", "birth", "uncertainty_flags", "question", "options"})
                self.assertEqual(item["birth"]["year"], 1988)
                self.assertIn("timezone_unknown", item["uncertainty_flags"])
                self.assertIn("birth_time_is_range", item["uncertainty_flags"])
                for option in item["options"]:
                    self.assertEqual(set(option), {"letter", "text"})

    def test_item_prompt_uses_only_the_selected_question_from_the_frozen_pack(self):
        case = self.development_case()
        target, sibling = synthetic_item(case, 0), synthetic_item(case, 1)
        sibling["question"] = "This sibling stem discloses the requested outcome."
        data, _ = self.prepare([target, sibling])
        pack = benchmark.make_pack(data, "ziwei")
        path = self.write("pack.json", pack)
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        question = next(item for item in pack["items"] if item["question"] == target["question"])
        command = [sys.executable, str(SCRIPT), "prompt", "--pack", str(path),
                   "--item-id", question["item_id"], "--expected-pack-sha256"]
        result = subprocess.run(command + [fingerprint], check=True, capture_output=True, text=True)
        prompt = json.loads(result.stdout)
        self.assertEqual(prompt["system"], "ziwei")
        self.assertEqual(prompt["item"], {key: value for key, value in question.items() if key != "case_id"})
        self.assertNotIn(sibling["question"], result.stdout)
        rejected = subprocess.run(command + ["0" * 64], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(rejected.stdout, "")
        self.assertIn("does not match", rejected.stderr)

    def test_original_bytes_answers_and_excluded_records_are_preserved_externally(self):
        record = synthetic_item()
        record["answer_provenance"] = "third-party"
        data, report = self.prepare([record])
        self.assertEqual((self.evaluation / "source.json").read_bytes(), self.source.read_bytes())
        self.assertEqual(data["metadata"]["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(data["entries"][0]["answer"], "A")
        self.assertEqual(report["total_items"], 1)
        self.assertEqual(report["excluded_items"], 1)
        self.assertIn("answer_not_official", data["entries"][0]["exclusion_reasons"])

    def test_case_splits_are_deterministic_and_not_question_splits(self):
        records = [synthetic_item(case, question) for case in range(80) for question in range(3)]
        data, report = self.prepare(records)
        memberships = {}
        for entry in data["entries"]:
            memberships.setdefault(entry["source_case_id"], set()).add(entry["split"])
        self.assertTrue(all(len(splits) == 1 for splits in memberships.values()))
        held_cases = report["splits"]["holdout"]["cases"]
        self.assertGreater(held_cases, 10)
        self.assertLess(held_cases, 30)
        second_dir = self.directory / "reversed-evaluation"
        reverse_source = self.write("reverse-source.json", list(reversed(records)))
        benchmark.prepare(reverse_source, second_dir, "synthetic-repo", "synthetic-ref", "synthetic-license")
        reversed_data = benchmark.load_evaluation(second_dir)
        self.assertEqual({entry["item_id"]: entry["split"] for entry in data["entries"]},
                         {entry["item_id"]: entry["split"] for entry in reversed_data["entries"]})
        for entry in data["entries"]:
            self.assertEqual(entry["split"], benchmark.split_for_case(entry["source_case_id"], benchmark.DEFAULT_SEED))

    def test_export_selects_whole_cases_and_holdout_requires_explicit_permission(self):
        data, report = self.prepare([synthetic_item(case, question) for case in range(30) for question in range(2)])
        selected = report["splits"]["development"]["case_ids"][0]
        pack = benchmark.make_pack(data, "ziwei", case_ids=[selected])
        self.assertEqual(len(pack["items"]), 2)
        self.assertEqual({item["case_id"] for item in pack["items"]}, {selected})
        self.assertEqual(len(benchmark.make_pack(data, "bazi", case_limit=2)["items"]), 4)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "explicit"):
            benchmark.make_pack(data, "bazi", split="holdout")
        self.assertTrue(benchmark.make_pack(data, "bazi", split="holdout", allow_holdout=True)["items"])

    def test_all_exclusion_reasons_are_retained_and_date_is_not_taken_from_root_year(self):
        record = synthetic_item()
        record["answer_provenance"] = "third-party"
        record["birth_info"].update(year=None, month=None, day=None, gender="未知",
                                    clock_hour=None, clock_minute=None, shichen=None,
                                    hour_start=None, hour_end=None)
        data, report = self.prepare([record])
        self.assertEqual(set(data["entries"][0]["exclusion_reasons"]),
                         {"answer_not_official", "missing_birth_year", "missing_birth_month",
                          "missing_birth_day", "unrecognized_birth_sex", "missing_usable_birth_time"})
        self.assertNotIn("year", data["entries"][0]["birth"])
        self.assertEqual(report["eligible_items"], 0)

    def test_invalid_date_clock_and_answer_are_excluded(self):
        record = synthetic_item()
        record["birth_info"].update(year=1989, clock_hour=24, clock_minute=60)
        record["answer"] = "Z"
        data, _ = self.prepare([record])
        self.assertTrue({"invalid_birth_date", "invalid_clock_hour", "invalid_clock_minute",
                         "invalid_answer_letter"} <= set(data["entries"][0]["exclusion_reasons"]))

    def test_unknown_and_reverse_inferred_times_are_excluded_even_with_stated_branch(self):
        records = [synthetic_item(0), synthetic_item(1)]
        records[0]["birth_info"]["raw"] = "合成出生资料：时辰不详"
        records[1]["birth_info"]["reason"] = "合成资料由经历反推时辰"
        data, report = self.prepare(records)
        self.assertEqual(report["eligible_items"], 0)
        self.assertIn("unknown_birth_time", data["entries"][0]["exclusion_reasons"])
        self.assertIn("reverse_inferred_birth_time", data["entries"][1]["exclusion_reasons"])

    def test_contradictory_structured_time_is_flagged_without_choosing_a_correction(self):
        records = [synthetic_item(0), synthetic_item(1), synthetic_item(2)]
        records[0]["birth_info"]["shichen"] = "午"
        records[1]["birth_info"].update(hour_start=11, hour_end=13)
        records[2]["birth_info"].update(clock_hour=0, shichen="子", hour_start=23, hour_end=1)
        data, _ = self.prepare(records)
        for entry in data["entries"][:2]:
            self.assertTrue(entry["eligible"])
            self.assertIn("contradictory_time_fields", entry["uncertainty_flags"])
        self.assertNotIn("contradictory_time_fields", data["entries"][2]["uncertainty_flags"])

    def test_question_with_time_words_does_not_override_known_birth_time(self):
        record = synthetic_item()
        record["question"] = "合成题：哪个时辰发生某件事？"
        data, _ = self.prepare([record])
        self.assertTrue(data["entries"][0]["eligible"])

    def test_branch_or_clock_basis_is_retained_without_inventing_precise_minute(self):
        records = [synthetic_item(0), synthetic_item(1)]
        records[0]["birth_info"].update(clock_hour=None, clock_minute=None, hour_start=23, hour_end=1, shichen="子时")
        records[1]["birth_info"].update(clock_minute=None, shichen=None, hour_start=None, hour_end=None,
                                        shichen_derived_from_clock=True)
        data, _ = self.prepare(records)
        first, second = data["entries"]
        self.assertTrue(first["eligible"])
        self.assertEqual(first["birth"]["shichen"], "子")
        self.assertNotIn("clock_hour", first["birth"])
        self.assertNotIn("clock_minute", second["birth"])
        self.assertIn("clock_minute_unspecified", second["uncertainty_flags"])
        self.assertIn("source_branch_derived_from_clock", second["uncertainty_flags"])

    def test_lunar_and_unknown_calendars_are_explicitly_uncertain(self):
        records = [synthetic_item(0), synthetic_item(1)]
        records[0]["birth_info"].update(calendar_type="lunar", day=30)
        records[1]["birth_info"]["calendar_type"] = None
        data, _ = self.prepare(records)
        self.assertTrue(data["entries"][0]["eligible"])
        self.assertIn("lunar_date_requires_calendar_validation", data["entries"][0]["uncertainty_flags"])
        self.assertIn("calendar_unknown", data["entries"][1]["uncertainty_flags"])

    def test_scoring_includes_wrong_and_abstained_in_total_and_uses_option_counts(self):
        data, pack, pack_path = self.prepare_pack()
        items = pack["items"]
        responses = [{"item_id": items[0]["item_id"], "answer": "A"},
                     {"item_id": items[1]["item_id"], "answer": "B"},
                     {"item_id": items[2]["item_id"], "abstain": True, "reason": "合成资料不足"}]
        response_path = self.write_responses("responses.json", pack_path, responses)
        report = benchmark.score(self.evaluation, pack_path, response_path)
        self.assertEqual((report["total"], report["answered"], report["correct"], report["wrong"], report["abstained"]),
                         (3, 2, 1, 1, 1))
        self.assertAlmostEqual(report["coverage"], 2 / 3)
        self.assertAlmostEqual(report["accuracy_all"], 1 / 3)
        self.assertAlmostEqual(report["accuracy_answered"], 1 / 2)
        self.assertAlmostEqual(report["random_guess_expectation"]["correct"], 1 / 2 + 1 / 3 + 1 / 5)
        self.assertAlmostEqual(report["random_guess_expectation"]["accuracy"], (1 / 2 + 1 / 3 + 1 / 5) / 3)
        self.assertEqual(report["case_counts"], {"total": 1, "answered": 1, "with_correct": 1,
                                               "with_wrong": 1, "with_abstention": 1, "fully_answered": 0})
        self.assertEqual(len(report["results"]), 3)
        self.assertEqual(next(result for result in report["results"] if result["status"] == "abstained")["reason"],
                         "合成资料不足")
        self.assertTrue(report["metadata"]["response_system_verified"])
        self.assertTrue(report["metadata"]["response_pack_sha256_verified"])
        self.assertEqual(report["metadata"]["response_sha256"], hashlib.sha256(response_path.read_bytes()).hexdigest())
        self.assertFalse(report["metadata"]["response_sha256_verified"])

    def test_frozen_response_digest_rejects_replacement_bound_to_same_pack(self):
        _, pack, pack_path = self.prepare_pack((2,))
        item_id = pack["items"][0]["item_id"]
        response = self.write_responses("frozen-response.json", pack_path,
                                        [{"item_id": item_id, "answer": "B"}])
        expected = hashlib.sha256(response.read_bytes()).hexdigest()
        report = benchmark.score(self.evaluation, pack_path, response, expected_response_sha256=expected.upper())
        self.assertEqual((report["correct"], report["wrong"]), (0, 1))
        self.assertTrue(report["metadata"]["response_sha256_verified"])

        replacement = self.write_responses("replacement-response.json", pack_path,
                                           [{"item_id": item_id, "answer": "A"}])
        output = self.directory / "score.json"
        with self.assertRaisesRegex(benchmark.BenchmarkError, "analyst responses SHA-256 .* frozen submission"):
            benchmark.score(self.evaluation, pack_path, replacement, output, expected_response_sha256=expected)
        self.assertFalse(output.exists())
        legacy = benchmark.score(self.evaluation, pack_path, replacement)
        self.assertEqual((legacy["correct"], legacy["wrong"]), (1, 0))
        self.assertTrue(legacy["metadata"]["response_pack_sha256_verified"])
        self.assertFalse(legacy["metadata"]["response_sha256_verified"])

    def test_frozen_export_digest_rejects_omitting_an_entire_case(self):
        cases = [number for number in range(100) if benchmark.split_for_case(
            "synthetic-person-outcome-%d" % number, benchmark.DEFAULT_SEED) == "development"][:2]
        self.prepare([synthetic_item(number) for number in cases])
        pack_path = self.directory / "frozen-pack.json"
        exported = benchmark.export_pack(self.evaluation, pack_path, "bazi")
        self.assertEqual((exported["cases"], exported["items"]), (2, 2))
        expected_digest = hashlib.sha256(pack_path.read_bytes()).hexdigest()
        self.assertEqual(exported["pack_sha256"], expected_digest)
        pack = json.loads(pack_path.read_text())
        responses = [{"item_id": item["item_id"], "answer": answer}
                     for item, answer in zip(pack["items"], ("A", "B"))]
        response_path = self.write_responses("responses.json", pack_path, responses)
        report = benchmark.score(self.evaluation, pack_path, response_path,
                                 expected_pack_sha256=expected_digest)
        self.assertEqual((report["total"], report["correct"], report["wrong"]), (2, 1, 1))
        self.assertEqual(report["metadata"]["pack_sha256"], expected_digest)
        self.assertTrue(report["metadata"]["pack_sha256_verified"])

        pack["items"] = pack["items"][:1]
        smaller_pack = self.write("smaller-pack.json", pack)
        smaller_responses = self.write("smaller-responses.json", responses[:1])
        with self.assertRaisesRegex(benchmark.BenchmarkError, "does not match the frozen export"):
            benchmark.score(self.evaluation, smaller_pack, smaller_responses,
                            expected_pack_sha256=expected_digest)
        legacy = benchmark.score(self.evaluation, smaller_pack, smaller_responses, allow_unbound_responses=True)
        self.assertEqual(legacy["accuracy_all"], 1)
        self.assertFalse(legacy["metadata"]["pack_sha256_verified"])

    def test_frozen_source_rejects_answer_revision_with_identical_blind_pack(self):
        record = synthetic_item(self.development_case())
        self.prepare([record])
        pack_path = self.directory / "original-pack.json"
        original = benchmark.export_pack(self.evaluation, pack_path, "ziwei")
        self.assertEqual(original["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        pack = json.loads(pack_path.read_text())
        responses = self.write_responses("responses.json", pack_path,
                                         [{"item_id": pack["items"][0]["item_id"], "answer": "A"}])
        correct = benchmark.score(self.evaluation, pack_path, responses,
                                  expected_pack_sha256=original["pack_sha256"],
                                  expected_source_sha256=original["source_sha256"])
        self.assertEqual(correct["correct"], 1)
        self.assertTrue(correct["metadata"]["source_sha256_verified"])

        revised_source = self.write("revised-source.json", [dict(record, answer="B")])
        revised_evaluation = self.directory / "revised-evaluation"
        benchmark.prepare(revised_source, revised_evaluation, "https://synthetic.invalid/repository",
                          "revised-synthetic-ref", "Synthetic fixture license citation")
        revised = benchmark.export_pack(revised_evaluation, self.directory / "revised-pack.json", "ziwei")
        self.assertEqual(revised["pack_sha256"], original["pack_sha256"])
        self.assertNotEqual(revised["source_sha256"], original["source_sha256"])
        with self.assertRaisesRegex(benchmark.BenchmarkError, "evaluation source SHA-256 does not match"):
            benchmark.score(revised_evaluation, pack_path, responses,
                            expected_pack_sha256=original["pack_sha256"],
                            expected_source_sha256=original["source_sha256"])
        pack_only = benchmark.score(revised_evaluation, pack_path, responses,
                                    expected_pack_sha256=original["pack_sha256"])
        self.assertEqual(pack_only["wrong"], 1)
        self.assertTrue(pack_only["metadata"]["pack_sha256_verified"])
        self.assertFalse(pack_only["metadata"]["source_sha256_verified"])

    def test_frozen_preparation_binds_provenance_through_export_and_score(self):
        data, prepared = self.prepare([synthetic_item(self.development_case())])
        private_record = self.evaluation / "evaluation.json"
        expected = hashlib.sha256(private_record.read_bytes()).hexdigest()
        self.assertEqual(prepared["evaluation_sha256"], expected)
        pack_path = self.directory / "pack.json"
        exported = benchmark.export_pack(self.evaluation, pack_path, "bazi",
                                         expected_evaluation_sha256=expected.upper())
        self.assertEqual(exported["evaluation_sha256"], expected)
        self.assertTrue(exported["evaluation_sha256_verified"])
        pack = benchmark.read_json(pack_path)
        self.assertNotIn("evaluation_sha256", pack)
        responses = self.write_responses("responses.json", pack_path,
                                         [{"item_id": pack["items"][0]["item_id"], "answer": "A"}])
        binding = dict(expected_pack_sha256=exported["pack_sha256"],
                       expected_source_sha256=exported["source_sha256"])
        report = benchmark.score(self.evaluation, pack_path, responses,
                                 expected_evaluation_sha256=expected, **binding)
        self.assertTrue(report["metadata"]["evaluation_sha256_verified"])
        self.assertEqual(report["metadata"]["evaluation_sha256"], expected)

        data["metadata"]["source_ref"] = "changed-after-preparation"
        data["metadata"]["preparation_tool_sha256"] = "0" * 64
        private_record.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(hashlib.sha256(pack_path.read_bytes()).hexdigest(), exported["pack_sha256"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), exported["source_sha256"])
        new_pack, output = self.directory / "new-pack.json", self.directory / "score.json"
        with self.assertRaisesRegex(benchmark.BenchmarkError, "prepared evaluation SHA-256 .* frozen preparation"):
            benchmark.export_pack(self.evaluation, new_pack, "bazi", expected_evaluation_sha256=expected)
        self.assertFalse(new_pack.exists())
        with self.assertRaisesRegex(benchmark.BenchmarkError, "prepared evaluation SHA-256 .* frozen export"):
            benchmark.score(self.evaluation, pack_path, responses, output,
                            expected_evaluation_sha256=expected, **binding)
        self.assertFalse(output.exists())
        legacy = benchmark.score(self.evaluation, pack_path, responses, **binding)
        self.assertEqual(legacy["correct"], report["correct"])
        self.assertFalse(legacy["metadata"]["evaluation_sha256_verified"])

    def test_bound_responses_reject_wrong_system_or_pack_with_identical_items(self):
        data, pack, pack_path = self.prepare_pack()
        ziwei_pack = benchmark.make_pack(data, "ziwei")
        self.assertEqual(pack["items"], ziwei_pack["items"])
        ziwei_path = self.write("ziwei-pack.json", ziwei_pack)
        answers = [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]]
        response_path = self.write_responses("bazi-responses.json", pack_path, answers)
        expected = {
            "expected_pack_sha256": hashlib.sha256(ziwei_path.read_bytes()).hexdigest(),
            "expected_source_sha256": data["metadata"]["source_sha256"],
        }
        score_path = self.directory / "misattributed-score.json"
        with self.assertRaisesRegex(benchmark.BenchmarkError, "response system does not match"):
            benchmark.score(self.evaluation, ziwei_path, response_path, score_path, **expected)
        wrong_pack = self.write("wrong-pack-responses.json", dict(benchmark.read_json(response_path), system="ziwei"))
        with self.assertRaisesRegex(benchmark.BenchmarkError, "response analyst pack SHA-256 does not match"):
            benchmark.score(self.evaluation, ziwei_path, wrong_pack, score_path, **expected)
        self.assertFalse(score_path.exists())

        ziwei_response = self.write_responses("ziwei-responses.json", ziwei_path, answers)
        report = benchmark.score(self.evaluation, ziwei_path, ziwei_response, **expected)
        self.assertEqual(report["correct"], len(answers))
        self.assertTrue(report["metadata"]["response_system_verified"])
        self.assertTrue(report["metadata"]["response_pack_sha256_verified"])

    def test_unbound_responses_require_explicit_legacy_replay(self):
        _, pack, pack_path = self.prepare_pack()
        answers = [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]]
        for payload in (answers, {"responses": answers}):
            with self.subTest(payload_type=type(payload)):
                legacy_path = self.write("legacy-responses.json", payload)
                with self.assertRaisesRegex(benchmark.BenchmarkError, "allow-unbound-responses"):
                    benchmark.score(self.evaluation, pack_path, legacy_path)
                legacy = benchmark.score(self.evaluation, pack_path, legacy_path, allow_unbound_responses=True)
                self.assertEqual(legacy["correct"], len(answers))
                self.assertFalse(legacy["metadata"]["response_system_verified"])
                self.assertFalse(legacy["metadata"]["response_pack_sha256_verified"])
        partial = self.write("partial-responses.json", {"system": "bazi", "responses": answers})
        with self.assertRaisesRegex(benchmark.BenchmarkError, "specify both system and pack_sha256"):
            benchmark.score(self.evaluation, pack_path, partial, allow_unbound_responses=True)

    def test_all_abstained_has_zero_coverage_and_no_answered_accuracy(self):
        _, pack, pack_path = self.prepare_pack()
        response_path = self.write_responses("responses.json", pack_path, [
            {"item_id": item["item_id"], "abstain": True, "reason": "合成时区不确定"} for item in pack["items"]
        ])
        report = benchmark.score(self.evaluation, pack_path, response_path)
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["abstained"], 3)
        self.assertEqual(report["coverage"], 0)
        self.assertEqual(report["accuracy_all"], 0)
        self.assertIsNone(report["accuracy_answered"])

    def test_preparation_and_scoring_implementation_hashes_are_independently_recorded(self):
        data, pack, pack_path = self.prepare_pack()
        expected_hash = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
        self.assertEqual(data["metadata"]["preparation_tool_sha256"], expected_hash)
        responses = self.write_responses("responses.json", pack_path,
                                         [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
        with mock.patch.object(benchmark, "tool_sha256", return_value="different-scoring-implementation"):
            report = benchmark.score(self.evaluation, pack_path, responses)
        self.assertEqual(report["metadata"]["preparation_tool_sha256"], expected_hash)
        self.assertEqual(report["metadata"]["scoring_tool_sha256"], "different-scoring-implementation")

    def test_missing_duplicate_unknown_and_invalid_responses_fail_without_score_file(self):
        _, pack, pack_path = self.prepare_pack()
        valid = [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]]
        invalid_sets = [valid[:-1], valid + [valid[0]], valid + [{"item_id": "unknown", "answer": "A"}],
                        [dict(valid[0], answer="Z")] + valid[1:],
                        [{"item_id": valid[0]["item_id"], "abstain": True}] + valid[1:],
                        [dict(valid[0], abstain=True, reason="ambiguous")] + valid[1:],
                        [{"item_id": valid[0]["item_id"], "abstain": "true", "reason": "uncertain"}] + valid[1:]]
        for index, responses in enumerate(invalid_sets):
            with self.subTest(index=index):
                response_path = self.write_responses("invalid-%d.json" % index, pack_path, responses)
                score_path = self.directory / ("score-%d.json" % index)
                with self.assertRaises(benchmark.BenchmarkError):
                    benchmark.score(self.evaluation, pack_path, response_path, score_path)
                self.assertFalse(score_path.exists())

    def test_dropping_hard_question_or_altering_pack_is_rejected(self):
        _, pack, pack_path = self.prepare_pack()
        responses = self.write_responses("responses.json", pack_path,
                                         [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
        variants = []
        reduced = copy.deepcopy(pack)
        reduced["items"].pop()
        variants.append(reduced)
        changed = copy.deepcopy(pack)
        changed["items"][0]["options"][0]["text"] = "篡改选项"
        variants.append(changed)
        duplicate = copy.deepcopy(pack)
        duplicate["items"].append(duplicate["items"][0])
        variants.append(duplicate)
        for index, (variant, error) in enumerate(zip(variants, ("omits eligible questions", "does not match prepared source",
                                                              "duplicate item"))):
            with self.subTest(index=index):
                path = self.write("changed-%d.json" % index, variant)
                with self.assertRaisesRegex(benchmark.BenchmarkError, error):
                    benchmark.score(self.evaluation, path, responses)

    def test_source_tampering_and_duplicate_source_ids_are_rejected(self):
        data, _ = self.prepare([synthetic_item()])
        source_copy = self.evaluation / "source.json"
        source_copy.write_bytes(source_copy.read_bytes() + b" ")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "checksum"):
            benchmark.load_evaluation(self.evaluation)
        duplicate_source = self.write("duplicates.json", [synthetic_item(), synthetic_item()])
        with self.assertRaisesRegex(benchmark.BenchmarkError, "duplicate source id"):
            benchmark.prepare(duplicate_source, self.directory / "duplicates", "repo", "ref", "license")
        self.assertFalse((self.directory / "duplicates").exists())

    def test_score_rejects_modified_prepared_answer_with_unchanged_source(self):
        data, pack, pack_path = self.prepare_pack()
        responses = self.write_responses("responses.json", pack_path, [
            {"item_id": item["item_id"], "answer": "A"} for item in pack["items"]
        ])
        self.assertEqual(benchmark.score(self.evaluation, pack_path, responses)["correct"], len(pack["items"]))
        data["entries"][0]["answer"] = "B"
        (self.evaluation / "evaluation.json").write_text(json.dumps(data), encoding="utf-8")
        score_path = self.directory / "forged-score.json"
        with self.assertRaisesRegex(benchmark.BenchmarkError, "prepared entries do not match"):
            benchmark.score(self.evaluation, pack_path, responses, score_path)
        self.assertFalse(score_path.exists())

    def test_export_rejects_modified_prepared_scope_with_unchanged_source(self):
        data, _, _ = self.prepare_pack()
        for field, value in (("eligible", False), ("split", "holdout"), ("case_id", "changed-case")):
            with self.subTest(field=field):
                changed = copy.deepcopy(data)
                changed["entries"][0][field] = value
                (self.evaluation / "evaluation.json").write_text(json.dumps(changed), encoding="utf-8")
                pack_path = self.directory / "forged-pack.json"
                with self.assertRaisesRegex(benchmark.BenchmarkError, "prepared entries do not match"):
                    benchmark.export_pack(self.evaluation, pack_path, "bazi")
                self.assertFalse(pack_path.exists())

    def test_outputs_cannot_overwrite_sources_existing_files_or_repository_paths(self):
        data, _, _ = self.prepare_pack()
        original = self.source.read_bytes()
        with self.assertRaisesRegex(benchmark.BenchmarkError, "overwrite"):
            benchmark.export_pack(self.evaluation, self.source, "bazi")
        self.assertEqual(self.source.read_bytes(), original)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "empty"):
            benchmark.prepare(self.source, self.evaluation, "repo", "ref", "license")
        for path in (benchmark.REPOSITORY / "knowledge" / "forbidden.json",
                     benchmark.REPOSITORY / "references" / "forbidden.json"):
            with self.subTest(path=str(path)):
                with self.assertRaisesRegex(benchmark.BenchmarkError, "outside repository"):
                    benchmark.export_pack(self.evaluation, path, "bazi")
                self.assertFalse(path.exists())
        alias = self.directory / "repository-alias"
        alias.symlink_to(benchmark.REPOSITORY, target_is_directory=True)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "outside repository"):
            benchmark.write_json(alias / "forbidden.json", {"synthetic": True})

    def test_preexisting_temporary_file_is_preserved_when_exclusive_creation_fails(self):
        output = self.directory / "new-output.json"
        temporary = self.directory / "new-output.json.tmp"
        original = b"synthetic data owned by another writer\n"
        temporary.write_bytes(original)
        with self.assertRaises(FileExistsError):
            benchmark.write_json(output, {"synthetic": True})
        self.assertEqual(temporary.read_bytes(), original)
        self.assertFalse(output.exists())

    def test_destination_created_during_serialization_is_never_replaced(self):
        output = self.directory / "racing-output.json"
        original = b"synthetic destination created by another writer\n"
        original_dump = benchmark.json.dump

        def create_destination_then_serialize(value, handle, **kwargs):
            output.write_bytes(original)
            return original_dump(value, handle, **kwargs)

        with mock.patch.object(benchmark.json, "dump", side_effect=create_destination_then_serialize):
            with self.assertRaises(FileExistsError):
                benchmark.write_json(output, {"synthetic": True})
        self.assertEqual(output.read_bytes(), original)
        self.assertFalse(output.with_name(output.name + ".tmp").exists())

    def test_source_copy_created_concurrently_is_never_replaced(self):
        source = self.write("race-source.json", [synthetic_item()])
        copied_source = (self.evaluation / "source.json").resolve()
        original = b"synthetic source created by another writer\n"
        original_open = Path.open

        def create_source_before_exclusive_open(path, mode="r", *args, **kwargs):
            if path == copied_source and mode == "xb":
                with original_open(copied_source, "wb") as handle:
                    handle.write(original)
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", new=create_source_before_exclusive_open):
            with self.assertRaises(FileExistsError):
                benchmark.prepare(source, self.evaluation, "repo", "ref", "synthetic-license")
        self.assertEqual(copied_source.read_bytes(), original)
        self.assertFalse((self.evaluation / "evaluation.json").exists())

    def test_cli_prepare_export_score_roundtrip_and_missing_response_exit_nonzero(self):
        case = self.development_case()
        self.write("cli-source.json", [synthetic_item(case)])
        def invoke(*args):
            return subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                                  capture_output=True, text=True, check=False)
        prepared = invoke("prepare", "--source", str(self.directory / "cli-source.json"),
                          "--output-dir", str(self.evaluation), "--source-repo", "synthetic-repo",
                          "--source-ref", "synthetic-ref", "--source-license", "synthetic-license")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        pack_path = self.directory / "cli-pack.json"
        exported = invoke("export", "--evaluation-dir", str(self.evaluation), "--output", str(pack_path),
                          "--system", "ziwei", "--case-limit", "1")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        pack = benchmark.read_json(pack_path)
        response_path = self.write_responses("cli-responses.json", pack_path, [
            {"item_id": pack["items"][0]["item_id"], "abstain": True, "reason": "合成案例不足"}
        ])
        score_path = self.directory / "cli-score.json"
        response_digest = hashlib.sha256(response_path.read_bytes()).hexdigest()
        scored = invoke("score", "--evaluation-dir", str(self.evaluation), "--pack", str(pack_path),
                        "--responses", str(response_path), "--expected-response-sha256", response_digest,
                        "--output", str(score_path))
        self.assertEqual(scored.returncode, 0, scored.stderr)
        report = benchmark.read_json(score_path)
        self.assertEqual(report["abstained"], 1)
        self.assertTrue(report["metadata"]["response_sha256_verified"])
        missing = self.write_responses("cli-missing.json", pack_path, [])
        rejected = invoke("score", "--evaluation-dir", str(self.evaluation), "--pack", str(pack_path),
                          "--responses", str(missing), "--output", str(self.directory / "bad-score.json"))
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("missing responses", rejected.stderr)
        self.assertFalse((self.directory / "bad-score.json").exists())


if __name__ == "__main__":
    unittest.main()
