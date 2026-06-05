import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, Badge, ProgressBar } from '../components/UI'
import { api } from '../services/api'
import type { Case, AuditLog } from '../types'
import { format } from 'date-fns'
import { useAuth } from '../context/AuthContext'

interface Stats {
  active: number
  total_evidence: number
  tamper_alerts?: number
  bns_classified?: number
  ai_analyses?: number
  my_audit_logs?: number
  total_users?: number
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const role = user?.role || 'Investigator'
  const [stats, setStats] = useState<Stats | null>(null)
  const [cases, setCases] = useState<Case[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getCaseStats(),
      api.getCases({ per_page: 8 }),
      api.getAuditLogs({ page: 1 })
    ]).then(([statsRes, casesRes, logsRes]) => {
      setStats(statsRes.data)
      setCases(casesRes.data)
      setLogs(logsRes.data)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filteredCases = cases.filter((c) => {
    const matchSearch = c.case_number.toLowerCase().includes(search.toLowerCase()) ||
      c.title.toLowerCase().includes(search.toLowerCase())
    const matchFilter = filter === 'All' || c.status === filter
    return matchSearch && matchFilter
  }).slice(0, 6)

  const actionColors: Record<string, string> = {
    'Login Successful': 'var(--text3)',
    'Logout Successful': 'var(--text3)',
    'BNS Classified': 'var(--purple)',
    'YOLO Scan': 'var(--amber)',
    'Tamper Detected': 'var(--red)',
    'Hash Verified': 'var(--green)',
    'Evidence Upload': 'var(--blue)',
    'Case Created': 'var(--blue)',
    'Case Access': 'var(--text2)',
    'Login': 'var(--text3)',
    'Logout': 'var(--text3)'
  }

  const statCards = role === 'Admin' ? [
    { label: 'Active Cases',    value: stats?.active ?? '—',           sub: 'Click to view',       color: 'var(--green)',  page: '/cases',    red: false },
    { label: 'Evidence Files',  value: stats?.total_evidence ?? '—',    sub: 'All uploaded files',  color: 'var(--green)',  page: '/evidence', red: false },
    { label: 'Tamper Alerts',   value: stats?.tamper_alerts ?? '—',     sub: 'Requires review',     color: 'var(--red)',    page: '_notif',    red: true  },
    { label: 'BNS Classified',  value: stats?.bns_classified ?? '—',    sub: 'Total classified',    color: 'var(--text3)',  page: '/bns',      red: false },
  ] : [
    { label: 'My Cases',        value: stats?.active ?? '—',           sub: 'Cases created by me', color: 'var(--green)',  page: '/cases',    red: false },
    { label: 'My Evidence',     value: stats?.total_evidence ?? '—',    sub: 'My evidence uploads', color: 'var(--green)',  page: '/evidence', red: false },
    { label: 'My AI Analyses',  value: stats?.ai_analyses ?? '—',       sub: 'AI analyses run by me',color: 'var(--text3)',  page: '/detection',red: false },
    { label: 'My Audit Activity', value: stats?.my_audit_logs ?? '—',     sub: 'My audit log count',  color: 'var(--text3)',  page: '/audit',    red: false },
  ]

  return (
    <AppShell title="Dashboard">
      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '12px', marginBottom: '20px' }}>
        {statCards.map((s) => (
          <div
            key={s.label}
            onClick={() => s.page === '_notif' ? {} : navigate(s.page)}
            style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', padding: '16px', cursor: 'pointer', transition: 'border .15s' }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border2)' }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: '6px' }}>{s.label}</div>
            <div style={{ fontSize: '26px', fontWeight: 700, color: s.red ? 'var(--red)' : 'var(--text)', fontFamily: 'var(--mono)', lineHeight: 1 }}>
              {loading ? '...' : s.value}
            </div>
            <div style={{ fontSize: '11px', color: s.color, marginTop: '6px' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Tamper Banner */}
      {role === 'Admin' && (stats?.tamper_alerts ?? 0) > 0 && (
        <div
          onClick={() => navigate('/evidence')}
          style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: 'var(--red-bg)', border: '1px solid var(--red)', borderRadius: 'var(--r)', marginBottom: '16px', cursor: 'pointer' }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '.85' }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
        >
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--red)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--red)' }}>{stats?.tamper_alerts} Tampered File{(stats?.tamper_alerts ?? 0) > 1 ? 's' : ''} Detected</div>
            <div style={{ fontSize: '11px', color: 'var(--red)', opacity: .8, marginTop: '1px' }}>Requires immediate review — click to view evidence</div>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--red)', fontWeight: 500, whiteSpace: 'nowrap' }}>View Alerts</span>
        </div>
      )}

      {/* Quick Actions */}
      <Card style={{ marginBottom: '16px', padding: '12px 16px' }}>
        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: '10px' }}>Quick Actions</div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Btn variant="primary" size="sm" onClick={() => navigate('/cases/new')}>New Case</Btn>
          <Btn size="sm" onClick={() => navigate('/evidence')}>Upload Evidence</Btn>
          <Btn size="sm" onClick={() => navigate('/detection')}>Run Detection</Btn>
          <Btn size="sm" onClick={() => navigate('/audit')}>View Audit Log</Btn>
        </div>
      </Card>

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '16px' }}>
        {/* Left: Cases */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Cases</CardTitle>
            <Btn size="xs" onClick={() => navigate('/cases')}>View All</Btn>
          </CardHeader>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input
              value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search cases..."
              style={{ flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '6px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
            />
            <select
              value={filter} onChange={(e) => setFilter(e.target.value)}
              style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '6px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
            >
              {['All', 'Active', 'Open', 'Pending', 'Critical', 'Closed'].map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          {loading ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>Loading...</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr>
                    {['Case ID', 'Title', 'Type', 'Status', ''].map((h) => (
                      <th key={h} style={{ textAlign: 'left', padding: '7px 10px', color: 'var(--text3)', fontWeight: 500, borderBottom: '1px solid var(--border)', fontSize: '11px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredCases.length === 0 && (
                    <tr><td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)' }}>No cases found</td></tr>
                  )}
                  {filteredCases.map((c) => (
                    <tr key={c.id}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                      <td
                        style={{ padding: '8px 10px', fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--blue)', fontWeight: 500, borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                        onClick={() => navigate(`/cases/${c.id}`)}
                      >{c.case_number}</td>
                      <td style={{ padding: '8px 10px', color: 'var(--text)', fontWeight: 500, borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => navigate(`/cases/${c.id}`)}>{c.title}</td>
                      <td style={{ padding: '8px 10px', color: 'var(--text2)', borderBottom: '1px solid var(--border)' }}>{c.offence_type}</td>
                      <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)' }}><Badge label={c.status} /></td>
                      <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>
                        <Btn size="xs" onClick={() => navigate(`/cases/${c.id}`)}>Open</Btn>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Right col */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Audit Feed */}
          <Card>
            <CardHeader>
              <CardTitle>Live Audit Feed</CardTitle>
              <Btn size="xs" onClick={() => navigate('/audit')}>Full Log</Btn>
            </CardHeader>
            {loading ? (
              <div style={{ color: 'var(--text3)', fontSize: '12px' }}>Loading...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {logs.slice(0, 7).map((log) => (
                  <div key={log.id}
                    style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '5px 6px', borderRadius: 'var(--r)', fontSize: '12px', cursor: log.case_id ? 'pointer' : 'default' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                    onClick={() => log.case_id && navigate(`/cases/${log.case_id}`)}
                  >
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0, marginTop: '5px', background: actionColors[log.action] || 'var(--blue)' }} />
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)', flexShrink: 0, minWidth: '46px' }}>
                      {format(new Date(log.created_at), 'HH:mm')}
                    </div>
                    <div>
                      <span style={{ color: 'var(--blue)', fontWeight: 500 }}>{log.user_name}</span>
                      {' '}<span style={{ color: 'var(--text2)' }}>{log.action}</span>
                      {log.case_id && <span style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)' }}> · {log.case_id}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Hash Integrity (Admin Only) */}
          {role === 'Admin' && (
            <Card>
              <CardHeader>
                <CardTitle>Hash Integrity</CardTitle>
                <span style={{ fontSize: '10px', color: 'var(--green)' }}>Verified</span>
              </CardHeader>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'var(--bg3)', borderRadius: 'var(--r)' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text2)' }}>Total Files</span>
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--text)' }}>{stats?.total_evidence ?? '—'}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'var(--green-bg)', borderRadius: 'var(--r)' }}>
                  <span style={{ fontSize: '12px', color: 'var(--green)' }}>Verified</span>
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--green)' }}>{(stats?.total_evidence ?? 0) - (stats?.tamper_alerts ?? 0)}</span>
                </div>
                {(stats?.tamper_alerts ?? 0) > 0 && (
                  <div
                    onClick={() => navigate('/evidence')}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'var(--red-bg)', borderRadius: 'var(--r)', cursor: 'pointer' }}
                    onMouseEnter={(e) => { e.currentTarget.style.opacity = '.8' }}
                    onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
                  >
                    <span style={{ fontSize: '12px', color: 'var(--red)' }}>Tampered</span>
                    <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--red)' }}>{stats?.tamper_alerts}</span>
                  </div>
                )}
              </div>
              <Btn size="sm" full style={{ marginTop: '10px' }} onClick={() => navigate('/evidence')}>View Details</Btn>
            </Card>
          )}

          {/* User Overview (Admin Only) */}
          {role === 'Admin' && (
            <Card>
              <CardTitle>User Overview</CardTitle>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: 'var(--bg3)', borderRadius: 'var(--r)', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text2)' }}>Total Registered Officers</span>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--text)' }}>{stats?.total_users ?? '—'}</span>
              </div>
              <Btn size="sm" full onClick={() => navigate('/users')}>Manage Users</Btn>
            </Card>
          )}

          {/* System Status */}
          <Card>
            <CardTitle>System Status</CardTitle>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--green)' }} />
                <span style={{ fontSize: '12px', color: 'var(--green)', fontWeight: 500 }}>System Online</span>
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text3)' }}>Live</span>
            </div>
            {[['YOLO Model', 'Loaded'], ['BNS Index', 'Loaded'], ['OCR Engine', 'Ready'], ['Database', 'Online']].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: '11px', color: 'var(--text3)' }}>{k}</span>
                <span style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 500 }}>{v}</span>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
