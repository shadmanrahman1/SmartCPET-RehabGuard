'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ECGStatistics } from '@/types'
import { ARRHYTHMIA_CLASSES } from '@/lib/ecg-config'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts'
import { Activity, AlertCircle, TrendingUp } from 'lucide-react'

interface ECGStatisticsDisplayProps {
  statistics: ECGStatistics | null
  className?: string
}

export function ECGStatisticsDisplay({ statistics, className = '' }: ECGStatisticsDisplayProps) {
  const surfaceStyle: React.CSSProperties = {
    background: 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.94))',
    border: '1px solid rgba(15,23,42,0.10)',
    boxShadow: '0 10px 26px rgba(15,23,42,0.05)',
    color: 'var(--text-primary)',
  }

  if (!statistics) {
    return (
      <Card className={className} style={surfaceStyle}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2" style={{ color: 'var(--text-primary)', fontSize: 15 }}>
            <TrendingUp className="h-5 w-5" color="var(--blue-color)" />
            Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
            No statistics available yet
          </p>
        </CardContent>
      </Card>
    )
  }

  const classDistribution = (statistics.class_distribution ?? {}) as Record<string, number>
  const totalBeats = typeof statistics.total_beats === 'number' ? statistics.total_beats : 0
  const predictionsPerSecond = typeof statistics.predictions_per_second === 'number'
    ? statistics.predictions_per_second
    : 0
  const alertCount = typeof statistics.alert_count === 'number' ? statistics.alert_count : 0

  // Prepare data for charts
  const barData = Object.entries(classDistribution).map(([name, value]) => ({
    name: name.replace('_', ' '),
    count: value,
    color: ARRHYTHMIA_CLASSES[
      Object.keys(ARRHYTHMIA_CLASSES).find(
        key => ARRHYTHMIA_CLASSES[Number(key) as keyof typeof ARRHYTHMIA_CLASSES].name === name
      ) as unknown as keyof typeof ARRHYTHMIA_CLASSES
    ]?.color || '#06b6d4'
  }))

  const pieData = Object.entries(classDistribution)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({
      name: name.replace('_', ' '),
      value,
      color: ARRHYTHMIA_CLASSES[
        Object.keys(ARRHYTHMIA_CLASSES).find(
          key => ARRHYTHMIA_CLASSES[Number(key) as keyof typeof ARRHYTHMIA_CLASSES].name === name
        ) as unknown as keyof typeof ARRHYTHMIA_CLASSES
      ]?.color || '#06b6d4'
    }))

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card style={surfaceStyle}>
          <CardContent className="pt-6">
            <div className="text-center">
              <Activity className="h-8 w-8 mx-auto mb-2 text-blue-500" />
              <div style={{ fontSize: 26, fontWeight: 850, color: 'var(--text-primary)' }}>{totalBeats}</div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 700 }}>Total Beats</p>
            </div>
          </CardContent>
        </Card>

        <Card style={surfaceStyle}>
          <CardContent className="pt-6">
            <div className="text-center">
              <TrendingUp className="h-8 w-8 mx-auto mb-2 text-green-500" />
              <div style={{ fontSize: 26, fontWeight: 850, color: 'var(--text-primary)' }}>{predictionsPerSecond.toFixed(1)}</div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 700 }}>Predictions/sec</p>
            </div>
          </CardContent>
        </Card>

        <Card style={surfaceStyle}>
          <CardContent className="pt-6">
            <div className="text-center">
              <AlertCircle className="h-8 w-8 mx-auto mb-2 text-red-500" />
              <div style={{ fontSize: 26, fontWeight: 850, color: 'var(--text-primary)' }}>{alertCount}</div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 700 }}>Alerts</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Distribution Charts */}
      <div className="grid grid-cols-2 gap-4">
        {/* Bar Chart */}
        <Card style={surfaceStyle}>
          <CardHeader>
            <CardTitle className="text-sm" style={{ color: 'var(--text-primary)', fontWeight: 800 }}>Beat Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={barData}>
                <XAxis 
                  dataKey="name" 
                  tick={{ fontSize: 10 }}
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    border: '1px solid rgba(15,23,42,0.12)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                    boxShadow: '0 12px 28px rgba(15,23,42,0.10)',
                  }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {barData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Pie Chart */}
        <Card style={surfaceStyle}>
          <CardHeader>
            <CardTitle className="text-sm" style={{ color: 'var(--text-primary)', fontWeight: 800 }}>Classification Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{
                    backgroundColor: '#ffffff',
                    border: '1px solid rgba(15,23,42,0.12)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                    boxShadow: '0 12px 28px rgba(15,23,42,0.10)',
                  }}
                />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-62.5">
                <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>No data yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
