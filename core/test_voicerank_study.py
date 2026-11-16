"""Pure Python expanded-study tests; no Django or external services required."""
from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from core.voicerank import PROMPTS, stimulus_plan
from core.voicerank_study import (
    counterbalanced_order, export_study_rows, fingerprint_audio,
    read_study_csvs, summarize_participants, EXPORT_FIELDS_V2,
)


def make_records():
    return [{**row, "sha256": "a" * 64} for row in stimulus_plan()]


def make_study_rows(pid="vr2-" + "1" * 20, assignment=0, fast=4, slow=2):
    records = make_records()
    order = counterbalanced_order(records, assignment)
    ratings = {str(item["clip_id"]): {
        "authority": fast if item["condition"] == "faster" else slow,
        "clarity": 3,
        "urgency": 2 if item["condition"] == "faster" else 3,
    } for item in records}
    return export_study_rows(records, order, ratings, pid, assignment)


class CounterbalancedScheduleTests(TestCase):
    def test_eight_schedules_perfect_structure(self):
        records = make_records()
        mapping = {x["clip_id"]: x for x in records}
        for seq in range(8):
            order = counterbalanced_order(records, seq)
            self.assertEqual(len(order), 8)
            self.assertEqual(len(set(order)), 8)
            prompts = [mapping[c]["prompt_id"] for c in order]
            self.assertEqual(len(set(prompts[:4])), 4)
            self.assertEqual(len(set(prompts[4:])), 4)
            self.assertTrue(all(a != b for a, b in zip(prompts, prompts[1:])))

    def test_each_prompt_condition_counterbalanced_across_schedules(self):
        records = make_records()
        by_id = {r["clip_id"]: r for r in records}
        for prompt, _ in PROMPTS:
            before = []
            positions = []
            for arm in range(8):
                first_four = [by_id[c] for c in counterbalanced_order(records, arm)[:4]]
                first = next(i for i in first_four if i["prompt_id"] == prompt)
                before.append(first["condition"])
                positions.append([i["prompt_id"] for i in first_four].index(prompt))
            self.assertEqual(before.count("slower"), 4)
            self.assertEqual(before.count("faster"), 4)
            self.assertEqual(sorted(positions), [0, 0, 1, 1, 2, 2, 3, 3])

    def test_reject_bad_assignments_and_pairs(self):
        with self.assertRaises(ValueError):
            counterbalanced_order(make_records(), 8)
        with self.assertRaises(ValueError):
            counterbalanced_order(make_records()[:-1], 0)

    def test_deterministic_audio_fingerprint(self):
        records = make_records()
        self.assertEqual(fingerprint_audio(records), fingerprint_audio(list(reversed(records))))
        changed = [{**r} for r in records]
        changed[0]["sha256"] = "b" * 64
        self.assertNotEqual(fingerprint_audio(records), fingerprint_audio(changed))


class ExportAndAnalysisTests(TestCase):
    def test_single_person_complete_export(self):
        records = make_records()
        order = counterbalanced_order(records, 3)
        ratings = {item["clip_id"]: {"authority": 3, "clarity": 4, "urgency": 2} for item in records}
        rows = export_study_rows(records, order, ratings, "vr2-" + "b" * 20, 3)
        self.assertEqual(len(rows), 8)
        self.assertEqual(set(rows[0]), set(EXPORT_FIELDS_V2))
        self.assertEqual([item["clip_id"] for item in rows], order)

    def test_reject_incomplete_export(self):
        records = make_records()
        with self.assertRaisesRegex(ValueError, "Complete"):
            export_study_rows(records, counterbalanced_order(records, 0), {}, "vr2-" + "b" * 20, 0)

    def test_two_independent_participants_are_unit_of_analysis(self):
        rows = make_study_rows("vr2-" + "1" * 20, 0, fast=4, slow=2)
        rows += make_study_rows("vr2-" + "2" * 20, 1, fast=2, slow=4)
        person, group = summarize_participants(rows)
        self.assertEqual(len(person), 2)
        self.assertEqual(group["participants"], 2)
        self.assertEqual(group["trials"], 16)
        self.assertEqual(group["authority"]["mean_participant_difference_faster_minus_slower"], 0)
        self.assertEqual(group["assignment_counts"]["0"], 1)
        self.assertEqual(group["assignment_counts"]["1"], 1)
        self.assertEqual(group["urgency"]["mean_participant_difference_faster_minus_slower"], -1)

    def test_reject_duplicate_export_in_aggregator(self):
        rows = make_study_rows()
        with TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f"p{i}.csv" for i in range(2)]
            for path in paths:
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS_V2)
                    writer.writeheader()
                    writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "Duplicate participant"):
                read_study_csvs(paths)

    def test_reject_wrong_trial_order(self):
        rows = make_study_rows()
        rows[0]["trial_index"], rows[1]["trial_index"] = rows[1]["trial_index"], rows[0]["trial_index"]
        with self.assertRaisesRegex(ValueError, "assigned sequence"):
            summarize_participants(rows)

    def test_reject_mixed_audio_versions(self):
        rows = make_study_rows() + make_study_rows("vr2-" + "2" * 20, 1)
        rows[-1]["audio_fingerprint"] = "f" * 64
        with self.assertRaises(ValueError):
            summarize_participants(rows)

    def test_reject_malformed_rating(self):
        rows = make_study_rows()
        rows[2]["clarity"] = "7"
        with self.assertRaisesRegex(ValueError, "clarity"):
            summarize_participants(rows)

    def test_reject_legacy_pilot_file(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.csv"
            path.write_text("trial_index,authority\n1,4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a VoiceRank"):
                read_study_csvs([path])
