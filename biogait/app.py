from __future__ import annotations

import csv
from datetime import datetime
import json
import time
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp

import config
from metrics import add_session_fields, calculate_pose_metrics, no_pose_metrics
from pose_utils import draw_camera_warning, draw_metrics_panel, extract_landmarks


CSV_FIELDS = [
    "timestamp",
    "elapsed_seconds",
    "frame_index",
    "tracking_status",
    "left_knee_angle",
    "right_knee_angle",
    "trunk_lean",
    "knee_asymmetry",
    "hip_imbalance",
    "ankle_alignment_delta",
    "average_visibility",
    "risk_score",
    "risk_level",
    "reasons",
    "missing_landmarks",
]


def write_latest_metrics(metrics: dict[str, Any]) -> None:
    temp_path = config.LATEST_METRICS_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)
    temp_path.replace(config.LATEST_METRICS_PATH)


def reset_session_files() -> None:
    config.ensure_output_dirs()
    with config.SESSION_METRICS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
    write_latest_metrics(
        add_session_fields(no_pose_metrics(), frame_index=0, elapsed_seconds=0.0)
    )


def csv_safe_row(metrics: dict[str, Any]) -> dict[str, Any]:
    row = {field: metrics.get(field) for field in CSV_FIELDS}
    row["reasons"] = "; ".join(metrics.get("reasons", []))
    row["missing_landmarks"] = "; ".join(metrics.get("missing_landmarks", []))
    return row


def append_session_metrics(metrics: dict[str, Any]) -> None:
    with config.SESSION_METRICS_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writerow(csv_safe_row(metrics))


def save_screenshot(frame: Any) -> Path:
    config.ensure_output_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = config.SCREENSHOT_DIR / f"biogait_{timestamp}.png"
    cv2.imwrite(str(path), frame)
    return path


def open_capture(source: int | str) -> cv2.VideoCapture:
    if isinstance(source, int):
        capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(source)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        capture.set(cv2.CAP_PROP_FPS, config.FRAME_FPS)
        return capture
    capture = cv2.VideoCapture(source)
    return capture


def main() -> None:
    config.ensure_output_dirs()
    reset_session_files()

    camera_source = config.get_camera_source()
    capture = open_capture(camera_source)
    if not capture.isOpened():
        raise RuntimeError(
            "Camera could not be opened. Check CAMERA_SOURCE in config.py or the "
            "BIOGAIT_CAMERA_SOURCE environment variable."
        )

    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    frame_index = 0
    session_started = time.time()
    last_latest_write = 0.0
    last_csv_write = 0.0

    with mp_pose.Pose(
        model_complexity=config.POSE_MODEL_COMPLEXITY,
        min_detection_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE,
    ) as pose:
        while True:
            success, frame = capture.read()
            if not success:
                blank = 255 * cv2.UMat(480, 720, cv2.CV_8UC3).get()
                draw_camera_warning(blank, "Waiting for camera frame...")
                cv2.imshow(config.WINDOW_NAME, blank)
                if cv2.waitKey(500) & 0xFF == ord("q"):
                    break
                continue

            frame_index += 1
            if isinstance(camera_source, int) and config.MIRROR_LAPTOP_WEBCAM:
                frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            results = pose.process(rgb_frame)

            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
                )
                landmarks = extract_landmarks(results.pose_landmarks, mp_pose)
                metrics = calculate_pose_metrics(landmarks)
            else:
                metrics = no_pose_metrics()

            elapsed_seconds = time.time() - session_started
            metrics = add_session_fields(metrics, frame_index, elapsed_seconds)
            draw_metrics_panel(frame, metrics)

            now = time.time()
            if now - last_latest_write >= config.LATEST_WRITE_INTERVAL_SECONDS:
                write_latest_metrics(metrics)
                last_latest_write = now
            if now - last_csv_write >= config.CSV_WRITE_INTERVAL_SECONDS:
                append_session_metrics(metrics)
                last_csv_write = now

            cv2.imshow(config.WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == ord("s"):
                screenshot_path = save_screenshot(frame)
                print(f"Saved screenshot: {screenshot_path}")
            if key == ord("r"):
                session_started = time.time()
                frame_index = 0
                reset_session_files()
                print("Session metrics reset.")

    capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
