import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardHeader, CardTitle, Btn, Badge } from '../components/UI'
import { api } from '../services/api'
import type { Case } from '../types'
import { format } from 'date-fns'

const PRIORITY_COLORS: Record<string, string> = {
  Critical: 'var(--red)', High: 'var(--amber)', Medium: 'var(--blue)', Low: 'var(--text3)'
}

export default function Cases() {
  const navigate = useNavigate()
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
      {/* Filter bar */}
      <Card style={{ marginBottom: '16px', padding: '12px 16px' }}>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleSearch}
            placeholder="Search by ID, title, type... (press Enter)"
            style={{ flex: 1, minWidth: '200px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
          >
            {['All Status', 'Active', 'Open', 'Pending', 'Critical', 'Closed'].map((s) => <option key={s}>{s}</option>)}
          </select>
          <Btn variant="primary" size="sm" onClick={() => navigate('/cases/new')}>New Case</Btn>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{total} cases found</CardTitle>
        </CardHeader>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr>
                {['Case ID', 'Title', 'Offence', 'Victim(s)', 'Investigator', 'Date', 'Priority', 'Status', ''].map((h) => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 10px', color: 'var(--text3)', fontWeight: 500, borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', fontSize: '11px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)' }}>Loading...</td></tr>
              )}
              {!loading && cases.length === 0 && (
                <tr><td colSpan={9} style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)' }}>No cases found</td></tr>
              )}
              {!loading && cases.map((c) => (
                <tr key={c.id}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                  <td style={{ padding: '9px 10px', fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--blue)', fontWeight: 500, borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => navigate(`/cases/${c.id}`)}>{c.case_number}</td>
                  <td style={{ padding: '9px 10px', color: 'var(--text)', fontWeight: 500, borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => navigate(`/cases/${c.id}`)}>{c.title}</td>
                  <td style={{ padding: '9px 10px', color: 'var(--text2)', borderBottom: '1px solid var(--border)' }}>{c.offence_type}</td>
                  <td style={{ padding: '9px 10px', fontSize: '11px', color: 'var(--text2)', borderBottom: '1px solid var(--border)' }}>{c.victims?.map((v) => v.name).join(', ') || '—'}</td>
                  <td style={{ padding: '9px 10px', fontSize: '11px', color: 'var(--text3)', borderBottom: '1px solid var(--border)' }}>{c.investigator_name || '—'}</td>
                  <td style={{ padding: '9px 10px', fontSize: '11px', color: 'var(--text3)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{format(new Date(c.created_at), 'dd MMM yyyy')}</td>
                  <td style={{ padding: '9px 10px', borderBottom: '1px solid var(--border)', fontSize: '10px', fontWeight: 500, color: PRIORITY_COLORS[c.priority] }}>{c.priority}</td>
                  <td style={{ padding: '9px 10px', borderBottom: '1px solid var(--border)' }}><Badge label={c.status} /></td>
                  <td style={{ padding: '9px 10px', borderBottom: '1px solid var(--border)' }}>
                    <Btn size="xs" onClick={() => navigate(`/cases/${c.id}`)}>Open</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        {total > 15 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
            <Btn size="xs" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Prev</Btn>
            <span style={{ fontSize: '12px', color: 'var(--text3)', alignSelf: 'center' }}>Page {page} of {Math.ceil(total / 15)}</span>
            <Btn size="xs" disabled={page >= Math.ceil(total / 15)} onClick={() => setPage((p) => p + 1)}>Next</Btn>
          </div>
        )}
      </Card>
    </AppShell>
  )
}
