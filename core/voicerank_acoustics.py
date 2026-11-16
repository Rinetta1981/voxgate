"""Audio quality audit for the existing VoiceRank v1/v2 matched speech clips.

This is a waveform-level quality check, not perceptual inference or agent safety.
Uses only Python standard-library modules; no APIs or downloads.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import sys
import wave

from .voicerank import validate_manifest

MAX_FILE_BYTES = 50 * 1024 * 1024


def measure_pcm16_wav(path: Path) -> dict[str, float | int | bool]:
    """Measure PCM16 WAV duration and amplitude without loading the whole file.

    RMS and peak are normalized by 32768; neither measures perceived loudness.
    Duration includes pauses and silence. No pitch or stress is measured.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"Unsafe, absent, or oversized audio file: {path}")
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            nframes = audio.getnframes()
            if (audio.getcomptype() != "NONE" or sample_width != 2
                    or channels not in (1, 2) or not 8000 <= sample_rate <= 192000
                    or not 0 < nframes <= sample_rate * 120):
                raise ValueError("Expected mono/stereo uncompressed PCM16 WAV, at most 120 seconds")
            peak = 0
            square_sum = 0
            sample_count = 0
            frame_count = 0
            while True:
                payload = audio.readframes(4096)
                if not payload:
                    break
                if len(payload) % (2 * channels):
                    raise ValueError("Truncated WAV sample data")
                samples = array("h")
                samples.frombytes(payload)
                if sys.byteorder != "little":
                    samples.byteswap()
                for value in samples:
                    abs_value = abs(value)
                    if abs_value > peak:
                        peak = abs_value
                    square_sum += value * value
                sample_count += len(samples)
                frame_count += len(samples) // channels
            if frame_count != nframes or sample_count == 0:
                raise ValueError("WAV frame count is inconsistent")
    except (OSError, EOFError, wave.Error) as exc:
        raise ValueError(f"Cannot decode PCM16 WAV: {path}") from exc
    rms = math.sqrt(square_sum / sample_count) / 32768.0
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "duration_seconds": round(nframes / sample_rate, 4),
        "rms_dbfs": round(20 * math.log10(rms), 2) if rms > 0 else float("-inf"),
        "peak_dbfs": round(20 * math.log10(peak / 32768.0), 2) if peak else float("-inf"),
        "near_clipping": peak >= 32760,
    }


def audit_stimuli(directory: Path) -> tuple[list[dict], list[dict]]:
    """Validate original manifest and compare measured durations per matched pair."""
    directory = Path(directory).expanduser()
    records = validate_manifest(directory)
    clips = []
    by_prompt = {}
    for record in records:
        measurements = measure_pcm16_wav(directory / str(record["file_name"]))
        word_count = len(str(record["transcript"]).split())
        duration = measurements["duration_seconds"]
        row = {
            "prompt_id": record["prompt_id"],
            "clip_id": record["clip_id"],
            "condition": record["condition"],
            "nominal_wpm": record["rate_wpm"],
            "word_count": word_count,
            "whole_clip_wpm": round(60 * word_count / duration, 2),
            **measurements,
        }
        clips.append(row)
        by_prompt.setdefault(str(record["prompt_id"]), {})[str(record["condition"])] = row
    pairs = []
    for prompt, pair in sorted(by_prompt.items()):
        if set(pair) != {"slower", "faster"}:
            raise ValueError(f"Missing acoustic pair for {prompt}")
        slow = pair["slower"]
        fast = pair["faster"]
        pairs.append({
            "prompt_id": prompt,
            "slower_duration_s": slow["duration_seconds"],
            "faster_duration_s": fast["duration_seconds"],
            "fast_to_slow_nominal_wpm_ratio": round(fast["nominal_wpm"] / slow["nominal_wpm"], 3),
            "fast_to_slow_observed_whole_clip_rate_ratio": round(slow["duration_seconds"] / fast["duration_seconds"], 3),
            "fast_clip_is_shorter": fast["duration_seconds"] < slow["duration_seconds"],
            "rms_difference_fast_minus_slow_db": round(fast["rms_dbfs"] - slow["rms_dbfs"], 2),
            "any_near_clipping": slow["near_clipping"] or fast["near_clipping"],
        })
    return clips, pairs
