"""Offline audit of saved 24-case spoken-action experiment (no model calls).

    python audit_spoken_action_results.py
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from core.spoken_action_audit import analyze, read_csv, render_markdown

DEFAULT_SOURCE = Path.home() / 'Desktop' / 'voxgate-spoken-action-reports'
DEFAULT_DESTINATION = Path.home() / 'Desktop' / 'voxgate-spoken-action-audit'


def save_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f'No rows to save: {path}')
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    try:
        if args.source_dir.resolve() == args.output_dir.resolve():
            raise ValueError('Output must be a different directory from original model results')
        analysis = analyze(
            read_csv(args.source_dir / 'model_choices.csv'),
            read_csv(args.source_dir / 'policy_replay.csv'),
            read_csv(args.source_dir / 'asr_model_comparisons.csv'),
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        save_rows(args.output_dir / 'policy_by_group.csv', analysis['policy_metrics'])
        save_rows(args.output_dir / 'paired_transitions.csv', analysis['paired_rows'])
        (args.output_dir / 'spoken_action_audit.md').write_text(render_markdown(analysis), encoding='utf-8')
        (args.output_dir / 'audit_summary.json').write_text(json.dumps({
            'n_cases': analysis['n_cases'],
            'n_paired_comparisons': analysis['n_paired_comparisons'],
            'n_model_changes': len(analysis['changed_rows']),
            'changed_cases': [{'case_id': r['case_id'], 'source': r['source'], 'transition': r['transition']}
                              for r in analysis['changed_rows']],
            'transition_counts': analysis['transition_counts'],
            'scope': 'Descriptive audit of symbolic Qwen proposals, not authorization or direct audio modeling',
        }, indent=2) + '\n', encoding='utf-8')
        print(f"PAIRED SPOKEN-ACTION AUDIT — {analysis['n_cases']} scenarios, {analysis['n_paired_comparisons']} comparisons")
        print(f"Model choice changed: {len(analysis['changed_rows'])}/{analysis['n_paired_comparisons']}")
        for r in analysis['changed_rows']:
            print(f"  {r['case_id']}/{r['source']}: {r['transition']} | {r['reference_choice']} -> {r['asr_choice']}")
        print('\nPolicy         Source       Group       Proposed Correct Wrong Held')
        for r in analysis['policy_metrics']:
            if r['group'] == 'all':
                print(f"{r['policy']:<14} {r['source']:<12} {r['group']:<10} {r['proposed']:>3}/{r['n']}  {r['correct']:>5} {r['wrong']:>5} {r['held']:>4}")
        print(f"\nFour audit files saved: {args.output_dir}")
        print('No inference, API, download, or action execution. Researcher-constructed pilot only.')
        return 0
    except (OSError, ValueError, KeyError) as e:
        print(f'Audit stopped: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
