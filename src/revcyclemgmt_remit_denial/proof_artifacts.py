"""Generated public proof artifacts for remit and denial operations."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from revcyclemgmt_remit_denial.ops import (
    build_console_model,
    load_remit_lines,
    load_taxonomy,
)


STATUS_COLORS = {
    "paid": "#00B3A4",
    "variance": "#FFD166",
    "partial": "#FFD166",
    "patient_responsibility": "#83f7f4",
    "denied": "#FF6B6B",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _money(value: Any) -> str:
    return f"${float(value or 0):,.0f}"


def _pct(value: Any) -> str:
    return f"{float(value or 0) * 100:.1f}%"


def _svg_text(
    x: int,
    y: int,
    text: Any,
    *,
    size: int = 18,
    weight: int = 600,
    color: str = "#f8fafc",
    anchor: str = "start",
    opacity: float = 1,
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" opacity="{opacity}">'
        f"{_escape(text)}</text>"
    )


def _svg_wrapped(
    x: int,
    y: int,
    text: str,
    *,
    width: int,
    line_height: int = 18,
    size: int = 13,
    color: str = "#cbd5e1",
    weight: int = 500,
    max_lines: int = 3,
) -> str:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    max_chars = max(18, width // max(7, round(size * 0.52)))
    for word in words:
        candidate = " ".join([*current, word])
        if len(candidate) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "..."
    return "\n".join(
        _svg_text(x, y + (index * line_height), line, size=size, weight=weight, color=color)
        for index, line in enumerate(lines)
    )


def _panel(x: int, y: int, w: int, h: int, *, stroke: str = "#17474a", fill: str = "#0a1012") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.2"/>'
    )


def _metric_card(x: int, y: int, label: str, value: str, detail: str, color: str = "#83f7f4") -> str:
    return "\n".join(
        [
            _panel(x, y, 204, 92, stroke="rgba(131,247,244,.25)", fill="rgba(10,16,18,.82)"),
            _svg_text(x + 18, y + 28, label.upper(), size=11, weight=800, color="#83f7f4"),
            _svg_text(x + 18, y + 60, value, size=28, weight=900, color=color),
            _svg_text(x + 18, y + 80, detail, size=12, weight=600, color="#94a3b8"),
        ]
    )


def _queue_row(x: int, y: int, queue: dict[str, Any]) -> str:
    return "\n".join(
        [
            _panel(x, y, 424, 58, stroke="rgba(131,247,244,.18)", fill="rgba(255,255,255,.035)"),
            f'<circle cx="{x + 22}" cy="{y + 29}" r="6" fill="#FFD166"/>',
            _svg_text(x + 40, y + 25, queue["queue"], size=14, weight=900),
            _svg_text(x + 40, y + 45, queue["owner"], size=11, weight=700, color="#94a3b8"),
            _svg_text(x + 246, y + 25, str(queue["claim_count"]), size=14, weight=900),
            _svg_text(x + 246, y + 45, "claims", size=11, weight=700, color="#94a3b8"),
            _svg_text(x + 330, y + 25, _money(queue["dollar_exposure"]), size=14, weight=900, color="#FFD166"),
            _svg_text(x + 330, y + 45, "exposure", size=11, weight=700, color="#94a3b8"),
        ]
    )


def _payer_row(x: int, y: int, row: dict[str, Any]) -> str:
    return "\n".join(
        [
            _panel(x, y, 358, 52, stroke="rgba(131,247,244,.16)", fill="rgba(255,255,255,.03)"),
            _svg_text(x + 18, y + 23, row["payer"], size=14, weight=900),
            _svg_text(x + 18, y + 42, row["top_root_cause"], size=11, weight=700, color="#94a3b8"),
            _svg_text(x + 208, y + 23, _pct(row["denial_rate"]), size=13, weight=900, color="#FF6B6B"),
            _svg_text(x + 208, y + 42, "denial rate", size=10, weight=700, color="#94a3b8"),
            _svg_text(x + 292, y + 23, _money(row["payment_variance"]), size=13, weight=900, color="#FFD166"),
            _svg_text(x + 292, y + 42, "variance", size=10, weight=700, color="#94a3b8"),
        ]
    )


def _path_stage(x: int, y: int, title: str, subtitle: str, badge: str) -> str:
    return "\n".join(
        [
            _panel(x, y, 176, 110, stroke="rgba(0,179,164,.40)", fill="rgba(7,13,15,.88)"),
            f'<circle cx="{x + 20}" cy="{y + 27}" r="6" fill="#00B3A4"/>',
            _svg_text(x + 36, y + 33, title, size=15, weight=900),
            _svg_wrapped(x + 18, y + 62, subtitle, width=140, size=12, line_height=16, max_lines=2),
            f'<rect x="{x + 18}" y="{y + 82}" width="94" height="20" rx="10" fill="rgba(0,179,164,.12)" stroke="rgba(131,247,244,.28)"/>',
            _svg_text(x + 65, y + 96, badge, size=10, weight=800, color="#83f7f4", anchor="middle"),
        ]
    )


def build_summary(model: dict[str, Any]) -> dict[str, Any]:
    metrics = model["metrics"]
    queues = model["workqueues"]["queues"]
    scorecard = model["payer_scorecard"]
    return {
        "scenario": "synthetic-remit-denial-ops",
        "remit_lines": metrics["remit_lines"],
        "total_allowed": metrics["total_allowed"],
        "total_paid": metrics["total_paid"],
        "payment_variance": metrics["total_payment_variance"],
        "denial_exposure": metrics["total_denial_exposure"],
        "denied_count": metrics["denied_count"],
        "denial_rate": metrics["denial_rate"],
        "queue_count": metrics["queue_count"],
        "average_days_to_remit": metrics["average_days_to_remit"],
        "top_queue": queues[0] if queues else None,
        "top_payer": scorecard[0] if scorecard else None,
        "workflow": [step["transaction"] for step in model["x12_remit_workflow"]],
        "public_boundary": "Synthetic proof only; no PHI, production 835s, payer credentials, or clearinghouse credentials.",
    }


def build_workqueue_excerpt(model: dict[str, Any]) -> dict[str, Any]:
    queues = model["workqueues"]["queues"]
    selected = next((queue for queue in queues if queue["dollar_exposure"] > 0), queues[0])
    items = selected["items"][:3]
    return {
        "queue": selected["queue"],
        "owner": selected["owner"],
        "claim_count": selected["claim_count"],
        "dollar_exposure": selected["dollar_exposure"],
        "items": [
            {
                "claim_id": item["claim_id"],
                "payer": item["payer"],
                "codes": item["codes"],
                "root_cause": item["root_cause"],
                "recommended_action": item["recommended_action"],
                "dollar_exposure": item["dollar_exposure"],
            }
            for item in items
        ],
        "public_boundary": "Synthetic denial queue excerpt. No PHI, real remit files, contract terms, or production payer records.",
    }


def build_svg(model: dict[str, Any]) -> str:
    metrics = model["metrics"]
    queues = model["workqueues"]["queues"]
    scorecard = model["payer_scorecard"]
    reconciled = model["workqueues"]["reconciled_remits"]
    top_denial = next((item for item in reconciled if item["status"] == "denied"), reconciled[0])

    queue_rows = "\n".join(_queue_row(774, 386 + (index * 66), queue) for index, queue in enumerate(queues[:4]))
    payer_rows = "\n".join(_payer_row(82, 620 + (index * 54), row) for index, row in enumerate(scorecard[:2]))
    path_labels = [
        ("835 intake", "Synthetic ERA line enters the cash control room.", "835"),
        ("Matchback", "Payment line ties back to source claim and trace.", "CLAIM"),
        ("Variance", "Allowed, paid, patient, and gap amounts split.", "BALANCE"),
        ("CARC/RARC", "Reason codes become root-cause queues.", "CODES"),
        ("Follow-up", "Owner and action are assigned before cash stalls.", "ACTION"),
        ("Scorecard", "Payer drag becomes leadership visibility.", "KPI"),
    ]
    stages = "\n".join(
        _path_stage(64 + (index * 202), 736, title, subtitle, badge)
        for index, (title, subtitle, badge) in enumerate(path_labels)
    )
    arrows = "\n".join(
        f'<path d="M {240 + (index * 202)} 791 L {266 + (index * 202)} 791" stroke="#00B3A4" stroke-width="3" marker-end="url(#arrow)"/>'
        for index in range(5)
    )

    cas_lines = "\n".join(
        _svg_text(462, 390 + (index * 25), line, size=13, weight=800, color="#d1f7f4")
        for index, line in enumerate(
            [
                "ST*835*0002~",
                f"CLP*{top_denial['claim_id']}*4*...~",
                f"CAS*{top_denial['codes'][0].replace('-', '*')}*{top_denial['payment_gap']:.2f}~",
                f"TRN*1*{top_denial['trace_number']}*...~",
            ]
        )
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="900" viewBox="0 0 1280 900" role="img" aria-labelledby="title desc">
  <title id="title">RevCycleMGMT remit and denial operations proof</title>
  <desc id="desc">Synthetic proof visual showing 835 remit matchback, payment variance, CARC/RARC denial queues, payer scorecards, and cash recovery actions.</desc>
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#0d1718"/>
      <stop offset=".52" stop-color="#070b0d"/>
      <stop offset="1" stop-color="#111827"/>
    </linearGradient>
    <radialGradient id="glow" cx="26%" cy="15%" r="68%">
      <stop offset="0" stop-color="#00B3A4" stop-opacity=".24"/>
      <stop offset=".42" stop-color="#00B3A4" stop-opacity=".08"/>
      <stop offset="1" stop-color="#00B3A4" stop-opacity="0"/>
    </radialGradient>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,6 L9,3 z" fill="#00B3A4"/>
    </marker>
  </defs>
  <rect width="1280" height="900" fill="url(#bg)"/>
  <rect width="1280" height="900" fill="url(#glow)"/>
  <path d="M 0 840 C 220 758, 478 942, 760 840 S 1130 804, 1280 860" stroke="#00B3A4" stroke-opacity=".18" stroke-width="2" fill="none"/>

  {_svg_text(64, 62, "Remit And Denial Ops Control Room", size=34, weight=900)}
  {_svg_wrapped(64, 96, "Synthetic 835 remit lines become claim matchback, payment variance, CARC/RARC workqueues, payer behavior, and cash recovery visibility.", width=780, size=16, line_height=24, max_lines=2)}
  {_svg_text(64, 144, "Post-adjudication cash recovery proof", size=13, weight=900, color="#83f7f4")}

  {_metric_card(64, 176, "Remits", str(metrics["remit_lines"]), "synthetic lines")}
  {_metric_card(288, 176, "Paid", _money(metrics["total_paid"]), "matched cash")}
  {_metric_card(512, 176, "Variance", _money(metrics["total_payment_variance"]), "cash gap", "#FFD166")}
  {_metric_card(736, 176, "Denials", str(metrics["denied_count"]), f"{_pct(metrics['denial_rate'])} denial rate", "#FF6B6B")}
  {_metric_card(960, 176, "Exposure", _money(metrics["total_denial_exposure"]), "denied allowed", "#FFD166")}

  {_panel(64, 306, 676, 214, stroke="rgba(0,179,164,.34)", fill="rgba(5,10,12,.82)")}
  {_svg_text(88, 338, "Cash recovery example", size=21, weight=900)}
  {_svg_text(88, 370, f"{top_denial['claim_id']} -> {top_denial['queue']}", size=16, weight=900, color="#83f7f4")}
  {_svg_text(88, 402, f"Payer: {top_denial['payer']}", size=14, weight=800)}
  {_svg_text(88, 428, f"Codes: {', '.join(top_denial['codes'])}", size=14, weight=800, color="#FFD166")}
  {_svg_wrapped(88, 458, top_denial["recommended_action"], width=300, size=13, line_height=18, max_lines=3)}
  <line x1="424" y1="334" x2="424" y2="496" stroke="rgba(131,247,244,.18)"/>
  {_svg_text(462, 338, "835 preview excerpt", size=21, weight=900)}
  {cas_lines}

  {_panel(764, 306, 456, 354, stroke="rgba(131,247,244,.25)", fill="rgba(5,10,12,.70)")}
  {_svg_text(790, 338, "Owner-ready workqueues", size=21, weight=900)}
  {_svg_text(790, 364, "Denials and variances are routed before cash stalls.", size=13, weight=800, color="#83f7f4")}
  {queue_rows}

  {_panel(64, 544, 382, 174, stroke="rgba(131,247,244,.20)", fill="rgba(5,10,12,.66)")}
  {_svg_text(88, 576, "Payer behavior scorecard", size=20, weight=900)}
  {_svg_text(88, 600, "Which route is creating drag?", size=13, weight=800, color="#83f7f4")}
  {payer_rows}

  {_svg_text(486, 720, "Remit-to-recovery workflow", size=22, weight=900)}
  {stages}
  {arrows}

  <rect x="64" y="860" width="1152" height="28" rx="14" fill="rgba(0,179,164,.10)" stroke="rgba(131,247,244,.22)"/>
  {_svg_text(640, 879, "Public proof uses synthetic data only: no PHI, no production 835s, no payer credentials, no clearinghouse credentials.", size=13, weight=800, color="#d1f7f4", anchor="middle")}
</svg>
"""


def run(remit_json: Path, taxonomy_csv: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    remit_lines = load_remit_lines(remit_json)
    taxonomy = load_taxonomy(taxonomy_csv)
    model = build_console_model(remit_lines, taxonomy)
    summary = build_summary(model)
    excerpt = build_workqueue_excerpt(model)
    svg = build_svg(model)

    summary_path = output_dir / "remit_denial_ops_summary.json"
    excerpt_path = output_dir / "denial_workqueue_excerpt.json"
    svg_path = output_dir / "remit_denial_ops_proof.svg"

    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    excerpt_path.write_text(json.dumps(excerpt, indent=2) + "\n", encoding="utf-8")
    svg_path.write_text(svg, encoding="utf-8")

    return {
        "remit_lines": summary["remit_lines"],
        "denied_count": summary["denied_count"],
        "payment_variance": summary["payment_variance"],
        "denial_exposure": summary["denial_exposure"],
        "queue_count": summary["queue_count"],
        "artifact_count": 3,
        "svg": str(svg_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public remit and denial operations proof artifacts.")
    parser.add_argument("--remit", type=Path, default=Path("samples/835_remit_lines.json"))
    parser.add_argument("--taxonomy", type=Path, default=Path("samples/carc_rarc_taxonomy.csv"))
    parser.add_argument("--out", type=Path, default=Path("output_demo"))
    args = parser.parse_args()
    print(json.dumps(run(args.remit, args.taxonomy, args.out), indent=2))


if __name__ == "__main__":
    main()
