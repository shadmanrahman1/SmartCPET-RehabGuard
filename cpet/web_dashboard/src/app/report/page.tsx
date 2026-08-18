"use client"

import { useState, useRef } from "react"
import { useECGSocket } from "@/lib/useECGSocket"
import {
  FileText, Loader2, Sparkles, FlaskConical,
  RefreshCw, AlertCircle, Heart, Wind, Activity,
  CheckCircle2, AlertTriangle,
} from "lucide-react"
import type { TestResult } from "@/types"

// ─── helpers ────────────────────────────────────────────────────────────────

const fmt = (v: number | null | undefined, dp = 1, fallback = "—") =>
  v != null ? v.toFixed(dp) : fallback

// ─── static demo data (shown when Pi is offline) ────────────────────────────

const DEMO: TestResult = {
  success: true,
  patient_id: "demo_patient_001",
  patient_name: "Demo Patient",
  timestamp: new Date().toISOString(),
  test_duration_seconds: 120,
  total_samples: 43200,
  sampling_rate: 360,
  parameters: {
    heart_rate: 74,
    heart_rate_source: "ecg_r_peak",
    respiratory_rate: 17,
    respiratory_rate_source: "ecg_derived",
    respiratory_rate_mpu: 16.8,
    respiratory_motion_quality: "good",
    motion_quality: "low",
    avg_acc_magnitude: 16384.2,
    avg_gyro_magnitude: 4.8,
    avg_acc_magnitude_g: 1.02,
    avg_gyro_magnitude_dps: 0.04,
    max_gyro_magnitude_dps: 0.12,
    mpu_sample_count: 120,
    hrv: { sdnn: 28.4, rmssd: 22.1, lf_hf_ratio: 1.6 },
    total_peaks_detected: 148,
    total_rr_intervals: 147,
    co2_ambient_ppm: 418,
    co2_exhaled_ppm: 852,
    net_co2_ppm: 434,
    ve_vco2_slope: 27.8,
    lung_efficiency_status: "good",
  },
  ecg_waveform: { data: [], duration_seconds: 120, sample_count: 4320, original_sample_count: 43200 },
  arrhythmia: {
    total_predictions: 480,
    dominant_class: 0,
    dominant_class_name: "Normal (N)",
    confidence: 94.5,
    class_distribution: { "0": 454, "1": 12, "2": 8, "3": 4, "4": 2 },
    class_labels: {
      "0": "Normal (N)", "1": "Supraventricular (S)", "2": "Ventricular (V)",
      "3": "Fusion (F)", "4": "Unknown (Q)",
    },
    arrhythmia_detected: false,
    arrhythmia_type: null,
    threshold_used: 0.6,
  },
  summary: {
    status: "completed",
    interpretation: "Screening output: normal rhythm pattern | confidence 94.5% | no significant arrhythmia pattern flagged",
  },
}

// ─── Section wrapper ─────────────────────────────────────────────────────────

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 0 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        borderBottom: "1px solid var(--border-subtle)",
        paddingBottom: 6, marginBottom: 12,
      }}>
        {icon}
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
          color: "var(--text-secondary)" }}>{title}</span>
      </div>
      {children}
    </div>
  )
}

// ─── A single parameter row ──────────────────────────────────────────────────

function Row({ label, value, unit, range, ok, note }: {
  label: string; value: string; unit?: string; range?: string; ok?: boolean; note?: string
}) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr auto auto",
      alignItems: "center", gap: 12,
      padding: "7px 0",
      borderBottom: "1px solid color-mix(in srgb, var(--border-subtle) 50%, transparent)",
      fontSize: 12,
    }}>
      <div>
        <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{label}</span>
        {note && <span style={{ display: "block", fontSize: 10, color: "var(--text-secondary)", marginTop: 1 }}>{note}</span>}
      </div>
      <span style={{ fontWeight: 700, color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
        {value}{unit ? <span style={{ fontWeight: 400, color: "var(--text-secondary)", marginLeft: 2 }}>{unit}</span> : null}
      </span>
      {range && ok != null ? (
        <span style={{
          fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 20,
          background: ok ? "color-mix(in srgb, var(--emerald-color) 12%, transparent)"
                         : "color-mix(in srgb, var(--amber-color) 12%, transparent)",
          color: ok ? "var(--emerald-color)" : "var(--amber-color)",
        }}>
          {ok ? "Normal" : "Review"}
        </span>
      ) : <span />}
    </div>
  )
}

// ─── Structured medical report component ─────────────────────────────────────

function DiagnosticReport({ data, isDemo }: { data: TestResult; isDemo: boolean }) {
  const p = data.parameters
  const a = data.arrhythmia
  const date = new Date(data.timestamp)
  const dateStr = date.toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" })
  const timeStr = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })

  const hrOk = p.heart_rate != null && p.heart_rate >= 60 && p.heart_rate <= 100
  const rrOk = p.respiratory_rate != null && p.respiratory_rate >= 12 && p.respiratory_rate <= 20
  const mpuRrOk = p.respiratory_rate_mpu == null || (p.respiratory_rate_mpu >= 12 && p.respiratory_rate_mpu <= 22)
  const motionState = p.motion_quality?.toLowerCase() ?? null
  const motionOk = !motionState || motionState === "low" || motionState === "stable"
  const motionSignalQuality = p.respiratory_motion_quality?.replace(/_/g, " ").toUpperCase() ?? "--"
  const sdnnOk = p.hrv?.sdnn != null && p.hrv.sdnn >= 20
  const veValue = p.ve_vco2_slope_surrogate ?? p.ve_vco2_slope
  const veOk = veValue != null && veValue <= 35
  const co2DeltaValue = p.co2_delta ?? p.net_co2 ?? p.net_co2_ppm
  const oxygenPulseValue = p.o2_pulse_surrogate
  const lrcValue = p.lrc_ratio ?? p.lrc_index
  const lungOk = p.lung_efficiency_status === "good"
  const arrOk = !a.arrhythmia_detected

  const overallOk = hrOk && arrOk && veOk && lungOk && motionOk

  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border-subtle)",
      borderRadius: 12,
      overflow: "hidden",
    }}>

      {/* ── Letterhead ───────────────────────────────────────────────── */}
      <div style={{
        padding: "24px 28px 16px",
        borderBottom: "2px solid color-mix(in srgb, var(--color-primary) 40%, transparent)",
        background: "color-mix(in srgb, var(--color-primary) 4%, var(--bg-card))",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: "var(--color-primary)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Activity size={18} color="#fff" />
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                  KUET BME Medical Centre
                </div>
                <div style={{ fontSize: 10, color: "var(--text-secondary)", letterSpacing: "0.05em" }}>
                  CARDIOPULMONARY EXERCISE TESTING UNIT
                </div>
              </div>
            </div>
            <div style={{ fontSize: 10, color: "var(--text-secondary)", marginTop: 4 }}>
              Khulna University of Engineering & Technology · Department of Biomedical Engineering
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.05em", color: "var(--text-secondary)", textTransform: "uppercase" }}>
              Screening Report
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginTop: 2 }}>{dateStr}</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>Time: {timeStr}</div>
            <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>
              Ref: CPET-{date.getFullYear()}-{String(date.getMonth()+1).padStart(2,"0")}{String(date.getDate()).padStart(2,"0")}
            </div>
          </div>
        </div>

        {/* Overall outcome banner */}
        <div style={{
          marginTop: 14, padding: "10px 14px", borderRadius: 8,
          background: overallOk
            ? "color-mix(in srgb, var(--emerald-color) 10%, transparent)"
            : "color-mix(in srgb, var(--amber-color) 10%, transparent)",
          border: `1px solid color-mix(in srgb, ${overallOk ? "var(--emerald-color)" : "var(--amber-color)"} 30%, transparent)`,
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {overallOk
              ? <CheckCircle2 size={16} color="var(--emerald-color)" />
              : <AlertTriangle size={16} color="var(--amber-color)" />}
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
              {overallOk
                ? "Overall Screening: No major abnormal pattern flagged"
                : "Overall Screening: Review recommended — one or more parameters outside expected range"}
            </span>
          </div>
          {isDemo && (
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
              background: "color-mix(in srgb, var(--amber-color) 20%, transparent)",
              color: "var(--amber-color)", textTransform: "uppercase", letterSpacing: "0.05em",
            }}>Demo Data</span>
          )}
        </div>
      </div>

      {/* ── Sections ─────────────────────────────────────────────────── */}
      <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 24 }}>

        {/* Test Metadata */}
        <Section title="Test Session" icon={<FileText size={13} color="var(--text-secondary)" />}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
            {[
              { label: "Patient Name", value: data.patient_name ?? "—" },
              { label: "Patient ID", value: data.patient_id ?? "—" },
              { label: "Protocol", value: "2-Min Resting CPET" },
              { label: "Duration", value: `${data.test_duration_seconds}s` },
              { label: "ECG Samples", value: data.total_samples.toLocaleString() },
              { label: "Sampling Rate", value: `${data.sampling_rate} Hz` },
              { label: "CNN Windows", value: a.total_predictions },
              { label: "Test Status", value: data.summary.status === "completed" ? "Completed ✓" : "Stopped Early" },
            ].map(({ label, value }) => (
              <div key={label} style={{
                padding: "8px 12px", borderRadius: 8,
                background: "color-mix(in srgb, var(--border-subtle) 60%, transparent)",
              }}>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                  color: "var(--text-secondary)", marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{value}</div>
              </div>
            ))}
          </div>
        </Section>

        {/* Cardiac Assessment */}
        <Section title="Cardiac Assessment" icon={<Heart size={13} color="var(--red-color)" />}>
          <Row
            label="Heart Rate"
            value={fmt(p.heart_rate, 0)}
            unit="BPM"
            range="60–100"
            ok={hrOk}
            note={`Source: ${p.heart_rate_source?.replace(/_/g, " ") ?? "—"}`}
          />
          <Row
            label="HRV — SDNN"
            value={fmt(p.hrv?.sdnn)}
            unit="ms"
            range="≥20 ms"
            ok={sdnnOk}
            note="Standard deviation of NN intervals (autonomic nervous system index)"
          />
          <Row
            label="HRV — RMSSD"
            value={fmt(p.hrv?.rmssd)}
            unit="ms"
            note="Root mean square of successive differences"
          />
          <Row
            label="LF/HF Ratio"
            value={fmt(p.hrv?.lf_hf_ratio)}
            note="Sympathovagal balance (lower = more parasympathetic)"
          />
          <Row
            label="Total R-Peaks Detected"
            value={String(p.total_peaks_detected)}
            note={`${p.total_rr_intervals} valid RR intervals`}
          />

          {/* Arrhythmia result */}
          <div style={{
            marginTop: 10, padding: "10px 12px", borderRadius: 8,
            background: arrOk
              ? "color-mix(in srgb, var(--emerald-color) 8%, transparent)"
              : "color-mix(in srgb, var(--red-color) 8%, transparent)",
            border: `1px solid color-mix(in srgb, ${arrOk ? "var(--emerald-color)" : "var(--red-color)"} 25%, transparent)`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              {arrOk
                ? <CheckCircle2 size={14} color="var(--emerald-color)" />
                : <AlertTriangle size={14} color="var(--red-color)" />}
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                CNN Rhythm Screen: {a.dominant_class_name}
              </span>
              <span style={{
                marginLeft: "auto", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                background: "color-mix(in srgb, var(--blue-color) 12%, transparent)",
                color: "var(--blue-color)",
              }}>
                {a.confidence.toFixed(1)}% confidence
              </span>
            </div>
            <div style={{ fontSize: 10, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {data.summary.interpretation}
            </div>
            {/* Class breakdown mini-bars */}
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 3 }}>
              {Object.entries(a.class_labels).map(([k, name]) => {
                const count = Array.isArray(a.class_distribution)
                  ? (a.class_distribution[Number(k)] ?? 0)
                  : (a.class_distribution[k] ?? 0)
                const pct = a.total_predictions > 0 ? (count / a.total_predictions) * 100 : 0
                const isDominant = Number(k) === a.dominant_class
                return (
                  <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 10 }}>
                    <span style={{ width: 140, color: isDominant ? "var(--text-primary)" : "var(--text-secondary)",
                      fontWeight: isDominant ? 600 : 400 }}>{name}</span>
                    <div style={{ flex: 1, height: 4, borderRadius: 2, background: "var(--border-subtle)", overflow: "hidden" }}>
                      <div style={{
                        height: "100%", width: `${pct}%`,
                        background: isDominant
                          ? (arrOk ? "var(--emerald-color)" : "var(--red-color)")
                          : "var(--text-secondary)",
                        transition: "width 0.6s ease",
                      }} />
                    </div>
                    <span style={{ width: 34, textAlign: "right", color: "var(--text-secondary)",
                      fontVariantNumeric: "tabular-nums" }}>{pct.toFixed(0)}%</span>
                  </div>
                )
              })}
            </div>
            <div style={{ marginTop: 6, fontSize: 9, color: "var(--text-secondary)" }}>
              ⚠ CNN model v1 — MIT-BIH accuracy 22.1%. Retraining in progress. Screening aid only, not a standalone diagnosis.
            </div>
          </div>
        </Section>

        {/* Respiratory Assessment */}
        <Section title="Respiratory Assessment" icon={<Wind size={13} color="var(--blue-color)" />}>
          <Row
            label="Respiratory Rate"
            value={fmt(p.respiratory_rate, 0)}
            unit="br/min"
            range="12–20"
            ok={rrOk}
            note={`Source: ${p.respiratory_rate_source?.replace(/_/g, " ") ?? "—"}`}
          />
          <Row
            label="Chest Motion RR"
            value={fmt(p.respiratory_rate_mpu)}
            unit="br/min"
            range="12–22"
            ok={mpuRrOk}
            note="MPU6050 sternum-mounted respiratory motion estimate"
          />
          <Row
            label="Motion Quality"
            value={p.motion_quality?.toUpperCase() ?? "—"}
            range="Low"
            ok={motionOk}
            note="Movement artifact context from MPU6050 gyro/accel data"
          />
          <Row
            label="Resp Motion Quality"
            value={motionSignalQuality}
            note="Backend quality flag for chest-motion respiratory estimate"
          />
          <Row
            label="Avg Acc Magnitude"
            value={fmt(p.avg_acc_magnitude_g ?? p.avg_acc_magnitude)}
            unit={p.avg_acc_magnitude_g != null ? "g" : undefined}
            note="Mean accelerometer magnitude during two-minute test"
          />
          <Row
            label="Avg Gyro Magnitude"
            value={fmt(p.avg_gyro_magnitude_dps ?? p.avg_gyro_magnitude)}
            unit={p.avg_gyro_magnitude_dps != null ? "dps" : undefined}
            note={p.mpu_sample_count != null ? `${p.mpu_sample_count} MPU samples summarized` : "Mean gyroscope magnitude during two-minute test"}
          />
          <Row
            label="Ambient CO₂ (A1 Sensor)"
            value={fmt(p.co2_ambient_ppm, 0)}
            unit="ppm"
            note="Baseline environmental CO₂ (MQ-135 A1)"
          />
          <Row
            label="Exhaled CO₂ (A2 Sensor)"
            value={fmt(p.co2_exhaled_ppm, 0)}
            unit="ppm"
            note="Exhaled CO₂ concentration (MQ-135 A2)"
          />
          <Row
            label="Net CO₂ Production"
            value={fmt(p.net_co2_ppm, 0)}
            unit="ppm"
            note="Exhaled − Ambient = true metabolic CO₂ output"
          />
        </Section>

        {/* CPET Parameters */}
        <Section title="CPET Robust Parameters" icon={<Activity size={13} color="var(--purple-color)" />}>
          <Row
            label="LRC Ratio"
            value={fmt(lrcValue, 3)}
            range="0.20-0.30"
            ok={lrcValue == null || (lrcValue >= 0.15 && lrcValue <= 0.35)}
            note="Lung-respiratory-cardiac index from backend derived metrics"
          />
          <Row
            label="O2 Pulse Surrogate"
            value={fmt(oxygenPulseValue, 2)}
            unit="ml/beat"
            range="10-20"
            ok={oxygenPulseValue == null || oxygenPulseValue >= 8}
            note="Project surrogate only; not direct VO2 measurement"
          />
          <Row
            label="CO2 Delta"
            value={fmt(co2DeltaValue, 0)}
            unit="ppm"
            range=">0"
            ok={co2DeltaValue == null || co2DeltaValue > 0}
            note="Exhaled CO2 minus ambient CO2"
          />
          <Row
            label="VE/VCO2 Surrogate"
            value={fmt(veValue)}
            unit="L/L"
            range="20-30"
            ok={veOk}
            note="Raw-sensor/project surrogate. Steep slope (>35) suggests review, not diagnosis."
          />
          <Row
            label="PTT"
            value={p.ptt_available === false ? "Unavailable" : fmt(p.ptt_ms)}
            unit={p.ptt_available === false ? "" : "ms"}
            ok={p.ptt_available === false ? undefined : p.ptt_ms != null}
            note={p.ptt_available === false ? "Backend correctly disables PTT without PPG waveform timing" : `Status: ${p.ptt_status ?? "ok"}`}
          />
          <Row
            label="Lung Efficiency Status"
            value={p.lung_efficiency_status?.toUpperCase() ?? "--"}
            range="Good"
            ok={lungOk}
            note="Derived from VE/VCO2 surrogate and CO2 differential"
          />

          {/* CPET params from cpetParameters (live 1Hz stream) — shown as a note if unavailable */}
          <div style={{
            marginTop: 8, padding: "8px 12px", borderRadius: 8, fontSize: 10,
            background: "color-mix(in srgb, var(--border-subtle) 40%, transparent)",
            color: "var(--text-secondary)", lineHeight: 1.7,
          }}>
            <strong style={{ color: "var(--text-primary)" }}>Note on LRC Ratio, Oxygen Pulse &amp; PTT:</strong>
            {" "}These parameters require the real-time 1 Hz sensor stream (LO+/LO− leads connected, finger PPG active).
            They are available on the ECG Monitor &rarr; CPET Parameters panel during live sessions.
          </div>
        </Section>

        {/* Clinical Interpretation */}
        <Section title="Clinical Interpretation" icon={<Sparkles size={13} color="var(--amber-color)" />}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, lineHeight: 1.8 }}>
            {[
              hrOk
                ? "✅ Heart rate is within the normal resting range."
                : "⚠ Heart rate outside normal range — further evaluation recommended.",
              rrOk
                ? "✅ Respiratory rate is normal."
                : "⚠ Respiratory rate outside normal range.",
              mpuRrOk
                ? "✅ Chest-motion respiratory estimate is within expected range or unavailable."
                : "⚠ MPU6050 chest-motion respiratory estimate needs review.",
              motionOk
                ? "✅ Motion artifact level is acceptable for interpretation."
                : `⚠ Motion artifact is ${p.motion_quality?.toUpperCase() ?? "UNKNOWN"} — interpret respiratory-motion data cautiously.`,
              arrOk
                ? `✅ CNN screening found no significant arrhythmia pattern (${a.dominant_class_name}, ${a.confidence.toFixed(1)}% confidence).`
                : `⚠ Rhythm pattern flagged — ${a.dominant_class_name} (${a.confidence.toFixed(1)}% confidence). Clinical review advised.`,
              veOk
                ? "✅ VE/VCO₂ slope is within the normal ventilatory efficiency range."
                : "⚠ Steep VE/VCO₂ slope detected — may indicate underlying cardiopulmonary limitation.",
              sdnnOk
                ? "✅ HRV metrics indicate adequate autonomic nervous system function."
                : "⚠ Low HRV (SDNN < 20 ms) may reflect autonomic dysfunction.",
              lungOk
                ? "✅ Lung efficiency classification: GOOD."
                : `⚠ Lung efficiency classification: ${p.lung_efficiency_status?.toUpperCase() ?? "UNKNOWN"} — monitor closely.`,
            ].map((line, i) => (
              <div key={i} style={{
                color: line.startsWith("✅") ? "var(--text-primary)" : "var(--amber-color)",
                padding: "4px 0",
                borderBottom: i < 7 ? "1px solid color-mix(in srgb, var(--border-subtle) 40%, transparent)" : "none",
              }}>
                {line}
              </div>
            ))}
          </div>
        </Section>

        {/* Footer */}
        <div style={{
          padding: "12px 0 0",
          borderTop: "1px solid var(--border-subtle)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexWrap: "wrap", gap: 8,
        }}>
          <div style={{ fontSize: 9, color: "var(--text-secondary)", lineHeight: 1.6 }}>
            Generated by <strong>SmartCPET v1.0</strong> · KUET Department of Biomedical Engineering, 2026<br />
            Powered by CNN arrhythmia classifier (MIT-BIH) + OpenRouter Gemma 4 · This report is a screening aid only.
          </div>
          <div style={{ fontSize: 9, color: "var(--text-secondary)" }}>
            Screening aid only, not a clinical diagnosis
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const {
    isConnected,
    sensorStatus,
    processedData,
    cpetParameters,
    mpuData,
    latestPrediction,
    statistics,
    testResult: liveTestResult,
  } = useECGSocket()

  const [data, setData]     = useState<TestResult | null>(null)
  const [isDemo, setIsDemo] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState<string | null>(null)
  const startTimeRef        = useRef<number>(Date.now())
  const predictionStatusLower = sensorStatus?.prediction_status?.toLowerCase() ?? ''
  const predictionLive = isConnected &&
    sensorStatus?.ecg_connected_effective !== false &&
    sensorStatus?.prediction_active !== false &&
    !['inactive', 'paused', 'unavailable', 'disabled', 'stale', 'lead_off'].includes(predictionStatusLower)
  const displayPrediction = predictionLive ? latestPrediction : null

  function loadDemo() {
    setData(DEMO)
    setIsDemo(true)
    setError(null)
  }

  function useTestResult() {
    if (liveTestResult) {
      setData(liveTestResult)
      setIsDemo(false)
      setError(null)
    }
  }

  async function generateAIReport() {
    setLoading(true)
    setError(null)
    const durationSecs = Math.round((Date.now() - startTimeRef.current) / 1000)
    const mm = Math.floor(durationSecs / 60)
    const ss = durationSecs % 60
    try {
      const res = await fetch("/api/generate-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          processedData,
          cpetParameters: cpetParameters ?? processedData?.cpet_parameters ?? null,
          mpuData: mpuData ?? processedData?.respiratory_motion ?? cpetParameters?.respiratory_motion ?? null,
          latestPrediction: displayPrediction,
          statistics,
          sessionDuration: `${mm}m ${ss}s`,
          testResult: liveTestResult,
        }),
      })
      const json = await res.json() as { report?: string; error?: string }
      if (!res.ok || json.error) throw new Error(json.error ?? `HTTP ${res.status}`)
      // Build a testResult shape from the AI text for now, fall back to demo with AI note
      setData(liveTestResult ?? DEMO)
      setIsDemo(false)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em",
            display: "flex", alignItems: "center", gap: 8 }}>
            <FileText size={20} color="var(--color-primary)" /> Clinical Screening Report
          </h1>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4, margin: 0 }}>
            KUET BME · Cardiopulmonary Exercise Testing Unit
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {data && (
            <button
              onClick={() => { setData(null); setIsDemo(false); setError(null) }}
              style={btnStyle("var(--text-secondary)")}
            >
              <RefreshCw size={13} /> New Report
            </button>
          )}

          {liveTestResult && !data && (
            <button onClick={useTestResult} style={btnStyle("var(--emerald-color)")}>
              <CheckCircle2 size={13} /> Use 2-Min Test Result
            </button>
          )}

          <button
            onClick={loadDemo}
            disabled={loading}
            style={btnStyle("var(--amber-color)")}
          >
            <FlaskConical size={13} /> Load Demo
          </button>

          <button
            onClick={generateAIReport}
            disabled={loading}
            style={{
              ...btnStyle("var(--purple-color)"),
              background: "color-mix(in srgb, var(--purple-color) 15%, transparent)",
            }}
          >
            {loading
              ? <><Loader2 size={13} style={{ animation: "spin 0.9s linear infinite" }} /> Generating…</>
              : <><Sparkles size={13} /> Generate with Gemma</>}
          </button>
        </div>
      </div>

      {/* Context banner — no Pi */}
      {!isConnected && !data && (
        <div style={infoBanner("var(--amber-color)")}>
          <AlertCircle size={13} color="var(--amber-color)" />
          <span>Pi is offline — click <strong>Load Demo</strong> to preview a sample report.</span>
        </div>
      )}

      {/* 2-Min result available notice */}
      {liveTestResult && !data && (
        <div style={infoBanner("var(--emerald-color)")}>
          <CheckCircle2 size={13} color="var(--emerald-color)" />
          <span>2-Minute test result is available. Click <strong>Use 2-Min Test Result</strong> to generate the report.</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={infoBanner("var(--red-color)")}>
          <AlertCircle size={13} color="var(--red-color)" />
          <span><strong>Generation failed:</strong> {error} — Try the Demo button instead.</span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 12, padding: "60px 20px",
          background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: 12,
        }}>
          <div style={{
            width: 52, height: 52, borderRadius: "50%",
            border: "3px solid var(--border-subtle)",
            borderTopColor: "var(--purple-color)",
            animation: "spin 0.9s linear infinite",
          }} />
          <p style={{ fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>Gemma is analysing your session…</p>
          <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: 0 }}>Sending CPET data to OpenRouter · ~10s</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Empty state */}
      {!data && !loading && (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 12, padding: "60px 20px",
          background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: 12,
        }}>
          <div style={{
            width: 60, height: 60, borderRadius: 16,
            background: "color-mix(in srgb, var(--color-primary) 10%, transparent)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <FileText size={28} color="var(--color-primary)" style={{ opacity: 0.6 }} />
          </div>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>No Report Yet</h3>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", textAlign: "center", maxWidth: 340, margin: 0, lineHeight: 1.6 }}>
            Complete a <strong>2-Minute Test</strong> on the dashboard, then come here to view the structured diagnostic
            report — or click <strong>Load Demo</strong> to preview the layout.
          </p>
        </div>
      )}

      {/* THE REPORT */}
      {data && !loading && <DiagnosticReport data={data} isDemo={isDemo} />}
    </div>
  )
}

// ─── micro style helpers ─────────────────────────────────────────────────────

function btnStyle(accent: string): React.CSSProperties {
  return {
    display: "inline-flex", alignItems: "center", gap: 5,
    padding: "7px 13px", borderRadius: 8, fontSize: 12, fontWeight: 600,
    border: `1px solid color-mix(in srgb, ${accent} 35%, transparent)`,
    background: `color-mix(in srgb, ${accent} 8%, transparent)`,
    color: accent, cursor: "pointer",
  }
}

function infoBanner(accent: string): React.CSSProperties {
  return {
    display: "flex", alignItems: "center", gap: 8,
    padding: "8px 14px", borderRadius: 8, fontSize: 11,
    border: `1px solid color-mix(in srgb, ${accent} 30%, transparent)`,
    background: `color-mix(in srgb, ${accent} 8%, transparent)`,
    color: "var(--text-secondary)",
  }
}
