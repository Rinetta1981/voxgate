# VOXGATE — When Voices Cross AI Safety Boundaries

A research-in-progress Django application exploring how spoken instructions, self-repairs, and social signals might affect AI agents' decisions. It contains two planned modules:

- **WaitWise:** interruption, hesitation, and correction-aware authorization.
- **VoiceRank:** effects of perceived vocal authority on agent permission decisions.

**Research status:** The present software is an early **text-only, rule-based prototype**. It does **not** yet generate speech, call language models, execute agent actions, or demonstrate improvements in AI safety. Do not interpret its classification scores as performance of an AI agent.

## Local setup

Requires Python 3.13 and the packages in `requirements.txt`.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -c 'from pathlib import Path; from django.core.management.utils import get_random_secret_key; p=Path(".secret_key"); p.write_text(get_random_secret_key()) if not p.exists() else None'
python manage.py migrate
python manage.py runserver
```

Visit http://127.0.0.1:8000/ . Never commit `.secret_key`. The current settings are for local development only (`DEBUG=True`); deployment will require separate production settings and environment-based secrets.

## Reproducible WaitWise evaluation

```bash
python evaluate_waitwise.py --output-dir ~/Desktop/voxgate-reports
python -m unittest core.tests -v
```

The evaluation command prints TP, FP, FN, TN, precision, recall, F1, and accuracy for each of three unchanged detector versions across:

- `data/waitwise_cases.csv` — eight original development examples.
- `data/waitwise_challenge.csv` — twelve additional examples whose errors were used to guide V3; **also development data**.
- `data/waitwise_stress.csv` — twenty further researcher-constructed stress cases written after V3 was frozen, useful for identifying new failure modes, **not representative or independently annotated test data**.

Reports are written to `~/Desktop/voxgate-reports/summary.json` and `~/Desktop/voxgate-reports/predictions.csv` when `--output-dir` is specified. Do not tune on stress examples and continue to call them held-out tests; subsequent improvements require another untouched set.

## Research validity limitations

These experiments detect lexical and textual patterns, not acoustic disfluency, timing, social perception, consent, or unauthorized tool use. Annotation labels are provisional and were not independently checked. Reliable claims will require a coding protocol, independent annotators, larger varied datasets, speech synthesis and recordings, controlled agent simulations, multiple model evaluations, and a separately designed held-out test set.

## Roadmap

1. Validate textual instruction-revision detection using independently annotated examples.
2. Implement constrained mock-agent evaluations with no external side effects.
3. Add controlled speech stimuli and matched transcription conditions.
4. Build VoiceRank authority/perceived status experiments with controlled acoustic variables.
5. Measure an authorization/repair-aware action gate against appropriate baselines.
6. Investigate internal representations where technically feasible; release reproducible findings and research manuscripts.
