"""BioGait temporal session analysis (M3, Sprint A) + session export schema (M4).

Contains a bounded session accumulator and DESCRIPTIVE temporal features.

All features here are descriptive kinematics only — they are NOT clinical
scores, pass/fail, risk, or rehabilitation-quality judgements. No clinical
thresholds live in this module.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Optional, Sequence

import numpy as np

from evidence_features import RESEARCH_EXERCISE
from reference_temporal import merge_side_events

SESSION_SCHEMA_VERSION = "1.0"

# Selected control-factor streams retained by the accumulator.
SELECTED_CONTROL_FACTOR_STREAMS = (
    "wrist_distance_m",
    "shoulder_distance_m",
    "hip_distance_m",
    "knee_distance_m",
    "ankle_distance_m",
    "left_wrist_shoulder_distance_m",
    "right_wrist_shoulder_distance_m",
    "torso_area_m2",
    "left_shoulder_x_m",
    "left_shoulder_z_m",
    "right_shoulder_x_m",
    "right_shoulder_z_m",
)

_REQUIRED_EVIDENCE_KEYS = (
    "schema_version",
    "exercise",
    "frame_index",
    "timestamp_seconds",
    "quality",
    "primary_outcomes",
)


class SessionAccumulator:
    """Bounded, testable session accumulator for frame evidence.

    Accepts frame-evidence dicts (e.g. ``FrameEvidence.to_dict()``), keeps a
    bounded window in arrival order, tracks dropped/unavailable frames, and
    exports finite arrays built only from frames whose research evidence is
    available. Invalid/missing samples are never mixed in silently.
    """

    def __init__(self, max_frames: Optional[int] = None) -> None:
        self._max_frames = max_frames
        self._frames: deque[dict] = deque(maxlen=max_frames)
        self._added = 0
        self._available = 0
        self._unavailable = 0
        self._evicted = 0

    # ── ingestion ─────────────────────────────────────────────────────────
    def add(self, evidence: dict) -> None:
        for key in _REQUIRED_EVIDENCE_KEYS:
            if key not in evidence:
                raise ValueError(f"evidence missing required key: {key}")

        if (
            self._max_frames is not None
            and len(self._frames) >= self._max_frames
        ):
            self._frames.popleft()
            self._evicted += 1

        self._frames.append(dict(evidence))
        self._added += 1
        if evidence["quality"].get("available"):
            self._available += 1
        else:
            self._unavailable += 1

    # ── counters ──────────────────────────────────────────────────────────
    @property
    def total_added(self) -> int:
        return self._added

    @property
    def available_count(self) -> int:
        return self._available

    @property
    def unavailable_count(self) -> int:
        return self._unavailable

    @property
    def evicted_count(self) -> int:
        return self._evicted

    @property
    def retained_frames(self) -> int:
        return len(self._frames)

    # ── exports ───────────────────────────────────────────────────────────
    def frames(self) -> list[dict]:
        return [dict(f) for f in self._frames]

    def finite_arrays(self) -> dict[str, list[float]]:
        """Finite arrays from available frames only (aligned by index).

        Missing samples are excluded, not zero-padded. When no available
        frames exist, every stream is an empty list.
        """
        arrays: dict[str, list[float]] = {name: [] for name in SELECTED_CONTROL_FACTOR_STREAMS}
        arrays.update(
            {
                "timestamps_s": [],
                "left_knee_sagittal_deg": [],
                "right_knee_sagittal_deg": [],
            }
        )
        for frame in self._frames:
            if not frame["quality"].get("available"):
                continue
            arrays["timestamps_s"].append(float(frame["timestamp_seconds"]))
            arrays["left_knee_sagittal_deg"].append(
                frame["primary_outcomes"]["left_knee_sagittal_deg"]
            )
            arrays["right_knee_sagittal_deg"].append(
                frame["primary_outcomes"]["right_knee_sagittal_deg"]
            )
            for name in SELECTED_CONTROL_FACTOR_STREAMS:
                value = frame["control_factors"].get(name)
                arrays[name].append(float(value) if value is not None else None)
        return arrays

    def effective_sample_rate(self) -> Optional[float]:
        """Effective sampling rate (Hz) estimated from available timestamps.

        Uses the median of consecutive positive inter-sample intervals to be
        robust against dropped frames. Returns None with <2 samples.
        """
        timestamps = self.finite_arrays()["timestamps_s"]
        if len(timestamps) < 2:
            return None
        diffs = [
            b - a
            for a, b in zip(timestamps, timestamps[1:])
            if b - a > 0
        ]
        if not diffs:
            return None
        median_dt = float(np.median(diffs))
        if median_dt <= 0:
            return None
        return 1.0 / median_dt


# ── Descriptive temporal features (Phase G) ───────────────────────────────────

def _range_deg(values: Sequence[float]) -> Optional[float]:
    finite = [float(v) for v in values if v is not None]
    if len(finite) < 2:
        return None
    return max(finite) - min(finite)


def _angular_velocity(
    values: Sequence[float], timestamps: Sequence[float]
) -> list[float]:
    finite = [float(v) for v in values if v is not None]
    if len(finite) < 2 or len(timestamps) < 2:
        return []
    ts = np.asarray([float(t) for t in timestamps[: len(finite)]])
    dt = np.diff(ts)
    with np.errstate(divide="ignore", invalid="ignore"):
        omega = np.diff(finite) / dt
    return [float(v) for v in omega[np.isfinite(omega)]]


def _abs_stats_deg_s(values: Sequence[float]) -> tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    abs_vals = [abs(v) for v in values]
    return max(abs_vals), sum(abs_vals) / len(abs_vals)


def descriptive_temporal_features(
    arrays: dict[str, list[float]],
    reference_summary: Optional[dict] = None,
    fs: Optional[float] = None,
) -> dict:
    """DESCRIPTIVE temporal features from valid angle/time streams.

    These are descriptive kinematics only — never good/bad, correct/
    incorrect, risk, or a rehabilitation score. Values are None when data
    is insufficient (never faked).
    """
    timestamps = arrays.get("timestamps_s", [])
    left = arrays.get("left_knee_sagittal_deg", [])
    right = arrays.get("right_knee_sagittal_deg", [])

    session_duration = None
    if len(timestamps) >= 2:
        session_duration = float(timestamps[-1] - timestamps[0])

    effective_fs = fs
    if effective_fs is None and len(timestamps) >= 2:
        diffs = [b - a for a, b in zip(timestamps, timestamps[1:]) if b - a > 0]
        if diffs:
            median_dt = float(np.median(diffs))
            if median_dt > 0:
                effective_fs = 1.0 / median_dt

    left_omega = _angular_velocity(left, timestamps)
    right_omega = _angular_velocity(right, timestamps)
    left_peak, left_mean = _abs_stats_deg_s(left_omega)
    right_peak, right_mean = _abs_stats_deg_s(right_omega)

    left_rom = _range_deg(left)
    right_rom = _range_deg(right)
    rom_difference = (
        abs(left_rom - right_rom)
        if left_rom is not None and right_rom is not None
        else None
    )

    n_candidates = None
    durations: Optional[list[float]] = None
    if reference_summary:
        n_candidates = reference_summary.get("n_reference_event_candidates")
        durations = reference_summary.get("candidate_repetition_durations_s")

    return {
        "session_duration_s": session_duration,
        "effective_sample_rate_hz": (
            round(effective_fs, 4) if effective_fs is not None else None
        ),
        "left_knee_rom_deg": _round_optional(left_rom),
        "right_knee_rom_deg": _round_optional(right_rom),
        "left_right_rom_difference_deg": _round_optional(rom_difference),
        "left_peak_abs_angular_velocity_deg_s": _round_optional(left_peak),
        "left_mean_abs_angular_velocity_deg_s": _round_optional(left_mean),
        "right_peak_abs_angular_velocity_deg_s": _round_optional(right_peak),
        "right_mean_abs_angular_velocity_deg_s": _round_optional(right_mean),
        "left_angular_velocity_deg_s": [round(v, 4) for v in left_omega],
        "right_angular_velocity_deg_s": [round(v, 4) for v in right_omega],
        "n_reference_event_candidates": n_candidates,
        "candidate_repetition_durations_s": (
            [round(float(d), 4) for d in durations]
            if durations is not None
            else None
        ),
    }


def _round_optional(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


# ── Structured session export (Phase I) ───────────────────────────────────────

def build_session_export(
    *,
    source: dict,
    method_provenance: dict,
    quality_summary: dict,
    frames: Sequence[dict],
    session_descriptors: dict,
    kimore_reference_analysis: dict,
    limitations: Sequence[str],
    include_frames: bool = True,
) -> dict:
    """Versioned research-session export object (no secrets, no PII).

    ``frames`` accepts the list of FrameEvidence dicts; pass already-sliced
    frames (or rely on the accumulator window) to bound the output size.
    """
    export: dict[str, Any] = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "module": "biogait",
        "exercise": RESEARCH_EXERCISE,
        "source": dict(source),
        "method_provenance": dict(method_provenance),
        "quality_summary": dict(quality_summary),
        "frames": list(frames) if include_frames else [],
        "session_descriptors": dict(session_descriptors),
        "kimore_reference_analysis": dict(kimore_reference_analysis),
        "limitations": list(limitations),
    }
    # Guard against accidental PII placeholders in exports.
    for forbidden in ("patient", "name", "subject_id"):
        assert forbidden not in str(export).lower(), (
            f"sensitive field {forbidden!r} guard triggered in session export"
        )
    return export