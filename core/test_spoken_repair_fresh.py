"""Offline regression and provenance tests for frozen post-V4 speech cases."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import wave

from .analysis_v3 import detect_instruction_revision_v3
from .analysis_v4 import detect_instruction_revision_v4
from .spoken_repair_fresh import CASES, SCHEMA, plan, validate_audio, evaluate, review_triage
from .voicerank import file_digest


def fake_audio_file(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 2000)


class FreshSpokenRepairTests(TestCase):
    def setUp(self):
        self.items = plan()

    def test_balanced_and_unique_texts(self):
        self.assertEqual(len(CASES), 24)
        self.assertEqual([case[2] for case in CASES].count(1), 12)
        self.assertEqual([case[2] for case in CASES].count(0), 12)
        self.assertEqual(len({case[1] for case in CASES}), 24)

    def test_pairs_have_same_words_different_nominal_rate(self):
        self.assertEqual(len(self.items), 48)
        by_case = {case[0]: [row for row in self.items if row["case_id"] == case[0]] for case in CASES}
        for case_id, entries in by_case.items():
            with self.subTest(case=case_id):
                self.assertEqual(len(entries), 2)
                self.assertEqual([item["condition"] for item in entries], ["slower", "faster"])
                self.assertEqual([item["rate_wpm"] for item in entries], [155, 210])
                self.assertEqual(entries[0]["transcript"], entries[1]["transcript"])

    def test_no_overlap_with_original_spoken_repair(self):
        from .spoken_repair import CASES as OLD_CASES
        self.assertFalse({case[1] for case in CASES} & {case[1] for case in OLD_CASES})

    def test_deterministic_clip_ids_and_unique_audio_paths(self):
        self.assertEqual(self.items, plan())
        self.assertEqual(len({item["clip_id"] for item in self.items}), 48)
        self.assertEqual(len({item["file_name"] for item in self.items}), 48)

    def test_invalid_voice_is_rejected(self):
        for name in ("", "new\nline", "bad\tvoice", "x" * 101):
            with self.subTest(name=name), self.assertRaises(ValueError):
                plan(name)

    def test_perfect_asr_is_zero_wer_and_consistent_metrics(self):
        hypothesis = {item["clip_id"]: item["transcript"] for item in self.items}
        rows, summary = evaluate(self.items, hypothesis)
        self.assertEqual(len(rows), 48)
        self.assertEqual(len(summary), 9)
        self.assertEqual({r["micro_wer"] for r in summary}, {0})
        self.assertEqual({r["exact_matches"] for r in summary}, {24, 48})
        for row in rows:
            self.assertEqual(row["asr_v3"], row["reference_v3"])
            self.assertEqual(row["asr_v4"], row["reference_v4"])
        for stat in summary:
            self.assertEqual(stat["tp"] + stat["fp"] + stat["fn"] + stat["tn"], stat["n"])
            self.assertEqual(stat["n"], 48 if stat["condition"] == "both" else 24)

    def test_v4_is_not_automatically_assumed_correct(self):
        source = self.items[0]["transcript"]
        self.assertEqual(int(detect_instruction_revision_v4(source)), int(self.items[0]["gold_revision"]))
        self.assertFalse(detect_instruction_revision_v3(source))  # V3 has narrower initial-verb coverage


    def test_review_triage_never_approves_actions(self):
        self.assertEqual(review_triage(""), "empty_transcript")
        self.assertEqual(review_triage("Center report to Alice, actually, sent it to Bob."), "unrecognized_opening")
        self.assertEqual(review_triage("Send the report to Alice, actually, send it to Bob."), "candidate_revision")
        self.assertEqual(review_triage("Send the report to Alice."), "not_flagged")

    def test_untrusted_asr_not_silently_repaired(self):
        hypotheses = {item["clip_id"]: item["transcript"] for item in self.items}
        for item in self.items:
            if item["case_id"] == "NR01" and item["condition"] == "faster":
                hypotheses[item["clip_id"]] = "The contract looks fine. Actually, the committee has approved it."
        rows, summary = evaluate(self.items, hypotheses)
        one = next(row for row in rows if row["case_id"] == "NR01" and row["condition"] == "faster")
        self.assertEqual(one["asr_v4"], 0)
        self.assertEqual(one["v4_result"], "FN")
        self.assertGreater(one["wer"], 0)
        self.assertTrue(any(row["micro_wer"] > 0 for row in summary))

    def test_missing_or_extra_asr_trial_is_rejected(self):
        hypotheses = {item["clip_id"]: item["transcript"] for item in self.items}
        hypotheses.pop(self.items[0]["clip_id"])
        with self.assertRaises(ValueError):
            evaluate(self.items, hypotheses)
        hypotheses[self.items[0]["clip_id"]] = self.items[0]["transcript"]
        hypotheses["unknown"] = "extra"
        with self.assertRaises(ValueError):
            evaluate(self.items, hypotheses)

    def test_invalid_asr_record_is_rejected(self):
        hypotheses = {item["clip_id"]: item["transcript"] for item in self.items}
        hypotheses[self.items[0]["clip_id"]] = "x" * 4001
        with self.assertRaises(ValueError):
            evaluate(self.items, hypotheses)

    def test_audio_manifest_hashes_and_tampering(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            written = []
            for item in self.items:
                f = directory / item["file_name"]
                fake_audio_file(f)
                written.append({**item, "sha256": file_digest(f)})
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({"schema": SCHEMA, "dataset": "fresh_v1", "stimuli": written}), encoding="utf-8")
            self.assertEqual(len(validate_audio(directory)), 48)
            (directory / self.items[0]["file_name"]).write_bytes(b"broken")
            with self.assertRaises(ValueError):
                validate_audio(directory)

    def test_manifest_mismatched_labels_and_duplicates_rejected(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            written = []
            for item in self.items:
                f = directory / item["file_name"]
                fake_audio_file(f)
                written.append({**item, "sha256": file_digest(f)})
            manifest = directory / "manifest.json"
            broken = [dict(item) for item in written]
            broken[0]["gold_revision"] = 0
            manifest.write_text(json.dumps({"schema": SCHEMA, "dataset": "fresh_v1", "stimuli": broken}), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_audio(directory)
            broken[0] = broken[1]
            manifest.write_text(json.dumps({"schema": SCHEMA, "dataset": "fresh_v1", "stimuli": broken}), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_audio(directory)
