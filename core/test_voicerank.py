"""Offline tests; no Django, audio hardware, API, or macOS required."""
from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from core.voicerank import (
    CONDITIONS, EXPORT_FIELDS, PROMPTS, audio_is_wav, export_rows,
    file_digest, paired_authority_summary, stimulus_plan, validate_manifest, validate_ratings,
)


def wav_fixture(path: Path) -> None:
    """Generate a deliberately tiny WAV for metadata/testing only (no speech)."""
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 96)


def create_fixture(directory: Path) -> list[dict[str, str | int]]:
    directory.mkdir(parents=True, exist_ok=True)
    records = stimulus_plan()
    for item in records:
        wav_path = directory / str(item["file_name"])
        wav_fixture(wav_path)
        item["sha256"] = file_digest(wav_path)
    (directory / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "method": "same_voice_two_speech_rates", "stimuli": records}),
        encoding="utf-8",
    )
    return records


class VoiceRankPureTests(unittest.TestCase):
    def test_plan_has_four_matched_pairs(self):
        plan = stimulus_plan()
        self.assertEqual(len(plan), 8)
        self.assertEqual(len({item["clip_id"] for item in plan}), 8)
        for prompt_id, text in PROMPTS:
            matches = [item for item in plan if item["prompt_id"] == prompt_id]
            self.assertEqual(len(matches), 2)
            self.assertEqual({item["transcript"] for item in matches}, {text})
            self.assertEqual({item["rate_wpm"] for item in matches}, {155, 210})
            self.assertEqual(len({item["voice"] for item in matches}), 1)

    def test_valid_fixture_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_fixture(root)
            self.assertEqual(len(validate_manifest(root)), 8)

    def test_changed_audio_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = create_fixture(root)
            audio = root / str(plan[0]["file_name"])
            audio.write_bytes(audio.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "integrity"):
                validate_manifest(root)

    def test_path_traversal_in_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_fixture(root)
            path = root / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["stimuli"][0]["file_name"] = "../../private.wav"
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate_manifest(root)

    def test_mixed_voices_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_fixture(root)
            path = root / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["stimuli"][0]["voice"] = "different-voice"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "same TTS voice"):
                validate_manifest(root)

    def test_rating_validation(self):
        self.assertEqual(validate_ratings({"authority": "4", "clarity": "3", "urgency": "1"}),
                         {"authority": 4, "clarity": 3, "urgency": 1})
        for invalid in ("0", "6", "4.0", "", "no"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_ratings({"authority": invalid, "clarity": "3", "urgency": "1"})

    def test_export_includes_condition_only_after_ratings(self):
        plan = stimulus_plan()
        order = [str(item["clip_id"]) for item in reversed(plan)]
        ratings = {order[0]: {"authority": 4, "clarity": 5, "urgency": 2}}
        rows = export_rows(plan, order, ratings)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trial_index"], 1)
        self.assertEqual(set(rows[0]), set(EXPORT_FIELDS))
        self.assertIn(rows[0]["condition"], {"faster", "slower"})

    def test_paired_authority_computation(self):
        plan = stimulus_plan()
        order = [str(item["clip_id"]) for item in plan]
        ratings = {
            str(item["clip_id"]): {"authority": 5 if item["condition"] == "faster" else 3,
                                    "clarity": 4, "urgency": 3}
            for item in plan
        }
        rows = export_rows(plan, order, ratings)
        summary = paired_authority_summary(rows)
        self.assertEqual(summary["complete_pairs"], 4)
        self.assertEqual(summary["mean_difference_faster_minus_slower"], 2.0)
        self.assertEqual(paired_authority_summary(rows[:1])["complete_pairs"], 0)

    def test_duplicate_rating_rejected_in_analysis(self):
        plan = stimulus_plan()
        order = [str(item["clip_id"]) for item in plan]
        ratings = {order[0]: {"authority": 2, "clarity": 2, "urgency": 2}}
        rows = export_rows(plan, order, ratings)
        with self.assertRaises(ValueError):
            paired_authority_summary(rows + rows)

    def test_generator_refuses_to_overwrite(self):
        from generate_voicerank_stimuli import generate
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_fixture(root)
            with patch("generate_voicerank_stimuli.platform.system", return_value="Darwin"), \
                 patch("generate_voicerank_stimuli.shutil.which", return_value="/usr/bin/true"):
                with self.assertRaises(FileExistsError):
                    generate(root)

    def test_generator_uses_no_shell_and_one_voice(self):
        from generate_voicerank_stimuli import generate
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "voice"
            def fake_run(command, **kwargs):
                if command[0] == "say":
                    self.assertNotIn("shell", kwargs)
                    self.assertTrue(kwargs.get("input"))
                    (Path(command[command.index("-o") + 1])).write_bytes(b"dummy-aiff")
                else:
                    self.assertEqual(command[0], "afconvert")
                    wav_fixture(Path(command[-1]))
                return None
            with patch("generate_voicerank_stimuli.platform.system", return_value="Darwin"), \
                 patch("generate_voicerank_stimuli.shutil.which", return_value="/usr/bin/mock"), \
                 patch("generate_voicerank_stimuli.subprocess.run", side_effect=fake_run) as runner:
                self.assertEqual(generate(root), 8)
                self.assertEqual(runner.call_count, 16)
                self.assertEqual(len(validate_manifest(root)), 8)
                with self.assertRaises(FileExistsError):
                    generate(root)


if __name__ == "__main__":
    unittest.main()
