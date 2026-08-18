'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import { ECGRawData, ServerStatus, ECGStatistics, ECGMode, SensorStatusPayload, TestStatus, TestResult, MPU6050Data } from '@/types'
import { ECG_SERVER_CONFIG } from './ecg-config'

// ECG chart point (from ecg_raw, high frequency)
export interface ECGChartPoint {
  t: number
  v: number
}

export type BpmSource = 'ecg' | 'max30102' | 'unknown'

export interface CnnResultPayload {
  predicted_class: number
  class_name: string
  confidence: number
  is_critical: boolean
  timestamp?: number | string
}

export interface CpetParametersPayload {
  lrc_ratio?: number | null
  lrc_index?: number | null
  lrc_status?: string
  oxygen_pulse?: number | null
  o2_pulse_surrogate?: number | null
  o2_pulse_surrogate_status?: string | null
  ve_vco2_slope?: number | null
  ve_vco2_slope_surrogate?: number | null
  ventilatory_efficiency_status?: string | null
  co2_delta?: number | null
  net_co2?: number | null
  ptt_ms?: number | null
  ptt_available?: boolean
  ptt_status?: string
  heart_rate_bpm?: number | null
  heart_rate_source?: BpmSource | string
  respiratory_rate_bpm?: number | null
  respiratory_rate_source?: string | null
  respiratory_rate_mpu_bpm?: number | null
  respiratory_motion_quality?: string | null
  motion_state?: string | null
  respiratory_motion?: MPU6050Data | null
  respiratory_rate_mpu?: number | null
  motion_quality?: string | null
  avg_acc_magnitude?: number | null
  avg_gyro_magnitude?: number | null
  avg_acc_magnitude_g?: number | null
  avg_gyro_magnitude_dps?: number | null
  derived_metrics?: Record<string, unknown>
  data_quality?: 'excellent' | 'good' | 'fair' | 'poor' | string
}

// Unified 1Hz payload from Pi for main vitals cards
export interface ProcessedSlow1Hz {
  timestamp: number
  bpm?: number | null
  bpm_source?: BpmSource | string
  hr?: number | null // backward compatibility
  spo2?: number | null
  co2_amb?: number | null
  co2_exh?: number | null
  co2_delta?: number | null
  net_co2?: number | null
  flow?: number | null
  respiratory_motion?: MPU6050Data | null
  mpu6050?: MPU6050Data | null
  cnn_result?: CnnResultPayload
  cpet_parameters?: CpetParametersPayload | null
  sensor_status?: Partial<SensorStatusPayload> | null
}

export interface CPETAlert {
  type: string
  timestamp: number
}

export interface PatientIdentity {
  patient_id: string
  patient_name: string
}

interface UseECGSocketReturn {
  isConnected: boolean
  connectionError: string | null

  // Connection/sensor state store
  sensorStatus: SensorStatusPayload | null
  ecgMode: ECGMode
  isEcgConnectedEffective: boolean
  isVitalsStale: boolean
  setEcgMode: (mode: ECGMode) => void
  setPatientIdentity: (patientId: string, patientName: string) => void
  setPatientId: (patientId: string, patientName?: string) => void
  acceptedPatientId: string | null
  acceptedPatientName: string | null
  acceptedPatientIdentity: PatientIdentity | null
  patientIdentityError: string | null

  // Waveform store
  ecgPoints: ECGChartPoint[]

  // Vitals store
  processedData: ProcessedSlow1Hz | null
  smoothedHR: number | null

  // CPET store
  cpetParameters: CpetParametersPayload | null
  mpuData: MPU6050Data | null

  // AI store
  latestPrediction: CnnResultPayload | null

  // Optional lightweight stores
  maxHeartRate: number | null
  respiratoryRate: number | null

  activeAlert: CPETAlert | null
  dismissAlert: () => void

  // Legacy support
  serverStatus: ServerStatus | null
  statistics: ECGStatistics | null
  ecgData: ECGRawData[]

  clinicalReport: string | null
  requestReport: () => void

  // 2-Minute Screening Test
  testStatus: TestStatus | null
  testResult: TestResult | null
  startTest: (patientId?: string, patientName?: string) => void
  stopTest: () => void
  requestTestStatus: () => void
  clearTestResult: () => void

  requestStatistics: () => void
  requestSensorStatus: () => void
  clearData: () => void
  disconnect: () => void
  reconnect: () => void
}

const MAX_ECG_POINTS = ECG_SERVER_CONFIG.chart.maxDataPoints
const ALERT_TTL_MS = 12_000
const VITALS_STALE_MS = 3_000

function asValidNumber(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null
}

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim().length > 0) {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  return null
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function normalizeConfidenceToUnitInterval(value: unknown): number {
  const n = asFiniteNumber(value)
  if (n === null) return 0
  if (n > 1) return Math.max(0, Math.min(1, n / 100))
  return Math.max(0, Math.min(1, n))
}

function toLowerStatus(value: string | undefined, fallback: string): string {
  return (value || fallback).toLowerCase()
}

function normalizeBpmSource(source: string | undefined): BpmSource {
  if (source === 'ecg' || source === 'max30102') return source
  return 'unknown'
}

function toStatusOrFallback(status: string | undefined, value: number | null | undefined, fallback = 'unavailable'): string {
  if (status && status.length > 0) return status
  return asValidNumber(value) !== null ? 'ok' : fallback
}

function normalizeSensorStatus(payload: Partial<SensorStatusPayload>): SensorStatusPayload {
  const p = asRecord(payload)
  const mode: ECGMode =
    payload.ecg_mode === 'connected' || payload.ecg_mode === 'disconnected'
      ? payload.ecg_mode
      : 'auto'

  const leadOff = Boolean(payload.lead_off)
  const effective = Boolean(payload.ecg_connected_effective) && !leadOff
  const mpu6050 = normalizeMpuData(payload.mpu6050)
  const respiratoryMotion = normalizeMpuData(payload.respiratory_motion) ?? mpu6050

  return {
    ecg_mode: mode,
    ecg_connected_effective: effective,
    ecg_reason: payload.ecg_reason || (leadOff ? 'lead_off' : 'unknown'),
    lead_off: leadOff,
    lo_pos: payload.lo_pos,
    lo_neg: payload.lo_neg,
    bpm: asValidNumber(payload.bpm) ?? null,
    bpm_source: normalizeBpmSource(payload.bpm_source as string | undefined),
    bpm_status: toLowerStatus(payload.bpm_status, 'unknown'),
    spo2_status: toLowerStatus(payload.spo2_status, 'unknown'),
    hr_status: toLowerStatus(payload.hr_status, 'unknown'),
    arduino_connected: typeof payload.arduino_connected === 'boolean' ? payload.arduino_connected : undefined,
    arduino_port: typeof payload.arduino_port === 'string' ? payload.arduino_port : null,
    arduino_connection_status: typeof payload.arduino_connection_status === 'string' ? payload.arduino_connection_status : undefined,
    arduino_status_message: typeof payload.arduino_status_message === 'string' ? payload.arduino_status_message : null,
    arduino_last_error: typeof payload.arduino_last_error === 'string' ? payload.arduino_last_error : null,
    arduino_stream_stale: typeof payload.arduino_stream_stale === 'boolean' ? payload.arduino_stream_stale : undefined,
    arduino_last_data_age_sec: asFiniteNumber(p.arduino_last_data_age_sec),
    prediction_active: typeof payload.prediction_active === 'boolean' ? payload.prediction_active : undefined,
    prediction_status: typeof payload.prediction_status === 'string' ? payload.prediction_status : null,
    mpu6050,
    respiratory_motion: respiratoryMotion,
  }
}

function pickFinite(p: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = asFiniteNumber(p[key])
    if (value !== null) return value
  }
  return null
}

function pickString(p: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = p[key]
    if (typeof value === 'string' && value.trim().length > 0) return value
  }
  return null
}

function normalizeMpuData(payload: unknown): MPU6050Data | null {
  const p = asRecord(payload)
  if (Object.keys(p).length === 0) return null

  const accX = pickFinite(p, 'acc_x', 'ACC_X', 'ax')
  const accY = pickFinite(p, 'acc_y', 'ACC_Y', 'ay')
  const accZ = pickFinite(p, 'acc_z', 'ACC_Z', 'az')
  const gyroX = pickFinite(p, 'gyro_x', 'GYRO_X', 'gx')
  const gyroY = pickFinite(p, 'gyro_y', 'GYRO_Y', 'gy')
  const gyroZ = pickFinite(p, 'gyro_z', 'GYRO_Z', 'gz')
  const respRateMpu = pickFinite(p, 'resp_rate_mpu', 'respiratory_rate_mpu', 'respiratory_rate_mpu_bpm', 'mpu_respiratory_rate')
  const motionState = pickString(p, 'motion_state', 'motion_quality')
  const respSignalQuality = pickString(p, 'resp_signal_quality', 'respiratory_motion_quality', 'signal_quality', 'quality')
  const accMagG = pickFinite(p, 'acc_mag_g', 'avg_acc_magnitude_g')
  const gyroMagDps = pickFinite(p, 'gyro_mag_dps', 'avg_gyro_magnitude_dps')

  const accMagnitude = pickFinite(p, 'acc_magnitude', 'avg_acc_magnitude', 'acc_mag_g', 'avg_acc_magnitude_g') ??
    (accX !== null && accY !== null && accZ !== null ? Math.sqrt(accX ** 2 + accY ** 2 + accZ ** 2) : null)
  const gyroMagnitude = pickFinite(p, 'gyro_magnitude', 'avg_gyro_magnitude', 'gyro_mag_dps', 'avg_gyro_magnitude_dps') ??
    (gyroX !== null && gyroY !== null && gyroZ !== null ? Math.sqrt(gyroX ** 2 + gyroY ** 2 + gyroZ ** 2) : null)

  const hasMpuValue = [
    accX, accY, accZ, gyroX, gyroY, gyroZ, respRateMpu, accMagnitude, gyroMagnitude,
  ].some(value => value !== null) || motionState !== null || respSignalQuality !== null

  if (!hasMpuValue) return null

  return {
    status: pickString(p, 'status'),
    acc_x: accX,
    acc_y: accY,
    acc_z: accZ,
    gyro_x: gyroX,
    gyro_y: gyroY,
    gyro_z: gyroZ,
    resp_rate_mpu: respRateMpu,
    respiratory_rate_mpu_bpm: respRateMpu,
    motion_state: motionState,
    resp_signal_quality: respSignalQuality,
    respiratory_motion_quality: respSignalQuality,
    acc_magnitude: accMagnitude,
    gyro_magnitude: gyroMagnitude,
    acc_mag_g: accMagG,
    gyro_mag_dps: gyroMagDps,
    resp_axis: pickString(p, 'resp_axis'),
    sample_count: pickFinite(p, 'sample_count'),
    sample_rate_hz: pickFinite(p, 'sample_rate_hz'),
    duration_seconds: pickFinite(p, 'duration_seconds'),
    units: asRecord(p.units) as Record<string, string>,
  }
}

function normalizeCpetParameters(payload: CpetParametersPayload | null | undefined): CpetParametersPayload | null {
  if (!payload) return null
  const p = asRecord(payload)
  const derived = asRecord(p.derived_metrics)
  const merged = { ...derived, ...p }

  const lrcValue = pickFinite(merged, 'lrc_ratio', 'lrc_index')
  const o2Pulse = pickFinite(merged, 'o2_pulse_surrogate', 'oxygen_pulse')
  const veVco2 = pickFinite(merged, 've_vco2_slope_surrogate', 've_vco2_slope')
  const co2Delta = pickFinite(merged, 'co2_delta', 'net_co2', 'net_co2_ppm')
  const pttMs = pickFinite(merged, 'ptt_ms')
  const pttAvailable = typeof merged.ptt_available === 'boolean'
    ? merged.ptt_available
    : pttMs !== null
  const pttStatus = typeof merged.ptt_status === 'string'
    ? merged.ptt_status
    : pttAvailable
      ? toStatusOrFallback(undefined, pttMs)
      : 'unavailable_no_ppg_waveform'

  const respiratoryMotion = normalizeMpuData(payload.respiratory_motion) ?? normalizeMpuData({
    resp_rate_mpu: pickFinite(merged, 'respiratory_rate_mpu', 'respiratory_rate_mpu_bpm'),
    motion_state: pickString(merged, 'motion_state', 'motion_quality'),
    resp_signal_quality: pickString(merged, 'respiratory_motion_quality'),
    acc_magnitude: pickFinite(merged, 'avg_acc_magnitude', 'avg_acc_magnitude_g'),
    gyro_magnitude: pickFinite(merged, 'avg_gyro_magnitude', 'avg_gyro_magnitude_dps'),
    acc_mag_g: pickFinite(merged, 'avg_acc_magnitude_g'),
    gyro_mag_dps: pickFinite(merged, 'avg_gyro_magnitude_dps'),
  })

  return {
    ...payload,
    lrc_ratio: lrcValue,
    lrc_index: lrcValue,
    oxygen_pulse: o2Pulse,
    o2_pulse_surrogate: o2Pulse,
    ve_vco2_slope: veVco2,
    ve_vco2_slope_surrogate: veVco2,
    co2_delta: co2Delta,
    net_co2: co2Delta,
    ptt_ms: pttMs,
    ptt_available: pttAvailable,
    ptt_status: pttStatus,
    lrc_status: toStatusOrFallback(payload.lrc_status ?? pickString(merged, 'lrc_status') ?? undefined, lrcValue),
    o2_pulse_surrogate_status: pickString(merged, 'o2_pulse_surrogate_status', 'oxygen_pulse_status'),
    respiratory_rate_bpm: pickFinite(merged, 'respiratory_rate_bpm', 'respiratory_rate'),
    respiratory_rate_source: pickString(merged, 'respiratory_rate_source'),
    ventilatory_efficiency_status: pickString(merged, 'ventilatory_efficiency_status'),
    heart_rate_source: normalizeBpmSource(payload.heart_rate_source as string | undefined),
    respiratory_motion: respiratoryMotion,
  }
}

function isPredictionActive(status: Partial<SensorStatusPayload> | null | undefined): boolean {
  if (!status) return true
  if (status.ecg_connected_effective === false) return false
  if (status.prediction_active === false) return false
  const predictionStatus = status.prediction_status?.toLowerCase()
  if (!predictionStatus) return true
  return !['inactive', 'paused', 'unavailable', 'disabled', 'stale', 'lead_off'].includes(predictionStatus)
}

function extractBpmFromHeartRateEvent(payload: unknown): number | null {
  const p = asRecord(payload)
  return (
    asValidNumber(p.bpm as number | null | undefined) ??
    asValidNumber(p.heart_rate as number | null | undefined) ??
    asValidNumber(p.heart_rate_bpm as number | null | undefined)
  )
}

function extractRespiratoryRate(payload: unknown): number | null {
  const p = asRecord(payload)
  return (
    asValidNumber(p.respiratory_rate_bpm as number | null | undefined) ??
    asValidNumber(p.breaths_per_minute as number | null | undefined) ??
    asValidNumber(p.respiratory_rate as number | null | undefined) ??
    asValidNumber(p.rr as number | null | undefined)
  )
}

function normalizeStatisticsPayload(payload: unknown): ECGStatistics {
  const p = asRecord(payload)
  const classCounts = asRecord(p.class_counts)
  const normalizedClassDistribution = {
    Normal: asFiniteNumber((p.class_distribution as Record<string, unknown>)?.Normal) ?? asFiniteNumber(classCounts['0']) ?? 0,
    Supraventricular: asFiniteNumber((p.class_distribution as Record<string, unknown>)?.Supraventricular) ?? asFiniteNumber(classCounts['1']) ?? 0,
    Ventricular: asFiniteNumber((p.class_distribution as Record<string, unknown>)?.Ventricular) ?? asFiniteNumber(classCounts['2']) ?? 0,
    Fusion: asFiniteNumber((p.class_distribution as Record<string, unknown>)?.Fusion) ?? asFiniteNumber(classCounts['3']) ?? 0,
    Unknown_Paced: asFiniteNumber((p.class_distribution as Record<string, unknown>)?.Unknown_Paced) ?? asFiniteNumber(classCounts['4']) ?? 0,
  }

  const totalFromClasses = Object.values(normalizedClassDistribution).reduce((a, b) => a + b, 0)
  const uptime = asFiniteNumber(p.uptime_seconds) ?? 0
  const predictionsMade = asFiniteNumber(p.predictions_made) ?? totalFromClasses
  const alertCount = asFiniteNumber(p.alert_count) ?? normalizedClassDistribution.Ventricular

  return {
    total_beats: asFiniteNumber(p.total_beats) ?? totalFromClasses,
    predictions_per_second: asFiniteNumber(p.predictions_per_second) ?? (uptime > 0 ? predictionsMade / uptime : 0),
    class_distribution: normalizedClassDistribution,
    class_counts: Object.keys(classCounts).length ? Object.fromEntries(
      Object.entries(classCounts).map(([k, v]) => [k, asFiniteNumber(v) ?? 0])
    ) : undefined,
    total_samples: asFiniteNumber(p.total_samples) ?? undefined,
    predictions_made: predictionsMade,
    uptime_seconds: uptime || undefined,
    alert_count: alertCount,
  }
}

function normalizeTestStatusPayload(payload: unknown): TestStatus {
  const p = asRecord(payload)
  const rawProgress = asFiniteNumber(p.progress_percent) ?? asFiniteNumber(p.progress) ?? 0
  const elapsed = asFiniteNumber(p.elapsed_seconds) ?? 0
  const remaining = asFiniteNumber(p.remaining_seconds) ?? Math.max(0, 120 - elapsed)
  const samples = asFiniteNumber(p.samples_collected) ?? asFiniteNumber(p.ecg_samples_collected) ?? asFiniteNumber(p.ecg_samples) ?? 0
  const status = (p.status as string | undefined) ?? (rawProgress >= 100 ? 'completed' : 'recording')

  return {
    active: Boolean(p.active ?? (status === 'recording' || status === 'processing')),
    success: typeof p.success === 'boolean' ? p.success : undefined,
    status,
    message: typeof p.message === 'string' ? p.message : undefined,
    error: typeof p.error === 'string' ? p.error : null,
    missing_fields: Array.isArray(p.missing_fields) ? p.missing_fields.map(String) : undefined,
    patient_id: typeof p.patient_id === 'string' ? p.patient_id : null,
    patient_name: typeof p.patient_name === 'string' ? p.patient_name : null,
    start_time: asFiniteNumber(p.start_time),
    progress_percent: Math.max(0, Math.min(100, rawProgress)),
    progress: rawProgress,
    samples_collected: samples,
    ecg_samples_collected: asFiniteNumber(p.ecg_samples_collected) ?? undefined,
    target_samples: asFiniteNumber(p.target_samples) ?? undefined,
    elapsed_seconds: elapsed,
    remaining_seconds: remaining,
  }
}

function normalizeTestResultPayload(payload: unknown): TestResult {
  const p = asRecord(payload)
  const rawTimestamp = p.timestamp
  const isoTimestamp =
    typeof rawTimestamp === 'string'
      ? rawTimestamp
      : typeof rawTimestamp === 'number'
        ? new Date(rawTimestamp * 1000).toISOString()
        : new Date().toISOString()

  const rawArrhythmia = asRecord(p.arrhythmia)
  const rawClassDistribution = rawArrhythmia.class_distribution
  const normalizedClassDistribution =
    Array.isArray(rawClassDistribution)
      ? Object.fromEntries(rawClassDistribution.map((value, index) => [String(index), asFiniteNumber(value) ?? 0]))
      : (rawClassDistribution as Record<string, number> | undefined) ?? {}

  const totalSamples =
    asFiniteNumber(p.total_samples) ??
    asFiniteNumber((p.ecg_waveform as Record<string, unknown> | undefined)?.original_sample_count) ??
    0

  const durationSeconds = asFiniteNumber(p.test_duration_seconds) ?? asFiniteNumber(p.duration_seconds) ?? 0
  const rawParameters = asRecord(p.parameters)
  const normalizedParameters = Object.keys(rawParameters).length > 0
    ? {
        ...rawParameters,
        lrc_ratio: pickFinite(rawParameters, 'lrc_ratio', 'lrc_index'),
        lrc_index: pickFinite(rawParameters, 'lrc_index', 'lrc_ratio'),
        o2_pulse_surrogate: pickFinite(rawParameters, 'o2_pulse_surrogate', 'oxygen_pulse'),
        co2_delta: pickFinite(rawParameters, 'co2_delta', 'net_co2', 'net_co2_ppm'),
        net_co2: pickFinite(rawParameters, 'net_co2', 'co2_delta', 'net_co2_ppm'),
        ve_vco2_slope_surrogate: pickFinite(rawParameters, 've_vco2_slope_surrogate', 've_vco2_slope'),
        respiratory_rate_source: pickString(rawParameters, 'respiratory_rate_source') ?? 'unknown',
        ptt_available: typeof rawParameters.ptt_available === 'boolean'
          ? rawParameters.ptt_available
          : pickFinite(rawParameters, 'ptt_ms') !== null,
        ptt_status: pickString(rawParameters, 'ptt_status') ?? (pickFinite(rawParameters, 'ptt_ms') !== null ? 'ok' : 'unavailable_no_ppg_waveform'),
      } as TestResult['parameters']
    : null

  return {
    success: p.success === undefined ? true : Boolean(p.success),
    test_id: typeof p.test_id === 'string' ? p.test_id : undefined,
    patient_id: typeof p.patient_id === 'string' ? p.patient_id : undefined,
    patient_name: typeof p.patient_name === 'string' ? p.patient_name : undefined,
    timestamp: isoTimestamp,
    duration_seconds: asFiniteNumber(p.duration_seconds) ?? undefined,
    status: typeof p.status === 'string' ? p.status : undefined,
    test_duration_seconds: durationSeconds,
    total_samples: totalSamples,
    sampling_rate: asFiniteNumber(p.sampling_rate) ?? 360,
    parameters: normalizedParameters ?? {
      heart_rate: null,
      heart_rate_source: 'unknown',
      respiratory_rate: null,
      respiratory_rate_source: 'unknown',
      hrv: { sdnn: null, rmssd: null, lf_hf_ratio: null },
      total_peaks_detected: 0,
      total_rr_intervals: 0,
      co2_ambient_ppm: null,
      co2_exhaled_ppm: null,
      net_co2_ppm: null,
      ve_vco2_slope: null,
      lung_efficiency_status: null,
    },
    ecg_waveform: (p.ecg_waveform as TestResult['ecg_waveform']) ?? {
      data: [],
      duration_seconds: durationSeconds,
      sample_count: 0,
      original_sample_count: totalSamples,
    },
    arrhythmia: {
      total_predictions: asFiniteNumber(rawArrhythmia.total_predictions) ?? 0,
      dominant_class: asFiniteNumber(rawArrhythmia.dominant_class) ?? 0,
      dominant_class_name: String(rawArrhythmia.dominant_class_name ?? 'Unknown'),
      confidence: asFiniteNumber(rawArrhythmia.confidence) ?? 0,
      class_distribution: normalizedClassDistribution,
      class_labels: (rawArrhythmia.class_labels as Record<string, string>) ?? {},
      arrhythmia_detected: Boolean(rawArrhythmia.arrhythmia_detected),
      arrhythmia_type: (rawArrhythmia.arrhythmia_type as string | null) ?? null,
      threshold_used: asFiniteNumber(rawArrhythmia.threshold_used) ?? 0,
    },
    summary: (p.summary as TestResult['summary']) ?? {
      status: 'completed',
      interpretation: 'No summary provided',
    },
    error: (p.error as string | null) ?? null,
  }
}

export function useECGSocket(): UseECGSocketReturn {
  const socketRef = useRef<Socket | null>(null)
  const ecgBufferRef = useRef<ECGRawData[]>([])
  const updateTimerRef = useRef<NodeJS.Timeout | null>(null)
  const alertTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tickRef = useRef<number>(0)
  const ecgConnectedEffectiveRef = useRef<boolean>(true)
  const sensorStatusRef = useRef<SensorStatusPayload | null>(null)
  const lastVitalsTickRef = useRef<number>(0)
  const staleGuardRef = useRef<NodeJS.Timeout | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [sensorStatus, setSensorStatus] = useState<SensorStatusPayload | null>(null)
  const [ecgMode, setEcgModeState] = useState<ECGMode>('auto')
  const [isVitalsStale, setIsVitalsStale] = useState(false)
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null)
  const [statistics, setStatistics] = useState<ECGStatistics | null>(null)
  const [ecgData, setEcgData] = useState<ECGRawData[]>([])
  const [ecgPoints, setEcgPoints] = useState<ECGChartPoint[]>([])
  const [processedData, setProcessedData] = useState<ProcessedSlow1Hz | null>(null)
  const [smoothedHR, setSmoothedHR] = useState<number | null>(null)
  const [cpetParameters, setCpetParameters] = useState<CpetParametersPayload | null>(null)
  const [mpuData, setMpuData] = useState<MPU6050Data | null>(null)
  const [latestPrediction, setLatestPrediction] = useState<CnnResultPayload | null>(null)
  const [maxHeartRate, setMaxHeartRate] = useState<number | null>(null)
  const [respiratoryRate, setRespiratoryRate] = useState<number | null>(null)
  const [activeAlert, setActiveAlert] = useState<CPETAlert | null>(null)
  const [clinicalReport, setClinicalReport] = useState<string | null>(null)
  const [testStatus, setTestStatus]     = useState<TestStatus | null>(null)
  const [testResult, setTestResult]     = useState<TestResult | null>(null)
  const [acceptedPatientId, setAcceptedPatientId] = useState<string | null>(null)
  const [acceptedPatientName, setAcceptedPatientName] = useState<string | null>(null)
  const [patientIdentityError, setPatientIdentityError] = useState<string | null>(null)

  const triggerAlert = useCallback((type: string) => {
    if (alertTimerRef.current) clearTimeout(alertTimerRef.current)
    setActiveAlert({ type, timestamp: Date.now() })
    alertTimerRef.current = setTimeout(() => setActiveAlert(null), ALERT_TTL_MS)
  }, [])

  const dismissAlert = useCallback(() => {
    if (alertTimerRef.current) clearTimeout(alertTimerRef.current)
    setActiveAlert(null)
  }, [])

  const clearData = useCallback(() => {
    setEcgData([])
    setEcgPoints([])
    setProcessedData(null)
    setSmoothedHR(null)
    setCpetParameters(null)
    setMpuData(null)
    setLatestPrediction(null)
    setMaxHeartRate(null)
    setRespiratoryRate(null)
    setIsVitalsStale(false)
    setActiveAlert(null)
    setClinicalReport(null)
  }, [])

  const requestSensorStatus = useCallback(() => {
    if (!socketRef.current?.connected) return
    socketRef.current.emit(ECG_SERVER_CONFIG.events.requestSensorStatus)
  }, [])

  const requestStatistics = useCallback(() => {
    if (!socketRef.current?.connected) return
    socketRef.current.emit(ECG_SERVER_CONFIG.events.requestStats)
    socketRef.current.emit(ECG_SERVER_CONFIG.events.requestStatistics)
  }, [])

  const requestReport = useCallback(() => {
    if (!socketRef.current?.connected) return
    setClinicalReport(null)
    socketRef.current.emit('request_report')
  }, [])

  const setPatientIdentity = useCallback((patientId: string, patientName: string) => {
    const trimmedId = patientId.trim()
    const trimmedName = patientName.trim()
    if (!trimmedId || !trimmedName) {
      setPatientIdentityError('Patient ID and patient name are required before starting a test')
      return
    }
    if (!socketRef.current?.connected) return
    setPatientIdentityError(null)
    socketRef.current.emit(ECG_SERVER_CONFIG.events.setPatientId, {
      patient_id: trimmedId,
      patient_name: trimmedName,
    })
  }, [])

  const setPatientId = useCallback((patientId: string, patientName = '') => {
    setPatientIdentity(patientId, patientName)
  }, [setPatientIdentity])

  const startTest = useCallback((patientId?: string, patientName?: string) => {
    const socket = socketRef.current
    if (!socket?.connected) return
    const trimmedPatientId = patientId?.trim() ?? ''
    const trimmedPatientName = patientName?.trim() ?? ''
    setTestResult(null)
    setTestStatus(null)

    if (trimmedPatientId || trimmedPatientName) {
      if (!trimmedPatientId || !trimmedPatientName) {
        setPatientIdentityError('Patient ID and patient name are required before starting a test')
        triggerAlert('Patient ID and patient name are required before starting a test')
        return
      }

      setPatientIdentityError(null)
      socket.once(ECG_SERVER_CONFIG.events.patientIdSet, () => {
        socket.emit(ECG_SERVER_CONFIG.events.startTest)
      })
      socket.emit(ECG_SERVER_CONFIG.events.setPatientId, {
        patient_id: trimmedPatientId,
        patient_name: trimmedPatientName,
      })
      return
    }

    if (!acceptedPatientId || !acceptedPatientName) {
      setPatientIdentityError('Patient ID and patient name are required before starting a test')
      triggerAlert('Patient ID and patient name are required before starting a test')
      return
    }

    socket.emit(ECG_SERVER_CONFIG.events.startTest)
  }, [acceptedPatientId, acceptedPatientName, triggerAlert])

  const stopTest = useCallback(() => {
    if (!socketRef.current?.connected) return
    socketRef.current.emit(ECG_SERVER_CONFIG.events.stopTest)
  }, [])

  const requestTestStatus = useCallback(() => {
    if (!socketRef.current?.connected) return
    socketRef.current.emit(ECG_SERVER_CONFIG.events.getTestStatus)
    socketRef.current.emit(ECG_SERVER_CONFIG.events.getTestStatusLegacy)
  }, [])

  const clearTestResult = useCallback(() => {
    setTestResult(null)
    setTestStatus(null)
  }, [])

  const setEcgMode = useCallback((mode: ECGMode) => {
    setEcgModeState(mode)

    setSensorStatus(prev => {
      const optimisticEffective =
        mode === 'connected' ? true : mode === 'disconnected' ? false : prev?.ecg_connected_effective ?? ecgConnectedEffectiveRef.current

      ecgConnectedEffectiveRef.current = optimisticEffective

      return {
        ...prev,
        ecg_mode: mode,
        ecg_connected_effective: optimisticEffective,
        lead_off: prev?.lead_off ?? !optimisticEffective,
        ecg_reason: prev?.ecg_reason ?? 'awaiting_sensor_status',
        bpm: prev?.bpm ?? null,
        bpm_source: prev?.bpm_source ?? 'unknown',
        bpm_status: prev?.bpm_status ?? 'unknown',
        spo2_status: prev?.spo2_status ?? 'unknown',
        hr_status: prev?.hr_status ?? 'unknown',
      }
    })

    if (socketRef.current?.connected) {
      socketRef.current.emit(ECG_SERVER_CONFIG.events.setEcgMode, { mode })
      socketRef.current.emit(ECG_SERVER_CONFIG.events.requestSensorStatus)
    }
  }, [])

  const disconnect = useCallback(() => { socketRef.current?.disconnect() }, [])
  const reconnect = useCallback(() => { socketRef.current?.connect() }, [])

  const isEcgConnectedEffective =
    (sensorStatus?.ecg_connected_effective ?? isConnected) &&
    !(sensorStatus?.lead_off ?? false)

  useEffect(() => {
    const socket = io(ECG_SERVER_CONFIG.url, ECG_SERVER_CONFIG.options)
    socketRef.current = socket

    const stopStaleGuard = () => {
      if (staleGuardRef.current) {
        clearInterval(staleGuardRef.current)
        staleGuardRef.current = null
      }
    }

    const startStaleGuard = () => {
      stopStaleGuard()
      staleGuardRef.current = setInterval(() => {
        if (!socket.connected) return
        if (lastVitalsTickRef.current === 0) return
        setIsVitalsStale(Date.now() - lastVitalsTickRef.current > VITALS_STALE_MS)
      }, 1_000)
    }

    socket.on('connect', () => {
      setIsConnected(true)
      setConnectionError(null)
      ecgConnectedEffectiveRef.current = true
      lastVitalsTickRef.current = Date.now()
      setIsVitalsStale(false)
      startStaleGuard()
      socket.emit(ECG_SERVER_CONFIG.events.requestSensorStatus)
      socket.emit(ECG_SERVER_CONFIG.events.requestStats)
      socket.emit(ECG_SERVER_CONFIG.events.requestStatistics)
    })

    socket.on('disconnect', () => {
      setIsConnected(false)
      ecgConnectedEffectiveRef.current = false
      setIsVitalsStale(false)
      stopStaleGuard()
    })

    socket.on('connect_error', (e) => {
      setConnectionError(e.message)
      setIsConnected(false)
      ecgConnectedEffectiveRef.current = false
      setIsVitalsStale(false)
      stopStaleGuard()
    })

    // sensor_status updates connection and badges store only
    socket.on(ECG_SERVER_CONFIG.events.sensorStatus, (payload: Partial<SensorStatusPayload>) => {
      const nextStatus = normalizeSensorStatus(payload)

      sensorStatusRef.current = nextStatus
      setSensorStatus(nextStatus)
      setEcgModeState(nextStatus.ecg_mode)
      ecgConnectedEffectiveRef.current = nextStatus.ecg_connected_effective
      if (nextStatus.respiratory_motion) setMpuData(nextStatus.respiratory_motion)

      if (!nextStatus.ecg_connected_effective) {
        ecgBufferRef.current = []
      }
      if (!isPredictionActive(nextStatus)) {
        setLatestPrediction(null)
      }
    })

    // ecg_raw feeds chart buffers only
    socket.on(ECG_SERVER_CONFIG.events.ecgRaw, (data: ECGRawData) => {
      if (!ecgConnectedEffectiveRef.current) return

      ecgBufferRef.current.push(data)
      if (!updateTimerRef.current) {
        updateTimerRef.current = setInterval(() => {
          if (ecgBufferRef.current.length > 0) {
            const batch = [...ecgBufferRef.current]
            ecgBufferRef.current = []
            setEcgData(prev => {
              const merged = [...prev, ...batch]
              return merged.length > MAX_ECG_POINTS ? merged.slice(-MAX_ECG_POINTS) : merged
            })
          }
        }, ECG_SERVER_CONFIG.chart.updateInterval)
      }

      setEcgPoints(prev => {
        const next = [...prev, { t: tickRef.current++, v: data.value }]
        return next.length > MAX_ECG_POINTS ? next.slice(next.length - MAX_ECG_POINTS) : next
      })
    })

    // processed_slow_1hz updates vitals store only
    socket.on(ECG_SERVER_CONFIG.events.processedSlow1hz, (data: ProcessedSlow1Hz) => {
      const fallbackSensorBpm = asValidNumber(data.sensor_status?.bpm)
      const unifiedBpm = asValidNumber(data.bpm) ?? asValidNumber(data.hr) ?? fallbackSensorBpm
      const source = normalizeBpmSource((data.bpm_source || data.sensor_status?.bpm_source) as string | undefined)
      const normalizedCpet = normalizeCpetParameters(data.cpet_parameters)
      const nestedSensorStatus = data.sensor_status ? normalizeSensorStatus(data.sensor_status) : null
      const normalizedMpu =
        normalizeMpuData(data.respiratory_motion) ??
        normalizeMpuData(data.mpu6050) ??
        normalizeMpuData(data) ??
        normalizedCpet?.respiratory_motion ??
        null

      const normalizedData: ProcessedSlow1Hz = {
        ...data,
        bpm: unifiedBpm,
        bpm_source: source,
        co2_delta: asFiniteNumber(data.co2_delta) ?? asFiniteNumber(data.net_co2) ?? normalizedCpet?.co2_delta ?? null,
        net_co2: asFiniteNumber(data.net_co2) ?? asFiniteNumber(data.co2_delta) ?? normalizedCpet?.net_co2 ?? null,
        respiratory_motion: normalizedMpu,
        cpet_parameters: normalizedCpet,
        sensor_status: nestedSensorStatus,
      }

      setProcessedData(normalizedData)
      setSmoothedHR(unifiedBpm)
      if (normalizedMpu) setMpuData(normalizedMpu)
      if (nestedSensorStatus) {
        sensorStatusRef.current = nestedSensorStatus
        setSensorStatus(nestedSensorStatus)
        setEcgModeState(nestedSensorStatus.ecg_mode)
        ecgConnectedEffectiveRef.current = nestedSensorStatus.ecg_connected_effective
        if (!isPredictionActive(nestedSensorStatus)) {
          setLatestPrediction(null)
        }
      }
      lastVitalsTickRef.current = Date.now()
      setIsVitalsStale(false)

      // Compatibility fallback if prediction event is not present
      if (normalizedData.cnn_result && isPredictionActive(nestedSensorStatus ?? sensorStatusRef.current)) {
        setLatestPrediction({
          ...normalizedData.cnn_result,
          confidence: normalizeConfidenceToUnitInterval(normalizedData.cnn_result.confidence),
        })
      }

      // Compatibility fallback if dedicated CPET event is not present
      if (normalizedData.cpet_parameters) {
        setCpetParameters(normalizedData.cpet_parameters)
      }

      if (data.cnn_result?.is_critical && isPredictionActive(nestedSensorStatus ?? sensorStatusRef.current)) {
        triggerAlert(`Rhythm pattern flagged - ${data.cnn_result.class_name}`)
      }
    })

    // cpet_parameters updates CPET store only
    socket.on(ECG_SERVER_CONFIG.events.cpetParameters, (payload: CpetParametersPayload) => {
      const normalized = normalizeCpetParameters(payload)
      setCpetParameters(normalized)
      if (normalized?.respiratory_motion) setMpuData(normalized.respiratory_motion)
    })

    // prediction updates AI store only
    socket.on(ECG_SERVER_CONFIG.events.prediction, (payload: unknown) => {
      if (!isPredictionActive(sensorStatusRef.current)) return
      const p = asRecord(payload)
      const normalized: CnnResultPayload = {
        predicted_class: Number(p.predicted_class ?? 0),
        class_name: String(p.class_name ?? 'Unknown'),
        confidence: normalizeConfidenceToUnitInterval(p.confidence),
        is_critical: Boolean(p.is_critical ?? p.is_alert ?? false),
        timestamp: typeof p.timestamp === 'number' || typeof p.timestamp === 'string' ? p.timestamp : undefined,
      }

      setLatestPrediction(normalized)

      if (normalized.is_critical) {
        triggerAlert(`Rhythm pattern flagged - ${normalized.class_name}`)
      }
    })

    // Optional lightweight MAX ticker
    socket.on(ECG_SERVER_CONFIG.events.heartRate, (payload: unknown) => {
      const bpm = extractBpmFromHeartRateEvent(payload)
      setMaxHeartRate(bpm)
    })

    // Optional respiration trend store
    socket.on(ECG_SERVER_CONFIG.events.respiratoryRate, (payload: unknown) => {
      setRespiratoryRate(extractRespiratoryRate(payload))
    })

    socket.on(ECG_SERVER_CONFIG.events.alert, (payload: { type: string }) => {
      triggerAlert(payload.type)
    })

    socket.on(ECG_SERVER_CONFIG.events.error, (payload: unknown) => {
      const p = asRecord(payload)
      if (p.status === 'patient_required') {
        const missing = Array.isArray(p.missing_fields) ? p.missing_fields.map(String).join(', ') : 'patient_id, patient_name'
        const message = typeof p.message === 'string'
          ? p.message
          : `Missing patient fields: ${missing}`
        setPatientIdentityError(message)
        triggerAlert(message)
        return
      }
      triggerAlert(String(p.message ?? p.error ?? 'Backend error'))
    })

    socket.on(ECG_SERVER_CONFIG.events.serverStatus, setServerStatus)
    socket.on(ECG_SERVER_CONFIG.events.statistics, (payload: unknown) => {
      setStatistics(normalizeStatisticsPayload(payload))
    })

    socket.on(ECG_SERVER_CONFIG.events.patientIdSet, (payload: unknown) => {
      const p = asRecord(payload)
      if (typeof p.patient_id === 'string') setAcceptedPatientId(p.patient_id)
      if (typeof p.patient_name === 'string') setAcceptedPatientName(p.patient_name)
      if (typeof p.patient_id === 'string' && typeof p.patient_name === 'string') {
        setPatientIdentityError(null)
      }
    })

    socket.on('clinical_report', (data: { report: string }) => {
      setClinicalReport(data.report)
    })

    // ── 2-Minute Screening Test events ──────────────────────────────

    // progress: fires every 5% — update ring/bar only
    socket.on(ECG_SERVER_CONFIG.events.testProgress, (payload: unknown) => {
      setTestStatus(normalizeTestStatusPayload(payload))
    })

    socket.on(ECG_SERVER_CONFIG.events.testStarted, (payload: unknown) => {
      const status = normalizeTestStatusPayload(payload)
      setTestStatus(status)
      if (status.status === 'patient_required') {
        const message = status.message ?? 'Patient ID and patient name are required before starting a test'
        setPatientIdentityError(message)
        triggerAlert(message)
      } else if (status.success === false || status.status === 'hardware_unavailable') {
        triggerAlert(status.message ?? 'Arduino data is unavailable; backend is online in degraded mode')
      }
    })

    socket.on(ECG_SERVER_CONFIG.events.testStopped, (payload: unknown) => {
      const status = normalizeTestStatusPayload(payload)
      setTestStatus({
        ...status,
        active: false,
        status: status.status === 'recording' ? 'completed' : status.status,
      })
    })

    socket.on(ECG_SERVER_CONFIG.events.testStatus, (payload: unknown) => {
      const status = normalizeTestStatusPayload(payload)
      setTestStatus(status)
      if (status.status === 'patient_required') {
        const message = status.message ?? 'Patient ID and patient name are required before starting a test'
        setPatientIdentityError(message)
        triggerAlert(message)
      } else if (status.success === false || status.status === 'hardware_unavailable') {
        triggerAlert(status.message ?? 'Arduino data is unavailable; backend is online in degraded mode')
      }
    })

    // live ECG during test — append chunks into the same ecgPoints buffer
    socket.on(ECG_SERVER_CONFIG.events.testLiveEcg, (payload: { data: number[] }) => {
      if (!Array.isArray(payload?.data)) return
      setEcgPoints(prev => {
        const newPts = payload.data.map(v => ({ t: tickRef.current++, v }))
        const merged = [...prev, ...newPts]
        return merged.length > MAX_ECG_POINTS ? merged.slice(-MAX_ECG_POINTS) : merged
      })
    })

    // test_complete: full result payload
    socket.on(ECG_SERVER_CONFIG.events.testComplete, (payload: unknown) => {
      const normalized = normalizeTestResultPayload(payload)
      setTestResult(normalized)
      setTestStatus(prev => prev
        ? { ...prev, active: false, status: 'completed', progress_percent: 100 }
        : {
            active: false,
            status: 'completed',
            progress_percent: 100,
            progress: 100,
            samples_collected: normalized.total_samples,
            elapsed_seconds: normalized.test_duration_seconds,
            remaining_seconds: 0,
          }
      )
      if (normalized.arrhythmia?.arrhythmia_detected) {
        triggerAlert(`Rhythm pattern flagged - ${normalized.arrhythmia.dominant_class_name}`)
      }
    })

    socket.on(ECG_SERVER_CONFIG.events.testResult, (payload: unknown) => {
      setTestResult(normalizeTestResultPayload(payload))
    })

    if (process.env.NODE_ENV === 'development') {
      socket.onAny((name, ...args) => console.log(`[Pi] "${name}"`, args))
    }

    return () => {
      if (updateTimerRef.current) clearInterval(updateTimerRef.current)
      if (alertTimerRef.current) clearTimeout(alertTimerRef.current)
      if (staleGuardRef.current) clearInterval(staleGuardRef.current)
      socket.disconnect()
    }
  }, [triggerAlert])

  return {
    isConnected,
    connectionError,
    sensorStatus,
    ecgMode,
    isEcgConnectedEffective,
    isVitalsStale,
    setEcgMode,
    setPatientIdentity,
    setPatientId,
    acceptedPatientId,
    acceptedPatientName,
    acceptedPatientIdentity: acceptedPatientId && acceptedPatientName
      ? { patient_id: acceptedPatientId, patient_name: acceptedPatientName }
      : null,
    patientIdentityError,

    ecgPoints,

    processedData,
    smoothedHR,

    cpetParameters,
    mpuData,

    latestPrediction,

    maxHeartRate,
    respiratoryRate,

    activeAlert,
    dismissAlert,

    serverStatus,
    statistics,
    ecgData,

    clinicalReport,
    requestReport,

    testStatus,
    testResult,
    startTest,
    stopTest,
    requestTestStatus,
    clearTestResult,

    requestStatistics,
    requestSensorStatus,
    clearData,
    disconnect,
    reconnect,
  }
}

