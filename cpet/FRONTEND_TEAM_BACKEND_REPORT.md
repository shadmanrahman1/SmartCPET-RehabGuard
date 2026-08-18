# Frontend Team Report to Backend

**Date:** 2026-04-22  
**Project:** CPET System Web Dashboard  
**Audience:** Backend / Raspberry Pi / Socket.IO integration team  
**Frontend Scope:** `web_dashboard/`

---

## Purpose

This file records frontend work completed in the current implementation pass and translates it into backend-facing requirements, assumptions, and integration notes.

The local PC frontend is responsible for displaying data. The Raspberry Pi server is the live data source.

---

## Task 1: Socket.IO Protocol Alignment

**Frontend status:** Completed

**What changed:**
- Updated `ecg-config.ts` event names to match the Pi Socket.IO protocol.
- Added support for `test_status`, `test_result`, `all_test_results`, `test_started`, and `test_stopped`.
- Kept compatibility with both `get_test_status` and legacy `get_test_status_request`.
- Normalized Pi payloads inside `useECGSocket.ts`.

**Backend/Pi impact:**
- Pi can continue sending `prediction.confidence` as `0-100`.
- Frontend now normalizes confidence internally for display.
- Pi can send `statistics.class_counts` as numeric string keys (`"0"` to `"4"`).
- Frontend maps those counts into display labels.
- Pi can send `test_complete.arrhythmia.class_distribution` as either an array or object.
- Frontend supports both shapes.

**Frontend files involved:**
- `web_dashboard/src/lib/ecg-config.ts`
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/types/index.ts`

---

## Task 2: Real-Time Dashboard Data Handling

**Frontend status:** Completed

**What changed:**
- Dashboard now uses socket data as the primary live source.
- Displays Pi connection state, live/stale/paused status, vitals, ECG waveform, prediction, statistics, and 2-minute test state.
- Fixed class count lookup for `Unknown/Paced` versus frontend key `Unknown_Paced`.

**Backend/Pi impact:**
- For normal operation, Pi should emit these events consistently:
  - `sensor_status`
  - `processed_slow_1hz`
  - `cpet_parameters`
  - `prediction`
  - `statistics`
  - `test_progress`
  - `test_status`
  - `test_live_ecg`
  - `test_complete`
- If Arduino is disconnected, Pi should still emit `sensor_status` with explicit unavailable/stale fields so frontend can show offline or paused states cleanly.

**Frontend files involved:**
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/components/ecg/EcgChart.tsx`
- `web_dashboard/src/components/ecg/PredictionDisplay.tsx`
- `web_dashboard/src/components/ecg/AlertBanner.tsx`

---

## Task 3: Pi Server URL Display

**Frontend status:** Completed

**What changed:**
- Dashboard and ECG monitor now display the server label from `NEXT_PUBLIC_PI_SERVER_URL`.
- The fallback remains `http://mypi.local:5000` when the env var is missing.

**Backend/Pi impact:**
- Pi server hostname/IP can change as long as frontend `.env.local` is updated.
- Frontend no longer depends on hardcoded display text.

**Frontend files involved:**
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/app/ecg-monitor/page.tsx`
- `web_dashboard/src/lib/ecg-config.ts`

---

## Task 4: Two-Minute Test Compatibility

**Frontend status:** Completed

**What changed:**
- Frontend now handles the documented two-minute test protocol.
- Normalizes `test_progress` and `test_status` into one frontend status shape.
- Normalizes `test_complete` and `test_result` into one frontend result shape.
- Report page can read test result class distribution from either array or object payloads.

**Backend/Pi impact:**
- Preferred event flow:
  - client emits `start_test`
  - Pi emits `test_started`
  - Pi emits `test_status`
  - Pi emits `test_progress`
  - Pi emits `test_live_ecg`
  - Pi emits `test_complete`
- Reconnected clients can request latest result with `get_test_result`.

**Frontend files involved:**
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/types/index.ts`
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/app/report/page.tsx`

---

## Task 5: Report Generation Flow

**Frontend status:** Completed for current architecture

**What changed:**
- Report page calls local Next.js API route `POST /api/generate-report`.
- API route uses `OPENROUTER_API_KEY` to call OpenRouter.
- Report can use live two-minute test result or demo fallback.

**Backend/Pi impact:**
- Pi does not need to generate the AI report for this frontend route.
- Existing socket event `clinical_report` is still listened to for compatibility, but current report UI primarily uses the local Next API route.

**Frontend files involved:**
- `web_dashboard/src/app/report/page.tsx`
- `web_dashboard/src/app/api/generate-report/route.ts`
- `web_dashboard/src/lib/useECGSocket.ts`

---

## Task 6: Backend Appwrite Handoff Received

**Frontend status:** Backend update received; frontend follow-up identified

**Backend work completed:**
- Appwrite database `cpet_db` was created or verified.
- Appwrite collections were created or verified:
  - `patients`
  - `sessions`
- Backend verified required patient and session attributes.
- Backend removed hardcoded Appwrite API-key fallback values from Python source files.
- Backend now owns Appwrite writes for completed test-session persistence.

**Verified backend schema summary:**
- `patients` includes patient identity, demographics, medical history, and `created_at`.
- `sessions` includes CPET metrics, arrhythmia fields, respiratory metrics, confidence, diagnosis, and `created_at`.
- Backend verification output reported:

```text
patients missing []
sessions missing []
schema_verify_ok
```

**Frontend impact:**
- Frontend should not use backend Appwrite API keys.
- Frontend should treat Appwrite writes as backend-owned for test sessions.
- Frontend may still read patient records with public/client-safe Appwrite configuration if that remains part of the chosen architecture.
- For saved test sessions, frontend must pass the selected patient identifier to the Pi Socket.IO backend before or during the test.

**Required frontend socket event:**

```js
socket.emit("set_patient_id", {
  patient_id: "patient_001",
  patient_name: "John Doe",
});
```

**Required frontend listener:**

```js
socket.on("patient_id_set", (payload) => {
  console.log("Patient accepted:", payload.patient_id, payload.patient_name);
});
```

**Backend follow-up status:** Completed in backend follow-up report
- Backend now copies selected `patient_id` and `patient_name` into the final `test_complete` result.
- Backend Appwrite persistence can save completed frontend-triggered two-minute tests.
- Backend Appwrite write smoke test passed with create/delete validation.

**Frontend files likely involved in follow-up:**
- `web_dashboard/src/lib/ecg-config.ts`
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/app/dashboard/page.tsx`
- Patient selection flow, once finalized

---

## Task 7: Quality and Run Stability

**Frontend status:** Completed

**What changed:**
- Fixed React purity issue in `AlertBanner.tsx`.
- Fixed malformed `start_frontend.bat`.
- Fixed frontend TypeScript compatibility after protocol normalization.
- Fixed lint errors that blocked clean frontend validation.

**Validation results:**
- `npm run lint`: pass with zero warnings.
- `npx tsc --noEmit`: pass.

---

## Task 8: Backend Protocol Integration Response Received

**Frontend status:** Backend response received; frontend can proceed with patient-ID integration

**Backend changes completed after frontend handoff:**
- Added `get_test_status` Socket.IO alias.
- Kept `get_test_status_request` compatibility.
- Fixed patient identity propagation into final `test_complete` result.
- Fixed Appwrite save payload compatibility for completed two-minute tests.
- Completed Appwrite patient/session save smoke test.

**Backend now supports these frontend-to-server events:**
- `request_stats`
- `request_sensor_status`
- `set_ecg_connection`
- `set_ecg_mode`
- `start_test`
- `stop_test`
- `get_test_status`
- `get_test_status_request`
- `get_test_result`
- `get_all_results`
- `set_patient_id`

**Backend now emits these server-to-frontend events:**
- `server_status`
- `sensor_status`
- `processed_slow_1hz`
- `cpet_parameters`
- `heart_rate`
- `ecg_raw`
- `cpet_stream`
- `ecg_heart_rate`
- `respiratory_rate`
- `prediction`
- `statistics`
- `test_started`
- `test_stopped`
- `test_status`
- `test_progress`
- `test_live_ecg`
- `test_complete`
- `test_result`
- `all_test_results`
- `patient_id_set`
- `error`

**Updated frontend integration contract:**

```js
socket.emit("set_patient_id", {
  patient_id: "patient_001",
  patient_name: "John Doe",
});

socket.emit("start_test");
```

Expected event flow:
- `patient_id_set`
- `test_started`
- `test_status`
- `test_progress`
- `test_live_ecg`
- `test_complete`

Expected `test_complete` high-level shape:

```json
{
  "success": true,
  "timestamp": "ISO datetime",
  "patient_id": "patient_001",
  "patient_name": "John Doe",
  "test_duration_seconds": 120,
  "total_samples": 43200,
  "sampling_rate": 360,
  "parameters": {},
  "ecg_waveform": {},
  "arrhythmia": {},
  "summary": {}
}
```

**Remaining backend blocker:**
- Pi backend still requires Arduino during startup.
- No-Arduino/degraded mode is not available yet.
- Frontend test case "Pi connected but hardware unavailable/stale" depends on backend adding degraded startup mode.

---

## Task 9: MPU6050 Respiratory Motion Frontend Support

**Frontend status:** Completed

**What changed:**
- Added a canonical `MPU6050Data` TypeScript shape for accel/gyro, MPU respiratory rate, motion state, signal quality, and magnitudes.
- `useECGSocket.ts` now normalizes MPU payloads from:
  - `processed_slow_1hz.respiratory_motion`
  - `sensor_status.mpu6050`
  - `sensor_status.respiratory_motion`
  - `processed_slow_1hz.mpu6050`
  - top-level processed payload keys such as `ACC_X`, `GYRO_Z`, or lowercase aliases
  - `cpet_parameters.respiratory_motion`
  - derived `cpet_parameters` fields such as `respiratory_rate_mpu_bpm`, `respiratory_motion_quality`, `motion_state`, `avg_acc_magnitude_g`, and `avg_gyro_magnitude_dps`
- Dashboard now displays:
  - `Resp (MPU)`
  - `Motion`
- ECG Monitor vitals panel now displays:
  - `Resp (MPU)`
  - `Motion`
  - signal quality or gyro magnitude when available
- Analytics page now includes respiratory-motion and motion-artifact context in the performance strip.
- Report page and `POST /api/generate-report` now include MPU respiratory/motion context in both structured display and AI report prompt input.

**Backend/Pi impact:**
- Preferred live payload extension:

```json
{
  "respiratory_motion": {
    "acc_x": 123,
    "acc_y": -54,
    "acc_z": 16780,
    "gyro_x": 5,
    "gyro_y": -2,
    "gyro_z": 1,
    "acc_mag_g": 1.024,
    "gyro_mag_dps": 0.04,
    "resp_rate_mpu": 16.8,
    "motion_state": "low",
    "resp_signal_quality": "good",
    "resp_axis": "ACC_Z"
  }
}
```

- Preferred event location: `processed_slow_1hz`.
- Also supported: `sensor_status.mpu6050`, `sensor_status.respiratory_motion`, and `cpet_parameters.respiratory_motion`.
- For final two-minute results, frontend will display these optional fields under `test_complete.parameters`:
  - `respiratory_rate_mpu`
  - `respiratory_motion_quality`
  - `motion_quality`
  - `avg_acc_magnitude`
  - `avg_gyro_magnitude`
  - `avg_acc_magnitude_g`
  - `avg_gyro_magnitude_dps`
  - `max_gyro_magnitude_dps`
  - `mpu_sample_count`

**Frontend files involved:**
- `web_dashboard/src/types/index.ts`
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/components/ecg/VitalsPanel.tsx`
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/app/ecg-monitor/page.tsx`
- `web_dashboard/src/app/analysis/page.tsx`
- `web_dashboard/src/app/report/page.tsx`
- `web_dashboard/src/app/api/generate-report/route.ts`

---

## Task 10: Latest Backend State Response

**Frontend status:** Completed

**Backend update received:**
- Backend now starts in degraded/no-Arduino mode.
- Backend emits Arduino availability fields in `sensor_status`.
- Backend supports both `set_patient_id` before test start and `start_test` with `{ patient_id, patient_name }`.
- Backend emits `patient_id_set`.
- Backend exposes MPU fields from `sensor_status`, `processed_slow_1hz`, and `cpet_parameters`.
- Backend cautions that CNN validation is weak, so frontend should avoid diagnostic certainty.

**What changed in frontend:**
- Added `setPatientIdentity(patientId, patientName)` helper to `useECGSocket.ts`.
- Added `patient_id_set` listener plus accepted patient ID/name state.
- Dashboard now has lightweight Patient ID and Patient Name inputs.
- Dashboard emits `set_patient_id` with both fields before `start_test`.
- `sensor_status` normalization now preserves:
  - `arduino_connected`
  - `arduino_connection_status`
  - `arduino_status_message`
  - `arduino_stream_stale`
  - `arduino_last_data_age_sec`
  - `mpu6050`
  - `respiratory_motion`
- Dashboard and ECG monitor now show Arduino unavailable/stale separately from Pi Socket.IO connection.
- Dashboard disables new test starts when backend reports Arduino data unavailable.
- Frontend listens to `test_started`, `test_stopped`, and backend `error` events.
- CNN UI copy was softened from diagnostic language to screening/assistive language.

**Frontend files involved:**
- `web_dashboard/src/lib/ecg-config.ts`
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/types/index.ts`
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/components/ecg/ConnectionStatus.tsx`
- `web_dashboard/src/components/ecg/PredictionDisplay.tsx`
- `web_dashboard/src/app/report/page.tsx`
- `web_dashboard/src/app/api/generate-report/route.ts`

---

## Task 11: Patient Identity Required Before Two-Minute Test

**Frontend status:** Completed

**Backend update received:**
- Two-minute CPET tests now require both:
  - `patient_id`
  - `patient_name`
- Backend returns `patient_required` if either field is missing.
- Backend includes both fields in `patient_id_set`, `test_started`, and `test_complete`.

**What changed in frontend:**
- Added `setPatientIdentity(patientId, patientName)` to `useECGSocket.ts`.
- Kept `setPatientId(patientId, patientName)` as a compatibility alias.
- Updated `startTest(patientId, patientName)` to use the preferred flow:
  - emit `set_patient_id`
  - wait once for `patient_id_set`
  - emit `start_test`
- Dashboard now has Patient ID and Patient Name inputs.
- Dashboard disables Start Test until both fields exist.
- Frontend stores accepted `patient_id` and `patient_name` from `patient_id_set`.
- Frontend handles backend `patient_required` errors without treating them as server crashes.
- Dashboard test result displays `test_complete.patient_id` and `test_complete.patient_name`.
- Report page displays Patient ID and Patient Name in the Test Session section.
- AI report prompt includes Patient ID and Patient Name when a live test result is available.

**Backend error handled:**

```json
{
  "success": false,
  "status": "patient_required",
  "message": "Patient ID and patient name are required before starting a test",
  "missing_fields": ["patient_id", "patient_name"]
}
```

**Frontend files involved:**
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/types/index.ts`
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/app/report/page.tsx`
- `web_dashboard/src/app/api/generate-report/route.ts`

---

## Current Integration Boundaries

**Realtime data source:** Raspberry Pi Socket.IO server  
**Local frontend role:** display live and derived data  
**REST backend role:** session/event storage for `/analysis/[id]`  
**Patient database:** Appwrite  
**AI report route:** local Next.js route to OpenRouter

Important distinction:
- `/dashboard`, `/ecg-monitor`, and `/analysis` are socket-driven.
- `/analysis/[id]` is FastAPI REST-driven.
- Appwrite writes for completed test sessions are backend-owned.
- Frontend should pass `patient_id` and `patient_name` through Socket.IO; it should not expose backend Appwrite secrets.

Backend should decide whether Pi will also persist live session events to FastAPI if `/analysis/[id]` should reflect real Pi sessions.

Latest backend response confirms completed two-minute tests can now persist to Appwrite when frontend sends `set_patient_id` with both patient ID and patient name.

---

## Backend/Pi Checklist

- Confirm Pi Socket.IO runs on default namespace `/`.
- Confirm Socket.IO v4 compatibility.
- Confirm `NEXT_PUBLIC_PI_SERVER_URL` points to reachable Pi host.
- Keep `prediction.confidence` numeric; frontend accepts both `94.52` and `0.9452`.
- Emit `sensor_status` even when Arduino is disconnected.
- Emit `arduino_stream_stale` and data-age fields when available.
- Keep `test_complete` shape stable enough to include `parameters`, `ecg_waveform`, `arrhythmia`, and `summary`.
- For `statistics`, either send `class_distribution` by names or `class_counts` by class IDs.
- Confirm `set_patient_id` emits `patient_id_set` after accepting patient ID and patient name.
- Ensure final `test_complete` processing includes the selected `patient_id` and `patient_name` before Appwrite save.
- Emit MPU6050 respiratory motion as `processed_slow_1hz.respiratory_motion` when Arduino SLOW packets include `ACC_X`, `ACC_Y`, `ACC_Z`, `GYRO_X`, `GYRO_Y`, and `GYRO_Z`.
- Include `respiratory_rate_mpu`, `motion_quality`, `avg_acc_magnitude`, and `avg_gyro_magnitude` in `test_complete.parameters` when test-level MPU summaries are available.
- Keep no-Arduino/degraded startup mode emitting `sensor_status` so the frontend can show Pi connected while sensor data is unavailable.

---

## Frontend Follow-Up Checklist

- Keep backend Appwrite API keys out of frontend code and browser bundles.
- Live-test Pi-connected/sensors-unavailable UI state against backend degraded mode.
- Verify selected Patient ID appears in `test_complete.patient_id`.
- Verify selected Patient Name appears in `test_complete.patient_name`.
- Verify completed test persists to Appwrite with the selected patient identity.

---

## Security Note

`web_dashboard/setup-appwrite.js` currently contains a hardcoded Appwrite API key. If that key is real, rotate it and move secrets to environment variables before sharing or deploying.

Backend report confirms no backend API key or secret value should be copied into frontend code.

---

## Latest Frontend Status

Frontend is ready for Pi-side integration testing with the documented Socket.IO protocol.

Recommended next backend test:
1. Start Pi server without Arduino and confirm frontend shows Pi connected plus Arduino unavailable.
2. Confirm test start is disabled or warns while hardware is unavailable.
3. Start Pi server with Arduino connected.
4. Enter a Patient ID and Patient Name, start a two-minute test, and confirm `patient_id_set`.
5. Emit MPU6050 fields in the Arduino SLOW stream and confirm frontend shows `Resp (MPU)`, `Motion`, and quality state.
6. Confirm `test_status`, `test_progress`, and `test_complete` render correctly.
7. Verify completed test persists to Appwrite with the selected `patient_id` and `patient_name`.
8. Confirm `test_complete.parameters` includes MPU summary fields when backend calculation is available.

---

## Task 10: Derived Metrics Backend Update Consumption

**Frontend status:** Completed

**Backend update consumed:** 2026-04-22 derived metrics update from Pi/backend team.

**What changed:**
- Added frontend type support for derived CPET aliases:
  - `lrc_index`
  - `o2_pulse_surrogate`
  - `co2_delta`
  - `net_co2`
  - `ve_vco2_slope_surrogate`
  - `respiratory_rate_source`
  - `ventilatory_efficiency_status`
  - `ptt_available`
  - `ptt_status`
- Updated socket normalization so older and newer backend field names map into one frontend shape.
- Dashboard, ECG Monitor, Analysis, Report, and AI report payload now prefer the new backend-derived fields.
- PTT is displayed as unavailable/disabled when `ptt_available === false`; frontend no longer implies PTT is working without PPG waveform timing.
- Prediction panels now respect `sensor_status.prediction_active` and `sensor_status.prediction_status`, so stale CNN predictions are hidden/paused when ECG/electrodes are unavailable.

**Backend/Pi impact:**
- Backend can emit either legacy names or new derived-metric names; frontend accepts both.
- Preferred names going forward:
  - `cpet_parameters.lrc_ratio` or `lrc_index`
  - `cpet_parameters.respiratory_rate_bpm`
  - `cpet_parameters.respiratory_rate_source`
  - `cpet_parameters.o2_pulse_surrogate`
  - `cpet_parameters.co2_delta`
  - `cpet_parameters.ve_vco2_slope_surrogate`
  - `cpet_parameters.ptt_available`
  - `sensor_status.prediction_active`
  - `sensor_status.prediction_status`

**Frontend files involved:**
- `web_dashboard/src/types/index.ts`
- `web_dashboard/src/lib/useECGSocket.ts`
- `web_dashboard/src/app/dashboard/page.tsx`
- `web_dashboard/src/app/ecg-monitor/page.tsx`
- `web_dashboard/src/app/analysis/page.tsx`
- `web_dashboard/src/app/report/page.tsx`
- `web_dashboard/src/app/api/generate-report/route.ts`
- `web_dashboard/src/components/ecg/VitalsPanel.tsx`
- `web_dashboard/src/components/ecg/CPETParametersDisplay.tsx`

**Validation:**
- `npx tsc --noEmit`: pass
- `npm run lint`: pass
