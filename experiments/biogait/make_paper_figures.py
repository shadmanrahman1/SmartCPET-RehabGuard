"""Paper-ready figure generator (Sprint B, B14).

Generates separate figures with matplotlib (no seaborn). Each figure is only
generated when its input data actually exists — no fabricated curves.
matplotlib is imported lazily so importing this module never requires it.

Figures (data-gated):
- Figure A: reference vs adapted filtered knee-angle trajectory
- Figure B: FPS sensitivity
- Figure C: missingness vs PO availability
- Figure D: runtime latency distribution
- Figure E: feature-availability matrix

Outputs go under experiments/biogait/results/figures/ (or --output-dir).

Example:
    python experiments/biogait/make_paper_figures.py --input-dir results
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from common import load_json


def plots_to_generate(input_dir: Optional[Path]) -> list[dict]:
    """Decide which figures can be generated from available data (side-effect free)."""
    input_dir = Path(input_dir) if input_dir else Path(__file__).resolve().parent / "results"
    plans = []
    session = load_json(input_dir / "session.json") or load_json(input_dir / "batch")
    bench = load_json(input_dir / "benchmark_batch.json")
    fps = load_json(input_dir / "fps_sensitivity.json")
    missing = load_json(input_dir / "missingness_sensitivity.json")

    # Figure A: reference vs adapted filtered trajectory.
    a_data = None
    if session and session.get("temporal_analysis"):
        a_data = {
            "reference": (session.get("temporal_analysis", {}).get("reference", {}) or {}),
            "adapted": (session.get("temporal_analysis", {}).get("adapted", {}) or {}),
        }
    plans.append({"figure": "A", "status": "COMPLETE" if a_data else "PENDING_DATA"})

    plans.append({"figure": "B", "status": "COMPLETE" if fps else "PENDING_DATA"})
    plans.append({"figure": "C", "status": "COMPLETE" if missing else "PENDING_DATA"})

    d_ok = bool(bench and bench.get("summary", {}).get("REAL_VIDEO_BENCHMARK") == "COMPLETE")
    plans.append({"figure": "D", "status": "COMPLETE" if d_ok else "PENDING_DATA"})

    plans.append({"figure": "E", "status": "COMPLETE"})  # synthetic landmark matrix always derivable
    return plans


def render_figures(input_dir: Optional[Path], output_dir: Path) -> list[dict]:
    """Render available figures; returns per-figure status."""
    try:
        import matplotlib
    except Exception as exc:  # noqa: BLE001 - optional dep
        return [{"figure": f, "status": "PENDING_DATA", "reason": f"matplotlib unavailable: {type(exc).__name__}"}
                for f in ("A", "B", "C", "D", "E")]
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from landmark_robustness import availability_matrix

    input_dir = Path(input_dir) if input_dir else Path(__file__).resolve().parent / "results"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    status = []

    def _save(name: str) -> None:
        path = output_dir / name
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()
        status.append({"figure": name[:-4], "status": "saved", "file": str(path.relative_to(output_dir))})

    # Figure A
    session = load_json(input_dir / "session.json")
    if session and session.get("temporal_analysis"):
        ref = (session["temporal_analysis"].get("reference") or {}).get("left", {})
        adapted = (session["temporal_analysis"].get("adapted") or {}).get("left", {})
        ref_sig = ref.get("filtered_signal") if isinstance(ref, dict) else None
        adapted_sig = adapted.get("filtered_signal") if isinstance(adapted, dict) else None
        if isinstance(ref_sig, list) and isinstance(adapted_sig, list):
            a_origin = session.get("data_origin", "UNKNOWN_UNVALIDATED")
            label = "synthetic validation fixture" if a_origin == "SYNTHETIC_FIXTURE" else a_origin
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(ref_sig, label="reference (REFERENCE_DERIVED)")
            ax.plot(adapted_sig, label="adapted (ENGINEERING_ADAPTED)")
            ax.set_xlabel("sample"); ax.set_ylabel("filtered knee angle (deg)")
            ax.set_title(f"Figure A: reference vs adapted filtered trajectory — {label}")
            ax.legend()
            _save("figure_A_trajectory.png")
            status[-1]["origin"] = a_origin
        else:
            status.append({"figure": "A", "status": "PENDING_DATA"})

    # Figure B: FPS sensitivity
    fps = load_json(input_dir / "fps_sensitivity.json")
    if fps and fps.get("rows"):
        fps_origin = fps.get("data_origin", "UNKNOWN_UNVALIDATED")
        label = "synthetic validation fixture" if fps_origin == "SYNTHETIC_FIXTURE" else fps_origin
        left_rows = [r for r in fps["rows"] if r.get("side") == "left"]
        x = [r["fps"] for r in left_rows]
        rom = [r["rom_deg"] for r in left_rows]
        if len(x) == len(rom):
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(x, rom, marker="o")
            ax.set_xlabel("sampling rate (Hz)")
            ax.set_ylabel("left ROM (deg)")
            ax.set_title(f"Figure B: FPS sensitivity — {label}")
            _save("figure_B_fps_sensitivity.png")
            status[-1]["origin"] = fps_origin
        else:
            status.append({"figure": "B", "status": "PENDING_DATA"})
    else:
        status.append({"figure": "B", "status": "PENDING_DATA"})

    # Figure C: missingness vs PO availability
    missing = load_json(input_dir / "missingness_sensitivity.json")
    if missing and missing.get("rows"):
        m_origin = missing.get("data_origin", "UNKNOWN_UNVALIDATED")
        label = "synthetic validation fixture" if m_origin == "SYNTHETIC_FIXTURE" else m_origin
        rows = missing["rows"]
        x = [r["missingness_level"] for r in rows]
        y_po = [r["po_coverage"]["both"] for r in rows]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(x, y_po, marker="o")
        ax.set_xlabel("injected missingness level")
        ax.set_ylabel("both-PO coverage")
        ax.set_title(f"Figure C: missingness vs PO availability — {label}")
        _save("figure_C_missingness.png")
        status[-1]["origin"] = m_origin
    else:
        status.append({"figure": "C", "status": "PENDING_DATA"})

    # Figure D: runtime latency distribution from benchmark batch
    bench = load_json(input_dir / "benchmark_batch.json")
    if bench and bench.get("summary", {}).get("REAL_VIDEO_BENCHMARK") == "COMPLETE":
        means = [r for r in bench.get("per_video", []) if r.get("status") == "ok" and r.get("mean_ms_per_frame") is not None]
        if means:
            # Opaque sequence labels only — never raw filenames.
            labels = ["seq-" + str(r.get("sequence_key", ""))[:6] for r in means]
            vals = [r["mean_ms_per_frame"] for r in means]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(labels, vals)
            ax.set_ylabel("mean ms/frame")
            ax.set_title("Figure D: runtime mean latency per sequence (measured, REAL_VIDEO_MEDIAPIPE)")
            ax.tick_params(axis="x", rotation=45)
            _save("figure_D_runtime.png")
        else:
            status.append({"figure": "D", "status": "PENDING_DATA"})
    else:
        status.append({"figure": "D", "status": "PENDING_DATA"})

    # Figure E: feature-availability matrix
    matrix = availability_matrix()
    key_order = ["left_po", "right_po", "wrist_cf", "torso_cf", "knee_cf", "overall_po_complete"]
    data = [[int(row[k]) for k in key_order] for row in matrix]
    conds = [row["landmark_condition"] for row in matrix]
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(data, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(key_order))); ax.set_xticklabels(key_order, rotation=45, ha="right")
    ax.set_yticks(range(len(conds))); ax.set_yticklabels(conds)
    ax.set_title("Figure E: feature availability matrix — synthetic validation fixture (SYNTHETIC_FIXTURE)")
    fig.colorbar(im)
    _save("figure_E_availability_matrix.png")
    status[-1]["origin"] = "SYNTHETIC_FIXTURE"

    return status


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="make_paper_figures", description="Generate data-gated paper figures.")
    p.add_argument("--input-dir", default=None)
    p.add_argument("--output-dir", default="results/figures")
    p.add_argument("--plan", action="store_true", help="print which figures would be generated, without rendering")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.plan:
        import json
        plans = plots_to_generate(Path(args.input_dir) if args.input_dir else None)
        print(json.dumps(plans, indent=2, allow_nan=False))
        return 0
    status = render_figures(Path(args.input_dir) if args.input_dir else None, Path(args.output_dir))
    import json
    print(json.dumps(status, indent=2, allow_nan=False))
    print(f"[make_paper_figures] rendered figures to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
