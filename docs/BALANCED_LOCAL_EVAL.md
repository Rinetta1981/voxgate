# WaitWise — balanced local-model pilot

## Why this update exists

The previous `python local_waitwise_agent.py --run-local --limit 4` selected **AG01–AG04**, and **all four are revised instructions**. V3 was designed to hold such cases, so observing 0% gate coverage on these four **cannot** establish that it would withhold every legitimate action. This update corrects that sampling problem without changing the detector, prompts, model, action list, or historical results.

## Install

Unzip this update into the existing `~/Desktop/voxgate` project. It only **adds** `core/experiment_design.py`, `core/test_experiment_design.py`, `balanced_local_waitwise_agent.py` and this document. It will not overwrite earlier reports.

```bash
cd ~/Desktop/voxgate
unzip -o ~/Downloads/voxgate_balanced_local_update.zip
python -m unittest core.tests core.test_agent_simulation core.test_live_agent core.test_local_agent core.test_experiment_design -q
python balanced_local_waitwise_agent.py
python balanced_local_waitwise_agent.py --run-local --limit 8
```

The preview has **no model calls**. The `--run-local` option explicitly calls the already-installed model through Ollama at `127.0.0.1:11434`. An eight-scenario experiment requires 16 local inference calls (partial and full); the gate reuses the full-text answer.

For the full 24 researcher-constructed scenarios:

```bash
python balanced_local_waitwise_agent.py --run-local --limit 24
```

Optional alternate local model (only **after** separately downloading it with Ollama):

```bash
python balanced_local_waitwise_agent.py --run-local --model qwen2.5:1.5b --limit 8 --output-dir ~/Desktop/voxgate-balanced-1p5b
```

No paid API, cloud-model tag, API key, true tool execution, audio, recording, or other remote requests are initiated by this script. Running a locally installed model consumes RAM/CPU/battery but no usage-based API fee.

## Design

- Labels are used only to stratify case sampling and score outcomes. No `gold_action`, `revised`, `discourse_function`, or case ID is provided to the model.
- Sample is deterministically ordered by SHA-256 hash of the fixed seed and case ID; equal revised and non-revised examples are interleaved. `--seed` changes the sample, `--limit` must be even, 2 through 24.
- All model conditions see the **same 34 global symbolic action IDs** irrespective of selection; the gate receives exactly the full-text model decision with a V3 hold post-processing step.
- `full_text_plus_v3_gate` and `full_text` share a model output, not two independently sampled outputs.
- Reports are written by default to `~/Desktop/voxgate-balanced-reports/balanced_summary.json` and `balanced_decisions.csv`.

## Interpretation

- **Coverage**: fraction of scenarios resulting in a symbolic action selection rather than `HOLD`.
- **Wrong/all**: fraction of all cases with an incorrect action selection; can decrease trivially when a gate withholds most actions.
- **Correct completion/all**: fraction of all cases with a correctly selected symbolic action. This measures utility as well as safety.
- Report results separately for true revised and true non-revised groups. Low gate coverage in true revised cases can be an intentional conservative policy rather than a false alarm. `wrong_rate_executed` is **undefined** (JSON `null`) when no actions were selected, never '0% safe'.
- Neither 'partial_text' nor 'full_text' reflects real-time audio streaming. None of these simulations demonstrates safety or permission handling by real deployed agents.
- These are **researcher-constructed, previously inspected cases**, not an independent sample or publishable causal estimate. The pilot supports pipeline debugging only. Larger independent annotation and prospective evaluation are essential.
- Performance of `qwen2.5:0.5b` with a 34-action catalog may be severely limited by model capability or prompt grounding; do not attribute all failure to repair detection.

## Next substantive study

Evaluate whether a **confirmation-mediated release** can preserve action completion while preventing actions not explicitly authorized. This requires a *separate participant confirmation signal*, not a fabricated 'yes' inferred from gold labels. Also improve model-to-action semantic grounding and evaluate a more capable local model where feasible.
