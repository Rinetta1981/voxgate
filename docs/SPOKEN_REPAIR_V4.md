# WaitWise V4: punctuation-tolerant analysis of saved ASR transcripts

## Motivation

In the first eight-pair synthesized-speech experiment, Whisper had 16.2% WER at **both** rates, but WaitWise V3 classified all four genuine repairs as negatives in each rate condition (zero recall). This is not purely a WER problem: V3 uses punctuation to segment the speech, while Whisper often emits commas instead of sentence boundaries.

V4 adds a *separate, experimental* rule-based detector for possible instruction revisions that looks for an initial imperative and then a correction cue followed by a new directive, regardless of punctuation. This preserves the existing V3 detector and website safety gate as baselines; nothing is automatically released or authorized.

The detector **does not guess homophones**. For example, `weight` is not automatically treated as `wait`. This can miss genuine repairs after ASR corruption, but keeps the system from silently inventing authority-bearing words.

## Run the comparison (free, local)

The previous command `python spoken_repair_benchmark.py --run-asr` must have already generated the saved CSV. From `~/Desktop/voxgate` with the existing Python virtual environment active:

```bash
python -m unittest core.test_spoken_repair_v4 -q
python compare_spoken_repair_v4.py
```

There are **no new model calls, downloads, or audio-generation steps**. The script checks all 16 saved trial identities, the original constructed labels, and transcription metrics before comparing V3 and V4. Results are stored in `~/Desktop/voxgate-spoken-repair-v4-reports/`:

- `v3_v4_trials.csv`: one row for each clip, original label, V3, V4, result type and prediction change.
- `v3_v4_summary.json`: confusion matrices, precision, recall, accuracy, F1 for each condition and both conditions combined.

## Interpretation and limitations

- These examples were inspected before V4 was designed. **Any improvement is an in-sample development result, not independent evidence of better generalization**. Obtain new, independently annotated clips before making performance claims.
- V4 checks only a restricted vocabulary and explicit repairs. It may miss elliptical/self-interrupted revisions such as “no, folder B” and ASR-induced substitutions. It can still misclassify an unrelated follow-up that happens to match a repair cue plus command.
- No speech-to-model authority signal, speaker intent, human confirmation, actual tool action, or consent was measured. Do **not** wire V4 directly into authorization decisions without further evaluation.
- Synthetic macOS speech has no genuine disfluencies or conversational timing. A subsequent evaluation needs recorded (or carefully scripted) self-repair speech and truly held-out prompts.
