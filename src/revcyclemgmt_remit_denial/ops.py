from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _taxonomy(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["code"]: row for row in csv.DictReader(handle)}


def build_workqueues(remit_lines: list[dict[str, Any]], taxonomy: dict[str, dict[str, str]]) -> dict[str, Any]:
    queues: dict[str, dict[str, Any]] = {}
    total_variance = 0.0

    for line in remit_lines:
        variance = round(float(line["allowed_amount"]) - float(line["paid_amount"]), 2)
        total_variance += max(variance, 0.0)
        codes = [code for code in [line.get("carc"), line.get("rarc")] if code]
        if not codes and line.get("status") == "paid":
            queue_name = "Paid and matched"
            owner = "posting lead"
            root_cause = "none"
        else:
            primary = next((code for code in codes if code in taxonomy), codes[0] if codes else "UNMAPPED")
            mapped = taxonomy.get(primary, {})
            queue_name = mapped.get("queue", "Unmapped denial review")
            owner = mapped.get("owner", "billing lead")
            root_cause = mapped.get("root_cause", "unmapped")

        queue = queues.setdefault(
            queue_name,
            {"queue": queue_name, "owner": owner, "items": [], "dollar_exposure": 0.0},
        )
        queue["items"].append(
            {
                "claim_id": line["claim_id"],
                "payer": line["payer"],
                "status": line["status"],
                "codes": codes,
                "root_cause": root_cause,
                "variance": variance,
            }
        )
        queue["dollar_exposure"] = round(queue["dollar_exposure"] + max(variance, 0.0), 2)

    return {
        "remit_lines": len(remit_lines),
        "total_payment_variance": round(total_variance, 2),
        "queues": sorted(queues.values(), key=lambda item: item["dollar_exposure"], reverse=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build synthetic remit and denial workqueues.")
    parser.add_argument("remit_json", type=Path)
    parser.add_argument("taxonomy_csv", type=Path)
    args = parser.parse_args()
    remit_lines = json.loads(args.remit_json.read_text(encoding="utf-8"))
    result = build_workqueues(remit_lines, _taxonomy(args.taxonomy_csv))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
