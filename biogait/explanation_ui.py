"""Qt-agnostic explanation runner helpers (Sprint C, C11).

Pure functions used by the live UI and tests to turn a current-evidence payload
into structured evidence for the bounded explainer, and to run it. The optional
QThread wrapper lives in this module but is only used when PyQt5 is present; the
pure helpers are fully testable without Qt.

The explainer is NEVER called per frame. It runs on explicit user action
(button) or after a completed session.
"""
from __future__ import annotations

from typing import Any, Optional

from openrouter_explainer import OpenRouterExplainer, make_explainer


def evidence_from_payload(payload: dict) -> dict:
    """Build a structured-evidence dict from a live/current evidence payload.

    Only non-identifying, structured fields are included (the explainer itself
    further whitelists them). Raw frames/camera/paths are never included here.
    """
    po = payload.get("primary_outcomes") or {}
    quality = payload.get("quality") or {}
    evidence = {
        "quality": quality,
        "primary_outcomes": {
            "left_knee_sagittal_deg": po.get("left_knee_sagittal_deg"),
            "right_knee_sagittal_deg": po.get("right_knee_sagittal_deg"),
            "left_po_available": quality.get("left_po_available"),
            "right_po_available": quality.get("right_po_available"),
        },
        "session_descriptors": {
            "left_knee_rom_deg": payload.get("rolling_left_knee_rom_deg"),
            "right_knee_rom_deg": payload.get("rolling_right_knee_rom_deg"),
        },
        # Empty/unknown payloads are NEVER promoted to a real data origin.
        "data_origin": payload.get("data_origin", "UNKNOWN_UNVALIDATED"),
        "processing_mode": payload.get("processing_mode", "live_mediapipe"),
    }
    # Only keep populated fields.
    return {k: v for k, v in evidence.items() if v is not None and (not isinstance(v, dict) or v)}


def run_explanation(evidence: dict, explainer: Optional[OpenRouterExplainer] = None, force: bool = False) -> dict:
    """Run the bounded explainer on ORIGINAL structured evidence; returns an audit.

    The original evidence is passed to the explainer UNCHANGED. The
    OpenRouterExplainer is the single provider boundary owner: it detects
    sensitive nested fields, builds/prunes the whitelisted provider payload,
    and never makes a remote call when sensitive fields are present.
    """
    explainer = explainer or make_explainer()
    return explainer.explain(evidence, force=force)
