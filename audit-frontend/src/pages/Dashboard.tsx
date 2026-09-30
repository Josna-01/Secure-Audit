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

interface BlockchainDashboard {
  status: {
    connected: boolean
    chainId?: number
    contractAddress?: string
    latestBlock?: number
    sender?: string
    error?: string
  }
  totalRegisteredEvidence: number
  verifiedEvidence: number
  tamperedEvidence: number
  latestTransactions?: Array<{
    event: string
    transactionHash: string
    blockNumber: number
    createdAt: string
    payload?: Record<string, any>
  }>
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
  const [blockchain, setBlockchain] = useState<BlockchainDashboard | null>(null)
  const [blockchainLoading, setBlockchainLoading] = useState(true)

  const fetchData = () => {
    setLoading(true)
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

    api.getBlockchainDashboard()
      .then((res: any) => {
        setBlockchain(res.data || res)
      })
      .catch(console.error)
      .finally(() => setBlockchainLoading(false))
  }

  useEffect(() => {
    fetchData()
  }, [])

  const filteredCases = cases.filter((c) => {
    const matchSearch = (c.case_number || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.title || '').toLowerCase().includes(search.toLowerCase())
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
    {
      label: 'Active Investigations',
      value: stats?.active ?? '—',
      sub: 'In progress',
      trend: '+12.5%',
      color: 'var(--blue)',
      icon: 'folder',
      page: '/cases',
      percent: 75
    },
    {
      label: 'Evidence Chain Assets',
      value: stats?.total_evidence ?? '—',
      sub: 'Cryptographically registered',
      trend: '+8.2%',
      color: 'var(--green)',
      icon: 'cube',
      page: '/evidence',
      percent: 92
    },
    {
      label: 'Tamper Alerts',
      value: stats?.tamper_alerts ?? 0,
      sub: (stats?.tamper_alerts ?? 0) > 0 ? 'Requires immediate action' : 'Zero tampering detected',
      trend: (stats?.tamper_alerts ?? 0) > 0 ? 'Urgent' : 'Secure',
      color: (stats?.tamper_alerts ?? 0) > 0 ? 'var(--red)' : 'var(--green)',
      icon: 'shield',
      page: (stats?.tamper_alerts ?? 0) > 0 ? '/evidence' : '_notif',
      percent: (stats?.tamper_alerts ?? 0) > 0 ? 100 : 0
    },
    {
      label: 'BNS Legal Predictions',
      value: stats?.bns_classified ?? '—',
      sub: 'AI Statutory classifications',
      trend: '+15.3%',
      color: 'var(--purple)',
      icon: 'law',
      page: '/bns',
      percent: 68
    }
  ] : [
    {
      label: 'Assigned Cases',
      value: stats?.active ?? '—',
      sub: 'Active cases',
      trend: 'Assigned',
      color: 'var(--blue)',
      icon: 'folder',
      page: '/cases',
      percent: 70
    },
    {
      label: 'Evidence Uploads',
      value: stats?.total_evidence ?? '—',
      sub: 'Registered custody files',
      trend: 'Secured',
      color: 'var(--green)',
      icon: 'cube',
      page: '/evidence',
      percent: 85
    },
    {
      label: 'AI Analyses Run',
      value: stats?.ai_analyses ?? '—',
      sub: 'Vision, Audio, OCR scans',
      trend: 'Completed',
      color: 'var(--purple)',
      icon: 'detect',
      page: '/detection',
      percent: 60
    },
    {
      label: 'Audit Log Trail',
      value: stats?.my_audit_logs ?? '—',
      sub: 'Verified actions recorded',
      trend: 'Compliant',
      color: 'var(--cyan)',
      icon: 'log',
      page: '/audit',
      percent: 100
    }
  ]

  const eventColor = (event: string) => {
    if (event === 'EvidenceRegistered') return 'var(--blue)'
    if (event === 'EvidenceVerified') return 'var(--green)'
    if (event === 'CustodyTransferred') return 'var(--purple)'
    return 'var(--text3)'
  }

  const currentDateFormatted = format(new Date(), 'EEEE, MMMM d, yyyy')

  return (
    <AppShell title="Dashboard">
      {/* ── WELCOME HERO BANNER (INSPIRED BY ENTERPRISE DESIGN) ── */}
      <div style={{
        background: 'var(--hero-gradient)',
        borderRadius: 'var(--r3)',
        padding: '24px 28px',
        color: '#ffffff',
        marginBottom: '24px',
        boxShadow: '0 10px 25px -5px rgba(30, 64, 175, 0.35)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Subtle background crest accent */}
        <div style={{
          position: 'absolute',
          right: '-20px',
          top: '-30px',
          opacity: 0.08,
          pointerEvents: 'none'
        }}>
          <svg width="220" height="220" viewBox="0 0 24 24" fill="white">
            <path d="M12 2L3 6v6c0 5.25 3.8 10.15 9 11.5 5.2-1.35 9-6.25 9-11.5V6L12 2z" />
          </svg>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'rgba(255,255,255,0.2)',
                padding: '2px 8px',
                borderRadius: '4px'
              }}>
                Secure Audit Portal
              </span>
              <span style={{ fontSize: '12px', opacity: 0.85 }}>{currentDateFormatted}</span>
            </div>
            <h2 style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em', margin: 0, lineHeight: 1.2 }}>
              Welcome back, {user?.full_name || user?.name || 'Officer'}
            </h2>
            <p style={{ fontSize: '13px', opacity: 0.9, marginTop: '4px', maxWidth: '600px', margin: '4px 0 0' }}>
              Cryptographic integrity is active. Forensic AI pipelines, blockchain ledger, and audit tracking are running smoothly.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={fetchData}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                background: 'rgba(255, 255, 255, 0.15)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.25)',
                borderRadius: 'var(--r)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background 0.15s'
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
              </svg>
              Refresh Stats
            </button>
            {user?.can_create_case && (
              <button
                onClick={() => navigate('/cases/new')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  background: '#ffffff',
                  color: '#1d4ed8',
                  borderRadius: 'var(--r)',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  transition: 'transform 0.15s'
                }}
              >
                + New Case
              </button>
            )}
          </div>
        </div>

        {/* Embedded Summary Mini-Pills */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '12px',
          background: 'rgba(0, 0, 0, 0.18)',
          borderRadius: 'var(--r2)',
          padding: '12px 16px'
        }}>
          <div>
            <div style={{ fontSize: '11px', opacity: 0.8, fontWeight: 500 }}>Active Cases</div>
            <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)' }}>{stats?.active ?? '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', opacity: 0.8, fontWeight: 500 }}>Registered Evidence</div>
            <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)' }}>{stats?.total_evidence ?? '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', opacity: 0.8, fontWeight: 500 }}>BNS Classified</div>
            <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)' }}>{stats?.bns_classified ?? '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', opacity: 0.8, fontWeight: 500 }}>Tamper Status</div>
            <div style={{
              fontSize: '14px',
              fontWeight: 800,
              color: (stats?.tamper_alerts ?? 0) > 0 ? '#fca5a5' : '#86efac',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '2px'
            }}>
              {(stats?.tamper_alerts ?? 0) > 0 ? `⚠️ ${stats?.tamper_alerts} Tampered` : '✓ 100% Intact'}
            </div>
          </div>
        </div>
      </div>

      {/* ── STAT CARDS GRID ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {statCards.map((s) => (
          <div
            key={s.label}
            onClick={() => s.page === '_notif' ? {} : navigate(s.page)}
            style={{
              background: 'var(--bg2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r3)',
              padding: '18px 20px',
              cursor: s.page === '_notif' ? 'default' : 'pointer',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all 0.2s ease',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
            className="card-hover"
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text3)' }}>{s.label}</span>
                <span style={{
                  fontSize: '10.5px',
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: 'var(--r-pill)',
                  background: s.color === 'var(--red)' ? 'var(--red-bg)' : 'var(--green-bg)',
                  color: s.color === 'var(--red)' ? 'var(--red)' : 'var(--green)',
                  border: `1px solid ${s.color === 'var(--red)' ? 'var(--red-border)' : 'var(--green-border)'}`
                }}>
                  {s.trend}
                </span>
              </div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text)', fontFamily: 'var(--mono)', lineHeight: 1.1, marginBottom: '8px' }}>
                {loading ? '...' : s.value}
              </div>
            </div>

            <div>
              <ProgressBar value={s.percent} color={s.color} height={4} />
              <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '8px' }}>{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── TAMPER ALERT BANNER (IF DETECTED) ── */}
      {role === 'Admin' && (stats?.tamper_alerts ?? 0) > 0 && (
        <div
          onClick={() => navigate('/evidence')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            padding: '14px 18px',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-border)',
            borderRadius: 'var(--r2)',
            marginBottom: '20px',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(220, 38, 38, 0.15)'
          }}
        >
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'var(--red)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontWeight: 800,
            fontSize: '18px',
            flexShrink: 0
          }}>
            !
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--red)' }}>
              {stats?.tamper_alerts} Tampered Evidence File{(stats?.tamper_alerts ?? 0) > 1 ? 's' : ''} Detected
            </div>
            <div style={{ fontSize: '12px', color: 'var(--red)', opacity: 0.9, marginTop: '2px' }}>
              SHA-256 hash mismatch detected against Ethereum on-chain ledger. Immediate forensic review required.
            </div>
          </div>
          <Btn variant="danger" size="sm">Inspect Evidence</Btn>
        </div>
      )}

      {/* ── QUICK ACTIONS BAR ── */}
      <Card style={{ marginBottom: '24px', padding: '16px 20px' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px' }}>
          Forensic Quick Actions
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px' }}>
          {user?.can_create_case && (
            <button
              onClick={() => navigate('/cases/new')}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
                background: 'var(--blue-bg)', border: '1px solid var(--blue-border)',
                borderRadius: 'var(--r)', color: 'var(--blue)', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              <span>📁</span> + New Case
            </button>
          )}
          <button
            onClick={() => navigate('/evidence')}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
              background: 'var(--green-bg)', border: '1px solid var(--green-border)',
              borderRadius: 'var(--r)', color: 'var(--green)', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
              transition: 'all 0.15s'
            }}
          >
            <span>⬆️</span> Upload Evidence
          </button>
          <button
            onClick={() => navigate('/bns')}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
              background: 'var(--purple-bg)', border: '1px solid var(--purple-border)',
              borderRadius: 'var(--r)', color: 'var(--purple)', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
              transition: 'all 0.15s'
            }}
          >
            <span>⚖️</span> BNS Legal Dossier
          </button>
          <button
            onClick={() => navigate('/detection')}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
              background: 'var(--amber-bg)', border: '1px solid var(--amber-border)',
              borderRadius: 'var(--r)', color: 'var(--amber)', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
              transition: 'all 0.15s'
            }}
          >
            <span>🔍</span> Weapon Scan
          </button>
          <button
            onClick={() => navigate('/blockchain')}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px',
              background: 'var(--bg3)', border: '1px solid var(--border)',
              borderRadius: 'var(--r)', color: 'var(--text)', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
              transition: 'all 0.15s'
            }}
          >
            <span>⛓️</span> Ledger Explorer
          </button>
        </div>
      </Card>

      {/* ── MAIN 2-COLUMN SECTION: CASES + BLOCKCHAIN & AUDIT ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Left Col: Recent Investigations Table */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent Investigations</CardTitle>
              <div style={{ fontSize: '12px', color: 'var(--text3)' }}>Active cases under your judicial jurisdiction</div>
            </div>
            <Btn size="xs" variant="outline" onClick={() => navigate('/cases')}>View All Cases →</Btn>
          </CardHeader>

          <div style={{ display: 'flex', gap: '10px', marginBottom: '14px' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by case number, title, or complainant..."
              style={{
                flex: 1,
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '8px 12px',
                fontSize: '12.5px',
                color: 'var(--text)',
                outline: 'none'
              }}
            />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              style={{
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '8px 12px',
                fontSize: '12.5px',
                color: 'var(--text)',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {['All', 'Active', 'Open', 'Pending', 'Critical', 'Closed'].map((s) => (
                <option key={s} value={s}>{s} Status</option>
              ))}
            </select>
          </div>

          {loading ? (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)', fontSize: '13px' }}>
              Loading investigation records...
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="sa-table">
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Investigation Title</th>
                    <th>Offence</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCases.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)' }}>
                        No matching investigations found.
                      </td>
                    </tr>
                  )}
                  {filteredCases.map((c) => (
                    <tr key={c.id}>
                      <td
                        style={{ fontFamily: 'var(--mono)', fontSize: '11.5px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer' }}
                        onClick={() => navigate(`/cases/${c.id}`)}
                      >
                        {c.case_number}
                      </td>
                      <td
                        style={{ fontWeight: 600, color: 'var(--text)', cursor: 'pointer' }}
                        onClick={() => navigate(`/cases/${c.id}`)}
                      >
                        {c.title}
                      </td>
                      <td style={{ color: 'var(--text2)', fontSize: '12px' }}>{c.offence_type}</td>
                      <td><Badge label={c.status} /></td>
                      <td style={{ textAlign: 'right' }}>
                        <Btn size="xs" variant="default" onClick={() => navigate(`/cases/${c.id}`)}>
                          Open
                        </Btn>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Right Col: Blockchain Ledger & Live Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Blockchain Ledger Health Card */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Ethereum Ledger Network</CardTitle>
                <div style={{ fontSize: '12px', color: 'var(--text3)' }}>Chain of Custody Smart Contract</div>
              </div>
              {!blockchainLoading && blockchain && (
                <span style={{
                  fontSize: '10.5px',
                  padding: '3px 8px',
                  borderRadius: 'var(--r-pill)',
                  background: blockchain.status?.connected ? 'var(--green-bg)' : 'var(--red-bg)',
                  color: blockchain.status?.connected ? 'var(--green)' : 'var(--red)',
                  border: `1px solid ${blockchain.status?.connected ? 'var(--green-border)' : 'var(--red-border)'}`,
                  fontWeight: 700,
                  letterSpacing: '0.02em'
                }}>
                  {blockchain.status?.connected ? '● Node Connected' : '○ Node Offline'}
                </span>
              )}
            </CardHeader>

            {blockchainLoading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>Loading ledger state...</div>
            ) : !blockchain || !blockchain.status?.connected ? (
              <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>
                Ganache RPC offline on port 8545. Start node to enable on-chain verification.
              </div>
            ) : (
              <div>
                {/* Chain stats mini grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '14px' }}>
                  <div style={{ background: 'var(--bg3)', borderRadius: 'var(--r)', padding: '10px', textAlign: 'center' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--blue)' }}>
                      {blockchain.totalRegisteredEvidence}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', fontWeight: 600, marginTop: '2px' }}>Registered</div>
                  </div>
                  <div style={{ background: 'var(--green-bg)', borderRadius: 'var(--r)', padding: '10px', textAlign: 'center', border: '1px solid var(--green-border)' }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--green)' }}>
                      {blockchain.verifiedEvidence}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--green)', textTransform: 'uppercase', fontWeight: 600, marginTop: '2px' }}>Verified</div>
                  </div>
                  <div style={{ background: (blockchain.tamperedEvidence > 0 ? 'var(--red-bg)' : 'var(--bg3)'), borderRadius: 'var(--r)', padding: '10px', textAlign: 'center', border: (blockchain.tamperedEvidence > 0 ? '1px solid var(--red-border)' : 'none') }}>
                    <div style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--mono)', color: (blockchain.tamperedEvidence > 0 ? 'var(--red)' : 'var(--text3)') }}>
                      {blockchain.tamperedEvidence}
                    </div>
                    <div style={{ fontSize: '10px', color: (blockchain.tamperedEvidence > 0 ? 'var(--red)' : 'var(--text3)'), textTransform: 'uppercase', fontWeight: 600, marginTop: '2px' }}>Tampered</div>
                  </div>
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text3)', fontFamily: 'var(--mono)', wordBreak: 'break-all', marginBottom: '12px', background: 'var(--bg3)', padding: '6px 10px', borderRadius: '6px' }}>
                  Contract: <span style={{ color: 'var(--blue)' }}>{blockchain.status.contractAddress?.slice(0, 18)}...{blockchain.status.contractAddress?.slice(-8)}</span>
                </div>

                <Btn size="xs" full variant="outline" onClick={() => navigate('/blockchain')}>
                  Open Blockchain Dashboard →
                </Btn>
              </div>
            )}
          </Card>

          {/* Live Forensic Audit Feed */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Live Audit Trail</CardTitle>
                <div style={{ fontSize: '12px', color: 'var(--text3)' }}>Real-time tamper & access events</div>
              </div>
              <Btn size="xs" variant="ghost" onClick={() => navigate('/audit')}>Full Log →</Btn>
            </CardHeader>

            {loading ? (
              <div style={{ color: 'var(--text3)', fontSize: '12px' }}>Loading audit stream...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {logs.slice(0, 6).map((log) => (
                  <div
                    key={log.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '8px 10px',
                      borderRadius: 'var(--r)',
                      background: 'var(--bg3)',
                      fontSize: '12px',
                      cursor: log.case_id ? 'pointer' : 'default',
                      transition: 'background 0.15s'
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                    onClick={() => log.case_id && navigate(`/cases/${log.case_id}`)}
                  >
                    <div style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      flexShrink: 0,
                      background: actionColors[log.action] || 'var(--blue)',
                      boxShadow: `0 0 5px ${actionColors[log.action] || 'var(--blue)'}`
                    }} />
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text3)', minWidth: '40px' }}>
                      {format(new Date(log.created_at), 'HH:mm')}
                    </div>
                    <div style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{log.user_name || 'System'}</span>
                      {' '}<span style={{ color: 'var(--text2)' }}>{log.action}</span>
                      {log.case_number && log.case_number !== 'N/A' && (
                        <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text3)' }}> · {log.case_number}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
