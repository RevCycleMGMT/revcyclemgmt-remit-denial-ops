"""Synthetic remit reconciliation and denial operations proof."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


STATUS_ORDER = {
    "denied": 0,
    "variance": 1,
    "partial": 2,
    "patient_responsibility": 3,
    "paid": 4,
}

X12_REMIT_WORKFLOW = [
    {
        "stage": "1. Remit intake",
        "transaction": "835 ERA",
        "artifact": "remit_lines.json",
        "handoff": "Capture payer payment, adjustment, trace, and CARC/RARC context.",
        "api_alignment": "Reports, remittance, or ERA mailbox retrieval workflow.",
    },
    {
        "stage": "2. Claim matchback",
        "transaction": "835 -> source claim",
        "artifact": "reconciled_remits.json",
        "handoff": "Tie paid, denied, or adjusted remit lines back to submitted claim IDs.",
        "api_alignment": "Claim-level reconciliation after 837 submission and acknowledgment tracking.",
    },
    {
        "stage": "3. Denial taxonomy",
        "transaction": "CARC / RARC",
        "artifact": "denial_workqueues.json",
        "handoff": "Group denial reasons into owner-ready queues.",
        "api_alignment": "Response normalization for follow-up operations.",
    },
    {
        "stage": "4. Payment variance",
        "transaction": "835 CAS / CLP balancing",
        "artifact": "payment_variance_report.json",
        "handoff": "Separate contractual, underpayment, patient responsibility, and missing-payment exposure.",
        "api_alignment": "Payment posting, variance, and contract-review workflow.",
    },
    {
        "stage": "5. Payer behavior",
        "transaction": "835 trend metrics",
        "artifact": "payer_scorecard.json",
        "handoff": "Rank payers by denial count, variance exposure, and average payment lag.",
        "api_alignment": "Leadership dashboard, payer-route monitoring, and 276/277 follow-up context.",
    },
]


def load_remit_lines(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("remit_lines"), list):
        return payload["remit_lines"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Remit input must be a list or an object with remit_lines.")


def load_taxonomy(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["code"]: row for row in csv.DictReader(handle)}


def _codes(line: dict[str, Any]) -> list[str]:
    codes = []
    for key in ("carc", "rarc"):
        value = str(line.get(key, "")).strip()
        if value:
            codes.append(value)
    for code in line.get("codes", []):
        if code and code not in codes:
            codes.append(str(code))
    return codes


def _money(value: Any) -> float:
    return round(float(value or 0), 2)


def _taxonomy_match(codes: list[str], taxonomy: dict[str, dict[str, str]]) -> dict[str, str]:
    for code in codes:
        if code in taxonomy:
            return taxonomy[code]
    return {
        "code": codes[0] if codes else "UNMAPPED",
        "root_cause": "unmapped",
        "owner": "billing lead",
        "queue": "Unmapped remit review",
        "action": "Review payer response and map the reason code.",
    }


def reconcile_line(line: dict[str, Any], taxonomy: dict[str, dict[str, str]]) -> dict[str, Any]:
    billed = _money(line.get("billed_amount"))
    allowed = _money(line.get("allowed_amount"))
    paid = _money(line.get("paid_amount"))
    patient_resp = _money(line.get("patient_responsibility"))
    contractual = max(round(billed - allowed, 2), 0.0)
    payment_gap = max(round(allowed - paid - patient_resp, 2), 0.0)
    codes = _codes(line)
    status = str(line.get("status", "unknown")).strip().lower()

    if not codes and status == "paid" and payment_gap == 0:
        queue_name = "Paid and matched"
        owner = "posting lead"
        root_cause = "none"
        action = "Post payment and close remit loop."
    else:
        mapped = _taxonomy_match(codes, taxonomy)
        queue_name = mapped.get("queue", "Unmapped remit review")
        owner = mapped.get("owner", "billing lead")
        root_cause = mapped.get("root_cause", "unmapped")
        action = mapped.get("action", "Review payer response and route follow-up.")

    variance_type = "none"
    if status == "denied":
        variance_type = "denial"
    elif payment_gap > 0:
        variance_type = "payment_gap"
    elif status == "patient_responsibility" or patient_resp > 0:
        variance_type = "patient_responsibility"
    elif contractual > 0:
        variance_type = "contractual_adjustment"

    return {
        "claim_id": line["claim_id"],
        "payer": line["payer"],
        "status": status,
        "billed_amount": billed,
        "allowed_amount": allowed,
        "paid_amount": paid,
        "patient_responsibility": patient_resp,
        "contractual_adjustment": contractual,
        "payment_gap": payment_gap,
        "dollar_exposure": payment_gap if status != "paid" else 0.0,
        "codes": codes,
        "root_cause": root_cause,
        "queue": queue_name,
        "owner": owner,
        "recommended_action": action,
        "trace_number": line.get("trace_number", ""),
        "service_date": line.get("service_date", ""),
        "remit_date": line.get("remit_date", ""),
        "days_to_remit": int(line.get("days_to_remit", 0) or 0),
        "variance_type": variance_type,
    }


def build_workqueues(remit_lines: list[dict[str, Any]], taxonomy: dict[str, dict[str, str]]) -> dict[str, Any]:
    reconciled = [reconcile_line(line, taxonomy) for line in remit_lines]
    queues: dict[str, dict[str, Any]] = {}

    for item in sorted(
        reconciled,
        key=lambda row: (STATUS_ORDER.get(row["status"], 99), -row["dollar_exposure"], row["claim_id"]),
    ):
        queue = queues.setdefault(
            item["queue"],
            {
                "queue": item["queue"],
                "owner": item["owner"],
                "items": [],
                "dollar_exposure": 0.0,
                "claim_count": 0,
            },
        )
        queue["items"].append(item)
        queue["claim_count"] += 1
        queue["dollar_exposure"] = round(queue["dollar_exposure"] + item["dollar_exposure"], 2)

    return {
        "remit_lines": len(remit_lines),
        "total_payment_variance": round(sum(item["payment_gap"] for item in reconciled), 2),
        "total_denial_exposure": round(
            sum(item["allowed_amount"] for item in reconciled if item["status"] == "denied"), 2
        ),
        "reconciled_remits": reconciled,
        "queues": sorted(queues.values(), key=lambda item: item["dollar_exposure"], reverse=True),
    }


def build_payer_scorecard(reconciled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_payer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in reconciled:
        by_payer[item["payer"]].append(item)

    scorecard = []
    for payer, rows in by_payer.items():
        claim_count = len(rows)
        denied = sum(1 for row in rows if row["status"] == "denied")
        variance = round(sum(row["payment_gap"] for row in rows), 2)
        paid = round(sum(row["paid_amount"] for row in rows), 2)
        average_lag = round(sum(row["days_to_remit"] for row in rows) / claim_count, 1)
        root_causes = Counter(row["root_cause"] for row in rows if row["root_cause"] != "none")
        scorecard.append(
            {
                "payer": payer,
                "claim_count": claim_count,
                "denied_count": denied,
                "denial_rate": round(denied / claim_count, 3),
                "payment_variance": variance,
                "paid_amount": paid,
                "average_days_to_remit": average_lag,
                "top_root_cause": root_causes.most_common(1)[0][0] if root_causes else "none",
            }
        )
    return sorted(scorecard, key=lambda row: (row["payment_variance"], row["denied_count"]), reverse=True)


def build_metrics(workqueue_result: dict[str, Any]) -> dict[str, Any]:
    reconciled = workqueue_result["reconciled_remits"]
    total_allowed = round(sum(row["allowed_amount"] for row in reconciled), 2)
    total_paid = round(sum(row["paid_amount"] for row in reconciled), 2)
    denied = sum(1 for row in reconciled if row["status"] == "denied")
    return {
        "remit_lines": len(reconciled),
        "total_allowed": total_allowed,
        "total_paid": total_paid,
        "total_payment_variance": workqueue_result["total_payment_variance"],
        "total_denial_exposure": workqueue_result["total_denial_exposure"],
        "denied_count": denied,
        "denial_rate": round(denied / len(reconciled), 3) if reconciled else 0,
        "queue_count": len(workqueue_result["queues"]),
        "average_days_to_remit": round(
            sum(row["days_to_remit"] for row in reconciled) / len(reconciled), 1
        )
        if reconciled
        else 0,
    }


def build_835_preview(reconciled: list[dict[str, Any]]) -> str:
    lines = [
        "ISA*00*          *00*          *ZZ*SYNTHETIC      *ZZ*REVCYCLEMGMT   *260507*1200*^*00501*000000002*0*T*:~",
        "GS*HP*SYNTHETIC*REVCYCLEMGMT*20260507*1200*2*X*005010X221A1~",
        "ST*835*0002~",
        "BPR*I*0*C*CHK************20260507~",
        "TRN*1*SYNTHETIC-TRACE*1999999999~",
    ]
    for item in reconciled:
        lines.append(
            f"CLP*{item['claim_id']}*{_clp_status(item['status'])}*{item['billed_amount']:.2f}*{item['paid_amount']:.2f}*{item['patient_responsibility']:.2f}*12*{item['trace_number'] or item['claim_id']}*11*1~"
        )
        adjustment = _cas_adjustment(item)
        if adjustment:
            group, reason, amount = adjustment
            lines.append(f"CAS*{group}*{reason}*{amount:.2f}~")
    transaction_segment_count = len(lines) - 2 + 1
    lines.extend([f"SE*{transaction_segment_count}*0002~", "GE*1*2~", "IEA*1*000000002~"])
    return "\n".join(lines)


def _cas_adjustment(item: dict[str, Any]) -> tuple[str, str, float] | None:
    for code in item["codes"]:
        if "-" not in code:
            continue
        group, reason = code.split("-", 1)
        if group in {"CO", "PR", "OA", "PI"} and reason:
            if group == "PR":
                amount = item["patient_responsibility"]
            else:
                amount = item["payment_gap"]
            return group, reason, amount
    return None


def _clp_status(status: str) -> str:
    return {
        "paid": "1",
        "partial": "2",
        "denied": "4",
        "variance": "2",
        "patient_responsibility": "1",
    }.get(status, "3")


def build_audit_log(reconciled: list[dict[str, Any]]) -> list[dict[str, str]]:
    events = []
    for item in reconciled:
        event_time = f"{item['remit_date']}T12:00:00+00:00" if item["remit_date"] else "2026-05-07T12:00:00+00:00"
        events.extend(
            [
                {
                    "timestamp": event_time,
                    "claim_id": item["claim_id"],
                    "event": "remit_matchback",
                    "detail": f"835 line matched to claim with status {item['status']}.",
                },
                {
                    "timestamp": event_time,
                    "claim_id": item["claim_id"],
                    "event": "workqueue_route",
                    "detail": f"Routed to {item['queue']} owned by {item['owner']}.",
                },
            ]
        )
    return events


def build_console_model(remit_lines: list[dict[str, Any]], taxonomy: dict[str, dict[str, str]]) -> dict[str, Any]:
    workqueues = build_workqueues(remit_lines, taxonomy)
    reconciled = workqueues["reconciled_remits"]
    return {
        "workqueues": workqueues,
        "metrics": build_metrics(workqueues),
        "payer_scorecard": build_payer_scorecard(reconciled),
        "x12_remit_workflow": X12_REMIT_WORKFLOW,
        "835_preview": build_835_preview(reconciled),
        "audit_log": build_audit_log(reconciled),
    }


def run(remit_json: Path, taxonomy_csv: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    remit_lines = load_remit_lines(remit_json)
    taxonomy = load_taxonomy(taxonomy_csv)
    model = build_console_model(remit_lines, taxonomy)

    (output_dir / "reconciled_remits.json").write_text(
        json.dumps(model["workqueues"]["reconciled_remits"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "denial_workqueues.json").write_text(
        json.dumps(model["workqueues"]["queues"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "payer_scorecard.json").write_text(
        json.dumps(model["payer_scorecard"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "remit_metrics.json").write_text(
        json.dumps(model["metrics"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "x12_remit_workflow.json").write_text(
        json.dumps(model["x12_remit_workflow"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "835_preview.edi").write_text(model["835_preview"] + "\n", encoding="utf-8")
    (output_dir / "audit_log.json").write_text(
        json.dumps(model["audit_log"], indent=2) + "\n", encoding="utf-8"
    )
    return {
        "metrics": model["metrics"],
        "queue_count": len(model["workqueues"]["queues"]),
        "payer_count": len(model["payer_scorecard"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build synthetic remit and denial workqueues.")
    parser.add_argument("remit_json", type=Path)
    parser.add_argument("taxonomy_csv", type=Path)
    parser.add_argument("--out", type=Path, default=Path("output_demo"))
    args = parser.parse_args()
    result = run(args.remit_json, args.taxonomy_csv, args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
