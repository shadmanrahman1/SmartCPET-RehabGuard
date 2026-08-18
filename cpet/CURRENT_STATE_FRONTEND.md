# CPET System Frontend - Current State Audit

**Date:** 2026-04-22  
**Project:** Next.js Web Dashboard for CPET (Cardiopulmonary Exercise Testing)  
**Location:** `web_dashboard/`

---

## 1. Current Folder Structure

```text
web_dashboard/src/
|-- app/
|   |-- api/
|   |   \-- generate-report/
|   |       \-- route.ts
|   |-- analysis/
|   |   |-- [id]/
|   |   |   \-- page.tsx
|   |   \-- page.tsx
|   |-- dashboard/
|   |   \-- page.tsx
|   |-- ecg-monitor/
|   |   \-- page.tsx
|   |-- patients/
|   |   \-- page.tsx
|   |-- report/
|   |   \-- page.tsx
|   |-- favicon.ico
|   |-- globals.css
|   |-- layout.tsx
|   \-- page.tsx
|-- components/
|   |-- ecg/
|   |   |-- AlertBanner.tsx
|   |   |-- ConnectionStatus.tsx
|   |   |-- CPETParametersDisplay.tsx
|   |   |-- EcgChart.tsx
|   |   |-- ECGModeControl.tsx
|   |   |-- ECGStatisticsDisplay.tsx
|   |   |-- PredictionDisplay.tsx
|   |   \-- VitalsPanel.tsx
|   |-- layout/
|   |   |-- app-layout.tsx
|   |   |-- header.tsx
|   |   \-- sidebar.tsx
|   |-- ui/
|   |   |-- button.tsx
|   |   |-- card.tsx
|   |   |-- input.tsx
|   |   \-- table.tsx
|   \-- theme-provider.tsx
|-- lib/
|   |-- api.ts
|   |-- appwrite.ts
|   |-- ecg-config.ts
|   |-- useECGSocket.ts
|   \-- utils.ts
\-- types/
    \-- index.ts
```

**Removed from active frontend tree:** `LandingNav.tsx`, `SplineScene.tsx`, `ECGWaveform.tsx`, `hooks/useSocket.ts`.

---

## 2. Runtime Architecture (Current)

1. `/` redirects to `/dashboard`.
2. Real-time monitoring pages (`/dashboard`, `/ecg-monitor`, `/analysis`) consume Socket.IO via `useECGSocket()`.
3. Session detail page `/analysis/[id]` uses REST polling from FastAPI (`getSession`, `getSessionStats`, `getSessionEvents`).
4. Patients page reads Appwrite database documents using client-side Appwrite config.
5. Report page calls local Next API route `/api/generate-report`, which calls OpenRouter.
6. Backend/Pi now owns Appwrite writes for completed two-minute test sessions.
7. MPU6050 respiratory-motion data is treated as a live Pi Socket.IO extension, not as browser-owned hardware logic.

---

## 3. Page-by-Page State

### 3.1 `/dashboard`
- Uses live socket state for connection, vitals, ECG chart, prediction, alerts, statistics.
- Includes 2-minute test controls and progress/result panel.
- Server label now uses env-driven value (`NEXT_PUBLIC_PI_SERVER_URL`) instead of hardcoded display text.
- Displays `Resp (MPU)` and `Motion` when respiratory-motion payloads are available.

### 3.2 `/ecg-monitor`
- Full live monitor page with connection status, waveform, prediction panel, vitals, statistics, CPET parameters.
- Header subtitle now uses dynamic server label from env var.
- Vitals panel now includes MPU6050 respiratory rate and motion-artifact context.

### 3.3 `/analysis`
- Live analytics with class distribution bar/pie charts and CPET metric strip.
- Reads from socket statistics + processed vitals.
- Includes respiratory-motion and motion quality in the performance strip when available.

### 3.4 `/analysis/[id]`
- REST-backed session detail page (FastAPI).
- Polls every 1 second.
- Confidence display now handles both scales (0-1 or 0-100).

### 3.5 `/patients`
- Appwrite-backed patient listing via `databases.listDocuments(...)`.
- Search input and Add Patient remain UI-level (not fully wired as CRUD flow).

### 3.6 `/report`
- Uses `POST /api/generate-report` (Next route) for AI report generation.
- Supports live test result and demo fallback.
- `OPENROUTER_API_KEY` required in environment for real generation.
- Structured report and AI prompt now include MPU respiratory-motion and artifact summaries when present.

---

## 4. Socket Contract Handling (Updated)

`useECGSocket.ts` now includes protocol-aligned normalization for Pi server contract:

- Handles `prediction.confidence` robustly (supports 0-100 and 0-1 inputs).
- Handles test events:
  - `test_progress`
  - `test_status`
  - `test_complete`
  - `test_result`
- Uses both status requests for compatibility:
  - `get_test_status`
  - `get_test_status_request`
- Normalizes `statistics` payload from either:
  - direct `class_distribution`, or
  - Pi-style `class_counts` map.
- Normalizes respiratory rate fields including `breaths_per_minute`.
- Normalizes MPU6050 respiratory-motion fields from:
  - `processed_slow_1hz.respiratory_motion`
  - `sensor_status.mpu6050`
  - `sensor_status.respiratory_motion`
  - `processed_slow_1hz.mpu6050`
  - top-level accel/gyro aliases such as `ACC_X`, `ACC_Z`, `GYRO_X`, `GYRO_Z`
  - `cpet_parameters.respiratory_motion`
  - test/result summary fields such as `respiratory_rate_mpu` and `motion_quality`.

Current configured test-related events in `ecg-config.ts` include:
- `start_test`, `stop_test`
- `set_patient_id`, `patient_id_set`
- `get_test_status`, `get_test_status_request`
- `get_test_result`
- `test_progress`, `test_status`, `test_live_ecg`, `test_started`, `test_stopped`, `test_complete`, `test_result`
- `get_all_results`, `all_test_results`

Patient handoff status:
- Frontend now exposes `setPatientIdentity(patientId, patientName)` in `useECGSocket.ts`.
- `setPatientId(patientId, patientName)` remains as a compatibility alias.
- Frontend listens for `patient_id_set` and stores the accepted patient ID and patient name.
- Dashboard has lightweight Patient ID and Patient Name fields.
- Start Test is disabled until both Patient ID and Patient Name exist.
- Dashboard uses the preferred flow: emit `set_patient_id` with both fields, wait for `patient_id_set`, then emit `start_test`.
- `test_complete.patient_id` and `test_complete.patient_name` are displayed in dashboard result and report views.

Current frontend flow:

```js
socket.emit("set_patient_id", {
  patient_id: "patient_001",
  patient_name: "John Doe",
});

socket.emit("start_test");
```

Expected backend event:

```js
socket.on("patient_id_set", (payload) => {
  console.log("Patient accepted:", payload.patient_id, payload.patient_name);
});
```

---

## 5. Backend Integration Update

Latest backend report confirms:
- `get_test_status` alias has been added.
- `get_test_status_request` remains supported.
- `patient_id` is now copied into the final `test_complete` result.
- `patient_name` is now required and copied into the final `test_complete` result.
- Completed two-minute test results can persist to Appwrite when patient identity is set.
- Appwrite patient/session save smoke test passed.

Degraded hardware status:
- Backend now supports no-Arduino/degraded startup.
- Frontend separates Pi/backend connection from Arduino hardware availability.
- Dashboard and ECG monitor render Arduino unavailable/stale state from `sensor_status`.
- Dashboard disables new two-minute test start while Arduino data is unavailable, while keeping the app shell usable.

---

## 6. MPU6050 Respiratory Motion Support

Frontend support is now implemented for the planned chest-mounted MPU6050 integration.

Preferred live Pi payload:

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

Frontend display locations:
- `/dashboard`: `Resp (MPU)` and `Motion` metric cards.
- `/ecg-monitor`: live vitals cards for `Resp (MPU)` and `Motion`.
- `/analysis`: performance strip includes respiratory-motion and artifact context.
- `/report`: structured report and AI prompt include MPU respiratory/motion data.

Optional final test-result fields supported under `test_complete.parameters`:
- `respiratory_rate_mpu`
- `motion_quality`
- `avg_acc_magnitude`
- `avg_gyro_magnitude`
- `avg_acc_magnitude_g`
- `avg_gyro_magnitude_dps`
- `max_gyro_magnitude_dps`
- `mpu_sample_count`

Backend still owns MPU parsing, filtering, respiratory-rate estimation, and Appwrite persistence.

---

## 7. Environment and URLs

Expected key frontend env vars:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_PI_SERVER_URL=http://mypi.local:5000
NEXT_PUBLIC_APPWRITE_ENDPOINT=...
NEXT_PUBLIC_APPWRITE_PROJECT_ID=...
NEXT_PUBLIC_APPWRITE_DATABASE_ID=...
NEXT_PUBLIC_APPWRITE_PATIENTS_COLLECTION_ID=...
OPENROUTER_API_KEY=...
```

Notes:
- Pi URL still has fallback default `http://mypi.local:5000` in code when env is missing.
- Dashboard and monitor now display server label from env-derived value (not hardcoded text).

---

## 8. Quality Checks (Executed)

### TypeScript
- Command: `npx tsc --noEmit`
- Status: **PASS**

### ESLint
- Command: `npm run lint`
- Status: **PASS**
- Current: 0 errors, 0 warnings.

### Dev Server
- Frontend was run successfully at `http://localhost:3000`.
- HTTP check returned status `200`.
- Dev server was later stopped by user request.

---

## 9. Data Mode Summary

### Live vs Static
- **Real-time vitals and ECG:** live from Pi socket stream.
- **Session analysis `/analysis/[id]`:** FastAPI REST polling.
- **Patients:** Appwrite live database read.
- **Completed test-session writes:** backend-owned Appwrite persistence.
- **Report:** AI generation via local Next API route to OpenRouter, with demo fallback.
- **MPU6050 respiratory motion:** live display from Pi socket payloads; backend-owned processing.

---

## 10. Current Frontend Follow-Up

Highest-priority frontend follow-up:
- Keep backend Appwrite API keys out of browser code.

Integration follow-up:
- Live-test Pi connection using the latest backend no-Arduino mode.
- Verify `sensor_status` degraded fields render correctly.
- After backend emits MPU fields from Arduino SLOW packets, verify live `Resp (MPU)` and `Motion` updates.
- Verify patient ID appears in final `test_complete.patient_id`.
- Verify patient name appears in final `test_complete.patient_name`.
- Verify Appwrite session persistence is under the selected patient identity.

---

## 11. Changes Since Previous Audit

Major differences versus the 2026-04-20 snapshot and latest backend handoffs:
- Socket protocol support expanded and normalized for current Pi contract.
- Confidence scale mismatches fixed in display paths.
- Test status/result schema compatibility added.
- Statistics mapping from `class_counts` supported.
- MPU6050 respiratory-motion normalization and display added.
- Hardcoded server label text removed from dashboard/monitor displays.
- `start_frontend.bat` repaired.
- Frontend now TypeScript-clean and ESLint-clean with zero warnings.
- Backend now supports `get_test_status`, `set_patient_id`, `patient_id_set`, Appwrite session persistence, and patient identity propagation into `test_complete`.
- Backend now requires both `patient_id` and `patient_name` before two-minute tests.
- Backend now supports no-Arduino/degraded startup mode.
- Frontend now wires patient ID and patient name selection/emission from the dashboard.
- Frontend now renders degraded Arduino state separately from backend connection.

---

*Updated to reflect current implemented frontend behavior and protocol handling as of 2026-04-22.*
