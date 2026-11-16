# WaitWise: fresh constructed speech benchmark after V4

This batch provides **24 newly written scenarios** (12 explicit instruction revisions, 12 non-revisions), each synthesized at 155 and 210 nominal WPM, for **48 recordings** total. The cases and reference labels are frozen in `core/spoken_repair_fresh.py` before running Whisper. V3 and V4 are **unchanged**. Original audio and reports are untouched.

## Protocol

1. Run `python -m unittest core.test_spoken_repair_fresh -q`.
2. Run `python spoken_repair_fresh_benchmark.py --generate` **once**. This creates new files in `~/Desktop/voxgate-fresh-spoken-repair-stimuli/` and refuses to overwrite them.
3. Run `python spoken_repair_fresh_benchmark.py --run-asr`. This uses only the previously installed local Whisper CLI and the local tiny.en model. There are no paid API calls. It saves per-clip CSV and summary JSON in `~/Desktop/voxgate-fresh-spoken-repair-reports/`.
4. Optionally run `python spoken_repair_fresh_benchmark.py --check` to verify audio hashes and metadata later.

Metrics: word error rate (WER), exact transcript matching, V3/V4 TP/FP/FN/TN, precision, recall, accuracy, and number of items flagged for **review**. The experimental `triage` comparator requests review when V4 detects a revision, the detectors disagree, the opening command is unrecognized, or the transcript is empty. It does not ever authorize release. Additional review requests may be false alarms. The tool never authorizes or executes real actions. **A negative detector result does not establish that an action is safe or authorized.**

## Essential limitations

- The 24 scenario texts were authored after V4; they have **not been independently annotated** and they were not sampled from natural conversations. They are a new pre-specified *constructed evaluation set*, not a representative benchmark. Check labels with independent annotators before any publication claim.
- To make a genuine held-out comparison, freeze V3/V4 and this dataset, report results once, and do not modify detector logic on the resulting errors. Any tuning means the set becomes development data, requiring a new blind evaluation.
- The stimuli are macOS synthetic speech with limited expressive prosody. The two rates have nominal labels; acoustic measurement is needed for realized timing. Native conversational repairs, overlapping speech, timing, hesitation and pitch/voice authority effects are not represented.
- Whisper transcription errors and detector failures must be distinguished. Review the per-trial file rather than only summary scores.
- No inference of **perceived authority** is possible from these ASR results; for that the research requires controlled voice cues and an audio-capable model with appropriate experimental baselines.

## Deliverables

- `fresh_spoken_repair_trials.csv`: frozen reference, recognized text, labels, detector outputs, transcription errors for every clip.
- `fresh_spoken_repair_summary.json`: grouped, comparable metrics and limitations.

## Next research step

Ask independent listeners to classify revision vs non-revision before opening any model predictions, then separately evaluate real audio-capable models with wholly simulated actions. Keep instructions, audio, prompts and annotator protocols versioned and do not infer consent from a heuristic.
