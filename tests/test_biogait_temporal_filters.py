"""
Tests for biogait/temporal_filters.py — KIMORE reference filter and causal
Butterworth adaptation.

Synthetic deterministic data only. No camera/GUI/network. These tests verify
filter mechanics, not clinical validity.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from temporal_filters import (  # noqa: E402
    CausalKimoreButterworth,
    kimore_reference_zero_phase_filter,
)


FS = 30.0


def _slow_sine_with_noise(periods=3, n_cycles=6, noise_amp=3.0, base=170.0, amp=40.0):
    """A low-frequency sine (0.5 Hz at 30 Hz) with added high-freq noise."""
    n = int(FS / 0.5) * periods
    t = [i / FS for i in range(n)]
    signal = [base + amp * math.sin(2 * math.pi * 0.5 * tt) for tt in t]
    # deterministic pseudo-random-ish noise via sin of index
    noise = [noise_amp * math.sin(97.0 * i) for i in range(n)]
    return signal, [s + nse for s, nse in zip(signal, noise)]


class ReferenceFilterTests(unittest.TestCase):
    def test_length_preserved_and_finite(self):
        clean, noisy = _slow_sine_with_noise()
        out = kimore_reference_zero_phase_filter(noisy, fs=FS)
        self.assertEqual(len(out), len(noisy))
        self.assertTrue(all(math.isfinite(v) for v in out))

    def test_noise_is_attenuated(self):
        clean, noisy = _slow_sine_with_noise()
        out = kimore_reference_zero_phase_filter(noisy, fs=FS)
        clean_std = _stdev(clean)
        self.assertLess(_stdev(list(out)), _stdev(noisy))
        # stays close to the clean zero-mean-ish signal
        self.assertLess(_stdev(list(out)), clean_std * 1.5)

    def test_missing_samples_are_dropped(self):
        clean, noisy = _slow_sine_with_noise()
        padded = noisy[:150] + [None] * 5 + noisy[150:]
        self.assertEqual(len(padded), len(noisy) + 5)
        out = kimore_reference_zero_phase_filter(padded, fs=FS)
        self.assertEqual(len(out), len(noisy))

    def test_raises_on_short_signal(self):
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter([1.0] * 5, fs=FS)

    def test_rejects_not_finite_after_filtering(self):
        _, noisy = _slow_sine_with_noise()
        out = kimore_reference_zero_phase_filter(noisy, fs=FS)
        self.assertTrue(all(math.isfinite(float(v)) for v in out))


class CausalFilterTests(unittest.TestCase):
    def test_validates_fs(self):
        with self.assertRaises(ValueError):
            CausalKimoreButterworth(fs=0)

    def test_validates_cutoff_below_nyquist(self):
        with self.assertRaises(ValueError):
            CausalKimoreButterworth(fs=30.0, cutoff_hz=15.0)

    def test_sequence_length_preserved(self):
        filt = CausalKimoreButterworth(fs=FS)
        values = [170.0 + 10.0 * math.sin(i / 10.0) for i in range(120)]
        out = filt.filter_sequence(values)
        self.assertEqual(len(out), len(values))
        self.assertTrue(all(math.isfinite(v) for v in out))

    def test_converges_on_constant_input(self):
        filt = CausalKimoreButterworth(fs=FS)
        for _ in range(300):
            filt.filter(10.0)
        self.assertAlmostEqual(filt.filter(10.0), 10.0, delta=0.1)

    def test_state_advances_between_single_samples(self):
        filt = CausalKimoreButterworth(fs=FS)
        first = filt.filter(10.0)
        # A step input: first output should be near zero (state starting cold),
        # later outputs should move toward the input value.
        self.assertLess(abs(first - 10.0), 10.0)
        vals = [filt.filter(10.0) for _ in range(200)]
        self.assertLess(abs(vals[-1] - 10.0), 0.5)
        self.assertNotEqual(first, vals[-1])

    def test_reset_clears_state(self):
        filt = CausalKimoreButterworth(fs=FS)
        for _ in range(200):
            filt.filter(100.0)
        settled = filt.filter(100.0)
        filt.reset()
        # After reset, state is cold again (output stays near 0 for a step).
        self.assertLess(abs(filt.filter(20.0)), abs(settled))

    def test_causal_not_zero_phase_equivalent(self):
        # Causal output on a low-frequency sine is phase-delayed relative to
        # the zero-phase reference filter; verify we do not claim equality.
        clean, noisy = _slow_sine_with_noise()
        ref = list(kimore_reference_zero_phase_filter(noisy[:300], fs=FS))
        causal = CausalKimoreButterworth(fs=FS).filter_sequence(noisy[:300])
        self.assertNotAlmostEqual(causal[150], ref[150], places=6)


def _stdev(values):
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


if __name__ == "__main__":
    unittest.main()