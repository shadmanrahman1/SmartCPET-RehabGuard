"""Paper-ready table generator (Sprint B, B13).

Generates Markdown + CSV tables:

- TABLE 1: BioGait component / input / output / provenance / validation status
- TABLE 2: KIMORE Exercise-5 source-to-BioGait feature mapping
- TABLE 3: evaluation protocol
- TABLE 4: landmark/missingness robustness (data-gated)
- TABLE 5: runtime benchmark (ONLY when measured runtime data exists)
- TABLE 6: FPS sensitivity (ONLY when experiment data exists)

No placeholder numeric values. If a numeric table's data is unavailable, the
table is either omitted or marked PENDING_DATA (never fake numbers).

Example:
    python experiments/biogait/make_paper_tables.py --input-dir results --output-dir paper
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

from common import load_json

TABLE1 = [
    {"component": "Sagittal knee angle (KIMORE Ex5)", "input": "world/projected hip,knee,ankle",
     "output": "left/right knee angle (deg)", "provenance": "REFERENCE_DERIVED equation + ENGINEERING_ADAPTED transfer", "validation": "None claimed"},
    {"component": "Source-aligned reference temporal analysis", "input": "complete 30 Hz knee-angle stream + uniform 30 Hz timestamps",
     "output": "candidate events (maxima/minima), per-side summary", "provenance": "REFERENCE_DERIVED (offline)", "validation": "None claimed (events are candidates)"},
    {"component": "Adapted temporal analysis", "input": "knee-angle stream at actual fs + uniform timestamps",
     "output": "candidate events at the actual frame rate", "provenance": "ENGINEERING_ADAPTED", "validation": "None claimed"},
    {"component": "Reference zero-phase filter", "input": "complete finite knee-angle stream",
     "output": "filtered signal (order 3, 1 Hz, 30 Hz, ba + filtfilt)", "provenance": "REFERENCE_DERIVED (offline)", "validation": "None claimed"},
    {"component": "Adapted zero-phase filter", "input": "complete finite stream + actual fs",
     "output": "filtered signal at actual fs", "provenance": "ENGINEERING_ADAPTED", "validation": "None claimed"},
    {"component": "Control factors geometry", "input": "world/projected joints",
     "output": "distances, knee_delta_y_m, torso area, shoulder x/z", "provenance": "REFERENCE_DERIVED equations + ENGINEERING_ADAPTED transfer; knee_euclidean_3d_m is DESCRIPTIVE", "validation": "None claimed"},
    {"component": "Descriptive session metrics", "input": "valid angle+time streams",
     "output": "ROM, angular velocity, ROM difference", "provenance": "DESCRIPTIVE", "validation": "None claimed"},
]

TABLE2 = [
    {"kimore_source": "Sagittal knee angle (feat_extract_Ex5.m)", "biogait": "atan2(hip_y-knee_y,hip_z-knee_z)+atan2(knee_y-ankle_y,ankle_z-knee_z)",
     "provenance": "REFERENCE_DERIVED (equation) / ENGINEERING_ADAPTED (transfer)"},
    {"kimore_source": "angle = angle(10:end) (1-based)", "biogait": "discard first 9 zero-based Python samples (values[9:])",
     "provenance": "REFERENCE_DERIVED"},
    {"kimore_source": "sign flip when consecutive diff outside [-100,+100]", "biogait": "negate sample; NOT ±360 unwrap",
     "provenance": "REFERENCE_DERIVED"},
    {"kimore_source": "butter(order3,1Hz,30Hz) + filtfilt", "biogait": "ba-form butter + filtfilt (fixed reference params)",
     "provenance": "REFERENCE_DERIVED"},
    {"kimore_source": "maxima at max/sqrt(2), minima on max-signal", "biogait": "find_peaks at max/sqrt(2); min peak distance floor(n/10)",
     "provenance": "REFERENCE_DERIVED"},
    {"kimore_source": "d_k = 'knee distance' (paper) vs deltayknee signed Y (script)", "biogait": "knee_delta_y_m (reference) + knee_euclidean_3d_m (descriptive, NOT source d_k)",
     "provenance": "REFERENCE_DERIVED equation + ENGINEERING_ADAPTED transfer / DESCRIPTIVE"},
]

TABLE3 = [
    {"step": "Dataset", "detail": "Local KIMORE Ex5 skeletal data via kimore_adapter (no auto-download; REAL validation PENDING without licensed data)"},
    {"step": "Geometry", "detail": "Source-aligned knee PO + CF geometry via evidence_features"},
    {"step": "Temporal", "detail": "Source-aligned reference path (30 Hz) + adapted path at actual fs"},
    {"step": "Experiment", "detail": "FPS sensitivity, missingness robustness, landmark robustness, runtime benchmark"},
    {"step": "Reporting", "detail": "Provenance-tagged aggregate + paper tables/figures; no clinical scoring"},
]


def _table_md(title: str, headers: list[str], rows: list[list[str]]) -> str:
    lines = [f"## {title}", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines)


def build_tables(input_dir: Optional[Path]) -> dict:
    input_dir = Path(input_dir) if input_dir else Path(__file__).resolve().parent / "results"

    # TABLE 4: landmark robustness (always derivable synthetically).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from landmark_robustness import availability_matrix
    matrix = availability_matrix()
    table4_headers = list(matrix[0].keys())
    table4 = {
        "status": "SYNTHETIC_ONLY",
        "headers": table4_headers,
        "rows": [[str(v) for v in row.values()] for row in matrix],
        "note": (
            "Software/algorithm validation on a deterministic synthetic "
            "fixture; not an empirical KIMORE or participant result."
        ),
    }

    # TABLE 5: runtime benchmark — EMPIRICAL_COMPLETE only from real video.
    bench = load_json(input_dir / "benchmark_batch.json")
    if bench and bench.get("summary", {}).get("REAL_VIDEO_BENCHMARK") == "COMPLETE":
        s = bench["summary"]
        table5 = {
            "status": "EMPIRICAL_COMPLETE",
            "headers": ["metric", "value"],
            "rows": [
                ["n_videos", str(s["n_videos"])],
                ["n_success", str(s["n_success"])],
                ["total_frames", str(s["aggregate"]["total_frames"])],
                ["mean_ms_per_frame_over_videos", str(s["aggregate"]["mean_ms_per_frame_over_videos"])],
                ["mean_of_video_p95_ms_per_frame", str(s["aggregate"]["mean_of_video_p95_ms_per_frame"])],
                ["overall_world_landmark_availability_rate", str(s["aggregate"]["overall_world_landmark_availability_rate"])],
                ["effective_throughput_fps_over_videos", str(s["aggregate"]["effective_throughput_fps_over_videos"])],
            ],
        }
    else:
        table5 = {"status": "PENDING_DATA", "headers": ["status", "value"], "rows": [["REAL_VIDEO_BENCHMARK", "PENDING"]], "note": "no real-video benchmark measurement"}

    # TABLE 6: FPS sensitivity — synthetic vs empirical by data_origin.
    fps = load_json(input_dir / "fps_sensitivity.json")
    fps_status = "PENDING_DATA"
    fps_note = None
    if fps and fps.get("rows"):
        origin = fps.get("data_origin", "UNKNOWN_UNVALIDATED")
        fps_status = "EMPIRICAL_COMPLETE" if origin in ("REAL_KIMORE_NATIVE_SKELETON",) else "SYNTHETIC_ONLY"
        if fps_status == "SYNTHETIC_ONLY":
            fps_note = ("Software/algorithm validation on a deterministic synthetic fixture; "
                        "not an empirical KIMORE or participant result.")
        headers = ["side", "fps", "classification", "rom_deg", "peak_abs_angular_velocity_deg_s", "n_event_candidates", "rom_drift_abs"]
        table6 = {
            "status": fps_status,
            "headers": headers,
            "rows": [
                [
                    str(r.get("side")), str(r.get("fps")), str(r.get("classification")),
                    _fmt(r.get("rom_deg")), _fmt(r.get("peak_abs_angular_velocity_deg_s")),
                    str(r.get("n_event_candidates")),
                    _fmt((r.get("drift_vs_30hz") or {}).get("rom_drift_abs")),
                ]
                for r in fps.get("rows", [])
            ],
            "note": fps_note,
        }
    else:
        table6 = {"status": "PENDING_DATA", "headers": ["status"], "rows": [["FPS_SENSITIVITY=PENDING"]]}

    return {
        "table1_components": {"status": "COMPLETE", "headers": list(TABLE1[0].keys()), "rows": [[str(r[h]) for h in TABLE1[0].keys()] for r in TABLE1]},
        "table2_kimore_mapping": {"status": "COMPLETE", "headers": list(TABLE2[0].keys()), "rows": [[str(r[h]) for h in TABLE2[0].keys()] for r in TABLE2]},
        "table3_protocol": {"status": "COMPLETE", "headers": ["step", "detail"], "rows": [[r["step"], r["detail"]] for r in TABLE3]},
        "table4_robustness": table4,
        "table5_benchmark": table5,
        "table6_fps": table6,
    }


def _fmt(v) -> str:
    return "None" if v is None else str(v)


def render_markdown(tables: dict) -> str:
    out = ["# BioGait Paper-Ready Tables (Sprint B)", ""]
    section_notes = {
        "table1_components": "Status: COMPLETE (structural; no numeric claims).",
        "table2_kimore_mapping": "Status: COMPLETE (provenance mapping).",
        "table3_protocol": "Status: COMPLETE (protocol description).",
        "table4_robustness": f"Status: {tables['table4_robustness']['status']}.",
        "table5_benchmark": f"Status: {tables['table5_benchmark']['status']}.",
        "table6_fps": f"Status: {tables['table6_fps']['status']}.",
    }
    titles = {
        "table1_components": "TABLE 1: BioGait components",
        "table2_kimore_mapping": "TABLE 2: KIMORE Ex5 source-to-BioGait mapping",
        "table3_protocol": "TABLE 3: Evaluation protocol",
        "table4_robustness": "TABLE 4: Landmark/missingness robustness",
        "table5_benchmark": "TABLE 5: Runtime benchmark",
        "table6_fps": "TABLE 6: FPS sensitivity",
    }
    for key in ("table1_components", "table2_kimore_mapping", "table3_protocol",
                "table4_robustness", "table5_benchmark", "table6_fps"):
        table = tables[key]
        out.append(_table_md(titles[key], table["headers"], table["rows"]))
        out.append(f"> {section_notes[key]}")
        note = table.get("note")
        if note:
            out.append(f"> {note}")
        out.append("")
    out.append(
        "> Status classes: EMPIRICAL_COMPLETE = real measured data; "
        "SYNTHETIC_ONLY = deterministic synthetic validation (not participant/"
        "dataset results); PENDING_DATA = no data, no fabricated numbers."
    )
    return "\n".join(out)


def write_csv(name: str, headers: list[str], rows: list[list[str]], out_dir: Path) -> None:
    with open(out_dir / name, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="make_paper_tables", description="Generate paper-ready tables.")
    p.add_argument("--input-dir", default=None, help="directory holding experiment result JSONs")
    p.add_argument("--output-dir", default="results/paper", help="output directory")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = build_tables(Path(args.input_dir) if args.input_dir else None)
    (out_dir / "paper_tables.md").write_text(render_markdown(tables), encoding="utf-8")
    for name, table in (("table1.csv", tables["table1_components"]), ("table2.csv", tables["table2_kimore_mapping"]), ("table3.csv", tables["table3_protocol"]), ("table4.csv", tables["table4_robustness"])):
        write_csv(name, table["headers"], table["rows"], out_dir)
    write_csv("table5.csv", tables["table5_benchmark"]["headers"], tables["table5_benchmark"]["rows"], out_dir)
    write_csv("table6.csv", tables["table6_fps"]["headers"], tables["table6_fps"]["rows"], out_dir)
    print(f"[make_paper_tables] wrote tables to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
