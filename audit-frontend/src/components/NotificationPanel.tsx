import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import type { Notification } from '../types'
import { Btn } from './UI'

const TYPE_META: Record<string, { icon: string; color: string }> = {
  tamper:  { icon: '[!]', color: 'var(--red)'    },
  bns:     { icon: '[=]', color: 'var(--purple)'  },
  upload:  { icon: '[^]', color: 'var(--blue)'    },
  yolo:    { icon: '[*]', color: 'var(--amber)'   },
  custody: { icon: '[>]', color: 'var(--blue)'    },
  audio:   { icon: '[~]', color: 'var(--purple)'  },
  login:   { icon: '[@]', color: 'var(--green)'   },
  system:  { icon: '[i]', color: 'var(--text3)'   }
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'var(--red)', warning: 'var(--amber)', info: 'var(--blue)'
}

// Fallback when a notification has no link of its own
const TYPE_ROUTE: Record<string, string> = {
  tamper: '/evidence', bns: '/bns', upload: '/evidence', yolo: '/detection', custody: '/evidence', audio: '/audio', login: '/users', system: '/audit'
}

function notificationUser(notification: Notification) {
  const match = notification.description.match(/^(.+?)\s+(uploaded|transferred|signed in)\b/i)
  return match?.[1] || (notification.type === 'system' || notification.type === 'tamper' ? 'System' : 'Forensic service')
}

function notificationDetails(notification: Notification) {
  if (notification.type === 'upload') {
    const file = notification.description.match(/'([^']+)'\s*\(([^)]+)\)/)
    if (file) return `${file[1]} · ${file[2]}`
  }
  return notification.description
}

function notificationDate(value: string) {
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

interface Props { open: boolean; refreshKey: number; onClose: () => void; onUnreadChange?: (count: number) => void }

export default function NotificationPanel({ open, refreshKey, onClose, onUnreadChange }: Props) {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    api.getNotifications(true)
      .then((res) => {
        setNotifications(res.data)
        onUnreadChange?.(res.data.filter((n) => !n.read).length)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open, refreshKey])

  const handleClick = async (n: Notification) => {
    if (!n.read) {
      try {
        await api.markNotificationRead(n.id)
      } catch {
        return
      }
      const next = notifications.filter((x) => x.id !== n.id)
      setNotifications(next)
      onUnreadChange?.(next.length)
    }
    onClose()
    navigate(n.link || TYPE_ROUTE[n.type] || '/dashboard')
  }

  const markAll = async () => {
    try {
      await api.markAllNotificationsRead()
    } catch {
      return
    }
    setNotifications([])
    onUnreadChange?.(0)
  }

  if (!open) return null

  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 140 }} onClick={onClose} />
      <div style={{ position: 'fixed', top: '84px', right: '16px', width: 'min(440px, calc(100vw - 32px))', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', zIndex: 150, boxShadow: '0 8px 24px rgba(0,0,0,.3)', maxHeight: '560px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>Notifications</span>
            {notifications.filter((n) => !n.read).length > 0 && (
              <span style={{ fontSize: '10px', fontWeight: 600, padding: '1px 6px', borderRadius: '10px', background: 'var(--red)', color: 'white' }}>
                {notifications.filter((n) => !n.read).length}
              </span>
            )}
          </div>
          <span style={{ color: 'var(--blue)', cursor: 'pointer', fontSize: '12px' }} onClick={markAll}>Mark all read</span>
        </div>

        {/* Body */}
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {loading && <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>Loading...</div>}
          {!loading && notifications.length === 0 && (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>No notifications</div>
          )}
          {!loading && notifications.map((n) => {
            const meta = TYPE_META[n.type] || TYPE_META.system
            return (
              <div
                key={n.id}
                onClick={() => handleClick(n)}
                style={{
                  padding: '12px 14px', borderBottom: '1px solid var(--border)', cursor: 'pointer',
                  transition: 'background .12s',
                  borderLeft: !n.read ? `3px solid ${SEVERITY_COLOR[n.severity] || 'var(--blue)'}` : 'none'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  <span style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: meta.color, flexShrink: 0, marginTop: '2px', fontWeight: 600 }}>{meta.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '2px' }}>
                      <span style={{ fontSize: '12px', fontWeight: !n.read ? 600 : 400, color: 'var(--text)' }}>{n.title}</span>
                      {!n.read && <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--blue)', flexShrink: 0 }} />}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '76px minmax(0, 1fr)', gap: '4px 8px', marginTop: '7px', fontSize: '11px', lineHeight: 1.4 }}>
                      <span style={{ color: 'var(--text3)' }}>User</span>
                      <span style={{ color: 'var(--text)', fontWeight: 500 }}>{notificationUser(n)}</span>
                      <span style={{ color: 'var(--text3)' }}>Operation</span>
                      <span style={{ color: 'var(--text2)' }}>{n.title}</span>
                      {n.case_id && <>
                        <span style={{ color: 'var(--text3)' }}>Case number</span>
                        <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)', overflowWrap: 'anywhere' }}>{n.case_number || n.case_id}</span>
                      </>}
                      <span style={{ color: 'var(--text3)' }}>Date &amp; time</span>
                      <span style={{ color: 'var(--text2)' }}>{notificationDate(n.created_at)}</span>
                      {n.type !== 'login' && <>
                        <span style={{ color: 'var(--text3)' }}>Details</span>
                        <span style={{ color: 'var(--text2)', overflowWrap: 'anywhere' }}>{notificationDetails(n)}</span>
                      </>}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <Btn size="sm" full onClick={() => { onClose(); navigate('/audit') }}>View All in Audit Log</Btn>
        </div>
      </div>
    </>
  )
}
