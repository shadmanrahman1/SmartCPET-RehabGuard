"""Deterministic BioGait evidence explainer (Sprint C, C7).

Produces plain-language statements from structured evidence only. This is the
REQUIRED fallback (and the default) explainer; it makes no clinical claims.

Example statements:

- "Both knee-angle streams were available for 84% of the retained analysis window."
- "The current left sagittal knee-angle evidence is unavailable because required
  pose landmarks were not available."
- "These values are descriptive kinematic evidence and should not be interpreted
  as a clinical score."

It never says: movement is correct, patient is healthy, rehabilitation is
successful, exercise quality is X/10, or clinical improvement.
"""
from __future__ import annotations

from typing import Any, Optional

from explanation_schema import (
    OUTPUT_SCHEMA_KEYS,
    build_input,
)

SAFETY_NOTE = (
    "This is descriptive research evidence and not a clinical assessment."
)


def _availability_summary(evidence_input: dict) -> Optional[float]:
    q = evidence_input.get("quality")
    if isinstance(q, dict):
        rate = q.get("availability_rate") or q.get("rolling_availability_rate")
        if rate is not None:
            try:
                return max(0.0, min(1.0, float(rate)))
            except (TypeError, ValueError):
                return None
        added = q.get("frames_added")
        available = q.get("available_frames")
        if added and available:
            return float(available) / float(added)
    return None


def _side_state(po: Any, side: str) -> str:
    if not isinstance(po, dict):
        return "unavailable"
    val = po.get(f"{side}_knee_sagittal_deg")
    return "available" if val is not None else "unavailable"


def _temporal_status(evidence_input: dict) -> list[str]:
    lines = []
    ta = evidence_input.get("temporal_analysis")
    if isinstance(ta, dict):
        for branch in ("reference", "adapted"):
            node = ta.get(branch) or {}
            warnings = []
            for side in ("left", "right"):
                sn = node.get(side) or {}
                if sn.get("warning"):
                    warnings.append(sn["warning"])
            if not isinstance(node, dict):
                continue
            cls = node.get("classification")
            if warnings:
                lines.append(
                    f"{branch} analysis ({cls}): {warnings[0]}"
                )
            elif cls:
                lines.append(
                    f"{branch} analysis ran ({cls}); candidate events are not "
                    "clinically validated repetitions."
                )
    return lines


def template_explain(evidence: dict) -> dict:
    """Produce a deterministic template explanation from structured evidence."""
    evidence_input = build_input(evidence)
    observations: list[str] = []
    limitations: list[str] = []

    q = evidence_input.get("quality")
    if isinstance(q, dict):
        if q.get("left_po_available") is False and q.get("right_po_available"):
            observations.append(
                "The current left sagittal knee-angle evidence is unavailable "
                "because required pose landmarks were not available."
            )
        elif q.get("right_po_available") is False and q.get("left_po_available"):
            observations.append(
                "The current right sagittal knee-angle evidence is unavailable "
                "because required pose landmarks were not available."
            )
        elif q.get("available") and q.get("left_po_available") and q.get("right_po_available"):
            observations.append(
                "Both current sagittal knee-angle streams were available."
            )

    rate = _availability_summary(evidence_input)
    if rate is not None:
        observations.append(
            f"Both knee-angle streams were available for {rate * 100:.0f}% of "
            "the retained analysis window."
        )

    po = evidence_input.get("primary_outcomes") or evidence_input.get("primary_outcomes")
    if isinstance(po, dict):
        observations.append(
            f"Left sagittal knee angle: {_side_state(po, 'left')}; "
            f"right sagittal knee angle: {_side_state(po, 'right')}."
        )

    descriptors = evidence_input.get("session_descriptors") or evidence_input.get("descriptive_kinematics")
    if isinstance(descriptors, dict):
        left_rom = descriptors.get("left_knee_rom_deg")
        right_rom = descriptors.get("right_knee_rom_deg")
        if left_rom is not None or right_rom is not None:
            observations.append(
                f"Descriptive rolling ROM: left={_fmt(left_rom)}, "
                f"right={_fmt(right_rom)} (degrees; descriptive kinematics)."
            )

    provenance = evidence_input.get("method_provenance")
    if isinstance(provenance, dict) or isinstance(evidence_input.get("temporal_analysis"), dict):
        observations.extend(_temporal_status(evidence_input))

    limitations.append(
        "These values are descriptive kinematic evidence and should not be "
        "interpreted as a clinical score."
    )
    for lim in (evidence_input.get("limitations") or []):
        if isinstance(lim, str):
            limitations.append(lim)

    return {
        "summary": _make_summary(evidence_input, rate, observations),
        "observations": observations,
        "limitations": limitations,
        "safety_note": SAFETY_NOTE,
    }


def _make_summary(evidence_input: dict, rate, observations: list[str]) -> str:
    origin = evidence_input.get("data_origin", "unknown")
    parts = [
        f"BioGait research-evidence summary (data origin: {origin}; "
        "KIMORE-informed, descriptive)."
    ]
    if rate is not None:
        parts.append(f"Retained-window availability: {rate * 100:.0f}%.")
    if observations:
        parts.append(observations[0])
    return " ".join(parts)


def _fmt(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"
