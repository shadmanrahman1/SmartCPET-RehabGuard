'use client'

import { useEffect } from 'react'
import { Activity, RefreshCw, Trash2 } from 'lucide-react'

import { useECGSocket }         from '@/lib/useECGSocket'
import { ConnectionStatus }     from '@/components/ecg/ConnectionStatus'
import { AlertBanner }          from '@/components/ecg/AlertBanner'
import { EcgChart }             from '@/components/ecg/EcgChart'
import { VitalsPanel }          from '@/components/ecg/VitalsPanel'
import { PredictionDisplay }    from '@/components/ecg/PredictionDisplay'
import { ECGStatisticsDisplay } from '@/components/ecg/ECGStatisticsDisplay'
import { CPETParametersDisplay } from '@/components/ecg/CPETParametersDisplay'

const monitorCardStyle: React.CSSProperties = {
  background: 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.96))',
  border: '1px solid rgba(15,23,42,0.10)',
  borderRadius: 18,
  padding: 20,
  boxShadow: '0 18px 45px rgba(15,23,42,0.07)',
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 800,
  color: 'var(--text-primary)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
}

export default function ECGMonitorPage() {
  const piServerLabel = (process.env.NEXT_PUBLIC_PI_SERVER_URL || 'http://mypi.local:5000')
    .replace('http://', '')
    .replace('https://', '')
  const {
    // connection
    isConnected, connectionError, serverStatus,
    sensorStatus, isEcgConnectedEffective, isVitalsStale,
    disconnect, reconnect,

    // data
    processedData, ecgPoints, activeAlert, dismissAlert,
    cpetParameters, mpuData, latestPrediction,
    statistics,
    requestStatistics, clearData,
  } = useECGSocket()

  const predictionStatusLower = sensorStatus?.prediction_status?.toLowerCase() ?? ''
  const predictionLive = isConnected &&
    isEcgConnectedEffective &&
    sensorStatus?.prediction_active !== false &&
    !['inactive', 'paused', 'unavailable', 'disabled', 'stale', 'lead_off'].includes(predictionStatusLower)
  const displayPrediction = predictionLive ? (latestPrediction ?? processedData?.cnn_result ?? null) : null

  // Auto-refresh statistics every 5 s while connected
  useEffect(() => {
    if (!isConnected) return
    requestStatistics()
    const id = setInterval(requestStatistics, 5000)
    return () => clearInterval(id)
  }, [isConnected, requestStatistics])

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      padding: '4px 0 28px',
      background: `
        radial-gradient(circle at top left, rgba(16,185,129,0.10), transparent 32%),
        radial-gradient(circle at 90% 10%, rgba(37,99,235,0.08), transparent 30%)
      `,
    }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div style={{
        ...monitorCardStyle,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        borderColor: 'rgba(16,185,129,0.18)',
      }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', margin: 0,
            display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 36,
              height: 36,
              borderRadius: 12,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, rgba(16,185,129,0.18), rgba(37,99,235,0.10))',
              border: '1px solid rgba(16,185,129,0.22)',
            }}>
              <Activity size={20} color="var(--emerald-color)" />
            </span>
            Real-time ECG Monitor
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Live rhythm screening · KUET BME CPET · target {piServerLabel}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <IconBtn onClick={clearData} label="Clear" icon={<Trash2 size={13}/>} />
          <IconBtn onClick={requestStatistics} label="Refresh Stats" icon={<RefreshCw size={13}/>} />
        </div>
      </div>

      {/* ── Connection status bar ────────────────────────────────────────── */}
      <ConnectionStatus
        isConnected={isConnected}
        connectionError={connectionError}
        serverStatus={serverStatus}
        sensorStatus={sensorStatus}
        isVitalsStale={isVitalsStale}
        onDisconnect={disconnect}
        onReconnect={reconnect}
      />

      {/* ── Arrhythmia alert banner ──────────────────────────────────────── */}
      <AlertBanner alert={activeAlert} onDismiss={dismissAlert} />

      {/* ── Main grid: ECG chart + prediction side panel ────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0,1fr) 320px',
        gap: 16,
      }}
        className="ecg-grid" // CSS fallback below for mobile
      >
        {/* ECG Waveform card */}
        <div style={{
          ...monitorCardStyle,
          borderColor: 'rgba(16,185,129,0.22)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <span style={sectionLabelStyle}>
              Live ECG Waveform
            </span>
            {isConnected && isEcgConnectedEffective && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: 'var(--color-primary)', boxShadow: '0 0 6px var(--color-primary)',
                  animation: 'pulse 1s ease-in-out infinite',
                }} />
                <span style={{ fontSize: 11, color: 'var(--color-primary)', fontWeight: 600 }}>LIVE</span>
              </div>
            )}
          </div>

          <EcgChart
            data={ecgPoints}
            height={240}
            connected={isConnected}
            ecgConnectedEffective={isEcgConnectedEffective}
            ecgReason={sensorStatus?.ecg_reason}
          />

          {/* Sample count */}
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-secondary)' }}>
            Buffer: {ecgPoints.length} / 300 samples
          </div>
        </div>

        {/* Prediction panel */}
        <div>
          <PredictionDisplay prediction={displayPrediction} />
          {isConnected && !predictionLive && (
            <div style={{
              marginTop: 10,
              padding: '8px 10px',
              borderRadius: 10,
              background: 'rgba(245,158,11,0.10)',
              border: '1px solid rgba(245,158,11,0.20)',
              color: '#92400e',
              fontSize: 11,
              fontWeight: 700,
            }}>
              Prediction paused until ECG/electrodes are available.
            </div>
          )}
        </div>
      </div>

      {/* ── Vitals panel ─────────────────────────────────────────────────── */}
      <div style={{
        ...monitorCardStyle,
        borderColor: 'rgba(16,185,129,0.18)',
      }}>
        <VitalsPanel
          data={processedData}
          sensorStatus={sensorStatus}
          cpetParameters={cpetParameters}
          mpuData={mpuData}
          isVitalsStale={isVitalsStale}
        />
      </div>

      {/* ── Statistics ───────────────────────────────────────────────────── */}
      <div style={monitorCardStyle}>
        <ECGStatisticsDisplay statistics={statistics} />
      </div>

      {/* ── CPET Parameters ── */}
      <div style={monitorCardStyle}>
        <CPETParametersDisplay parameters={cpetParameters ?? processedData?.cpet_parameters ?? null} />
      </div>

      {/* ── Getting-started info (offline only) ──────────────────────────── */}
      {!isConnected && (
        <div style={{
          padding: 20, borderRadius: 14,
          border: '1px solid var(--blue-color)',
          background: 'var(--accent-soft)',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--blue-color)', marginBottom: 12 }}>
            Getting Started
          </div>
          <ol style={{ paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6, margin: 0 }}>
            {[
              'Make sure the Raspberry Pi is powered on and connected to your local network.',
              'The Pi Socket.IO server should be running on port 5000.',
              'Sensors (ECG, SpO₂, CO₂) must be connected to the Pi.',
              'Click Reconnect above — real-time data will appear automatically.',
            ].map((s, i) => (
              <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Scoped styles for grid mobile collapse */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1;   }
          50%       { opacity: 0.5; }
        }
        @media (max-width: 768px) {
          .ecg-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}

// ── Helper ────────────────────────────────────────────────────────────────────
function IconBtn({ onClick, label, icon }: { onClick?: () => void; label: string; icon: React.ReactNode }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
      border: '1px solid rgba(15,23,42,0.12)',
      background: '#ffffff',
      color: 'var(--text-primary)', cursor: 'pointer',
      boxShadow: '0 6px 18px rgba(15,23,42,0.06)',
    }}>
      {icon} {label}
    </button>
  )
}

