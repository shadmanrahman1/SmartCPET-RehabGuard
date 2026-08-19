"""Reproducible dataset enumeration + subject-disjoint split tooling (Sprint B).

Purpose: reproducible dataset enumeration and future subject-disjoint
evaluation. This is infrastructure ONLY — no ML model is trained in Sprint B.

Policies:
- Never expose local raw paths in committed result files.
- Use neutral opaque keys: ``dataset_group``, ``dataset_subject_key``,
  ``exercise``, ``sequence_key``. Never participant names.
- Do not copy demographics unless explicitly required later.
- Deterministic ordering: entries are sorted by (group, subject_key,
  sequence_key).
- Subject-disjoint splits: a subject may never appear across multiple folds;
  a fixed random seed is stored in the manifest.

No clinical claims are made by this module.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from common import atomic_json_write

MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass
class ManifestEntry:
    dataset_group: str
    dataset_subject_key: str
    exercise: str
    sequence_key: str
    n_frames: int = 0
    sampling_rate_hz: Optional[float] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dataset_group": self.dataset_group,
            "dataset_subject_key": self.dataset_subject_key,
            "exercise": self.exercise,
            "sequence_key": self.sequence_key,
            "n_frames": self.n_frames,
            "sampling_rate_hz": self.sampling_rate_hz,
            **self.extra,
        }

    def subject_key(self) -> tuple[str, str]:
        return (self.dataset_group, self.dataset_subject_key)


def build_manifest(
    sequences: Iterable[dict],
    seed: int = 0,
) -> dict[str, Any]:
    """Build a manifest from sequence dicts (neutral keys).

    ``sequences`` are dicts containing ``dataset_group``,
    ``dataset_subject_key``, ``sequence_key``, ``exercise``, and optionally
    ``n_frames`` / ``sampling_rate_hz``. Entries are deterministically ordered
    by (group, subject_key, sequence_key).
    """
    entries = []
    for seq in sequences:
        entries.append(
            ManifestEntry(
                dataset_group=str(seq.get("dataset_group", "unknown")),
                dataset_subject_key=str(seq.get("dataset_subject_key", "unknown")),
                exercise=str(seq.get("exercise", "unknown")),
                sequence_key=str(seq.get("sequence_key", "unknown")),
                n_frames=int(seq.get("n_frames", 0)),
                sampling_rate_hz=(
                    float(seq["sampling_rate_hz"])
                    if seq.get("sampling_rate_hz") is not None
                    else None
                ),
            )
        )
    entries.sort(key=lambda e: (e.dataset_group, e.dataset_subject_key, e.sequence_key))
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "seed": int(seed),
        "n_sequences": len(entries),
        "n_subjects": len({e.subject_key() for e in entries}),
        "entries": [e.to_dict() for e in entries],
    }


def save_manifest(manifest: dict, path: Path) -> None:
    atomic_json_write(path, manifest)


def subject_disjoint_split(
    manifest: dict,
    *,
    test_frac: float = 0.2,
    val_frac: float = 0.2,
    seed: int = 0,
    stratify_by: Optional[str] = None,
) -> dict[str, Any]:
    """Return a subject-disjoint train/val/test split (infrastructure only).

    Splits by SUBJECT, never by individual frames: a subject (group,
    subject_key) appears in exactly one fold. A fixed seed makes the split
    reproducible. When ``stratify_by="group"``, subjects are stratified by
    ``dataset_group`` before assignment.
    """
    entries = [ManifestEntry(**{k: e[k] for k in (
        "dataset_group", "dataset_subject_key", "exercise", "sequence_key",
        "n_frames", "sampling_rate_hz",
    ) if k in e}, extra={}) for e in manifest.get("entries", [])]

    subjects: dict[tuple[str, str], list[ManifestEntry]] = {}
    for e in entries:
        subjects.setdefault(e.subject_key(), []).append(e)

    subjects_list = list(subjects.keys())

    rng = random.Random(int(seed))
    if stratify_by == "group":
        groups: dict[str, list] = {}
        for sk in subjects_list:
            groups.setdefault(sk[0], []).append(sk)
        ordered: list = []
        for g in sorted(groups.keys()):
            shuffled = groups[g]
            rng.shuffle(shuffled)
            ordered.extend(shuffled)
    else:
        ordered = subjects_list
        rng.shuffle(ordered)

    n = len(ordered)
    n_test = int(round(n * test_frac))
    n_val = int(round(n * val_frac))
    n_train = n - n_test - n_val
    if n_train <= 0:
        raise ValueError("test_frac + val_frac leave no training subjects")

    train_subjects = ordered[:n_train]
    val_subjects = ordered[n_train:n_train + n_val]
    test_subjects = ordered[n_train + n_val:]

    def _fold(subject_list) -> list[dict]:
        out = []
        for sk in subject_list:
            out.extend(e.to_dict() for e in subjects[sk])
        return out

    split = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "seed": int(seed),
        "test_frac": test_frac,
        "val_frac": val_frac,
        "stratify_by": stratify_by,
        "n_subjects": {"train": len(train_subjects), "val": len(val_subjects), "test": len(test_subjects)},
        "n_sequences": {
            "train": len(_fold(train_subjects)),
            "val": len(_fold(val_subjects)),
            "test": len(_fold(test_subjects)),
        },
        "train": _fold(train_subjects),
        "val": _fold(val_subjects),
        "test": _fold(test_subjects),
    }
    return split


def subject_overlap(split: dict) -> bool:
    """True if any subject appears in more than one fold (should never happen)."""
    def _subject_keys(fold):
        return {(e["dataset_group"], e["dataset_subject_key"]) for e in fold}

    train = _subject_keys(split.get("train", []))
    val = _subject_keys(split.get("val", []))
    test = _subject_keys(split.get("test", []))
    return bool(train & val or train & test or val & test)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="experiment_manifest",
        description="BioGait dataset manifest + subject-disjoint split (infra only).",
    )
    p.add_argument("--input", required=True, help="manifest or sequences JSON (list or {entries:[]})")
    p.add_argument("--output", required=True, help="output manifest JSON")
    p.add_argument("--split", default=None, help="optional output split JSON path")
    p.add_argument("--test-frac", type=float, default=0.2)
    p.add_argument("--val-frac", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--stratify-by-group", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    sequences = data.get("entries", data) if isinstance(data, dict) else data
    manifest = build_manifest(sequences, seed=args.seed)
    save_manifest(manifest, Path(args.output))
    print(json.dumps(manifest, indent=2, allow_nan=False))
    print(f"[experiment_manifest] wrote {args.output}")
    if args.split:
        split = subject_disjoint_split(
            manifest,
            test_frac=args.test_frac,
            val_frac=args.val_frac,
            seed=args.seed,
            stratify_by="group" if args.stratify_by_group else None,
        )
        atomic_json_write(Path(args.split), split)
        print(f"[experiment_manifest] wrote split {args.split}")
        print(f"[experiment_manifest] subject overlap: {subject_overlap(split)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
