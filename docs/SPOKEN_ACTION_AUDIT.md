# VOXGATE — Paired speech-to-action audit

## What this adds

This update creates a **descriptive, zero-inference research report** from the CSV results of the existing full experiment (`spoken_action_benchmark.py --run-local --limit 24`). It makes no network requests, does not rerun Whisper or Qwen, and cannot execute symbolic actions. It uses Python's standard library only.

## Running it

```bash
python -m unittest core.test_spoken_action_audit -q
python audit_spoken_action_results.py
```

Reads from `~/Desktop/voxgate-spoken-action-reports` (three existing CSV files):

- `model_choices.csv`: action choices for reference transcripts and two ASR variants.
- `policy_replay.csv`: same model choices under three *review* policies.
- `asr_model_comparisons.csv`: pairs speech-derived model choices with the reference choice.

Writes a *separate* folder `~/Desktop/voxgate-spoken-action-audit`:

- `spoken_action_audit.md`: human-readable methods/results summary and the changed cases.
- `policy_by_group.csv`: counts by speaking-rate source, policy, and genuine/non-revision group.
- `paired_transitions.csv`: the paired change/outcome of each of 48 source comparisons.
- `audit_summary.json`: machine-readable counts of changed cases and outcomes.

The existing experiment reports and audio recordings are not altered.

## How to read it

- **Proposed** means a symbolic selection passed the review filter; it is *not* execution or authorization.
- **Wrong/proposed** measures the fraction of the *unheld* selected actions that disagree with provisional gold action labels. A lower value after withholding is not necessarily better model accuracy.
- **Held** means a review is requested or the model abstains.
- **Reference → slower/faster** comparisons are *paired* within cases. There are only 24 unique sentence scenarios, not 72 independent cases.
- A change in model choice need not be a change in correctness; the report labels each transition (e.g. `wrong_to_correct` or `correct_to_wrong`).
- If the same textual input is generated with different speaking rates, text-only Qwen cannot directly perceive that variation. Differences observed here are mediated through transcription and possible model-output variability.

## Known limitations

The experiment uses synthetic speech, selected researcher-written sentences, researcher-provisional labels, and small local models. Neither a real-world action safety improvement nor direct vocal-authority sensitivity is demonstrated. A stronger study should predefine risk and utility endpoints; collect independent annotations; include repeated model runs to estimate sampling variability; add natural speech with speakers and prosody controls; and evaluate an audio-conditioned model separately from the speech-to-text route. Always require explicit authorized confirmation before connecting real tools.
