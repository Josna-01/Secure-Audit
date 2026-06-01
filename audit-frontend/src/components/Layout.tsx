import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { Btn } from './UI'
import NotificationPanel from './NotificationPanel'

const NAV = [
  { section: 'Main' },
  { id: '/dashboard', label: 'Dashboard', icon: 'grid' },
  { id: '/cases', label: 'Case Management', icon: 'folder' },
  { id: '/personal', label: 'Personal Space', icon: 'notes', badge: 'Private' },
  { id: '/evidence', label: 'Evidence Upload', icon: 'upload' },
  { section: 'AI Modules' },
  { id: '/detection', label: 'Object Detection', icon: 'detect' },
  { id: '/bns', label: 'BNS Classification', icon: 'law' },
  { id: '/ocr', label: 'OCR Extraction', icon: 'ocr' },
  { id: '/photo3d', label: '3D Reconstruction', icon: 'cube' },
  { id: '/audio', label: 'Audio Forensics', icon: 'audio' },
  { id: '/graph', label: 'POLE Graph', icon: 'graph' },
  { section: 'System' },
  { id: '/audit', label: 'Audit Log', icon: 'log' },
  { id: '/settings', label: 'Settings', icon: 'cog' }
]

const SVG_ICONS: Record<string, JSX.Element> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  folder: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" fill="none" stroke="currentColor" strokeWidth="1.8" />,
  notes: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="1.8" /><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="1.8" /></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" fill="none" stroke="currentColor" strokeWidth="1.8" /><polyline points="17 8 12 3 7 8" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="1.8" /></>,
  detect: <><circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" strokeWidth="1.8" /></>,
  law: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="1.8" /></>,
  ocr: <><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="9" y1="9" x2="15" y2="9" stroke="currentColor" strokeWidth="1.8" /><line x1="9" y1="12" x2="15" y2="12" stroke="currentColor" strokeWidth="1.8" /></>,
  cube: <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" fill="none" stroke="currentColor" strokeWidth="1.8" />,
  audio: <><path d="M3 18v-6a9 9 0 0 1 18 0v6" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z" fill="none" stroke="currentColor" strokeWidth="1.8" /></>,
  graph: <><circle cx="18" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><circle cx="6" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><circle cx="18" cy="19" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke="currentColor" strokeWidth="1.8" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke="currentColor" strokeWidth="1.8" /></>,
  log: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" fill="none" stroke="currentColor" strokeWidth="1.8" />,
  cog: <><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M19.07 4.93A10 10 0 1 0 4.93 19.07 10 10 0 0 0 19.07 4.93z" fill="none" stroke="currentColor" strokeWidth="1.8" /></>,
  sun: <><circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" strokeWidth="1.8" /><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" strokeWidth="1.8" /><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" strokeWidth="1.8" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" strokeWidth="1.8" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" strokeWidth="1.8" /><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" strokeWidth="1.8" /><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" strokeWidth="1.8" /></>,
  moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="none" stroke="currentColor" strokeWidth="1.8" />,
  bell: <><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M13.73 21a2 2 0 0 1-3.46 0" fill="none" stroke="currentColor" strokeWidth="1.8" /></>,
  plus: <><line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="1.8" /><line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="1.8" /></>
}

function Icon({ name, size = 15 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
      {SVG_ICONS[name]}
    </svg>
  )
}

function BadgeChip({ label }: { label: string }) {
  const isLive = label === 'Live'
  const isPrivate = label === 'Private'
  return (
    <span style={{
      marginLeft: 'auto', fontSize: '9px', fontWeight: 600, padding: '2px 7px', borderRadius: '10px',
      background: isLive ? 'var(--green-bg)' : isPrivate ? 'var(--amber-bg)' : 'var(--bg4)',
      color: isLive ? 'var(--green)' : isPrivate ? 'var(--amber)' : 'var(--text3)'
    }}>
      {label}
    </span>
  )
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()

  const initials = user?.name?.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'SA'

  return (
    <div style={{ width: '224px', background: 'var(--bg2)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0, height: '100vh' }}>
      {/* Logo */}
      <div style={{ padding: '16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ width: '34px', height: '34px', background: 'var(--blue)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', flexShrink: 0, fontSize: '16px' }}>
          <svg width="18" height="18" viewBox="0 0 24 24"><path d="M12 2L3 6v6c0 5.25 3.8 10.15 9 11.5 5.2-1.35 9-6.25 9-11.5V6L12 2z" fill="white" /></svg>
        </div>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)', lineHeight: 1.2 }}>Secure Audits</div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '8px', overflowY: 'auto' }}>
        {NAV.map((item, i) => {
          if ('section' in item) {
            return (
              <div key={i} style={{ fontSize: '10px', color: 'var(--text3)', letterSpacing: '.8px', textTransform: 'uppercase', padding: '10px 8px 4px', marginTop: '4px' }}>
                {item.section}
              </div>
            )
          }
          const isActive = location.pathname === item.id || location.pathname.startsWith(item.id + '/')
          return (
            <div
              key={item.id}
              onClick={() => navigate(item.id!)}
              style={{
                display: 'flex', alignItems: 'center', gap: '9px', padding: '8px 10px',
                borderRadius: 'var(--r)', cursor: 'pointer', color: isActive ? 'var(--blue)' : 'var(--text2)',
                fontSize: '13px', transition: 'all .12s', marginBottom: '1px', userSelect: 'none',
                background: isActive ? 'var(--blue-bg)' : 'transparent', fontWeight: isActive ? 500 : 400
              }}
              onMouseEnter={(e) => { if (!isActive) { e.currentTarget.style.background = 'var(--bg3)'; e.currentTarget.style.color = 'var(--text)' } }}
              onMouseLeave={(e) => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text2)' } }}
            >
              <Icon name={item.icon!} size={15} />
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && <BadgeChip label={item.badge} />}
            </div>
          )
        })}
      </nav>

      {/* User */}
      <div
        onClick={() => navigate('/profile')}
        style={{ padding: '12px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <div style={{ width: '30px', height: '30px', borderRadius: '50%', background: 'var(--blue-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 600, color: 'var(--blue)', flexShrink: 0 }}>
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {user?.name || 'Investigator'}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text3)' }}>{user?.role === 'admin' ? 'Administrator' : 'Investigator'} · {user?.department || ''}</div>
        </div>
        <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--green)', flexShrink: 0 }} />
      </div>
    </div>
  )
}

export function Topbar({ title, onNewCase }: { title: string; onNewCase: () => void }) {
  const { theme, toggleTheme } = useTheme()
  const [notifOpen, setNotifOpen] = useState(false)

  return (
    <>
      <div style={{ height: '52px', background: 'var(--bg2)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', padding: '0 20px', gap: '12px', flexShrink: 0 }}>
        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>{title}</div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--green)' }}>
            <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--green)' }} />
            System Online
          </div>
          <Btn size="sm" onClick={toggleTheme}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={13} />
            {theme === 'dark' ? 'Light' : 'Dark'}
          </Btn>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', borderRadius: 'var(--r)', border: '1px solid var(--border)', background: 'var(--bg3)', cursor: 'pointer', transition: 'all .15s' }}
            onClick={() => setNotifOpen((o) => !o)}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
          >
            <Icon name="bell" size={14} />
            <div id="notif-dot" style={{ position: 'absolute', top: '4px', right: '4px', width: '7px', height: '7px', borderRadius: '50%', background: 'var(--red)', border: '1.5px solid var(--bg2)' }} />
          </div>
          <Btn variant="primary" size="sm" onClick={onNewCase}>
            <Icon name="plus" size={13} />
            New Case
          </Btn>
        </div>
      </div>
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  )
}

export function AppShell({ children, title }: { children: React.ReactNode; title: string }) {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <Topbar title={title} onNewCase={() => navigate('/cases/new')} />
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {children}
        </div>
      </div>
    </div>
  )
}
