import React, { useCallback, useEffect, useState } from 'react'
import { AppShell } from '../components/Layout'
import { AlertBox, Badge, Btn, Card, CardTitle, Input, Modal, Select, Spinner } from '../components/UI'
import { api, describeVerification } from '../services/api'
import { useAuth } from '../context/AuthContext'
import type { BlockchainTransaction, LedgerEvidenceDetail, LedgerRow } from '../types'

const PAGE_SIZE = 20
const STATUS_FILTERS = ['All', 'Verified', 'Tampered', 'Missing', 'Unregistered', 'Verification Failed']

const mono: React.CSSProperties = { fontFamily: 'var(--mono)', fontSize: 11 }
const cell: React.CSSProperties = { padding: '8px 10px', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', fontSize: 12 }
const head: React.CSSProperties = { ...cell, fontSize: 10.5, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px', fontWeight: 600, textAlign: 'left', background: 'var(--bg3)' }

/** Stored hashes have no 0x prefix; display them the way explorers do. */
const hex0x = (value?: string | null) => (value ? (value.startsWith('0x') ? value : `0x${value}`) : '')
const short = (value?: string | null, head = 8, tail = 6) => {
  if (!value) return '—'
  return value.length > head + tail + 3 ? `${value.slice(0, head)}…${value.slice(-tail)}` : value
}
const when = (value?: string | null) => (value ? new Date(value).toLocaleString() : '—')
const errorText = (e: any, fallback: string) => (typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : fallback)

function CopyButton({ value, label }: { value?: string | null; label: string }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      window.prompt(`Copy ${label}`, value)
    }
  }
  return (
    <button onClick={copy} title={`Copy ${label}`} aria-label={`Copy ${label}`}
      style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px', borderRadius: 4, border: '1px solid var(--border2)', background: 'var(--bg3)', color: copied ? 'var(--green)' : 'var(--text3)', cursor: 'pointer' }}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function Field({ label, value, copy, monoValue }: { label: string; value: React.ReactNode; copy?: string | null; monoValue?: boolean }) {
  return (
    <>
      <span style={{ color: 'var(--text3)', fontSize: 12 }}>{label}</span>
      <span style={{ fontSize: 12, wordBreak: 'break-all', ...(monoValue ? mono : {}) }}>
        {value ?? '—'}{copy ? <CopyButton value={copy} label={label} /> : null}
      </span>
    </>
  )
}

const grid: React.CSSProperties = { display: 'grid', gridTemplateColumns: '170px 1fr', gap: '7px 12px', alignItems: 'center' }
const sectionTitle: React.CSSProperties = { fontSize: 11, fontWeight: 700, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '.5px', margin: '18px 0 8px' }

function TransactionModal({ txHash, onClose }: { txHash: string | null; onClose: () => void }) {
  const [tx, setTx] = useState<BlockchainTransaction | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!txHash) return
    setTx(null); setError('')
    api.getBlockchainTransaction(txHash).then((r) => setTx(r.data)).catch((e) => setError(errorText(e, 'Transaction details unavailable')))
  }, [txHash])
  return (
    <Modal open={!!txHash} onClose={onClose} title="Transaction Details" maxWidth="720px">
      {error && <AlertBox type="error">{error}</AlertBox>}
      {!tx && !error && <div style={{ textAlign: 'center', padding: 30 }}><Spinner /></div>}
      {tx && (
        <div style={grid}>
          <Field label="Status" value={<Badge label={tx.status} />} />
          <Field label="Transaction Hash" value={hex0x(tx.transactionHash)} copy={hex0x(tx.transactionHash)} monoValue />
          <Field label="Block" value={tx.blockNumber ?? 'Pending'} />
          <Field label="Block Hash" value={hex0x(tx.blockHash) || '—'} copy={hex0x(tx.blockHash)} monoValue />
          <Field label="Timestamp" value={when(tx.timestamp)} />
          <Field label="Confirmations" value={tx.confirmations} />
          <Field label="From (wallet)" value={tx.from} copy={tx.from} monoValue />
          <Field label="To (contract)" value={tx.to || '—'} monoValue />
          <Field label="Function" value={tx.function || '—'} monoValue />
          <Field label="Nonce" value={tx.nonce} />
          <Field label="Gas Used / Limit" value={`${tx.gasUsed?.toLocaleString() ?? '—'} / ${tx.gasLimit.toLocaleString()}`} />
          <Field label="Gas Price" value={tx.effectiveGasPriceWei ?? tx.gasPriceWei ? `${((tx.effectiveGasPriceWei ?? tx.gasPriceWei) as number) / 1e9} gwei` : '—'} />
          <Field label="Chain ID" value={tx.chainId} />
          {Object.keys(tx.arguments).length > 0 && <>
            <span style={{ gridColumn: '1 / -1', ...sectionTitle, margin: '10px 0 0' }}>Arguments</span>
            {Object.entries(tx.arguments).map(([k, v]) => <Field key={k} label={k} value={v} monoValue />)}
          </>}
          {tx.events.length > 0 && <>
            <span style={{ gridColumn: '1 / -1', ...sectionTitle, margin: '10px 0 0' }}>Events Emitted</span>
            {tx.events.map((ev, i) => (
              <Field key={`${ev.name}-${i}`} label={ev.name}
                value={Object.entries(ev.args).map(([k, v]) => `${k}: ${String(v)}`).join(' · ')} monoValue />
            ))}
          </>}
        </div>
      )}
    </Modal>
  )
}

function EvidenceModal({ evidenceId, onClose, onOpenTx, onVerified }: {
  evidenceId: string | null; onClose: () => void; onOpenTx: (hash: string) => void; onVerified: () => void
}) {
  const [detail, setDetail] = useState<LedgerEvidenceDetail | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState<'' | 'verify' | 'download'>('')

  const load = useCallback(() => {
    if (!evidenceId) return
    setError('')
    api.getBlockchainEvidence(evidenceId).then((r) => setDetail(r.data)).catch((e) => setError(errorText(e, 'Evidence details unavailable')))
  }, [evidenceId])
  useEffect(() => { setDetail(null); setNotice(''); load() }, [load])

  const verify = async () => {
    if (!evidenceId) return
    setBusy('verify')
    try {
      const res = await api.verifyHash(evidenceId)
      setNotice(describeVerification(res.data))
    } catch (e: any) {
      setNotice(describeVerification(null, e))
    } finally {
      setBusy(''); load(); onVerified()
    }
  }

  const download = async () => {
    if (!evidenceId || !detail) return
    setBusy('download')
    try {
      const { blob, sha256, integrity } = await api.downloadEvidence(evidenceId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = detail.evidence.fileName || 'evidence'
      link.click()
      URL.revokeObjectURL(url)
      setNotice(integrity === 'match' ? `Downloaded · SHA-256 ${short(sha256, 12, 8)} matches the recorded hash` : `Downloaded · ⚠ served file hash ${short(sha256, 12, 8)} differs from the recorded hash`)
      load()
    } catch (e: any) {
      setNotice(errorText(e, 'Download failed'))
    } finally {
      setBusy('')
    }
  }

  const ev = detail?.evidence
  const chain = detail?.blockchain
  return (
    <Modal open={!!evidenceId} onClose={onClose} title="Evidence Ledger Record" maxWidth="820px"
      footer={detail && <>
        {chain?.transactionHash && <Btn size="sm" onClick={() => onOpenTx(chain.transactionHash as string)}>View Transaction</Btn>}
        <Btn size="sm" onClick={download} loading={busy === 'download'}>Download</Btn>
        <Btn size="sm" variant="primary" onClick={verify} loading={busy === 'verify'}>Verify Now</Btn>
      </>}>
      {error && <AlertBox type="error">{error}</AlertBox>}
      {!detail && !error && <div style={{ textAlign: 'center', padding: 30 }}><Spinner /></div>}
      {notice && <div style={{ marginBottom: 12 }}><AlertBox type="info">{notice}</AlertBox></div>}
      {detail && ev && chain && (
        <>
          {!detail.chainAvailable && <AlertBox type="warning">The blockchain node is unavailable; on-chain checks were skipped and cached data is shown.</AlertBox>}
          <div style={sectionTitle}>Evidence</div>
          <div style={grid}>
            <Field label="Evidence ID" value={ev.id} copy={ev.id} monoValue />
            <Field label="Evidence Name" value={ev.fileName} />
            <Field label="Case ID" value={ev.caseId} monoValue />
            <Field label="SHA-256" value={ev.sha256} copy={ev.sha256} monoValue />
            <Field label="Evidence Status" value={<Badge label={ev.status} />} />
            <Field label="Last Verification" value={<><Badge label={ev.verificationStatus} />{ev.verificationReason ? <span style={{ marginLeft: 8, color: 'var(--text3)', fontSize: 11 }}>{ev.verificationReason}</span> : null}</>} />
            <Field label="Verified At" value={when(ev.verifiedAt)} />
          </div>

          <div style={sectionTitle}>Blockchain Registration</div>
          <div style={grid}>
            <Field label="Blockchain Status" value={<Badge label={ev.blockchainStatus} />} />
            <Field label="Transaction Hash" value={hex0x(chain.transactionHash)} copy={hex0x(chain.transactionHash)} monoValue />
            <Field label="Transaction Status" value={chain.transactionStatus ? <Badge label={chain.transactionStatus} /> : '—'} />
            <Field label="Block Number" value={chain.blockNumber} />
            <Field label="Block Hash" value={hex0x(chain.blockHash) || '—'} copy={hex0x(chain.blockHash)} monoValue />
            <Field label="Wallet Address" value={chain.walletAddress || '—'} copy={chain.walletAddress} monoValue />
            <Field label="Registered At" value={when(chain.registeredAt)} />
            <Field label="Network" value={chain.network ? `${chain.network} (chain ${chain.chainId})` : '—'} />
            <Field label="Smart Contract" value={chain.contractAddress || '—'} copy={chain.contractAddress} monoValue />
            <Field label="Gas Used" value={chain.gasUsed?.toLocaleString()} />
          </div>

          {detail.onChain && <>
            <div style={sectionTitle}>On-chain Record</div>
            <div style={grid}>
              <Field label="Registered SHA-256" value={detail.onChain.sha256Hash} monoValue />
              <Field label="File Name" value={detail.onChain.fileName} />
              <Field label="Registered By" value={detail.onChain.uploadedBy} monoValue />
              <Field label="Block Time" value={when(detail.onChain.timestamp)} />
            </div>
          </>}

          <div style={{ ...sectionTitle, display: 'flex', alignItems: 'center', gap: 10 }}>Integrity Checks <Badge label={detail.integrity} /></div>
          {detail.integrityChecks.length === 0 && <div style={{ fontSize: 12, color: 'var(--text3)' }}>Not available while the blockchain is offline.</div>}
          {detail.integrityChecks.map((check) => (
            <div key={check.code} style={{ fontSize: 12, padding: '4px 0', color: check.ok ? 'var(--text2)' : check.severity === 'critical' ? 'var(--red)' : 'var(--amber)' }}>
              {check.ok ? '✓' : '✗'} {check.message}
            </div>
          ))}

          <div style={sectionTitle}>Chain of Custody</div>
          {detail.timeline.length === 0 && <div style={{ fontSize: 12, color: 'var(--text3)' }}>No custody records.</div>}
          {detail.timeline.map((entry, i) => (
            <div key={`${entry.action}-${entry.timestamp}-${i}`} style={{ borderLeft: `2px solid ${entry.source === 'blockchain' ? 'var(--blue)' : 'var(--border2)'}`, padding: '5px 0 5px 10px', fontSize: 12 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <strong>{entry.label}</strong>
                <span style={{ fontSize: 10, color: entry.source === 'blockchain' ? 'var(--blue)' : 'var(--text3)' }}>{entry.source === 'blockchain' ? 'ON-CHAIN' : 'DATABASE'}</span>
              </div>
              <div style={{ color: 'var(--text3)', fontSize: 11 }}>
                {when(entry.timestamp)} · {entry.officerName || entry.officerId}
                {entry.transactionHash && <> · <a onClick={() => onOpenTx(entry.transactionHash as string)} style={{ ...mono, color: 'var(--blue)', cursor: 'pointer' }}>{short(hex0x(entry.transactionHash))}</a></>}
              </div>
            </div>
          ))}
        </>
      )}
    </Modal>
  )
}

export default function BlockchainDashboard() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'Admin'
  const [data, setData] = useState<any>(null)
  const [network, setNetwork] = useState<any>(null)
  const [rows, setRows] = useState<LedgerRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [error, setError] = useState('')
  const [loadingRows, setLoadingRows] = useState(true)
  const [rowNotice, setRowNotice] = useState<Record<string, string>>({})
  const [verifying, setVerifying] = useState<string | null>(null)
  const [openEvidence, setOpenEvidence] = useState<string | null>(null)
  const [openTx, setOpenTx] = useState<string | null>(null)
  const [scan, setScan] = useState<Record<string, number> | null>(null)
  const [scanning, setScanning] = useState(false)

  const loadSummary = useCallback(() => {
    api.getBlockchainDashboard().then((r) => setData(r.data)).catch((e) => setError(errorText(e, 'Unable to load blockchain dashboard')))
    api.getBlockchainNetwork().then((r) => setNetwork(r.data)).catch(() => setNetwork(null))
  }, [])

  const loadRows = useCallback(() => {
    setLoadingRows(true)
    api.getBlockchainLedger({ search: search || undefined, status: statusFilter, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => { setRows(r.data); setTotal(r.total) })
      .catch((e) => setError(errorText(e, 'Unable to load the ledger')))
      .finally(() => setLoadingRows(false))
  }, [search, statusFilter, page])

  useEffect(() => { loadSummary() }, [loadSummary])
  useEffect(() => {
    const timer = setTimeout(loadRows, 250)  // debounce typing in the search box
    return () => clearTimeout(timer)
  }, [loadRows])

  const refreshVerification = async (id: string) => {
    setVerifying(id)
    try {
      const res = await api.verifyHash(id)
      setRowNotice((n) => ({ ...n, [id]: describeVerification(res.data) }))
    } catch (e: any) {
      setRowNotice((n) => ({ ...n, [id]: describeVerification(null, e) }))
    } finally {
      setVerifying(null); loadRows(); loadSummary()
    }
  }

  const runScan = async () => {
    setScanning(true)
    try { setScan((await api.runIntegrityScan()).data.summary) }
    catch (e: any) { setError(errorText(e, 'Integrity scan failed')) }
    finally { setScanning(false); loadRows(); loadSummary() }
  }

  if (error && !data) return <AppShell title="Blockchain Ledger"><AlertBox type="error">{error}</AlertBox></AppShell>
  if (!data) return <AppShell title="Blockchain Ledger"><div style={{ padding: 48, textAlign: 'center' }}><Spinner size={28} /></div></AppShell>

  const rate = data.verificationSuccessRate
  const stats: [string, React.ReactNode, string?][] = [
    ['Registered Evidence', data.totalRegisteredEvidence],
    ['Verified', data.verifiedEvidence, 'var(--green)'],
    ['Tampered', data.tamperedEvidence, data.tamperedEvidence ? 'var(--red)' : undefined],
    ['Missing', data.missingEvidence, data.missingEvidence ? 'var(--red)' : undefined],
    ['Unregistered', data.unregisteredEvidence, data.unregisteredEvidence ? 'var(--amber)' : undefined],
    ['Verification Failed', data.verificationFailed, data.verificationFailed ? 'var(--amber)' : undefined],
    ['Verification Success Rate', rate === null || rate === undefined ? '—' : `${rate}%`],
    ['Checks Performed', data.verificationChecks],
  ]
  const connected = network?.connected ?? data.status?.connected

  return (
    <AppShell title="Blockchain Ledger">
      {error && <div style={{ marginBottom: 12 }}><AlertBox type="error">{error}</AlertBox></div>}

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
          <CardTitle subtitle="Evidence digests are anchored in the EvidenceRegistry smart contract">Blockchain Network</CardTitle>
          <div style={{ display: 'flex', gap: 8 }}>
            {isAdmin && <Btn size="sm" onClick={runScan} loading={scanning}>Run Integrity Scan</Btn>}
            <Btn size="sm" onClick={() => { loadSummary(); loadRows() }}>Refresh</Btn>
          </div>
        </div>
        <div style={{ ...grid, gridTemplateColumns: '150px 1fr 150px 1fr', marginTop: 12 }}>
          <Field label="Status" value={<span style={{ color: connected ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>{connected ? '● Connected' : `○ Offline${network?.error ? ` — ${network.error}` : ''}`}</span>} />
          <Field label="Network" value={network?.network ? `${network.network} · chain ${network.chainId}` : '—'} />
          <Field label="Smart Contract" value={short(network?.contractAddress || data.status?.contractAddress, 10, 8)} copy={network?.contractAddress || data.status?.contractAddress} monoValue />
          <Field label="Latest Block" value={network?.latestBlock ?? data.status?.latestBlock ?? '—'} />
          <Field label="Signing Wallet" value={short(network?.walletAddress, 10, 8)} copy={network?.walletAddress} monoValue />
          <Field label="Wallet Authorised" value={network?.walletAuthorised === undefined ? 'n/a (legacy contract)' : network.walletAuthorised ? 'Yes' : 'No — registrations will be rejected'} />
          <Field label="RPC Latency" value={network?.latencyMs ? `${network.latencyMs} ms` : '—'} />
          <Field label="Confirmations Required" value={network?.confirmationsRequired ?? '—'} />
        </div>
        {scan && <div style={{ marginTop: 12 }}><AlertBox type={scan.Inconsistent ? 'warning' : 'success'}>Integrity scan: {scan.Consistent} consistent · {scan.Warning} with warnings · {scan.Inconsistent} inconsistent (details in the audit log)</AlertBox></div>}
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 16 }}>
        {stats.map(([label, value, color]) => (
          <Card key={label}>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>{label}</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 24, marginTop: 6, color: color || 'var(--text)' }}>{value ?? 0}</div>
          </Card>
        ))}
      </div>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px' }}>
            <Input label="Search" placeholder="Evidence name, SHA-256 or transaction hash" value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0) }} />
          </div>
          <div style={{ width: 200 }}>
            <Select label="Verification status" value={statusFilter} options={STATUS_FILTERS.map((s) => ({ value: s, label: s }))}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }} />
          </div>
        </div>
        <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--r)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>{['Evidence', 'SHA-256', 'Blockchain', 'Transaction Hash', 'Block', 'Wallet', 'Registered', 'Network', 'Contract', 'Gas Used', 'Verification', 'Actions']
                .map((h) => <th key={h} style={head}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {loadingRows && <tr><td colSpan={12} style={{ ...cell, textAlign: 'center' }}><Spinner /></td></tr>}
              {!loadingRows && rows.length === 0 && <tr><td colSpan={12} style={{ ...cell, textAlign: 'center', color: 'var(--text3)' }}>No evidence matches.</td></tr>}
              {!loadingRows && rows.map((row) => (
                <React.Fragment key={row.id}>
                  <tr>
                    <td style={cell}>
                      <div style={{ fontWeight: 600, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }} title={row.fileName || ''}>{row.fileName || 'Evidence'}</div>
                      <div style={{ ...mono, color: 'var(--text3)' }}>{short(row.id, 8, 4)}<CopyButton value={row.id} label="evidence ID" /></div>
                    </td>
                    <td style={{ ...cell, ...mono }}>{short(row.sha256, 10, 6)}<CopyButton value={row.sha256} label="SHA-256" /></td>
                    <td style={cell}><Badge label={row.blockchainStatus} /></td>
                    <td style={{ ...cell, ...mono }}>
                      {row.transactionHash
                        ? <><a onClick={() => setOpenTx(row.transactionHash as string)} style={{ color: 'var(--blue)', cursor: 'pointer' }} title="View transaction details">{short(hex0x(row.transactionHash), 10, 6)}</a><CopyButton value={hex0x(row.transactionHash)} label="transaction hash" /></>
                        : '—'}
                    </td>
                    <td style={cell}>{row.blockNumber ?? '—'}</td>
                    <td style={{ ...cell, ...mono }}>{short(row.walletAddress, 8, 6)}<CopyButton value={row.walletAddress} label="wallet address" /></td>
                    <td style={cell}>{when(row.registeredAt)}</td>
                    <td style={cell}>{row.network ?? '—'}</td>
                    <td style={{ ...cell, ...mono }} title={row.contractAddress || ''}>{short(row.contractAddress, 8, 6)}</td>
                    <td style={cell}>{row.gasUsed?.toLocaleString() ?? '—'}</td>
                    <td style={cell} title={row.verificationReason || ''}><Badge label={row.verificationStatus} /></td>
                    <td style={cell}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <Btn size="xs" onClick={() => setOpenEvidence(row.id)}>Details</Btn>
                        <Btn size="xs" onClick={() => refreshVerification(row.id)} loading={verifying === row.id}>Re-verify</Btn>
                      </div>
                    </td>
                  </tr>
                  {rowNotice[row.id] && <tr><td colSpan={12} style={{ ...cell, whiteSpace: 'normal', fontSize: 11, color: 'var(--text2)', background: 'var(--bg3)' }}>{rowNotice[row.id]}</td></tr>}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, fontSize: 12, color: 'var(--text3)' }}>
          <span>{total} evidence item(s)</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn size="xs" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Btn>
            <span style={{ alignSelf: 'center' }}>Page {page + 1} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
            <Btn size="xs" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)}>Next</Btn>
          </div>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <Card>
          <CardTitle>Latest Blockchain Transactions</CardTitle>
          {!data.latestTransactions?.length && <div style={{ fontSize: 12, color: 'var(--text3)' }}>No transactions yet.</div>}
          {data.latestTransactions?.map((t: any) => (
            <div key={`${t.id}`} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 11.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>{t.event} · block {t.blockNumber ?? '—'}</span><span style={{ color: 'var(--text3)' }}>{when(t.createdAt)}</span></div>
              {t.transactionHash && <a onClick={() => setOpenTx(t.transactionHash)} style={{ ...mono, color: 'var(--blue)', cursor: 'pointer' }}>{short(hex0x(t.transactionHash), 14, 10)}</a>}
            </div>
          ))}
        </Card>
        <Card>
          <CardTitle>Latest Verification Events</CardTitle>
          {!data.latestVerificationEvents?.length && <div style={{ fontSize: 12, color: 'var(--text3)' }}>No verification events yet.</div>}
          {data.latestVerificationEvents?.map((v: any, i: number) => (
            <div key={`${v.createdAt}-${i}`} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 11.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span><Badge label={v.result || v.action} /> <span style={{ marginLeft: 6 }}>{v.action}</span></span>
                <span style={{ color: 'var(--text3)' }}>{when(v.createdAt)}</span>
              </div>
              <div style={{ color: 'var(--text3)', marginTop: 3 }}>
                {v.userName || 'Unknown user'}{v.reason ? ` · ${v.reason}` : ''}
                {v.evidenceId && <> · <a onClick={() => setOpenEvidence(v.evidenceId)} style={{ color: 'var(--blue)', cursor: 'pointer' }}>{short(v.evidenceId, 8, 4)}</a></>}
              </div>
            </div>
          ))}
        </Card>
      </div>

      <EvidenceModal evidenceId={openEvidence} onClose={() => setOpenEvidence(null)} onOpenTx={(hash) => setOpenTx(hash)}
        onVerified={() => { loadRows(); loadSummary() }} />
      <TransactionModal txHash={openTx} onClose={() => setOpenTx(null)} />
    </AppShell>
  )
}
