"""Results aggregator (Sprint B, B12).

Combines machine-readable outputs from the evaluation tooling (session JSON,
KIMORE evaluation JSON, FPS sensitivity JSON, missingness JSON, benchmark JSON)
into a single machine-readable aggregate JSON plus CSV tables.

Provenance is never mixed: every aggregated record is tagged with exactly one of
REFERENCE_DERIVED / ENGINEERING_ADAPTED / DESCRIPTIVE, and per-provenance CSV
tables are written. No clinical scoring is introduced.

Only inputs that actually exist are aggregated. Example --inputs map:
    reference: path/to/reference.json
    evaluation: path/to/evaluation.json
    fps_sensitivity: path/to/fps.json
    missingness: path/to/missing.json
    benchmark: path/to/benchmark.json

Example:
    python experiments/biogait/aggregate_results.py \
        --inputs '{"evaluation":"out/ex5.json","fps_sensitivity":"out/fps.json"}' \
        --output-dir out
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write, load_json

# label -> provenance category for a top-level input file.
PROVENANCE_BY_INPUT = {
    "reference": "REFERENCE_DERIVED",
    "adapted": "ENGINEERING_ADAPTED",
    "descriptive": "DESCRIPTIVE",
    "evaluation": "REFERENCE_DERIVED",  # source-aligned engine on native skeleton
    "fps_sensitivity": "ENGINEERING_ADAPTED",
    "missingness": "ENGINEERING_ADAPTED",
    "benchmark": "ENGINEERING_ADAPTED",
    "batch": "ENGINEERING_ADAPTED",
}


def _tag_records(container: Any, provenance: str) -> list[dict]:
    """Flatten a loaded JSON blob into provenance-tagged records.

    Preserves structure; every record gains a ``provenance`` and a
    ``source`` (input label). Only enumerable lists/dicts are flattened so the
    output remains machine-readable.
    """
    records: list[dict] = []

    def _walk(value, path: str):
        if isinstance(value, dict):
            records.append({"provenance": provenance, "source": path, "keys": sorted(value.keys())})
            for k, v in value.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                _walk(item, f"{path}[{i}]")
        else:
            records.append({"provenance": provenance, "source": path, "value": value})

    _walk(container, "root")
    return records


def aggregate(inputs: dict[str, Path]) -> dict[str, Any]:
    """Aggregate the provided (label -> path) result files."""
    per_provenance: dict[str, list[dict]] = {
        "REFERENCE_DERIVED": [],
        "ENGINEERING_ADAPTED": [],
        "DESCRIPTIVE": [],
        "UNCLASSIFIED": [],
    }
    present = {}
    missing = {}
    for label, path in inputs.items():
        path = Path(path)
        if not path.exists():
            missing[label] = str(path)
            continue
        data = load_json(path)
        present[label] = data
        provenance = PROVENANCE_BY_INPUT.get(label, "UNCLASSIFIED")
        per_provenance[provenance].extend(_tag_records(data, provenance))

    return {
        "experiment": "aggregate_results",
        "schema_version": "1.0",
        "inputs_present": {k: str(v) for k, v in present.items()},
        "inputs_missing": missing,
        "records_by_provenance": {
            k: len(v) for k, v in per_provenance.items()
        },
        "per_provenance": per_provenance,
        "note": "Provenance categories are never mixed; no clinical scoring.",
    }


def write_csv_tables(aggregate: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_records = []
    for provenance, records in aggregate["per_provenance"].items():
        all_records.extend(records)
        path = output_dir / f"aggregate_{provenance.lower()}.csv"
        fieldnames = ["provenance", "source", "value", "keys"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(record)
    # A combined table with an explicit provenance column (never mixed silently).
    combined = output_dir / "aggregate_all.csv"
    fieldnames = ["provenance", "source", "value"]
    with open(combined, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in all_records:
            writer.writerow({k: (v if isinstance(v, (str, int, float)) or v is None else json.dumps(v)) for k, v in record.items()})


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
