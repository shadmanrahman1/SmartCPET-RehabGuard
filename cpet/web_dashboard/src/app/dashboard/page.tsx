"use client"

import { useEffect, useState, useRef } from "react"
import Link from "next/link"
import {
  Heart, Activity, Wind, Zap, Droplets,
  Wifi, WifiOff, AlertTriangle, ArrowRight, BarChart2, CheckCircle2, RefreshCw, Timer, Square, Loader2
} from "lucide-react"
import { useECGSocket } from "@/lib/useECGSocket"
import { EcgChart }    from "@/components/ecg/EcgChart"
import { AlertBanner } from "@/components/ecg/AlertBanner"
import { ARRHYTHMIA_CLASSES } from "@/lib/ecg-config"

// ─── Vital metric card ───────────────────────────────────────────────────────
function MetricCard({
  label, value, unit, icon, color, sub
}: {
  label: string; value: string; unit: string
  icon: React.ReactNode; color: string; sub?: string
}) {
  return (
    <div style={{
      flex: "1 1 160px", minWidth: 140,
      padding: "16px 18px", borderRadius: 12,
      border: `1px solid var(--border-subtle)`,
      background: `var(--bg-card)`,
      display: "flex", flexDirection: "column", gap: 8,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.05em",
          color: "var(--text-secondary)", textTransform: "uppercase" }}>{label}</span>
        <div style={{ color, opacity: 0.8 }}>{icon}</div>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 26, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em",
          fontVariantNumeric: "tabular-nums" }}>{value}</span>
        <span style={{ fontSize: 12, color: color, fontWeight: 500, opacity: 0.9 }}>{unit}</span>
      </div>
      {sub && <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>{sub}</div>}
    </div>
  )
}

// ─── Arrhythmia class distribution bar ──────────────────────────────────────
function ClassBar({ name, count, total, color }: { name: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0"
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{name}</span>
        <span style={{ fontSize: 11, color, fontWeight: 500 }}>{pct}%</span>
      </div>
      <div style={{ height: 3, borderRadius: 1.5, background: "var(--border-subtle)" }}>
        <div style={{
          height: "100%", borderRadius: 1.5,
          width: `${pct}%`,
          background: color,
          minWidth: count > 0 ? 3 : 0,
          transition: "width 0.5s ease",
        }} />
      </div>
    </div>
  )
}

function ParameterGuideCard({
  label,
  meaning,
  source,
  note,
  color,
  icon,
}: {
  label: string
  meaning: string
  source: string
  note?: string
  color: string
  icon: React.ReactNode
}) {
  return (
    <div style={{
      padding: "14px 15px",
      borderRadius: 14,
      border: "1px solid rgba(15,23,42,0.10)",
      background: "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.96))",
      boxShadow: "0 10px 26px rgba(15,23,42,0.05)",
      display: "flex",
      flexDirection: "column",
      gap: 8,
      minHeight: 150,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span style={{
          width: 30,
          height: 30,
          borderRadius: 10,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color,
          background: `color-mix(in srgb, ${color} 10%, transparent)`,
          border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
          flexShrink: 0,
        }}>
          {icon}
        </span>
        <span style={{
          fontSize: 11,
          fontWeight: 850,
          color: "var(--text-primary)",
          textTransform: "uppercase",
          letterSpacing: "0.07em",
        }}>
          {label}
        </span>
      </div>

      <div style={{ fontSize: 12, color: "var(--text-primary)", lineHeight: 1.5, fontWeight: 600 }}>
        {meaning}
      </div>

      <div style={{ fontSize: 10.5, color: "var(--text-secondary)", lineHeight: 1.45 }}>
        <strong style={{ color: "var(--text-primary)" }}>Source:</strong> {source}
      </div>

      {note && (
        <div style={{
          marginTop: "auto",
          padding: "6px 8px",
          borderRadius: 9,
          background: "rgba(245,158,11,0.10)",
          color: "#92400e",
          fontSize: 10,
          lineHeight: 1.45,
          fontWeight: 700,
        }}>
          {note}
        </div>
      )}
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const {
    isConnected,
    sensorStatus, isEcgConnectedEffective, isVitalsStale,
    processedData, ecgPoints, activeAlert, dismissAlert,
    cpetParameters, mpuData, latestPrediction,
    statistics,
    reconnect, disconnect,
    testStatus, testResult, startTest, stopTest, requestTestStatus, clearTestResult,
    acceptedPatientId, acceptedPatientName, patientIdentityError
  } = useECGSocket()

  const [sessionTime, setSessionTime] = useState(0)
  const [patientId, setPatientIdInput] = useState('')
  const [patientName, setPatientNameInput] = useState('')
  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const piServerLabel = (process.env.NEXT_PUBLIC_PI_SERVER_URL || 'http://mypi.local:5000').replace(/^https?:\/\//, '')

  const toConfidencePercent = (value: number | null | undefined) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 0
    return value > 1 ? value : value * 100
  }

  const getClassCount = (name: string) => {
    if (!statistics) return 0
    if (name === 'Unknown/Paced') return statistics.class_distribution.Unknown_Paced ?? 0
    return statistics.class_distribution[name as keyof typeof statistics.class_distribution] ?? 0
  }

  const isTestRunning = testStatus?.active === true

  useEffect(() => {
    if (isTestRunning) {
      pollerRef.current = setInterval(requestTestStatus, 1000)
    } else {
      if (pollerRef.current) { clearInterval(pollerRef.current); pollerRef.current = null }
    }
    return () => { if (pollerRef.current) clearInterval(pollerRef.current) }
  }, [isTestRunning, requestTestStatus])

  function handleStartTest() {
    const trimmedPatientId = patientId.trim()
    const trimmedPatientName = patientName.trim()
    startTest(trimmedPatientId || undefined, trimmedPatientName || undefined)
    setTimeout(requestTestStatus, 400)
  }

  // Session clock — starts ticking when connected
  useEffect(() => {
    if (!isConnected) return
    const id = setInterval(() => setSessionTime(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [isConnected])

  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`

  const unifiedBpm = typeof processedData?.bpm === 'number' && processedData.bpm > 0
    ? processedData.bpm
    : typeof processedData?.hr === 'number' && processedData.hr > 0
      ? processedData.hr
      : typeof sensorStatus?.bpm === 'number' && sensorStatus.bpm > 0
        ? sensorStatus.bpm
        : null

  const bpmSource = processedData?.bpm_source ?? sensorStatus?.bpm_source

  const bpmSourceLabel = bpmSource === 'max30102'
    ? 'Source: Finger Sensor'
    : bpmSource === 'ecg'
      ? 'Source: ECG'
      : 'Source: Auto'

  const hrStatusOk = sensorStatus ? ((sensorStatus.bpm_status ?? sensorStatus.hr_status) === 'ok') : true
  const spo2StatusOk = sensorStatus ? sensorStatus.spo2_status === 'ok' : true

  const hr   = hrStatusOk ? (unifiedBpm?.toFixed(0) ?? "--") : "--"
  const spo2 = spo2StatusOk ? (processedData?.spo2?.toFixed(1) ?? "--") : "--"

  const cpet = cpetParameters ?? processedData?.cpet_parameters ?? null

  const co2DeltaValue = cpet?.co2_delta ?? cpet?.net_co2 ?? processedData?.co2_delta ?? processedData?.net_co2 ?? null
  const co2  = typeof co2DeltaValue === 'number' && Number.isFinite(co2DeltaValue) ? co2DeltaValue.toFixed(1) : "--"

  const pttUnavailable = cpet?.ptt_available === false || (cpet?.ptt_status && cpet.ptt_status !== 'ok')
  const lrcUnavailable = cpet?.lrc_status && cpet.lrc_status !== 'ok'

  const ptt  = pttUnavailable ? 'N/A' : (cpet?.ptt_ms?.toFixed(0) ?? "--")
  const lrcValue = cpet?.lrc_ratio ?? cpet?.lrc_index ?? null
  const lrc  = lrcUnavailable ? 'N/A' : (lrcValue?.toFixed(3) ?? "--")
  const respiratoryRate = cpet?.respiratory_rate_bpm?.toFixed(1) ?? "--"
  const respiratoryRateSource = cpet?.respiratory_rate_source
    ? cpet.respiratory_rate_source.replace(/_/g, ' ')
    : 'Backend selected source'
  const oxygenPulse = (cpet?.o2_pulse_surrogate ?? cpet?.oxygen_pulse)?.toFixed(2) ?? "--"
  const veVco2 = (cpet?.ve_vco2_slope_surrogate ?? cpet?.ve_vco2_slope)?.toFixed(2) ?? "--"

  const pttHint = pttUnavailable
    ? (cpet?.ptt_available === false
        ? 'PTT disabled: no PPG waveform timing'
        : cpet?.ptt_status === 'unavailable_no_ppg_waveform'
          ? 'Requires finger sensor waveform'
          : `Unavailable: ${(cpet?.ptt_status || 'unknown').replace(/_/g, ' ')}`)
    : undefined

  const lrcHint = lrcUnavailable
    ? (cpet?.lrc_status === 'unavailable_rr'
        ? 'Requires ECG respiratory rate'
        : `Unavailable: ${(cpet?.lrc_status || 'unknown').replace(/_/g, ' ')}`)
    : undefined

  const predictionStatusLower = sensorStatus?.prediction_status?.toLowerCase() ?? ''
  const predictionLive = isConnected &&
    isEcgConnectedEffective &&
    sensorStatus?.prediction_active !== false &&
    !['inactive', 'paused', 'unavailable', 'disabled', 'stale', 'lead_off'].includes(predictionStatusLower)
  const displayPrediction = predictionLive ? (latestPrediction ?? processedData?.cnn_result ?? null) : null
  const respiratoryMotion =
    mpuData ??
    processedData?.respiratory_motion ??
    cpet?.respiratory_motion ??
    sensorStatus?.respiratory_motion ??
    sensorStatus?.mpu6050 ??
    null
  const mpuResp = respiratoryMotion?.resp_rate_mpu ?? null
  const mpuRespDisplay = typeof mpuResp === 'number' && Number.isFinite(mpuResp) ? mpuResp.toFixed(1) : "--"
  const motionState = respiratoryMotion?.motion_state ?? null
  const motionStateLower = motionState?.toLowerCase() ?? ''
  const motionDisplay = motionState ? motionState.replace(/_/g, ' ').toUpperCase() : "--"
  const motionQuality = respiratoryMotion?.resp_signal_quality ?? null
  const motionColor = motionStateLower === 'high' || motionStateLower === 'severe'
    ? 'var(--red-color)'
    : motionStateLower === 'moderate' || motionStateLower === 'medium'
      ? 'var(--amber-color)'
      : motionStateLower
        ? 'var(--emerald-color)'
        : 'var(--text-secondary)'

  const streamStatus = !isConnected
    ? 'OFFLINE'
    : isVitalsStale
      ? 'STALE'
      : (isEcgConnectedEffective ? 'LIVE' : 'PAUSED')

  const hardwareUnavailable =
    sensorStatus?.arduino_connected === false ||
    sensorStatus?.arduino_connection_status === 'unavailable' ||
    sensorStatus?.ecg_reason === 'arduino_unavailable'

  const patientReady = patientId.trim().length > 0 && patientName.trim().length > 0
  const testStartDisabled = !isConnected || (!isTestRunning && (hardwareUnavailable || !patientReady))
  const testButtonHint = hardwareUnavailable
    ? (sensorStatus?.arduino_status_message ?? 'Arduino data unavailable; backend is online in degraded mode')
    : !patientReady
      ? 'Patient ID and patient name are required before starting a test'
    : acceptedPatientId
      ? `Patient accepted: ${acceptedPatientName ?? 'Unknown'} (${acceptedPatientId})`
      : undefined
  const selectedPatientLabel = patientReady
    ? `${patientName.trim()} (${patientId.trim()})`
    : acceptedPatientId && acceptedPatientName
      ? `${acceptedPatientName} (${acceptedPatientId})`
      : null

  const streamStatusColor = !isConnected
    ? '#ef4444'
    : isVitalsStale
      ? '#f59e0b'
      : (isEcgConnectedEffective ? '#22c55e' : '#ef4444')

  const totalBeats = statistics
    ? Object.values(statistics.class_distribution).reduce((a, b) => a + b, 0)
    : 0

  const measuredParameters = [
    {
      label: "ECG Waveform",
      meaning: "Electrical activity of the heart. Used for rhythm view, R-peak timing, ECG heart rate, HRV, and arrhythmia screening.",
      source: "Chest electrodes through Arduino/Pi ECG stream.",
      note: "Lead-off or unavailable electrodes pause ECG-based prediction.",
      color: "var(--emerald-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "Heart Rate",
      meaning: "How many times the heart beats per minute.",
      source: "Primarily MAX30102 finger sensor; ECG can be used when available.",
      color: "var(--red-color)",
      icon: <Heart size={14} />,
    },
    {
      label: "SpO2",
      meaning: "Estimated blood oxygen saturation percentage.",
      source: "MAX30102 finger pulse oximeter.",
      note: "Poor finger contact can make this stale or unavailable.",
      color: "var(--blue-color)",
      icon: <Droplets size={14} />,
    },
    {
      label: "Ambient CO2",
      meaning: "Room/background CO2 baseline before comparing exhaled air.",
      source: "Ambient gas sensor channel on Arduino slow stream.",
      color: "var(--purple-color)",
      icon: <Wind size={14} />,
    },
    {
      label: "Exhaled CO2",
      meaning: "CO2 trend measured from the breathing/exhalation path.",
      source: "Exhaled gas sensor channel on Arduino slow stream.",
      color: "var(--purple-color)",
      icon: <Wind size={14} />,
    },
    {
      label: "CO2 Delta",
      meaning: "Difference between exhaled CO2 and ambient CO2. It is the project gas-exchange proxy.",
      source: "Backend derived from exhaled CO2 minus ambient CO2.",
      color: "var(--purple-color)",
      icon: <Wind size={14} />,
    },
    {
      label: "Airflow",
      meaning: "Breathing airflow trend used as a ventilation proxy.",
      source: "Flow sensor value from Arduino slow stream.",
      note: "Current value is a project proxy unless calibrated to clinical L/min.",
      color: "var(--cyan-color)",
      icon: <Wind size={14} />,
    },
    {
      label: "Resp Rate",
      meaning: "Breaths per minute selected by the backend from the best available respiratory source.",
      source: "ECG-derived respiration or MPU6050 chest motion.",
      color: "var(--blue-color)",
      icon: <Wind size={14} />,
    },
    {
      label: "Resp (MPU)",
      meaning: "Breathing rate estimated from chest motion.",
      source: "MPU6050 accelerometer/gyroscope mounted on the chest.",
      note: "Motion artifacts can reduce confidence.",
      color: "var(--blue-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "Motion",
      meaning: "Body movement/artifact context used to judge signal quality.",
      source: "MPU6050 gyro and acceleration magnitude.",
      color: "var(--amber-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "LRC Index",
      meaning: "Lung-respiratory-cardiac coupling index. It relates breathing rhythm to heart rhythm.",
      source: "Backend derived from respiratory rate and heart rate/ECG timing.",
      note: "Unavailable until a respiratory-rate source is present.",
      color: "var(--emerald-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "O2 Pulse",
      meaning: "Project surrogate for oxygen used per heartbeat. It hints at stroke-volume/exercise response.",
      source: "Backend derived surrogate from available oxygen/heart-rate context.",
      note: "Not direct VO2; label as surrogate.",
      color: "var(--red-color)",
      icon: <Heart size={14} />,
    },
    {
      label: "PTT",
      meaning: "Pulse transit time: delay between ECG R-peak and finger pulse arrival.",
      source: "Would need synchronized ECG and PPG waveform peak timing.",
      note: "Correctly disabled now because PPG waveform timing is not available yet.",
      color: "var(--amber-color)",
      icon: <Zap size={14} />,
    },
    {
      label: "VE/VCO2",
      meaning: "Ventilation to CO2 relationship. In this project it is a raw-sensor efficiency surrogate.",
      source: "Backend derived from airflow proxy and CO2 delta.",
      note: "Use as project trend, not clinical ventilatory-equivalent diagnosis.",
      color: "var(--cyan-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "HRV",
      meaning: "Heart-rate variability, including SDNN/RMSSD/LF-HF. It reflects beat-to-beat timing variation.",
      source: "Backend derives it from ECG R-R intervals during tests.",
      color: "var(--emerald-color)",
      icon: <Activity size={14} />,
    },
    {
      label: "Arrhythmia CNN",
      meaning: "Prototype AI classification of ECG windows into Normal, Supraventricular, Ventricular, Fusion, or Unknown.",
      source: "Pi backend CNN over ECG windows.",
      note: "Screening aid only; not a clinical diagnosis.",
      color: "var(--blue-color)",
      icon: <BarChart2 size={14} />,
    },
  ]

  // Pre-compute test result panel so we avoid IIFE in JSX
  const testResultPanel = testResult ? (() => {
    const a = testResult.arrhythmia
    const p = testResult.parameters
    const isAbnormal = a?.arrhythmia_detected
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
        {/* Rhythm header */}
        <div style={{
          padding: '12px', borderRadius: 10,
          border: `1px solid color-mix(in srgb, ${isAbnormal ? 'var(--red-color)' : 'var(--emerald-color)'} 30%, transparent)`,
          background: `color-mix(in srgb, ${isAbnormal ? 'var(--red-color)' : 'var(--emerald-color)'} 8%, transparent)`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            {isAbnormal ? <AlertTriangle size={15} color="var(--red-color)" /> : <CheckCircle2 size={15} color="var(--emerald-color)" />}
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{a?.dominant_class_name}</span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {testResult.summary?.interpretation}
          </div>
        </div>

        {/* Key metrics */}
        {([
          { label: 'Patient',    value: testResult.patient_name ? `${testResult.patient_name}` : '—', color: 'var(--text-primary)' },
          { label: 'Patient ID', value: testResult.patient_id ?? '—',                                  color: 'var(--text-secondary)' },
          { label: 'Confidence', value: `${a?.confidence?.toFixed(1)}%`,                              color: 'var(--blue-color)' },
          { label: 'HR (ECG)',   value: p?.heart_rate ? `${p.heart_rate} bpm` : '—',                  color: 'var(--red-color)' },
          { label: 'RR',        value: p?.respiratory_rate ? `${p.respiratory_rate} br/m` : '—',      color: 'var(--text-primary)' },
          { label: 'RR (MPU)',   value: p?.respiratory_rate_mpu != null ? `${p.respiratory_rate_mpu.toFixed(1)} br/m` : '—', color: 'var(--blue-color)' },
          { label: 'Motion',     value: p?.motion_quality ? p.motion_quality.toUpperCase() : '—',     color: 'var(--amber-color)' },
          { label: 'HRV SDNN',  value: p?.hrv?.sdnn ? `${p.hrv.sdnn.toFixed(1)} ms` : '—',           color: 'var(--text-primary)' },
          { label: 'Net CO₂',   value: p?.net_co2_ppm ? `${p.net_co2_ppm.toFixed(0)} ppm` : '—',     color: 'var(--purple-color)' },
          { label: 'VE/VCO₂',  value: p?.ve_vco2_slope ? p.ve_vco2_slope.toFixed(2) : '—',           color: 'var(--amber-color)' },
        ] as { label: string; value: string; color: string }[]).map(({ label, value, color }) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
            <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
            <span style={{ fontWeight: 600, color }}>{value}</span>
          </div>
        ))}

        {/* Lung efficiency chip */}
        {p?.lung_efficiency_status && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 10px', borderRadius: 6,
            background: `color-mix(in srgb, ${p.lung_efficiency_status === 'good' ? 'var(--emerald-color)' : p.lung_efficiency_status === 'fair' ? 'var(--amber-color)' : 'var(--red-color)'} 15%, transparent)`,
            fontSize: 10, fontWeight: 700,
          }}>
            <span style={{ color: 'var(--text-secondary)' }}>LUNG EFFICIENCY</span>
            <span style={{ textTransform: 'uppercase',
              color: p.lung_efficiency_status === 'good' ? 'var(--emerald-color)'
                : p.lung_efficiency_status === 'fair' ? 'var(--amber-color)' : 'var(--red-color)',
            }}>{p.lung_efficiency_status}</span>
          </div>
        )}

        <div style={{ fontSize: 9, color: 'var(--text-secondary)', marginTop: 2 }}>
          {a?.total_predictions} CNN windows · {testResult.total_samples} samples · {testResult.test_duration_seconds}s
        </div>

        <Link href="/report" style={{
          display: 'block', textAlign: 'center', padding: '8px',
          borderRadius: 6, background: 'var(--blue-color)', color: '#fff',
          fontSize: 11, fontWeight: 600, textDecoration: 'none'
        }}>
          View Full AI Report
        </Link>
      </div>
    )
  })() : null

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Showcase banner ──────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "4px 12px", borderRadius: 6,
        border: "1px solid var(--border-subtle)",
        background: "transparent",
        letterSpacing: "0.05em",
        marginBottom: -8,
      }}>
        <span style={{ fontSize: 10, fontWeight: 500, color: "var(--text-secondary)", textTransform: "uppercase" }}>
          KUET BME &nbsp;·&nbsp; SmartCPET v1.0 &nbsp;—&nbsp; Live Demo
        </span>
      </div>

      {/* ── Header row ──────────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            CPET Dashboard
          </h1>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
            Real-time cardiopulmonary exercise monitoring
          </p>
        </div>

        {/* Connection pill */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 14px", borderRadius: 20,
            border: `1px solid color-mix(in srgb, ${isConnected ? "var(--emerald-color)" : "var(--red-color)"} 30%, transparent)`,
            background: `color-mix(in srgb, ${isConnected ? "var(--emerald-color)" : "var(--red-color)"} 8%, transparent)`,
          }}>
            {isConnected
              ? <Wifi size={14} color="#22c55e" />
              : <WifiOff size={14} color="#ef4444" />
            }
            <span style={{ fontSize: 12, fontWeight: 600,
              color: isConnected ? "#22c55e" : "#ef4444" }}>
              {isConnected ? "Pi Connected" : "Pi Offline"}
            </span>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {!testResult && (
              <>
                <input
                  value={patientId}
                  onChange={(event) => setPatientIdInput(event.target.value)}
                  placeholder="Patient ID"
                  aria-label="Patient ID"
                  style={{
                    width: 108,
                    padding: "7px 10px",
                    borderRadius: 8,
                    border: "1px solid var(--border-subtle)",
                    background: "var(--bg-card)",
                    color: "var(--text-primary)",
                    fontSize: 11,
                    outline: "none",
                  }}
                />
                <input
                  value={patientName}
                  onChange={(event) => setPatientNameInput(event.target.value)}
                  placeholder="Patient Name"
                  aria-label="Patient Name"
                  style={{
                    width: 140,
                    padding: "7px 10px",
                    borderRadius: 8,
                    border: "1px solid var(--border-subtle)",
                    background: "var(--bg-card)",
                    color: "var(--text-primary)",
                    fontSize: 11,
                    outline: "none",
                  }}
                />
              </>
            )}
            {!testResult ? (
              <button
                disabled={testStartDisabled}
                onClick={isTestRunning ? stopTest : handleStartTest}
                title={testButtonHint}
                style={{
                  ...pillBtn(isTestRunning ? "var(--red-color)" : "var(--blue-color)"),
                  opacity: testStartDisabled ? 0.5 : 1,
                  display: "flex", alignItems: "center", gap: 6,
                  background: `color-mix(in srgb, ${isTestRunning ? 'var(--red-color)' : 'var(--blue-color)'} 10%, transparent)`,
                }}
              >
                {isTestRunning ? <Square size={12} /> : <Timer size={12} />}
                {isTestRunning ? "Stop Test" : "2-Min Test"}
              </button>
            ) : (
              <button
                onClick={clearTestResult}
                style={{
                  ...pillBtn("var(--text-secondary)"),
                  display: "flex", alignItems: "center", gap: 6,
                }}
              >
                <RefreshCw size={12} /> Clear Result
              </button>
            )}

            {isConnected
              ? <button onClick={disconnect} style={pillBtn("#ef4444")}>Disconnect</button>
              : <button onClick={reconnect}  style={pillBtn("#22c55e")}>Reconnect</button>
            }
          </div>
          {!testResult && (
            <div style={{
              fontSize: 10,
              color: patientIdentityError ? 'var(--amber-color)' : 'var(--text-secondary)',
              width: '100%',
              textAlign: 'right',
              marginTop: -4,
            }}>
              {patientIdentityError
                ? patientIdentityError
                : selectedPatientLabel
                  ? `Selected patient: ${selectedPatientLabel}`
                  : 'Select patient ID and name before starting a test'}
            </div>
          )}
        </div>
      </div>

      {/* ── Alert banner ───────────────────────────────────────────────── */}
      <AlertBanner alert={activeAlert} onDismiss={dismissAlert} />

      {isConnected && hardwareUnavailable && (
        <div style={{
          padding: "10px 14px",
          borderRadius: 10,
          border: "1px solid color-mix(in srgb, var(--amber-color) 35%, transparent)",
          background: "color-mix(in srgb, var(--amber-color) 9%, transparent)",
          color: "var(--amber-color)",
          fontSize: 11,
          fontWeight: 600,
        }}>
          Backend online in degraded mode. {sensorStatus?.arduino_status_message ?? "Arduino sensor stream is unavailable or stale."}
        </div>
      )}

      {/* ── Session info strip ──────────────────────────────────────────── */}
      <div style={{
        display: "flex", gap: 16, flexWrap: "wrap",
        padding: "12px 16px", borderRadius: 10,
        border: "1px solid var(--border-subtle)",
        background: "var(--bg-card)",
      }}>
        <InfoChip label="STATUS"   value={streamStatus}
          color={streamStatusColor} />
        <InfoChip label="SESSION TIME" value={fmtTime(sessionTime)} color="var(--text-secondary)" />
        
        {isTestRunning ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, minWidth: 100 }}>
             <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.05em", color: "var(--blue-color)", textTransform: "uppercase" }}>
               TEST PROGRESS ({Math.round(testStatus.progress_percent)}%)
             </span>
             <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
               <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--border-subtle)", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${testStatus.progress_percent}%`, background: "var(--blue-color)", transition: "width 0.5s linear" }} />
               </div>
               <span style={{ fontSize: 11, fontWeight: 600, color: "var(--blue-color)", fontVariantNumeric: "tabular-nums" }}>
                 {fmtTime(testStatus.remaining_seconds)}
               </span>
             </div>
          </div>
        ) : (
          <InfoChip label="TOTAL BEATS"  value={String(totalBeats || 0)} color="var(--blue-color)" />
        )}
        
        <InfoChip label="ALERTS"       value={String(statistics?.alert_count || 0)}
          color={(statistics?.alert_count || 0) > 0 ? "var(--red-color)" : "var(--text-secondary)"} />
        <InfoChip
          label="ARDUINO"
          value={hardwareUnavailable ? "UNAVAILABLE" : (sensorStatus?.arduino_stream_stale ? "STALE" : "READY")}
          color={hardwareUnavailable || sensorStatus?.arduino_stream_stale ? "var(--amber-color)" : "var(--emerald-color)"}
        />
        <InfoChip label="SERVER" value={piServerLabel} color="var(--text-secondary)" />
      </div>

      {/* ── Vitals row ──────────────────────────────────────────────────── */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <MetricCard label="Heart Rate" value={hr} unit="BPM" color="var(--red-color)" icon={<Heart size={16}/>} sub={hr === '--' ? 'Source unavailable' : bpmSourceLabel} />
        <MetricCard label="SpO2" value={spo2} unit="%" color="var(--blue-color)" icon={<Droplets size={16}/>} />
        <MetricCard label="CO2 Delta" value={co2} unit="ppm" color="var(--purple-color)" icon={<Wind size={16}/>} sub="Exhaled - ambient" />
        <MetricCard label="Resp Rate" value={respiratoryRate} unit="br/min" color="var(--blue-color)" icon={<Wind size={16}/>} sub={respiratoryRateSource} />
        <MetricCard label="O2 Pulse" value={oxygenPulse} unit="ml/beat" color="var(--red-color)" icon={<Heart size={16}/>} sub="Surrogate" />
        <MetricCard label="PTT" value={ptt} unit="ms" color="var(--amber-color)" icon={<Zap size={16}/>} sub={pttHint} />
        <MetricCard label="LRC Index" value={lrc} unit="" color="var(--emerald-color)" icon={<Activity size={16}/>} sub={lrcHint} />
        <MetricCard label="VE/VCO2" value={veVco2} unit="" color="var(--cyan-color)" icon={<Activity size={16}/>} sub="Raw-sensor surrogate" />
        <MetricCard label="Resp (MPU)" value={mpuRespDisplay} unit="br/min" color="var(--blue-color)" icon={<Wind size={16}/>} sub={motionQuality ? `Quality: ${motionQuality}` : 'Chest motion'} />
        <MetricCard label="Motion" value={motionDisplay} unit="" color={motionColor} icon={<Activity size={16}/>} sub="Artifact context" />
      </div>

      {/* Parameter meaning guide */}
      <div style={{
        padding: 18,
        borderRadius: 16,
        border: "1px solid rgba(15,23,42,0.10)",
        background: "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.94))",
        boxShadow: "0 18px 44px rgba(15,23,42,0.06)",
      }}>
        <div style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 14,
        }}>
          <div>
            <div style={{
              fontSize: 12,
              fontWeight: 900,
              color: "var(--text-primary)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}>
              Measured Parameters Guide
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.55 }}>
              Short definitions for every value shown by SmartCPET. Surrogate labels mean the project estimates a trend from available sensors, not a direct clinical measurement.
            </div>
          </div>
          <div style={{
            padding: "6px 10px",
            borderRadius: 999,
            background: "rgba(37,99,235,0.10)",
            border: "1px solid rgba(37,99,235,0.18)",
            color: "var(--blue-color)",
            fontSize: 10,
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}>
            Dashboard glossary
          </div>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
        }}>
          {measuredParameters.map((item) => (
            <ParameterGuideCard key={item.label} {...item} />
          ))}
        </div>
      </div>

      {/* ── ECG + classification grid ────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}
        className="dash-grid">

        {/* ECG Waveform */}
        <div style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: 12, padding: 16,
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.05em",
              color: "var(--text-secondary)", textTransform: "uppercase" }}>
              Lead II · Real-time ECG
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {isConnected && isEcgConnectedEffective && (
                <>
                  <div style={{
                    width: 7, height: 7, borderRadius: "50%",
                    background: "var(--color-primary)", boxShadow: "0 0 6px var(--color-primary)",
                  }} />
                  <span style={{ fontSize: 10, color: "var(--color-primary)", fontWeight: 600 }}>25mm/sec</span>
                </>
              )}
            </div>
          </div>
          <EcgChart
            data={ecgPoints}
            height={200}
            connected={isConnected}
            ecgConnectedEffective={isEcgConnectedEffective}
            ecgReason={sensorStatus?.ecg_reason}
          />
        </div>

        {/* Arrhythmia classification */}
        <div style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: 12, padding: 16,
          display: "flex", flexDirection: "column", gap: 16,
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.05em",
            color: "var(--text-secondary)", textTransform: "uppercase" }}>
            {testResult ? "Screening Result" : "Arrhythmia CNN"}
          </div>

          {testResultPanel ? testResultPanel : isTestRunning ? (
            /* Test Running Status */
            <div style={{
              flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              gap: 12, padding: "20px 0"
            }}>
              <div style={{ animation: "spin 2s linear infinite" }}>
                 <Loader2 size={32} color="var(--blue-color)" />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Recording ECG…</div>
              <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{Math.round(testStatus.progress_percent)}% · {testStatus.samples_collected} samples</div>
            </div>
          ) : (
            <>
              {/* Latest prediction (Standard Live Monitor) */}
              {displayPrediction ? (
                <div style={{
                  padding: "12px 14px", borderRadius: 10,
                  border: "1px solid var(--border-accent)",
                  background: "var(--accent-soft)",
                }}>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>Latest live classification</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
                    {displayPrediction.class_name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
                    Confidence: {toConfidencePercent(displayPrediction.confidence).toFixed(1)}%
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: "var(--text-secondary)", textAlign: "center", padding: "12px 0" }}>
                  {isConnected && !predictionLive ? "Prediction paused until ECG/electrodes are available" : isConnected ? "Awaiting classification..." : "Connect to Pi to classify"}
                </div>
              )}

              {/* Class distribution */}
              {statistics && totalBeats > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {Object.entries(ARRHYTHMIA_CLASSES).map(([key, cls]) => {
                    const count = getClassCount(cls.name)
                    return (
                      <ClassBar key={key}
                        name={cls.name} count={count}
                        total={totalBeats} color={cls.color} />
                    )
                  })}
                </div>
              )}
            </>
          )}


          <Link href="/ecg-monitor" style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            padding: "10px", borderRadius: 8, textDecoration: "none",
            border: "1px solid var(--border-accent)",
            background: "var(--accent-soft)",
            color: "var(--color-primary)", fontSize: 12, fontWeight: 600,
            marginTop: "auto",
          }}>
            {testResult ? "Return to Monitor" : "Full ECG Monitor"} <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {/* ── Quick nav cards ──────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))", gap: 12 }}>
        <NavCard href="/ecg-monitor" icon={<Heart size={18}/>} color="var(--red-color)"
          title="ECG Monitor" desc="Full real-time waveform & arrhythmia detection" />
        <NavCard href="/analysis" icon={<BarChart2 size={18}/>} color="var(--blue-color)"
          title="Analytics" desc="Exercise performance & gas exchange analysis" />
        <NavCard href="/patients" icon={<Activity size={18}/>} color="var(--emerald-color)"
          title="Patients" desc="Session history & patient records" />
      </div>

      <style>{`
        @media (max-width: 768px) {
          .dash-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function pillBtn(color: string) {
  return {
    padding: "6px 12px", borderRadius: 16, fontSize: 11, fontWeight: 500,
    border: `1px solid ${color}30`, background: `transparent`,
    color, cursor: "pointer",
  } as React.CSSProperties
}

function InfoChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.05em", color: "var(--text-secondary)",
        textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color }}>{value}</span>
    </div>
  )
}

function NavCard({ href, icon, color, title, desc }: {
  href: string; icon: React.ReactNode; color: string; title: string; desc: string
}) {
  return (
    <Link href={href} style={{
      display: "flex", flexDirection: "column", gap: 10, padding: "16px 18px",
      borderRadius: 12, textDecoration: "none",
      border: `1px solid var(--border-subtle)`,
      background: `var(--bg-card)`,
      transition: "all 0.2s",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: `${color}10`, border: `1px solid ${color}20`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color,
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>{title}</div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>{desc}</div>
      </div>
    </Link>
  )
}
