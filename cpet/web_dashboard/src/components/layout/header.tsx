"use client"

import { Bell, User, Menu, Moon, Sun } from "lucide-react"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

interface HeaderProps {
  onMenuToggle?: () => void
}

export function Header({ onMenuToggle }: HeaderProps) {
  const user = { name: "Dr. Admin", role: "Physiologist" }
  const pathname = usePathname()
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  let title = "Dashboard Overview"
  if (pathname === '/dashboard') title = "Dashboard Overview"
  else if (pathname === '/ecg-monitor') title = "Live ECG Monitor"
  else if (pathname?.startsWith('/analysis')) title = "Analysis"
  else if (pathname === '/patients') title = "Patient Records"
  else if (pathname === '/report') title = "Clinical Report"

  return (
    <>
      {/* Scoped hamburger style — only shows on mobile */}
      <style>{`
        .ag-hamburger {
          display: none;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 8px;
          border: 1px solid rgba(52,211,153,0.2);
          background: rgba(52,211,153,0.08);
          cursor: pointer;
          color: #94a3b8;
          flex-shrink: 0;
        }
      `}</style>

      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 30,
        display: 'flex',
        height: 64,
        width: '100%',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        background: 'var(--header-bg)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
      }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Hamburger button — CSS shows it only on mobile via ag-hamburger class */}
          <button
            className="ag-hamburger"
            onClick={onMenuToggle}
            aria-label="Open navigation menu"
          >
            <Menu style={{ width: 18, height: 18 }} />
          </button>

          <h1 style={{ fontSize: 16, fontWeight: 600, color: '#f1f5f9', margin: 0 }}>
            {title}
          </h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Theme Toggle */}
          <button 
            onClick={() => {
              const activeTheme = resolvedTheme ?? theme
              setTheme(activeTheme === 'dark' ? 'light' : 'dark')
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 36, height: 36,
              borderRadius: 8,
              border: '1px solid var(--border-subtle)',
              background: 'transparent',
              cursor: 'pointer',
              color: 'var(--text-secondary)'
            }}>
            {mounted
              ? (resolvedTheme ?? theme) === 'dark'
                ? <Sun style={{ width: 16, height: 16 }} />
                : <Moon style={{ width: 16, height: 16 }} />
              : <span style={{ width: 16, height: 16, display: 'block' }} />
            }
          </button>

          {/* Bell */}
          <button style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 36, height: 36,
            borderRadius: 8,
            border: '1px solid var(--border-subtle)',
            background: 'transparent',
            cursor: 'pointer',
          }}>
            <Bell style={{ width: 16, height: 16, color: 'var(--text-secondary)' }} />
            <span style={{
              position: 'absolute', right: 7, top: 7,
              width: 8, height: 8,
              borderRadius: '50%',
              background: '#ef4444',
              boxShadow: '0 0 4px #ef4444',
            }} />
          </button>

          {/* Divider */}
          <div style={{ width: 1, height: 32, background: 'rgba(52,211,153,0.15)' }} />

          {/* User avatar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34, height: 34,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 10px rgba(16,185,129,0.35)',
            }}>
              <User style={{ width: 16, height: 16, color: '#fff' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{user.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{user.role}</span>
            </div>
          </div>
        </div>
      </header>
    </>
  )
}
