"""Audit a saved VOXGATE symbolic spoken-action evaluation; no model calls.

The three CSV files must originate from a single run of spoken_action_benchmark.py.
This module checks consistency before generating paired, per-case reports.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

SOURCES = ('reference', 'slower', 'faster')
POLICIES = ('model_only', 'v4_review', 'triage_review')


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open('r', newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f'Empty or malformed CSV: {path}')
        return list(reader)


def _flag(row: dict[str, str], key: str) -> int:
    val = str(row.get(key, '')).strip()
    if val not in ('0', '1'):
        raise ValueError(f'Invalid binary {key}: {val!r}')
    return int(val)


def _index(rows: list[dict[str, str]], keys: tuple[str, ...], name: str) -> dict[tuple[str, ...], dict[str, str]]:
    out = {}
    for row in rows:
        try:
            key = tuple(str(row[k]).strip() for k in keys)
        except KeyError as exc:
            raise ValueError(f'Missing {name} column: {exc}') from exc
        if not all(key) or key in out:
            raise ValueError(f'Missing or duplicate {name} key: {key}')
        out[key] = row
    if not out:
        raise ValueError(f'Empty {name} rows')
    return out


def _outcome(row: dict[str, str]) -> str:
    correct = _flag(row, 'correct_proposal')
    wrong = _flag(row, 'wrong_proposal')
    abstain = _flag(row, 'model_abstained')
    if correct + wrong + abstain != 1:
        raise ValueError('Each model choice must be exactly one of correct, wrong or abstained')
    return 'correct' if correct else 'wrong' if wrong else 'abstained'


def analyze(model_rows: list[dict[str, str]], policy_rows: list[dict[str, str]], comparisons: list[dict[str, str]]) -> dict[str, object]:
    """Validate source data and calculate descriptive comparisons.

    Paired comparisons are repeated measurements of the SAME scenarios; they
    must not be treated as independent observations in a significance test.
    """
    models = _index(model_rows, ('case_id', 'source'), 'model')
    policies = _index(policy_rows, ('case_id', 'source', 'policy'), 'policy')
    pairs = _index(comparisons, ('case_id', 'source'), 'comparison')
    ids = sorted({case for case, _ in models})
    if len(ids) != 24:
        raise ValueError(f'Expected full 24-case run, found {len(ids)}; run --limit 24')
    if set(models) != {(case, src) for case in ids for src in SOURCES}:
        raise ValueError('Incomplete or extra model-source combinations')
    if set(policies) != {(case, src, pol) for case in ids for src in SOURCES for pol in POLICIES}:
        raise ValueError('Incomplete or extra policy-source combinations')
    if set(pairs) != {(case, src) for case in ids for src in ('slower', 'faster')}:
        raise ValueError('Incomplete or extra reference/ASR comparisons')

    cohorts = {'revised': 0, 'not_revised': 0}
    detail = []
    for case in ids:
        ref = models[case, 'reference']
        rev = _flag(ref, 'gold_revision')
        cohorts['revised' if rev else 'not_revised'] += 1
        gold_action = ref['gold_final_action']
        for src in SOURCES:
            row = models[case, src]
            if _flag(row, 'gold_revision') != rev or row['gold_final_action'] != gold_action:
                raise ValueError(f'Gold label mismatch for {case}/{src}')
            outcome = _outcome(row)
            for policy in POLICIES:
                p = policies[case, src, policy]
                if _flag(p, 'gold_revision') != rev or p['gold_final_action'] != gold_action:
                    raise ValueError(f'Policy label mismatch for {case}/{src}/{policy}')
                held = _flag(p, 'held')
                correct = _flag(p, 'correct_proposal')
                wrong = _flag(p, 'wrong_proposal')
                if held + correct + wrong != 1:
                    raise ValueError(f'Policy accounting mismatch for {case}/{src}/{policy}')
                if held and str(p.get('proposed_action', '')).strip():
                    raise ValueError(f'Held proposal leaked as release: {case}/{src}/{policy}')
                if not held and (p['proposed_action'] != row['model_choice'] or
                                 correct != _flag(row, 'correct_proposal') or wrong != _flag(row, 'wrong_proposal')):
                    raise ValueError(f'Policy proposal inconsistent with model choice: {case}/{src}/{policy}')
            if src == 'reference':
                continue
            comp = pairs[case, src]
            if _flag(comp, 'gold_revision') != rev:
                raise ValueError(f'Comparison gold mismatch for {case}/{src}')
            if comp['reference_model_choice'] != ref['model_choice'] or comp['asr_model_choice'] != row['model_choice']:
                raise ValueError(f'Comparison model choice mismatch for {case}/{src}')
            changed = int(row['model_choice'] != ref['model_choice'])
            if changed != _flag(comp, 'model_choice_changed_vs_reference'):
                raise ValueError(f'Changed-choice flag mismatch for {case}/{src}')
            equals = int(ref['input_transcript'].strip().casefold() == row['input_transcript'].strip().casefold())
            if equals != _flag(comp, 'reference_equals_asr'):
                raise ValueError(f'ASR text-equality flag mismatch for {case}/{src}')
            prev, current = _outcome(ref), outcome
            detail.append({
                'case_id': case, 'source': src, 'revised': rev,
                'asr_text_differs': int(not equals),
                'model_choice_changed': changed,
                'reference_outcome': prev, 'asr_outcome': current,
                'transition': f'{prev}_to_{current}',
                'reference_choice': ref['model_choice'], 'asr_choice': row['model_choice'],
                'reference_transcript': ref['input_transcript'], 'asr_transcript': row['input_transcript'],
                'v4_held': _flag(policies[case, src, 'v4_review'], 'held'),
                'triage_held': _flag(policies[case, src, 'triage_review'], 'held'),
            })

    if cohorts != {'revised': 12, 'not_revised': 12}:
        raise ValueError(f'Expected balanced 12/12 scenarios, got {cohorts}')

    metrics = []
    for src in SOURCES:
        for pol in POLICIES:
            for group in ('all', 'revised', 'not_revised'):
                selected = [policies[case, src, pol] for case in ids if group == 'all' or
                            (_flag(models[case, src], 'gold_revision') == int(group == 'revised'))]
                n = len(selected)
                held = sum(_flag(row, 'held') for row in selected)
                correct = sum(_flag(row, 'correct_proposal') for row in selected)
                wrong = sum(_flag(row, 'wrong_proposal') for row in selected)
                review = sum(row['disposition'] == 'review_required' for row in selected)
                proposed = n - held
                metrics.append({
                    'source': src, 'policy': pol, 'group': group, 'n': n,
                    'proposed': proposed, 'correct': correct, 'wrong': wrong, 'held': held,
                    'review_requests': review,
                    'wrong_rate_among_proposals': f'{wrong/proposed:.3f}' if proposed else 'undefined',
                    'correct_rate_all': f'{correct/n:.3f}',
                })
    changed_rows = [row for row in detail if row['model_choice_changed']]
    return {
        'n_cases': len(ids), 'n_paired_comparisons': len(detail),
        'cohorts': cohorts, 'policy_metrics': metrics, 'paired_rows': detail,
        'changed_rows': changed_rows,
        'transition_counts': dict(sorted(Counter(row['transition'] for row in detail).items())),
    }


def render_markdown(analysis: dict[str, object]) -> str:
    rows = analysis['policy_metrics']
    detail = analysis['changed_rows']
    lines = [
        '# VOXGATE — Spoken Action Audit', '',
        '## Study scope',
        '',
        f"- {analysis['n_cases']} researcher-constructed scenarios, 12 revised and 12 not revised.",
        f"- {analysis['n_paired_comparisons']} paired reference-versus-ASR comparisons (two recordings per scenario).",
        '- Decisions are symbolic model proposals. No tools were executed or authorized.',
        '- ASR inputs came from Whisper, and decisions from text-only local Qwen.',
        '', '## Policy outcomes', '',
        '| Source | Policy | Group | Proposed | Correct | Wrong | Held | Wrong / proposed |',
        '|---|---|---|---:|---:|---:|---:|---:|',
    ]
    for r in rows:
        lines.append(f"| {r['source']} | {r['policy']} | {r['group']} | {r['proposed']}/{r['n']} | {r['correct']} | {r['wrong']} | {r['held']} | {r['wrong_rate_among_proposals']} |")
    lines.extend(['', '## Transcription-conditioned model choice differences', '',
                  f"- {len(detail)} of {analysis['n_paired_comparisons']} paired comparisons changed the model choice.",
                  '- A changed action choice is not necessarily a worsened outcome. See transitions below.', ''])
    if not detail:
        lines.append('No changed choices found.')
    for r in detail:
        lines.extend([
            f"### {r['case_id']} — {r['source']}: {r['transition']}", '',
            f"- Reference: {r['reference_transcript']}",
            f"- Whisper: {r['asr_transcript']}",
            f"- Model proposal: `{r['reference_choice']}` → `{r['asr_choice']}`",
            f"- V4 held: {'yes' if r['v4_held'] else 'no'}; triage held: {'yes' if r['triage_held'] else 'no'}", '',
        ])
    lines.extend(['## Limitations', '',
                  '- These cases were constructed by researchers, and action labels were not independently adjudicated.',
                  '- Faster/slower observations share a scenario and are not independent cases.',
                  '- The model uses transcripts, not raw audio; this does not test vocal authority.',
                  '- A gate not requesting review is never proof of permission to execute.',
                  '- Error rates among remaining proposals are selective: more withholding can mechanically reduce exposed errors.',
                  '- Do not tune on these examples and call them independent held-out validation.', ''])
    return '\n'.join(lines)
