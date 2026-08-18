"""KIMORE reference temporal analysis for Exercise 5 (squat) — OFFLINE ONLY.

Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME.

This implements a research/comparison reference path that reproduces the
behaviour of the reviewed KIMORE wrapper source
(``matlab/matlab_original/feat_extract_Ex5.m`` and ``filtering.m``):

1. remove the initial 10 samples from the knee-angle stream;
2. reference singularity handling (sign correction when the consecutive
   knee-angle difference exceeds 100 degrees);
3. KIMORE zero-phase reference filter (order 3, 1 Hz, 30 Hz);
4. maxima detection at ``max(signal)/sqrt(2)``;
5. minima detection on ``max(signal) - signal`` at its
   ``max/ sqrt(2)`` threshold;
6. reference minimum peak distance ``floor(n_samples / 10)``.

Detected candidates are NOT clinically valid repetitions. This path does NOT
produce pass/fail or any clinical decision.

The original KIMORE acquisition protocol involved repeated exercise
execution; its full-sequence peak settings are not automatically valid for
an arbitrary live session length. That limitation is documented in the deep
status output too.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Union

import numpy as np
from scipy import signal as sp_signal

from temporal_filters import kimore_reference_zero_phase_filter

KIMORE_INITIAL_TRIM_SAMPLES = 10
KIMORE_WRAP_DIFF_THRESHOLD_DEG = 100.0
KIMORE_PEAK_HEIGHT_FACTOR = 1.0 / math.sqrt(2.0)


def remove_initial_samples(
    values: Sequence[float], n: int = KIMORE_INITIAL_TRIM_SAMPLES
) -> list[float]:
    """Remove the first ``n`` samples (reference acquisition warm-up trim)."""
    if n < 0:
        return list(values)
    return list(values[n:]) if n < len(values) else []


def kimore_wrap_correction(
    angles: Sequence[float],
    threshold_deg: float = KIMORE_WRAP_DIFF_THRESHOLD_DEG,
) -> tuple[list[float], int]:
    """Reference singularity/sign handling for wrapped knee-angle samples.

    For each consecutive pair, when ``abs(current - previous_corrected)``
    exceeds the threshold (100 degrees by default), the current sample is
    shifted by the appropriate multiple of 360 degrees (sign correction
    represented by the reference source) so discontinuities are unwrapped.

    Returns ``(corrected, n_corrections)``.
    """
    corrected: list[float] = []
    corrections = 0
    for sample in angles:
        if not corrected:
            corrected.append(float(sample))
            continue
        prev = corrected[-1]
        d = float(sample) - prev
        if abs(d) > threshold_deg:
            sample = float(sample) - 360.0 * (1.0 if d > 0 else -1.0)
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


def kimore_reference_ex5_temporal_analysis(
    angle_stream: Sequence[Union[float, int]],
    timestamps: Optional[Sequence[float]] = None,
    fs: float = 30.0,
) -> dict:
    """Run the offline KIMORE reference temporal analysis on one knee stream.

    ``angle_stream`` must be a finite, valid (non-missing) sequence of knee
    sagittal angles. ``timestamps`` (optional) must be the aligned
    per-sample timestamps; when omitted, time is derived from ``fs``.

    Returns a dict with the filtered signal, maxima/minima indices and
    values, reference repetition-event candidates, and candidate
    peak-to-peak repetition durations (seconds). Candidates are reference
    events — not clinically validated repetitions and not pass/fail.
    """
    angles = [float(a) for a in angle_stream]
    if len(angles) <= KIMORE_INITIAL_TRIM_SAMPLES:
        return {
            "classification": "REFERENCE_DERIVED",
            "offline": True,
            "warning": "insufficient_samples_after_trimming",
            "fs_hz": fs,
            "n_initial_samples_removed": KIMORE_INITIAL_TRIM_SAMPLES,
            "trimmed_length": 0,
            "filtered_signal": [],
            "maxima_indices": [],
            "maxima_values": [],
            "minima_indices": [],
            "minima_values": [],
            "event_candidates": [],
            "candidate_repetition_durations_s": [],
        }

    trimmed = remove_initial_samples(angles)
    corrected, n_corrections = kimore_wrap_correction(trimmed)

    try:
        filtered = kimore_reference_zero_phase_filter(corrected, fs=fs)
    except ValueError as exc:
        return {
            "classification": "REFERENCE_DERIVED",
            "offline": True,
            "warning": f"insufficient_samples_for_reference_filter: {exc}",
            "fs_hz": fs,
            "n_initial_samples_removed": KIMORE_INITIAL_TRIM_SAMPLES,
            "trimmed_length": len(corrected),
            "filtered_signal": [],
            "maxima_indices": [],
            "maxima_values": [],
            "minima_indices": [],
            "minima_values": [],
            "event_candidates": [],
            "candidate_repetition_durations_s": [],
        }

    n_filtered = len(filtered)
    if n_filtered < 3:
        return {
            "classification": "REFERENCE_DERIVED",
            "offline": True,
            "warning": "insufficient_filtered_samples",
            "fs_hz": fs,
            "n_initial_samples_removed": KIMORE_INITIAL_TRIM_SAMPLES,
            "trimmed_length": len(corrected),
            "filtered_signal": [float(v) for v in filtered],
            "maxima_indices": [],
            "maxima_values": [],
            "minima_indices": [],
            "minima_values": [],
            "event_candidates": [],
            "candidate_repetition_durations_s": [],
        }

    distance = _min_peak_distance(n_filtered)
    max_idx, max_vals = detect_maxima(filtered, distance)
    min_idx, min_vals = detect_minima(filtered, distance)

    def _time_of(stream_index: int) -> float:
        original_index = stream_index + KIMORE_INITIAL_TRIM_SAMPLES
        if timestamps is not None and original_index < len(timestamps):
            return float(timestamps[original_index])
        return stream_index / fs

    events = [
        {"index": int(i), "original_index": int(i + KIMORE_INITIAL_TRIM_SAMPLES),
         "time_s": _time_of(i), "type": "max"}
        for i in max_idx
    ] + [
        {"index": int(i), "original_index": int(i + KIMORE_INITIAL_TRIM_SAMPLES),
         "time_s": _time_of(i), "type": "min"}
        for i in min_idx
    ]
    events.sort(key=lambda e: e["index"])

    # Candidate repetition durations from consecutive maxima (peak-to-peak).
    durations: list[float] = []
    for i in range(1, len(max_idx)):
        durations.append(_time_of(max_idx[i]) - _time_of(max_idx[i - 1]))
    durations = [d for d in durations if d > 0]

    return {
        "classification": "REFERENCE_DERIVED",
        "offline": True,
        "warning": None,
        "fs_hz": fs,
        "n_initial_samples_removed": KIMORE_INITIAL_TRIM_SAMPLES,
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


def merge_side_events(
    left_analysis: Optional[dict],
    right_analysis: Optional[dict],
) -> dict:
    """Merge per-side maxima candidates into a single event summary.

    Engineering-pragmatic, documented choice: the squat is a bilateral
    exercise, so maxima event candidates from either knee are merged and
    counted once via a time-sorted union. Does NOT claim clinical validity.
    """
    left_events = (
        left_analysis.get("event_candidates", []) if left_analysis else []
    )
    right_events = (
        right_analysis.get("event_candidates", []) if right_analysis else []
    )
    left_max = [e for e in left_events if e["type"] == "max"]
    right_max = [e for e in right_events if e["type"] == "max"]

    union = sorted(left_max + right_max, key=lambda e: (e["time_s"], e["index"]))
    durations: list[float] = []
    for i in range(1, len(union)):
        durations.append(union[i]["time_s"] - union[i - 1]["time_s"])
    durations = [d for d in durations if d > 0]

    return {
        "n_left_maxima": len(left_max),
        "n_right_maxima": len(right_max),
        "n_reference_event_candidates": len(union),
        "candidate_repetition_durations_s": durations,
    }