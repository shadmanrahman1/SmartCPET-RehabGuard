from __future__ import annotations

from typing import Any

import cv2


LANDMARK_NAME_MAP = {
    "left_shoulder": "LEFT_SHOULDER",
    "right_shoulder": "RIGHT_SHOULDER",
    "left_hip": "LEFT_HIP",
    "right_hip": "RIGHT_HIP",
    "left_knee": "LEFT_KNEE",
    "right_knee": "RIGHT_KNEE",
    "left_ankle": "LEFT_ANKLE",
    "right_ankle": "RIGHT_ANKLE",
}

RISK_COLORS = {
    "LOW": (82, 196, 118),
    "MODERATE": (35, 178, 230),
    "HIGH": (84, 92, 255),
}


def extract_landmarks(pose_landmarks: Any, mp_pose: Any) -> dict[str, dict[str, float]]:
    landmarks: dict[str, dict[str, float]] = {}
    for simple_name, mediapipe_name in LANDMARK_NAME_MAP.items():
        landmark_id = getattr(mp_pose.PoseLandmark, mediapipe_name).value
        landmark = pose_landmarks.landmark[landmark_id]
        landmarks[simple_name] = {
            "x": float(landmark.x),
            "y": float(landmark.y),
            "z": float(landmark.z),
            "visibility": float(landmark.visibility),
        }
    return landmarks


def format_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "--"
    return f"{value}{suffix}"


def draw_text(
    frame: Any,
    text: str,
    origin: tuple[int, int],
    scale: float = 0.65,
    color: tuple[int, int, int] = (245, 248, 252),
    thickness: int = 1,
) -> None:
    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_metrics_panel(frame: Any, metrics: dict[str, Any]) -> None:
    height, width = frame.shape[:2]
    panel_width = min(500, width - 24)
    panel_height = 250

    overlay = frame.copy()
    cv2.rectangle(overlay, (12, 12), (12 + panel_width, 12 + panel_height), (20, 28, 38), -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

    risk_level = metrics.get("risk_level", "LOW")
    risk_score = metrics.get("risk_score", 0)
    risk_color = RISK_COLORS.get(risk_level, (245, 248, 252))

    draw_text(frame, "SmartCPET-RehabGuard BioGait", (28, 42), 0.68, (255, 255, 255), 2)
    draw_text(frame, f"Status: {metrics.get('tracking_status', '--')}", (28, 72), 0.58)
    draw_text(frame, f"Risk: {risk_level}  {risk_score}/100", (28, 104), 0.72, risk_color, 2)

    lines = [
        f"Left knee: {format_value(metrics.get('left_knee_angle'), ' deg')}",
        f"Right knee: {format_value(metrics.get('right_knee_angle'), ' deg')}",
        f"Knee asymmetry: {format_value(metrics.get('knee_asymmetry'), ' deg')}",
        f"Trunk lean: {format_value(metrics.get('trunk_lean'), ' deg')}",
        f"Landmark confidence: {format_value(metrics.get('average_visibility'))}",
    ]

    y = 136
    for line in lines:
        draw_text(frame, line, (28, y), 0.57)
        y += 27

    controls = "q quit | s screenshot | r reset session"
    draw_text(frame, controls, (18, height - 18), 0.56, (230, 235, 242), 1)


def draw_camera_warning(frame: Any, message: str) -> None:
    height, width = frame.shape[:2]
    text_size, _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    x = max(12, (width - text_size[0]) // 2)
    y = max(48, height // 2)
    cv2.rectangle(frame, (x - 12, y - 34), (x + text_size[0] + 12, y + 12), (28, 28, 38), -1)
    draw_text(frame, message, (x, y), 0.75, (255, 255, 255), 2)
