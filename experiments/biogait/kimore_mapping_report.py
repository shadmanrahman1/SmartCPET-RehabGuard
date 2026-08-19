"""KIMORE paper/source discrepancy report (Sprint B, B6).

Automatically produces a machine-readable JSON + Markdown report covering known
paper/source mapping decisions. This documents provenance boundaries; it is NOT
a measurement of any kind.

Sections:
- Knee CF: paper "knee distance" vs reviewed source signed Knee_R.y - Knee_L.y.
- Hand -> MediaPipe wrist applies ONLY to the MediaPipe pipeline, not when
  analyzing native KIMORE skeleton Hand joints.
- CF temporal preprocessing: source has a last-15 trim/filter; Sprint-A live
  MediaPipe CF preprocessing remains deferred.

Example:
    python experiments/biogait/kimore_mapping_report.py --output-dir out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write

MAPPING_REPORT = {
    "report": "KIMORE paper/source mapping decisions",
    "schema_version": "1.0",
    "sections": {
        "knee_cf_discrepancy": {
            "paper": "knee distance (d_k)",
            "reviewed_source_script": "signed Knee_R.y - Knee_L.y (deltayknee = Knee_R(:,2) - Knee_L(:,2))",
            "biogait": {
                "knee_delta_y_m": "source-aligned implementation (REFERENCE_DERIVED equation + ENGINEERING_ADAPTED coordinate transfer)",
                "knee_euclidean_3d_m": "descriptive extra (DESCRIPTIVE / ENGINEERING_ADAPTED); NOT the source d_k",
            },
            "statement": (
                "The KIMORE paper labels d_k as knee distance, while the "
                "reviewed feature-extraction source implements a signed "
                "Y-coordinate difference. BioGait preserves this discrepancy "
                "in provenance rather than silently equating the two."
            ),
        },
        "hand_to_wrist": {
            "paper_role": "Hand",
            "mediapipe_pipeline": (
                "MediaPipe wrist is an ENGINEERING_ADAPTED proxy for the "
                "KIMORE Hand joint; applies ONLY to the MediaPipe pipeline."
            ),
            "kimore_native_skeleton": (
                "When analyzing native KIMORE skeleton data, the native Hand "
                "joint (not MediaPipe wrist) is used directly; the wrist proxy "
                "does not apply."
            ),
        },
        "cf_temporal_preprocessing": {
            "reviewed_source": (
                "The reviewed source later discards the last ~15 samples from "
                "several CF streams and applies filtering to CF streams."
            ),
            "sprint_a_status": (
                "Sprint A implements CF geometry/evidence only; the source "
                "CF temporal trim/filter preprocessing remains DEFERRED for "
                "the live MediaPipe CF pipeline."
            ),
        },
    },
}


def mapping_report_json() -> dict:
    return MAPPING_REPORT


def mapping_report_markdown() -> str:
    lines = [
        "# KIMORE Paper/Source Mapping Decisions (Sprint B)",
        "",
        "This document records known paper/source mapping decisions. It is a "
        "provenance record, not a measurement.",
        "",
        "## Knee CF discrepancy",
        "",
        f"- **Paper:** {MAPPING_REPORT['sections']['knee_cf_discrepancy']['paper']}",
        f"- **Reviewed source script:** {MAPPING_REPORT['sections']['knee_cf_discrepancy']['reviewed_source_script']}",
        f"- **BioGait:**",
        f"  - `knee_delta_y_m` = {MAPPING_REPORT['sections']['knee_cf_discrepancy']['biogait']['knee_delta_y_m']}",
        f"  - `knee_euclidean_3d_m` = {MAPPING_REPORT['sections']['knee_cf_discrepancy']['biogait']['knee_euclidean_3d_m']}",
        "",
        f"> {MAPPING_REPORT['sections']['knee_cf_discrepancy']['statement']}",
        "",
        "## Hand -> wrist proxy scope",
        "",
        f"- {MAPPING_REPORT['sections']['hand_to_wrist']['mediapipe_pipeline']}",
        f"- {MAPPING_REPORT['sections']['hand_to_wrist']['kimore_native_skeleton']}",
        "",
        "## CF temporal preprocessing",
        "",
        f"- **Reviewed source:** {MAPPING_REPORT['sections']['cf_temporal_preprocessing']['reviewed_source']}",
        f"- **Sprint A status:** {MAPPING_REPORT['sections']['cf_temporal_preprocessing']['sprint_a_status']}",
        "",
    ]
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kimore_mapping_report",
        description="Write the KIMORE paper/source mapping report (JSON + Markdown).",
    )
    p.add_argument("--output-dir", default="results/kimore_mapping", help="output directory")
    p.add_argument("--no-markdown", action="store_true", help="write JSON only")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_json_write(out_dir / "kimore_mapping_report.json", mapping_report_json())
    print(f"[kimore_mapping_report] wrote {out_dir / 'kimore_mapping_report.json'}")
    if not args.no_markdown:
        (out_dir / "kimore_mapping_report.md").write_text(mapping_report_markdown(), encoding="utf-8")
        print(f"[kimore_mapping_report] wrote {out_dir / 'kimore_mapping_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
