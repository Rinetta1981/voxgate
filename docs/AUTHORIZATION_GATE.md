# Authorization-aware research gate: retrospective comparison

This package replays policies against the **model outputs already saved** by the
balanced local experiment. It requires no model calls, no cloud API, and no new
Python packages. No fictional action is actually executed.

## Run on your Mac

From `~/Desktop/voxgate`, with its virtual environment active:

```bash
python -m unittest core.tests core.test_agent_simulation core.test_live_agent core.test_local_agent core.test_experiment_design core.test_authorization_gate -q
python audit_authorization_gate.py
```

The CLI expects `~/Desktop/voxgate-balanced-reports/balanced_decisions.csv` and
writes `gate_summary.json` and `gate_decisions.csv` under
`~/Desktop/voxgate-gate-reports`. Change paths with `--input` or `--output-dir`.

## Conditions

- **full_text**: original unprotected full-transcript model choice.
- **v3_gate**: existing lexical/discourse detector holds flagged revisions.
- **disagreement_gate**: wait until the speaker finishes; hold if initial and
  final model selections disagree or either output was invalid/abstained.
- **combined_gate**: hold if either V3 flags or the model selections disagree.

A hold is *not* a successful completion. The gate does not know the speaker's
true intention and cannot safely release a held action without an independent
review/confirmation step. The included `InertConfirmationQueue` demonstrates a
one-use, exact-match approval handshake but does not ask users to confirm or
execute actions. Test it in the offline test suite.

### Scientific caveats

This is a **retrospective, exploratory replay** on researcher-constructed cases
already used in development. The gate can use the first and last model choices
only because the evaluation saved both; a real deployment must wait for the end
of the utterance and never execute the initial action. Condition labels use only
model outputs and V3 flags, not gold case labels. Gold labels are used *only to
score* output. Changes in model response across runs may be nondeterministic.

Rates among executed choices are reported as undefined if no choices execute.
Any observed difference is only a diagnostic for this toy task, **not** a
measured reduction in real-world risk, nor evidence of genuine user authorization.
Future work requires a live two-turn confirmation protocol, speech inputs,
independent annotation and larger held-out samples.
