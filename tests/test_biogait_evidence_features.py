"""
Tests for biogait/evidence_features.py — world-landmark extraction and
KIMORE-informed geometry.

Designed to require NO camera, GUI, network, or MediaPipe download. Uses
deterministic synthetic landmark data. No clinical-validity claims are tested.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from evidence_features import (  # noqa: E402
    REQUIRED_WORLD_LANDMARKS,
    build_frame_evidence,
    center_sequence,
    euclidean_distance_3d,
    extract_normalized_landmarks,
    extract_world_landmarks,
    kimore_reference_sagittal_knee_angle_yz,
    mean_visibility,
    missing_evidence,
    missing_world_landmarks,
    pairwise_control_factors,
    shoulder_coordinates,
    torso_area_m2,
)


def _lm(x, y, z, visibility=1.0):
    return {"x": x, "y": y, "z": z, "visibility": visibility}


def default_landmarks(**overrides):
    """A default full-body world-landmark scene (all visibility 1.0)."""
    scene = {
        "left_shoulder": _lm(0.0, 1.5, 0.0),
        "right_shoulder": _lm(0.3, 1.5, 0.0),
        "left_wrist": _lm(0.0, 1.4, 0.2),
        "right_wrist": _lm(0.3, 1.4, 0.2),
        "left_hip": _lm(0.0, 1.0, 0.0),
        "right_hip": _lm(0.3, 1.0, 0.0),
        "left_knee": _lm(0.0, 0.5, 0.0),
        "right_knee": _lm(0.3, 0.5, 0.0),
        "left_ankle": _lm(0.0, 0.0, 0.0),
        "right_ankle": _lm(0.3, 0.0, 0.0),
    }
    scene.update(overrides)
    return scene


def _fake_result(world_row=None, norm_row=None):
    return SimpleNamespace(
        pose_world_landmarks=[world_row] if world_row is not None else None,
        pose_landmarks=[norm_row] if norm_row is not None else None,
    )


def _landmark_row(positions=None):
    positions = positions or {}
    row = []
    for idx in range(29):
        pos = positions.get(idx, (float(idx), 0.0, 0.0))
        row.append(
            SimpleNamespace(
                x=pos[0], y=pos[1], z=pos[2], visibility=1.0
            )
        )
    return row


class LandmarkExtractionTests(unittest.TestCase):
    def test_world_extraction_empty_when_no_pose(self):
        self.assertEqual(extract_world_landmarks(_fake_result()), {})

    def test_normalized_extraction_empty_when_no_pose(self):
        self.assertEqual(extract_normalized_landmarks(_fake_result()), {})

    def test_world_extraction_maps_expected_names(self):
        row = _landmark_row({
            11: (0.1, 1.5, 0.0),
            12: (0.4, 1.5, 0.0),
            15: (0.1, 1.4, 0.2),
            16: (0.4, 1.4, 0.2),
            23: (0.1, 1.0, 0.0),
            24: (0.4, 1.0, 0.0),
            25: (0.1, 0.5, 0.0),
            26: (0.4, 0.5, 0.0),
            27: (0.1, 0.0, 0.0),
            28: (0.4, 0.0, 0.0),
        })
        out = extract_world_landmarks(_fake_result(world_row=row))
        self.assertEqual(set(out), set(REQUIRED_WORLD_LANDMARKS))
        self.assertAlmostEqual(out["left_shoulder"]["x"], 0.1)
        self.assertAlmostEqual(out["right_ankle"]["x"], 0.4)

    def test_missing_world_landmarks_reports_drops(self):
        scene = default_landmarks()
        del scene["right_ankle"]
        missing = missing_world_landmarks(scene)
        self.assertIn("right_ankle", missing)
        self.assertEqual(len(missing), 1)

    def test_mean_visibility_over_required(self):
        scene = default_landmarks()
        scene["left_shoulder"] = _lm(0.0, 1.5, 0.0, visibility=0.6)
        self.assertGreater(mean_visibility(scene), 0.9)


class GeometryTests(unittest.TestCase):
    def test_euclidean_distance_3d(self):
        a = {"x": 0.0, "y": 0.0, "z": 0.0}
        b = {"x": 3.0, "y": 4.0, "z": 0.0}
        self.assertAlmostEqual(euclidean_distance_3d(a, b), 5.0)
        self.assertAlmostEqual(euclidean_distance_3d(a, a), 0.0)

    def test_torso_area_rectangle_is_0_5(self):
        ls = _lm(0.0, 1.0, 0.0)
        rs = _lm(0.5, 1.0, 0.0)
        lh = _lm(0.0, 0.0, 0.0)
        rh = _lm(0.5, 0.0, 0.0)
        self.assertAlmostEqual(torso_area_m2(ls, rs, lh, rh), 0.5, places=4)

    def test_torso_area_degenerate_geometry_is_zero(self):
        col = lambda y: _lm(0.0, y, 0.0)  # noqa: E731
        self.assertEqual(torso_area_m2(col(2), col(1), col(0), col(-1)), 0.0)

    def test_pairwise_control_factors(self):
        scene = default_landmarks()
        cf = pairwise_control_factors(scene)
        self.assertAlmostEqual(cf["shoulder_distance_m"], 0.3, places=4)
        self.assertAlmostEqual(cf["hip_distance_m"], 0.3, places=4)
        self.assertAlmostEqual(
            cf["left_wrist_shoulder_distance_m"],
            math.sqrt(0.0 + 0.1 ** 2 + 0.2 ** 2),
            places=4,
        )

    def test_shoulder_coordinates_preserved(self):
        coords = shoulder_coordinates(default_landmarks())
        self.assertAlmostEqual(coords["left_shoulder_x_m"], 0.0)
        self.assertAlmostEqual(coords["right_shoulder_z_m"], 0.0)


def _acos_angle(hip, knee, ankle):
    """Generic conventional acos 0..180 vector angle (test only)."""
    v_hk = (hip["y"] - knee["y"], hip["z"] - knee["z"])
    v_ak = (ankle["y"] - knee["y"], ankle["z"] - knee["z"])
    n_hk = math.hypot(*v_hk)
    n_ak = math.hypot(*v_ak)
    cos_t = (v_hk[0] * v_ak[0] + v_hk[1] * v_ak[1]) / (n_hk * n_ak)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_t))))


class KimoreReferenceKneeTests(unittest.TestCase):
    """Exact reviewed Ex5 atan2 knee-angle convention (FIX 1 / 16)."""

    def test_exact_atan2_equation(self):
        hip = _lm(0.0, 1.0, 0.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, 0.0, 1.0)
        expected = math.degrees(
            math.atan2(hip["y"] - knee["y"], hip["z"] - knee["z"])
            + math.atan2(knee["y"] - ankle["y"], ankle["z"] - knee["z"])
        )
        got = kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        self.assertAlmostEqual(got, expected, places=6)

    def test_atan2_differs_from_generic_acos(self):
        # Hip above and BEHIND the knee; ankle below and BEHIND the knee.
        hip = _lm(0.0, 2.0, -1.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, -2.0, -1.0)
        ref = kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        generic = _acos_angle(hip, knee, ankle)
        self.assertNotAlmostEqual(ref, generic, places=4)
        expected = math.degrees(
            math.atan2(hip["y"] - knee["y"], hip["z"] - knee["z"])
            + math.atan2(knee["y"] - ankle["y"], ankle["z"] - knee["z"])
        )
        self.assertAlmostEqual(ref, expected, places=6)

    def test_no_forced_0_180_clamp(self):
        # Reference representation legitimately exceeds 180 degrees.
        hip = _lm(0.0, 2.0, -1.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, -2.0, -1.0)
        ref = kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        self.assertGreater(ref, 180.0)
        self.assertLessEqual(ref, 360.0)

    def test_degenerate_hip_knee_segment_is_none(self):
        hip = _lm(0.0, 1.0, 0.0)
        knee = _lm(0.0, 1.0, 0.0)  # zero-length hip-knee segment
        ankle = _lm(0.0, 0.0, 0.0)
        self.assertIsNone(
            kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        )

    def test_degenerate_knee_ankle_segment_is_none(self):
        hip = _lm(0.0, 1.0, 0.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, 0.0, 0.0)  # zero-length knee-ankle segment
        self.assertIsNone(
            kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        )

    def test_missing_point_is_none(self):
        self.assertIsNone(
            kimore_reference_sagittal_knee_angle_yz(_lm(0, 1, 0), None, None)
        )


class CenteringTests(unittest.TestCase):
    def test_center_sequence_subtracts_mean(self):
        self.assertEqual(center_sequence([1.0, 2.0, 3.0]), [-1.0, 0.0, 1.0])

    def test_center_sequence_preserves_none(self):
        out = center_sequence([1.0, None, 3.0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[0], -1.0)
        self.assertAlmostEqual(out[2], 1.0)

    def test_center_sequence_all_none(self):
        self.assertEqual(center_sequence([None, None]), [None, None])

    def test_center_sequence_empty(self):
        self.assertEqual(center_sequence([]), [])


class FrameEvidenceTests(unittest.TestCase):
    def test_available_evidence_fields(self):
        evidence = build_frame_evidence(default_landmarks(), frame_index=3, timestamp_seconds=0.1)
        self.assertTrue(evidence.quality["available"])
        self.assertEqual(evidence.quality["missing_landmarks"], [])
        self.assertEqual(evidence.quality["reason"], "ok")
        self.assertEqual(evidence.coordinate_source, "mediapipe_world")
        self.assertTrue(evidence.metadata["wrist_proxy_for_kimore_hand"])
        self.assertIsNotNone(evidence.primary_outcomes["left_knee_sagittal_deg"])
        self.assertIsNotNone(evidence.primary_outcomes["right_knee_sagittal_deg"])
        self.assertIsNotNone(evidence.control_factors["torso_area_m2"])
        self.assertEqual(evidence.frame_index, 3)
        self.assertAlmostEqual(evidence.timestamp_seconds, 0.1)

    def test_missing_landmark_evidence_is_none_not_zero(self):
        scene = default_landmarks()
        del scene["right_knee"]
        evidence = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(evidence.quality["available"])
        self.assertIn("right_knee", evidence.quality["missing_landmarks"])
        self.assertEqual(evidence.quality["reason"], "missing_world_landmarks")
        self.assertIsNone(evidence.primary_outcomes["left_knee_sagittal_deg"])
        self.assertIsNone(evidence.control_factors["torso_area_m2"])

    def test_low_visibility_evidence_unavailable(self):
        scene = default_landmarks()
        scene["left_ankle"] = _lm(0.0, 0.0, 0.0, visibility=0.1)
        evidence = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(evidence.quality["available"])
        self.assertEqual(evidence.quality["reason"], "low_landmark_visibility")

    def test_blank_evidence_helper(self):
        evidence = missing_evidence(0, 0.0).to_dict()
        self.assertFalse(evidence["quality"]["available"])
        self.assertIsNone(evidence["primary_outcomes"]["right_knee_sagittal_deg"])

    def test_sagittal_angles_are_float_or_absent(self):
        evidence = build_frame_evidence(default_landmarks(), 0, 0.0)
        for key in ("left_knee_sagittal_deg", "right_knee_sagittal_deg"):
            val = evidence.primary_outcomes[key]
            self.assertIsInstance(val, float)

    def test_degenerate_geometry_evidence_is_explicit(self):
        scene = default_landmarks()
        scene["left_knee"] = _lm(0.0, 1.0, 0.0)  # same as left_hip: degenerate
        evidence = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(evidence.quality["available"])
        self.assertEqual(evidence.quality["reason"], "degenerate_knee_geometry")
        self.assertEqual(evidence.quality["missing_landmarks"], [])
        self.assertIsNone(evidence.primary_outcomes["left_knee_sagittal_deg"])
        # The right side still computes; control factors remain valid geometry.
        self.assertIsNotNone(evidence.primary_outcomes["right_knee_sagittal_deg"])
        self.assertTrue(evidence.control_factors["torso_area_m2"] > 0.0)

    def test_to_dict_roundtrip(self):
        evidence = build_frame_evidence(default_landmarks(), 1, 0.033).to_dict()
        self.assertEqual(evidence["schema_version"], "1.0")
        self.assertEqual(evidence["exercise"], "kimore_ex5_squat")
        self.assertIn("left_knee_sagittal_deg", evidence["primary_outcomes"])
        self.assertIn("torso_area_m2", evidence["control_factors"])


if __name__ == "__main__":
    unittest.main()