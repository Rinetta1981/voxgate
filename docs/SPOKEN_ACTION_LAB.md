# VOXGATE: Local spoken-action comparison (experimental)

**Research question:** When a local text model receives either a canonical instruction or a Whisper transcription of synthesized speech, does it propose a different symbolic action? How does a *review-only* WaitWise gate alter proposal coverage and wrong-proposal counts?

This is a **text-only downstream model**. Neither Qwen nor WaitWise hears the audio, perceives authority, or executes anything. Whisper is the only component processing acoustic input.

## Requirements

- Prior successful `spoken_repair_fresh_benchmark.py --run-asr` output at `~/Desktop/voxgate-fresh-spoken-repair-reports/fresh_spoken_repair_trials.csv`.
- Your already-installed local Ollama model (`qwen2.5:0.5b`), available on `127.0.0.1:11434`.
- No Python dependencies beyond existing VOXGATE requirements; **no cloud API or downloads**.

## Commands

```bash
cd ~/Desktop/voxgate
python -m unittest core.test_spoken_action -q
python spoken_action_benchmark.py
python spoken_action_benchmark.py --run-local --limit 4
# Optionally, after inspecting the first run:
python spoken_action_benchmark.py --run-local --limit 24
```

The default uses **4 balanced cases**, and makes 12 local Ollama requests (one reference and two ASR transcription conditions per case). The full 24-case run makes 72 local requests. The *global* action catalog is compiled from all 24 scenarios and stays constant in both modes; no per-case gold labels are shown to the model. The experimental action IDs were researcher-specified **after** the fresh-ASR experiment, and have not been independently adjudicated.

The model returns a JSON choice from the shared action catalog or `HOLD`. It cannot call external tools. Every choice is a **symbolic proposal, never a real action**. `v4_review` withholds candidate revisions. `triage_review` additionally requests review for certain uncertain openings. `not_flagged` does **not** imply authorized, safe, or correct.

Results (under `~/Desktop/voxgate-spoken-action-reports`):

- `model_choices.csv` — raw text-model selection and correctness by source.
- `policy_replay.csv` — decisions derived from the **same** model choices (no extra model calls per policy).
- `asr_model_comparisons.csv` — paired model-choice differences for slow/fast vs. reference transcript.
- `summary.json` — proposal/review/incorrect counts and local model digest.

### Scientific limitations

- 24 researcher-constructed, provisionally labeled cases; each is repeated at two speaking rates, yielding **paired** rather than 48 independent linguistic items.
- Action labels are a new exploratory scoring layer and were not preregistered before the speech transcription run.
- The little 0.5B model may struggle to use a large global catalog. Report invalid choices, abstentions, and wrong proposals separately rather than discarding them.
- Text-only Qwen never sees the raw waveform; this **cannot** measure acoustic authority recognition or prosodic agent misalignment.
- Review flags can *suppress* proposals but cannot determine user authorization. A system handling real permissions needs a separate authenticated consent/action-confirmation mechanism, which this lab intentionally does not provide.
- No real action, consent, authorization, tool invocation, deployment, or API billing takes place in this benchmark.
