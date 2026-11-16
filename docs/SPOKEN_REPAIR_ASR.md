# VoiceRank/WaitWise bridge: spoken self-repair stress test

**Purpose:** test whether local ASR preserves revisions and whether transcription changes flip WaitWise V3's text-only classification. This is a bridge between the audio and authorization research streams, *not* a direct test of vocal authority or an AI agent.

## How to run (free, local, Mac)

Requires the previously installed `whisper.cpp`, `ggml-tiny.en.bin` and `say`/`afconvert` macOS utilities. No additional dependencies.

```bash
python spoken_repair_benchmark.py --generate
python spoken_repair_benchmark.py --run-asr
```

16 WAV clips: 8 constructed utterances (4 explicit revisions; 4 unrelated follow-ups) synthesized with the same TTS voice at 155 and 210 nominal WPM. WAV clips and manifest are created in `~/Desktop/voxgate-spoken-repair-stimuli/`, without changing your original VoiceRank clips. The generator refuses to overwrite a nonempty output folder. To verify later: `python spoken_repair_benchmark.py --check`.

Outputs:

- `~/Desktop/voxgate-spoken-repair-reports/spoken_repair_trials.csv`
- `~/Desktop/voxgate-spoken-repair-reports/spoken_repair_summary.json`

Metrics: punctuation-insensitive WER; exact word-sequence matches; TP/FP/FN/TN on ASR output compared against researcher-assigned instruction-revision labels; `prediction flips` measures changes relative to applying the unchanged V3 detector to the original written transcript.

**Important interpretation:** A 0% WER does not prove identical punctuation, and V3 relies on punctuation to split commands. ASR punctuation errors can therefore alter safety-gate outputs without word errors. The labels are constructed and used for development, with no independent annotation. The spoken clips have no real hesitations or interactive turn-taking beyond TTS punctuation. No real actions or tools can be executed. This experiment does not measure speaker authority, consent or real-world agent safety.
