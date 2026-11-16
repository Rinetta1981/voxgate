"""Regression and provenance tests for experimental punctuation-tolerant V4."""
from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .analysis_v3 import detect_instruction_revision_v3
from .analysis_v4 import detect_instruction_revision_v4 as v4
from .spoken_repair import CASES, plan
from .voicerank_speech import transcription_score
from compare_spoken_repair_v4 import compare, read_verified_results


class RepairV4Tests(TestCase):
    def test_detects_revision_with_or_without_punctuation(self):
        texts = (
            "Send the report to Alice actually send it to Bob",
            "Send the report to Alice, actually, send it to Bob.",
            "Please delete the draft no keep the draft",
            "Book the morning flight sorry make it the evening flight",
            "Email Mira wait email Niko instead",
            "Book the morning flight but change that to the evening flight",
            "Send the report now actually wait do not send it yet",
            "At noon, send the announcement. Sorry, make it 3 PM.",
        )
        for sentence in texts:
            with self.subTest(sentence=sentence):
                self.assertTrue(v4(sentence))

    def test_ignores_unrelated_cues_and_contrasts(self):
        texts = (
            "Send the report to Alice actually the agenda changed",
            "Please delete the draft sorry about the delay",
            "Book the morning flight wait what time is the meeting",
            "Email Mira actually the budget was approved",
            "Email the team instead of calling them",
            "Please wait until tomorrow to send the report",
            "The report arrived yesterday actually please send it now",
        )
        for sentence in texts:
            with self.subTest(sentence=sentence):
                self.assertFalse(v4(sentence))

    def test_asr_orthography_only_not_homophone_guesses(self):
        self.assertTrue(v4("E-mail Mira, wait, e-mail Nico instead"))
        self.assertFalse(v4("e-mail mirror, weight, e-mail Niko instead."))
        self.assertFalse(v4("Center report to Alice, actually, sent it to Bob."))
        self.assertFalse(v4("The booking was fine, actually, send it to Bob."))

    def test_original_reference_stimuli(self):
        for _, text, label, _ in CASES:
            with self.subTest(text=text):
                self.assertEqual(int(v4(text)), label)

    def test_v3_unchanged_and_punctuation_sensitivity(self):
        text = "Send the report to Alice actually send it to Bob"
        self.assertFalse(detect_instruction_revision_v3(text))
        self.assertTrue(v4(text))

    def test_challenge_negatives(self):
        negative = (
            "Send the memo to Pat. Actually, the presentation went well.",
            "Book the room for Friday. Wait, what time does the venue close?",
            "Please move the files to Archive. Sorry about yesterday.",
            "Email the team instead of calling them.",
        )
        self.assertTrue(all(not v4(t) for t in negative))

    def test_saved_report_round_trip(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "spoken_repair_trials.csv"
            rows = []
            for trial in plan():
                score = transcription_score(trial["transcript"], trial["transcript"])
                rows.append({
                    "clip_id": trial["clip_id"], "case_id": trial["case_id"],
                    "condition": trial["condition"], "gold_revision": trial["gold_revision"],
                    "discourse_function": trial["discourse_function"],
                    "reference_transcript": trial["transcript"], "asr_transcript": trial["transcript"], **score,
                })
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            verified = read_verified_results(path)
            outcomes, summary = compare(verified)
            self.assertEqual(len(outcomes), 16)
            self.assertEqual(len(summary), 6)
            v4both = next(r for r in summary if r["condition"] == "both" and r["version"] == "v4")
            self.assertEqual((v4both["tp"], v4both["fp"], v4both["fn"], v4both["tn"]), (8, 0, 0, 8))
            # Defend against metadata mismatches.
            rows[0]["gold_revision"] = 0
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError):
                read_verified_results(path)

    def test_synthetic_spoken_asr_samples(self):
        observed = {
            "SR01": ("Send the report to Alice, actually, send it to Bob.", "Center report to Alice, actually, sent it to Bob."),
            "SR02": ("Please delete the draft, no, keep the draft.", "Please delete the draft, no, keep the draft."),
            "SR03": ("Book the morning slide, sorry, make it the evening slide.", "Put the morning slide. Sorry, make it the evening slide."),
            "SR04": ("e-mail mirror, weight, e-mail Niko instead.", "Email Mira, wait, email Nico instead."),
            "SR05": ("Send the report to Alice, actually, the agenda changed.", "Center report to Alice, actually, the agenda changed."),
            "SR06": ("Please delete the draft. Sorry about the delay.", "Please delete the draft. Sorry about the delay."),
            "SR07": ("book The Morning Slide. Wait, what time is the meeting?", "Put the morning slide. Wait, what time is the meeting?"),
            "SR08": ("E-mail Mira, actually, the budget was approved.", "Email Mira, actually, the budget was approved."),
        }
        self.assertEqual(sum(v4(t[0]) for case, t in observed.items() if case in {"SR01", "SR02", "SR03", "SR04"}), 3)
        self.assertEqual(sum(v4(t[1]) for case, t in observed.items() if case in {"SR01", "SR02", "SR03", "SR04"}), 3)
        self.assertEqual(sum(v4(text) for case, pair in observed.items() if case not in {"SR01", "SR02", "SR03", "SR04"} for text in pair), 0)
