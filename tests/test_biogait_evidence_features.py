"""
Tests for biogait/evidence_features.py — world-landmark extraction and
KIMORE-informed geometry with feature-specific quality gating.

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
    CONTROL_FACTOR_REQUIREMENTS,
    MIN_LANDMARK_VISIBILITY,
    PO_REQUIRED_LANDMARKS,
    REQUIRED_WORLD_LANDMARKS,
    build_frame_evidence,
    center_sequence,
    compute_control_factors,
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
                x=pos[0], y=pos[1], z=pos[2], visibility=1.0, presence=1.0
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

    def test_world_extraction_drops_non_finite(self):
        positions = {11: (float("nan"), 1.5, 0.0)}
        out = extract_world_landmarks(_fake_result(world_row=_landmark_row(positions)))
        self.assertNotIn("left_shoulder", out)

    def test_missing_world_landmarks_reports_drops(self):
        scene = default_landmarks()
        del scene["right_ankle"]
        missing = missing_world_landmarks(scene)
        self.assertIn("right_ankle", missing)
        self.assertEqual(len(missing), 1)

    def test_non_finite_landmark_treated_as_missing(self):
        scene = default_landmarks()
        scene["right_knee"] = _lm(float("inf"), 0.5, 0.0)
        missing = missing_world_landmarks(scene)
        self.assertIn("right_knee", missing)

    def test_low_visibility_treated_as_missing(self):
        scene = default_landmarks()
        scene["left_ankle"] = _lm(0.0, 0.0, 0.0, visibility=0.1)
        missing = missing_world_landmarks(scene)
        self.assertIn("left_ankle", missing)

    def test_threshold_matches_single_config_source(self):
        self.assertEqual(MIN_LANDMARK_VISIBILITY, 0.55)


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

    def test_shoulder_coordinates_preserved(self):
        coords = shoulder_coordinates(default_landmarks())
        self.assertAlmostEqual(coords["left_shoulder_x_m"], 0.0)
        self.assertAlmostEqual(coords["right_shoulder_z_m"], 0.0)

    def test_knee_delta_y_is_signed_y_difference(self):
        # Reference source: deltayknee = Knee_R(:,2) - Knee_L(:,2) (signed).
        scene = default_landmarks()
        cf = compute_control_factors(scene)
        expected = scene["right_knee"]["y"] - scene["left_knee"]["y"]
        self.assertAlmostEqual(cf["knee_delta_y_m"], expected)
        self.assertAlmostEqual(cf["knee_delta_y_m"], 0.0)  # symmetric default

    def test_knee_euclidean_is_3d_distance_not_y_difference(self):
        scene = default_landmarks()
        cf = compute_control_factors(scene)
        self.assertAlmostEqual(cf["knee_euclidean_3d_m"], 0.3)
        self.assertNotAlmostEqual(cf["knee_euclidean_3d_m"], cf["knee_delta_y_m"])


class FeatureGatingTests(unittest.TestCase):
    """Per-feature quality gating (item 8 / 24 J/K/L)."""

    def test_missing_left_wrist_does_not_erase_knee_pos(self):
        scene = default_landmarks()
        del scene["left_wrist"]
        ev = build_frame_evidence(scene, 0, 0.0)
        self.assertTrue(ev.quality["left_po_available"])
        self.assertTrue(ev.quality["right_po_available"])
        self.assertTrue(ev.quality["available"])
        self.assertIsNotNone(ev.primary_outcomes["left_knee_sagittal_deg"])
        self.assertIsNotNone(ev.primary_outcomes["right_knee_sagittal_deg"])
        self.assertIsNone(ev.control_factors["wrist_distance_m"])
        self.assertIsNone(ev.control_factors["left_wrist_shoulder_distance_m"])
        self.assertIsNotNone(ev.control_factors["torso_area_m2"])
        self.assertFalse(ev.quality["control_factors_complete"])
        self.assertEqual(ev.quality["reason"], "partial")

    def test_missing_left_ankle_invalidates_left_po_only(self):
        scene = default_landmarks()
        del scene["left_ankle"]
        ev = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(ev.quality["left_po_available"])
        self.assertTrue(ev.quality["right_po_available"])
        self.assertFalse(ev.quality["available"])
        self.assertIsNone(ev.primary_outcomes["left_knee_sagittal_deg"])
        self.assertIsNotNone(ev.primary_outcomes["right_knee_sagittal_deg"])
        self.assertEqual(ev.quality["reason"], "missing_world_landmarks")

    def test_missing_right_hip_affects_only_dependent_features(self):
        scene = default_landmarks()
        del scene["right_hip"]
        ev = build_frame_evidence(scene, 0, 0.0)
        self.assertTrue(ev.quality["left_po_available"])
        self.assertFalse(ev.quality["right_po_available"])
        self.assertIsNone(ev.control_factors["hip_distance_m"])
        self.assertIsNotNone(ev.control_factors["knee_euclidean_3d_m"])

    def test_non_finite_world_landmark_becomes_unavailable(self):
        scene = default_landmarks()
        scene["left_knee"] = _lm(float("nan"), 0.5, 0.0)
        ev = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(ev.quality["left_po_available"])
        self.assertIsNone(ev.primary_outcomes["left_knee_sagittal_deg"])
        self.assertTrue(ev.quality["right_po_available"])
        self.assertIn("left_knee", ev.quality["missing_or_low_quality_landmarks"])
        self.assertEqual(ev.quality["reason"], "non_finite_landmark")

    def test_all_features_available_full_quality(self):
        ev = build_frame_evidence(default_landmarks(), 0, 0.0)
        self.assertTrue(ev.quality["available"])
        self.assertTrue(ev.quality["primary_outcomes_complete"])
        self.assertTrue(ev.quality["control_factors_complete"])
        self.assertEqual(ev.quality["missing_or_low_quality_landmarks"], [])
        self.assertEqual(ev.quality["reason"], "ok")

    def test_missing_evidence_helper_fully_unavailable(self):
        ev = missing_evidence(0, 0.0)
        self.assertFalse(ev.quality["available"])
        self.assertFalse(ev.quality["left_po_available"])
        self.assertIsNone(ev.primary_outcomes["right_knee_sagittal_deg"])

    def test_control_factors_always_have_all_keys(self):
        scene = default_landmarks()
        del scene["left_wrist"]
        cf = compute_control_factors(scene)
        self.assertEqual(set(cf), set(CONTROL_FACTOR_REQUIREMENTS))
        self.assertIsNone(cf["wrist_distance_m"])
        self.assertIsNotNone(cf["torso_area_m2"])

    def test_degenerate_geometry_is_explicit(self):
        scene = default_landmarks()
        scene["left_knee"] = _lm(0.0, 1.0, 0.0)  # same as left_hip
        ev = build_frame_evidence(scene, 0, 0.0)
        self.assertFalse(ev.quality["left_po_available"])
        self.assertIsNone(ev.primary_outcomes["left_knee_sagittal_deg"])
        # Right PO still computed (feature-specific).
        self.assertTrue(ev.quality["right_po_available"])
        self.assertEqual(ev.quality["reason"], "degenerate_knee_geometry")


class KimoreReferenceKneeTests(unittest.TestCase):
    """Source-aligned reviewed atan2 knee-angle convention (blockers 1/16)."""

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
        hip = _lm(0.0, 2.0, -1.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, -2.0, -1.0)
        ref = kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        generic = _acos_angle(hip, knee, ankle)
        self.assertNotAlmostEqual(ref, generic, places=4)

    def test_no_forced_0_180_clamp(self):
        hip = _lm(0.0, 2.0, -1.0)
        knee = _lm(0.0, 0.0, 0.0)
        ankle = _lm(0.0, -2.0, -1.0)
        ref = kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)
        self.assertGreater(ref, 180.0)

    def test_degenerate_segments_return_none(self):
        hip = _lm(0.0, 1.0, 0.0)
        knee = _lm(0.0, 1.0, 0.0)  # zero-length hip-knee
        ankle = _lm(0.0, 0.0, 0.0)
        self.assertIsNone(kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle))

        knee2 = _lm(0.0, 0.0, 0.0)
        ankle2 = _lm(0.0, 0.0, 0.0)  # zero-length knee-ankle
        self.assertIsNone(kimore_reference_sagittal_knee_angle_yz(hip, knee2, ankle2))


def _acos_angle(hip, knee, ankle):
    v_hk = (hip["y"] - knee["y"], hip["z"] - knee["z"])
    v_ak = (ankle["y"] - knee["y"], ankle["z"] - knee["z"])
    n_hk = math.hypot(*v_hk)
    n_ak = math.hypot(*v_ak)
    cos_t = (v_hk[0] * v_ak[0] + v_hk[1] * v_ak[1]) / (n_hk * n_ak)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_t))))


class CenteringTests(unittest.TestCase):
    def test_center_sequence_subtracts_mean(self):
        self.assertEqual(center_sequence([1.0, 2.0, 3.0]), [-1.0, 0.0, 1.0])

    def test_center_sequence_preserves_none(self):
        out = center_sequence([1.0, None, 3.0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[0], -1.0)
        self.assertAlmostEqual(out[2], 1.0)


class FrameEvidenceSurfaceTests(unittest.TestCase):
    def test_available_evidence_fields(self):
        evidence = build_frame_evidence(default_landmarks(), frame_index=3, timestamp_seconds=0.1)
        self.assertTrue(evidence.quality["available"])
        self.assertEqual(evidence.coordinate_source, "mediapipe_world")
        self.assertTrue(evidence.metadata["wrist_proxy_for_kimore_hand"])
        self.assertEqual(evidence.frame_index, 3)
        self.assertAlmostEqual(evidence.timestamp_seconds, 0.1)
        self.assertIsInstance(evidence.primary_outcomes["left_knee_sagittal_deg"], float)

    def test_to_dict_roundtrip(self):
        evidence = build_frame_evidence(default_landmarks(), 1, 0.033).to_dict()
        self.assertEqual(evidence["schema_version"], "1.0")
        self.assertEqual(evidence["exercise"], "kimore_ex5_squat")
        self.assertIn("left_knee_sagittal_deg", evidence["primary_outcomes"])
        self.assertIn("knee_delta_y_m", evidence["control_factors"])
        self.assertNotIn("knee_distance_m", evidence["control_factors"])

    def test_no_nan_emitted_for_valid_input(self):
        ev = build_frame_evidence(default_landmarks(), 0, 0.0).to_dict()
        import math as _math
        po = ev["primary_outcomes"]
        for v in list(po.values()) + list(ev["control_factors"].values()):
            if v is not None:
                self.assertTrue(_math.isfinite(v), f"non-finite: {v}")


if __name__ == "__main__":
    unittest.main()