# WaitWise mock-agent policy study (Batch 2)

## Purpose and boundaries

This is an **offline counterfactual simulator** of abstract authorization policies. It does **not** invoke actual LLMs, generate or recognize speech, send emails, book tickets, transfer files, manipulate external systems, or prove a deployable AI safety improvement.

The dataset is a set of **24 researcher-constructed scenarios** (12 with revisions and 12 without). Some are reused or adapted from the examples examined while developing WaitWise V3. The labels and abstract action IDs are supplied by the researcher; they are **not** predictions of the AI model. These data are **not** independently annotated, representative, or held out.

## Two abstract moments

- At **0 ms**, an initial action request is available (the corresponding `initial_action` ID is a controlled annotation).
- At **2000 ms**, the complete transcript has become available (a fixed illustrative timeline, not measured speech timing).

No code attempts to reconstruct the intended corrected action from speech. The gold `final_action` ID is available **only** to the evaluator and to an explicitly unattainable oracle comparator.

## Five policy comparisons

| Policy | Simulated behavior | Main limitation |
| --- | --- | --- |
| `immediate` | Commits initial action at 0 ms | Defined to be premature; cannot undo it when revisions follow |
| `turn_end` | Commits original action after utterance completion | Ignores subsequent corrections |
| `repair_gate` | Applies unchanged WaitWise V3 to complete transcript; holds if revision detected, otherwise commits original action | May miss corrections; detects but cannot resolve corrections; holding is not completing the task |
| `confirmation_gate` | Holds every case pending explicit confirmation | Confirmation step is absent from dataset, so completion coverage is zero |
| `oracle_final` | Commits researcher-supplied gold final action at turn end | **Unattainable upper bound**, not a deployable model |

`premature_action_rate_all_cases` is partly a consequence of each policy's timing definition; it is not an empirical measurement of real-world latency. `wrong_action_rate_all_cases` counts execution of an action ID different from the annotated final action. It is **not** automatically a real-world unauthorized-action rate. `action_coverage` measures whether any action is committed; a held case is not considered successfully completed.

## Run inside VOXGATE project root

```bash
python -m unittest core.tests core.test_agent_simulation -v
python simulate_waitwise_agent.py --output-dir ~/Desktop/voxgate-agent-reports
```

The script prints one row for each policy and the V3 confusion matrix, and saves:

- `~/Desktop/voxgate-agent-reports/policy_summary.json`
- `~/Desktop/voxgate-agent-reports/simulated_decisions.csv`

Neither command performs any real external operation. The model has only symbolic actions and deterministic policies.

## Next research steps

1. Specify a prospectively written, independently annotated instruction/repair corpus with real timing boundaries, including speech transcriptions and ambiguity categories.
2. Introduce an **executable but sandboxed mock tool API** and an agent that must infer final actions itself; do not give its action selector any gold targets.
3. Separate **premature execution**, **wrong final action**, **wrong permission**, **unnecessary hold**, and **successful completion**. Include standard action/latency baselines and statistical uncertainty.
4. Independently evaluate across voices, registers, social status cues, languages, ASR quality and interaction settings, following ethics/privacy safeguards.
5. Require confirmation or reversible staging for consequential external actions; compare trade-offs transparently. Do not deploy `DEBUG=True` Django settings or connect irreversible tools without safeguards.
