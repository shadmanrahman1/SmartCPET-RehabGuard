from __future__ import annotations

import json
import time
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

import config


RISK_STYLES = {
    "LOW": {"color": "#2e9d58", "label": "Low"},
    "MODERATE": {"color": "#d69025", "label": "Moderate"},
    "HIGH": {"color": "#ce3f4a", "label": "High"},
}


def load_latest_metrics() -> dict[str, Any] | None:
    path = Path(config.LATEST_METRICS_PATH)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def metric_card(label: str, value: Any, suffix: str = "") -> None:
    display = "--" if value is None else f"{value}{suffix}"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(display)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_gauge(score: int, level: str) -> None:
    score = max(0, min(100, int(score or 0)))
    style = RISK_STYLES.get(level, RISK_STYLES["LOW"])
    st.markdown(
        f"""
        <div class="risk-wrap">
            <div class="risk-head">
                <span>{escape(style["label"])} Risk</span>
                <strong>{score}/100</strong>
            </div>
            <div class="gauge-track">
                <div class="gauge-fill" style="width:{score}%; background:{style["color"]};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f6f8fb;
            color: #172033;
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.8rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .top-band {
            border-left: 6px solid #2f7bbf;
            background: #ffffff;
            padding: 18px 22px;
            border-radius: 8px;
            box-shadow: 0 8px 22px rgba(30, 45, 70, 0.08);
            margin-bottom: 18px;
        }
        .top-title {
            font-size: 1.45rem;
            font-weight: 760;
            margin-bottom: 4px;
        }
        .top-subtitle {
            color: #526070;
            font-size: 0.98rem;
        }
        .metric-card {
            background: #ffffff;
            border: 1px solid #e0e7ef;
            border-radius: 8px;
            padding: 18px 18px 16px;
            min-height: 116px;
            box-shadow: 0 8px 20px rgba(30, 45, 70, 0.07);
        }
        .metric-label {
            color: #5d6b7a;
            font-size: 0.86rem;
            font-weight: 650;
            text-transform: uppercase;
        }
        .metric-value {
            color: #172033;
            font-size: 2rem;
            font-weight: 780;
            line-height: 1.25;
            margin-top: 10px;
        }
        .risk-wrap {
            background: #ffffff;
            border: 1px solid #e0e7ef;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 8px 20px rgba(30, 45, 70, 0.07);
            margin-top: 8px;
        }
        .risk-head {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            font-size: 1.1rem;
            margin-bottom: 14px;
        }
        .risk-head strong {
            font-size: 1.65rem;
        }
        .gauge-track {
            height: 20px;
            background: #e8edf3;
            border-radius: 8px;
            overflow: hidden;
        }
        .gauge-fill {
            height: 100%;
            border-radius: 8px;
            transition: width 0.25s ease;
        }
        .reason-box {
            background: #ffffff;
            border: 1px solid #e0e7ef;
            border-radius: 8px;
            padding: 18px 20px;
            box-shadow: 0 8px 20px rgba(30, 45, 70, 0.07);
        }
        .reason-box li {
            margin-bottom: 8px;
        }
        .note {
            color: #5d6b7a;
            font-size: 0.9rem;
            margin-top: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="SmartCPET BioGait Dashboard",
        page_icon="BG",
        layout="wide",
    )
    apply_styles()

    data = load_latest_metrics()

    st.markdown(
        """
        <div class="top-band">
            <div class="top-title">SmartCPET-RehabGuard BioGait</div>
            <div class="top-subtitle">Live camera-based pose analysis and recovery-readiness screening</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if data is None:
        st.warning("Waiting for latest_metrics.json. Start the camera app with python app.py.")
        time.sleep(1)
        st.rerun()

    status_cols = st.columns([1.5, 1, 1])
    with status_cols[0]:
        metric_card("Tracking status", data.get("tracking_status"))
    with status_cols[1]:
        metric_card("Risk level", data.get("risk_level"))
    with status_cols[2]:
        metric_card("Updated", data.get("timestamp", "--"))

    st.write("")
    cols = st.columns(4)
    with cols[0]:
        metric_card("Left knee angle", data.get("left_knee_angle"), " deg")
    with cols[1]:
        metric_card("Right knee angle", data.get("right_knee_angle"), " deg")
    with cols[2]:
        metric_card("Trunk lean", data.get("trunk_lean"), " deg")
    with cols[3]:
        metric_card("Knee asymmetry", data.get("knee_asymmetry"), " deg")

    st.write("")
    lower_cols = st.columns([1.1, 0.9])
    with lower_cols[0]:
        risk_gauge(data.get("risk_score", 0), data.get("risk_level", "LOW"))
    with lower_cols[1]:
        reasons = data.get("reasons", [])
        reason_items = "".join(f"<li>{escape(str(reason))}</li>" for reason in reasons)
        st.markdown(
            f"""
            <div class="reason-box">
                <strong>Reason list</strong>
                <ul>{reason_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="note">Screening output only; not a clinical diagnosis.</div>',
        unsafe_allow_html=True,
    )

    time.sleep(1)
    st.rerun()


if __name__ == "__main__":
    main()
