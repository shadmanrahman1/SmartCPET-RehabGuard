# BioGait M1 — Runtime Stabilization

**Milestone:** M1 (Engineering / Runtime)
**Module:** Module 2 / BioGait only

---

> M1 introduces no new rehabilitation assessment method and does not
> change the legacy BioGait scientific scoring logic.

This milestone is **engineering-only**. It improves runtime reliability,
resource cleanup, timing correctness, and testability of the primary BioGait
application. No scientific equation, risk weight, or clinical threshold was
changed.

---

## Primary Runtime Architecture

The primary BioGait runtime is unchanged in M1:

```
app_qt.py
    ↓
CameraWorker (biogait/ui_worker.py)  — runs in a QThread
    ↓
MediaPipe Tasks PoseLandmarker (VIDEO mode)
    ↓
biogait/metrics.py  — pose metrics + legacy risk scoring (unchanged)
    ↓
PyQt5 UI (ui_widgets.py + app_qt.py dashboard)
```

The legacy `app.py` / Streamlit path is **not** merged into this runtime.

---

## Engineering Problems Addressed

1. **Wall-clock timing** — MediaPipe VIDEO timestamps and metric-emission
   timing previously used `time.time()`, which is not monotonic and can jump
   (NTP sync, manual clock changes), producing timestamps that decrease over
   time.
2. **No-signal tight loop** — repeated failed frame reads caused an unbounded
   `time.sleep(0.05)` loop that never attempted to recover the camera.
3. **Camera open robustness** — no Windows-friendly backend preference
   (`CAP_DSHOW`) and no fallback path.
4. **Resource cleanup gap** — `cv2.VideoCapture` release and landmarker close
   were not guaranteed if an exception occurred inside the frame loop.
5. **QImage buffer lifetime** — the emitted `QImage` could reference a
   temporary Python bytes/frame buffer.
6. **Status flooding** — the UI received an identical status string every
   frame instead of only on meaningful changes.
7. **Prompt shutdown** — `stop()` could not interrupt long sleep delays.

---

## Monotonic Timing

New helper: `MonotonicClock` in `biogait/runtime_utils.py`.

- Based on `time.perf_counter()` — never depends on wall-clock adjustments.
- `elapsed_seconds()` — monotonic session elapsed time.
- `video_timestamp_ms()` — strictly increasing milliseconds for
  `detect_for_video` (each call is at least `previous + 1`).

Metrics emission throttling now uses the same monotonic clock. The human-
readable `timestamp` string written into metrics records is still produced by
`metrics.add_session_fields()` and is unchanged.

---

## Reconnect Behavior

New helper: `ReconnectPolicy` in `biogait/runtime_utils.py`.

Bounded, conservative recovery on repeated frame-read failure:

```
TRACKING
   ↓ read failure
NO_SIGNAL
   ↓ repeated failure (threshold reached)
RECONNECTING
   ↓ release capture
reopen capture
   ↓ success
CONNECTING → next frame read decides
```

- Consecutive read failures count toward a threshold
  (`READ_FAILURE_RECONNECT_THRESHOLD`).
- When the threshold is reached, bounded exponential backoff delays apply
  (`RECONNECT_BASE_DELAY_SECONDS` → `RECONNECT_MAX_DELAY_SECONDS`,
  capped at `RECONNECT_MAX_ATTEMPTS`).
- When attempts are exhausted for a stretch, the worker pauses
  (`RECONNECT_PAUSE_RESET_SECONDS`) then resets — no infinite tight loop.
- A successful reopen only means frames *may* become available: the worker
  does **not** report `TRACKING` from camera-open success alone. The next
  frame read decides `TRACKING` / `NO_POSE` / `NO_SIGNAL`.
- All waiting uses `interruptible_sleep()`, which checks the stop flag in
  small chunks so the application can close promptly.

### Capture ownership

`run()` opens the initial capture and transfers ownership to
`_stream_loop()`, which holds the *current* capture reference and releases
whichever capture is active when the stream exits.

**The currently active VideoCapture instance, including a replacement
created during reconnect, is released on worker exit.** When a reconnect
replaces the capture, the old instance is released at that moment and the
replacement becomes the new current capture; there is no double ownership.

The reconnect decision is delegated to a pure helper
(`reconnect_capture()` in `runtime_utils.py`) so the ownership/release
semantics are directly unit-testable without hardware or GUI.

All values live in `biogait/config.py` under the explicit banner:

> `ENGINEERING RUNTIME SETTINGS — NOT CLINICAL THRESHOLDS`

---

## Camera Opening

New helper: `open_camera()` in `biogait/runtime_utils.py`.

- Integer webcam index on **Windows**: attempts `CAP_DSHOW` first, falls back
  to the default backend if that fails.
- Integer webcam index on **non-Windows** systems: uses the default backend
  directly (no DSHOW attempt).
- URL / IP source: uses the default `cv2.VideoCapture(source)`.
- Returns `None` instead of an opened capture when all attempts fail.

---

## Runtime Statuses

The worker exposes only engineering statuses (no medical meaning):

| Status | Meaning |
|--------|---------|
| `CONNECTING` | Starting up / attempting camera or model init |
| `TRACKING` | Frames are flowing and pose is detected |
| `NO_POSE` | Frames flowing, no pose currently detected |
| `NO_SIGNAL` | Camera frames not flowing |
| `RECONNECTING` | Attempting to recover a lost camera |
| `ERROR` | Model or camera initialization failed |
| `STOPPED` | Worker shutdown complete |

A `StatusGuard` helper ensures status is emitted only when it changes, so the
UI is not flooded with an identical status every frame.

---

## Safe Shutdown / Resource Cleanup

- `run()` opens the initial capture and transfers ownership to
  `_stream_loop()`. The frame loop runs inside `try/finally`, so
  `cv2.VideoCapture.release()` always runs on normal exit or exception.
- **The currently active VideoCapture instance, including a replacement
  created during reconnect, is released on worker exit.** When a reconnect
  replaces the capture, the old instance is released at that moment; the
  replacement becomes current and is released when the stream/shutdown exits.
- The PoseLandmarker is used as a context manager, guaranteeing close.
- `_running` is cleared in a `finally` block.
- `stop()` sets `_running = False`; any in-progress retry/backoff wait is
  interrupted promptly by `interruptible_sleep()`.

---

## Safe QImage Handoff

The emitted `QImage` is now created with `.copy()`, so it owns detached pixel
memory and does not depend on a temporary Python bytes/frame buffer after the
worker iteration continues. Displayed image content is unchanged.

---

## Error Reporting

Lightweight console diagnostics are logged for engineering failures:

- model load failure (`ERROR` status)
- camera open failure (`ERROR` status)
- repeated frame-read failure / reconnect attempts
- worker shutdown

No API keys, patient data, private biomedical recordings, or full frames are
logged.

---

## Tests Added

`tests/test_biogait_runtime.py` covers the engineering helpers:

- **Monotonic clock** — elapsed seconds never decrease; VIDEO timestamps are
  strictly increasing and non-negative.
- **Status guard** — repeated identical statuses are not re-emitted; a state
  transition is reported.
- **Status emitter (review regression)** — the wrapped emit callback returns
  `True` on a real transition and `False` on a duplicate, and emits each
  change only once.
- **Camera open helper (mocked)** — Windows integer webcam DSHOW preference,
  Windows fallback to default backend, non-Windows integer source using the
  default backend directly, URL source path, and all-fail → `None`.
- **Reconnect policy** — failure-threshold triggering, bounded backoff with no
  infinite loop, and full reset on a successful frame.
- **Reconnect / ownership (review regression)** — reopen success does **not**
  report `TRACKING`; original capture is released when replaced; replacement is
  returned as current; failed/tired reconnects keep the current capture.
- **Worker stream ownership (review regression)** — exercising `_stream_loop()`
  with mocked dependencies verifies the active capture (including a reconnect
  replacement) is released when the stream exits.
- **Interruptible sleep** — completes normally when not stopped; interrupts
  promptly on stop.

These tests require no webcam, phone, MediaPipe model download, hardware, or
GUI display.

---

## Validation Commands

```bash
python -m compileall biogait
python -m unittest tests/test_biogait_metrics.py
python -m unittest tests/test_biogait_runtime.py
python -m unittest discover -s tests -p "test_biogait_*.py"
```

---

## Limitations

- M1 does not launch the camera during automated tests; live camera behavior
  must still be exercised on hardware.
- M1 does not download or re-validate the MediaPipe model artifact during
  automated tests.
- The Qt sparklines remain display-history only; they are **not** converted
  into scientific temporal features (smoothing, repetition detection, ROM,
  angular velocity, or movement-quality scoring) in M1.
- M1 adds no new rehabilitation assessment method and makes no CPET changes.