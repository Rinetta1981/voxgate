"""Offline tests for ASR-mediated spoken repair; no model calls."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock
import wave

from .analysis_v3 import detect_instruction_revision_v3
from .spoken_repair import CASES, CONDITIONS, analyze_asr, plan, validate
from .voicerank import file_digest
from .voicerank_speech import transcription_score


def fake_audio(folder: Path):
    entries = []
    for rec in plan():
        audio = folder / rec["file_name"]
        with wave.open(str(audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 100)
        entries.append({**rec, "sha256": file_digest(audio)})
    (folder / "manifest.json").write_text(json.dumps({"schema": 1, "stimuli": entries}), encoding="utf-8")
    return entries


class SpokenRepairTests(TestCase):
    def test_balanced_paired_design(self):
        entries = plan()
        self.assertEqual(len(entries), 16)
        self.assertEqual(len({r["clip_id"] for r in entries}), 16)
        for condition, rate in CONDITIONS:
            subset = [r for r in entries if r["condition"] == condition]
            self.assertEqual(len(subset), 8)
            self.assertEqual(sum(r["gold_revision"] for r in subset), 4)
            self.assertEqual({r["rate_wpm"] for r in subset}, {rate})
        for i in range(0, 16, 2):
            self.assertEqual(entries[i]["transcript"], entries[i+1]["transcript"])

    def test_reference_labels_match_v3_for_selected_development_examples(self):
        for entry in plan():
            with self.subTest(case=entry["case_id"]):
                self.assertEqual(int(detect_instruction_revision_v3(entry["transcript"])), entry["gold_revision"])

    def test_stimuli_identifiers_deterministic(self):
        self.assertEqual(plan(), plan())
        self.assertEqual({x["voice"] for x in plan()}, {"system_default"})

    def test_invalid_voice(self):
        with self.assertRaises(ValueError):
            plan("a\n-b")

    def test_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            expected = fake_audio(folder)
            self.assertEqual(validate(folder), expected)

    def test_manifest_detects_changed_content(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            fake_audio(folder)
            target = folder / plan()[0]["file_name"]
            target.write_bytes(target.read_bytes() + b"damaged")
            with self.assertRaises(ValueError):
                validate(folder)

    def test_manifest_detects_duplicate_record(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            fake_audio(folder)
            path = folder / "manifest.json"
            data = json.loads(path.read_text())
            data["stimuli"][0] = data["stimuli"][1]
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                validate(folder)

    def test_manifest_detects_swapped_labels(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            fake_audio(folder)
            path = folder / "manifest.json"
            data = json.loads(path.read_text())
            data["stimuli"][0]["gold_revision"] = 0
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                validate(folder)

    def test_perfect_asr_summary(self):
        entries = plan()
        rows, summary = analyze_asr(entries, {e["clip_id"]: e["transcript"] for e in entries})
        self.assertEqual(len(rows), 16)
        for item in summary:
            self.assertEqual((item["tp"],item["fp"],item["fn"],item["tn"]), (4,0,0,4))
            self.assertEqual(item["micro_wer"], 0)
            self.assertEqual(item["exact_matches"], 8)
            self.assertEqual(item["v3_prediction_changes_from_reference"], 0)

    def test_punctuation_can_change_gate_without_word_errors(self):
        import re
        entries = plan()
        unpunctuated = {e["clip_id"]: re.sub(r"[^\w\s]", "", e["transcript"]) for e in entries}
        rows, summary = analyze_asr(entries, unpunctuated)
        self.assertTrue(all(s["micro_wer"] == 0 for s in summary))
        self.assertTrue(all(s["v3_prediction_changes_from_reference"] == 4 for s in summary))
        self.assertTrue(all(s["fn"] == 4 for s in summary))

    def test_missing_trial_rejected(self):
        entries = plan()
        with self.assertRaises(ValueError):
            analyze_asr(entries, {e["clip_id"]: e["transcript"] for e in entries[:-1]})

    def test_overlong_asr_rejected(self):
        entries = plan()
        asr = {e["clip_id"]: e["transcript"] for e in entries}
        asr[entries[0]["clip_id"]] = "A" * 4001
        with self.assertRaises(ValueError):
            analyze_asr(entries, asr)

    def test_generation_refuses_to_overwrite_existing_data(self):
        from spoken_repair_benchmark import generate_audio
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "old_audio.wav").write_bytes(b"test")
            with mock.patch("spoken_repair_benchmark.platform.system", return_value="Darwin"), \
                 mock.patch("spoken_repair_benchmark.shutil.which", return_value="/bin/say"):
                with self.assertRaises(FileExistsError):
                    generate_audio(folder, "system_default")
            self.assertTrue((folder / "old_audio.wav").exists())
