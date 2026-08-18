"""BioGait research evidence features (M2, Sprint A).

Pure, UI-independent geometry built on MediaPipe *world* landmarks
(monocular-RGB pose inference). This module contains NO clinical scoring.

Method provenance (see AGENTS.md):
- ``REFERENCE_DERIVED``: geometry concepts directly traceable to
  Capecci et al. 2019 (KIMORE), DOI 10.1109/TNSRE.2019.2923060.
- ``ENGINEERING_ADAPTED``: KIMORE uses Kinect RGB-D 3D skeletons; BioGait
  adapts the concepts to MediaPipe world landmarks inferred from monocular
  RGB. Numerical equivalence and clinical validity are NOT assumed.
- ``DESCRIPTIVE``: mathematical summaries of measured motion, not scores.

This module intentionally holds no thresholds of medical significance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Optional, Sequence

# ── Schema / exercise constants ────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"
RESEARCH_EXERCISE = "kimore_ex5_squat"

# Landmarks required for the Exercise-5 (squat) research evidence.
# MediaPipe WRIST is an ENGINEERING_ADAPTED proxy for the KIMORE Hand joint;
# it is never presented as an exact kinematic Hand equivalent.
WORLD_LANDMARK_NAMES = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}
REQUIRED_WORLD_LANDMARKS = tuple(WORLD_LANDMARK_NAMES)

# Engineering quality gate for research evidence (not a clinical threshold).
RESEARCH_MIN_LANDMARK_VISIBILITY = 0.55

_kimore_provenance = {
    "classification": "ENGINEERING_ADAPTED",
    "reference": "Capecci et al. 2019, IEEE Transactions on Neural Systems "
    "and Rehabilitation Engineering",
    "doi": "10.1109/TNSRE.2019.2923060",
    "dataset": "KIMORE",
    "exercise": "Exercise 5 (squat)",
    "adaptation_note": (
        "KIMORE uses Kinect RGB-D 3D skeletal coordinates; BioGait uses "
        "MediaPipe world landmarks inferred from monocular RGB. Numerical "
        "equivalence and clinical validity are not assumed."
    ),
    "wrist_proxy_note": (
        "MediaPipe wrist is used as an ENGINEERING_ADAPTED proxy for the "
        "KIMORE Hand joint; it is not an exact kinematic Hand equivalent."
    ),
}


# ── Landmark extraction ───────────────────────────────────────────────────────

def extract_normalized_landmarks(pose_result) -> dict[str, dict[str, float]]:
    """Extract normalized (image-space) landmarks from a PoseLandmarker result.

    Returns ``{name: {"x","y","z","visibility"}}`` in normalized image
    coordinates, or ``{}`` when no pose is detected. Used for the legacy
    pipeline; research evidence uses :func:`extract_world_landmarks`.
    """
    norms = getattr(pose_result, "pose_landmarks", None)
    if not norms:
        return {}
    lms = norms[0]  # first detected person
    out: dict[str, dict[str, float]] = {}
    for name, idx in WORLD_LANDMARK_NAMES.items():
        if idx < len(lms):
            lm = lms[idx]
            out[name] = {
                "x": float(lm.x),
                "y": float(lm.y),
                "z": float(lm.z),
                "visibility": float(getattr(lm, "visibility", 1.0)),
            }
    return out


def extract_world_landmarks(pose_result) -> dict[str, dict[str, float]]:
    """Extract the model-specific world landmarks from a PoseLandmarker result.

    Returns ``{name: {"x","y","z","visibility"}}`` or ``{}`` when the result
    carries no world landmarks (e.g., no pose detected).
    """
    world = getattr(pose_result, "pose_world_landmarks", None)
    if not world:
        return {}
    lms = world[0]  # first detected person
    out: dict[str, dict[str, float]] = {}
    for name, idx in WORLD_LANDMARK_NAMES.items():
        if idx < len(lms):
            lm = lms[idx]
            out[name] = {
                "x": float(lm.x),
                "y": float(lm.y),
                "z": float(lm.z),
                "visibility": float(getattr(lm, "visibility", 1.0)),
            }
    return out


def available_world_landmarks(
    landmarks: Mapping[str, Mapping[str, float]],
    threshold: float = RESEARCH_MIN_LANDMARK_VISIBILITY,
) -> list[str]:
    """Names in ``REQUIRED_WORLD_LANDMARKS`` that are present above threshold."""
    return [
        name
        for name in REQUIRED_WORLD_LANDMARKS
        if name in landmarks
        and landmarks[name].get("visibility", 0.0) >= threshold
    ]


def missing_world_landmarks(
    landmarks: Mapping[str, Mapping[str, float]],
    threshold: float = RESEARCH_MIN_LANDMARK_VISIBILITY,
) -> list[str]:
    """Names in ``REQUIRED_WORLD_LANDMARKS`` that are missing or low-visibility."""
    return [
        name
        for name in REQUIRED_WORLD_LANDMARKS
        if name not in landmarks
        or landmarks[name].get("visibility", 0.0) < threshold
    ]


def mean_visibility(
    landmarks: Mapping[str, Mapping[str, float]],
) -> float:
    """Average visibility across the required world landmarks that are present."""
    values = [
        landmarks[name].get("visibility", 0.0)
        for name in REQUIRED_WORLD_LANDMARKS
        if name in landmarks
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)


# ── Pure geometry ──────────────────────────────────────────────────────────────

def euclidean_distance_3d(
    a: Mapping[str, float], b: Mapping[str, float]
) -> float:
    """Euclidean 3D distance between two world-coordinate points (meters)."""
    return math.sqrt(
        (a["x"] - b["x"]) ** 2
        + (a["y"] - b["y"]) ** 2
        + (a["z"] - b["z"]) ** 2
    )


def kimore_sagittal_knee_angle_yz(
    hip: Mapping[str, float],
    knee: Mapping[str, float],
    ankle: Mapping[str, float],
) -> float:
    """KIMORE-style sagittal knee angle computed in the Y-Z plane (degrees).

    Uses the same mathematical convention for left and right sides; it does
    NOT produce correct/incorrect labels. Pure descriptive geometry.
    """
    v_hip = (hip["y"] - knee["y"], hip["z"] - knee["z"])
    v_ankle = (ankle["y"] - knee["y"], ankle["z"] - knee["z"])
    norm_hip = math.hypot(*v_hip)
    norm_ankle = math.hypot(*v_ankle)
    if norm_hip == 0 or norm_ankle == 0:
        return 0.0
    cos_theta = (v_hip[0] * v_ankle[0] + v_hip[1] * v_ankle[1]) / (
        norm_hip * norm_ankle
    )
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.degrees(math.acos(cos_theta))


def _triangle_area_heron(
    p1: Mapping[str, float],
    p2: Mapping[str, float],
    p3: Mapping[str, float],
) -> float:
    """Area of a triangle via Heron's formula (m^2). Degenerate -> 0.0."""
    a = euclidean_distance_3d(p1, p2)
    b = euclidean_distance_3d(p2, p3)
    c = euclidean_distance_3d(p1, p3)
    s = (a + b + c) / 2.0
    radicand = s * (s - a) * (s - b) * (s - c)
    if radicand <= 0.0:
        return 0.0
    return math.sqrt(radicand)


def torso_area_m2(
    left_shoulder: Mapping[str, float],
    right_shoulder: Mapping[str, float],
    left_hip: Mapping[str, float],
    right_hip: Mapping[str, float],
) -> float:
    """KIMORE-inspired torso area (m^2) using a two-triangle construction.

    Quadrilateral order: left_shoulder -> right_shoulder -> right_hip ->
    left_hip. It is decomposed along the diagonal (right_shoulder, left_hip)
    into triangles ``(LS, RS, LH)`` and ``(RS, RH, LH)``; each triangle area
    is computed with Heron's formula. Degenerate/collinear input yields 0.0.
    """
    return _triangle_area_heron(
        left_shoulder, right_shoulder, left_hip
    ) + _triangle_area_heron(right_shoulder, right_hip, left_hip)


def pairwise_control_factors(
    landmarks: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Euclidean 3D control-factor distances (meters) from world landmarks.

    Distances:

    - wrist_to_wrist
    - shoulder_to_shoulder
    - hip_to_hip
    - knee_to_knee
    - ankle_to_ankle
    - left_wrist_to_shoulder (wrist proxy for KIMORE hand)
    - right_wrist_to_shoulder
    """
    return {
        "wrist_distance_m": euclidean_distance_3d(
            landmarks["left_wrist"], landmarks["right_wrist"]
        ),
        "shoulder_distance_m": euclidean_distance_3d(
            landmarks["left_shoulder"], landmarks["right_shoulder"]
        ),
        "hip_distance_m": euclidean_distance_3d(
            landmarks["left_hip"], landmarks["right_hip"]
        ),
        "knee_distance_m": euclidean_distance_3d(
            landmarks["left_knee"], landmarks["right_knee"]
        ),
        "ankle_distance_m": euclidean_distance_3d(
            landmarks["left_ankle"], landmarks["right_ankle"]
        ),
        "left_wrist_shoulder_distance_m": euclidean_distance_3d(
            landmarks["left_wrist"], landmarks["left_shoulder"]
        ),
        "right_wrist_shoulder_distance_m": euclidean_distance_3d(
            landmarks["right_wrist"], landmarks["right_shoulder"]
        ),
    }


def shoulder_coordinates(
    landmarks: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Preserve left/right shoulder X and Z world coordinates."""
    return {
        "left_shoulder_x_m": landmarks["left_shoulder"]["x"],
        "left_shoulder_z_m": landmarks["left_shoulder"]["z"],
        "right_shoulder_x_m": landmarks["right_shoulder"]["x"],
        "right_shoulder_z_m": landmarks["right_shoulder"]["z"],
    }


def center_sequence(
    values: Sequence[Optional[float]],
) -> list[Optional[float]]:
    """Sequence-centering helper: ``centered[t] = value[t] - mean(sequence)``.

    Only valid (non-None) values contribute to the mean. ``None`` entries stay
    ``None``. This is per-sequence centering — it must not be used to fake
    whole-session centering during live streaming.
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return list(values)
    mean = sum(valid) / len(valid)
    return [None if v is None else v - mean for v in values]


# ── Frame evidence (Phase C) ──────────────────────────────────────────────────

@dataclass
class FrameEvidence:
    """Structured BioGait research evidence for one processed frame.

    All research values are ``None`` when evidence is unavailable — never 0.
    No fake measurements are ever generated.
    """

    schema_version: str = SCHEMA_VERSION
    exercise: str = RESEARCH_EXERCISE
    frame_index: int = 0
    timestamp_seconds: float = 0.0
    quality: dict = field(default_factory=dict)
    coordinate_source: str = "mediapipe_world"
    provenance: dict = field(default_factory=lambda: dict(_kimore_provenance))
    primary_outcomes: dict = field(default_factory=dict)
    control_factors: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=lambda: {"wrist_proxy_for_kimore_hand": True})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_frame_evidence(
    landmarks: Mapping[str, Mapping[str, float]],
    frame_index: int,
    timestamp_seconds: float,
    visibility_threshold: float = RESEARCH_MIN_LANDMARK_VISIBILITY,
) -> FrameEvidence:
    """Build a FrameEvidence object from world landmarks.

    If any required world landmark is missing or below the visibility gate,
    the evidence is marked unavailable and every research value is ``None``,
    with an explicit reason (``missing_world_landmarks`` or
    ``low_landmark_visibility``).
    """
    missing = missing_world_landmarks(landmarks, visibility_threshold)
    if missing:
        reason = (
            "missing_world_landmarks"
            if any(name not in landmarks for name in missing)
            else "low_landmark_visibility"
        )
        return FrameEvidence(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            quality={
                "available": False,
                "missing_landmarks": missing,
                "mean_visibility": mean_visibility(landmarks),
                "reason": reason,
            },
            primary_outcomes={
                "left_knee_sagittal_deg": None,
                "right_knee_sagittal_deg": None,
            },
            control_factors={
                "wrist_distance_m": None,
                "shoulder_distance_m": None,
                "hip_distance_m": None,
                "knee_distance_m": None,
                "ankle_distance_m": None,
                "left_wrist_shoulder_distance_m": None,
                "right_wrist_shoulder_distance_m": None,
                "torso_area_m2": None,
                "left_shoulder_x_m": None,
                "left_shoulder_z_m": None,
                "right_shoulder_x_m": None,
                "right_shoulder_z_m": None,
            },
        )

    return FrameEvidence(
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        quality={
            "available": True,
            "missing_landmarks": [],
            "mean_visibility": mean_visibility(landmarks),
            "reason": "ok",
        },
        primary_outcomes={
            "left_knee_sagittal_deg": kimore_sagittal_knee_angle_yz(
                landmarks["left_hip"],
                landmarks["left_knee"],
                landmarks["left_ankle"],
            ),
            "right_knee_sagittal_deg": kimore_sagittal_knee_angle_yz(
                landmarks["right_hip"],
                landmarks["right_knee"],
                landmarks["right_ankle"],
            ),
        },
        control_factors={
            **pairwise_control_factors(landmarks),
            "torso_area_m2": torso_area_m2(
                landmarks["left_shoulder"],
                landmarks["right_shoulder"],
                landmarks["left_hip"],
                landmarks["right_hip"],
            ),
            **shoulder_coordinates(landmarks),
        },
    )


def missing_evidence(frame_index: int, timestamp_seconds: float) -> FrameEvidence:
    """A fully unavailable FrameEvidence (used when world landmarks are absent)."""
    return build_frame_evidence({}, frame_index, timestamp_seconds)