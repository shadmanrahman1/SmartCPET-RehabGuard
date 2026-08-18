"""
Tests for CLI loading (analyze_video / benchmark_video) and the deterministic
source-video timeline helper.

These tests verify that the offline CLIs can be imported and their argument
parsers can load WITHOUT a camera, a model download, or a real video, and that
the source-video timeline follows frame_index/fps with strictly increasing
millisecond timestamps. Heavy runtime deps (cv2/mediapipe) are stubbed only
where a module-level import needs them; no inference is executed.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
BIOGAIT = REPO / "biogait"
sys.path.insert(0, str(BIOGAIT))

from runtime_utils import SourceVideoTimeline  # noqa: E402


class _FakeCap:
    def isOpened(self):
        return True

    def get(self, _prop):
        return 30.0

    def read(self):
        return (False, None)

    def release(self):
        pass


def _install_cv2_stub():
    if "cv2" in sys.modules:
        return
    sys.modules["cv2"] = types.SimpleNamespace(
        CAP_PROP_FPS=5,
        VideoCapture=_FakeCap,
        cvtColor=lambda img, code: img,
        COLOR_BGR2RGB=0,
    )


def _install_mp_stub():
    if "mediapipe" in sys.modules:
        return
    sys.modules["mediapipe"] = types.SimpleNamespace()


_install_cv2_stub()
_install_mp_stub()

import analyze_video  # noqa: E402

# benchmark_video lives under experiments/biogait/ and is not on sys.path for
# test discovery; load it by file to exercise its real path-construction and
# sibling imports (it installs repo-level biogait/ on sys.path itself).
import importlib.util  # noqa: E402

_bench_spec = importlib.util.spec_from_file_location(
    "benchmark_video", REPO / "experiments" / "biogait" / "benchmark_video.py"
)
benchmark_video = importlib.util.module_from_spec(_bench_spec)
sys.modules["benchmark_video"] = benchmark_video
assert _bench_spec.loader is not None
_bench_spec.loader.exec_module(benchmark_video)


class SourceVideoTimelineTests(unittest.TestCase):
    """FIX 7/8: deterministic source-video timeline, not wall clock."""

    def test_timestamp_seconds_is_frame_index_over_fps(self):
        tl = SourceVideoTimeline(30.0)
        for i in (0, 1, 2, 10):
            self.assertAlmostEqual(tl.timestamp_seconds(i), i / 30.0)

    def test_video_timestamp_ms_rounded(self):
        tl = SourceVideoTimeline(30.0)
        self.assertEqual(tl.video_timestamp_ms(0), 0)
        self.assertEqual(tl.video_timestamp_ms(1), 33)  # round(1000/30)
        self.assertEqual(tl.video_timestamp_ms(2), 67)

    def test_video_timestamp_ms_strictly_increasing(self):
        tl = SourceVideoTimeline(1e9)
        seen = [tl.video_timestamp_ms(i) for i in range(100)]
        for a, b in zip(seen, seen[1:]):
            self.assertGreater(b, a)

    def test_video_timestamp_ms_wraps_to_next_integer_when_round_ties(self):
        # Even when rounding would re-emit the same ms, the helper guarantees
        # strict numerical increase via max(ts_ms, previous_ms + 1).
        tl = SourceVideoTimeline(2_000.0)  # 0.5 ms steps -> rounds 0,1,1,2...
        seen = [tl.video_timestamp_ms(i) for i in range(5)]
        for a, b in zip(seen, seen[1:]):
            self.assertGreater(b, a)

    def test_new_timeline_restarts_sequence(self):
        tl = SourceVideoTimeline(30.0)
        self.assertEqual(tl.video_timestamp_ms(0), 0)
        tl2 = SourceVideoTimeline(30.0)
        self.assertEqual(tl2.video_timestamp_ms(0), 0)

    def test_rejects_invalid_fps(self):
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                SourceVideoTimeline(bad)


class FpsResolutionTests(unittest.TestCase):
    """FIX 8: valid FPS -> video; else --fps -> override; else stop."""

    def test_uses_valid_video_fps(self):
        self.assertEqual(analyze_video._resolve_fps(30.0, True, None), 30.0)

    def test_uses_override_when_video_fps_invalid(self):
        self.assertEqual(analyze_video._resolve_fps(0.0, False, 25.0), 25.0)

    def test_stops_when_invalid_and_no_override(self):
        with self.assertRaises(ValueError) as ctx:
            analyze_video._resolve_fps(0.0, False, None)
        self.assertIn("--fps", str(ctx.exception))

    def test_never_silently_assumes_30hz(self):
        # 0/NaN video FPS without override must not fall back to 30 silently.
        with self.assertRaises(ValueError):
            analyze_video._resolve_fps(float("nan"), False, None)


class CliLoadTests(unittest.TestCase):
    """FIX 9: offline CLIs load and parse without path/model/video failure."""

    def test_analyze_video_parser_has_expected_arguments(self):
        parser = analyze_video._build_parser()
        names = {a.dest for a in parser._actions}
        self.assertTrue({"input", "output", "fps", "model"}.issubset(names))

    def test_benchmark_video_parser_has_expected_arguments(self):
        parser = benchmark_video._build_parser()
        names = {a.dest for a in parser._actions}
        self.assertTrue({"input", "output", "fps"}.issubset(names))

    def test_analyze_video_help_runs(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                analyze_video.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage: analyze_video", out.getvalue())

    def test_benchmark_video_help_runs(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                benchmark_video.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage: benchmark_video", out.getvalue())

    def test_benchmark_sys_path_points_to_repo_biogait(self):
        biogait = str(REPO / "biogait")
        self.assertIn(biogait, sys.path)
        self.assertTrue(Path(benchmark_video._REPO_BIOGAIT).resolve() == REPO / "biogait")


class AnalyzeVideoLifecycleTests(unittest.TestCase):
    """BLOCKER 1: analyzed Python analyze_video() real-execution lifecycle.

    Mocks cv2 (VideoCapture/isOpened/get/read/release) and the model/landmarker
    construction so the real analyze_video() runs VideoCapture creation ->
    isOpened() -> _read_video_fps() -> FPS resolution without real cv2,
    MediaPipe, a model download, or a video file.
    """

    class _MockCap:
        def __init__(self, fps=30.0, opened=True, end=True):
            self._fps = fps
            self.opened = opened
            self.end = end
            self.release_count = 0

        def isOpened(self):
            return self.opened

        def get(self, prop):
            if prop == 1:  # CAP_PROP_FPS
                return self._fps
            return 0.0

        def read(self):
            if self.end:
                return (False, None)
            return (True, None)

        def release(self):
            self.release_count += 1

    class _MockLandmarker:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _patch_runtime(self, cap):
        fake_cv2 = types.SimpleNamespace(
            CAP_PROP_FPS=1,
            VideoCapture=lambda _path: cap,
            cvtColor=lambda img, code: img,
            COLOR_BGR2RGB=0,
        )
        patchers = [
            mock.patch.object(analyze_video, "cv2", fake_cv2),
            mock.patch.object(analyze_video, "_ensure_model", lambda: "dummy.task"),
            mock.patch.object(
                analyze_video, "_build_landmarker", lambda model: self._MockLandmarker()
            ),
        ]
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])

    def _run(self, cap, **kwargs):
        tmp = tempfile.mkdtemp(prefix="biogait_offline_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        out = Path(tmp) / "session.json"
        result = analyze_video.analyze_video(
            Path("movie.mp4"), out, **kwargs
        )
        return result, out

    def test_valid_capture_no_tuple_unpacking_error(self):
        # Regression: _read_video_fps returns (fps, trusted); analyze_video
        # must unpack exactly 2 values, not 3.
        cap = self._MockCap(fps=30.0)
        self._patch_runtime(cap)
        result, out = self._run(cap)
        self.assertEqual(result["source"]["fps_used_hz"], 30.0)
        self.assertEqual(result["source"]["video_fps_hz"], 30.0)
        self.assertIs(result["source"]["fps_trusted_from_video"], True)
        self.assertEqual(result["source"]["frames_read"], 0)
        self.assertTrue(out.exists())
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"]["source_type"], "local_video")
        self.assertEqual(cap.release_count, 1)

    def test_video_fps_resolved_correctly(self):
        cap = self._MockCap(fps=29.97)
        self._patch_runtime(cap)
        result, _ = self._run(cap)
        self.assertEqual(result["source"]["fps_used_hz"], 29.97)
        self.assertEqual(result["source"]["video_fps_hz"], 29.97)
        self.assertIs(result["source"]["fps_trusted_from_video"], True)

    def test_invalid_fps_uses_override(self):
        cap = self._MockCap(fps=0.0)  # invalid metadata
        self._patch_runtime(cap)
        result, _ = self._run(cap, fps_override=25.0)
        self.assertEqual(result["source"]["fps_used_hz"], 25.0)
        self.assertIsNone(result["source"]["video_fps_hz"])
        self.assertIs(result["source"]["fps_trusted_from_video"], False)
        self.assertEqual(cap.release_count, 1)

    def test_invalid_fps_without_override_raises_and_releases(self):
        cap = self._MockCap(fps=0.0)
        self._patch_runtime(cap)
        with self.assertRaises(ValueError) as ctx:
            self._run(cap)
        self.assertIn("--fps", str(ctx.exception))
        self.assertEqual(cap.release_count, 1)  # capture released on failure

    def test_capture_released_when_not_opened(self):
        cap = self._MockCap(opened=False)
        self._patch_runtime(cap)
        with self.assertRaises(RuntimeError):
            self._run(cap)
        self.assertEqual(cap.release_count, 1)


if __name__ == "__main__":
    unittest.main()