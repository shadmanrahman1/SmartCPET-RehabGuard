'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ARRHYTHMIA_CLASSES } from '@/lib/ecg-config'
import { Activity, AlertTriangle } from 'lucide-react'

// Matches cnn_result shape from ProcessedSlow1Hz
interface CnnResult {
  predicted_class: number
  class_name:      string
  confidence:      number
  is_critical:     boolean
}

interface PredictionDisplayProps {
  prediction: CnnResult | null
  className?: string
}

export function PredictionDisplay({ prediction, className = '' }: PredictionDisplayProps) {
  const cardStyle: React.CSSProperties = {
    background: 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.96))',
    border: prediction?.is_critical
      ? '1px solid rgba(220,38,38,0.35)'
      : '1px solid rgba(15,23,42,0.10)',
    boxShadow: prediction?.is_critical
      ? '0 18px 42px rgba(220,38,38,0.10)'
      : '0 18px 42px rgba(15,23,42,0.07)',
    color: 'var(--text-primary)',
  }

  if (!prediction) {
    return (
      <Card className={className} style={cardStyle}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2" style={{ color: 'var(--text-primary)', fontSize: 15 }}>
            <Activity className="h-5 w-5" color="var(--emerald-color)" />
            AI Screening
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
            Waiting for prediction...
          </p>
        </CardContent>
      </Card>
    )
  }

  const classInfo = ARRHYTHMIA_CLASSES[prediction.predicted_class as keyof typeof ARRHYTHMIA_CLASSES]
  const confidencePctValue = prediction.confidence > 1 ? prediction.confidence : prediction.confidence * 100
  const confidencePercent = confidencePctValue.toFixed(1)

  return (
    <Card className={className} style={cardStyle}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2" style={{ color: 'var(--text-primary)', fontSize: 15 }}>
          <Activity className="h-5 w-5" color="var(--emerald-color)" />
          AI Screening
          {prediction.is_critical && (
            <AlertTriangle className="h-5 w-5 text-red-500 animate-pulse" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Class Name */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Classification</span>
            <span 
              className="text-2xl font-bold"
              style={{ color: classInfo.color }}
            >
              {classInfo.name}
            </span>
          </div>
        </div>

        {/* Confidence */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Confidence</span>
            <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>{confidencePercent}%</span>
          </div>
          <div style={{ width: '100%', height: 10, borderRadius: 999, background: 'rgba(15,23,42,0.08)', overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                borderRadius: 999,
                width: `${confidencePercent}%`,
                backgroundColor: classInfo.color,
                transition: 'width 0.3s ease',
              }}
            />
          </div>
          <div className="mt-1 text-right">
            <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
              Model v1 — Retraining in progress
            </span>
          </div>
        </div>

        {/* Alert Status */}
        {prediction.is_critical && (
          <div style={{
            background: 'rgba(254,242,242,0.95)',
            border: '1px solid rgba(220,38,38,0.25)',
            borderRadius: 12,
            padding: 12,
          }}>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
              <span className="text-sm font-semibold text-red-600 dark:text-red-400">
                Critical rhythm pattern flagged
              </span>
            </div>
            <p className="text-xs text-red-600/80 dark:text-red-400/80 mt-1">
              Clinical review recommended. Screening aid only.
            </p>
          </div>
        )}

        {/* Timestamp — omitted since new payload has no timestamp per beat */}
      </CardContent>
    </Card>
  )
}
