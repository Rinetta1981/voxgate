# Free, local-only WaitWise model evaluation

## Purpose and boundaries

This package connects VOXGATE's **existing inert action-selection experiment** to a small language model on **your own Mac**, via Ollama's local server. There is **no paid API**, no cloud model, no real-world tools, and no installation of Python packages. The experimental cases contain fictional instructions and action IDs.

The Python adapter calls **only** `127.0.0.1:11434` using the built-in Python `http.client` module. It refuses model tags ending in `:cloud`; it neither downloads models nor has remote URL settings. You explicitly install the model using Ollama's command-line tool. The model weights download requires an internet connection and disk space, but local inference needs no OpenAI API key.

## One-time setup (macOS, Apple M2, 8 GB RAM)

1. Download and install Ollama for macOS from https://ollama.com/download/mac and open the **Ollama** application. Requires macOS 14 or later.
2. In VOXGATE's existing Terminal 2, run:

   ```bash
   ollama pull qwen2.5:0.5b
   ```

   This explicitly downloads the small **398 MB** Qwen2.5 0.5B model. Downloaded model files and Ollama's cache consume disk space; inference consumes additional RAM. The 0.5B model is a resource-conscious *baseline*, not a high-capability safety model. If the `ollama` command is unavailable, open/restart the Ollama application and a new Terminal window.

3. Install the ZIP **from the project root** (after downloading it to `~/Downloads`):

   ```bash
   cd ~/Desktop/voxgate
   unzip -o ~/Downloads/voxgate_local_model_update.zip
   ```

4. Test **without calling any model**:

   ```bash
   python -m unittest core.tests core.test_agent_simulation core.test_live_agent core.test_local_agent -q
   python local_waitwise_agent.py
   ```

5. Check that the local model is available (**no inference**):

   ```bash
   python local_waitwise_agent.py --check
   ```

6. Run the **first four scenarios** (8 model requests; all local):

   ```bash
   python local_waitwise_agent.py --run-local --limit 4
   ```

The resulting reports are saved to `~/Desktop/voxgate-local-reports/` as `local_llm_summary.json` and `local_llm_decisions.csv`.

## Extending the experiment

Run more locally:

```bash
python local_waitwise_agent.py --run-local --limit 24
```

For a stronger but still compact follow-up baseline (optional, **986 MB** download):

```bash
ollama pull qwen2.5:1.5b
python local_waitwise_agent.py --run-local --model qwen2.5:1.5b --limit 24
```

Report **model name and digest** (automatically in JSON), number of cases, decision coverage, wrong-action rate, correct-completion rate and invalid outputs. Do not compare models unless conditions, catalog and scenario selection are identical.

## Interpretation / limitations

- The 24 cases were created for development. Some originated in detector tuning; they **are not an independently annotated or representative benchmark**.
- The model chooses among 34 globally specified symbolic action IDs or `HOLD`. This is a **closed-world classification task**, not autonomous AI-agent behavior.
- `partial_text` means the first segment of transcript text chosen by a heuristic, **not actual audio streaming, latency or timing**.
- `full_text_plus_v3_gate` is a post-processing hold applied to the same full-text model choice, not a separate model call. A lower wrong-action rate may simply reflect fewer actions completed.
- The model may fail to output correctly structured JSON, especially at only 0.5B parameters. Such outputs are counted as invalid/abstained rather than ignored. Genuine connection errors abort the experiment.
- No speech is generated or transcribed; no voices, speaker status, timing, tool-authorization workflows or mechanistic model internals are tested yet.
- The previously added `live_waitwise_agent.py --live` **still invokes a paid external API**. Do **not** use that command if avoiding charges.

## Useful references

- https://docs.ollama.com/api/chat — local `/api/chat`, JSON output format and non-streaming responses
- https://docs.ollama.com/api/tags — locally installed model list
- https://ollama.com/library/qwen2.5 — model tags and sizes
