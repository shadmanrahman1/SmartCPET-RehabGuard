'use client'

import {
  AreaChart, Area, XAxis, YAxis,
  ResponsiveContainer, CartesianGrid, Tooltip,
} from 'recharts'
import { ECGChartPoint } from '@/lib/useECGSocket'

interface EcgChartProps {
  data:      ECGChartPoint[]
  height?:   number
  connected: boolean
  ecgConnectedEffective?: boolean
  ecgReason?: string | null
}

interface TooltipPayloadItem {
  value?: number
}

interface ECGTooltipProps {
  active?: boolean
  payload?: TooltipPayloadItem[]
}

// Custom tooltip - minimal for clinical use
const ECGTooltip = ({ active, payload }: ECGTooltipProps) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(7,13,26,0.95)',
      border: '1px solid rgba(34,197,94,0.3)',
      borderRadius: 6, padding: '4px 10px',
      fontSize: 11, color: '#22c55e',
    }}>
      {payload[0].value?.toFixed(2)} mV
    </div>
  )
}

export function EcgChart({
  data,
  height = 220,
  connected,
  ecgConnectedEffective,
  ecgReason,
}: EcgChartProps) {
  const isEmpty = data.length === 0
  const effectiveConnected = ecgConnectedEffective ?? connected
  const electrodesDisconnected = connected && !effectiveConnected

  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      {/* Grid lines for clinical paper look */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(34,197,94,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(34,197,94,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
        pointerEvents: 'none',
        zIndex: 0,
      }} />

      {/* Placeholder when no data yet */}
      {isEmpty && !electrodesDisconnected && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          color: '#475569', fontSize: 13, gap: 8, zIndex: 2,
        }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
            stroke={connected ? '#22c55e' : '#ef4444'} strokeWidth="1.5">
            <path d="M22 12h-4l-3 9L9 3 6 12H2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {connected
            ? 'Waiting for ECG signal…'
            : 'Connect to Raspberry Pi to begin'}
        </div>
      )}

      {electrodesDisconnected && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 8,
          zIndex: 3,
          background: 'rgba(2, 6, 23, 0.62)',
          borderRadius: 8,
          border: '1px solid rgba(239,68,68,0.25)',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f87171' }}>
            Electrodes not connected
          </div>
          <div style={{ fontSize: 11, color: '#fca5a5' }}>
            {ecgReason || 'No ECG contact detected'}
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <AreaChart
          data={data}
          margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="ecgGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.18} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0}    />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke="rgba(34,197,94,0.06)"
            strokeDasharray="0"
          />

          <XAxis dataKey="t" hide />

          <YAxis
            tick={{ fill: '#475569', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={36}
            domain={['auto', 'auto']}
          />

          <Tooltip
            content={<ECGTooltip />}
            isAnimationActive={false}
          />

          <Area
            type="linear"
            dataKey="v"
            stroke="#22c55e"
            strokeWidth={1.5}
            fill="url(#ecgGrad)"
            dot={false}
            isAnimationActive={false}
            activeDot={{ r: 3, fill: '#22c55e', stroke: '#070d1a', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
