"""BioGait research evidence report generator (Sprint C, C12).

Input : a BioGait session JSON (offline/live export or experiment result).
Output: a Markdown "BioGait Research Evidence Report" (never called clinical,
diagnostic, or medical) plus an optional JSON summary.

The report includes session metadata, data origin, method provenance, PO
coverage, control-factor coverage, descriptive kinematics, temporal-analysis
status, runtime/quality summary, an evidence explanation if present, and
limitations. No clinical score is produced.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write, load_json


def _md_field(label: str, value: Any) -> str:
    return f"- **{label}:** {value}\n"


def _validate_session(session) -> None:
    """Validate that the input is a BioGait structured research object.

    Rejects non-dicts, NaN/Infinity, forbidden identity keys, and invalid
    data_origin/processing_mode/provenance enums. Missing optional fields are
    fine (None values allowed).
    """
    if not isinstance(session, dict):
        raise ValueError("session must be a structured dict")
    from evidence_schema import validate_evidence_record
    validate_evidence_record(session)


def build_report(session: dict) -> str:
    _validate_session(session)
    coverage = (
        f"left={session.get('po_coverage', {}).get('left')}; "
        f"right={session.get('po_coverage', {}).get('right')}"
        if isinstance(session.get("po_coverage"), dict)
        else session.get("po_coverage")
    )
    desc = session.get("descriptive") or session.get("session_descriptors") or {}
    ta = session.get("temporal_analysis")

    lines = [
        "# BioGait Research Evidence Report",
        "",
        f"> This is a **research evidence** report. It is NOT a clinical, diagnostic, "
        f"or medical report and contains no clinical score.",
        "",
        "## Session metadata",
        f"- schema_version: {session.get('schema_version')}",
        f"- module: {session.get('module')}",
        f"- exercise: {session.get('exercise')}",
        f"- data_origin: {session.get('data_origin')}",
        f"- processing_mode: {session.get('processing_mode')}",
        f"- session_state: {session.get('session_state')}",
        f"- processed_frames: {session.get('processed_frames')}",
        "",
        "## Data origin",
        f"- {session.get('data_origin', 'UNKNOWN_UNVALIDATED')}",
        "",
        "## Method provenance",
    ]
    provenance = session.get("method_provenance")
    if isinstance(provenance, dict):
        for k, v in provenance.items():
            lines.append(_md_field(k, v))
    else:
        lines.append(f"- {provenance}")

    lines += [
        "",
        "## PO coverage",
        f"- {coverage}",
        "",
        "## Control-factor coverage",
    ]
    cf = session.get("control_factor_coverage")
    if isinstance(cf, dict) and cf:
        for k, v in sorted(cf.items()):
            lines.append(_md_field(k, v))
    else:
        lines.append(f"- {cf}")

    lines += ["", "## Descriptive kinematics"]
    if isinstance(desc, dict) and desc:
        for k, v in sorted(desc.items()):
            lines.append(_md_field(k, v))
    else:
        lines.append("- n/a")

    lines += ["", "## Temporal-analysis status"]
    if isinstance(ta, dict):
        for branch in ("reference", "adapted"):
            node = ta.get(branch) or {}
            if isinstance(node, dict):
                lines.append(
                    f"- {branch}: classification={node.get('classification')}, "
                    f"left={node.get('left')}, right={node.get('right')}"
                )
    else:
        lines.append(f"- {ta}")

    # Quality / runtime summary.
    qs = session.get("quality_summary") or session.get("quality") or {}
    lines += ["", "## Quality / runtime summary"]
    if isinstance(qs, dict) and qs:
        for k, v in sorted(qs.items()):
            lines.append(_md_field(k, v))

    lines += ["", "## Evidence explanation"]
    explanation = session.get("explanation")
    if isinstance(explanation, dict):
        outputs = explanation.get("output") or {}
        lines.append(_md_field("summary", outputs.get("summary")))
        lines.append(f"- observations:\n" + "\n".join(
            f"  - {item}" for item in outputs.get("observations") or []))
        lines.append(_md_field("status", explanation.get("status")))
        lines.append(_md_field("explainer_mode", explanation.get("explainer_mode")))
    else:
        lines.append(f"- {explanation}")

    lines += ["", "## Limitations"]
    limitations = session.get("limitations")
    if isinstance(limitations, list) and limitations:
        for lim in limitations:
            lines.append(f"- {lim}")
    else:
        lines.append(f"- {limitations}")

    lines += ["", "> Descriptive and reference-derived evidence only; not a "
                  "clinical assessment."]
    return "\n".join(lines)


def json_summary(session: dict) -> dict:
    return {
        "schema_version": session.get("schema_version"),
        "data_origin": session.get("data_origin"),
        "processing_mode": session.get("processing_mode"),
        "po_coverage": session.get("po_coverage"),
        "control_factor_coverage": session.get("control_factor_coverage"),
        "descriptive": session.get("descriptive") or session.get("session_descriptors"),
        "temporal_status": session.get("temporal_analysis"),
        "explanation_status": (session.get("explanation") or {}).get("status"),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generate_research_report",
        description="Generate a BioGait Research Evidence Report from a session JSON.",
    )
    p.add_argument("--input", required=True, help="BioGait session JSON")
    p.add_argument("--output", default=None, help="output Markdown path")
    p.add_argument("--json-summary", default=None, help="optional JSON summary path")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    session = load_json(Path(args.input))
    if session is None:
        print("[generate_research_report] ERROR: session not found")
        return 1
    try:
        report = build_report(session)
    except ValueError as exc:
        print(f"[generate_research_report] ERROR: invalid BioGait research session: {exc}")
        return 1
    print(report)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"[generate_research_report] wrote {args.output}")
    if args.json_summary:
        atomic_json_write(Path(args.json_summary), json_summary(session))
        print(f"[generate_research_report] wrote {args.json_summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
