'use client'

import { AlertTriangle, X } from 'lucide-react'
import { CPETAlert } from '@/lib/useECGSocket'

interface AlertBannerProps {
  alert: CPETAlert | null
  onDismiss: () => void
}

export function AlertBanner({ alert, onDismiss }: AlertBannerProps) {
  if (!alert) return null

  return (
    <>
      <style>{`
        @keyframes alertPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.75; }
        }
        @keyframes alertSlide {
          from { transform: translateY(-12px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>

      <div
        role="alert"
        aria-live="assertive"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '14px 20px',
          borderRadius: 12,
          border: '1px solid rgba(239,68,68,0.6)',
          background: 'linear-gradient(135deg, rgba(239,68,68,0.18), rgba(185,28,28,0.1))',
          boxShadow: '0 0 24px rgba(239,68,68,0.3), inset 0 0 12px rgba(239,68,68,0.06)',
          animation: 'alertSlide 0.3s ease, alertPulse 2s ease-in-out infinite',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 38,
            height: 38,
            borderRadius: 10,
            background: 'rgba(239,68,68,0.2)',
            border: '1px solid rgba(239,68,68,0.4)',
            flexShrink: 0,
          }}
        >
          <AlertTriangle size={18} color="#ef4444" />
        </div>

        <div style={{ flex: 1 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--red-color)',
              letterSpacing: '-0.01em',
            }}
          >
            Warning: {alert.type}
          </div>
          <div style={{ fontSize: 11, color: 'var(--red-color)', opacity: 0.8, marginTop: 2 }}>
            CNN arrhythmia classifier triggered recently.
            <span style={{ color: 'var(--red-color)', opacity: 1, fontWeight: 600 }}> Auto-dismiss in 12s</span>
          </div>
        </div>

        <button
          onClick={onDismiss}
          aria-label="Dismiss alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: 6,
            border: '1px solid rgba(239,68,68,0.3)',
            background: 'rgba(239,68,68,0.12)',
            cursor: 'pointer',
            color: 'var(--red-color)',
            flexShrink: 0,
          }}
        >
          <X size={14} />
        </button>
      </div>
    </>
  )
}
