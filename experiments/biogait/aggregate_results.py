"""Results aggregator (Sprint B, B12, integrity-corrected).

Combines machine-readable outputs from the evaluation tooling into a single
aggregate JSON plus CSV tables. Provenance is preserved FROM THE RESULT
STRUCTURE ITSELF (never assigned to a whole input file), and every aggregated
record carries BOTH ``method_provenance`` and ``data_origin`` so the aggregate
can answer:

- what method produced this value?  (REFERENCE_DERIVED / ENGINEERING_ADAPTED /
  DESCRIPTIVE / EXPERIMENTAL)
- what data origin produced this value?  (SYNTHETIC_FIXTURE /
  REAL_KIMORE_NATIVE_SKELETON / REAL_VIDEO_MEDIAPIPE / UNKNOWN_UNVALIDATED)

Input metadata is neutral: only input LABELS are persisted (present / missing),
never local paths, filenames, or full result object stringifications.

No clinical scoring is introduced.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write, load_json


def _scalar(v) -> bool:
    return isinstance(v, (int, float, str, bool)) or v is None


def _ex5_or_session_records(data: dict) -> list[dict]:
    origin = data.get("data_origin", "UNKNOWN_UNVALIDATED")
    records: list[dict] = []
    ta = data.get("temporal_analysis") or {}
    for branch, cls in (("reference", "REFERENCE_DERIVED"), ("adapted", "ENGINEERING_ADAPTED")):
        node = ta.get(branch) or {}
        for side in ("left", "right"):
            side_node = node.get(side) or {}
            for k, v in side_node.items():
                records.append({
                    "method_provenance": cls, "data_origin": origin,
                    "key": f"temporal_analysis.{branch}.{side}.{k}", "value": v,
                })
    for k, v in (data.get("descriptive") or {}).items():
        records.append({
            "method_provenance": "DESCRIPTIVE", "data_origin": origin,
            "key": f"descriptive.{k}", "value": v,
        })
    return records


def _fps_records(data: dict) -> list[dict]:
    origin = data.get("data_origin", "UNKNOWN_UNVALIDATED")
    records: list[dict] = []
    for row in data.get("rows", []):
        cls = row.get("classification", "UNKNOWN")
        for k, v in row.items():
            if k in ("classification", "side", "fps", "data_origin"):
                continue
            if k == "drift_vs_30hz" and isinstance(v, dict):
                for dk, dv in v.items():
                    records.append({
                        "method_provenance": cls, "data_origin": origin,
                        "key": f"fps.{row.get('fps')}.drift.{dk}", "value": dv,
                    })
            elif _scalar(v):
                records.append({
                    "method_provenance": cls, "data_origin": origin,
                    "key": f"fps.{row.get('fps')}.{k}", "value": v,
                })
    return records


def _experiment_records(data: dict, cls: str) -> list[dict]:
    origin = data.get("data_origin", "UNKNOWN_UNVALIDATED")
    records: list[dict] = []
    for row in data.get("rows", []):
        for k, v in row.items():
            if k == "data_origin":
                continue
            if isinstance(v, dict):
                for dk, dv in v.items():
                    if _scalar(dv):
                        records.append({
                            "method_provenance": cls, "data_origin": origin,
                            "key": f"{data.get('experiment')}.{k}.{dk}", "value": dv,
                        })
            elif _scalar(v):
                records.append({
                    "method_provenance": cls, "data_origin": origin,
                    "key": f"{data.get('experiment')}.{k}", "value": v,
                })
    return records


def _benchmark_records(data: dict) -> list[dict]:
    origin = data.get("data_origin", "REAL_VIDEO_MEDIAPIPE")
    records: list[dict] = []
    agg = (data.get("aggregate") or data.get("summary", {}).get("aggregate") or {})
    for k, v in agg.items():
        if _scalar(v):
            records.append({
                "method_provenance": "ENGINEERING_ADAPTED", "data_origin": origin,
                "key": f"benchmark.aggregate.{k}", "value": v,
            })
    return records


def _generic_records(data: Any, provenance: str) -> list[dict]:
    origin = data.get("data_origin", "UNKNOWN_UNVALIDATED") if isinstance(data, dict) else "UNKNOWN_UNVALIDATED"
    records: list[dict] = []

    def _walk(value, path: str):
        if isinstance(value, dict):
            for k, v in value.items():
                _walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                _walk(item, f"{path}[{i}]")
        elif _scalar(value):
            records.append({
                "method_provenance": provenance, "data_origin": origin,
                "key": path or "value", "value": value,
            })

    _walk(data, "")
    return records


def aggregate(inputs: dict[str, Path]) -> dict[str, Any]:
    """Aggregate the provided (label -> path) result files (paths not persisted)."""
    per_provenance: dict[str, list[dict]] = {}
    present_labels: list[str] = []
    missing_labels: list[str] = []

    for label, path in inputs.items():
        path = Path(path)
        if not path.exists():
            missing_labels.append(label)
            continue
        data = load_json(path)
        present_labels.append(label)
        if isinstance(data, dict) and "temporal_analysis" in data:
            records = _ex5_or_session_records(data)
        elif isinstance(data, dict) and data.get("experiment") == "fps_sensitivity":
            records = _fps_records(data)
        elif isinstance(data, dict) and data.get("experiment") in (
            "missingness_sensitivity", "landmark_robustness",
        ):
            cls = "EXPERIMENTAL"
            records = _experiment_records(data, cls)
        elif isinstance(data, dict) and data.get("summary") and isinstance(data["summary"], dict):
            records = _benchmark_records(data)
        else:
            records = _generic_records(data, "UNKNOWN")
        for rec in records:
            per_provenance.setdefault(rec["method_provenance"], []).append(
                {**rec, "source": label}
            )

    return {
        "experiment": "aggregate_results",
        "schema_version": "1.0",
        "inputs_present": sorted(present_labels),
        "inputs_missing": sorted(missing_labels),
        "records_by_provenance": {
            k: len(v) for k, v in per_provenance.items()
        },
        "per_provenance": per_provenance,
        "note": (
            "method_provenance and data_origin are preserved from each result "
            "structure; provenance is never inferred from a whole input label. "
            "No local paths or filenames are persisted."
        ),
    }


def write_csv_tables(aggregate: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_records = []
    fieldnames = ["source", "method_provenance", "data_origin", "key", "value"]
    for provenance, records in aggregate["per_provenance"].items():
        all_records.extend(records)

    for provenance, records in aggregate["per_provenance"].items():
        path = output_dir / f"aggregate_{provenance.lower()}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(record)

    combined = output_dir / "aggregate_all.csv"
    with open(combined, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in all_records:
            writer.writerow({k: v for k, v in record.items() if k in fieldnames})


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aggregate_results", description="BioGait results aggregator.")
    p.add_argument("--inputs", required=True, help="JSON map label->path of result files to aggregate")
    p.add_argument("--output-dir", required=True, help="output directory for aggregate JSON + CSVs")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    inputs = {k: Path(v) for k, v in json.loads(args.inputs).items()}
    result = aggregate(inputs)
    out_dir = Path(args.output_dir)
    atomic_json_write(out_dir / "aggregate.json", result)
    write_csv_tables(result, out_dir)
    print(json.dumps(result, indent=2, allow_nan=False))
    print(f"[aggregate_results] wrote {out_dir / 'aggregate.json'} + CSV tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
