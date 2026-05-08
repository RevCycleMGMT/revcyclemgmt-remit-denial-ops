from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from revcyclemgmt_remit_denial.ops import build_console_model, load_remit_lines, load_taxonomy


REMIT_PATH = ROOT / "samples" / "835_remit_lines.json"
TAXONOMY_PATH = ROOT / "samples" / "carc_rarc_taxonomy.csv"


def _load_uploaded_remits(uploaded_file: Any) -> list[dict[str, Any]]:
    payload = json.loads(uploaded_file.read().decode("utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("remit_lines"), list):
        return payload["remit_lines"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Upload must be a JSON list or an object with remit_lines.")


def _render_css() -> None:
    st.markdown(
        """
        <style>
          .stApp {
            background:
              radial-gradient(circle at 18% 8%, rgba(0, 179, 164, .15), transparent 30%),
              linear-gradient(135deg, rgba(255,255,255,.035), transparent 28%),
              #070b0d;
            color: #f8fafc;
          }
          .block-container {
            padding-top: 2rem;
            max-width: 1240px;
          }
          .rcm-hero {
            border: 1px solid rgba(131,247,244,.22);
            background: rgba(10,16,18,.76);
            border-radius: 8px;
            padding: 22px 24px;
            box-shadow: 0 0 38px rgba(0, 179, 164, .08);
          }
          .rcm-kicker {
            color: #83f7f4;
            font-size: .76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .08em;
          }
          .rcm-chip {
            display: inline-flex;
            margin: 5px 8px 5px 0;
            padding: 6px 10px;
            border-radius: 999px;
            border: 1px solid rgba(131,247,244,.22);
            background: rgba(0,179,164,.08);
            color: #d1f7f4;
            font-size: .76rem;
            font-weight: 700;
          }
          div[data-testid="stMetric"] {
            border: 1px solid rgba(131,247,244,.18);
            background: rgba(10, 16, 18, .70);
            border-radius: 8px;
            padding: 12px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _reconciled_frame(model: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(model["workqueues"]["reconciled_remits"])[
        [
            "claim_id",
            "payer",
            "status",
            "allowed_amount",
            "paid_amount",
            "payment_gap",
            "codes",
            "queue",
            "owner",
            "days_to_remit",
        ]
    ]


def _queues_frame(model: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Queue": queue["queue"],
                "Owner": queue["owner"],
                "Claims": queue["claim_count"],
                "Exposure": queue["dollar_exposure"],
            }
            for queue in model["workqueues"]["queues"]
        ]
    )


def _workflow_frame(model: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(model["x12_remit_workflow"])


def main() -> None:
    st.set_page_config(
        page_title="RevCycleMGMT Remit and Denial Ops",
        page_icon="RCM",
        layout="wide",
    )
    _render_css()

    st.markdown(
        """
        <div class="rcm-hero">
          <div class="rcm-kicker">Synthetic 835 Remit And Denial Ops</div>
          <h1 style="margin: .3rem 0 0;">From remit noise to owner-ready workqueues.</h1>
          <p style="max-width: 930px; color: #cbd5e1; line-height: 1.65;">
            This local console shows how RevCycleMGMT reconciles synthetic 835 remit lines,
            groups CARC/RARC reasons, measures payment variance, ranks payer behavior,
            and routes denial follow-up without public PHI or production payment files.
          </p>
          <span class="rcm-chip">835 ERA</span>
          <span class="rcm-chip">CARC/RARC taxonomy</span>
          <span class="rcm-chip">Payment variance</span>
          <span class="rcm-chip">Denial workqueues</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("Scenario")
    st.sidebar.caption("Use synthetic JSON only. Do not upload PHI, payer files, credentials, or production remits.")
    uploaded = st.sidebar.file_uploader("Load synthetic 835 remit JSON", type=["json"])

    try:
        remit_lines = _load_uploaded_remits(uploaded) if uploaded else load_remit_lines(REMIT_PATH)
        taxonomy = load_taxonomy(TAXONOMY_PATH)
    except Exception as exc:  # pragma: no cover
        st.error(f"Unable to load remit scenario: {exc}")
        st.stop()

    model = build_console_model(remit_lines, taxonomy)
    metrics = model["metrics"]

    st.write("")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Remit Lines", metrics["remit_lines"])
    m2.metric("Denied", metrics["denied_count"])
    m3.metric("Denial Rate", f"{metrics['denial_rate']:.0%}")
    m4.metric("Payment Variance", f"${metrics['total_payment_variance']:,.0f}")
    m5.metric("Denial Exposure", f"${metrics['total_denial_exposure']:,.0f}")

    tabs = st.tabs(["Control Room", "Workqueues", "Payer Scorecard", "835 Preview", "X12/API Flow", "Audit Log"])

    with tabs[0]:
        left, right = st.columns([1.35, 1])
        with left:
            st.subheader("Reconciled remit lines")
            st.dataframe(_reconciled_frame(model), width="stretch", hide_index=True)
        with right:
            st.subheader("Exposure by queue")
            queue_df = _queues_frame(model)
            st.bar_chart(queue_df.set_index("Queue")[["Exposure"]], color="#00B3A4")

    with tabs[1]:
        st.subheader("Owner-ready workqueues")
        st.dataframe(_queues_frame(model), width="stretch", hide_index=True)
        selected_queue = st.selectbox("Queue detail", [queue["queue"] for queue in model["workqueues"]["queues"]])
        queue = next(queue for queue in model["workqueues"]["queues"] if queue["queue"] == selected_queue)
        st.dataframe(pd.DataFrame(queue["items"]), width="stretch", hide_index=True)

    with tabs[2]:
        st.subheader("Payer behavior")
        st.dataframe(pd.DataFrame(model["payer_scorecard"]), width="stretch", hide_index=True)

    with tabs[3]:
        st.subheader("Synthetic 835 preview")
        st.caption("This preview is synthetic X12-style output for implementation proof. It is not a production remit.")
        st.code(model["835_preview"], language="text")

    with tabs[4]:
        st.subheader("X12 and API workflow alignment")
        st.caption("Vendor-neutral mapping for ERA mailbox/report retrieval, remit reconciliation, CARC/RARC routing, and dashboard handoff.")
        st.dataframe(_workflow_frame(model), width="stretch", hide_index=True)

    with tabs[5]:
        st.subheader("Audit log")
        st.dataframe(pd.DataFrame(model["audit_log"]), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
