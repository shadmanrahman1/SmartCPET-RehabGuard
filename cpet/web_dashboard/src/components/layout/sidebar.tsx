"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, Users, Activity, Heart,
  LogOut, BarChart2, HelpCircle, FileText
} from "lucide-react"

const navigation = [
  { name: "Dashboard",   href: "/dashboard",   icon: LayoutDashboard },
  { name: "ECG Monitor", href: "/ecg-monitor",  icon: Heart },
  { name: "Analytics",   href: "/analysis",     icon: BarChart2 },
  { name: "Patients",    href: "/patients",     icon: Users },
  { name: "Report",      href: "/report",       icon: FileText },
]

interface SidebarProps {
  sidebarOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ sidebarOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname()

  return (
    <div
      className="ag-sidebar"
      data-open={sidebarOpen ? "true" : "false"}
      style={{
        display: "flex",
        flexDirection: "column",
        background: "var(--sidebar-bg)",
        backdropFilter: "blur(16px)",
        borderRight: "1px solid var(--border-subtle)",
      }}
    >
      {/* Logo */}
      <div style={{
        display: "flex", alignItems: "center",
        height: 64, padding: "0 20px",
        borderBottom: "1px solid var(--border-subtle)",
      }}>
        <Link
          href="/dashboard"
          onClick={onClose}
          style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}
        >
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: "linear-gradient(135deg, #10b981, #059669)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 14px rgba(16,185,129,0.35)", flexShrink: 0,
          }}>
            <Activity style={{ color: "#fff", width: 17, height: 17 }} />
          </div>
          <div>
            <div style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 13, letterSpacing: "-0.01em", lineHeight: 1.2 }}>
              KUET BME
            </div>
            <div style={{ color: "var(--color-primary)", fontWeight: 600, fontSize: 11, letterSpacing: "0.04em" }}>
              CPET SYSTEM
            </div>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: "16px 8px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: "var(--text-secondary)",
          textTransform: "uppercase", padding: "0 12px 8px", opacity: 0.8 }}>
          Monitoring
        </div>
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onClose}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "10px 12px", borderRadius: 8,
                textDecoration: "none", fontSize: 13, fontWeight: 500,
                transition: "all 0.15s",
                background: isActive
                  ? "var(--accent-soft)"
                  : "transparent",
                color: isActive ? "var(--color-primary)" : "var(--text-secondary)",
                borderLeft: isActive ? "2px solid var(--color-primary)" : "2px solid transparent",
              }}
            >
              <item.icon style={{ width: 16, height: 16, flexShrink: 0,
                color: isActive ? "var(--color-primary)" : "var(--text-secondary)" }} />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div style={{ borderTop: "1px solid var(--border-subtle)", padding: "12px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
        <Link href="#" style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "9px 12px", borderRadius: 8, textDecoration: "none",
          color: "var(--text-secondary)", fontSize: 13, fontWeight: 500,
        }}>
          <HelpCircle style={{ width: 16, height: 16 }} />
          Support
        </Link>
        <button style={{
          display: "flex", width: "100%", alignItems: "center", gap: 12,
          padding: "9px 12px", borderRadius: 8, border: "none",
          background: "transparent", color: "#ef4444",
          fontSize: 13, fontWeight: 500, cursor: "pointer",
        }}>
          <LogOut style={{ width: 16, height: 16 }} />
          Sign out
        </button>
      </div>
    </div>
  )
}
