import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { Btn } from './UI'
import NotificationPanel from './NotificationPanel'

const NAV = [
  { section: 'Main Operations' },
  { id: '/dashboard', label: 'Dashboard', icon: 'grid' },
  { id: '/cases', label: 'Case Management', icon: 'folder' },
  { id: '/personal', label: 'Personal Space', icon: 'notes', badge: 'Private' },
  { id: '/evidence', label: 'Evidence Upload', icon: 'upload' },
  { id: '/blockchain', label: 'Blockchain Ledger', icon: 'cube' },
  { section: 'Forensic AI Engines' },
  { id: '/detection', label: 'Object Detection', icon: 'detect' },
  { id: '/bns', label: 'BNS Classification', icon: 'law' },
  { id: '/ocr', label: 'OCR Extraction', icon: 'ocr' },
  { id: '/photo3d', label: '3D Reconstruction', icon: 'cube' },
  { id: '/audio', label: 'Audio Forensics', icon: 'audio' },
  { id: '/graph', label: 'POLE Graph', icon: 'graph' },
  { section: 'Security & Governance' },
  { id: '/audit', label: 'Audit Trail', icon: 'log' }
]

const SVG_ICONS: Record<string, JSX.Element> = {
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
    </>
  ),
  folder: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />,
  notes: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <polyline points="14 2 14 8 20 8" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  upload: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <polyline points="17 8 12 3 7 8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  detect: (
    <>
      <circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  law: (
    <>
      <path d="M12 3v18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M6 8l6-3 6 3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 8l-3 7h6L6 8z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M18 8l-3 7h6l-3-7z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </>
  ),
  ocr: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <line x1="7" y1="8" x2="17" y2="8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="7" y1="12" x2="17" y2="12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="7" y1="16" x2="13" y2="16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  cube: <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />,
  audio: (
    <>
      <path d="M3 18v-6a9 9 0 0 1 18 0v6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </>
  ),
  graph: (
    <>
      <circle cx="18" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="6" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="18" cy="19" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  log: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
  cog: (
    <>
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M19.07 4.93A10 10 0 1 0 4.93 19.07 10 10 0 0 0 19.07 4.93z" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
  bell: (
    <>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  plus: (
    <>
      <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </>
  )
}

function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
      {SVG_ICONS[name]}
    </svg>
  )
}

function BadgeChip({ label }: { label: string }) {
  const isPrivate = label === 'Private'
  return (
    <span style={{
      marginLeft: 'auto',
      fontSize: '9.5px',
      fontWeight: 700,
      padding: '2px 8px',
      borderRadius: 'var(--r-pill)',
      background: isPrivate ? 'var(--amber-bg)' : 'var(--blue-bg)',
      color: isPrivate ? 'var(--amber)' : 'var(--blue)',
      border: `1px solid ${isPrivate ? 'var(--amber-border)' : 'var(--blue-border)'}`,
      letterSpacing: '0.02em'
    }}>
      {label}
    </span>
  )
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()

  const visibleNav = [...NAV]
  if (user?.role === 'Admin' || user?.role?.toLowerCase() === 'admin') {
    visibleNav.push({ id: '/users', label: 'User Management', icon: 'cog' })
  }

  const getDisplayRole = (roleKey: string) => {
    const map: Record<string, string> = {
      admin: 'Admin',
      lead_investigator: 'Lead Investigator',
      investigator: 'Investigator',
      analyst: 'Forensic Analyst',
      viewer: 'Viewer'
    }
    return map[roleKey?.toLowerCase()] || roleKey || 'Investigator'
  }

  const initials = ((user?.full_name || user?.name || 'SA') as string)
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <aside style={{
      width: '240px',
      background: 'var(--bg2)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      height: '100vh',
      boxShadow: 'var(--shadow-xs)',
      zIndex: 20
    }}>
      {/* Brand Header */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div style={{
          width: '38px',
          height: '38px',
          background: 'var(--hero-gradient)',
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ffffff',
          flexShrink: 0,
          boxShadow: '0 4px 10px rgba(37, 99, 235, 0.35)'
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L3 6v6c0 5.25 3.8 10.15 9 11.5 5.2-1.35 9-6.25 9-11.5V6L12 2z" fill="rgba(255,255,255,0.2)" />
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <div>
          <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em', lineHeight: 1.15 }}>
            Secure Audit
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <nav style={{ flex: 1, padding: '12px 10px', overflowY: 'auto' }}>
        {visibleNav.map((item, i) => {
          if ('section' in item) {
            return (
              <div key={i} style={{
                fontSize: '10px',
                fontWeight: 700,
                color: 'var(--text3)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                padding: '14px 10px 6px',
                marginTop: i === 0 ? 0 : '6px'
              }}>
                {item.section}
              </div>
            )
          }
          const isActive = location.pathname === item.id || (item.id !== '/dashboard' && location.pathname.startsWith(item.id + '/'))
          return (
            <div
              key={item.id}
              onClick={() => navigate(item.id!)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '9px 12px',
                borderRadius: 'var(--r)',
                cursor: 'pointer',
                color: isActive ? 'var(--blue)' : 'var(--text2)',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                transition: 'all 0.15s ease',
                marginBottom: '2px',
                userSelect: 'none',
                background: isActive ? 'var(--blue-bg)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--blue)' : '3px solid transparent'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'var(--bg3)'
                  e.currentTarget.style.color = 'var(--text)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text2)'
                }
              }}
            >
              <span style={{ color: isActive ? 'var(--blue)' : 'var(--text3)', display: 'flex' }}>
                <Icon name={item.icon!} size={16} />
              </span>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && <BadgeChip label={item.badge} />}
            </div>
          )
        })}
      </nav>

      {/* User Profile Footer */}
      <div
        onClick={() => navigate('/profile')}
        style={{
          padding: '14px 16px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          cursor: 'pointer',
          background: 'var(--bg3)',
          transition: 'background 0.15s ease'
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
      >
        <div style={{
          width: '34px',
          height: '34px',
          borderRadius: '50%',
          background: 'var(--blue-dim)',
          border: '1.5px solid var(--blue-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '12px',
          fontWeight: 700,
          color: 'var(--blue)',
          flexShrink: 0
        }}>
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {user?.full_name || user?.name || 'Investigator'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {getDisplayRole(user?.role || '')} {user?.department ? `· ${user.department}` : ''}
          </div>
        </div>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: 'var(--green)',
          boxShadow: '0 0 6px var(--green)',
          flexShrink: 0
        }} title="Officer Status: Active" />
      </div>
    </aside>
  )
}

export function Topbar({ title, onNewCase }: { title: string; onNewCase: () => void }) {
  const { theme, toggleTheme } = useTheme()
  const [notifOpen, setNotifOpen] = useState(false)
  const { user } = useAuth()

  return (
    <>
      <header style={{
        height: '58px',
        background: 'var(--bg2)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        gap: '16px',
        flexShrink: 0,
        zIndex: 10,
        boxShadow: 'var(--shadow-xs)'
      }}>
        {/* Page Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <h1 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.01em', margin: 0 }}>
            {title}
          </h1>
        </div>

        {/* Right Tools */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Security Status Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11.5px',
            fontWeight: 600,
            color: 'var(--green)',
            padding: '4px 10px',
            background: 'var(--green-bg)',
            border: '1px solid var(--green-border)',
            borderRadius: 'var(--r-pill)'
          }}>
            <span style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: 'var(--green)',
              boxShadow: '0 0 6px var(--green)'
            }} />
            Ledger & AI Synced
          </div>

          {/* Theme Toggle */}
          <Btn size="sm" variant="default" onClick={toggleTheme} style={{ padding: '6px 12px' }}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14} />
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </Btn>

          {/* Notification Button */}
          <div
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: 'var(--r)',
              border: '1px solid var(--border)',
              background: 'var(--bg3)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              color: 'var(--text)'
            }}
            onClick={() => setNotifOpen((o) => !o)}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)'; e.currentTarget.style.borderColor = 'var(--border2)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg3)'; e.currentTarget.style.borderColor = 'var(--border)' }}
            title="Notifications & Tamper Alerts"
          >
            <Icon name="bell" size={16} />
            <div id="notif-dot" style={{
              position: 'absolute',
              top: '6px',
              right: '6px',
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: 'var(--red)',
              border: '1.5px solid var(--bg2)'
            }} />
          </div>

          {/* New Case Button */}
          {user?.can_create_case && (
            <Btn variant="primary" size="sm" onClick={onNewCase}>
              <Icon name="plus" size={14} />
              <span>New Case</span>
            </Btn>
          )}
        </div>
      </header>
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  )
}

export function AppShell({ children, title }: { children: React.ReactNode; title: string }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <Topbar title={title} onNewCase={() => navigate('/cases/new')} />
        <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '24px 28px', boxSizing: 'border-box' }}>
          {children}
        </main>
      </div>
    </div>
  )
}
