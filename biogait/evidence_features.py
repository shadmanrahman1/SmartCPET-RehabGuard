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

MediaPipe world landmarks are 3D coordinates in meters with the midpoint of
the hips as the origin (a MediaPipe convention, not a camera-centered frame).
Kinect and MediaPipe axes/coordinate frames are not assumed to be numerically
equivalent.

This module intentionally holds no thresholds of medical significance. The
single visibility gate is ``config.MIN_LANDMARK_VISIBILITY`` (an engineering
quality threshold, not a clinical one).

Feature-specific gating: each primary outcome and each control factor is
computed from its OWN required landmark set. A missing wrist, for example,
never erases a valid knee primary outcome; it only none-ifies the wrist-based
control factors.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Optional, Sequence

import config

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

# Engineering visibility gate for research evidence (not a clinical
# threshold). Defined once in config so no second independent threshold is
# maintained here.
MIN_LANDMARK_VISIBILITY = config.MIN_LANDMARK_VISIBILITY

# Per-feature landmark requirements (feature-specific quality gating).
PO_REQUIRED_LANDMARKS = {
    "left": ("left_hip", "left_knee", "left_ankle"),
    "right": ("right_hip", "right_knee", "right_ankle"),
}
CONTROL_FACTOR_REQUIREMENTS = {
    "wrist_distance_m": ("left_wrist", "right_wrist"),
    "shoulder_distance_m": ("left_shoulder", "right_shoulder"),
    "hip_distance_m": ("left_hip", "right_hip"),
    "knee_euclidean_3d_m": ("left_knee", "right_knee"),
    "knee_delta_y_m": ("left_knee", "right_knee"),
    "ankle_distance_m": ("left_ankle", "right_ankle"),
    "left_wrist_shoulder_distance_m": ("left_wrist", "left_shoulder"),
    "right_wrist_shoulder_distance_m": ("right_wrist", "right_shoulder"),
    "torso_area_m2": (
        "left_shoulder", "right_shoulder", "left_hip", "right_hip",
    ),
    "left_shoulder_x_m": ("left_shoulder",),
    "left_shoulder_z_m": ("left_shoulder",),
    "right_shoulder_x_m": ("right_shoulder",),
    "right_shoulder_z_m": ("right_shoulder",),
}

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
    "knee_cf_discrepancy_note": (
        "The KIMORE paper labels d_k as knee distance, while the reviewed "
        "feature-extraction source computes a signed Y-coordinate difference "
        "(deltayknee = Knee_R(:,2) - Knee_L(:,2)). BioGait preserves this "
        "discrepancy in provenance rather than silently equating the two."
    ),
}


# ── Landmark extraction ───────────────────────────────────────────────────────

def _finite(value: Any) -> bool:
    """True for a real finite number (rejects NaN / +-inf; also rejects None)."""
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _build_landmark(lm) -> Optional[dict[str, float]]:
    """Convert a raw MediaPipe landark to a plain dict, or None if non-finite."""
    if lm is None:
        return None
    entry = {
        "x": float(getattr(lm, "x", 0.0)),
        "y": float(getattr(lm, "y", 0.0)),
        "z": float(getattr(lm, "z", 0.0)),
        "visibility": float(getattr(lm, "visibility", 1.0)),
    }
    if not all(_finite(v) for v in entry.values()):
        return None
    return entry


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
            entry = _build_landmark(lms[idx])
            if entry is not None:
                out[name] = entry
    return out


def extract_world_landmarks(pose_result) -> dict[str, dict[str, float]]:
    """Extract the model-specific world landmarks from a PoseLandmarker result.

    Returns ``{name: {"x","y","z","visibility"}}`` or ``{}`` when the result
    carries no world landmarks (e.g., no pose detected). Entries with
    non-finite coordinates/visibility are dropped (never propagated).
    """
    world = getattr(pose_result, "pose_world_landmarks", None)
    if not world:
        return {}
    lms = world[0]  # first detected person
    out: dict[str, dict[str, float]] = {}
    for name, idx in WORLD_LANDMARK_NAMES.items():
        if idx < len(lms):
            entry = _build_landmark(lms[idx])
            if entry is not None:
                out[name] = entry
    return out


def landmark_is_available(
    name: str,
    landmarks: Mapping[str, Mapping[str, float]],
    threshold: float = MIN_LANDMARK_VISIBILITY,
) -> bool:
    """A landmark is available when present, finite, and above the threshold."""
    lm = landmarks.get(name)
    if lm is None:
        return False
    if not all(_finite(lm.get(k)) for k in ("x", "y", "z", "visibility")):
        return False
    return float(lm.get("visibility", 0.0)) >= threshold


def available_world_landmarks(
    landmarks: Mapping[str, Mapping[str, float]],
    threshold: float = MIN_LANDMARK_VISIBILITY,
) -> list[str]:
    """Required names that are present, finite, and above the threshold."""
    return [
        name
        for name in REQUIRED_WORLD_LANDMARKS
        if landmark_is_available(name, landmarks, threshold)
    ]


def missing_world_landmarks(
    landmarks: Mapping[str, Mapping[str, float]],
    threshold: float = MIN_LANDMARK_VISIBILITY,
) -> list[str]:
    """Required names that are missing, non-finite, or below the threshold."""
    return [
        name
        for name in REQUIRED_WORLD_LANDMARKS
        if not landmark_is_available(name, landmarks, threshold)
    ]


def mean_visibility(
    landmarks: Mapping[str, Mapping[str, float]],
) -> float:
    """Average visibility across required landmarks that are present and finite."""
    values = []
    for name in REQUIRED_WORLD_LANDMARKS:
        lm = landmarks.get(name)
        if lm is not None and _finite(lm.get("visibility")):
            values.append(float(lm["visibility"]))
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


def kimore_reference_sagittal_knee_angle_yz(
    hip: Mapping[str, float] | None,
    knee: Mapping[str, float] | None,
    ankle: Mapping[str, float] | None,
) -> Optional[float]:
    """Source-aligned KIMORE Ex5 sagittal knee angle (reviewed convention).

    For one side::

        angle_deg = degrees(
            atan2(hip_y - knee_y, hip_z - knee_z)
            + atan2(knee_y - ankle_y, ankle_z - knee_z)
        )

    This is NOT a clamped 0..180 vector angle: the reference representation
    can contain values outside that range, which is why the reference temporal
    pipeline includes explicit sign/singularity handling. The equation is
    directly source-derived; numerical identity with the original MATLAB
    runtime has not been established.

    Returns ``None`` when any required point is missing or the hip-knee or
    knee-ankle segment is degenerate (zero length). It never fabricates a
    0-degree measurement.
    """
    if hip is None or knee is None or ankle is None:
        return None

    hip_knee_y = hip["y"] - knee["y"]
    hip_knee_z = hip["z"] - knee["z"]
    knee_ankle_y = knee["y"] - ankle["y"]
    ankle_knee_z = ankle["z"] - knee["z"]

    if (hip_knee_y == 0 and hip_knee_z == 0) or (
        knee_ankle_y == 0 and ankle_knee_z == 0
    ):
        return None

    theta_hip = math.atan2(hip_knee_y, hip_knee_z)
    theta_ankle = math.atan2(knee_ankle_y, ankle_knee_z)
    return math.degrees(theta_hip + theta_ankle)


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


def _knee_delta_y_m(
    left_knee: Mapping[str, float],
    right_knee: Mapping[str, float],
) -> float:
    """Signed Y-coordinate knee difference: ``right_knee.y - left_knee.y``.

    REFERENCE_DERIVED equation: the reviewed KIMORE feature-extraction source
    computes ``deltayknee = Knee_R(:,2) - Knee_L(:,2)``. The KIMORE paper
    labels d_k as "knee distance"; BioGait preserves that discrepancy in
    provenance rather than silently equating it with a Euclidean distance.
    """
    return right_knee["y"] - left_knee["y"]


def compute_control_factors(
    landmarks: Mapping[str, Mapping[str, float]],
    available: Optional[set[str]] = None,
) -> dict[str, Optional[float]]:
    """Compute ALL control factors with feature-specific gating.

    A control factor is computed only when every landmark it requires is
    available (present, finite, above the visibility threshold). Otherwise it
    is ``None`` (never 0, never fabricated). The result always contains every
    key in ``CONTROL_FACTOR_REQUIREMENTS`` so session streams stay aligned.
    """
    if available is None:
        available = set(available_world_landmarks(landmarks))
    available = set(available)
    out: dict[str, Optional[float]] = {}

    def _have(*names: str) -> Optional[list]:
        if all(n in available for n in names):
            return [landmarks[n] for n in names]
        return None

    pts = _have("left_wrist", "right_wrist")
    out["wrist_distance_m"] = euclidean_distance_3d(*pts) if pts else None
    pts = _have("left_shoulder", "right_shoulder")
    out["shoulder_distance_m"] = euclidean_distance_3d(*pts) if pts else None
    pts = _have("left_hip", "right_hip")
    out["hip_distance_m"] = euclidean_distance_3d(*pts) if pts else None
    pts = _have("left_knee", "right_knee")
    out["knee_euclidean_3d_m"] = euclidean_distance_3d(*pts) if pts else None
    out["knee_delta_y_m"] = _knee_delta_y_m(*pts) if pts else None
    pts = _have("left_ankle", "right_ankle")
    out["ankle_distance_m"] = euclidean_distance_3d(*pts) if pts else None
    pts = _have("left_wrist", "left_shoulder")
    out["left_wrist_shoulder_distance_m"] = (
        euclidean_distance_3d(*pts) if pts else None
    )
    pts = _have("right_wrist", "right_shoulder")
    out["right_wrist_shoulder_distance_m"] = (
        euclidean_distance_3d(*pts) if pts else None
    )
    pts = _have("left_shoulder", "right_shoulder", "left_hip", "right_hip")
    out["torso_area_m2"] = torso_area_m2(*pts) if pts else None
    out["left_shoulder_x_m"] = (
        landmarks["left_shoulder"]["x"] if "left_shoulder" in available else None
    )
    out["left_shoulder_z_m"] = (
        landmarks["left_shoulder"]["z"] if "left_shoulder" in available else None
    )
    out["right_shoulder_x_m"] = (
        landmarks["right_shoulder"]["x"] if "right_shoulder" in available else None
    )
    out["right_shoulder_z_m"] = (
        landmarks["right_shoulder"]["z"] if "right_shoulder" in available else None
    )
    return out


def pairwise_control_factors(
    landmarks: Mapping[str, Mapping[str, float]],
) -> dict[str, Optional[float]]:
    """Alias for :func:`compute_control_factors` (kept for import compatibility)."""
    return compute_control_factors(landmarks)


def shoulder_coordinates(
    landmarks: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Raw per-frame shoulder X/Z world coordinates (meters).

    Raw coordinates are captured per frame. Full source-style zero-mean
    shoulder transverse-plane CF preprocessing is NOT applied per frame; it
    remains deferred (offline centering helper: :func:`center_sequence`).
    """
    return {
        "left_shoulder_x_m": landmarks["left_shoulder"]["x"],
        "left_shoulder_z_m": landmarks["left_shoulder"]["z"],
        "right_shoulder_x_m": landmarks["right_shoulder"]["x"],
        "right_shoulder_z_m": landmarks["right_shoulder"]["z"],
    }


def center_sequence(
    values: Sequence[Optional[float]],
) -> list[Optional[float]]:
    """Offline sequence-centering helper: ``centered[t] = value[t] - mean``.

    Only valid (non-None) values contribute to the mean. ``None`` entries stay
    ``None``. This is per-sequence centering — it must not be used to fake
    whole-session centering during live streaming. It is an offline helper;
    it does not claim the full KIMORE CF temporal preprocessing is reproduced.
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

    Feature-specific: a value is ``None`` when the landmarks it depends on are
    unavailable (missing, non-finite, or below the visibility gate) — never 0.
    Missing values are never fabricated. No NaN/Infinity is ever emitted.
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
    visibility_threshold: float = MIN_LANDMARK_VISIBILITY,
) -> FrameEvidence:
    """Build a FrameEvidence object from world landmarks (feature-gated).

    Each primary outcome and each control factor is computed from its own
    required landmark set. ``quality["available"]`` means BOTH primary knee
    outcomes are available (NOT that every possible control factor is).
    Additional flags expose per-side availability, completeness, and the
    missing/low-quality landmark list.
    """
    available = set(available_world_landmarks(landmarks, visibility_threshold))

    def _po(side: str) -> Optional[float]:
        names = PO_REQUIRED_LANDMARKS[side]
        if not all(n in available for n in names):
            return None
        hip, knee, ankle = (landmarks[n] for n in names)
        return kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)

    left_po = _po("left")
    right_po = _po("right")
    left_po_available = left_po is not None
    right_po_available = right_po is not None

    control_factors = compute_control_factors(landmarks, available)
    control_factors_complete = all(v is not None for v in control_factors.values())

    missing = [
        name
        for name in REQUIRED_WORLD_LANDMARKS
        if not landmark_is_available(name, landmarks, visibility_threshold)
    ]

    def _reason_for_names(names) -> Optional[str]:
        for name in names:
            lm = landmarks.get(name)
            if lm is None:
                return "missing_world_landmarks"
            if not all(_finite(lm.get(k)) for k in ("x", "y", "z", "visibility")):
                return "non_finite_landmark"
            if float(lm.get("visibility", 0.0)) < visibility_threshold:
                return "low_landmark_visibility"
        return None

    if left_po_available and right_po_available:
        reason = "ok" if control_factors_complete else "partial"
    else:
        po_missing_names = sorted(
            {
                n
                for side in ("left", "right")
                for n in PO_REQUIRED_LANDMARKS[side]
                if not landmark_is_available(n, landmarks, visibility_threshold)
            }
        )
        if po_missing_names:
            reason = _reason_for_names(po_missing_names) or "missing_world_landmarks"
        else:
            reason = "degenerate_knee_geometry"

    quality = {
        "available": left_po_available and right_po_available,
        "left_po_available": left_po_available,
        "right_po_available": right_po_available,
        "primary_outcomes_complete": left_po_available and right_po_available,
        "control_factors_complete": control_factors_complete,
        "missing_or_low_quality_landmarks": missing,
        "mean_visibility": mean_visibility(landmarks),
        "reason": reason,
    }

    return FrameEvidence(
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        quality=quality,
        primary_outcomes={
            "left_knee_sagittal_deg": left_po,
            "right_knee_sagittal_deg": right_po,
        },
        control_factors=control_factors,
    )


def missing_evidence(frame_index: int, timestamp_seconds: float) -> FrameEvidence:
    """A fully unavailable FrameEvidence (used when world landmarks are absent)."""
    return build_frame_evidence({}, frame_index, timestamp_seconds)