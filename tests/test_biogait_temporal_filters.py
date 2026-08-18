"""
Tests for biogait/temporal_filters.py — KIMORE reference filter, adapted
zero-phase filter, and causal Butterworth adaptation.

Synthetic deterministic data only. No camera/GUI/network. These tests verify
filter mechanics and provenance boundaries, not clinical validity.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from temporal_filters import (  # noqa: E402
    CausalKimoreButterworth,
    kimore_adapted_zero_phase_filter,
    kimore_reference_zero_phase_filter,
)


FS = 30.0


def _slow_sine_with_noise(periods=3, n_cycles=6, noise_amp=3.0, base=170.0, amp=40.0):
    """A low-frequency sine (0.5 Hz at 30 Hz) with added high-freq noise."""
    n = int(FS / 0.5) * periods
    t = [i / FS for i in range(n)]
    signal = [base + amp * math.sin(2 * math.pi * 0.5 * tt) for tt in t]
    noise = [noise_amp * math.sin(97.0 * i) for i in range(n)]
    return signal, [s + nse for s, nse in zip(signal, noise)]


class ReferenceFilterTests(unittest.TestCase):
    def test_length_preserved_and_finite(self):
        clean, noisy = _slow_sine_with_noise()
        out = kimore_reference_zero_phase_filter(noisy)
        self.assertEqual(len(out), len(noisy))
        self.assertTrue(all(math.isfinite(v) for v in out))

    def test_noise_is_attenuated(self):
        clean, noisy = _slow_sine_with_noise()
        out = kimore_reference_zero_phase_filter(noisy)
        self.assertLess(_stdev(list(out)), _stdev(noisy))

    def test_fixed_30hz_parameters_not_redefinable(self):
        # Reference filter must NOT accept fs/cutoff/order caller overrides.
        for kwargs in ({"fs": 25.0}, {"cutoff_hz": 0.5}, {"order": 5}):
            with self.assertRaises(TypeError):
                kimore_reference_zero_phase_filter([1.0] * 100, **kwargs)

    def test_rejects_none_not_silently_dropped(self):
        clean, noisy = _slow_sine_with_noise()
        padded = noisy[:50] + [None] * 5 + noisy[50:]
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter(padded)

    def test_rejects_nan_and_inf(self):
        clean, noisy = _slow_sine_with_noise()
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter(noisy[:100] + [float("nan")])
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter(noisy[:100] + [float("inf")])
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter(noisy[:100] + [float("-inf")])

    def test_raises_on_short_signal(self):
        with self.assertRaises(ValueError):
            kimore_reference_zero_phase_filter([1.0] * 5)


class AdaptedFilterTests(unittest.TestCase):
    def test_separate_adapted_filter_exists_and_is_clearly_different(self):
        self.assertTrue(callable(kimore_adapted_zero_phase_filter))
        self.assertIsNot(kimore_adapted_zero_phase_filter,
                         kimore_reference_zero_phase_filter)

    def test_runs_at_actual_fs(self):
        clean, noisy = _slow_sine_with_noise()
        out = kimore_adapted_zero_phase_filter(noisy, fs=25.0)
        self.assertEqual(len(out), len(noisy))
        self.assertTrue(all(math.isfinite(v) for v in out))

    def test_rejects_invalid_fs(self):
        for bad in (0.0, -1.0, float("nan")):
            with self.assertRaises(ValueError):
                kimore_adapted_zero_phase_filter([1.0] * 200, fs=bad)

    def test_rejects_none_and_non_finite(self):
        clean, noisy = _slow_sine_with_noise()
        with self.assertRaises(ValueError):
            kimore_adapted_zero_phase_filter(noisy[:50] + [None], fs=25.0)
        with self.assertRaises(ValueError):
            kimore_adapted_zero_phase_filter(noisy[:50] + [float("nan")], fs=25.0)

    def test_cutoff_below_nyquist_enforced(self):
        with self.assertRaises(ValueError):
            kimore_adapted_zero_phase_filter([1.0] * 200, fs=1.0)


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

    def test_reset_clears_state(self):
        filt = CausalKimoreButterworth(fs=FS)
        for _ in range(200):
            filt.filter(100.0)
        settled = filt.filter(100.0)
        filt.reset()
        self.assertLess(abs(filt.filter(20.0)), abs(settled))

    def test_rejects_non_finite_input(self):
        filt = CausalKimoreButterworth(fs=FS)
        with self.assertRaises(ValueError):
            filt.filter(float("nan"))
        with self.assertRaises(ValueError):
            filt.filter_sequence([1.0, None])

    def test_causal_not_zero_phase_equivalent(self):
        clean, noisy = _slow_sine_with_noise()
        ref = list(kimore_reference_zero_phase_filter(noisy[:300]))
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