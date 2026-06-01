import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import type { Notification } from '../types'
import { Btn } from './UI'

const TYPE_META: Record<string, { icon: string; color: string }> = {
  tamper: { icon: '[!]', color: 'var(--red)'    },
  bns:    { icon: '[=]', color: 'var(--purple)'  },
  upload: { icon: '[^]', color: 'var(--blue)'    },
  yolo:   { icon: '[*]', color: 'var(--amber)'   },
  system: { icon: '[i]', color: 'var(--text3)'   }
}

const TYPE_ROUTE: Record<string, string> = {
  tamper: '/evidence', bns: '/bns', upload: '/evidence', yolo: '/detection', system: '/audit'
}

interface Props { open: boolean; onClose: () => void }

export default function NotificationPanel({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    api.getNotifications()
      .then((res) => setNotifications(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open])

  const handleClick = async (n: Notification) => {
    if (!n.read) {
      await api.markNotificationRead(n.id).catch(() => {})
      setNotifications((prev) => prev.map((x) => x.id === n.id ? { ...x, read: true } : x))
    }
    onClose()
    navigate(TYPE_ROUTE[n.type] || '/dashboard')
  }

  const markAll = async () => {
    await api.markAllNotificationsRead().catch(() => {})
    setNotifications((prev) => prev.map((x) => ({ ...x, read: true })))
    const dot = document.getElementById('notif-dot')
    if (dot) dot.style.display = 'none'
  }

  if (!open) return null

  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 140 }} onClick={onClose} />
      <div style={{ position: 'fixed', top: '56px', right: '16px', width: '360px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', zIndex: 150, boxShadow: '0 8px 24px rgba(0,0,0,.3)', maxHeight: '520px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
                  borderLeft: !n.read ? `3px solid ${n.type === 'tamper' ? 'var(--red)' : 'var(--blue)'}` : 'none'
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
                    <div style={{ fontSize: '11px', color: 'var(--text2)', lineHeight: 1.4, marginBottom: '3px', whiteSpace: 'pre-line' }}>{n.description}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: 'var(--text3)' }}>
                      <span>{new Date(n.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                      {n.case_id && <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{n.case_id}</span>}
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
