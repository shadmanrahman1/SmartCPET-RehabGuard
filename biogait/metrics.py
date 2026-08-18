from __future__ import annotations

from datetime import datetime
import math
from typing import Any

import config


LEFT_KNEE_POINTS = ("left_hip", "left_knee", "left_ankle")
RIGHT_KNEE_POINTS = ("right_hip", "right_knee", "right_ankle")
TRUNK_POINTS = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
HIP_POINTS = ("left_hip", "right_hip")
ANKLE_POINTS = ("left_ankle", "right_ankle")
REQUIRED_POINTS = tuple(
    dict.fromkeys(LEFT_KNEE_POINTS + RIGHT_KNEE_POINTS + TRUNK_POINTS + ANKLE_POINTS)
)


def round_optional(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def angle_between_points(
    point_a: dict[str, float],
    point_b: dict[str, float],
    point_c: dict[str, float],
) -> float:
    """Return the 2D angle at point_b in degrees."""
    vector_ba = (point_a["x"] - point_b["x"], point_a["y"] - point_b["y"])
    vector_bc = (point_c["x"] - point_b["x"], point_c["y"] - point_b["y"])

    norm_ba = math.hypot(*vector_ba)
    norm_bc = math.hypot(*vector_bc)
    if norm_ba == 0 or norm_bc == 0:
        return 0.0

    cosine = (
        vector_ba[0] * vector_bc[0] + vector_ba[1] * vector_bc[1]
    ) / (norm_ba * norm_bc)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def midpoint(point_a: dict[str, float], point_b: dict[str, float]) -> dict[str, float]:
    return {
        "x": (point_a["x"] + point_b["x"]) / 2.0,
        "y": (point_a["y"] + point_b["y"]) / 2.0,
        "z": (point_a.get("z", 0.0) + point_b.get("z", 0.0)) / 2.0,
        "visibility": (point_a.get("visibility", 0.0) + point_b.get("visibility", 0.0))
        / 2.0,
    }


def trunk_lean_angle(
    left_shoulder: dict[str, float],
    right_shoulder: dict[str, float],
    left_hip: dict[str, float],
    right_hip: dict[str, float],
) -> float:
    """Return trunk lean from image vertical in degrees."""
    shoulder_mid = midpoint(left_shoulder, right_shoulder)
    hip_mid = midpoint(left_hip, right_hip)
    dx = shoulder_mid["x"] - hip_mid["x"]
    dy = shoulder_mid["y"] - hip_mid["y"]
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def points_are_visible(
    landmarks: dict[str, dict[str, float]],
    names: tuple[str, ...],
    threshold: float = config.MIN_LANDMARK_VISIBILITY,
) -> bool:
    return all(
        name in landmarks and landmarks[name].get("visibility", 0.0) >= threshold
        for name in names
    )


def average_visibility(landmarks: dict[str, dict[str, float]]) -> float:
    values = [
        landmarks[name].get("visibility", 0.0)
        for name in REQUIRED_POINTS
        if name in landmarks
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)


def missing_landmarks(landmarks: dict[str, dict[str, float]]) -> list[str]:
    return [
        name
        for name in REQUIRED_POINTS
        if name not in landmarks
        or landmarks[name].get("visibility", 0.0) < config.MIN_LANDMARK_VISIBILITY
    ]


def calculate_risk_score(metrics: dict[str, Any]) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []

    knee_asymmetry = metrics.get("knee_asymmetry")
    if knee_asymmetry is None:
        score += 10
        reasons.append("Knee angle measurement is not reliable")
    elif knee_asymmetry > config.KNEE_ASYMMETRY_HIGH_DEG:
        score += 25
        reasons.append("High knee angle asymmetry")
    elif knee_asymmetry > config.KNEE_ASYMMETRY_MODERATE_DEG:
        score += 12
        reasons.append("Mild knee angle asymmetry")

    trunk_lean = metrics.get("trunk_lean")
    if trunk_lean is None:
        score += 10
        reasons.append("Trunk lean measurement is not reliable")
    elif trunk_lean > config.TRUNK_LEAN_HIGH_DEG:
        score += 20
        reasons.append("High trunk lean")
    elif trunk_lean > config.TRUNK_LEAN_MODERATE_DEG:
        score += 10
        reasons.append("Moderate trunk lean")

    hip_imbalance = metrics.get("hip_imbalance")
    if hip_imbalance is not None and hip_imbalance > config.HIP_IMBALANCE_WARNING:
        score += 15
        reasons.append("Visible left-right hip height imbalance")

    ankle_alignment_delta = metrics.get("ankle_alignment_delta")
    if (
        ankle_alignment_delta is not None
        and ankle_alignment_delta > config.ANKLE_ALIGNMENT_WARNING
    ):
        score += 15
        reasons.append("Visible ankle alignment difference")

    if metrics.get("average_visibility", 1.0) < config.LOW_CONFIDENCE_AVG_VISIBILITY:
        score += 10
        reasons.append("Low landmark confidence")

    if metrics.get("missing_landmarks"):
        score += 10
        reasons.append("Some body landmarks are missing or partly hidden")

    score = min(100, score)
    if score <= 30:
        level = "LOW"
    elif score <= 60:
        level = "MODERATE"
    else:
        level = "HIGH"

    if not reasons:
        reasons.append("No major camera-visible risk indicators detected")

    return score, level, reasons


def calculate_pose_metrics(landmarks: dict[str, dict[str, float]]) -> dict[str, Any]:
    left_knee_angle = None
    right_knee_angle = None
    trunk_lean = None
    knee_asymmetry = None
    hip_imbalance = None
    ankle_alignment_delta = None

    if points_are_visible(landmarks, LEFT_KNEE_POINTS):
        left_knee_angle = angle_between_points(
            landmarks["left_hip"], landmarks["left_knee"], landmarks["left_ankle"]
        )

    if points_are_visible(landmarks, RIGHT_KNEE_POINTS):
        right_knee_angle = angle_between_points(
            landmarks["right_hip"], landmarks["right_knee"], landmarks["right_ankle"]
        )

    if points_are_visible(landmarks, TRUNK_POINTS):
        trunk_lean = trunk_lean_angle(
            landmarks["left_shoulder"],
            landmarks["right_shoulder"],
            landmarks["left_hip"],
            landmarks["right_hip"],
        )

    if left_knee_angle is not None and right_knee_angle is not None:
        knee_asymmetry = abs(left_knee_angle - right_knee_angle)

    if points_are_visible(landmarks, HIP_POINTS):
        hip_imbalance = abs(landmarks["left_hip"]["y"] - landmarks["right_hip"]["y"])

    if points_are_visible(landmarks, ANKLE_POINTS):
        ankle_alignment_delta = abs(
            landmarks["left_ankle"]["y"] - landmarks["right_ankle"]["y"]
        )

    metrics: dict[str, Any] = {
        "left_knee_angle": round_optional(left_knee_angle),
        "right_knee_angle": round_optional(right_knee_angle),
        "trunk_lean": round_optional(trunk_lean),
        "knee_asymmetry": round_optional(knee_asymmetry),
        "hip_imbalance": round_optional(hip_imbalance, 3),
        "ankle_alignment_delta": round_optional(ankle_alignment_delta, 3),
        "average_visibility": round_optional(average_visibility(landmarks), 3),
        "missing_landmarks": missing_landmarks(landmarks),
        "tracking_status": "TRACKING",
    }

    score, level, reasons = calculate_risk_score(metrics)
    metrics.update(
        {
            "risk_score": score,
            "risk_level": level,
            "reasons": reasons,
            "screening_note": "Screening output only; not a clinical diagnosis.",
        }
    )
    return metrics


def no_pose_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "left_knee_angle": None,
        "right_knee_angle": None,
        "trunk_lean": None,
        "knee_asymmetry": None,
        "hip_imbalance": None,
        "ankle_alignment_delta": None,
        "average_visibility": 0.0,
        "missing_landmarks": list(REQUIRED_POINTS),
        "tracking_status": "NO_POSE",
    }
    score, level, reasons = calculate_risk_score(metrics)
    metrics.update(
        {
            "risk_score": score,
            "risk_level": level,
            "reasons": ["No pose detected. Keep the full body inside the camera view."]
            + reasons,
            "screening_note": "Screening output only; not a clinical diagnosis.",
        }
    )
    return metrics


def add_session_fields(
    metrics: dict[str, Any], frame_index: int, elapsed_seconds: float
) -> dict[str, Any]:
    enriched = dict(metrics)
    enriched.update(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "frame_index": frame_index,
            "elapsed_seconds": round(elapsed_seconds, 2),
        }
    )
    return enriched
