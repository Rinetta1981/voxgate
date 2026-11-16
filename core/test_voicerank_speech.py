"""Tests for VoiceRank offline ASR metrics, integrity and inert model selection."""
from __future__ import annotations

from array import array
import csv
import json
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import wave

from .voicerank import file_digest, stimulus_plan
from .voicerank_speech import (
    AUDIO_RATE, VOICE_ACTIONS, asr_summary, build_asr_row,
    convert_wav_to_whisper, edit_distance, recognize_clip, require_whisper,
    transcription_score, validate_asr_rows, words,
)


def write_sound(path: Path, *, rate: int = 8000, n: int = 800, channels: int = 1):
    samples = []
    for i in range(n):
        value = int(2000 * math.sin(i * 2 * math.pi * 200 / rate))
        samples.extend([value] * channels)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))


def fake_stimuli(folder: Path):
    records = []
    for item in stimulus_plan():
        path = folder / item["file_name"]
        write_sound(path)
        records.append({**item, "sha256": file_digest(path)})
    (folder / "manifest.json").write_text(json.dumps({"schema_version": 1, "stimuli": records}))
    return records


class TranscriptScoresTests(TestCase):
    def test_tokenization_is_case_and_punctuation_independent(self):
        self.assertEqual(words("Send the summary, NOW!"), ["send", "the", "summary", "now"])
        self.assertEqual(transcription_score("Send the summary.", "SEND THE SUMMARY"),
                         {"reference_words": 3, "word_edits": 0, "wer": 0., "exact_match": 1})

    def test_substitution_insertion_deletion(self):
        self.assertEqual(edit_distance(["a", "b", "c"], ["a", "x", "c"]), 1)
        self.assertEqual(edit_distance(["a", "b"], ["a", "b", "c"]), 1)
        self.assertEqual(edit_distance(["a", "b", "c"], ["a", "b"]), 1)

    def test_empty_hypothesis_is_not_a_perfect_transcription(self):
        score = transcription_score("Send the summary.", "")
        self.assertEqual(score["wer"], 1)
        self.assertEqual(score["exact_match"], 0)

    def test_wer_can_exceed_one_with_insertions(self):
        score = transcription_score("Send.", "send many extra words today")
        self.assertGreater(score["wer"], 1)

    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError):
            transcription_score("", "send")

    def test_one_fixed_catalog(self):
        self.assertEqual(len(VOICE_ACTIONS), 4)
        self.assertEqual(len(set(VOICE_ACTIONS)), 4)


class AudioAndIntegrationTests(TestCase):
    def test_resampling_to_16khz_mono_from_stereo(self):
        with TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "in.wav", Path(tmp) / "out.wav"
            write_sound(src, rate=8000, n=800, channels=2)
            convert_wav_to_whisper(src, dst)
            with wave.open(str(dst), "rb") as audio:
                self.assertEqual(audio.getframerate(), AUDIO_RATE)
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getnframes(), 1600)
                self.assertEqual(audio.getsampwidth(), 2)

    def test_empty_wav_rejected(self):
        with TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "in.wav", Path(tmp) / "out.wav"
            with wave.open(str(src), "wb") as sound:
                sound.setnchannels(1)
                sound.setsampwidth(2)
                sound.setframerate(16000)
            with self.assertRaises(ValueError):
                convert_wav_to_whisper(src, dst)

    def test_local_whisper_requires_executable_and_model(self):
        with TemporaryDirectory() as tmp:
            with mock.patch("core.voicerank_speech.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "not found"):
                    require_whisper(Path(tmp) / "model.bin")
            with mock.patch("core.voicerank_speech.shutil.which", return_value="/bin/true"):
                with self.assertRaisesRegex(RuntimeError, "missing"):
                    require_whisper(Path(tmp) / "model.bin")

    def test_whisper_is_invoked_without_shell(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "a.wav"
            write_sound(src)
            def mock_run(command, **kwargs):
                self.assertEqual(command[0], "/local/whisper-cli")
                self.assertIn("--model", command)
                self.assertIn("--language", command)
                self.assertNotIn("--translate", command)
                self.assertNotIn("shell", kwargs)
                (root / "recognition.txt").write_text("Send the summary.")
                return mock.Mock(returncode=0, stderr="")
            with mock.patch("core.voicerank_speech.subprocess.run", side_effect=mock_run):
                transcript = recognize_clip(src, root / "model.bin", "/local/whisper-cli", root)
            self.assertEqual(transcript, "Send the summary.")

    def test_summary_counts_and_verified_csv(self):
        records = [{**item, "sha256": "a" * 64} for item in stimulus_plan()]
        rows = []
        for entry in records:
            text = entry["transcript"] if entry["condition"] == "slower" else ""
            rows.append(build_asr_row(entry, text))
        validate_asr_rows(records, [{k: str(v) for k, v in row.items()} for row in rows])
        summary = asr_summary(rows)
        self.assertEqual([group["exact_matches"] for group in summary], [4, 0])
        self.assertEqual([group["micro_wer"] for group in summary], [0, 1])

    def test_tampered_transcript_or_hash_rejected(self):
        records = [{**item, "sha256": "a" * 64} for item in stimulus_plan()]
        rows = [{k: str(v) for k, v in build_asr_row(entry, entry["transcript"]).items()} for entry in records]
        rows[0]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "audio mismatch"):
            validate_asr_rows(records, rows)
        rows[0]["sha256"] = "a" * 64
        rows[1]["asr_transcript"] = "Unrelated transcript"
        with self.assertRaisesRegex(ValueError, "scores"):
            validate_asr_rows(records, rows)

    def test_duplicate_clip_rejected(self):
        records = [{**item, "sha256": "a" * 64} for item in stimulus_plan()]
        rows = [{k: str(v) for k, v in build_asr_row(entry, "").items()} for entry in records]
        rows[1] = rows[0].copy()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_asr_rows(records, rows)

    def test_full_asr_run_creates_local_reports(self):
        from voicerank_speech_benchmark import run_asr
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice_dir, reports = root / "voice", root / "reports"
            voice_dir.mkdir()
            records = fake_stimuli(voice_dir)
            with mock.patch("voicerank_speech_benchmark.require_whisper", return_value="/local/whisper-cli"):
                with mock.patch("voicerank_speech_benchmark.recognize_clip", side_effect=lambda path, model, cli, td: next(
                    x["transcript"] for x in records if path.name == x["file_name"])):
                    run_asr(records, voice_dir, reports, root / "model.bin")
            with (reports / "voicerank_asr_trials.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["exact_match"] == "1" for row in rows))
            self.assertTrue((reports / "voicerank_asr_summary.json").exists())

    def test_run_model_is_inert_and_requires_saved_asr(self):
        from voicerank_speech_benchmark import run_model
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [{**item, "sha256": "a" * 64} for item in stimulus_plan()]
            rows = [build_asr_row(entry, entry["transcript"]) for entry in records]
            out = root / "reports"
            out.mkdir()
            with (out / "voicerank_asr_trials.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            def response(transcript, catalog):
                self.assertEqual(catalog, VOICE_ACTIONS)
                return json.dumps({"action_id": transcript})
            class FakeModel:
                model = "test:local"
                def __init__(self, *args, **kwargs):
                    pass
                def check_ready(self):
                    return {}
                def __call__(self, transcript, catalog):
                    return response(transcript, catalog)
            with mock.patch("core.local_agent.LocalOllamaModel", FakeModel):
                run_model(records, out, "test:local")
            with (out / "voicerank_text_decisions.csv").open(newline="") as f:
                result = list(csv.DictReader(f))
            self.assertEqual(len(result), 16)
            self.assertEqual(sum(int(r["correct"]) for r in result), 16)
            self.assertEqual(sum(int(r["incorrect"]) for r in result), 0)
