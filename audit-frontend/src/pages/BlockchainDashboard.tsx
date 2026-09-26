import React, { useEffect, useState } from 'react'
import { AppShell } from '../components/Layout'
import { AlertBox, Card, CardTitle, Spinner } from '../components/UI'
import { api } from '../services/api'

export default function BlockchainDashboard() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  useEffect(() => { api.getBlockchainDashboard().then((r) => setData(r.data)).catch((e) => setError(e.response?.data?.detail || 'Unable to load blockchain dashboard')) }, [])
  if (error) return <AppShell title="Blockchain Dashboard"><AlertBox type="error">{error}</AlertBox></AppShell>
  if (!data) return <AppShell title="Blockchain Dashboard"><div style={{ padding: 48, textAlign: 'center' }}><Spinner size={28} /></div></AppShell>
  const cards = [['Registered Evidence', data.totalRegisteredEvidence], ['Verified Evidence', data.verifiedEvidence], ['Tampered Evidence', data.tamperedEvidence], ['Pending Transactions', data.pendingTransactions]]
  return <AppShell title="Blockchain Dashboard">
    <Card style={{ marginBottom: 16 }}><CardTitle>Ethereum Network</CardTitle><div style={{ color: data.status.connected ? 'var(--green)' : 'var(--red)', fontSize: 13 }}>{data.status.connected ? `Connected · Chain ${data.status.chainId} · ${data.status.contractAddress}` : data.status.error}</div></Card>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>{cards.map(([label, value]) => <Card key={String(label)}><div style={{ fontSize: 11, color: 'var(--text3)' }}>{label}</div><div style={{ fontFamily: 'var(--mono)', fontSize: 26, marginTop: 8 }}>{value}</div></Card>)}</div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <Card><CardTitle>Latest Transactions</CardTitle>{data.latestTransactions?.map((t: any) => <div key={t.transactionHash} style={{ padding: '9px 0', borderBottom: '1px solid var(--border)', fontSize: 11 }}><div>{t.event} · block {t.blockNumber}</div><div style={{ fontFamily: 'var(--mono)', color: 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.transactionHash}</div></div>)}</Card>
      <Card><CardTitle>Latest Blocks</CardTitle>{data.latestBlocks?.map((b: any) => <div key={b.number} style={{ padding: '9px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>#{b.number} · {b.transactions} transaction(s) · {new Date(b.timestamp).toLocaleString()}</div>)}</Card>
    </div>
  </AppShell>
}
