import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, Btn, Badge, Spinner, AlertBox, InfoRow } from '../components/UI'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'
import type { User, Case, AuditLog } from '../types'
import { format } from 'date-fns'

// ── RBAC DEFINITION ────────────────────────────────────────────────────────
interface PermissionDef {
  key: string
  label: string
}

const ALL_PERMISSIONS: PermissionDef[] = [
  { key: 'create_cases', label: 'Create Cases' },
  { key: 'upload_evidence', label: 'Upload Evidence' },
  { key: 'run_ai', label: 'Run AI Analysis' },
  { key: 'access_logs', label: 'Access Audit Logs' },
  { key: 'user_mgmt', label: 'User Management' },
  { key: 'sys_settings', label: 'System Settings' }
]

const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['create_cases', 'upload_evidence', 'run_ai', 'access_logs', 'user_mgmt', 'sys_settings'],
  lead_investigator: ['create_cases', 'upload_evidence', 'run_ai', 'access_logs'],
  investigator: ['create_cases', 'upload_evidence', 'run_ai', 'access_logs'],
  analyst: ['upload_evidence', 'run_ai', 'access_logs'],
  viewer: ['access_logs']
}

const ROLE_SUMMARIES: Record<string, string> = {
  admin: 'Full platform access including user management, audit oversight and system administration.',
  lead_investigator: 'Can manage investigations, assign cases and supervise investigators.',
  investigator: 'Can create and manage assigned cases, upload evidence and run AI analysis.',
  analyst: 'Can perform OCR, object detection, audio forensics and 3D reconstruction analysis.',
  viewer: 'Read-only access to cases, evidence, reports and audit records.'
}

// ── DYNAMIC UNIT MAP ────────────────────────────────────────────────────────
const getUnit = (role: string) => {
  const r = role?.toLowerCase()
  if (r === 'admin') return 'Administration'
  if (r === 'lead_investigator') return 'Investigation Unit'
  if (r === 'investigator') return 'Investigation Unit'
  if (r === 'analyst' || r === 'forensic_analyst') return 'Digital Forensics Unit'
  return 'Legal Review Unit'
}

// ── DYNAMIC ROLE DETAILS FALLBACKS ──────────────────────────────────────────
const getRoleDetailsFallback = (user: User) => {
  const roleLower = user.role?.toLowerCase()
  if (roleLower === 'admin') {
    return {
      badgeId: user.badge_number || user.badge_id || 'ADMIN 001',
      department: user.department || 'Headquarters',
      phone: user.phone || '+91 98765 43210'
    }
  } else if (roleLower === 'lead_investigator') {
    return {
      badgeId: user.badge_number || user.badge_id || 'LINV 007',
      department: user.department || 'Special Crimes',
      phone: user.phone || '+91 97654 32109'
    }
  } else if (roleLower === 'investigator') {
    return {
      badgeId: user.badge_number || user.badge_id || 'INV 012',
      department: user.department || 'Cyber Crimes',
      phone: user.phone || '+91 91234 56789'
    }
  } else if (roleLower === 'analyst' || roleLower === 'forensic_analyst') {
    return {
      badgeId: user.badge_number || user.badge_id || 'ANL 008',
      department: user.department || 'Forensics Lab',
      phone: user.phone || '+91 94567 12345'
    }
  } else {
    return {
      badgeId: user.badge_number || user.badge_id || 'VWR 003',
      department: user.department || 'Legal',
      phone: user.phone || '+91 99887 76655'
    }
  }
}

// ── SESSION INFORMATION CONFIG ─────────────────────────────────────────────
const getLoginMethod = (role: string) => {
  const roleLower = role?.toLowerCase()
  return (roleLower === 'admin' || roleLower === 'lead_investigator' || roleLower === 'investigator') 
    ? 'OTP Verified' 
    : 'Password'
}

const formatDateTime = (ts?: string) => {
  if (!ts) return '—'
  try {
    return format(new Date(ts), 'dd MMM yyyy, hh:mm a')
  } catch {
    return ts
  }
}

export function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cases, setCases] = useState<Case[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])

  // Statistics State
  const [stats, setStats] = useState({
    casesAssigned: 0,
    evidenceUploaded: 0,
    aiAnalysesRun: 0,
    lastActive: 'Active Now'
  })

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }

    setLoading(true)
    Promise.all([
      api.getCases(),
      api.getAuditLogs({ user_id: user.id, page: 1 })
    ]).then(([casesRes, logsRes]) => {
      setCases(casesRes.data)
      setLogs(logsRes.data)

      // Calculate Statistics Dynamically
      const username = user.full_name || user.name || ''
      const roleLower = user.role?.toLowerCase()

      // Cases Assigned
      const userCases = casesRes.data.filter((c: Case) => 
        c.investigator_id === user.id || 
        (c.investigator_name && c.investigator_name.toLowerCase() === username.toLowerCase())
      )
      const casesCount = roleLower === 'admin' ? casesRes.data.length : userCases.length

      // User specific logs
      const userLogs = logsRes.data

      // Evidence Uploads
      const uploadCount = userLogs.filter((l: AuditLog) => l.action === 'Evidence Upload').length

      // AI Analysis runs
      const aiCount = userLogs.filter((l: AuditLog) => 
        l.action === 'YOLO Scan' || 
        l.action === 'BNS Classified' || 
        l.action === 'OCR Extraction'
      ).length

      // Last Active
      let lastActiveText = 'Active Now'
      if (userLogs.length > 0) {
        try {
          lastActiveText = format(new Date(userLogs[0].created_at), 'dd MMM yyyy, HH:mm')
        } catch {
          lastActiveText = 'Active Now'
        }
      }

      setStats({
        casesAssigned: casesCount,
        evidenceUploaded: uploadCount,
        aiAnalysesRun: aiCount,
        lastActive: lastActiveText
      })

    }).catch((err) => {
      console.error('Failed to load profile dashboard details:', err)
      setError('Failed to fetch platform metrics.')
    }).finally(() => {
      setLoading(false)
    })
  }, [user, navigate])

  if (loading) {
    return (
      <AppShell title="User Profile">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
          <Spinner size={32} />
        </div>
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="User Profile">
        <div style={{ padding: '20px' }}>
          <AlertBox type="error">{error}</AlertBox>
        </div>
      </AppShell>
    )
  }

  if (!user) return null

  // Initials
  const initials = ((user.full_name || user.name || 'SA') as string)
    .split(' ')
    .map((w: string) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const fallbackData = getRoleDetailsFallback(user)
  const loginMethod = getLoginMethod(user.role)
  const lastLoginVal = user.last_login || user.last_sign_in_at
  const lastLoginDisplay = lastLoginVal ? formatDateTime(lastLoginVal) : 'First Session'
  const sessionStartVal = localStorage.getItem('sa_session_start')
  const sessionStartedDisplay = sessionStartVal ? formatDateTime(sessionStartVal) : 'Active Now'

  // Dynamic Permissions calculation
  const roleLower = user.role?.toLowerCase() || 'viewer'
  const userPermissions = ROLE_PERMISSIONS[roleLower] || ROLE_PERMISSIONS['viewer']
  const grantedCount = ALL_PERMISSIONS.filter(p => userPermissions.includes(p.key)).length

  // Filter logs for user activity timeline
  const userActivities = logs.slice(0, 5)

  // Access Level Highlight Box Styles
  const roleBorderColors: Record<string, string> = {
    admin: 'var(--purple)',
    lead_investigator: 'var(--blue)',
    investigator: 'var(--blue)',
    analyst: 'var(--amber)',
    viewer: 'var(--text3)'
  }

  const roleBgColors: Record<string, string> = {
    admin: 'var(--purple-bg)',
    lead_investigator: 'var(--blue-bg)',
    investigator: 'var(--blue-bg)',
    analyst: 'var(--amber-bg)',
    viewer: 'var(--bg4)'
  }

  const actionColors: Record<string, string> = {
    'Login Successful': 'var(--text3)',
    'Logout Successful': 'var(--text3)',
    'BNS Classified': 'var(--purple)',
    'YOLO Scan': 'var(--amber)',
    'Tamper Detected': 'var(--red)',
    'Hash Verified': 'var(--green)',
    'Evidence Upload': 'var(--blue)',
    'Case Created': 'var(--blue)',
    'Login': 'var(--text3)',
    'Logout': 'var(--text3)'
  }

  return (
    <AppShell title="User Profile">
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '20px',
        alignItems: 'start'
      }}>
        
        {/* LEFT COLUMN: IDENTITY & STATS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Identity Card */}
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: 'var(--blue-dim)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '20px',
                fontWeight: 700,
                color: 'var(--blue)',
                flexShrink: 0
              }}>
                {initials}
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)', margin: '0 0 4px 0' }}>
                  {user.full_name || user.name}
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Badge label={user.role === 'viewer' ? 'Viewer' : (user.role?.replace('_', ' ') || 'Investigator')} />
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--green)', fontWeight: 500 }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--green)' }} />
                    Active
                  </span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <InfoRow label="Badge / ID" value={fallbackData.badgeId} />
              <InfoRow label="Department" value={fallbackData.department} />
              <InfoRow label="Unit" value={getUnit(user.role)} />
              <InfoRow label="Role" value={user.role === 'viewer' ? 'Viewer' : (user.role?.replace('_', ' ') || 'Investigator')} />
              <InfoRow label="Email" value={user.email} />
              <InfoRow label="Contact" value={fallbackData.phone} />
            </div>

            <div style={{ marginTop: '24px' }}>
              <Btn
                variant="danger"
                full
                onClick={() => {
                  if (confirm('Are you sure you want to log out of the platform?')) {
                    logout()
                    navigate('/login')
                  }
                }}
              >
                Log Out
              </Btn>
            </div>
          </Card>

          {/* Statistics Card */}
          <Card>
            <CardTitle>Platform Statistics</CardTitle>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Cases Assigned</div>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--text)' }}>
                  {stats.casesAssigned}
                </div>
              </div>
              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Evidence Uploads</div>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--blue)' }}>
                  {stats.evidenceUploaded}
                </div>
              </div>
              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>AI Analyses</div>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--purple)' }}>
                  {stats.aiAnalysesRun}
                </div>
              </div>
              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Last Active</div>
                <div style={{ fontSize: '11px', fontWeight: 500, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {stats.lastActive}
                </div>
              </div>
            </div>
          </Card>
          
        </div>

        {/* CENTER COLUMN: SESSION & PERMISSIONS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Session Information */}
          <Card>
            <CardTitle>Session Information</CardTitle>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div style={{
                background: 'rgba(0, 112, 243, 0.05)',
                border: '1.5px solid var(--blue)',
                borderRadius: 'var(--r)',
                padding: '12px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Current Session</div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--blue)' }}>Active</div>
              </div>
              <div style={{
                background: 'rgba(0, 200, 83, 0.05)',
                border: '1.5px solid var(--green)',
                borderRadius: 'var(--r)',
                padding: '12px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Login Method</div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--green)' }}>{loginMethod}</div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <InfoRow label="Last Login" value={lastLoginDisplay} />
              <InfoRow label="Session Started" value={sessionStartedDisplay} />
            </div>
          </Card>

          {/* Permissions */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px' }}>
                Permissions
              </span>
              <span style={{ fontSize: '10px', color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
                {grantedCount} / {ALL_PERMISSIONS.length} granted
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {ALL_PERMISSIONS.map((perm) => {
                const isGranted = userPermissions.includes(perm.key)
                return (
                  <div
                    key={perm.key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      background: 'var(--bg3)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r)',
                      opacity: isGranted ? 1 : 0.45
                    }}
                  >
                    <span style={{ fontSize: '12px', color: 'var(--text2)', fontWeight: 500 }}>
                      {perm.label}
                    </span>
                    <span style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      color: isGranted ? 'var(--green)' : 'var(--text3)'
                    }}>
                      {isGranted ? 'Granted' : 'Denied'}
                    </span>
                  </div>
                )
              })}
            </div>
          </Card>
          
        </div>

        {/* RIGHT COLUMN: RECENT ACTIVITY & ROLE SUMMARY */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Recent Activity */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px' }}>
                Recent Activity
              </span>
              <span style={{ fontSize: '10px', color: 'var(--text3)' }}>
                {userActivities.length} events
              </span>
            </div>

            {userActivities.length === 0 ? (
              <div style={{ padding: '24px 10px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px', lineHeight: '1.6' }}>
                No recent activity found.<br />Activity will appear here once actions are performed.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative', paddingLeft: '8px' }}>
                {/* Timeline vertical bar */}
                <div style={{
                  position: 'absolute',
                  left: '14px',
                  top: '8px',
                  bottom: '8px',
                  width: '1px',
                  background: 'var(--border2)'
                }} />

                {userActivities.map((log) => {
                  const logTime = format(new Date(log.created_at), 'HH:mm')
                  const actionColor = actionColors[log.action] || 'var(--blue)'
                  return (
                    <div key={log.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', position: 'relative', zIndex: 1 }}>
                      {/* Timeline dot */}
                      <div style={{
                        width: '13px',
                        height: '13px',
                        borderRadius: '50%',
                        border: `2px solid ${actionColor}`,
                        background: 'var(--bg2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '3px'
                      }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text2)', display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{log.action}</span>
                          <span style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--text3)', flexShrink: 0 }}>{logTime}</span>
                        </div>
                        {log.case_id && (
                          <div style={{ fontSize: '10px', fontFamily: 'var(--mono)', color: 'var(--text3)', marginTop: '2px' }}>
                            {log.case_id}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <div style={{ marginTop: '20px', borderTop: '1px solid var(--border)', paddingTop: '12px', textAlign: 'center' }}>
              <span
                onClick={() => navigate('/audit')}
                style={{
                  fontSize: '11px',
                  color: 'var(--blue)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                  letterSpacing: '.4px'
                }}
              >
                View All Activity
              </span>
            </div>
          </Card>

          {/* Role Summary */}
          <Card>
            <CardTitle>Role Summary</CardTitle>
            <div style={{
              background: roleBgColors[roleLower] || 'var(--bg4)',
              border: `1.5px solid ${roleBorderColors[roleLower] || 'var(--border)'}`,
              borderRadius: 'var(--r)',
              padding: '16px'
            }}>
              <div style={{
                fontSize: '11px',
                fontWeight: 700,
                color: roleBorderColors[roleLower] || 'var(--text2)',
                textTransform: 'uppercase',
                letterSpacing: '.6px',
                marginBottom: '8px'
              }}>
                {(user.role?.replace('_', ' ') || 'Investigator')} Capabilities
              </div>
              <p style={{
                fontSize: '12px',
                color: 'var(--text)',
                lineHeight: '1.6',
                margin: 0
              }}>
                {ROLE_SUMMARIES[roleLower] || ROLE_SUMMARIES['viewer']}
              </p>
            </div>
          </Card>

        </div>

      </div>
    </AppShell>
  )
}
