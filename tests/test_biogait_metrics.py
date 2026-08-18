"""
Lightweight tests for biogait/metrics.py mathematical primitives.

These tests only cover STABLE mathematical/runtime primitives.
They do NOT canonize clinical thresholds as medically correct.

The current risk scoring is a legacy rule-based experimental screening
baseline and is not clinically validated. See AGENTS.md.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

# Make biogait importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from metrics import (  # noqa: E402
    angle_between_points,
    average_visibility,
    calculate_pose_metrics,
    calculate_risk_score,
    midpoint,
    missing_landmarks,
    no_pose_metrics,
    points_are_visible,
    add_session_fields,
    REQUIRED_POINTS,
)


# ── Test helpers ────────────────────────────────────────────────────────────────

def _lm(x: float, y: float, visibility: float = 1.0) -> dict:
    """Build a synthetic landmark dict matching metrics.py expectations."""
    return {"x": x, "y": y, "z": 0.0, "visibility": visibility}


def _full_landmarks(visibility: float = 1.0) -> dict[str, dict[str, float]]:
    """Build a complete landmark dict with all 8 required points visible."""
    return {
        "left_shoulder": _lm(0.4, 0.3, visibility),
        "right_shoulder": _lm(0.6, 0.3, visibility),
        "left_hip": _lm(0.45, 0.6, visibility),
        "right_hip": _lm(0.55, 0.6, visibility),
        "left_knee": _lm(0.43, 0.75, visibility),
        "right_knee": _lm(0.57, 0.75, visibility),
        "left_ankle": _lm(0.42, 0.9, visibility),
        "right_ankle": _lm(0.58, 0.9, visibility),
    }


# ── Mathematical primitives ─────────────────────────────────────────────────────

class TestAngleBetweenPoints(unittest.TestCase):
    def test_straight_line_returns_180(self):
        # hip -> knee -> ankle on a straight horizontal line
        a = _lm(0.0, 0.5)
        b = _lm(0.5, 0.5)
        c = _lm(1.0, 0.5)
        angle = angle_between_points(a, b, c)
        self.assertAlmostEqual(angle, 180.0, places=4)

    def test_perpendicular_returns_90(self):
        a = _lm(0.5, 0.0)
        b = _lm(0.5, 0.5)
        c = _lm(1.0, 0.5)
        angle = angle_between_points(a, b, c)
        self.assertAlmostEqual(angle, 90.0, places=4)

    def test_returned_returns_180(self):
        # angle at knee when knee is between hip and ankle (straight leg)
        hip = _lm(0.5, 0.0)
        knee = _lm(0.5, 0.5)
        ankle = _lm(0.5, 1.0)
        angle = angle_between_points(hip, knee, ankle)
        self.assertAlmostEqual(angle, 180.0, places=4)

    def test_degenerate_returns_zero(self):
        # zero-length vector: norm = 0
        a = _lm(0.5, 0.5)
        b = _lm(0.5, 0.5)
        c = _lm(0.7, 0.7)
        self.assertEqual(angle_between_points(a, b, c), 0.0)


class TestMidpoint(unittest.TestCase):
    def test_simple(self):
        a = _lm(0.0, 0.0, 0.5)
        b = _lm(1.0, 1.0, 0.9)
        m = midpoint(a, b)
        self.assertAlmostEqual(m["x"], 0.5)
        self.assertAlmostEqual(m["y"], 0.5)
        self.assertAlmostEqual(m["visibility"], 0.7)

    def test_z_average(self):
        a = {"x": 0.0, "y": 0.0, "z": 0.2, "visibility": 1.0}
        b = {"x": 1.0, "y": 1.0, "z": 0.6, "visibility": 1.0}
        m = midpoint(a, b)
        self.assertAlmostEqual(m["z"], 0.4)

    def test_missing_keys_default_to_zero(self):
        a = {"x": 0.0, "y": 0.0}
        b = {"x": 1.0, "y": 1.0}
        m = midpoint(a, b)
        self.assertAlmostEqual(m["z"], 0.0)
        self.assertAlmostEqual(m["visibility"], 0.0)


# ── Visibility and landmark checks ──────────────────────────────────────────────

class TestPointsAreVisible(unittest.TestCase):
    def test_all_visible(self):
        lms = _full_landmarks(visibility=1.0)
        self.assertTrue(points_are_visible(lms, ("left_knee", "left_hip", "left_ankle")))

    def test_one_below_threshold(self):
        lms = _full_landmarks(visibility=1.0)
        lms["left_knee"]["visibility"] = 0.0
        self.assertFalse(points_are_visible(lms, ("left_knee", "left_hip", "left_ankle")))

    def test_missing_landmark(self):
        lms = _full_landmarks(visibility=1.0)
        del lms["left_knee"]
        self.assertFalse(points_are_visible(lms, ("left_knee", "left_hip", "left_ankle")))


class TestAverageVisibility(unittest.TestCase):
    def test_all_visible(self):
        lms = _full_landmarks(visibility=0.8)
        self.assertAlmostEqual(average_visibility(lms), 0.8)

    def test_empty(self):
        self.assertEqual(average_visibility({}), 0.0)


class TestMissingLandmarks(unittest.TestCase):
    def test_no_missing(self):
        lms = _full_landmarks(visibility=1.0)
        self.assertEqual(missing_landmarks(lms), [])

    def test_low_visibility_counted(self):
        lms = _full_landmarks(visibility=1.0)
        lms["left_knee"]["visibility"] = 0.0
        lms["right_ankle"]["visibility"] = 0.0
        missing = missing_landmarks(lms)
        self.assertIn("left_knee", missing)
        self.assertIn("right_ankle", missing)
        self.assertEqual(len(missing), 2)

    def test_uses_required_points(self):
        self.assertEqual(len(REQUIRED_POINTS), 8)


# ── Pose metrics integration ────────────────────────────────────────────────────

class TestCalculatePoseMetrics(unittest.TestCase):
    def test_schema_with_valid_landmarks(self):
        lms = _full_landmarks(visibility=1.0)
        m = calculate_pose_metrics(lms)
        expected_keys = {
            "left_knee_angle", "right_knee_angle", "trunk_lean",
            "knee_asymmetry", "hip_imbalance", "ankle_alignment_delta",
            "average_visibility", "missing_landmarks", "tracking_status",
            "risk_score", "risk_level", "reasons", "screening_note",
        }
        self.assertTrue(expected_keys.issubset(set(m.keys())))

    def test_knee_angles_present(self):
        # Build landmarks with truly collinear hip→knee→ankle for each side
        lms = _full_landmarks(visibility=1.0)
        # Left side: perfect vertical line
        lms["left_hip"]   = _lm(0.45, 0.6)
        lms["left_knee"]  = _lm(0.45, 0.75)
        lms["left_ankle"] = _lm(0.45, 0.9)
        # Right side: perfect vertical line
        lms["right_hip"]   = _lm(0.55, 0.6)
        lms["right_knee"]  = _lm(0.55, 0.75)
        lms["right_ankle"] = _lm(0.55, 0.9)
        m = calculate_pose_metrics(lms)
        self.assertIsNotNone(m["left_knee_angle"])
        self.assertIsNotNone(m["right_knee_angle"])
        # perfectly straight legs → 180 deg
        self.assertAlmostEqual(m["left_knee_angle"], 180.0, places=1)
        self.assertAlmostEqual(m["right_knee_angle"], 180.0, places=1)

    def test_knee_asymmetry_with_mirror(self):
        lms = _full_landmarks(visibility=1.0)
        m = calculate_pose_metrics(lms)
        self.assertIsNotNone(m["knee_asymmetry"])
        self.assertAlmostEqual(m["knee_asymmetry"], 0.0, places=1)

    def test_trunk_lean_symmetric(self):
        lms = _full_landmarks(visibility=1.0)
        m = calculate_pose_metrics(lms)
        # symmetric shoulders and hips → trunk vertical → ~0 deg from vertical
        self.assertAlmostEqual(m["trunk_lean"], 0.0, places=1)


# ── No-pose fallback ────────────────────────────────────────────────────────────

class TestNoPoseMetrics(unittest.TestCase):
    def test_returns_no_pose_status(self):
        m = no_pose_metrics()
        self.assertEqual(m["tracking_status"], "NO_POSE")

    def test_measurement_fields_are_none(self):
        m = no_pose_metrics()
        self.assertIsNone(m["left_knee_angle"])
        self.assertIsNone(m["right_knee_angle"])
        self.assertIsNone(m["trunk_lean"])
        self.assertIsNone(m["knee_asymmetry"])
        self.assertIsNone(m["hip_imbalance"])
        self.assertIsNone(m["ankle_alignment_delta"])

    def test_all_required_points_marked_missing(self):
        m = no_pose_metrics()
        self.assertEqual(set(m["missing_landmarks"]), set(REQUIRED_POINTS))

    def test_risk_score_in_valid_range(self):
        m = no_pose_metrics()
        self.assertGreaterEqual(m["risk_score"], 0)
        self.assertLessEqual(m["risk_score"], 100)


# ── Risk score: shape only (NOT clinical validation) ────────────────────────────

class TestCalculateRiskScore(unittest.TestCase):
    def test_returns_score_level_reasons_tuple(self):
        score, level, reasons = calculate_risk_score(
            {"knee_asymmetry": None, "trunk_lean": None,
             "hip_imbalance": None, "ankle_alignment_delta": None,
             "average_visibility": 0.0, "missing_landmarks": []}
        )
        self.assertIsInstance(score, int)
        self.assertIn(level, ("LOW", "MODERATE", "HIGH"))
        self.assertIsInstance(reasons, list)

    def test_score_in_0_100_range(self):
        for asym in [None, 0.0, 12.0, 20.0, 30.0]:
            score, _, _ = calculate_risk_score(
                {"knee_asymmetry": asym, "trunk_lean": None,
                 "hip_imbalance": None, "ankle_alignment_delta": None,
                 "average_visibility": 1.0, "missing_landmarks": []}
            )
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)


# ── Session fields ──────────────────────────────────────────────────────────────

class TestAddSessionFields(unittest.TestCase):
    def test_adds_session_keys(self):
        m = {"foo": 1}
        enriched = add_session_fields(m, frame_index=42, elapsed_seconds=3.14)
        self.assertEqual(enriched["foo"], 1)
        self.assertEqual(enriched["frame_index"], 42)
        self.assertEqual(enriched["elapsed_seconds"], 3.14)
        self.assertIn("timestamp", enriched)


if __name__ == "__main__":
    unittest.main(verbosity=2)
