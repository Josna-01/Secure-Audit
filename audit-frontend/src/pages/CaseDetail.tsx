import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, Badge, Tabs, InfoRow, HashChip, AlertBox, Spinner } from '../components/UI'
import { OcrTextViewer } from '../components/OcrTextViewer'
import { api, describeVerification } from '../services/api'
import type { Case, Evidence, BNSResult, Storyboard, CustodyRecord } from '../types'
import { format } from 'date-fns'
import { useAuth } from '../context/AuthContext'

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'Admin'
  const [showMetadata, setShowMetadata] = useState(false)
  const [activeTab, setActiveTab] = useState(0)
  const [cas, setCas] = useState<Case | null>(null)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [bnsResult, setBnsResult] = useState<BNSResult | null>(null)
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [storyLoading, setStoryLoading] = useState(false)
  const [selectedOcrEvidenceId, setSelectedOcrEvidenceId] = useState('')
  const [selectedOcrLang, setSelectedOcrLang] = useState('auto')
  const [ocrRunning, setOcrRunning] = useState(false)
  const [ocrResult, setOcrResult] = useState<any | null>(null)
  const [ocrError, setOcrError] = useState('')
  const [ocrRunLang, setOcrRunLang] = useState('auto')
  const [chainData, setChainData] = useState<Record<string, { status: any; custodyHistory: CustodyRecord[] }>>({})
  const [verifyResult, setVerifyResult] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.getCase(id),
      api.getEvidence(id),
      api.getBNSResults(id)
    ]).then(([caseRes, evRes, bnsRes]) => {
      setCas(caseRes.data)
      setEvidence(evRes.data)
      setBnsResult(bnsRes.data[0] || null)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [id])

  const loadBlockchain = async (evidenceId: string) => {
    try { const result = await api.getEvidenceBlockchain(evidenceId); setChainData((current) => ({ ...current, [evidenceId]: result.data })) }
    catch (e: any) { setVerifyResult((current) => ({ ...current, [evidenceId]: e.response?.data?.detail || 'Blockchain details unavailable' })) }
  }

  const verifyIntegrity = async (evidenceId: string) => {
    setVerifyResult((current) => ({ ...current, [evidenceId]: 'Verifying integrity on Ethereum…' }))
    try {
      const result = await api.verifyHash(evidenceId)
      setVerifyResult((current) => ({ ...current, [evidenceId]: describeVerification(result.data) }))
      await loadBlockchain(evidenceId)
      const evRes = await api.getEvidence(id); setEvidence(evRes.data)
    } catch (e: any) {
      setVerifyResult((current) => ({ ...current, [evidenceId]: describeVerification(null, e) }))
      const evRes = await api.getEvidence(id); setEvidence(evRes.data)  // may now be Missing / Unregistered
    }
  }

  const generateStoryboard = async () => {
    if (!id) return
    setStoryLoading(true)
    try {
      const res = await api.generateStoryboard(id)
      setStoryboard(res.data)
    } catch { /* show error */ }
    finally { setStoryLoading(false) }
  }

  if (loading) return (
    <AppShell title="Case Detail">
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}><Spinner size={32} /></div>
    </AppShell>
  )

  if (!cas) return (
    <AppShell title="Case Detail">
      <AlertBox type="error">Case not found.</AlertBox>
    </AppShell>
  )

  return (
    <AppShell title={`${cas.case_number} — ${cas.title}`}>
      {/* Case header */}
      <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', padding: '16px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--blue)', fontWeight: 600 }}>{cas.case_number}</span>
              <Badge label={cas.status} />
              <span style={{ fontSize: '10px', fontWeight: 600, color: cas.priority === 'Critical' ? 'var(--red)' : cas.priority === 'High' ? 'var(--amber)' : 'var(--text3)' }}>{cas.priority}</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px' }}>{cas.title}</div>
            <div style={{ fontSize: '12px', color: 'var(--text3)' }}>{cas.offence_type} · {cas.investigator_name || 'Unassigned'} · {format(new Date(cas.created_at), 'dd MMM yyyy')}</div>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Btn size="xs" onClick={() => navigate('/detection')}>Run Detection</Btn>
            <Btn size="xs" onClick={() => navigate('/bns')}>BNS Classify</Btn>
            <Btn size="xs" onClick={() => navigate(`/audio?case_id=${cas.id}`)}>Audio Forensics</Btn>
            <Btn size="xs" onClick={() => navigate(`/photo3d?case_id=${cas.id}`)}>3D Reconstruction</Btn>
            <Btn size="xs" onClick={() => navigate('/evidence')}>Add Evidence</Btn>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs tabs={['Overview', 'Evidence', 'Detection', 'OCR Analysis', 'BNS', 'Storyboard / AI Insights']} activeIndex={activeTab} onChange={setActiveTab} />

      {/* Tab: Overview */}
      {activeTab === 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardTitle>Case Information</CardTitle>
              <InfoRow label="Case ID" value={cas.case_number} mono />
              <InfoRow label="Title" value={cas.title} />
              <InfoRow label="Offence Type" value={cas.offence_type} />
              <InfoRow label="Complainant" value={cas.complainant_name} />
              <InfoRow label="Incident Date" value={cas.incident_date || '—'} />
              <InfoRow label="Location" value={cas.incident_location || '—'} />
              <InfoRow label="Investigator" value={cas.investigator_name || '—'} />
              <InfoRow label="Created" value={format(new Date(cas.created_at), 'dd MMM yyyy HH:mm')} />
            </Card>
            <Card>
              <CardTitle>FIR / Complaint Description</CardTitle>
              <div style={{ fontSize: '13px', color: 'var(--text2)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{cas.fir_description}</div>
              {cas.fir_language && (
                <div style={{ marginTop: '10px', fontSize: '10px', color: 'var(--text3)' }}>Original language: {cas.fir_language} · Translated to English for AI processing</div>
              )}
            </Card>
            {isAdmin && (
              <Card>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }} onClick={() => setShowMetadata(!showMetadata)}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px' }}>Technical Metadata</div>
                  <span style={{ fontSize: '11px', color: 'var(--text3)' }}>{showMetadata ? '▲ Hide' : '▼ Show'}</span>
                </div>
                {showMetadata && (
                  <div style={{ marginTop: '12px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                    <InfoRow label="Case UUID" value={cas.id} mono />
                  </div>
                )}
              </Card>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardTitle>People</CardTitle>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text3)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Victims</div>
                {cas.victims?.length ? cas.victims.map((v, i) => (
                  <div key={i} style={{ padding: '6px 10px', background: 'var(--bg3)', borderRadius: 'var(--r)', marginBottom: '4px', fontSize: '12px', color: 'var(--text2)' }}>{v.name}</div>
                )) : <div style={{ fontSize: '12px', color: 'var(--text3)' }}>None recorded</div>}
              </div>
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text3)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Suspects</div>
                {cas.suspects?.length ? cas.suspects.map((s, i) => (
                  <div key={i} style={{ padding: '6px 10px', background: 'var(--bg3)', borderRadius: 'var(--r)', marginBottom: '4px', fontSize: '12px', color: 'var(--text2)' }}>{s.name}</div>
                )) : <div style={{ fontSize: '12px', color: 'var(--text3)' }}>None recorded</div>}
              </div>
            </Card>
            <Card>
              <CardTitle>Quick Stats</CardTitle>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {[['Evidence Files', evidence.length], ['BNS Sections', (bnsResult?.bns || bnsResult?.sections)?.length || 0], ['Tampered', evidence.filter((e) => e.status === 'Tampered').length], ['Verified', evidence.filter((e) => e.status === 'Verified').length]].map(([k, v]) => (
                  <div key={k} style={{ textAlign: 'center', padding: '12px', background: 'var(--bg3)', borderRadius: 'var(--r)' }}>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)', fontFamily: 'var(--mono)' }}>{v}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '4px' }}>{k}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Tab: Evidence */}
      {activeTab === 1 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
            <Btn variant="primary" size="sm" onClick={() => navigate('/evidence')}>+ Add Evidence</Btn>
          </div>
          {evidence.length === 0 && (
            <Card style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text3)' }}>No evidence uploaded yet</div>
            </Card>
          )}
          {evidence.map((f) => (
            <div key={f.id} style={{ border: '1px solid var(--border)', borderLeft: `3px solid ${f.status === 'Tampered' || f.status === 'Missing' ? 'var(--red)' : f.status === 'Unregistered' ? 'var(--amber)' : 'var(--green)'}`, borderRadius: 'var(--r)', padding: '10px 12px', background: 'var(--bg3)', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.file_name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>{f.file_type} · {(f.file_size / 1024 / 1024).toFixed(2)} MB · {format(new Date(f.uploaded_at), 'dd MMM yyyy HH:mm')}</div>
                </div>
                <Badge label={f.status} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                <HashChip hash={f.sha256_hash} />
                <div style={{ flex: 1 }} />
                <Btn size="xs" onClick={() => verifyIntegrity(f.id)}>Verify Integrity</Btn>
                <Btn size="xs" onClick={() => loadBlockchain(f.id)}>Blockchain Details</Btn>
                {f.file_type === 'Audio' ? (
                  <Btn size="xs" onClick={() => navigate(`/audio?case_id=${cas.id}&evidence_id=${f.id}`)}>Analyze Audio</Btn>
                ) : f.file_type === 'Video' ? (
                  <Btn size="xs" onClick={() => navigate(`/photo3d?case_id=${cas.id}&evidence_id=${f.id}`)}>3D Reconstruct</Btn>
                ) : (
                  <Btn size="xs" onClick={() => navigate('/detection')}>Run YOLO</Btn>
                )}
              </div>
              {f.status === 'Missing' && (
                <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--red)', padding: '4px 8px', background: 'var(--red-bg)', borderRadius: '4px' }}>Evidence file is missing from storage — integrity cannot be verified</div>
              )}
              {f.status === 'Unregistered' && (
                <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--amber)', padding: '4px 8px', background: 'var(--amber-bg)', borderRadius: '4px' }}>Not registered on the blockchain — integrity cannot be verified</div>
              )}
              {f.status === 'Tampered' && (
                <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--red)', padding: '4px 8px', background: 'var(--red-bg)', borderRadius: '4px' }}>Hash mismatch — file may have been modified after upload</div>
              )}
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)', fontSize: 11 }}>
                <div style={{ color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px', marginBottom: 6 }}>Blockchain Status</div>
                <div style={{ color: chainData[f.id]?.status?.connected ? 'var(--green)' : 'var(--text3)' }}>{chainData[f.id]?.status?.connected ? 'Connected' : 'Load blockchain details to check status'}</div>
                {f.blockchain && <div style={{ display: 'grid', gridTemplateColumns: '130px 1fr', gap: '4px 8px', marginTop: 7, color: 'var(--text2)' }}>
                  <span>Evidence Hash</span><span style={{ fontFamily: 'var(--mono)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.sha256_hash}</span>
                  <span>Transaction Hash</span><span style={{ fontFamily: 'var(--mono)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.blockchain.transactionHash || '—'}</span>
                  <span>Block Number</span><span>{f.blockchain.blockNumber ?? '—'}</span><span>Contract Address</span><span style={{ fontFamily: 'var(--mono)' }}>{f.blockchain.contractAddress || '—'}</span>
                  <span>Gas Used</span><span>{f.blockchain.gasUsed ?? '—'}</span><span>Latest Verification</span><span>{f.blockchain.latestVerificationAt ? new Date(f.blockchain.latestVerificationAt).toLocaleString() : '—'}</span>
                </div>}
                {verifyResult[f.id] && <div style={{ marginTop: 7, color: verifyResult[f.id].startsWith('✓') && !verifyResult[f.id].includes('⚠') ? 'var(--green)' : verifyResult[f.id].startsWith('⚠') ? 'var(--red)' : 'var(--text2)' }}>{verifyResult[f.id]}</div>}
                {chainData[f.id]?.custodyHistory?.length > 0 && <div style={{ marginTop: 9 }}><div style={{ color: 'var(--text3)', marginBottom: 5 }}>Chain of Custody Timeline</div>{chainData[f.id].custodyHistory.map((record, index) => <div key={`${record.timestamp}-${index}`} style={{ padding: '4px 0', borderLeft: '2px solid var(--blue)', paddingLeft: 8 }}>{record.action} · {record.officerId} · {new Date(record.timestamp).toLocaleString()}</div>)}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab: Detection */}
      {activeTab === 2 && (
        <Card style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '13px', color: 'var(--text3)', marginBottom: '16px' }}>Run YOLO Object Detection on crime scene images for this case</div>
          <Btn variant="primary" onClick={() => navigate('/detection')}>Go to Object Detection</Btn>
        </Card>
      )}

      {/* Tab: OCR Analysis */}
      {activeTab === 3 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '16px', alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardTitle>OCR Configuration</CardTitle>
              {ocrError && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{ocrError}</AlertBox></div>}
              
              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Evidence Document/Image</label>
                <select 
                  value={selectedOcrEvidenceId} 
                  onChange={(e) => {
                    setSelectedOcrEvidenceId(e.target.value)
                    setOcrResult(null)
                    setOcrError('')
                  }} 
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                >
                  <option value="">Select file from case evidence...</option>
                  {evidence.map((f) => (
                    <option key={f.id} value={f.id}>{f.file_name} ({f.file_type})</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>OCR Language Mode</label>
                <select 
                  value={selectedOcrLang} 
                  onChange={(e) => setSelectedOcrLang(e.target.value)} 
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                >
                  <option value="auto">Auto-detect (all supported languages)</option>
                  <option value="eng">English (eng)</option>
                  <option value="hin">Hindi (hin)</option>
                  <option value="kan">Kannada (kan)</option>
                  <option value="tel">Telugu (tel)</option>
                  <option value="tam">Tamil (tam)</option>
                  <option value="mal">Malayalam (mal)</option>
                  <option value="eng+hin">English + Hindi</option>
                  <option value="eng+kan">English + Kannada</option>
                </select>
              </div>

              <Btn 
                variant="primary" 
                full 
                loading={ocrRunning} 
                onClick={async () => {
                  if (!selectedOcrEvidenceId) {
                    setOcrError('Please select an evidence file.')
                    return
                  }
                  setOcrRunning(true)
                  setOcrError('')
                  setOcrResult(null)
                  try {
                    const res = await api.runOCR(selectedOcrEvidenceId, selectedOcrLang)
                    setOcrResult(res.data)
                    setOcrRunLang(selectedOcrLang)
                  } catch (err: any) {
                    const msg = err.response?.data?.detail || err.message || 'OCR extraction failed.'
                    setOcrError(msg)
                  } finally {
                    setOcrRunning(false)
                  }
                }}
              >
                Run OCR Processing
              </Btn>
            </Card>

            {ocrResult && (
              <Card>
                <CardTitle>OCR Processing Summary</CardTitle>
                <InfoRow label="Extraction Status" value={<Badge label="Verified" />} />
                <InfoRow label="Language Config" value={ocrResult.language} mono />
                {ocrResult.detected_languages?.length > 0 && (
                  <InfoRow
                    label="Detected Languages"
                    value={ocrResult.detected_languages.map((l: any) => `${l.name} ${Math.round(l.ratio * 100)}%`).join(', ')}
                  />
                )}
                <InfoRow
                  label="Average Confidence" 
                  value={
                    <span style={{ color: ocrResult.confidence > 0.8 ? 'var(--green)' : ocrResult.confidence > 0.5 ? 'var(--amber)' : 'var(--red)', fontWeight: 600 }}>
                      {Math.round(ocrResult.confidence * 100)}%
                    </span>
                  } 
                />
                <InfoRow label="Pages Processed" value={ocrResult.total_pages ?? (ocrResult.pages?.length || 1)} />
                {ocrResult.processing_time_ms !== undefined && (
                  <InfoRow
                    label="Processing Time"
                    value={ocrResult.cached ? 'Cached result' : `${(ocrResult.processing_time_ms / 1000).toFixed(1)}s`}
                  />
                )}
                {ocrResult.warnings?.length > 0 && (
                  <div style={{ marginTop: '8px' }}><AlertBox type="warning">{ocrResult.warnings.join(' · ')}</AlertBox></div>
                )}
              </Card>
            )}
          </div>

          <Card style={{ minHeight: '350px' }}>
            <CardTitle>Extracted Content Viewer</CardTitle>

            {!ocrResult && !ocrRunning && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '250px', color: 'var(--text3)', fontSize: '12px' }}>
                Select an evidence file and click Run OCR Processing to extract text.
              </div>
            )}

            {ocrRunning && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '250px', gap: '12px' }}>
                <Spinner size={24} />
                <div style={{ fontSize: '11px', color: 'var(--text3)' }}>Detecting page layout, languages and text...</div>
              </div>
            )}

            {ocrResult && !ocrRunning && (
              <OcrTextViewer
                result={ocrResult}
                downloadName={`ocr_evidence_${id}`}
                onTranslate={async (target) => {
                  const res = await api.runOCR(ocrResult.evidence_id, ocrRunLang, { translate: true, target_language: target })
                  setOcrResult(res.data)
                }}
              />
            )}
          </Card>
        </div>
      )}

      {/* Tab: BNS */}
      {activeTab === 4 && (
        <div>
          {!bnsResult ? (
            <Card style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text3)', marginBottom: '16px' }}>BNS classification not yet run for this case</div>
              <Btn variant="primary" onClick={() => navigate('/bns')}>Run BNS Classification</Btn>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>BNS Section Predictions &amp; Legal Dossier</CardTitle>
                <span style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 500 }}>
                  {(bnsResult?.bns || bnsResult?.sections)?.length || 0} Applicable Sections
                </span>
              </CardHeader>
              <div style={{ padding: '10px 14px', background: 'var(--purple-bg)', border: '1px solid var(--purple)', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--purple)', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  Bharatiya Nyaya Sanhita (BNS) · Crime Type: <span style={{ fontWeight: 700 }}>{bnsResult.crime_type}</span>
                </div>
                <Btn size="xs" onClick={() => navigate('/bns')}>Re-Classify</Btn>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(bnsResult?.bns || bnsResult?.sections)?.map((s: any) => {
                  const confVal = s.confidence !== undefined ? s.confidence : (s.score || 0)
                  const confPct = s.confidence_percent || (confVal > 0 ? `${Math.round(confVal * 100)}%` : '')
                  
                  return (
                    <div key={s.section_id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', background: 'var(--bg2)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 700, color: 'var(--purple)', background: 'var(--purple-bg)', padding: '2px 6px', borderRadius: '3px' }}>
                            BNS {s.section_id}
                          </span>
                          <span style={{ fontSize: '13px', color: 'var(--text)', fontWeight: 600 }}>
                            {s.title || s.name}
                          </span>
                        </div>
                        {confPct && (
                          <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', fontWeight: 700, color: confVal >= 0.8 ? 'var(--green)' : 'var(--blue)', background: 'var(--bg3)', padding: '2px 6px', borderRadius: '3px' }}>
                            {confPct}
                          </span>
                        )}
                      </div>

                      {s.explanation && (
                        <div style={{ fontSize: '12px', color: 'var(--text)', background: 'rgba(99, 102, 241, 0.08)', padding: '6px 10px', borderRadius: 'var(--r)', marginBottom: '6px', borderLeft: '3px solid var(--purple)' }}>
                          {s.explanation}
                        </div>
                      )}

                      <div style={{ fontSize: '11px', color: 'var(--text3)', lineHeight: 1.5 }}>
                        {s.description || s.meaning}
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Tab: Storyboard */}
      {activeTab === 5 && (

        <div>
          {!storyboard && !storyLoading && (
            <Card style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text3)', marginBottom: '16px' }}>Generate an AI-powered incident narrative from FIR and evidence</div>
              <Btn variant="primary" onClick={generateStoryboard}>Generate Storyboard</Btn>
            </Card>
          )}
          {storyLoading && (
            <Card style={{ textAlign: 'center', padding: '40px' }}>
              <Spinner size={28} />
              <div style={{ fontSize: '12px', color: 'var(--text3)', marginTop: '12px' }}>Generating narrative from FIR and evidence...</div>
            </Card>
          )}
          {storyboard && (
            <div>
              <Card style={{ marginBottom: '16px' }}>
                <CardHeader>
                  <CardTitle>AI Storyboard — {cas.case_number}</CardTitle>
                  <Btn size="xs" loading={storyLoading} onClick={generateStoryboard}>Regenerate</Btn>
                </CardHeader>
                <div style={{ padding: '8px 12px', background: 'var(--amber-bg)', border: '1px solid var(--amber)', borderRadius: 'var(--r)', fontSize: '11px', color: 'var(--amber)', marginBottom: '16px' }}>
                  AI-generated insights are for investigation support only and do not constitute legal conclusions.
                </div>
                {storyboard.steps.map((s, i) => (
                  <div key={i}>
                    <div style={{ display: 'flex', gap: '14px', marginBottom: '8px' }}>
                      <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: 'var(--blue-bg)', border: '1.5px solid var(--blue)', color: 'var(--blue)', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{s.step}</div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: '4px' }}>{s.label}</div>
                        <div style={{ fontSize: '13px', color: 'var(--text2)', lineHeight: 1.6 }}>{s.content}</div>
                      </div>
                    </div>
                    {i < storyboard.steps.length - 1 && <div style={{ marginLeft: '14px', borderLeft: '1.5px dashed var(--border2)', height: '16px' }} />}
                  </div>
                ))}
                <div style={{ padding: '12px 14px', background: 'var(--purple-bg)', border: '1px solid var(--purple)', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--purple)', marginTop: '16px' }}>
                  Conclusion: {storyboard.conclusion}
                </div>
              </Card>
              <Card>
                <CardTitle>Evidence Insights Summary</CardTitle>
                {storyboard.evidence_insights.map((ins, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '7px 10px', background: 'var(--bg3)', borderRadius: 'var(--r)', marginBottom: '6px', fontSize: '12px', color: 'var(--text2)' }}>
                    <span style={{ color: 'var(--blue)', fontWeight: 600 }}>→</span> {ins}
                  </div>
                ))}
              </Card>
            </div>
          )}
        </div>
      )}
    </AppShell>
  )
}
