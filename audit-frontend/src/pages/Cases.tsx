import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardHeader, CardTitle, Btn, Badge } from '../components/UI'
import { api } from '../services/api'
import type { Case } from '../types'
import { format } from 'date-fns'
import { useAuth } from '../context/AuthContext'

const PRIORITY_BADGES: Record<string, { bg: string; color: string; border: string }> = {
  Critical: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  High: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Medium: { bg: 'var(--blue-bg)', color: 'var(--blue)', border: 'var(--blue-border)' },
  Low: { bg: 'var(--bg4)', color: 'var(--text3)', border: 'var(--border2)' }
}

export default function Cases() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [cases, setCases] = useState<Case[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('All Status')
  const [page, setPage] = useState(1)

  const fetchCases = () => {
    setLoading(true)
    api.getCases({
      status: status === 'All Status' ? undefined : status,
      search: search || undefined,
      page,
      per_page: 15
    }).then((res) => {
      setCases(res.data)
      setTotal(res.total)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchCases() }, [status, page])

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { setPage(1); fetchCases() }
  }

  return (
    <AppShell title="Case Management">
      {/* Search & Filter Header Bar */}
      <Card style={{ marginBottom: '20px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '260px', position: 'relative' }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleSearch}
              placeholder="Search by case number, title, offence type... (Press Enter)"
              style={{
                width: '100%',
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '9px 14px',
                fontSize: '13px',
                color: 'var(--text)',
                outline: 'none',
                transition: 'border-color 0.15s'
              }}
            />
          </div>

          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            style={{
              background: 'var(--bg3)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r)',
              padding: '9px 14px',
              fontSize: '13px',
              color: 'var(--text)',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {['All Status', 'Active', 'Open', 'Pending', 'Critical', 'Closed'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <Btn size="md" variant="default" onClick={() => { setPage(1); fetchCases() }}>
            Search
          </Btn>

          {user?.can_create_case && (
            <Btn variant="primary" size="md" onClick={() => navigate('/cases/new')}>
              + New Case
            </Btn>
          )}
        </div>
      </Card>

      {/* Main Cases Table Card */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Registered Cases & FIR Dossiers</CardTitle>
            <div style={{ fontSize: '12px', color: 'var(--text3)' }}>
              Showing {cases.length} of {total} total recorded cases
            </div>
          </div>
        </CardHeader>

        <div style={{ overflowX: 'auto' }}>
          <table className="sa-table">
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Investigation Title</th>
                <th>Offence Category</th>
                <th>Victims / Complainant</th>
                <th>Investigator</th>
                <th>Date Filed</th>
                <th>Priority</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={9} style={{ padding: '36px', textAlign: 'center', color: 'var(--text3)' }}>
                    Loading case files...
                  </td>
                </tr>
              )}
              {!loading && cases.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ padding: '36px', textAlign: 'center', color: 'var(--text3)' }}>
                    No case records match the specified filters.
                  </td>
                </tr>
              )}
              {!loading && cases.map((c) => {
                const prio = PRIORITY_BADGES[c.priority] || PRIORITY_BADGES.Medium
                return (
                  <tr key={c.id}>
                    <td
                      style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
                      onClick={() => navigate(`/cases/${c.id}`)}
                    >
                      {c.case_number}
                    </td>
                    <td
                      style={{ fontWeight: 600, color: 'var(--text)', cursor: 'pointer', maxWidth: '240px' }}
                      onClick={() => navigate(`/cases/${c.id}`)}
                    >
                      {c.title}
                    </td>
                    <td style={{ color: 'var(--text2)', fontSize: '12.5px' }}>{c.offence_type}</td>
                    <td style={{ fontSize: '12px', color: 'var(--text2)' }}>
                      {c.victims?.map((v) => v.name).join(', ') || c.complainant_name || '—'}
                    </td>
                    <td style={{ fontSize: '12px', color: 'var(--text3)' }}>{c.investigator_name || '—'}</td>
                    <td style={{ fontSize: '12px', color: 'var(--text3)', whiteSpace: 'nowrap' }}>
                      {format(new Date(c.created_at), 'dd MMM yyyy')}
                    </td>
                    <td>
                      <span style={{
                        fontSize: '10.5px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 'var(--r-pill)',
                        background: prio.bg,
                        color: prio.color,
                        border: `1px solid ${prio.border}`
                      }}>
                        {c.priority}
                      </span>
                    </td>
                    <td><Badge label={c.status} /></td>
                    <td style={{ textAlign: 'right' }}>
                      <Btn size="xs" variant="default" onClick={() => navigate(`/cases/${c.id}`)}>
                        Open Dossier
                      </Btn>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        {total > 15 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: '12px', color: 'var(--text3)' }}>
              Page {page} of {Math.ceil(total / 15)}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Btn size="xs" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                ← Previous
              </Btn>
              <Btn size="xs" disabled={page >= Math.ceil(total / 15)} onClick={() => setPage((p) => p + 1)}>
                Next →
              </Btn>
            </div>
          </div>
        )}
      </Card>
    </AppShell>
  )
}
