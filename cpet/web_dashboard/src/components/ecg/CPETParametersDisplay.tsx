'use client'

interface CpetParameters {
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
  respiratory_rate_bpm?: number | null
  respiratory_rate_source?: string | null
  ptt_ms?: number | null
  ptt_available?: boolean
  ptt_status?: string
}

interface CPETParametersDisplayProps {
  parameters: CpetParameters | null
  className?: string
}

interface ParameterCardProps {
  label: string
  value: number | null
  unit: string
  description: string
  normalRange: string
  icon: string
  warningThreshold?: { min?: number; max?: number }
  unavailableReason?: string
}

function statusToMessage(status: string | undefined, fallback: string): string | undefined {
  if (!status || status === 'ok') return undefined
  if (status === 'unavailable_no_ppg_waveform') return 'Requires finger sensor waveform'
  if (status === 'unavailable_rr') return 'Requires ECG-derived respiratory rate'
  return `${fallback}: ${status.replace(/_/g, ' ')}`
}

function sourceToLabel(source: string | null | undefined): string {
  if (source === 'ecg_derived') return 'ECG-derived respiration'
  if (source === 'mpu6050') return 'MPU6050 chest motion'
  if (source === 'unavailable') return 'Source unavailable'
  return source ? source.replace(/_/g, ' ') : 'Backend selected source'
}

function ParameterCard({
  label,
  value,
  unit,
  description,
  normalRange,
  icon,
  warningThreshold,
  unavailableReason,
}: ParameterCardProps) {
  const unavailable = Boolean(unavailableReason || value === null)
  const color = (() => {
    if (unavailableReason || value === null) return '#334155'
    if (warningThreshold?.min !== undefined && value < warningThreshold.min) return 'var(--amber-color)'
    if (warningThreshold?.max !== undefined && value > warningThreshold.max) return 'var(--red-color)'
    return 'var(--emerald-color)'
  })()
  const iconBackground = unavailable
    ? 'rgba(245,158,11,0.14)'
    : color === 'var(--red-color)'
      ? 'rgba(220,38,38,0.12)'
      : color === 'var(--amber-color)'
        ? 'rgba(217,119,6,0.12)'
        : 'rgba(5,150,105,0.12)'

  return (
    <div style={{
      padding: 16,
      borderRadius: 16,
      border: unavailable
        ? '1px solid rgba(245,158,11,0.34)'
        : '1px solid rgba(15,23,42,0.10)',
      borderLeft: `5px solid ${unavailable ? '#f59e0b' : color}`,
      background: unavailable
        ? 'linear-gradient(180deg, #fffdf7 0%, #fff7ed 100%)'
        : 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
      boxShadow: '0 12px 30px rgba(15,23,42,0.07)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          width: 34,
          height: 34,
          borderRadius: 12,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: iconBackground,
          color: unavailable ? '#b45309' : color,
          fontSize: 12,
          fontWeight: 900,
          letterSpacing: '0.03em',
        }}>
          {icon}
        </span>
        <div>
          <div style={{
            fontSize: 12,
            fontWeight: 850,
            color: '#334155',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}>
            {label}
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, fontWeight: 600 }}>
            {description}
          </div>
        </div>
      </div>

      <div style={{
        marginTop: 14,
        display: 'flex',
        alignItems: 'baseline',
        gap: 4,
      }}>
        <span style={{
          fontSize: 30,
          fontWeight: 900,
          color,
          letterSpacing: '-0.04em',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {unavailableReason ? 'N/A' : value !== null ? value.toFixed(2) : '--'}
        </span>
        <span style={{ fontSize: 12, color: '#475569', fontWeight: 800 }}>
          {unit}
        </span>
      </div>

      {unavailableReason && (
        <div style={{
          display: 'inline-flex',
          marginTop: 7,
          padding: '5px 8px',
          borderRadius: 999,
          background: 'rgba(245,158,11,0.12)',
          color: '#92400e',
          fontSize: 11,
          fontWeight: 800,
        }}>
          {unavailableReason}
        </div>
      )}

      <div style={{ marginTop: 8, fontSize: 11, color: '#64748b', fontWeight: 700 }}>
        Normal: <span style={{ color: '#334155', fontWeight: 850 }}>{normalRange}</span>
      </div>
    </div>
  )
}

export function CPETParametersDisplay({
  parameters,
  className = '',
}: CPETParametersDisplayProps) {
  if (!parameters) {
    return (
      <div className={className}>
        <h2 style={headingStyle}>CPET Robust Parameters</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{
              height: 120,
              borderRadius: 14,
              border: '1px solid rgba(15,23,42,0.08)',
              background: 'rgba(248,250,252,0.85)',
            }} />
          ))}
        </div>
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: 13, marginTop: 16 }}>
          Waiting for CPET parameter data from Raspberry Pi...
        </p>
      </div>
    )
  }

  const lrcUnavailable = statusToMessage(parameters.lrc_status, 'LRC')
  const pttUnavailable = parameters.ptt_available === false
    ? 'PTT unavailable: PPG waveform timing is not available'
    : statusToMessage(parameters.ptt_status, 'PTT')
  const lrcValue = lrcUnavailable ? null : (parameters.lrc_ratio ?? parameters.lrc_index ?? null)
  const pttValue = pttUnavailable ? null : (parameters.ptt_ms ?? null)
  const oxygenPulseValue = parameters.o2_pulse_surrogate ?? parameters.oxygen_pulse ?? null
  const respiratoryRateValue = parameters.respiratory_rate_bpm ?? null
  const co2DeltaValue = parameters.co2_delta ?? parameters.net_co2 ?? null
  const veVco2Value = parameters.ve_vco2_slope_surrogate ?? parameters.ve_vco2_slope ?? null

  return (
    <div className={className}>
      <h2 style={headingStyle}>CPET Robust Parameters</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <ParameterCard
          icon="LR"
          label="LRC Ratio"
          value={lrcValue}
          unit="ratio"
          description="Breathing Rate / Heart Rate"
          normalRange="0.20 - 0.30"
          warningThreshold={{ min: 0.15, max: 0.35 }}
          unavailableReason={lrcUnavailable}
        />
        <ParameterCard
          icon="O2"
          label="O2 Pulse Surrogate"
          value={oxygenPulseValue}
          unit="ml/beat"
          description="Project stroke-volume proxy"
          normalRange="10 - 20"
          warningThreshold={{ min: 8 }}
          unavailableReason={statusToMessage(parameters.o2_pulse_surrogate_status ?? undefined, 'O2 pulse')}
        />
        <ParameterCard
          icon="RR"
          label="Respiratory Rate"
          value={respiratoryRateValue}
          unit="br/min"
          description={sourceToLabel(parameters.respiratory_rate_source)}
          normalRange="12 - 22"
          warningThreshold={{ min: 8, max: 30 }}
        />
        <ParameterCard
          icon="CO"
          label="CO2 Delta"
          value={co2DeltaValue}
          unit="ppm"
          description="Exhaled minus ambient"
          normalRange="> 0"
          warningThreshold={{ min: 0.01 }}
        />
        <ParameterCard
          icon="PT"
          label="PTT"
          value={pttValue}
          unit="ms"
          description="ECG to PPG delay"
          normalRange="200 - 350"
          warningThreshold={{ min: 150, max: 400 }}
          unavailableReason={pttUnavailable}
        />
        <ParameterCard
          icon="VE"
          label="VE/VCO2 Surrogate"
          value={veVco2Value}
          unit="L/L"
          description="Raw-sensor project surrogate"
          normalRange="20 - 30"
          warningThreshold={{ max: 35 }}
        />
      </div>

      <div style={{
        marginTop: 16,
        padding: 16,
        borderRadius: 16,
        border: '1px solid rgba(37,99,235,0.20)',
        background: 'linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%)',
        boxShadow: '0 12px 30px rgba(15,23,42,0.06)',
      }}>
        <h3 style={{
          margin: 0,
          marginBottom: 8,
          fontSize: 12,
          fontWeight: 850,
          color: 'var(--blue-color)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}>
          Screening Interpretation
        </h3>
        <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.65 }}>
          {lrcValue !== null && lrcValue > 0.35 && <p>Elevated LRC Ratio may indicate respiratory stress.</p>}
          {oxygenPulseValue !== null && oxygenPulseValue < 8 && <p>Low oxygen pulse surrogate may require review.</p>}
          {veVco2Value !== null && veVco2Value > 35 && <p>Steep VE/VCO2 slope may indicate cardiopulmonary limitation.</p>}
          {pttUnavailable && <p>PTT unavailable: finger waveform/PPG peak timing is required.</p>}
          {lrcUnavailable && <p>LRC unavailable: backend needs a respiratory-rate source for this calculation.</p>}
          {!pttUnavailable && !lrcUnavailable && veVco2Value !== null && veVco2Value <= 35 && (
            <p>Available CPET parameters are within expected screening limits.</p>
          )}
        </div>
      </div>
    </div>
  )
}

const headingStyle: React.CSSProperties = {
  margin: '0 0 16px',
  fontSize: 13,
  fontWeight: 850,
  color: 'var(--text-primary)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}
