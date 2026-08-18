"""KIMORE reference temporal analysis for Exercise 5 (squat) — OFFLINE ONLY.

Two deliberately separate paths:

- :func:`kimore_reference_ex5_temporal_analysis` — EXACT reference path.
  Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME. Reproduces the
  reviewed KIMORE wrapper source conventions
  (``matlab/matlab_original/feat_extract_Ex5.m`` and ``filtering.m``):

  1. KIMORE source retains samples ``10:end`` in MATLAB (1-based) indexing,
     equivalent to discarding the first 9 samples in zero-based Python —
     i.e. ``values[9:]``;
  2. reference sign-flip handling (negate a sample when the consecutive
     difference exceeds 100 degrees — NOT a +/-360 unwrap);
  3. KIMORE reference zero-phase filter (order 3, 1 Hz, 30 Hz; ba-form
     Butterworth + ``filtfilt``);
  4. maxima detection at ``max(signal)/sqrt(2)``;
  5. minima detection on ``max(signal) - signal`` at its ``max/sqrt(2)``
     threshold;
  6. reference minimum peak distance ``floor(n_samples / 10)``.

  The exact path requires a uniform, complete sample stream at the 30 Hz
  reference convention. Missing samples or a non-30 Hz rate return a
  structured warning and filtering/peak detection is NOT run (no silent
  resampling is introduced in this sprint).

- :func:`kimore_adapted_ex5_temporal_analysis` — actual-frame-rate path.
  Classification: ENGINEERING_ADAPTED. Uses the supplied frame rate while
  retaining the 1 Hz / order-3 filter concept. It is NOT the exact KIMORE
  reference pipeline and its results are not REFERENCE_DERIVED.

Detected candidates are NOT clinically valid repetitions. This module does
NOT produce pass/fail or any clinical decision. The KIMORE acquisition
protocol involved repeated exercise execution; its full-sequence peak
settings are not automatically valid for an arbitrary live session length.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Union

import numpy as np
from scipy import signal as sp_signal

from temporal_filters import kimore_reference_zero_phase_filter

# MATLAB indexing is 1-based: the reviewed source keeps ``angle = angle(10:end)``,
# i.e. it discards samples 1..9 and retains samples 10..end. The zero-based
# Python equivalent is ``values[9:]`` (NOT ``values[10:]``).
KIMORE_FIRST_RETAINED_MATLAB_SAMPLE = 10
KIMORE_INITIAL_DISCARDED_SAMPLES = 9
KIMORE_WRAP_DIFF_THRESHOLD_DEG = 100.0
KIMORE_PEAK_HEIGHT_FACTOR = 1.0 / math.sqrt(2.0)
KIMORE_REFERENCE_FS_HZ = 30.0


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
    angle_stream: Sequence[float],
    timestamps: Optional[Sequence[float]],
    fs: float,
) -> dict:
    """Shared offline Ex5 pipeline mechanics (trim, sign-flip, filter, extrema)."""
    angles = [float(a) for a in angle_stream]
    if len(angles) <= KIMORE_INITIAL_DISCARDED_SAMPLES:
        result = _base_result(fs=fs)
        result["warning"] = "insufficient_samples_after_trimming"
        return result

    trimmed = remove_initial_samples(angles)
    corrected, n_corrections = kimore_reference_sign_flip_correction(trimmed)

    try:
        filtered = kimore_reference_zero_phase_filter(corrected, fs=fs)
    except ValueError as exc:
        result = _base_result(fs=fs)
        result["trimmed_length"] = len(corrected)
        result["warning"] = f"insufficient_samples_for_reference_filter: {exc}"
        return result

    if len(filtered) < 3:
        result = _base_result(fs=fs)
        result["trimmed_length"] = len(corrected)
        result["filtered_signal"] = [float(v) for v in filtered]
        result["warning"] = "insufficient_filtered_samples"
        return result

    distance = _min_peak_distance(len(filtered))
    max_idx, max_vals = detect_maxima(filtered, distance)
    min_idx, min_vals = detect_minima(filtered, distance)

    def _time_of(stream_index: int) -> float:
        original_index = stream_index + KIMORE_INITIAL_DISCARDED_SAMPLES
        if timestamps is not None and original_index < len(timestamps):
            return float(timestamps[original_index])
        return stream_index / fs

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
    return result


def kimore_reference_ex5_temporal_analysis(
    angle_stream: Sequence[Union[float, int, None]],
    timestamps: Optional[Sequence[float]] = None,
    fs: float = KIMORE_REFERENCE_FS_HZ,
) -> dict:
    """EXACT KIMORE reference path for one knee stream (OFFLINE, not realtime).

    Only runs when the stream is complete (no ``None`` samples) and the
    sample rate is the 30 Hz reference convention. Otherwise returns a
    structured warning and does NOT run filtering/peak detection:

    - ``missing_samples_require_resampling`` — a ``None`` sample is present.
    - ``reference_requires_30hz_or_resampling`` — ``fs`` is not 30 Hz
      (within a tiny floating-point tolerance used only to distinguish
      30.0 from representation noise).

    Classification: REFERENCE_DERIVED.
    """
    if any(v is None for v in angle_stream):
        result = _base_result(fs=fs)
        result["classification"] = "REFERENCE_DERIVED"
        result["offline"] = True
        result["warning"] = "missing_samples_require_resampling"
        return result

    if not math.isclose(float(fs), KIMORE_REFERENCE_FS_HZ, rel_tol=0.0, abs_tol=1e-6):
        result = _base_result(fs=fs)
        result["classification"] = "REFERENCE_DERIVED"
        result["offline"] = True
        result["warning"] = "reference_requires_30hz_or_resampling"
        return result

    result = _run_ex5_pipeline(angle_stream, timestamps, fs)
    result["classification"] = "REFERENCE_DERIVED"
    result["offline"] = True
    return result


def kimore_adapted_ex5_temporal_analysis(
    angle_stream: Sequence[Union[float, int, None]],
    timestamps: Optional[Sequence[float]] = None,
    fs: float = 30.0,
) -> dict:
    """ACTUAL-frame-rate ADAPTED analysis path.

    Classification: ENGINEERING_ADAPTED — NOT the exact KIMORE reference
    pipeline. Uses the supplied frame rate while retaining the 1 Hz,
    order-3 filter concept. Missing samples return
    ``missing_samples_require_resampling`` and no filtering is applied.
    """
    if any(v is None for v in angle_stream):
        result = _base_result(fs=fs)
        result["classification"] = "ENGINEERING_ADAPTED"
        result["offline"] = True
        result["warning"] = "missing_samples_require_resampling"
        return result

    result = _run_ex5_pipeline(angle_stream, timestamps, fs)
    result["classification"] = "ENGINEERING_ADAPTED"
    result["offline"] = True
    result["adapted_note"] = (
        "Uses the actual supplied frame rate; not the exact 30 Hz KIMORE "
        "reference pipeline. Results are engineering-adapted, not "
        "REFERENCE_DERIVED."
    )
    return result


def side_event_summary(
    left_analysis: Optional[dict],
    right_analysis: Optional[dict],
) -> dict:
    """Per-side reference event summary; no combined/bilateral repetition count.

    Repetition-event candidate counts and peak-to-peak durations are reported
    per knee side. Bilateral pairing is explicitly deferred (no temporal
    pairing tolerance is invented in this sprint); `bilateral_pairing_status`
    is always ``"deferred"``.
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
        "left_reference_maxima_count": _count(left_analysis),
        "right_reference_maxima_count": _count(right_analysis),
        "left_candidate_repetition_durations_s": _durations(left_analysis),
        "right_candidate_repetition_durations_s": _durations(right_analysis),
        "bilateral_pairing_status": "deferred",
    }