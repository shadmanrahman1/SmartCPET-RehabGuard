"""
Tests for experiments/biogait/kimore_adapter.py (B3, B20).

Uses synthetic fixtures only — no real KIMORE dataset, no download, no camera.
Skipped automatically if a real dataset is required (it is not, here).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPERIMENTS = REPO / "experiments" / "biogait"
sys.path.insert(0, str(EXPERIMENTS))

from kimore_adapter import (  # noqa: E402
    KIMORE_DATASET_ROOT_ENV,
    JOINT_ROLE_CANDIDATES,
    discover_root,
    normalized_ex5_sequence,
    parse_joint_table,
    synthetic_ex5_sequence,
)
from kimore_adapter import _match_role  # noqa: E402


class RoleMappingTests(unittest.TestCase):
    def test_matches_axis_suffixes(self):
        self.assertEqual(_match_role("L_HIP_x"), ("left_hip", "x"))
        self.assertEqual(_match_role("R_KNEE_Y"), ("right_knee", "y"))
        self.assertEqual(_match_role("L_ANK_z"), ("left_ankle", "z"))

    def test_matches_candidates(self):
        self.assertEqual(_match_role("LEFT_SHOULDER_X")[0], "left_shoulder")

    def test_no_match_for_unknown(self):
        self.assertIsNone(_match_role("FOO_BAR_x"))

    def test_roles_cover_ex5_needs(self):
        for role in ("left_shoulder", "right_shoulder", "left_hand", "right_hand",
                     "left_hip", "right_hip", "left_knee", "right_knee",
                     "left_ankle", "right_ankle"):
            self.assertIn(role, JOINT_ROLE_CANDIDATES)


class SyntheticFixtureTests(unittest.TestCase):
    def test_synthetic_produces_normalized_sequence(self):
        seq = synthetic_ex5_sequence(n_frames=120, fs=30.0, seed=0)
        self.assertEqual(seq["exercise"], "ex5_squat")
        self.assertEqual(seq["n_frames"], 120)
        self.assertEqual(seq["sampling_rate_hz"], 30.0)
        self.assertEqual(len(seq["joints"]["left_knee"]["z"]), 120)
        self.assertEqual(len(seq["timestamps_s"]), 120)

    def test_synthetic_has_opaque_keys(self):
        seq = synthetic_ex5_sequence(n_frames=120, fs=30.0, seed=1)
        self.assertTrue(seq["dataset_subject_key"])
        self.assertTrue(seq["sequence_key"])

    def test_synthetic_knee_angle_varies(self):
        from common import to_landmarks
        from evidence_features import kimore_reference_sagittal_knee_angle_yz

        seq = synthetic_ex5_sequence(n_frames=120, fs=30.0, seed=0)
        angles = []
        for i in range(120):
            lm = to_landmarks(seq["joints"], i)
            a = kimore_reference_sagittal_knee_angle_yz(
                lm.get("left_hip"), lm.get("left_knee"), lm.get("left_ankle")
            )
            angles.append(a)
        distinct = {round(a, 1) for a in angles if a is not None}
        self.assertGreater(len(distinct), 5)


class ParseAndDiscoverTests(unittest.TestCase):
    def test_parse_csv_table(self):
        import csv
        import math

        rows = [["L_HIP_x", "L_HIP_y", "L_HIP_z", "R_KNEE_x", "R_KNEE_y", "R_KNEE_z"]]
        for i in range(4):
            rows.append([str(float(i)), "1.0", "0.0", "0.3", "0.5", str(math.sin(i))])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "joints.csv"
            with open(path, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rows)
            joints = parse_joint_table(path)
            self.assertIsNotNone(joints)
            self.assertIn("left_hip", joints)
            self.assertIn("right_knee", joints)
            self.assertEqual(len(joints["left_hip"]["x"]), 4)

    def test_discover_root_synthetic_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            g = root / "healthy"; g.mkdir()
            s = g / "subject_a"; s.mkdir()
            (s / "data.csv").write_text("x,y\n1,2\n", encoding="utf-8")
            report = discover_root(root)
            self.assertTrue(report["candidate_data_files"])
            self.assertEqual(report["validation_status"], "present")

    def test_discover_root_missing_dir_raises(self):
        with self.assertRaises(ValueError):
            discover_root(Path("definitely_missing_dir_xyz"))

    def test_normalize_sequence_dict(self):
        joints = {"left_knee": {"x": [1.0], "y": [2.0], "z": [3.0]}}
        seq = normalized_ex5_sequence(joints, sequence_key="k")
        self.assertEqual(seq["n_frames"], 1)
        self.assertEqual(seq["joints"]["left_knee"]["y"], [2.0])


if __name__ == "__main__":
    unittest.main()
