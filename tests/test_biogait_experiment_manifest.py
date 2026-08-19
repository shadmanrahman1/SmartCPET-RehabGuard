"""
Tests for experiments/biogait/experiment_manifest.py (B4, B20).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from common import opaque_key  # noqa: E402
from experiment_manifest import (  # noqa: E402
    build_manifest,
    subject_disjoint_split,
    subject_overlap,
)


def _sequences(n_subjects, per_subject=2):
    seqs = []
    for s in range(n_subjects):
        sk = opaque_key("subject", str(s))
        for i in range(per_subject):
            seqs.append(
                {
                    "dataset_group": "G1",
                    "dataset_subject_key": sk,
                    "exercise": "ex5_squat",
                    "sequence_key": opaque_key(sk, str(i)),
                    "n_frames": 100,
                    "sampling_rate_hz": 30.0,
                }
            )
    return seqs


class ManifestTests(unittest.TestCase):
    def test_deterministic_ordering(self):
        seqs = _sequences(3)
        m1 = build_manifest(seqs, seed=0)
        m2 = build_manifest(list(reversed(seqs)), seed=0)
        self.assertEqual(
            [e["sequence_key"] for e in m1["entries"]],
            [e["sequence_key"] for e in m2["entries"]],
        )
        self.assertEqual(m1["n_sequences"], len(seqs))
        self.assertEqual(m1["n_subjects"], 3)

    def test_entries_have_neutral_keys(self):
        m = build_manifest(_sequences(1))
        entry = m["entries"][0]
        self.assertIn("dataset_group", entry)
        self.assertIn("dataset_subject_key", entry)
        self.assertIn("sequence_key", entry)
        self.assertNotIn("participant_name", entry)
        self.assertNotIn("name", entry)


class SplitTests(unittest.TestCase):
    def test_subject_disjoint_no_overlap(self):
        m = build_manifest(_sequences(8, per_subject=2), seed=1)
        split = subject_disjoint_split(m, test_frac=0.25, val_frac=0.25, seed=1)
        self.assertFalse(subject_overlap(split))
        total_subjects = sum(split["n_subjects"].values())
        self.assertEqual(total_subjects, 8)

    def test_split_reproducible_with_seed(self):
        m = build_manifest(_sequences(8, per_subject=2), seed=2)
        s1 = subject_disjoint_split(m, seed=2)
        s2 = subject_disjoint_split(m, seed=2)
        self.assertEqual(
            [sorted(e["sequence_key"] for e in f) for f in (s1["train"], s1["val"], s1["test"])],
            [sorted(e["sequence_key"] for e in f) for f in (s2["train"], s2["val"], s2["test"])],
        )

    def test_group_stratification_keeps_groups_repr(self):
        seqs = [{"dataset_group": "A", "dataset_subject_key": opaque_key("a", str(i)),
                 "exercise": "ex5", "sequence_key": opaque_key("a seq", str(i))}
                for i in range(3)]
        seqs += [{"dataset_group": "B", "dataset_subject_key": opaque_key("b", str(i)),
                  "exercise": "ex5", "sequence_key": opaque_key("b seq", str(i))}
                 for i in range(3)]
        m = build_manifest(seqs, seed=0)
        split = subject_disjoint_split(m, test_frac=0.5, val_frac=0.0, seed=0, stratify_by="group")
        self.assertFalse(subject_overlap(split))

    def test_split_rejects_no_train(self):
        m = build_manifest(_sequences(4), seed=0)
        with self.assertRaises(ValueError):
            subject_disjoint_split(m, test_frac=0.6, val_frac=0.6, seed=0)

    def test_split_fraction_validation(self):
        m = build_manifest(_sequences(8), seed=0)
        for bad_t, bad_v in ((float("nan"), 0.2), (float("inf"), 0.2), (-0.1, 0.2),
                             (1.0, 0.0), (0.7, 0.4)):
            with self.assertRaises(ValueError):
                subject_disjoint_split(m, test_frac=bad_t, val_frac=bad_v, seed=0)

    def test_valid_fractions_do_not_raise(self):
        m = build_manifest(_sequences(8), seed=0)
        subject_disjoint_split(m, test_frac=0.2, val_frac=0.2, seed=0)


if __name__ == "__main__":
    unittest.main()
