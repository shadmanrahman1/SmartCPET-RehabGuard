'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Header } from "./header";
import { Sidebar } from "./sidebar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (pathname === '/') {
    return <>{children}</>;
  }

  return (
    <>
      {/*
        Scoped styles — embedded directly so Tailwind/PostCSS cannot purge them.
        On desktop (≥768px): sidebar is normal-flow 256px wide column.
        On mobile (<768px): sidebar is a fixed overlay, hidden by default.
      */}
      <style>{`
        .ag-layout {
          display: flex;
          height: 100vh;
          width: 100%;
          overflow: hidden;
          background: var(--background);
        }

        /* ── Desktop: sidebar in normal flow ── */
        @media (min-width: 768px) {
          .ag-sidebar {
            position: relative;
            transform: none !important;
            width: 256px;
            height: 100%;
            flex-shrink: 0;
            z-index: auto;
          }
          .ag-sidebar-backdrop { display: none !important; }
          .ag-hamburger { display: none !important; }
          .ag-sidebar-pill { display: none !important; }
        }

        /* ── Mobile: sidebar as fixed overlay ── */
        @media (max-width: 767px) {
          .ag-sidebar {
            position: fixed;
            top: 0;
            left: 0;
            width: 256px;
            height: 100%;
            z-index: 50;
            transform: translateX(-100%);
            transition: transform 0.28s cubic-bezier(0.4,0,0.2,1);
          }
          .ag-sidebar[data-open="true"] {
            transform: translateX(0px);
          }
          .ag-sidebar-backdrop {
            display: block;
            position: fixed;
            inset: 0;
            z-index: 49;
            background: rgba(0,0,0,0.65);
          }
          .ag-hamburger {
            display: flex !important;
          }
          .ag-sidebar-pill {
            display: flex !important;
          }
        }
      `}</style>

      <div className="ag-layout">

        {/* Dark backdrop — only rendered when open on mobile */}
        {sidebarOpen && (
          <div
            className="ag-sidebar-backdrop"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <Sidebar
          sidebarOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Main area */}
        <div style={{ display: 'flex', flex: 1, flexDirection: 'column', overflow: 'hidden' }}>
          <Header onMenuToggle={() => setSidebarOpen(o => !o)} />
          <main style={{ flex: 1, overflowY: 'auto', padding: 24, background: 'var(--background)' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
              {children}
            </div>
          </main>
        </div>

      </div>
    </>
  );
}
