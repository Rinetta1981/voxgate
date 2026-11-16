# VOXGATE — When Voices Cross AI Safety Boundaries

VOXGATE is an **experimental, locally run AI safety research platform** for studying the relationship between speech, instruction revisions, perceived vocal authority, and simulated AI-agent action selection.

It combines two research tracks:

- **WaitWise:** Detects possible changes to spoken instructions and examines when a proposed action should be withheld for review.
- **VoiceRank:** Studies how controlled speech-rate variations affect human ratings of authority, clarity and urgency, and how speech recognition may affect downstream text-model decisions.

**Research status (November 2026):** Functional local research prototype, **not** a validated safety product or publicly deployable service. Its experiments include synthetic speech, on-device speech recognition, and optional local Qwen text-model inference. It does not directly test vocal authority in an audio-native AI model. The agent-action catalog is symbolic: no emails, bookings, transfers, deletions or other external actions are performed.

## What works

| Area | Available functionality | Main limitation |
|---|---|---|
| WaitWise | V1–V4 rule-based repair detectors, benchmarks, error analysis | Heuristic detection is not evidence of speaker authorization |
| Agent evaluation | Mock policies, local Qwen symbolic action proposals, review-gate comparisons | Small model, constructed scenarios; no real tools |
| Speech | Local synthesized WAV stimuli, acoustic audit, whisper.cpp transcription | Speech recognition loses acoustic information for downstream text-only Qwen |
| VoiceRank | Listening pilot and counterbalanced expanded study with CSV export | Human perception pilot; direct audio-model permission tests not implemented |
| Web application | Django home page, authorization lab, listening study, results dashboard | Local development only; not secured for public deployment |

## Run locally (macOS)

Python **3.13** is used in the existing development environment. From the repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -c 'from pathlib import Path; from django.core.management.utils import get_random_secret_key; p=Path(".secret_key"); p.write_text(get_random_secret_key()) if not p.exists() else None'
python manage.py migrate
python manage.py runserver
```

The generated `.secret_key` is private and excluded by `.gitignore`. The Django configuration is a **development** configuration (`DEBUG=True`), not production-ready.

Open these local pages:

- Home: http://127.0.0.1:8000/
- WaitWise authorization review: http://127.0.0.1:8000/lab/
- VoiceRank pilot: http://127.0.0.1:8000/voice/
- VoiceRank expanded study: http://127.0.0.1:8000/voice/study/
- Saved research results: http://127.0.0.1:8000/results/

Some interfaces require locally generated stimulus files or prior saved experimental reports; they will indicate when those resources are absent. Do not expose the development server on a public network.

## Free, optional local model and audio dependencies

The existing experiments have used **Ollama** with the `qwen2.5:0.5b` text model and **whisper.cpp** with the `ggml-tiny.en.bin` model. Install these separately on your Mac; they are not included in the Git repository.

```bash
ollama pull qwen2.5:0.5b
brew install whisper.cpp
```

`whisper-cli` must be on your `PATH` for speech-recognition benchmarks. Some audio generation commands also rely on macOS speech synthesis tools. See `docs/LOCAL_MODELS.md`, `docs/VOICERANK_SPEECH_ASR.md`, and the relevant experiment documentation for full requirements and setup.

Running the documented local workflows does not require paid cloud APIs. `live_waitwise_agent.py` is an **optional** separate API-backed path; do not run it with `--live` if you want to avoid API charges.

## Tests and representative evaluation commands

From the repository root with the virtual environment active:

```bash
python manage.py test core -v 1
python evaluate_waitwise.py --output-dir ~/Desktop/voxgate-reports
python audit_spoken_action_results.py
```

Other research workflows require locally generated data. Examples, after the prerequisites described in `docs/` are complete:

```bash
python generate_voicerank_stimuli.py --check
python audit_voicerank_audio.py
python voicerank_speech_benchmark.py --run-asr
python compare_spoken_repair_v4.py
python spoken_action_benchmark.py --run-local --limit 24
```

Each command has its own input requirements. The 24-case spoken-action benchmark uses a constructed action catalog and on-device inference; it does **not** execute actual actions.

## Selected exploratory findings

The following are **descriptive, researcher-constructed pilot results**; neither labels nor samples have undergone independent validation.

- On 24 constructed speech scenarios, recorded at two speaking rates, WaitWise V4 detected **23/24** positive revision recordings with **0** false positives among 24 negative recordings. These 48 observations represent **24 paired scenarios**, not 48 independent language examples. V4 had been tuned on earlier researcher-constructed material.
- In a 24-scenario local Qwen experiment using **reference transcripts**, model-only symbolic action proposals were **10 correct / 14 wrong**; V4 review retained **8 correct / 4 wrong**, while holding **12**. Fewer exposed wrong proposals came with less action coverage.
- Whisper-related changes altered Qwen's action choice in **3/48** paired transcript comparisons: two wrong-to-correct changes and one correct-to-wrong change.
- The original VoiceRank listening pilots were completed by **one listener**; they do not establish population-level effects or causation beyond the narrow within-stimulus comparison.

These figures are neither evidence of reliable authorization enforcement nor proof that an audio-capable model responds to vocal authority.

## Scientific integrity and privacy

- All simulated actions are non-operative. **A model's output is not permission to execute an action.**
- The gate's hold/review decision is not equivalent to user confirmation or authorization.
- Speech stimuli were synthesized for controlled local studies. Participation by independent listeners requires an appropriate ethics and consent framework.
- Publicly committing a codebase does not automatically publish participants' CSV exports, WAV files, local model weights, API credentials, or keys. Keep those outside the repository and review all staged changes before every push.
- The fresh constructed benchmarks are not a substitute for representative, independently annotated held-out evaluations.
- There is no current mechanism-level or audio-native vocal-authority result; both are future work.

## Research and implementation notes

The `docs/` folder includes experiment setup, evaluation methodology and limitations. Key starting points:

- `docs/LOCAL_MODELS.md`
- `docs/VOICERANK_EXPANDED.md`
- `docs/SPOKEN_REPAIR_FRESH.md`
- `docs/SPOKEN_ACTION_AUDIT.md`
- `docs/RESULTS_DASHBOARD.md`

## Next milestones

1. Confirm reproducible local installation and Django route coverage from a fresh checkout.
2. Record model, stimuli and dataset provenance; review pilot findings for a technical research report.
3. Obtain appropriately consented independent annotations and listener judgments.
4. Compare stronger local text models, then study audio-native decision-making with suitable controls.
5. Add formal controls for confirmation/authorization, evaluate accuracy-versus-coverage, and document a threat model.
6. Prepare a research preprint describing methods, results, limitations and reproducible artifacts.

**License:** No license is asserted here. Add an explicit project license only after deciding how the code and research assets should be reused.
