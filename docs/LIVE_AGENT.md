# Batch 3 — LLM-based WaitWise action selection, with inert tools

## What this adds

- A Python-only, opt-in **OpenAI Responses API** adapter, with API key taken from the `OPENAI_API_KEY` environment variable (never from a committed file).
- A **global, fixed action catalog** assembled from all 24 existing mock scenarios. Every action is an inert symbolic label. The model never receives per-case annotations, gold labels, initial action IDs or final action IDs as privileged metadata.
- A strict parser: a model response is either `{"action_id":"one_of_the_global_actions"}` or `{"action_id":"HOLD"}`. Malformed or out-of-catalog responses result in a recorded hold, never execution.
- Three comparison conditions: model choosing from an initial *text fragment*; model choosing from the full transcript; and that same full-transcript choice filtered by the frozen WaitWise V3 detector.
- Regression tests, offline preview and CSV/JSON experiment reports.

**Important:** The tool executor is deliberately *inert*. It logs action ID selections without connecting to real email, booking, file, bank or calendar services. `partial_text` means a heuristic split at a punctuation/conjunction boundary, **not real-time streaming or measured speech latency**.

## Step 1 — offline verification (FREE, no key or internet needed)

From Terminal 2 at the VOXGATE project root:

```bash
python -m unittest core.tests core.test_agent_simulation core.test_live_agent -v
python live_waitwise_agent.py
```

The second command only previews the first text fragment, catalog size, and prompt keys. **No API requests** occur without `--live`.

## Step 2 — optional, explicitly paid live-model comparison

You need an independently provisioned OpenAI API key with API billing or credit; **ChatGPT subscription access alone is not an API key**. Never paste your key into a chat, a GitHub file, or experiment output.

In Terminal 2, a temporary key for the active shell can be entered (not in a version-controlled file):

```bash
read -s -p 'OpenAI API key: ' OPENAI_API_KEY; echo; export OPENAI_API_KEY
python live_waitwise_agent.py --live --model gpt-4.1-mini --limit 4
unset OPENAI_API_KEY
```

On some bash configurations, paste the key when prompted and press Return; it will not be displayed. This sends **8 requests** (2 for each of 4 cases). The API may charge for tokens. If your account does not have access to that model, rerun with an available model ID. The request endpoint is fixed at `https://api.openai.com/v1/responses`, and `store:false` is set. Each request sends the synthetic transcript and the complete, global catalog of action IDs.

The default output directory is `~/Desktop/voxgate-live-reports` with:

- `llm_summary.json` — coverage, wrong-action rates, correct completion, and invalid outputs by condition.
- `llm_decisions.csv` — per-case choices and evaluation labels.

**A failed HTTP request aborts**: it is not counted as a legitimate hold. No local API key is written to disk or report files.

## Experimental caveats

1. These scenarios were researcher-constructed and many were used in detector development. They cannot establish generalization.
2. The action catalog encodes the possible intended outcomes across all scenarios. The real model is therefore doing **closed-world action selection**, not unconstrained tool use; this is a useful intermediate test but can overstate ability.
3. `full_text_plus_v3_gate` is a post-filter on the same model response, not an independent model call. The gate can reduce errors simply by increasing abstentions; report correct completion **and** coverage.
4. Speech production, audio streaming, interruption timing, autonomous tool calls, user confirmation, high-stakes approvals, fairness/accent evaluation and deployment all require separate experiments.
5. The code is intentionally not part of the public Django request path and has no real side-effect-capable tools.
6. This is **not** a full model red-team, nor evidence of unauthorized real-world action.

## Next

Collect independently annotated examples and introduce genuine timed audio chunks and ASR outputs. Measure model choices under matched voices/registers and evaluate a confirmation-based gate. Only then consider a carefully controlled agent API with reversible or read-only tools.
