"""Temporal filters for BioGait research (M2/M3, Sprint A).

Three filter paths are provided and kept deliberately separate:

- :func:`kimore_reference_zero_phase_filter` — REFERENCE_DERIVED, OFFLINE
  ONLY, NON-CAUSAL (MATLAB ``filtfilt`` equivalent). FIXED KIMORE source
  parameters: order 3, cutoff 1 Hz, reference sample rate 30 Hz. Callers
  cannot redefine those parameters while still calling the result
  "reference". It rejects missing/non-finite (None/NaN/+-inf) input with a
  clear ``ValueError`` — missing values are never silently dropped.
- :func:`kimore_adapted_zero_phase_filter` — ENGINEERING_ADAPTED OFFLINE
  (non-causal) filter using the actual supplied sampling rate with the same
  order-3 / 1 Hz concept. It is NOT the KIMORE reference filter and its
  output must never be presented as REFERENCE_DERIVED.
- :class:`CausalKimoreButterworth` — ENGINEERING_ADAPTED causal counterpart
  for potential live use. It is NOT equivalent to either zero-phase output,
  introduces phase delay, and has not been clinically validated.

The algorithmic conventions and parameters follow the reviewed KIMORE source.
Numerical identity with the original MATLAB runtime has not been established.
Filters here contain no clinical thresholds.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Union

import numpy as np
from scipy import signal

KIMORE_REFERENCE_FS_HZ = 30.0
KIMORE_REFERENCE_CUTOFF_HZ = 1.0
KIMORE_REFERENCE_ORDER = 3

_MIN_FILTER_TAP = 4  # filtfilt requires padding; enforce a practical floor


def _require_finite_sequence(values: Sequence) -> list[float]:
    """Validate and convert an input sequence; rejects None/NaN/+-inf.

    Raises ``ValueError`` for any missing or non-finite sample. Missing values
    are NEVER silently dropped (that would hide temporal gaps).
    """
    out: list[float] = []
    for v in values:
        if v is None:
            raise ValueError("filter input contains None; missing samples "
                             "must not be dropped silently")
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"filter input must be numeric, got {v!r}") from exc
        if not math.isfinite(f):
            raise ValueError("filter input contains NaN or infinity")
        out.append(f)
    return out


def kimore_reference_zero_phase_filter(values: Sequence[Union[float, int]]) -> np.ndarray:
    """KIMORE reference zero-phase low-pass filter (offline only).

    FIXED source parameters (not caller-redefinable):

    - ``[b, a] = butter(order=3, cutoff=1 Hz, fs=30 Hz)``
    - ``filtfilt(b, a, x)``

    Classification: REFERENCE_DERIVED / OFFLINE ONLY / NON-CAUSAL.

    It uses future samples and must not be used as realtime causal filtering.
    Input must be a complete finite sequence (no None/NaN/+-inf); missing
    values raise a clear ``ValueError``. Too-short inputs also raise.
    """
    finite = _require_finite_sequence(values)
    if len(finite) < 2 * max(2 * KIMORE_REFERENCE_ORDER + 1, _MIN_FILTER_TAP):
        raise ValueError(
            "kimore_reference_zero_phase_filter requires a longer signal "
            f"(got {len(finite)} finite samples; the reference path is "
            "30 Hz / order 3)."
        )
    b, a = signal.butter(
        KIMORE_REFERENCE_ORDER,
        KIMORE_REFERENCE_CUTOFF_HZ,
        btype="lowpass",
        fs=KIMORE_REFERENCE_FS_HZ,
        output="ba",
    )
    return signal.filtfilt(b, a, np.asarray(finite, dtype=float))


def kimore_adapted_zero_phase_filter(
    values: Sequence[Union[float, int]],
    fs: float,
) -> np.ndarray:
    """ENGINEERING_ADAPTED offline zero-phase low-pass filter at an actual fs.

    Classification: ENGINEERING_ADAPTED / OFFLINE / NON-CAUSAL.

    Uses the caller-supplied actual sampling rate ``fs`` with the same
    order-3 / 1 Hz concept as the reference. This is NOT the KIMORE
    reference filter: at any ``fs`` other than the 30 Hz reference convention
    the result must not be presented as REFERENCE_DERIVED.

    Input must be a complete finite sequence (no None/NaN/+-inf); missing
    values raise a clear ``ValueError``. Too-short inputs also raise.
    """
    if not fs > 0 or not math.isfinite(fs):
        raise ValueError("fs must be a positive finite number")
    finite = _require_finite_sequence(values)
    if len(finite) < 2 * max(2 * KIMORE_REFERENCE_ORDER + 1, _MIN_FILTER_TAP):
        raise ValueError(
            "kimore_adapted_zero_phase_filter requires a longer signal "
            f"(got {len(finite)} finite samples)."
        )
    if KIMORE_REFERENCE_CUTOFF_HZ >= float(fs) / 2.0:
        raise ValueError("cutoff_hz must be below the Nyquist frequency")
    b, a = signal.butter(
        KIMORE_REFERENCE_ORDER,
        KIMORE_REFERENCE_CUTOFF_HZ,
        btype="lowpass",
        fs=float(fs),
        output="ba",
    )
    return signal.filtfilt(b, a, np.asarray(finite, dtype=float))


class CausalKimoreButterworth:
    """Causal Butterworth low-pass filter for streaming use.

    Classification: ENGINEERING_ADAPTED.

    - Same Butterworth order/cutoff convention as the reference filter.
    - Stateful SOS filtering, one sample at a time (or a batch via
      :meth:`filter_sequence`).
    - Sampling rate must be provided explicitly.
    - NOT equivalent to either zero-phase filter; introduces phase delay.
    - Not clinically validated.

    It is an engineering timing/filtering component only.
    """

    def __init__(
        self,
        fs: float,
        cutoff_hz: float = KIMORE_REFERENCE_CUTOFF_HZ,
        order: int = KIMORE_REFERENCE_ORDER,
    ) -> None:
        if not fs > 0 or not math.isfinite(fs):
            raise ValueError("fs must be a positive finite number")
        self.fs = float(fs)
        self.order = int(order)
        self.cutoff_hz = float(cutoff_hz)
        if self.cutoff_hz >= self.fs / 2.0:
            raise ValueError("cutoff_hz must be below the Nyquist frequency")
        self._sos = signal.butter(
            self.order, self.cutoff_hz, btype="lowpass", fs=self.fs, output="sos"
        )
        self.reset()

    def reset(self) -> None:
        """Reset the filter state (zero initial state)."""
        self._zi = np.zeros((self._sos.shape[0], 2))

    def filter(self, sample: Union[float, int]) -> float:
        """Filter a single sample, advancing the internal state."""
        if sample is None or not math.isfinite(float(sample)):
            raise ValueError("causal filter input must be finite")
        y, self._zi = signal.sosfilt(self._sos, [float(sample)], zi=self._zi)
        return float(y[0])

    def filter_sequence(self, values: Sequence[Union[float, int]]) -> List[float]:
        """Filter a batch of samples, advancing the internal state."""
        finite = _require_finite_sequence(values)
        x = np.asarray(finite, dtype=float)
        y, self._zi = signal.sosfilt(self._sos, x, zi=self._zi)
        return [float(v) for v in y]