import json
import tempfile
import unittest
from pathlib import Path

from revcyclemgmt_remit_denial.ops import (
    build_835_preview,
    build_console_model,
    build_metrics,
    build_payer_scorecard,
    build_workqueues,
    load_remit_lines,
    load_taxonomy,
    reconcile_line,
    run,
)
from revcyclemgmt_remit_denial.proof_artifacts import run as proof_artifacts_run


ROOT = Path(__file__).resolve().parents[1]
REMIT_PATH = ROOT / "samples" / "835_remit_lines.json"
TAXONOMY_PATH = ROOT / "samples" / "carc_rarc_taxonomy.csv"


class RemitDenialOpsTest(unittest.TestCase):
    def setUp(self):
        self.remit = load_remit_lines(REMIT_PATH)
        self.taxonomy = load_taxonomy(TAXONOMY_PATH)

    def test_denial_and_variance_queues_are_created(self):
        result = build_workqueues(self.remit, self.taxonomy)
        queue_names = {queue["queue"] for queue in result["queues"]}

        self.assertIn("Claim correction", queue_names)
        self.assertIn("Payment variance", queue_names)
        self.assertIn("Authorization follow-up", queue_names)
        self.assertIn("Medical necessity review", queue_names)
        self.assertEqual(result["remit_lines"], 6)
        self.assertGreater(result["total_payment_variance"], 0)

    def test_reconcile_line_maps_denial_reason(self):
        line = next(item for item in self.remit if item["claim_id"] == "SYN-CLAIM-9002")
        reconciled = reconcile_line(line, self.taxonomy)

        self.assertEqual(reconciled["queue"], "Claim correction")
        self.assertEqual(reconciled["owner"], "billing lead")
        self.assertEqual(reconciled["root_cause"], "missing_or_invalid_information")
        self.assertEqual(reconciled["payment_gap"], 210.0)

    def test_patient_responsibility_keeps_its_own_variance_type(self):
        line = next(item for item in self.remit if item["claim_id"] == "SYN-CLAIM-9004")
        reconciled = reconcile_line(line, self.taxonomy)

        self.assertEqual(reconciled["queue"], "Patient responsibility posting")
        self.assertEqual(reconciled["payment_gap"], 0.0)
        self.assertEqual(reconciled["variance_type"], "patient_responsibility")

    def test_payer_scorecard_ranks_variance(self):
        result = build_workqueues(self.remit, self.taxonomy)
        scorecard = build_payer_scorecard(result["reconciled_remits"])

        self.assertEqual(scorecard[0]["payer"], "Synthetic Payer B")
        self.assertGreater(scorecard[0]["payment_variance"], 0)
        self.assertGreaterEqual(scorecard[0]["denied_count"], 1)

    def test_metrics_and_835_preview(self):
        result = build_workqueues(self.remit, self.taxonomy)
        metrics = build_metrics(result)
        preview = build_835_preview(result["reconciled_remits"])

        self.assertEqual(metrics["remit_lines"], 6)
        self.assertEqual(metrics["denied_count"], 2)
        self.assertIn("ST*835", preview)
        self.assertIn("CLP*SYN-CLAIM-9002", preview)
        self.assertIn("CAS*CO*16*210.00", preview)
        self.assertIn("CAS*CO*50*80.00", preview)
        self.assertIn("CAS*PR*1*40.00", preview)

    def test_console_model_contains_x12_remit_workflow(self):
        model = build_console_model(self.remit, self.taxonomy)
        transactions = {step["transaction"] for step in model["x12_remit_workflow"]}

        self.assertIn("835 ERA", transactions)
        self.assertIn("CARC / RARC", transactions)
        self.assertIn("835 trend metrics", transactions)
        self.assertEqual(len(model["audit_log"]), 12)

    def test_run_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = run(REMIT_PATH, TAXONOMY_PATH, output_dir)

            self.assertEqual(result["queue_count"], 6)
            self.assertTrue((output_dir / "reconciled_remits.json").exists())
            self.assertTrue((output_dir / "denial_workqueues.json").exists())
            self.assertTrue((output_dir / "payer_scorecard.json").exists())
            self.assertTrue((output_dir / "remit_metrics.json").exists())
            self.assertTrue((output_dir / "x12_remit_workflow.json").exists())
            self.assertTrue((output_dir / "835_preview.edi").exists())
            self.assertTrue((output_dir / "audit_log.json").exists())

            metrics = json.loads((output_dir / "remit_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["remit_lines"], 6)

    def test_public_proof_artifacts_show_cash_recovery_and_denial_queues(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = proof_artifacts_run(REMIT_PATH, TAXONOMY_PATH, output_dir)

            self.assertEqual(result["remit_lines"], 6)
            self.assertEqual(result["denied_count"], 2)
            self.assertEqual(result["queue_count"], 6)
            self.assertEqual(result["artifact_count"], 3)

            summary = json.loads((output_dir / "remit_denial_ops_summary.json").read_text(encoding="utf-8"))
            excerpt = json.loads((output_dir / "denial_workqueue_excerpt.json").read_text(encoding="utf-8"))
            svg = (output_dir / "remit_denial_ops_proof.svg").read_text(encoding="utf-8")

            self.assertIn("835 ERA", summary["workflow"])
            self.assertIn("CARC / RARC", summary["workflow"])
            self.assertIn("835 trend metrics", summary["workflow"])
            self.assertIn("Synthetic proof only", summary["public_boundary"])
            self.assertGreater(summary["payment_variance"], 0)
            self.assertGreater(summary["denial_exposure"], 0)
            self.assertIn("Synthetic denial queue excerpt", excerpt["public_boundary"])
            self.assertIn("Remit And Denial Ops Control Room", svg)
            self.assertIn("Cash recovery example", svg)
            self.assertIn("Owner-ready workqueues", svg)
            self.assertIn("CARC/RARC", svg)
            self.assertIn("no PHI", svg)


if __name__ == "__main__":
    unittest.main()
