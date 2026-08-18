"""Temporal filters for BioGait research (M2/M3, Sprint A).

Two filter paths are provided and kept deliberately separate:

- :func:`kimore_reference_zero_phase_filter` — REFERENCE_DERIVED, OFFLINE
  ONLY, NON-CAUSAL (MATLAB ``filtfilt`` equivalent). It uses future samples
  and MUST NOT be used as realtime causal filtering.
- :class:`CausalKimoreButterworth` — ENGINEERING_ADAPTED causal counterpart
  for potential live use. It is NOT equivalent to ``filtfilt``, introduces
  phase delay, and has not been clinically validated.

Parameters follow the KIMORE reference source (order 3, 1 Hz cutoff at a 30
Hz reference sample rate). Filters here contain no clinical thresholds.
"""
from __future__ import annotations

from typing import List, Sequence, Union

import numpy as np
from scipy import signal

KIMORE_REFERENCE_FS_HZ = 30.0
KIMORE_REFERENCE_CUTOFF_HZ = 1.0
KIMORE_REFERENCE_ORDER = 3


def kimore_reference_zero_phase_filter(
    values: Sequence[Union[float, int, None]],
    fs: float = KIMORE_REFERENCE_FS_HZ,
    cutoff_hz: float = KIMORE_REFERENCE_CUTOFF_HZ,
    order: int = KIMORE_REFERENCE_ORDER,
) -> np.ndarray:
    """KIMORE reference zero-phase low-pass filter (offline only).

    Uses a Butterworth filter (order 3, 1 Hz cutoff, 30 Hz reference sample
    rate by default) applied with :func:`scipy.signal.sosfiltfilt`, the
    zero-phase equivalent of MATLAB's ``filtfilt`` (sosfiltfilt is the
    documented SOS form of filtfilt).

    Classification: REFERENCE_DERIVED / OFFLINE ONLY / NON-CAUSAL.

    It uses future samples and must not be used as realtime causal
    filtering. ``None``/missing entries are dropped; a ``ValueError`` is
    raised when too few valid samples remain for a stable ``filtfilt`` pass.
    """
    finite = np.asarray(
        [float(v) for v in values if v is not None], dtype=float
    )
    if finite.size < 2 * max(2 * order + 1, 4):
        raise ValueError(
            "kimore_reference_zero_phase_filter requires a longer finite "
            f"signal (got {finite.size} valid samples with order={order})."
        )
    sos = signal.butter(order, cutoff_hz, btype="lowpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, finite)


class CausalKimoreButterworth:
    """Causal Butterworth low-pass filter for streaming use.

    Classification: ENGINEERING_ADAPTED.

    - Same Butterworth order/cutoff convention as the reference filter.
    - Stateful SOS filtering, one sample at a time (or a batch via
      :meth:`filter_sequence`).
    - Sampling rate must be provided explicitly.
    - NOT equivalent to ``filtfilt``; introduces phase delay.
    - Not clinically validated.

    It is an engineering timing/filtering component only.
    """

    def __init__(
        self,
        fs: float,
        cutoff_hz: float = KIMORE_REFERENCE_CUTOFF_HZ,
        order: int = KIMORE_REFERENCE_ORDER,
    ) -> None:
        if fs <= 0:
            raise ValueError("fs must be positive")
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
        y, self._zi = signal.sosfilt(self._sos, [float(sample)], zi=self._zi)
        return float(y[0])

    def filter_sequence(self, values: Sequence[Union[float, int]]) -> List[float]:
        """Filter a batch of samples, advancing the internal state."""
        x = np.asarray([float(v) for v in values])
        y, self._zi = signal.sosfilt(self._sos, x, zi=self._zi)
        return [float(v) for v in y]