# VoiceRank speech stimulus acoustic audit

This module verifies the actual *waveform durations and amplitudes* of the eight synthesized VoiceRank recordings. The original perception study labels the conditions 155 and 210 nominal words per minute, which are macOS `say` synthesis settings, not direct acoustic measurements.

## Run locally, for free

In the project directory after installing the ZIP:

```bash
python -m unittest core.test_voicerank_acoustics -v
python audit_voicerank_audio.py
```

No new dependencies, model calls, speech generation, downloads, or third-party API requests are used. The script checks the original WAV manifest and SHA-256 digests, then reads the existing audio files from `~/Desktop/voxgate-voice-stimuli`.

Reports will be saved to `~/Desktop/voxgate-acoustic-reports`:

- `clip_acoustics.csv`: duration including silence, sample rate, channels, RMS and peak amplitude in dBFS, approximate whole-clip words per minute.
- `paired_acoustics.csv`: slower/faster durations and relative duration-derived rate, plus level differences.
- `acoustic_summary.json`: high-level quality-control summary and limitations.

## Scientific limitations

This is a **manipulation quality-control check**, not a validated phonetic analysis. Total duration includes silence, and the whole-clip rate estimate counts written words divided by total duration; it is *not* a measurement of syllable rate, articulation rate, or timing of individual words. RMS dBFS is not perceived loudness. These measures do not test F0, intonation, stress, accent, social identity, perceived authority, or AI agent permission decisions. Mac speech synthesis may change several acoustic properties as the speaking rate changes.

The first expanded study CSV contains one participant. Its direction of ratings cannot be generalized without adequate independent samples and ethically reviewed collection procedures. Next research phases include independent listener replication, a fuller acoustic prosody analysis, and an actual audio-conditioned model experiment comparing matched audio to transcript-only baselines.
