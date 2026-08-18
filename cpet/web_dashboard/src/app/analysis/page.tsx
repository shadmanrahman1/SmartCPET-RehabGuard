"use client"

import { useEffect } from "react"
import { useECGSocket }  from "@/lib/useECGSocket"
import { ARRHYTHMIA_CLASSES } from "@/lib/ecg-config"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from "recharts"
import { Activity, TrendingUp, Heart, Wind, Zap } from "lucide-react"

export default function AnalyticsPage() {
  const { isConnected, sensorStatus, processedData, cpetParameters, mpuData, latestPrediction, statistics, requestStatistics } = useECGSocket()

  useEffect(() => {
    if (!isConnected) return
    requestStatistics()
    const id = setInterval(requestStatistics, 5000)
    return () => clearInterval(id)
  }, [isConnected, requestStatistics])

  const predictionStatusLower = sensorStatus?.prediction_status?.toLowerCase() ?? ''
  const predictionLive = isConnected &&
    sensorStatus?.ecg_connected_effective !== false &&
    sensorStatus?.prediction_active !== false &&
    !['inactive', 'paused', 'unavailable', 'disabled', 'stale', 'lead_off'].includes(predictionStatusLower)
  const livePrediction = predictionLive ? (latestPrediction ?? processedData?.cnn_result ?? null) : null
  const statsDist = statistics?.class_distribution
  const statsTotal = statsDist ? Object.values(statsDist).reduce((a, b) => a + b, 0) : 0
  const livePredictionDist = livePrediction
    ? {
        Normal: livePrediction.predicted_class === 0 ? 1 : 0,
        Supraventricular: livePrediction.predicted_class === 1 ? 1 : 0,
        Ventricular: livePrediction.predicted_class === 2 ? 1 : 0,
        Fusion: livePrediction.predicted_class === 3 ? 1 : 0,
        Unknown_Paced: livePrediction.predicted_class === 4 ? 1 : 0,
      }
    : null
  const dist = statsTotal > 0 ? statsDist : livePredictionDist
  const total = dist ? Object.values(dist).reduce((a, b) => a + b, 0) : 0

  const barData = dist
    ? Object.values(ARRHYTHMIA_CLASSES).map((cls) => ({
        name: cls.name,
        count: cls.name === "Unknown/Paced"
          ? dist.Unknown_Paced ?? 0
          : dist[cls.name as keyof typeof dist] ?? 0,
        fill: cls.color,
      }))
    : []

  const pieData = barData.filter(d => d.count > 0)
  const chartSourceLabel = statsTotal > 0 ? "Session statistics" : livePrediction ? "Latest live prediction" : null

  const unifiedBpm = typeof processedData?.bpm === 'number' && processedData.bpm > 0
    ? processedData.bpm
    : typeof processedData?.hr === 'number' && processedData.hr > 0
      ? processedData.hr
      : typeof sensorStatus?.bpm === 'number' && sensorStatus.bpm > 0
        ? sensorStatus.bpm
        : null

  const bpmSource = processedData?.bpm_source ?? sensorStatus?.bpm_source

  const bpmSourceLabel = bpmSource === 'max30102'
    ? 'Finger Sensor'
    : bpmSource === 'ecg'
      ? 'ECG'
      : 'Auto'

  const hrStatusOk = sensorStatus ? ((sensorStatus.bpm_status ?? sensorStatus.hr_status) === 'ok') : true
  const spo2StatusOk = sensorStatus ? sensorStatus.spo2_status === 'ok' : true

  const hrDisplay = hrStatusOk
    ? (unifiedBpm?.toFixed(0) ?? '--')
    : '--'

  const spo2Display = spo2StatusOk
    ? (processedData?.spo2?.toFixed(1) ?? '--')
    : '--'

  const cpet = cpetParameters ?? processedData?.cpet_parameters ?? null
  const respiratoryMotion =
    mpuData ??
    processedData?.respiratory_motion ??
    cpet?.respiratory_motion ??
    sensorStatus?.respiratory_motion ??
    sensorStatus?.mpu6050 ??
    null
  const mpuRespDisplay = respiratoryMotion?.resp_rate_mpu != null
    ? respiratoryMotion.resp_rate_mpu.toFixed(1)
    : "--"
  const motionState = respiratoryMotion?.motion_state ?? null
  const motionDisplay = motionState ? motionState.replace(/_/g, " ").toUpperCase() : "--"
  const motionSource = respiratoryMotion?.resp_signal_quality
    ? `Quality: ${respiratoryMotion.resp_signal_quality}`
    : "Chest motion"
  const motionColor = motionState?.toLowerCase() === "high" || motionState?.toLowerCase() === "severe"
    ? "var(--red-color)"
    : motionState?.toLowerCase() === "moderate" || motionState?.toLowerCase() === "medium"
      ? "var(--amber-color)"
      : motionState
        ? "var(--emerald-color)"
        : "var(--text-secondary)"

  const pttUnavailable = cpet?.ptt_available === false || (cpet?.ptt_status && cpet.ptt_status !== 'ok')
  const lrcUnavailable = cpet?.lrc_status && cpet.lrc_status !== 'ok'

  const pttDisplay = pttUnavailable
    ? 'N/A'
    : (cpet?.ptt_ms?.toFixed(0) ?? '--')

  const lrcDisplay = lrcUnavailable
    ? 'N/A'
    : ((cpet?.lrc_ratio ?? cpet?.lrc_index)?.toFixed(3) ?? '--')

  const respiratoryRateDisplay = cpet?.respiratory_rate_bpm?.toFixed(1) ?? '--'
  const respiratoryRateSource = cpet?.respiratory_rate_source
    ? cpet.respiratory_rate_source.replace(/_/g, ' ')
    : 'Backend selected source'
  const oxygenPulseDisplay = (cpet?.o2_pulse_surrogate ?? cpet?.oxygen_pulse)?.toFixed(2) ?? '--'
  const co2DeltaDisplay = (cpet?.co2_delta ?? cpet?.net_co2 ?? processedData?.co2_delta ?? processedData?.net_co2)?.toFixed(1) ?? '--'
  const veVco2Display = (cpet?.ve_vco2_slope_surrogate ?? cpet?.ve_vco2_slope)?.toFixed(2) ?? '--'
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", margin: 0,
          display: "flex", alignItems: "center", gap: 10 }}>
          <Activity size={20} color="var(--blue-color)" />
          Exercise Performance Analytics
        </h1>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
          CPET arrhythmia classification · Gas exchange · Cardiorespiratory metrics
        </p>
      </div>

      {/* Peak performance strip */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        {[
          { label: "Peak HR",       value: hrDisplay,              unit: "bpm",    color: "var(--red-color)", icon: <Heart size={14}/>, source: `Source: ${bpmSourceLabel}` },
          { label: "SpO2",          value: spo2Display,            unit: "%",      color: "var(--blue-color)", icon: <Activity size={14}/> },
          { label: "CO2 Delta",     value: co2DeltaDisplay,        unit: "ppm",    color: "var(--purple-color)", icon: <Wind size={14}/>, source: "Exhaled - ambient" },
          { label: "Resp Rate",     value: respiratoryRateDisplay, unit: "br/min", color: "var(--blue-color)", icon: <Wind size={14}/>, source: respiratoryRateSource },
          { label: "O2 Pulse",      value: oxygenPulseDisplay,     unit: "ml/beat", color: "var(--red-color)", icon: <Heart size={14}/>, source: "Surrogate" },
          { label: "PTT",           value: pttDisplay,             unit: "ms",     color: "var(--amber-color)", icon: <Zap size={14}/>, source: pttUnavailable ? 'Unavailable: no waveform timing' : undefined },
          { label: "LRC Ratio",     value: lrcDisplay,             unit: "",       color: "var(--emerald-color)", icon: <TrendingUp size={14}/>, source: lrcUnavailable ? 'Requires respiratory rate' : undefined },
          { label: "VE/VCO2",       value: veVco2Display,          unit: "",       color: "var(--cyan-color)", icon: <Activity size={14}/>, source: "Raw-sensor surrogate" },
          { label: "Resp (MPU)",    value: mpuRespDisplay,         unit: "br/min", color: "var(--blue-color)", icon: <Wind size={14}/>, source: motionSource },
          { label: "Motion",        value: motionDisplay,          unit: "",       color: motionColor, icon: <Activity size={14}/>, source: "Artifact context" },
          { label: "Total Beats",   value: String(total),          unit: "beats",  color: "var(--text-secondary)", icon: <Heart size={14}/> },
        ].map(m => (
          <div key={m.label} style={{
            flex: "1 1 140px", minWidth: 130,
            padding: "14px 16px", borderRadius: 12,
            border: `1px solid var(--border-subtle)`,
            background: `var(--bg-card)`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ color: m.color }}>{m.icon}</span>
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                color: "var(--text-secondary)", textTransform: "uppercase" }}>{m.label}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
              <span style={{ fontSize: 26, fontWeight: 700, color: m.color,
                fontVariantNumeric: "tabular-nums" }}>{m.value}</span>
              <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{m.unit}</span>
            </div>
            {m.source && (
              <div style={{ fontSize: 10, color: "var(--text-secondary)", marginTop: 4 }}>{m.source}</div>
            )}
          </div>
        ))}
      </div>

      {/* Charts grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}
        className="analytics-grid">

        {/* Beat classification bar chart */}
        <div style={{
          background: "var(--bg-card)", borderRadius: 14, padding: 20,
          border: "1px solid var(--border-subtle)",
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--blue-color)",
            textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
            Beat Classification (AAMI Standard)
            {chartSourceLabel && (
              <span style={{ marginLeft: 8, fontSize: 10, color: "var(--text-secondary)", letterSpacing: 0, textTransform: "none" }}>
                {chartSourceLabel}
              </span>
            )}
          </div>
          {total > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} margin={{ top: 4, right: 4, left: -20, bottom: 40 }}>
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="0" />
                <XAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                  angle={-35} textAnchor="end" tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: 8 }}
                  labelStyle={{ color: "var(--text-secondary)" }} itemStyle={{ color: "var(--text-primary)" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg={isConnected ? "Waiting for predictions…" : "Connect Pi to load data"} />
          )}
        </div>

        {/* Distribution pie */}
        <div style={{
          background: "var(--bg-card)", borderRadius: 14, padding: 20,
          border: "1px solid var(--border-subtle)",
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--emerald-color)",
            textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
            Beat Distribution
            {chartSourceLabel && (
              <span style={{ marginLeft: 8, fontSize: 10, color: "var(--text-secondary)", letterSpacing: 0, textTransform: "none" }}>
                {chartSourceLabel}
              </span>
            )}
          </div>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} dataKey="count" nameKey="name"
                  cx="50%" cy="50%" outerRadius={80}
                  label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "var(--bg-main)", border: "1px solid var(--border-subtle)", borderRadius: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg={isConnected ? "Waiting for data…" : "Connect Pi to load data"} />
          )}
        </div>
      </div>

      {/* CPET Parameters panel */}
      {cpet && (
        <div style={{
          background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
          borderRadius: 18,
          padding: 22,
          border: "1px solid rgba(15,23,42,0.10)",
          boxShadow: "0 18px 44px rgba(15,23,42,0.08)",
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            flexWrap: "wrap",
            marginBottom: 18,
          }}>
            <div>
              <div style={{
                fontSize: 13,
                fontWeight: 900,
                color: "#1e293b",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}>
                CPET Robust Parameters
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: "#64748b", fontWeight: 600 }}>
                Derived screening metrics from live backend processing
              </div>
            </div>
            <span style={{
              padding: "6px 10px",
              borderRadius: 999,
              background: "rgba(124,58,237,0.10)",
              border: "1px solid rgba(124,58,237,0.20)",
              color: "#6d28d9",
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            }}>
              1 Hz CPET stream
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {[
              {
                label: "LRC Ratio (BR/HR)",
                value: lrcUnavailable ? null : (cpet.lrc_ratio ?? cpet.lrc_index ?? null),
                unit: "",
                desc: lrcUnavailable ? `Requires: ${(cpet.lrc_status || 'unknown').replace(/_/g, ' ')}` : "Lung-Resp-Cardiac balance",
                accent: "#7c3aed",
                icon: "LR",
                normal: "0.20 - 0.30",
              },
              {
                label: "Respiratory Rate",
                value: cpet.respiratory_rate_bpm ?? null,
                unit: "br/min",
                desc: respiratoryRateSource,
                accent: "#2563eb",
                icon: "RR",
                normal: "12 - 22",
              },
              {
                label: "O2 Pulse Surrogate",
                value: cpet.o2_pulse_surrogate ?? cpet.oxygen_pulse ?? null,
                unit: "ml/beat",
                desc: "Project stroke-volume proxy",
                accent: "#e11d48",
                icon: "O2",
                normal: "10 - 20",
              },
              {
                label: "CO2 Delta",
                value: cpet.co2_delta ?? cpet.net_co2 ?? processedData?.co2_delta ?? processedData?.net_co2 ?? null,
                unit: "ppm",
                desc: "Exhaled minus ambient",
                accent: "#9333ea",
                icon: "CO",
                normal: "> 0",
              },
              {
                label: "PTT",
                value: pttUnavailable ? null : (cpet.ptt_ms ?? null),
                unit: "ms",
                desc: pttUnavailable ? "Unavailable: no PPG waveform timing" : "ECG to PPG delay",
                accent: "#2563eb",
                icon: "PT",
                normal: "200 - 350",
              },
              {
                label: "VE/VCO2 Surrogate",
                value: cpet.ve_vco2_slope_surrogate ?? cpet.ve_vco2_slope ?? null,
                unit: "",
                desc: "Raw-sensor project surrogate",
                accent: "#0891b2",
                icon: "VE",
                normal: "20 - 30",
              },
            ].map(p => (
              <div key={p.label} style={{
                flex: "1 1 240px",
                minWidth: 220,
                padding: "16px 18px",
                borderRadius: 16,
                border: p.value == null
                  ? "1px solid rgba(245,158,11,0.34)"
                  : "1px solid rgba(15,23,42,0.10)",
                background: p.value == null
                  ? "linear-gradient(180deg, #fffdf7 0%, #fff7ed 100%)"
                  : "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
                boxShadow: "0 12px 30px rgba(15,23,42,0.07)",
                borderLeft: `5px solid ${p.value == null ? "#f59e0b" : p.accent}`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{
                    width: 34,
                    height: 34,
                    borderRadius: 12,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: p.value == null ? "rgba(245,158,11,0.14)" : `${p.accent}18`,
                    color: p.value == null ? "#b45309" : p.accent,
                    fontSize: 11,
                    fontWeight: 900,
                    letterSpacing: "0.04em",
                  }}>
                    {p.icon}
                  </span>
                  <div>
                    <div style={{
                      fontSize: 11,
                      fontWeight: 900,
                      color: "#334155",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}>
                      {p.label}
                    </div>
                    <div style={{ marginTop: 2, fontSize: 11, color: "#64748b", fontWeight: 600 }}>
                      {p.desc}
                    </div>
                  </div>
                </div>
                <div style={{
                  fontSize: 30,
                  fontWeight: 900,
                  color: p.value == null ? "#334155" : p.accent,
                  letterSpacing: "-0.04em",
                  fontVariantNumeric: "tabular-nums",
                }}>
                  {p.value != null ? p.value.toFixed(3) : "N/A"}
                  {p.unit && <span style={{ fontSize: 12, color: "#475569", marginLeft: 5, fontWeight: 800 }}>{p.unit}</span>}
                </div>
                <div style={{
                  display: "inline-flex",
                  marginTop: 10,
                  padding: "5px 8px",
                  borderRadius: 999,
                  background: p.value == null ? "rgba(245,158,11,0.12)" : "rgba(15,23,42,0.04)",
                  color: p.value == null ? "#92400e" : "#475569",
                  fontSize: 11,
                  fontWeight: 800,
                }}>
                  Normal: {p.normal}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clinical interpretation box */}
      {livePrediction && (
        <div style={{
          padding: "18px 22px",
          borderRadius: 18,
          border: livePrediction?.is_critical
            ? "1px solid rgba(220,38,38,0.22)"
            : "1px solid rgba(16,185,129,0.22)",
          background: livePrediction?.is_critical
            ? "linear-gradient(180deg, #fff7ed 0%, #fff1f2 100%)"
            : "linear-gradient(180deg, #ecfdf5 0%, #f0fdf4 100%)",
          boxShadow: "0 16px 38px rgba(15,23,42,0.07)",
        }}>
          <div style={{
            fontSize: 11,
            fontWeight: 900,
            letterSpacing: "0.08em",
            color: livePrediction?.is_critical ? "#dc2626" : "#047857",
            textTransform: "uppercase",
            marginBottom: 8,
          }}>
            {livePrediction?.is_critical ? "Alert - " : "Stable - "}Clinical Interpretation
          </div>
          <div style={{ fontSize: 18, fontWeight: 850, color: "#0f172a" }}>
            {livePrediction?.class_name}
          </div>
          <div style={{ fontSize: 13, color: "#334155", marginTop: 6, fontWeight: 600, lineHeight: 1.55 }}>
            Confidence: {(((livePrediction?.confidence ?? 0) * 100).toFixed(1))}% -
            Class {livePrediction?.predicted_class} (AAMI) - {" "}
            {livePrediction?.is_critical ? "Immediate clinical attention recommended." : "Rhythm within acceptable screening range."}
          </div>
        </div>
      )}

      <style>{`
        @media (max-width: 768px) {
          .analytics-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div style={{ height: 220, display: "flex", alignItems: "center",
      justifyContent: "center", color: "var(--text-secondary)", fontSize: 13 }}>
      {msg}
    </div>
  )
}

