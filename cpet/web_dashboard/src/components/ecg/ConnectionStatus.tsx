'use client'

import { Wifi, WifiOff, Server, Cpu, Clock, Radio, Activity, Droplets, Heart } from 'lucide-react'
import { ServerStatus, SensorStatusPayload } from '@/types'
import { ECG_SERVER_CONFIG } from '@/lib/ecg-config'

interface ConnectionStatusProps {
  isConnected:    boolean
  connectionError?: string | null
  serverStatus?:  ServerStatus | null
  sensorStatus?:  SensorStatusPayload | null
  isVitalsStale?: boolean
  onDisconnect?:  () => void
  onReconnect?:   () => void
}

export function ConnectionStatus({
  isConnected,
  connectionError,
  serverStatus,
  sensorStatus,
  isVitalsStale = false,
  onDisconnect,
  onReconnect,
}: ConnectionStatusProps) {
  const arduinoUnavailable =
    sensorStatus?.arduino_connected === false ||
    sensorStatus?.arduino_connection_status === 'unavailable' ||
    sensorStatus?.ecg_reason === 'arduino_unavailable'
  const respiratoryMotion = sensorStatus?.respiratory_motion ?? sensorStatus?.mpu6050 ?? null

  return (
    <>
      <style>{`
        @keyframes pingStatus {
          0%   { transform: scale(1); opacity: 0.8; }
          70%  { transform: scale(2); opacity: 0;   }
          100% { transform: scale(1); opacity: 0;   }
        }
      `}</style>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        padding: '12px 18px',
        borderRadius: 12,
        border: `1px solid ${isConnected ? 'rgba(16,185,129,0.24)' : 'rgba(220,38,38,0.25)'}`,
        background: isConnected
          ? 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(240,253,250,0.72))'
          : 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(254,242,242,0.72))',
        boxShadow: '0 14px 34px rgba(15,23,42,0.06)',
        transition: 'all 0.3s',
      }}>
        {/* Left: Status + URL */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {/* Dot + label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ position: 'relative', width: 10, height: 10 }}>
              {isConnected && (
                <div style={{
                  position: 'absolute', inset: 0, borderRadius: '50%',
                  background: '#22c55e',
                  animation: 'pingStatus 1.5s ease-out infinite',
                }} />
              )}
              <div style={{
                position: 'absolute', inset: 0, borderRadius: '50%',
                background: isConnected ? '#22c55e' : '#ef4444',
                boxShadow: isConnected ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
              }} />
            </div>
            <span style={{
              fontSize: 13, fontWeight: 700,
              color: isConnected ? '#22c55e' : '#ef4444',
            }}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* URL */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-secondary)' }}>
            <Server size={13} />
            <span style={{ fontSize: 12, fontFamily: 'monospace' }}>
              {ECG_SERVER_CONFIG.url}
            </span>
          </div>

          {/* Error */}
          {!isConnected && connectionError && (
            <span style={{ fontSize: 11, color: '#ef4444' }}>{connectionError}</span>
          )}

          {/* Server status chips */}
          {serverStatus && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Chip icon={<Radio size={12}/>} active={serverStatus.arduino_connected}
                label={`Arduino: ${serverStatus.arduino_connected ? 'Online' : 'Offline'}`} />
              <Chip icon={<Cpu size={12}/>} active={serverStatus.model_loaded}
                label={`AI Model: ${serverStatus.model_loaded ? 'Ready' : 'Not loaded'}`} />
              <Chip icon={<Clock size={12}/>} active={true}
                label={`Up: ${fmt(serverStatus.uptime)}`} />
            </div>
          )}

          {sensorStatus && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Chip
                icon={<Activity size={12} />}
                active={sensorStatus.ecg_connected_effective}
                label={`ECG: ${sensorStatus.ecg_connected_effective ? 'Connected' : 'Disconnected'}${sensorStatus.lead_off ? ' (Lead-off)' : ''}`}
              />
              <Chip
                icon={<Radio size={12} />}
                active={sensorStatus.ecg_mode !== 'disconnected'}
                label={`Mode: ${formatMode(sensorStatus.ecg_mode)}`}
              />
              <Chip
                icon={<Clock size={12} />}
                active={!isVitalsStale}
                label={`Vitals: ${isVitalsStale ? 'Stale' : 'Live'}`}
              />
              <Chip
                icon={<Radio size={12} />}
                active={!arduinoUnavailable && !sensorStatus.arduino_stream_stale}
                label={`Arduino: ${arduinoUnavailable ? 'Unavailable' : sensorStatus.arduino_stream_stale ? 'Stale' : 'Ready'}`}
              />
              {respiratoryMotion && (
                <Chip
                  icon={<Activity size={12} />}
                  active={respiratoryMotion.resp_signal_quality === 'good'}
                  label={`MPU: ${respiratoryMotion.motion_state ?? respiratoryMotion.status ?? 'ready'}`}
                />
              )}
              {sensorStatus.bpm != null && (
                <Chip
                  icon={<Heart size={12} />}
                  active={sensorStatus.bpm_status === 'ok'}
                  label={`BPM: ${sensorStatus.bpm.toFixed(0)} (${formatBpmSource(sensorStatus.bpm_source)})`}
                />
              )}
              <Chip
                icon={<Droplets size={12} />}
                active={sensorStatus.spo2_status === 'ok'}
                label={`SpO2: ${formatSensorState(sensorStatus.spo2_status)}`}
              />
              <Chip
                icon={<Heart size={12} />}
                active={sensorStatus.hr_status === 'ok'}
                label={`HR: ${formatSensorState(sensorStatus.hr_status)}`}
              />
              <span style={{ fontSize: 11, color: '#64748b' }}>
                Reason: {sensorStatus.ecg_reason || 'unknown'}
              </span>
              {sensorStatus.arduino_status_message && (
                <span style={{ fontSize: 11, color: arduinoUnavailable ? '#f59e0b' : '#64748b' }}>
                  {sensorStatus.arduino_status_message}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Right: action buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          {isConnected
            ? <ActionBtn onClick={onDisconnect} danger label="Disconnect" icon={<WifiOff size={13}/>} />
            : <ActionBtn onClick={onReconnect}         label="Reconnect"  icon={<Wifi    size={13}/>} />
          }
        </div>
      </div>
    </>
  )
}

// ── helpers ──────────────────────────────────────────────────────────────────

function Chip({ icon, active, label }: { icon: React.ReactNode; active: boolean; label: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      padding: '4px 8px',
      borderRadius: 999,
      border: `1px solid ${active ? 'rgba(5,150,105,0.22)' : 'rgba(220,38,38,0.16)'}`,
      background: active ? 'rgba(16,185,129,0.08)' : 'rgba(220,38,38,0.06)',
      color: active ? '#047857' : '#b91c1c',
      fontWeight: 700,
    }}>
      {icon}
      <span style={{ fontSize: 11 }}>{label}</span>
    </div>
  )
}

function ActionBtn({ onClick, label, icon, danger = false }:
  { onClick?: () => void; label: string; icon: React.ReactNode; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
        border: `1px solid ${danger ? 'rgba(239,68,68,0.35)' : 'rgba(34,197,94,0.35)'}`,
        background: danger ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.08)',
        color: danger ? '#ef4444' : '#22c55e',
        cursor: 'pointer',
      }}
    >
      {icon} {label}
    </button>
  )
}

function fmt(s: number) {
  return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`
}

function formatMode(mode: string) {
  if (mode === 'connected') return 'Connected'
  if (mode === 'disconnected') return 'Disconnected'
  return 'Auto'
}

function formatSensorState(status: string) {
  if (status === 'ok') return 'OK'
  if (status === 'no_data') return 'No data'
  return 'Unavailable'
}

function formatBpmSource(source: string | undefined) {
  if (source === 'max30102') return 'MAX'
  if (source === 'ecg') return 'ECG'
  return 'Auto'
}
