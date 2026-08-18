'use client'

import { ECGMode } from '@/types'

interface ECGModeControlProps {
  mode: ECGMode
  onChange: (mode: ECGMode) => void
  disabled?: boolean
  effectiveConnected: boolean
  reason?: string | null
}

const OPTIONS: Array<{ value: ECGMode; label: string; hint: string }> = [
  { value: 'auto', label: 'Auto', hint: 'Recommended default' },
  { value: 'connected', label: 'Connected', hint: 'Manual override' },
  { value: 'disconnected', label: 'Disconnected', hint: 'Manual override' },
]

export function ECGModeControl({
  mode,
  onChange,
  disabled = false,
  effectiveConnected,
  reason,
}: ECGModeControlProps) {
  return (
    <div style={{
      border: '1px solid rgba(148,163,184,0.18)',
      background: 'rgba(15,23,42,0.65)',
      borderRadius: 12,
      padding: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>
            ECG Connection Mode
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            Select automatic or manual ECG electrode state
          </div>
        </div>

        <div style={{
          fontSize: 11,
          fontWeight: 700,
          color: effectiveConnected ? '#22c55e' : '#f87171',
          padding: '4px 8px',
          borderRadius: 999,
          border: `1px solid ${effectiveConnected ? 'rgba(34,197,94,0.35)' : 'rgba(248,113,113,0.35)'}`,
          background: effectiveConnected ? 'rgba(34,197,94,0.08)' : 'rgba(248,113,113,0.08)',
        }}>
          Effective ECG: {effectiveConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {OPTIONS.map((option) => {
          const active = mode === option.value
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              disabled={disabled}
              style={{
                flex: '1 1 150px',
                minWidth: 120,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: 3,
                borderRadius: 10,
                border: `1px solid ${active ? 'rgba(34,197,94,0.45)' : 'rgba(71,85,105,0.45)'}`,
                background: active ? 'rgba(34,197,94,0.12)' : 'rgba(15,23,42,0.75)',
                color: active ? '#dcfce7' : '#cbd5e1',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.65 : 1,
                padding: '10px 12px',
                transition: 'all 0.2s ease',
              }}
            >
              <span style={{ fontSize: 12, fontWeight: 700 }}>{option.label}</span>
              <span style={{ fontSize: 10, color: active ? '#86efac' : '#64748b' }}>{option.hint}</span>
            </button>
          )
        })}
      </div>

      <div style={{ fontSize: 11, color: '#94a3b8' }}>
        Reason: <span style={{ color: '#cbd5e1' }}>{reason || 'awaiting_sensor_status'}</span>
      </div>
    </div>
  )
}
