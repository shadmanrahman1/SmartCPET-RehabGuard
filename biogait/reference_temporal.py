"""KIMORE temporal analysis for Exercise 5 (squat) — OFFLINE ONLY.

The project is PYTHON-ONLY. The reviewed original KIMORE source was written
in MATLAB; BioGait does not depend on or execute MATLAB. Source equations and
preprocessing conventions are re-implemented in Python for methodological
traceability ("source-aligned KIMORE reference implementation").

Two deliberately separate paths:

- :func:`kimore_reference_ex5_temporal_analysis` — SOURCE-ALIGNED KIMORE
  REFERENCE PATH. Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME.
  Reproduces the reviewed conventions
  (``matlab/matlab_original/feat_extract_Ex5.m`` and ``filtering.m``):

  1. KIMORE source retains samples ``10:end`` in MATLAB (1-based) indexing,
     equivalent to discarding the first 9 samples in zero-based Python —
     i.e. ``values[9:]``;
  2. reference sign-flip handling (negate a sample when the consecutive
     difference is outside [-100, +100] degrees — NOT a +/-360 unwrap);
  3. KIMORE reference zero-phase filter (fixed order 3, 1 Hz, 30 Hz;
     ba-form Butterworth + ``filtfilt``);
  4. maxima detection at ``max(signal)/sqrt(2)``;
  5. minima detection on ``max(signal) - signal`` at its ``max/sqrt(2)``
     threshold;
  6. reference minimum peak distance ``floor(n_samples / 10)``.

  The algorithmic conventions and parameters follow the reviewed KIMORE
  source. Numerical identity with the original MATLAB runtime has not been
  established.

  The exact path requires a complete sample stream (no None/NaN/+-inf) at the
  30 Hz reference convention, and — when timestamps are supplied — timestamps
  that are finite, strictly increasing, and uniform at 30 Hz. Any violation
  returns a structured warning and filtering/peak detection is NOT run.

- :func:`kimore_adapted_ex5_temporal_analysis` — ACTUAL-frame-rate path.
  Classification: ENGINEERING_ADAPTED. Uses the supplied frame rate with the
  order-3 / 1 Hz filter concept, via the separate adapted zero-phase filter.
  It is NOT the exact KIMORE reference pipeline and its results are not
  REFERENCE_DERIVED. Provided timestamps must be finite, strictly increasing,
  and uniform at the supplied ``fs``.

Detected candidates are NOT clinically valid repetitions; no pass/fail is
produced. The KIMORE acquisition protocol involved repeated exercise
execution; its full-sequence peak settings are not automatically valid for an
arbitrary session length. CF temporal trim/filter preprocessing from the
reviewed source remains DEFERRED in Sprint A.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Union

import numpy as np
from scipy import signal as sp_signal

from temporal_filters import (
    kimore_adapted_zero_phase_filter,
    kimore_reference_zero_phase_filter,
)

# MATLAB indexing is 1-based: the reviewed source keeps ``angle = angle(10:end)``,
# i.e. it discards samples 1..9 and retains samples 10..end. The zero-based
# Python equivalent is ``values[9:]`` (NOT ``values[10:]``).
KIMORE_FIRST_RETAINED_MATLAB_SAMPLE = 10
KIMORE_INITIAL_DISCARDED_SAMPLES = 9
KIMORE_WRAP_DIFF_THRESHOLD_DEG = 100.0
KIMORE_PEAK_HEIGHT_FACTOR = 1.0 / math.sqrt(2.0)
KIMORE_REFERENCE_FS_HZ = 30.0

# Tiny numerical tolerance used only to distinguish 30.0 / dt from
# floating-point representation noise — engineering/numerical, not clinical.
_FS_TOLERANCE_HZ = 1e-6
_DT_TOLERANCE_S = 1e-6

ADAPTED_NOTE = (
    "Uses the actual supplied frame rate; not the exact 30 Hz KIMORE "
    "reference pipeline. Results are engineering-adapted, not "
    "REFERENCE_DERIVED."
)


def remove_initial_samples(
    values: Sequence[float], n: int = KIMORE_INITIAL_DISCARDED_SAMPLES
) -> list[float]:
    """Discard the first ``n`` samples (default 9, matching MATLAB ``10:end``).

    ``values[n:]`` — the default discards the first 9 zero-based samples, so
    the first retained element is the original Python index 9 / MATLAB sample
    10.
    """
    if n < 0:
        return list(values)
    return list(values[n:]) if n < len(values) else []


def kimore_reference_sign_flip_correction(
    angles: Sequence[float],
    threshold_deg: float = KIMORE_WRAP_DIFF_THRESHOLD_DEG,
) -> tuple[list[float], int]:
    """Exact KIMORE reference sign-flip correction.

    Source logic concept (Matlab ``feat_extract_Ex5.m`` convention)::

        for j in range(len(angle) - 1):
            difference = angle[j+1] - angle[j]
            if difference < -100 or difference > 100:
                angle[j+1] = -angle[j+1]

    The sequence is modified in place conceptually, so subsequent differences
    use previously corrected values. This is a sign flip (negation), NOT a
    generic +/-360-degree angle unwrap.

    Classification: REFERENCE_DERIVED.

    Returns ``(corrected, n_corrections)``.
    """
    corrected: list[float] = []
    corrections = 0
    for sample in angles:
        if not corrected:
            corrected.append(float(sample))
            continue
        prev = corrected[-1]
        difference = float(sample) - prev
        if difference < -threshold_deg or difference > threshold_deg:
            sample = -float(sample)
            corrections += 1
        corrected.append(float(sample))
    return corrected, corrections


def _min_peak_distance(n_samples: int) -> int:
    """Reference minimum peak distance: ``floor(n_samples / 10)``."""
    return int(math.floor(n_samples / 10.0))


def detect_maxima(
    filtered, distance: int
) -> tuple[list[int], list[float]]:
    """Maxima detection at ``max(signal) / sqrt(2)``."""
    filtered = np.asarray(filtered, dtype=float)
    threshold = float(np.max(filtered)) * KIMORE_PEAK_HEIGHT_FACTOR
    idx, _ = sp_signal.find_peaks(filtered, height=threshold, distance=distance)
    return [int(i) for i in idx], [float(v) for v in filtered[idx]]


def detect_minima(
    filtered, distance: int
) -> tuple[list[int], list[float]]:
    """Minima detection via ``max(signal) - signal`` at its ``max/sqrt(2)``."""
    filtered = np.asarray(filtered, dtype=float)
    transformed = float(np.max(filtered)) - filtered
    threshold = float(np.max(transformed)) * KIMORE_PEAK_HEIGHT_FACTOR
    idx, _ = sp_signal.find_peaks(
        transformed, height=threshold, distance=distance
    )
    idx = np.sort(idx)
    return [int(i) for i in idx], [float(v) for v in filtered[idx]]


# ── Timestamp integrity (item: validate temporal timestamps) ──────────────────

def validate_timestamps(
    timestamps: Optional[Sequence[float]],
    n_samples: int,
    *,
    uniform_at: float,
) -> tuple[bool, Optional[str]]:
    """Validate supplied timestamps: length, finite, strictly increasing, uniform.

    Returns ``(ok, issue)``. When ``timestamps is None`` the caller will
    derive time from ``fs`` instead, so ``(True, None)`` is returned.
    A non-uniform-at-``uniform_at`` result is reported separately.
    """
    if timestamps is None:
        return True, None
    if len(timestamps) != n_samples:
        return False, (
            f"timestamp count ({len(timestamps)}) does not match "
            f"angle count ({n_samples})"
        )
    values = [float(t) for t in timestamps]
    prev = None
    for i, t in enumerate(values):
        if t is None or not math.isfinite(t):
            return False, f"timestamp {i} is missing or non-finite"
        if prev is not None and t <= prev:
            return False, f"timestamps are not strictly increasing at index {i}"
        prev = t
    expected_dt = 1.0 / uniform_at
    for i in range(1, len(values)):
        dt = values[i] - values[i - 1]
        if not math.isclose(dt, expected_dt, rel_tol=0.0, abs_tol=_DT_TOLERANCE_S):
            return False, (
                f"timestamps are not uniform at {uniform_at} Hz "
                f"(interval {dt:.6f} s at index {i})"
            )
    return True, None


def _base_result(
    *,
    fs: float,
    trim_removed: int = KIMORE_INITIAL_DISCARDED_SAMPLES,
) -> dict:
    return {
        "fs_hz": fs,
        "n_initial_samples_removed": trim_removed,
        "first_retained_matlab_sample": KIMORE_FIRST_RETAINED_MATLAB_SAMPLE,
        "source_index_convention": "zero_based_python_index",
        "trimmed_length": 0,
        "filtered_signal": [],
        "maxima_indices": [],
        "maxima_values": [],
        "minima_indices": [],
        "minima_values": [],
        "event_candidates": [],
        "candidate_repetition_durations_s": [],
    }


def _run_ex5_pipeline(
    angles: Sequence[float],
    timestamps: Optional[Sequence[float]],
    fs: float,
    filter_fn,
    classification: str,
    adapted_note: Optional[str] = None,
) -> dict:
    """Shared offline Ex5 pipeline mechanics (trim, sign-flip, filter, extrema).

    ``angles`` are pre-validated: complete finite samples (no None/NaN/+-inf).
    ``filter_fn`` selects the REFERENCE vs ADAPTED zero-phase filter so the
    source-aligned reference path can never call a non-30 Hz filter and the
    adapted path never claims to be the reference filter.
    """
    if len(angles) <= KIMORE_INITIAL_DISCARDED_SAMPLES:
        result = _base_result(fs=fs)
        result["classification"] = classification
        result["offline"] = True
        result["warning"] = "insufficient_samples_after_trimming"
        if adapted_note:
            result["adapted_note"] = adapted_note
        return result

    trimmed = remove_initial_samples(angles)
    corrected, n_corrections = kimore_reference_sign_flip_correction(trimmed)

    try:
        filtered = filter_fn(corrected)
    except ValueError as exc:
        result = _base_result(fs=fs)
        result["classification"] = classification
        result["offline"] = True
        result["trimmed_length"] = len(corrected)
        result["warning"] = f"insufficient_samples_for_filter: {exc}"
        if adapted_note:
            result["adapted_note"] = adapted_note
        return result

    if len(filtered) < 3:
        result = _base_result(fs=fs)
        result["classification"] = classification
        result["offline"] = True
        result["trimmed_length"] = len(corrected)
        result["filtered_signal"] = [float(v) for v in filtered]
        result["warning"] = "insufficient_filtered_samples"
        if adapted_note:
            result["adapted_note"] = adapted_note
        return result

    distance = _min_peak_distance(len(filtered))
    max_idx, max_vals = detect_maxima(filtered, distance)
    min_idx, min_vals = detect_minima(filtered, distance)

    def _time_of(stream_index: int) -> float:
        original_index = stream_index + KIMORE_INITIAL_DISCARDED_SAMPLES
        if timestamps is not None:
            return float(timestamps[original_index])
        # No explicit timestamps: time_s refers to the ORIGINAL source-session
        # timeline via the zero-based source index (never restarting at 0).
        return original_index / fs

    events = [
        {
            "index": int(i),
            "original_index": int(i + KIMORE_INITIAL_DISCARDED_SAMPLES),
            "time_s": _time_of(i),
            "type": "max",
        }
        for i in max_idx
    ] + [
        {
            "index": int(i),
            "original_index": int(i + KIMORE_INITIAL_DISCARDED_SAMPLES),
            "time_s": _time_of(i),
            "type": "min",
        }
        for i in min_idx
    ]
    events.sort(key=lambda e: e["index"])

    durations: list[float] = []
    for i in range(1, len(max_idx)):
        durations.append(_time_of(max_idx[i]) - _time_of(max_idx[i - 1]))
    durations = [d for d in durations if d > 0]

    result = _base_result(fs=fs)
    result.update(
        {
            "classification": classification,
            "offline": True,
            "warning": None,
            "n_sign_corrections": n_corrections,
            "trimmed_length": len(corrected),
            "min_peak_distance": distance,
            "filtered_signal": [float(v) for v in filtered],
            "maxima_indices": max_idx,
            "maxima_values": max_vals,
            "minima_indices": min_idx,
            "minima_values": min_vals,
            "event_candidates": events,
            "candidate_repetition_durations_s": durations,
        }
    )
    if adapted_note:
        result["adapted_note"] = adapted_note
    return result


def kimore_reference_ex5_temporal_analysis(
    angle_stream: Sequence[Union[float, int, None]],
    timestamps: Optional[Sequence[float]] = None,
    fs: float = KIMORE_REFERENCE_FS_HZ,
) -> dict:
    """SOURCE-ALIGNED KIMORE reference path for one knee stream (OFFLINE).

    Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME.

    Requirements (all must hold, else a structured warning is returned and
    filtering/peak detection is NOT run):

    - complete samples: no ``None`` / NaN / +-inf
    - the reference convention sample rate is 30 Hz (``fs`` within a tiny
      float tolerance used only to distinguish 30.0 from representation noise)
    - when timestamps are supplied: finite, strictly increasing, uniform at
      30 Hz.

    The reference filter is called ONLY with its fixed 30 Hz / order-3 / 1 Hz
    parameters; this path never passes an arbitrary FPS to it.
    """
    if any(v is None for v in angle_stream):
        result = _base_result(fs=fs)
        result["classification"] = "REFERENCE_DERIVED"
        result["offline"] = True
        result["warning"] = "missing_samples_require_resampling"
        return result

    if not math.isclose(float(fs), KIMORE_REFERENCE_FS_HZ, rel_tol=0.0, abs_tol=_FS_TOLERANCE_HZ):
        result = _base_result(fs=fs)
        result["classification"] = "REFERENCE_DERIVED"
        result["offline"] = True
        result["warning"] = "reference_requires_30hz_or_resampling"
        return result

    ok, issue = validate_timestamps(timestamps, len(angle_stream), uniform_at=KIMORE_REFERENCE_FS_HZ)
    if timestamps is not None and not ok:
        warning = (
            "reference_requires_uniform_30hz_timestamps_or_resampling"
            if "not uniform" in issue
            else f"invalid_reference_timestamps: {issue}"
        )
        result = _base_result(fs=fs)
        result["classification"] = "REFERENCE_DERIVED"
        result["offline"] = True
        result["warning"] = warning
        return result

    return _run_ex5_pipeline(
        [float(a) for a in angle_stream],
        timestamps,
        fs,
        filter_fn=lambda values: kimore_reference_zero_phase_filter(values),
        classification="REFERENCE_DERIVED",
    )


def kimore_adapted_ex5_temporal_analysis(
    angle_stream: Sequence[Union[float, int, None]],
    timestamps: Optional[Sequence[float]] = None,
    fs: float = KIMORE_REFERENCE_FS_HZ,
) -> dict:
    """ACTUAL-frame-rate ADAPTED analysis path.

    Classification: ENGINEERING_ADAPTED — NOT the exact KIMORE reference
    pipeline. Uses the supplied frame rate with the order-3 / 1 Hz concept via
    the separate adapted zero-phase filter. Complete finite samples are
    required; supplied timestamps must be finite, strictly increasing, and
    uniform at ``fs`` (the Butterworth filter assumes fixed-rate samples).
    """
    if any(v is None for v in angle_stream):
        result = _base_result(fs=fs)
        result["classification"] = "ENGINEERING_ADAPTED"
        result["offline"] = True
        result["warning"] = "missing_samples_require_resampling"
        result["adapted_note"] = ADAPTED_NOTE
        return result

    ok, issue = validate_timestamps(timestamps, len(angle_stream), uniform_at=float(fs))
    if timestamps is not None and not ok:
        result = _base_result(fs=fs)
        result["classification"] = "ENGINEERING_ADAPTED"
        result["offline"] = True
        result["warning"] = (
            "adapted_requires_uniform_sampling_or_resampling"
            if "not uniform" in issue
            else f"invalid_adapted_timestamps: {issue}"
        )
        result["adapted_note"] = ADAPTED_NOTE
        return result

    return _run_ex5_pipeline(
        [float(a) for a in angle_stream],
        timestamps,
        fs,
        filter_fn=lambda values: kimore_adapted_zero_phase_filter(values, fs),
        classification="ENGINEERING_ADAPTED",
        adapted_note=ADAPTED_NOTE,
    )


def side_event_summary(
    left_analysis: Optional[dict],
    right_analysis: Optional[dict],
) -> dict:
    """Per-side event summary; no combined/bilateral repetition count.

    Event candidate counts and peak-to-peak durations are reported per knee
    side under GENERIC names (no "reference" provenance in the summary itself;
    provenance is assigned by the caller's own branch). Bilateral pairing is
    explicitly deferred (`bilateral_pairing_status: "deferred"`).
    """
    def _count(analysis: Optional[dict]) -> int:
        if not analysis:
            return 0
        return len(analysis.get("maxima_indices", []))

    def _durations(analysis: Optional[dict]) -> list[float]:
        if not analysis:
            return []
        return [
            float(d)
            for d in analysis.get("candidate_repetition_durations_s", [])
        ]

    return {
        "left_maxima_count": _count(left_analysis),
        "right_maxima_count": _count(right_analysis),
        "left_candidate_durations_s": _durations(left_analysis),
        "right_candidate_durations_s": _durations(right_analysis),
        "bilateral_pairing_status": "deferred",
    }