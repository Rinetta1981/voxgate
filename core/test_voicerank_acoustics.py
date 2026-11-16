"""Standard-library regression tests for the VoiceRank acoustic audit."""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from unittest import TestCase
import wave

from .voicerank import stimulus_plan, file_digest
from .voicerank_acoustics import audit_stimuli, measure_pcm16_wav


def write_wav(path: Path, *, nframes: int, rate: int = 8000, loud: bool = False) -> None:
    amplitude = 32760 if loud else 2500
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / rate)) for i in range(nframes)]
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(struct.pack("<" + "h" * nframes, *samples))


class VoiceRankAcousticsTests(TestCase):
    def test_duration_and_normalized_amplitudes(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "example.wav"
            write_wav(p, nframes=4000)
            observed = measure_pcm16_wav(p)
            self.assertEqual(observed["duration_seconds"], 0.5)
            self.assertEqual(observed["sample_rate_hz"], 8000)
            self.assertLess(observed["rms_dbfs"], 0)
            self.assertFalse(observed["near_clipping"])

    def test_reject_missing_file(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                measure_pcm16_wav(Path(folder) / "missing.wav")

    def test_reject_wrong_sample_width(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "wrong.wav"
            with wave.open(str(p), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(1)
                audio.setframerate(8000)
                audio.writeframes(bytes([128] * 8000))
            with self.assertRaises(ValueError):
                measure_pcm16_wav(p)

    def test_reject_empty_recording(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "empty.wav"
            with wave.open(str(p), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b"")
            with self.assertRaises(ValueError):
                measure_pcm16_wav(p)

    def test_pair_ratios_and_integrity(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            entries = []
            for entry in stimulus_plan():
                duration_frames = 8000 if entry["condition"] == "slower" else 4000
                p = root / entry["file_name"]
                write_wav(p, nframes=duration_frames)
                entries.append({**entry, "sha256": file_digest(p)})
            (root / "manifest.json").write_text(json.dumps({"schema_version": 1, "stimuli": entries}))
            clips, pairs = audit_stimuli(root)
            self.assertEqual(len(clips), 8)
            self.assertEqual(len(pairs), 4)
            self.assertTrue(all(p["fast_clip_is_shorter"] for p in pairs))
            self.assertTrue(all(p["fast_to_slow_observed_whole_clip_rate_ratio"] == 2 for p in pairs))
            (root / entries[0]["file_name"]).write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                audit_stimuli(root)
