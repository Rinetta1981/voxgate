"""Tests for the read-only research-report parser (no Django required)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from core.results_dashboard import AuditReadError, GROUPS, POLICIES, SOURCES, load_dashboard
from install_results_dashboard import install


# Self-contained artificial fixture: numbers are intentionally not real results.
def make_fixture(root: Path) -> None:
    summary = {
        "n_cases": 24, "n_paired_comparisons": 48, "n_model_changes": 3,
        "changed_cases": [
            {"case_id": "NR01", "source": "slower", "transition": "wrong_to_correct"},
            {"case_id": "NR01", "source": "faster", "transition": "wrong_to_correct"},
            {"case_id": "NR23", "source": "faster", "transition": "correct_to_wrong"},
        ],
    }
    (root / "audit_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    target = root / "policy_by_group.csv"
    with target.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["source", "policy", "group", "n", "proposed", "correct", "wrong", "held", "review_requests"])
        writer.writeheader()
        for s in SOURCES:
            for p in POLICIES:
                if p == "model_only":
                    revised = dict(n=12, proposed=12, correct=2, wrong=10, held=0, review_requests=0)
                    unrevised = dict(n=12, proposed=12, correct=8, wrong=4, held=0, review_requests=0)
                else:
                    revised = dict(n=12, proposed=0, correct=0, wrong=0, held=12, review_requests=12)
                    unrevised = dict(n=12, proposed=12, correct=8, wrong=4, held=0, review_requests=0)
                all_data = {k: revised[k] + unrevised[k] for k in revised}
                for group, data in (("all", all_data), ("revised", revised), ("not_revised", unrevised)):
                    writer.writerow({"source": s, "policy": p, "group": group, **data})


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        make_fixture(self.root)

    def test_complete_fixture(self):
        result = load_dashboard(self.root)
        self.assertEqual(len(result["overview"]), 9)
        self.assertEqual(len(result["breakdown"]), 18)
        self.assertEqual(result["summary"]["changes"], 3)
        self.assertEqual(result["summary"]["improvements"], 2)
        self.assertEqual(result["summary"]["regressions"], 1)

    def test_nonzero_denominator_percent(self):
        rows = load_dashboard(self.root)["overview"]
        model = next(r for r in rows if r["source"] == "reference" and r["policy"] == "model_only")
        self.assertEqual(model["wrong_percent"], "58.3%")
        self.assertEqual(model["completion_percent"], "41.7%")

    def test_missing_file_fails_gracefully(self):
        (self.root / "audit_summary.json").unlink()
        with self.assertRaisesRegex(AuditReadError, "Missing audit_summary.json"):
            load_dashboard(self.root)

    def test_malformed_summary(self):
        (self.root / "audit_summary.json").write_text("{invalid", encoding="utf-8")
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_inconsistent_summary(self):
        path = self.root / "audit_summary.json"
        doc = json.loads(path.read_text())
        doc["n_model_changes"] = 5
        path.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_inconsistent_policy_count(self):
        path = self.root / "policy_by_group.csv"
        text = path.read_text()
        path.write_text(text.replace("reference,model_only,all,24,24,10,14,0,0", "reference,model_only,all,24,24,10,13,0,0"), encoding="utf-8")
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_duplicate_metric_combination_rejected(self):
        path = self.root / "policy_by_group.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join([*lines, lines[-1], ""]), encoding="utf-8")
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_symlink_not_followed(self):
        path = self.root / "audit_summary.json"
        other = self.root / "legitimate.json"
        path.replace(other)
        path.symlink_to(other)
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_missing_groups_rejected(self):
        path = self.root / "policy_by_group.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        with self.assertRaises(AuditReadError):
            load_dashboard(self.root)

    def test_zero_proposal_rate_is_undefined(self):
        rows = load_dashboard(self.root)["breakdown"]
        held = next(r for r in rows if r["group"] == "revised" and r["policy"] == "v4_review")
        self.assertEqual(held["wrong_percent"], "Undefined")

    def test_url_installer_is_idempotent_and_preserves_routes(self):
        urls = self.root / "urls.py"
        urls.write_text('from django.urls import path\nurlpatterns = [path("existing/", lambda request: None)]\n', encoding="utf-8")
        first = install(urls)
        original = urls.read_text()
        self.assertIn("Results route installed", first)
        self.assertIn('path("existing/"', original)
        self.assertIn('path("results/"', original)
        self.assertIn("already installed", install(urls))
        self.assertEqual(urls.read_text(), original)
        self.assertTrue((self.root / "urls.before_results_dashboard.py").exists())


if __name__ == "__main__":
    unittest.main()
