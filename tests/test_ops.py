import csv
import json
import unittest
from pathlib import Path

from revcyclemgmt_remit_denial.ops import build_workqueues


class RemitDenialOpsTest(unittest.TestCase):
    def test_denial_and_variance_queues_are_created(self):
        root = Path(__file__).resolve().parents[1]
        remit = json.loads((root / "samples" / "835_remit_lines.json").read_text(encoding="utf-8"))
        with (root / "samples" / "carc_rarc_taxonomy.csv").open(newline="", encoding="utf-8") as handle:
            taxonomy = {row["code"]: row for row in csv.DictReader(handle)}
        result = build_workqueues(remit, taxonomy)
        queue_names = {queue["queue"] for queue in result["queues"]}
        self.assertIn("Claim correction", queue_names)
        self.assertIn("Payment variance", queue_names)
        self.assertEqual(result["remit_lines"], 3)
        self.assertGreater(result["total_payment_variance"], 0)


if __name__ == "__main__":
    unittest.main()
