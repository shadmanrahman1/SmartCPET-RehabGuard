'use client'

import { Heart, Wind, Droplets, Activity, Zap } from 'lucide-react'
import { CpetParametersPayload, ProcessedSlow1Hz } from '@/lib/useECGSocket'
import { MPU6050Data, SensorStatusPayload } from '@/types'

interface VitalCardProps {
  label:    string
  value:    number | string | null | undefined
  unit:     string
  icon:     React.ReactNode
  status:   'normal' | 'warning' | 'critical' | 'idle'
  decimals?: number
  subtext?: string
}

const STATUS_COLORS = {
  normal:   { border: 'rgba(34,197,94,0.35)',  bg: 'rgba(34,197,94,0.06)',  text: '#22c55e', glow: 'rgba(34,197,94,0.2)'  },
  warning:  { border: 'rgba(245,158,11,0.35)', bg: 'rgba(245,158,11,0.06)', text: '#f59e0b', glow: 'rgba(245,158,11,0.2)' },
  critical: { border: 'rgba(239,68,68,0.45)',  bg: 'rgba(239,68,68,0.08)',  text: '#ef4444', glow: 'rgba(239,68,68,0.25)' },
  idle:     { border: 'rgba(71,85,105,0.4)',   bg: 'rgba(71,85,105,0.05)',  text: '#64748b', glow: 'transparent'          },
} as const

function VitalCard({ label, value, unit, icon, status, decimals = 0, subtext }: VitalCardProps) {
  const c = STATUS_COLORS[status]
  const display = typeof value === 'number'
    ? value.toFixed(decimals)
    : value != null
      ? value
      : '--'

  return (
    <div style={{
      flex: '1 1 140px',
      minWidth: 120,
      padding: '16px 18px',
      borderRadius: 12,
      border: `1px solid ${c.border}`,
      background: c.bg,
      boxShadow: `0 0 16px ${c.glow}`,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      transition: 'all 0.3s ease',
    }}>
      {/* Icon + label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ color: c.text, opacity: 0.8 }}>{icon}</div>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
          color: '#64748b', textTransform: 'uppercase' }}>
          {label}
        </span>
      </div>

      {/* Value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{
          fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em',
          color: c.text, fontVariantNumeric: 'tabular-nums',
          transition: 'color 0.3s',
        }}>
          {display}
        </span>
        {unit && (
          <span style={{ fontSize: 12, color: '#475569', fontWeight: 500 }}>
            {unit}
          </span>
        )}
      </div>

      {/* Status dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: c.text,
          boxShadow: status !== 'idle' ? `0 0 6px ${c.text}` : 'none',
        }} />
        <span style={{ fontSize: 10, color: '#475569', textTransform: 'capitalize' }}>
          {status === 'idle' ? 'no signal' : status}
        </span>
      </div>

      {subtext && (
        <div style={{ fontSize: 10, color: '#94a3b8' }}>
          {subtext}
        </div>
      )}
    </div>
  )
}

// ─── Status classifiers ──────────────────────────────────────────────────────

function hrStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v < 50 || v > 120) return 'critical'
  if (v < 60 || v > 100) return 'warning'
  return 'normal'
}

function spo2Status(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v < 90) return 'critical'
  if (v < 95) return 'warning'
  return 'normal'
}

function co2DeltaStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v <= 0) return 'warning'
  return 'normal'
}

function pttStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  return 'normal'
}

function lrcStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  return 'normal'
}

function respiratoryRateStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v < 8 || v > 30) return 'critical'
  if (v < 12 || v > 22) return 'warning'
  return 'normal'
}

function o2PulseStatus(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v < 8) return 'warning'
  return 'normal'
}

function veVco2Status(v: number | null): VitalCardProps['status'] {
  if (v == null) return 'idle'
  if (v > 35) return 'warning'
  return 'normal'
}

function mpuRespStatus(v: number | null, quality: string | null | undefined): VitalCardProps['status'] {
  const normalizedQuality = quality?.toLowerCase()
  if (normalizedQuality === 'no_data' || normalizedQuality === 'warming_up') return 'idle'
  if (normalizedQuality === 'motion_artifact' || normalizedQuality === 'poor') return 'warning'
  if (normalizedQuality === 'flat_signal' || normalizedQuality === 'insufficient_peaks' || normalizedQuality === 'out_of_range') return 'warning'
  if (v == null) return 'idle'
  if (v < 8 || v > 30) return 'critical'
  if (v < 12 || v > 22) return 'warning'
  return 'normal'
}

function motionStatus(state: string | null | undefined): VitalCardProps['status'] {
  const normalized = state?.toLowerCase()
  if (!normalized || normalized === 'no_data') return 'idle'
  if (normalized === 'high' || normalized === 'severe') return 'critical'
  if (normalized === 'moderate' || normalized === 'medium') return 'warning'
  return 'normal'
}

function formatMotionState(state: string | null | undefined): string {
  if (!state) return '--'
  return state.replace(/_/g, ' ').toUpperCase()
}

function normalizeSourceLabel(source: string | null | undefined): string {
  if (source === 'ecg') return 'Source: ECG'
  if (source === 'max30102') return 'Source: Finger Sensor'
  if (source === 'ecg_derived') return 'Source: ECG-derived'
  if (source === 'mpu6050') return 'Source: MPU6050'
  if (source === 'unavailable') return 'Source unavailable'
  return 'Source: Auto'
}

function formatUnavailableStatus(status: string | null | undefined, fallback: string): string | undefined {
  if (!status || status === 'ok') return undefined
  if (status === 'unavailable_no_ppg_waveform') return 'N/A - Requires finger sensor waveform'
  if (status === 'unavailable_rr') return 'N/A - Requires ECG respiratory rate'
  return `N/A - ${fallback}: ${status.replace(/_/g, ' ')}`
}

// ─── Component ───────────────────────────────────────────────────────────────

interface VitalsPanelProps {
  data: ProcessedSlow1Hz | null
  sensorStatus: SensorStatusPayload | null
  cpetParameters?: CpetParametersPayload | null
  mpuData?: MPU6050Data | null
  isVitalsStale?: boolean
}

export function VitalsPanel({ data, sensorStatus, cpetParameters, mpuData, isVitalsStale = false }: VitalsPanelProps) {
  const hrAvailable = sensorStatus ? ((sensorStatus.bpm_status ?? sensorStatus.hr_status) === 'ok') : true
  const spo2Available = sensorStatus ? sensorStatus.spo2_status === 'ok' : true

  // Canonical BPM: processed_slow_1hz first, then sensor_status fallback
  const unifiedBpm = typeof data?.bpm === 'number' && data.bpm > 0
    ? data.bpm
    : typeof data?.hr === 'number' && data.hr > 0
      ? data.hr
      : typeof sensorStatus?.bpm === 'number' && sensorStatus.bpm > 0
        ? sensorStatus.bpm
        : null

  const bpmSource = data?.bpm_source ?? sensorStatus?.bpm_source

  const hr   = hrAvailable ? unifiedBpm : null
  const spo2 = spo2Available ? (data?.spo2 ?? null) : null

  const cpet = cpetParameters ?? data?.cpet_parameters ?? null

  const pttUnavailable = cpet?.ptt_available === false
    ? 'N/A - PTT not available without PPG waveform timing'
    : formatUnavailableStatus(cpet?.ptt_status, 'PTT')
  const lrcUnavailable = formatUnavailableStatus(cpet?.lrc_status, 'LRC')

  const ptt  = pttUnavailable ? null : (cpet?.ptt_ms ?? null)
  const lrc  = lrcUnavailable ? null : (cpet?.lrc_ratio ?? cpet?.lrc_index ?? null)
  const respiratoryRate = cpet?.respiratory_rate_bpm ?? null
  const respiratoryRateSource = cpet?.respiratory_rate_source ?? null
  const oxygenPulse = cpet?.o2_pulse_surrogate ?? cpet?.oxygen_pulse ?? null
  const co2Delta = cpet?.co2_delta ?? cpet?.net_co2 ?? data?.co2_delta ?? data?.net_co2 ?? null
  const veVco2 = cpet?.ve_vco2_slope_surrogate ?? cpet?.ve_vco2_slope ?? null
  const respiratoryMotion =
    mpuData ??
    data?.respiratory_motion ??
    cpet?.respiratory_motion ??
    sensorStatus?.respiratory_motion ??
    sensorStatus?.mpu6050 ??
    null
  const mpuResp = respiratoryMotion?.resp_rate_mpu ?? null
  const motionState = respiratoryMotion?.motion_state ?? null
  const motionQuality = respiratoryMotion?.resp_signal_quality ?? null

  return (
    <div>
      <div style={{
        fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
        color: '#475569', textTransform: 'uppercase', marginBottom: 12,
      }}>
        Live Vitals
      </div>

      {isVitalsStale && (
        <div style={{
          marginBottom: 10,
          fontSize: 11,
          color: '#f59e0b',
        }}>
          Vitals stream stale. Reconnecting to 1Hz feed...
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <VitalCard
          label="Heart Rate" value={hr} unit="BPM"
          icon={<Heart size={14} />}
          status={hrStatus(hr)}
          subtext={
            hr !== null
              ? `${normalizeSourceLabel(bpmSource)}${isVitalsStale ? ' - stale' : ''}`
              : (isVitalsStale ? 'Vitals stream stale' : 'Source unavailable')
          }
        />
        <VitalCard
          label="SpO2" value={spo2} unit="%" decimals={1}
          icon={<Droplets size={14} />}
          status={spo2Status(spo2)}
        />
        <VitalCard
          label="CO2 Delta" value={co2Delta} unit="ppm" decimals={1}
          icon={<Wind size={14} />}
          status={co2DeltaStatus(co2Delta)}
          subtext="Exhaled minus ambient"
        />
        <VitalCard
          label="Resp Rate" value={respiratoryRate} unit="br/min" decimals={1}
          icon={<Wind size={14} />}
          status={respiratoryRateStatus(respiratoryRate)}
          subtext={normalizeSourceLabel(respiratoryRateSource)}
        />
        <VitalCard
          label="O2 Pulse" value={oxygenPulse} unit="ml/beat" decimals={2}
          icon={<Heart size={14} />}
          status={o2PulseStatus(oxygenPulse)}
          subtext="Project surrogate"
        />
        <VitalCard
          label="PTT" value={ptt} unit="ms" decimals={1}
          icon={<Zap size={14} />}
          status={pttStatus(ptt)}
          subtext={pttUnavailable}
        />
        <VitalCard
          label="LRC Index" value={lrc} unit="" decimals={3}
          icon={<Activity size={14} />}
          status={lrcStatus(lrc)}
          subtext={lrcUnavailable}
        />
        <VitalCard
          label="VE/VCO2" value={veVco2} unit="" decimals={2}
          icon={<Activity size={14} />}
          status={veVco2Status(veVco2)}
          subtext="Raw-sensor surrogate"
        />
        <VitalCard
          label="Resp (MPU)" value={mpuResp} unit="br/min" decimals={1}
          icon={<Wind size={14} />}
          status={mpuRespStatus(mpuResp, motionQuality)}
          subtext={motionQuality ? `Quality: ${motionQuality}` : 'Chest motion sensor'}
        />
        <VitalCard
          label="Motion" value={formatMotionState(motionState)} unit=""
          icon={<Activity size={14} />}
          status={motionStatus(motionState)}
          subtext={
            respiratoryMotion?.gyro_mag_dps != null
              ? `Gyro: ${respiratoryMotion.gyro_mag_dps.toFixed(2)} dps`
              : respiratoryMotion?.gyro_magnitude != null
                ? `Gyro magnitude: ${respiratoryMotion.gyro_magnitude.toFixed(1)}`
                : 'Artifact context'
          }
        />
      </div>
    </div>
  )
}
