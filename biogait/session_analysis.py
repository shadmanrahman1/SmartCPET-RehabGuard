"""BioGait temporal session analysis (M3, Sprint A) + session export schema (M4).

Contains a bounded session accumulator and DESCRIPTIVE temporal features.

All features here are descriptive kinematics only — they are NOT clinical
scores, pass/fail, risk, or rehabilitation-quality judgements. No clinical
thresholds live in this module.

Data model: frames are retained in arrival order. ``aligned_arrays()``
preserves EVERY retained frame, keeping ``None`` entries for unavailable/
no-pose frames so temporal gaps are never silently compressed.
``finite_arrays()`` (valid-only) is used only where valid-only alignment is
explicitly required (e.g. effective sampling-rate estimation).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from evidence_features import RESEARCH_EXERCISE

SESSION_SCHEMA_VERSION = "1.0"

# Selected control-factor streams retained by the accumulator.
# NOTE: knee_delta_y_m is the reviewed source's signed Y-coordinate difference
# (deltayknee = Knee_R(:,2) - Knee_L(:,2)); knee_euclidean_3d_m is a separate
# DESCRIPTIVE Euclidean distance that is NOT presented as the source's d_k.
SELECTED_CONTROL_FACTOR_STREAMS = (
    "wrist_distance_m",
    "shoulder_distance_m",
    "hip_distance_m",
    "knee_euclidean_3d_m",
    "knee_delta_y_m",
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

# Structural data-safety policy: forbidden KEY NAMES (recursive). Values are
# NOT scanned for substrings (that would reject benign scientific text such as
# "landmark name"); only these exact key names are rejected.
FORBIDDEN_EXPORT_KEYS = {
    "patient",
    "patient_id",
    "patient_name",
    "participant_id",
    "participant_name",
    "subject_name",
    "subject_id",
    "email",
}


class SessionAccumulator:
    """Bounded, testable session accumulator for frame evidence.

    Accepts frame-evidence dicts (e.g. ``FrameEvidence.to_dict()``), keeps a
    bounded window in arrival order, and distinguishes:

    - lifetime counters (``total_added``, ``available_count``,
      ``unavailable_count``), and
    - retained-window counters (``retained_available_count``,
      ``retained_unavailable_count``, ``retained_availability_rate``) for the
      rolling live window.

    ``aligned_arrays()`` preserves every retained frame (missing values stay
    ``None``); invalid/missing samples are never dropped silently.
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

    # ── lifetime counters ─────────────────────────────────────────────────
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

    # ── retained-window counters ──────────────────────────────────────────
    @property
    def retained_available_count(self) -> int:
        return sum(
            1 for f in self._frames if f["quality"].get("available")
        )

    @property
    def retained_unavailable_count(self) -> int:
        return self.retained_frames - self.retained_available_count

    @property
    def retained_availability_rate(self) -> Optional[float]:
        if not self._frames:
            return None
        return self.retained_available_count / self.retained_frames

    # ── exports ───────────────────────────────────────────────────────────
    def frames(self) -> list[dict]:
        return [dict(f) for f in self._frames]

    def aligned_arrays(self) -> dict[str, list[Optional[float]]]:
        """Aligned arrays preserving EVERY retained frame.

        Each stream has one entry per retained frame in arrival order.
        Unavailable/no-pose frames remain explicit ``None`` entries — no
        sample is silently removed or zero-filled.
        """
        arrays: dict[str, list[Optional[float]]] = {
            name: [] for name in SELECTED_CONTROL_FACTOR_STREAMS
        }
        arrays.update(
            {
                "timestamps_s": [],
                "left_knee_sagittal_deg": [],
                "right_knee_sagittal_deg": [],
            }
        )
        for frame in self._frames:
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

    def finite_arrays(self) -> dict[str, list[float]]:
        """Valid-only arrays (available frames), aligned by output index.

        Used where valid-only data is explicitly acceptable (e.g. sample-rate
        estimation). For gap-preserving analysis prefer :meth:`aligned_arrays`.
        """
        arrays: dict[str, list[float]] = {
            name: [] for name in SELECTED_CONTROL_FACTOR_STREAMS
        }
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
        """Effective sampling rate (Hz) from valid timestamps (median interval).

        Returns None with fewer than two valid samples.
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

def _range_deg(values: Sequence[Optional[float]]) -> Optional[float]:
    finite = [float(v) for v in values if v is not None]
    if len(finite) < 2:
        return None
    return max(finite) - min(finite)


def _aligned_angular_velocity(
    values: Sequence[Optional[float]],
    timestamps: Sequence[Optional[float]],
) -> list[float]:
    """Index-aligned finite-difference angular velocity (deg/s).

    An interval is computed ONLY when both adjacent angle values are finite
    and both aligned timestamps are valid and strictly increasing. Gaps /
    missing frames are skipped — never bridged as though they did not exist.
    """
    result: list[float] = []
    for i in range(1, len(values)):
        a_prev, a_cur = values[i - 1], values[i]
        t_prev, t_cur = timestamps[i - 1], timestamps[i]
        if a_prev is None or a_cur is None:
            continue
        if t_prev is None or t_cur is None:
            continue
        dt = t_cur - t_prev
        if dt <= 0:
            continue
        result.append((a_cur - a_prev) / dt)
    return result


def _abs_stats_deg_s(values: Sequence[float]) -> tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    abs_vals = [abs(v) for v in values]
    return max(abs_vals), sum(abs_vals) / len(abs_vals)


def descriptive_temporal_features(
    aligned_arrays: Mapping[str, Sequence[Optional[float]]],
    fs: Optional[float] = None,
) -> dict:
    """DESCRIPTIVE temporal features from index-aligned angle/time streams.

    These are descriptive kinematics only — never good/bad, correct/
    incorrect, risk, or a rehabilitation score. Values are None when data
    is insufficient (never faked). Candidate-event analysis (reference event
    counts and durations) intentionally does NOT live here; that belongs
    under the export's ``temporal_analysis`` provenance branches.
    """
    timestamps = list(aligned_arrays.get("timestamps_s", []))
    left = list(aligned_arrays.get("left_knee_sagittal_deg", []))
    right = list(aligned_arrays.get("right_knee_sagittal_deg", []))

    session_duration = None
    if len(timestamps) >= 2 and timestamps[0] is not None and timestamps[-1] is not None:
        session_duration = float(timestamps[-1] - timestamps[0])

    effective_fs = fs
    if effective_fs is None and len(timestamps) >= 2:
        diffs = [
            b - a
            for a, b in zip(timestamps, timestamps[1:])
            if a is not None and b is not None and b > a
        ]
        if diffs:
            median_dt = float(np.median(diffs))
            if median_dt > 0:
                effective_fs = 1.0 / median_dt

    left_omega = _aligned_angular_velocity(left, timestamps)
    right_omega = _aligned_angular_velocity(right, timestamps)
    left_peak, left_mean = _abs_stats_deg_s(left_omega)
    right_peak, right_mean = _abs_stats_deg_s(right_omega)

    left_rom = _range_deg(left)
    right_rom = _range_deg(right)
    rom_difference = (
        abs(left_rom - right_rom)
        if left_rom is not None and right_rom is not None
        else None
    )

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
    }


def _round_optional(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


# ── Structured session export (Phase I) ───────────────────────────────────────

def _validate_no_forbidden_keys(obj: Any, path: str = "") -> None:
    """Recursively reject forbidden KEYS (data-safety, structural, not String).

    Raises ``ValueError`` on the first forbidden key. Values are not
    substring-scanned, so benign scientific text (e.g. "landmark name") is
    unaffected. Unlike ``assert``, this executes regardless of ``-O``.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_name = str(key)
            if key_name in FORBIDDEN_EXPORT_KEYS:
                raise ValueError(
                    f"forbidden key {key_name!r} at {path or '<root>'}"
                )
            _validate_no_forbidden_keys(value, f"{path}.{key_name}")
    elif isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            _validate_no_forbidden_keys(item, f"{path}[{index}]")


def build_session_export(
    *,
    source: dict,
    method_provenance: dict,
    quality_summary: dict,
    frames: Sequence[dict],
    session_descriptors: dict,
    temporal_analysis: dict,
    limitations: Sequence[str],
    include_frames: bool = True,
) -> dict:
    """Versioned research-session export object (no secrets, no PII).

    ``source`` must NOT carry local/absolute input paths (see
    ``analyze_video.py`` which writes ``source_type``/``fps`` metadata
    instead). ``temporal_analysis`` holds the reference/adapted provenance
    branches, each with per-side analysis and a generic summary (no unified
    repetition count; bilateral pairing deferred). Forbidden keys are rejected
    structurally via :func:`_validate_no_forbidden_keys`.
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
        "temporal_analysis": dict(temporal_analysis),
        "limitations": list(limitations),
    }
    _validate_no_forbidden_keys(export)
    return export