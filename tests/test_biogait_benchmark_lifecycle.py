"""
Mocked lifecycle tests for experiments/biogait/benchmark_video.py (B0.2).

Verifies resource ownership without cv2/mediapipe/PyQt5/hardware: the video
capture is released on every failure path, the input/FPS/timeline are validated
before any model download, and a created PoseLandmarker is always closed.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
BIOGAIT = REPO / "biogait"
sys.path.insert(0, str(BIOGAIT))


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def _install_stubs():
    sys.modules.setdefault(
        "cv2",
        types.SimpleNamespace(
            CAP_PROP_FPS=5,
            VideoCapture=object,
            cvtColor=lambda img, code: img,
            COLOR_BGR2RGB=0,
        ),
    )
    mp = _ns(
        Image=lambda *a, **k: object(),
        ImageFormat=_ns(SRGB=0),
    )
    mp.tasks = _ns()
    mp.tasks.python = _ns()
    mp.tasks.python.vision = _ns()
    sys.modules.setdefault("mediapipe", mp)
    sys.modules.setdefault("mediapipe.tasks", mp.tasks)
    sys.modules.setdefault("mediapipe.tasks.python", mp.tasks.python)
    sys.modules.setdefault("mediapipe.tasks.python.vision", mp.tasks.python.vision)


_install_stubs()

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "benchmark_video", REPO / "experiments" / "biogait" / "benchmark_video.py"
)
benchmark_video = importlib.util.module_from_spec(_spec)
sys.modules["benchmark_video"] = benchmark_video
assert _spec.loader is not None
_spec.loader.exec_module(benchmark_video)


class _MockCap:
    def __init__(self, fps=30.0, opened=True, reads=None):
        self._fps = fps
        self.opened = opened
        self._reads = list(reads or [])
        self.release_count = 0

    def isOpened(self):
        return self.opened

    def get(self, prop):
        if prop == 5:  # CAP_PROP_FPS stub value
            return self._fps
        return 0.0

    def read(self):
        if self._reads:
            return self._reads.pop(0)
        return (False, None)

    def release(self):
        self.release_count += 1


class _MockLandmarker:
    enter_count = 0
    exit_count = 0
    close_count = 0

    def __enter__(self):
        type(self).enter_count += 1
        return self

    def __exit__(self, *exc):
        type(self).exit_count += 1
        return False

    def close(self):
        type(self).close_count += 1

    def detect_for_video(self, img, ts_ms):
        return _ns(pose_landmarks=[], pose_world_landmarks=[])


class _Result:
    def __init__(self):
        self.pose_landmarks = None
        self.pose_world_landmarks = None


class BenchmarkLifecycleTests(unittest.TestCase):
    def _patch_runtime(self, cap, landmarker=None, build_error=None):
        fake_cv2 = types.SimpleNamespace(
            CAP_PROP_FPS=5,
            VideoCapture=lambda _p: cap,
            cvtColor=lambda img, code: img,
            COLOR_BGR2RGB=0,
        )
        _MockLandmarker.enter_count = 0
        _MockLandmarker.exit_count = 0
        _MockLandmarker.close_count = 0

        def _build(model):
            if build_error is not None:
                raise build_error
            return landmarker

        patchers = [
            mock.patch.object(benchmark_video, "cv2", fake_cv2),
            mock.patch.object(benchmark_video, "_build_landmarker", _build),
        ]
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])

    def _no_download(self):
        # Replacing _ensure_model with an AssertionError proves it is not called.
        return mock.patch.object(benchmark_video, "_ensure_model",
                                 side_effect=AssertionError("model downloaded"))

    def test_open_failure_releases_and_does_not_download_model(self):
        cap = _MockCap(opened=False)
        self._patch_runtime(cap)
        with self._no_download() as ensure:
            with self.assertRaises(RuntimeError):
                benchmark_video.benchmark(Path("x.mp4"), None, None)
            self.assertEqual(cap.release_count, 1)
            ensure.assert_not_called()

    def test_invalid_fps_releases_and_does_not_download_model(self):
        for bad in (0.0, float("nan"), float("inf"), float("-inf"), -1.0):
            cap = _MockCap(fps=bad)
            self._patch_runtime(cap)
            with self._no_download() as ensure:
                with self.assertRaises(ValueError):
                    benchmark_video.benchmark(Path("x.mp4"), None, None)
                self.assertEqual(cap.release_count, 1)
                ensure.assert_not_called()

    def test_fps_override_resolves_invalid_metadata_then_runs(self):
        lm = _MockLandmarker()
        cap = _MockCap(fps=0.0, reads=[(True, object()), (False, None)])
        self._patch_runtime(cap, landmarker=lm)
        with mock.patch.object(benchmark_video, "_ensure_model", lambda: "dummy.task"):
            result = benchmark_video.benchmark(Path("x.mp4"), None, 25.0)
        self.assertEqual(result["fps_used_hz"], 25.0)
        self.assertFalse(result["fps_trusted_from_video"])
        self.assertEqual(cap.release_count, 1)
        self.assertEqual(_MockLandmarker.close_count, 1)
        self.assertEqual(_MockLandmarker.enter_count, _MockLandmarker.exit_count)

    def test_invalid_fps_no_override_requiring_override(self):
        cap = _MockCap(fps=0.0)
        self._patch_runtime(cap)
        with self._no_download() as ensure:
            with self.assertRaises(ValueError) as ctx:
                benchmark_video.benchmark(Path("x.mp4"), None, None)
            self.assertIn("--fps", str(ctx.exception))
            self.assertEqual(cap.release_count, 1)
            ensure.assert_not_called()

    def test_landmarker_build_failure_still_releases_capture(self):
        cap = _MockCap(fps=30.0)
        err = RuntimeError("landmarker failed")
        # Ensure_model IS reached (FPS valid) before the build fails.
        self._patch_runtime(cap, build_error=err)
        with mock.patch.object(benchmark_video, "_ensure_model", lambda: "dummy.task"):
            with self.assertRaises(RuntimeError):
                benchmark_video.benchmark(Path("x.mp4"), None, None)
        self.assertEqual(cap.release_count, 1)

    def test_success_releases_capture_and_closes_landmarker(self):
        lm = _MockLandmarker()
        cap = _MockCap(fps=30.0, reads=[(True, object()), (False, None)])
        self._patch_runtime(cap, landmarker=lm)
        with mock.patch.object(benchmark_video, "_ensure_model", lambda: "dummy.task"):
            result = benchmark_video.benchmark(Path("x.mp4"), None, None)
        self.assertEqual(result["fps_used_hz"], 30.0)
        self.assertTrue(result["fps_trusted_from_video"])
        self.assertEqual(cap.release_count, 1)
        self.assertEqual(_MockLandmarker.close_count, 1)
        self.assertEqual(_MockLandmarker.enter_count, _MockLandmarker.exit_count)

    def test_timeline_rejects_invalid_fps_from_override(self):
        cap = _MockCap(fps=0.0, opened=True)
        self._patch_runtime(cap)
        with self._no_download() as ensure:
            with self.assertRaises(ValueError):
                benchmark_video.benchmark(Path("x.mp4"), None, float("nan"))
            self.assertEqual(cap.release_count, 1)
            ensure.assert_not_called()


if __name__ == "__main__":
    unittest.main()