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
        response_path = self.write("responses.json", {"responses": responses})
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

    def test_all_abstained_has_zero_coverage_and_no_answered_accuracy(self):
        _, pack, pack_path = self.prepare_pack()
        response_path = self.write("responses.json", [{"item_id": item["item_id"], "abstain": True,
                                                     "reason": "合成时区不确定"} for item in pack["items"]])
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
        responses = self.write("responses.json", [{"item_id": item["item_id"], "answer": "A"}
                                                  for item in pack["items"]])
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
                response_path = self.write("invalid-%d.json" % index, responses)
                score_path = self.directory / ("score-%d.json" % index)
                with self.assertRaises(benchmark.BenchmarkError):
                    benchmark.score(self.evaluation, pack_path, response_path, score_path)
                self.assertFalse(score_path.exists())

    def test_dropping_hard_question_or_altering_pack_is_rejected(self):
        _, pack, _ = self.prepare_pack()
        responses = self.write("responses.json", [{"item_id": item["item_id"], "answer": "A"} for item in pack["items"]])
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
        for index, variant in enumerate(variants):
            with self.subTest(index=index):
                path = self.write("changed-%d.json" % index, variant)
                with self.assertRaises(benchmark.BenchmarkError):
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
        response_path = self.write("cli-responses.json", [{"item_id": pack["items"][0]["item_id"],
                                                          "abstain": True, "reason": "合成案例不足"}])
        score_path = self.directory / "cli-score.json"
        scored = invoke("score", "--evaluation-dir", str(self.evaluation), "--pack", str(pack_path),
                        "--responses", str(response_path), "--output", str(score_path))
        self.assertEqual(scored.returncode, 0, scored.stderr)
        self.assertEqual(benchmark.read_json(score_path)["abstained"], 1)
        missing = self.write("cli-missing.json", [])
        rejected = invoke("score", "--evaluation-dir", str(self.evaluation), "--pack", str(pack_path),
                          "--responses", str(missing), "--output", str(self.directory / "bad-score.json"))
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("missing responses", rejected.stderr)
        self.assertFalse((self.directory / "bad-score.json").exists())


if __name__ == "__main__":
    unittest.main()
