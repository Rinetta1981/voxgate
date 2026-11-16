# Prototype release checklist

This checklist describes **local research prototype readiness**, not production safety certification.

## Code and routing

- [ ] Verify the GitHub branch and commit that will be cited in research reports.
- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py test core -v 1` and retain the full test output.
- [ ] Visit `/`, `/lab/`, `/voice/`, `/voice/study/`, and `/results/` locally.
- [ ] Verify correct local-only restrictions; never deploy Django `DEBUG=True` to a public host.
- [ ] Check that `.secret_key`, participant CSVs, audio WAV files, model weights, and experiment reports remain untracked.

## Reproducibility

- [ ] Record macOS, CPU, RAM, Python, Django, Ollama model tag + digest, and whisper.cpp model hash/version.
- [ ] Record generator voice, synthesis arguments, audio clip hashes, and playback/recording conditions.
- [ ] Retain exact dataset versions, labeling protocol, randomization and scenario IDs.
- [ ] Document local output directory locations and archive reports separately from code.
- [ ] Describe the difference between the trained/tuned detector and any truly untouched evaluation data.

## Scientific claims

- [ ] Mark exploratory examples as researcher-constructed; distinguish pairs from independent samples.
- [ ] Report TP/FP/FN/TN, precision, recall, F1, and action-coverage trade-offs.
- [ ] Distinguish wrong proposals from executed wrong actions; the simulator executes none.
- [ ] Do not attribute speaking-rate effects to Qwen when its input is transcript text only.
- [ ] Arrange ethics review and consent before collecting external participant data.

## Publication

- [ ] Create an explicit code and asset reuse policy (license/consent restrictions).
- [ ] Prepare a methods-and-limitations report with frozen commit SHA and data provenance.
- [ ] Do not claim direct audio-native authority effects or demonstrated real-world AI-agent safety without experiments that test them.
