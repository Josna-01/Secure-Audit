// ── EVIDENCE UPLOAD ───────────────────────────────────────────────────────
import React, { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, Badge, HashChip, AlertBox, FutureNotice, UploadZone, InfoRow, Spinner, Tabs } from '../components/UI'
import { api } from '../services/api'
import type { Evidence, Case } from '../types'
import { format } from 'date-fns'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'

// ── EVIDENCE ──────────────────────────────────────────────────────────────
export function EvidencePage() {
  const [caseSearch, setCaseSearch] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [evidenceType, setEvidenceType] = useState('Image')
  const [language, setLanguage] = useState('auto')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [err, setErr] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    try {
      const res = await api.getCases({ search: q, per_page: 5 })
      setCaseResults(res.data)
    } catch { /* ignore */ }
  }

  const fetchEvidence = async () => {
    try {
      const res = await api.getEvidence(selectedCase?.id)
      setEvidence(res.data)
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchEvidence() }, [selectedCase])

  const handleUpload = async () => {
    if (!selectedCase) { setErr('Please select a case first.'); return }
    if (!file) { setErr('Please select a file.'); return }
    setUploading(true); setErr('')
    try {
      await api.uploadEvidence(selectedCase.id, file, { evidence_type: evidenceType, description, language })
      setUploadDone(true); setFile(null)
      await fetchEvidence()
    } catch (error: any) {
      console.error("[DEBUG] Upload Error:", error.response?.data || error)
      const errorDetail = error.response?.data?.detail || error.message || 'Unknown error'
      if (Array.isArray(errorDetail)) {
        setErr(`Upload failed: ${errorDetail[0]?.msg} (${errorDetail[0]?.loc?.join('.')})`)
      } else {
        setErr(`Upload failed: ${errorDetail}`)
      }
    }
    finally { setUploading(false) }
  }

  return (
    <AppShell title="Evidence Upload">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardTitle>Upload New Evidence</CardTitle>
            {err && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{err}</AlertBox></div>}

            {/* Case search */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Search / Link to Case</label>
              <div style={{ position: 'relative' }}>
                <input
                  value={caseSearch}
                  onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
                  placeholder="Case ID, title, victim name..."
                  style={{ width: '100%', paddingLeft: '10px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                />
              </div>
              {caseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px', overflow: 'hidden' }}>
                  {caseResults.map((c) => (
                    <div key={c.id} onClick={() => { setSelectedCase(c); setCaseSearch(''); setCaseResults([]) }}
                      style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{c.case_number}</span> — {c.title}
                    </div>
                  ))}
                </div>
              )}
              {selectedCase && (
                <div style={{ marginTop: '6px', padding: '8px 10px', background: 'var(--blue-dim)', border: '1px solid var(--blue)', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--blue)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{selectedCase.case_number} — {selectedCase.title}</span>
                  <span style={{ cursor: 'pointer', fontSize: '11px' }} onClick={() => setSelectedCase(null)}>Clear</span>
                </div>
              )}
              <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '4px' }}>Evidence must always be linked to a case</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Evidence Type</label>
                <select value={evidenceType} onChange={(e) => setEvidenceType(e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                  {['Image', 'Video', 'Audio', 'Document', 'FIR'].map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Language</label>
                <select value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                  {[['auto', 'Auto Detect'], ['en', 'English'], ['hi', 'Hindi'], ['kn', 'Kannada']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Description / Notes</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Brief description of this evidence item..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', resize: 'vertical' }} />
            </div>

            <input ref={fileRef} type="file" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <UploadZone
              title={file ? file.name : 'Drop file here or click to browse'}
              sub="JPG · PNG · MP4 · MP3 · WAV · PDF · DOCX · Max 500MB"
              onClick={() => fileRef.current?.click()}
              onDropFile={(f) => setFile(f)}
            />

            <Btn variant="primary" full loading={uploading} onClick={handleUpload}>
              Upload &amp; Generate SHA-256 Hash
            </Btn>
            {uploadDone && <div style={{ marginTop: '10px' }}><AlertBox type="success">Evidence uploaded · SHA-256 generated · Audit log entry created</AlertBox></div>}
          </Card>
        </div>

        {/* Evidence List */}
        <Card>
          <CardHeader>
            <CardTitle>Evidence Files{selectedCase ? ` · ${selectedCase.case_number}` : ''}</CardTitle>
            <span style={{ fontSize: '11px', color: 'var(--text3)' }}>{evidence.length} files</span>
          </CardHeader>
          {evidence.length === 0 && <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)', fontSize: '12px' }}>No evidence uploaded yet</div>}
          {evidence.map((f) => (
            <div key={f.id} style={{ border: '1px solid var(--border)', borderLeft: `3px solid ${f.status === 'Tampered' ? 'var(--red)' : 'var(--green)'}`, borderRadius: 'var(--r)', padding: '10px 12px', background: 'var(--bg3)', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.file_name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>{f.file_type} · {(f.file_size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
                <Badge label={f.status} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                <HashChip hash={f.sha256_hash} />
                <div style={{ flex: 1 }} />
                <Btn size="xs" onClick={() => api.verifyHash(f.id).then(() => alert('Hash verified'))}>Verify Hash</Btn>
              </div>
              {f.status === 'Tampered' && <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--red)', padding: '4px 8px', background: 'var(--red-bg)', borderRadius: '4px' }}>Hash mismatch detected</div>}
            </div>
          ))}
        </Card>
      </div>
    </AppShell>
  )
}

// ── OBJECT DETECTION ──────────────────────────────────────────────────────
export function DetectionPage() {
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseSearch, setCaseSearch] = useState('')
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [evidenceFiles, setEvidenceFiles] = useState<Evidence[]>([])
  const [selectedEvidence, setSelectedEvidence] = useState<string>('')
  const [imgSource, setImgSource] = useState<'upload' | 'evidence'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<import('../types').DetectionResult | null>(null)
  const [err, setErr] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    const res = await api.getCases({ search: q, per_page: 5 })
    setCaseResults(res.data)
  }

  const selectCase = async (c: Case) => {
    setSelectedCase(c); setCaseSearch(''); setCaseResults([])
    const ev = await api.getEvidence(c.id)
    setEvidenceFiles(ev.data.filter((e) => e.file_type === 'Image'))
  }

  const runDetection = async () => {
    if (!selectedCase) { setErr('Select a case first.'); return }
    let evId = imgSource === 'evidence' ? selectedEvidence : ''
    if (imgSource === 'evidence' && !evId) { setErr('Select an evidence image.'); return }
    if (imgSource === 'upload' && !file) { setErr('Upload an image first.'); return }
    setRunning(true); setErr(''); setResult(null)
    try {
      if (imgSource === 'upload' && file) {
        const upRes = await api.uploadEvidence(selectedCase.id, file, { evidence_type: 'Image' })
        evId = upRes.data.id
      }
      const res = await api.runDetection(evId, selectedCase.id)
      setResult(res.data)
    } catch (error: any) {
      console.error("[DEBUG] Detection API Error:", error.response?.data || error)
      const errorDetail = error.response?.data?.detail || error.message || 'Unknown error'
      setErr(`Detection failed: ${errorDetail}`)
    }
    finally { setRunning(false) }
  }

  return (
    <AppShell title="Object Detection — YOLO">
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 7fr', gap: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardTitle>Upload Crime Scene Image</CardTitle>
            {err && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{err}</AlertBox></div>}

            {/* Case link */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Case</label>
              <input value={caseSearch} onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }} placeholder="Search case..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
              {caseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px' }}>
                  {caseResults.map((c) => <div key={c.id} onClick={() => selectCase(c)} style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}><span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{c.case_number}</span> — {c.title}</div>)}
                </div>
              )}
              {selectedCase && <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--blue)', fontWeight: 500 }}>{selectedCase.case_number} — {selectedCase.title}</div>}
            </div>

            {/* Source selector */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Image Source</label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <Btn size="xs" variant={imgSource === 'upload' ? 'primary' : 'default'} onClick={() => setImgSource('upload')}>Upload New</Btn>
                <Btn size="xs" variant={imgSource === 'evidence' ? 'primary' : 'default'} onClick={() => setImgSource('evidence')} disabled={evidenceFiles.length === 0}>From Evidence</Btn>
              </div>
            </div>

            {imgSource === 'upload' && (
              <>
                <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] || null)} />
                <UploadZone
                  title={file ? file.name : 'Drag & Drop or Click to Upload'}
                  sub="JPG · PNG · Max 20MB"
                  onClick={() => fileRef.current?.click()}
                  onDropFile={(f) => setFile(f)}
                />
              </>
            )}
            {imgSource === 'evidence' && (
              <select value={selectedEvidence} onChange={(e) => setSelectedEvidence(e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', marginBottom: '12px' }}>
                <option value="">Select evidence image...</option>
                {evidenceFiles.map((f) => <option key={f.id} value={f.id}>{f.file_name}</option>)}
              </select>
            )}

            <Btn variant="primary" full loading={running} onClick={runDetection}>Run Object Detection</Btn>
          </Card>

          {/* Results */}
          {result && (
            <Card>
              <CardHeader>
                <CardTitle>Detection Results</CardTitle>
                <span style={{ fontSize: '10px', color: 'var(--green)' }}>{result.objects.length} objects detected</span>
              </CardHeader>
              {result.objects.map((obj, i) => (
                <div key={i} style={{ marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '10px', fontWeight: 600, padding: '2px 9px', borderRadius: '20px', color: 'var(--red)', background: 'var(--red-bg)', minWidth: '100px', textAlign: 'center' }}>{obj.label}</span>
                    <div style={{ flex: 1, background: 'var(--bg4)', borderRadius: '2px', height: '5px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', background: 'var(--red)', width: `${Math.round(obj.confidence * 100)}%` }} />
                    </div>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text3)', minWidth: '30px', textAlign: 'right' }}>{Math.round(obj.confidence * 100)}%</span>
                  </div>
                  <div style={{ marginLeft: '112px', fontSize: '10px', color: 'var(--text3)', fontFamily: 'var(--mono)' }} title="Format: [x, y, width, height] in pixels">
                    bbox: [{obj.bbox.join(', ')}]
                  </div>
                </div>
              ))}
              <AlertBox type="success">{result.objects.length} objects detected · Results saved to case · SHA-256 generated</AlertBox>
            </Card>
          )}
        </div>

        {/* Preview */}
        <Card>
          <CardTitle>Annotated Output Preview</CardTitle>
          <div style={{ background: 'var(--bg4)', borderRadius: 'var(--r)', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px', position: 'relative', overflow: 'hidden' }}>
            {!result ? (
              <>
                <div style={{ fontSize: '13px', color: 'var(--text3)' }}>Annotated image appears after detection</div>
                <div style={{ fontSize: '11px', color: 'var(--text3)' }}>Bounding boxes will be drawn on the image</div>
              </>
            ) : (
              <div style={{ padding: '16px', width: '100%', display: 'flex', flexDirection: 'column' }}>
                <div style={{ width: '100%', height: '550px', background: '#000', borderRadius: '4px', marginBottom: '16px', display: 'flex', justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }}>
                  <div style={{ position: 'relative', display: 'inline-flex', maxWidth: '100%', maxHeight: '100%' }}>
                    <img src={result.image_url} alt="Annotated Detection Output" style={{ display: 'block', maxWidth: '100%', maxHeight: '550px', objectFit: 'contain' }} />
                    {result.objects.map((obj, i) => {
                      const [left, top, w, h] = obj.bbox;
                      return (
                        <div key={i} style={{ position: 'absolute', border: '2px solid var(--red)', left, top, width: w, height: h, pointerEvents: 'none' }}>
                          <span style={{ background: 'var(--red)', color: '#fff', fontSize: '10px', fontWeight: 600, position: 'absolute', top: '-15px', left: '-2px', padding: '1px 4px', whiteSpace: 'nowrap' }}>
                            {obj.label} {Math.round(obj.confidence * 100)}%
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text3)', marginBottom: '10px' }}>Detection Legend</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                  {result.objects.map((obj, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                      <div style={{ width: '12px', height: '12px', border: '2px solid var(--red)', borderRadius: '2px', flexShrink: 0 }} />
                      <span style={{ fontSize: '11px', color: 'var(--text2)' }}>{obj.label}</span>
                      <span style={{ fontSize: '10px', fontFamily: 'var(--mono)', color: 'var(--text3)' }}>[{obj.bbox.join(', ')}]</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  )
}

// ── BNS CLASSIFICATION ────────────────────────────────────────────────────
export function BNSPage() {
  const [caseSearch, setCaseSearch] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [firText, setFirText] = useState('')
  const [language, setLanguage] = useState('auto')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<import('../types').BNSResult | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [err, setErr] = useState('')
  const [evidenceInsights] = useState(['Weapon detected in scene — supports violent offence', 'Physical confrontation evidence present', 'Multiple evidence items corroborate reported incident'])

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    const res = await api.getCases({ search: q, per_page: 5 })
    setCaseResults(res.data)
  }

  const selectCase = (c: Case) => {
    setSelectedCase(c); setCaseSearch(''); setCaseResults([])
    setFirText(c.fir_description || '')
  }

  const classify = async () => {
    if (!selectedCase) { setErr('Select a case first.'); return }
    if (!firText.trim()) { setErr('FIR description is required.'); return }
    setRunning(true); setErr(''); setResult(null); setAccepted(false)
    try {
      const res = await api.predictBNS(firText)
      setResult(res.data || res)
    } catch { setErr('Classification failed. Ensure the BNS model server is running on port 8001.') }
    finally { setRunning(false) }
  }

  const accept = async () => {
    if (!result || !selectedCase) return
    try {
      await api.storeBNS(selectedCase.id, result, firText)
      setAccepted(true)
    } catch {
      setErr('Failed to store BNS sections.')
    }
  }

  return (
    <AppShell title="BNS Section Classification">
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 5fr', gap: '16px', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardTitle>FIR Input</CardTitle>
            {err && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{err}</AlertBox></div>}
            <div style={{ marginBottom: '10px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Case Reference</label>
              <input value={caseSearch} onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }} placeholder="Search case to auto-fill FIR..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
              {caseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px' }}>
                  {caseResults.map((c) => <div key={c.id} onClick={() => selectCase(c)} style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}><span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{c.case_number}</span> — {c.title}</div>)}
                </div>
              )}
              {selectedCase && <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--blue)' }}>{selectedCase.case_number} — {selectedCase.title}</div>}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px' }}>FIR Narrative</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '3px 8px', fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                {[['auto', 'Auto Detect'], ['en', 'English'], ['hi', 'Hindi'], ['kn', 'Kannada']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <textarea value={firText} onChange={(e) => setFirText(e.target.value)} rows={20} placeholder="FIR text (auto-filled from case or enter manually)..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '9px 12px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', resize: 'vertical', lineHeight: 1.6, marginBottom: '12px' }} />
            <Btn variant="primary" full loading={running} onClick={classify}>Run BNS Classification</Btn>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>BNS Section Predictions</CardTitle>
            <span style={{ fontSize: '10px', color: result ? 'var(--green)' : 'var(--text3)' }}>{result ? 'Complete' : 'Awaiting input'}</span>
          </CardHeader>
          {!result && !running && <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)', fontSize: '12px' }}>Run classification to see predictions</div>}
          {running && (
            <div style={{ padding: '20px' }}>
              {['Detecting language & translating', 'FAISS RAG retrieval', 'LegalBERT embedding (768-dim)', 'HGAT classification (57 sections)'].map((s, i) => (
                <div key={i} style={{ marginBottom: '10px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', marginBottom: '3px' }}>{s}</div>
                  <div style={{ background: 'var(--bg4)', borderRadius: '2px', height: '5px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', background: 'var(--purple)', width: `${90 - i * 20}%`, transition: 'width .5s' }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          {result && (
            <>
              <div style={{ padding: '8px 12px', background: 'var(--purple-bg)', border: '1px solid var(--purple)', borderRadius: 'var(--r)', fontSize: '11px', color: 'var(--purple)', marginBottom: '16px' }}>
                Bharatiya Nyaya Sanhita (BNS) · Crime Type: <span style={{ fontWeight: 600 }}>{result.crime_type}</span> · {result.bns?.length || 0} sections applicable
              </div>
              {result.bns?.map((s: any) => (
                <div key={s.section_id} style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '5px' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--purple)', fontWeight: 600, minWidth: '80px' }}>{s.section_id}</span>
                    <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 500, flex: 1, whiteSpace: 'normal', wordBreak: 'break-word' }}>{s.name}</span>
                  </div>
                  <div style={{ marginLeft: '90px', fontSize: '11px', color: 'var(--text3)', marginTop: '2px', lineHeight: 1.5, whiteSpace: 'normal', wordBreak: 'break-word' }}>{s.meaning}</div>
                </div>
              ))}
              {!accepted ? (
                <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                  <Btn variant="primary" full onClick={accept}>Accept &amp; Save to Database</Btn>
                </div>
              ) : (
                <AlertBox type="success">BNS sections securely stored in Supabase and audit log generated</AlertBox>
              )}
            </>
          )}
        </Card>
      </div>
    </AppShell>
  )
}

// ── OCR ───────────────────────────────────────────────────────────────────
export function OCRPage() {
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('auto')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<{ extracted_text: string; translated_text?: string; detected_language: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const run = async () => {
    if (!file) { alert('Please select a file.'); return }
    setRunning(true)
    try {
      const res = await api.runOCR('temp', language)
      setResult(res.data)
    } catch { alert('OCR failed.') }
    finally { setRunning(false) }
  }

  return (
    <AppShell title="OCR Extraction">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardTitle>Upload Scanned FIR / Document</CardTitle>
            <input ref={fileRef} type="file" accept="image/*,.pdf" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <UploadZone
              title={file ? file.name : 'Upload scanned FIR for OCR extraction'}
              sub="JPG · PNG · PDF · Handwritten text supported"
              onClick={() => fileRef.current?.click()}
              onDropFile={(f) => setFile(f)}
            />
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Document Language</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                {[['auto', 'Auto Detect'], ['en', 'English'], ['hi', 'Hindi'], ['kn', 'Kannada'], ['ml', 'Malayalam']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <Btn variant="primary" full loading={running} onClick={run}>Extract Text via Tesseract</Btn>
          </Card>
          <Card>
            <CardTitle>Reference</CardTitle>
            {[['Engine', 'Tesseract 4.0 + LSTM'], ['Accuracy', '96.87% word accuracy'], ['Preprocessing', 'Leptonica binarisation'], ['Reference', 'Al Sayem et al. (2023)'], ['Output', 'Original + English translation']].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', gap: '10px', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: '11px', color: 'var(--text3)', minWidth: '100px' }}>{k}</span>
                <span style={{ fontSize: '11px', color: 'var(--text2)' }}>{v}</span>
              </div>
            ))}
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Extracted Text</CardTitle>
            <span style={{ fontSize: '10px', color: result ? 'var(--green)' : 'var(--text3)' }}>{result ? `Detected: ${result.detected_language}` : 'Awaiting upload'}</span>
          </CardHeader>
          {!result && <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)', fontSize: '12px' }}>Extracted text appears here after processing</div>}
          {result && (
            <div>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: '6px' }}>Original Text ({result.detected_language})</div>
                <div style={{ fontSize: '13px', color: 'var(--text2)', lineHeight: 1.7, padding: '10px', background: 'var(--bg3)', borderRadius: 'var(--r)', whiteSpace: 'pre-wrap' }}>{result.extracted_text}</div>
              </div>
              {result.translated_text && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: '6px' }}>Translated (English)</div>
                  <div style={{ fontSize: '13px', color: 'var(--text2)', lineHeight: 1.7, padding: '10px', background: 'var(--green-bg)', borderRadius: 'var(--r)', border: '1px solid var(--green)', whiteSpace: 'pre-wrap' }}>{result.translated_text}</div>
                </div>
              )}
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                <Btn size="sm">Use for BNS Classification</Btn>
                <Btn size="sm">Add to Case FIR</Btn>
              </div>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  )
}

// ── PLACEHOLDER PAGE ──────────────────────────────────────────────────────
export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <AppShell title={title}>
      <FutureNotice text="UI shown for stakeholder review and future scope demonstration" />
      <Card style={{ textAlign: 'center', padding: '60px' }}>
        <div style={{ fontSize: '13px', color: 'var(--text3)', marginBottom: '8px' }}>{description}</div>
        <div style={{ fontSize: '11px', color: 'var(--text3)' }}>Implementation planned for v2</div>
      </Card>
    </AppShell>
  )
}

// ── AUDIT LOG ─────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const isWarning = status === 'Warning'
  const isFailed = status === 'Failed'
  const bg = isWarning ? 'var(--amber-bg)' : isFailed ? 'var(--red-bg)' : 'var(--green-bg)'
  const color = isWarning ? 'var(--amber)' : isFailed ? 'var(--red)' : 'var(--green)'
  return (
    <span style={{
      fontSize: '10px',
      fontWeight: 600,
      padding: '2px 8px',
      borderRadius: '20px',
      background: bg,
      color: color,
      display: 'inline-block'
    }}>
      {status}
    </span>
  )
}

function formatUserEventDescription(log: any) {
  if (log.metadata?.description) {
    return log.metadata.description
  }
  const updates = log.metadata?.updates
  if (updates) {
    const changes: string[] = []
    if (updates.role !== undefined) {
      changes.push(`Role changed to ${updates.role}`)
    }
    if (updates.is_active !== undefined) {
      changes.push(updates.is_active ? 'Officer account activated' : 'Officer account deactivated')
    }
    if (updates.full_name !== undefined) {
      changes.push(`Name changed to ${updates.full_name}`)
    }
    if (updates.department !== undefined) {
      changes.push(`Department changed to ${updates.department}`)
    }
    if (updates.badge_number !== undefined) {
      changes.push(`Badge ID changed to ${updates.badge_number}`)
    }
    if (changes.length > 0) {
      return changes.join(', ')
    }
  }
  if (log.action === 'User Created') {
    return `Officer account created for ${log.metadata?.target_user_name || 'new user'} with role ${log.metadata?.target_user_role || 'Investigator'}`
  }
  if (log.action === 'Reset Access') {
    return 'Password recovery request generated'
  }
  if (log.action === 'Password Changed') {
    return 'Password updated by user'
  }
  return 'Account details updated'
}

export function AuditPage() {
  const { user } = useAuth()
  const currentRole = user?.role || 'Investigator'
  const navigate = useNavigate()

  const [logs, setLogs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  // Filter states
  const [action, setAction] = useState('All Actions')
  const [selectedRole, setSelectedRole] = useState('All Roles')
  const [userId, setUserId] = useState('All Users')
  const [dateRange, setDateRange] = useState('All Dates')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [search, setSearch] = useState('')
  const [dynamicUsers, setDynamicUsers] = useState<any[]>([])
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null)

  const actionsList = [
    'All Actions',
    'Login Successful',
    'Logout Successful',
    'Case Created',
    'Evidence Upload',
    'YOLO Scan',
    'BNS Classified',
    'Hash Verified',
    'Tamper Detected'
  ]

  const rolesList = ['All Roles', 'Admin', 'Investigator']
  const dateRangeOptions = ['All Dates', 'Today', 'Last 7 Days', 'Last 30 Days', 'Custom Range']

  // Fetch dynamic users for dropdown if Admin
  useEffect(() => {
    if (currentRole === 'Admin') {
      api.getUsers().then((res) => {
        setDynamicUsers(res.data)
      }).catch(console.error)
    }
  }, [currentRole])

  const getParams = () => {
    let apiAction = action === 'All Actions' ? undefined : action
    let apiRole = selectedRole === 'All Roles' ? undefined : selectedRole
    let apiUserId = userId === 'All Users' ? undefined : userId

    let apiStart: string | undefined = undefined
    let apiEnd: string | undefined = undefined

    const now = new Date()
    if (dateRange === 'Today') {
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      apiStart = today.toISOString()
    } else if (dateRange === 'Last 7 Days') {
      const past = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      apiStart = past.toISOString()
    } else if (dateRange === 'Last 30 Days') {
      const past = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      apiStart = past.toISOString()
    } else if (dateRange === 'Custom Range') {
      if (startDate) apiStart = new Date(startDate).toISOString()
      if (endDate) {
        const end = new Date(endDate)
        end.setHours(23, 59, 59, 999)
        apiEnd = end.toISOString()
      }
    }

    return {
      action: apiAction,
      role: apiRole,
      user_id: apiUserId,
      start_date: apiStart,
      end_date: apiEnd,
      search: search.trim() || undefined,
      page
    }
  }

  const fetchLogs = () => {
    setLoading(true)
    const params = getParams()
    api.getAuditLogs(params).then((res) => {
      setLogs(res.data)
      setTotal(res.total)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }

  // Refresh logs when any filter changes
  useEffect(() => {
    fetchLogs()
  }, [action, selectedRole, userId, dateRange, startDate, endDate, search, page])

  const handleFilterChange = (setter: any, val: any) => {
    setter(val)
    setPage(1)
  }

  return (
    <AppShell title="Audit Log">
      {/* Filters Card */}
      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', alignItems: 'end' }}>
          <div>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Action</label>
            <select value={action} onChange={(e) => handleFilterChange(setAction, e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
              {actionsList.map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>

          {currentRole === 'Admin' && (
            <>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Role</label>
                <select value={selectedRole} onChange={(e) => handleFilterChange(setSelectedRole, e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                  {rolesList.map((r) => <option key={r}>{r}</option>)}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>User</label>
                <select value={userId} onChange={(e) => handleFilterChange(setUserId, e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                  <option value="All Users">All Users</option>
                  {dynamicUsers.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </select>
              </div>
            </>
          )}

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Date Range</label>
            <select value={dateRange} onChange={(e) => handleFilterChange(setDateRange, e.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
              {dateRangeOptions.map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>

          <div style={{ gridColumn: 'span 1' }}>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Search Logs</label>
            <input
              value={search}
              onChange={(e) => handleFilterChange(setSearch, e.target.value)}
              placeholder="Search user, action, case title..."
              style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
            />
          </div>
        </div>

        {dateRange === 'Custom Range' && (
          <div style={{ display: 'flex', gap: '12px', marginTop: '12px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Start Date</label>
              <input type="date" value={startDate} onChange={(e) => handleFilterChange(setStartDate, e.target.value)} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '6px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
            </div>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>End Date</label>
              <input type="date" value={endDate} onChange={(e) => handleFilterChange(setEndDate, e.target.value)} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '6px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Immutable Audit Trail</CardTitle>
          <span style={{ fontSize: '11px', color: 'var(--green)' }}>Write-once · Append-only · Tamper-evident</span>
        </CardHeader>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Time', 'User', 'Role', 'Action', 'Status', 'Case', ''].map((h) => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text3)', fontWeight: 500, fontSize: '11px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)' }}>Loading audit logs...</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'var(--text3)' }}>No logs found matching current criteria</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <React.Fragment key={log.id}>
                    <tr
                      style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                      onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                    >
                      <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)' }}>{log.date}</td>
                      <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)' }}>{log.time}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--blue)', fontWeight: 600 }}>{log.user_name}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--text2)' }}>{log.user_role}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ fontSize: '10px', fontWeight: 500, padding: '2px 8px', borderRadius: '20px', background: 'var(--blue-bg)', color: 'var(--blue)' }}>{log.action}</span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <StatusBadge status={log.status} />
                      </td>
                      <td
                        style={{ padding: '10px 12px', color: log.case_id ? 'var(--blue)' : 'var(--text3)', fontWeight: log.case_id ? 500 : 400 }}
                        onClick={(e) => {
                          if (log.case_id) {
                            e.stopPropagation()
                            navigate(`/cases/${log.case_id}`)
                          }
                        }}
                      >
                        {log.case_id ? `${log.case_number} - ${log.case_title}` : '—'}
                      </td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                        <span style={{ color: 'var(--text3)', fontSize: '10px' }}>
                          {expandedLogId === log.id ? '▲ Hide' : '▼ Expand'}
                        </span>
                      </td>
                    </tr>

                    {expandedLogId === log.id && (() => {
                      const action = log.action || ''
                      const caseInfo = log.case_id ? `${log.case_number} - ${log.case_title}` : 'N/A'
                      
                      let detailContent = null
                      
                      if (action === 'User Activated') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Account Activation Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.metadata?.target_user_name || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Action:</span><span style={{ color: 'var(--green)', fontWeight: 600 }}>Officer Account Activated</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Performed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'User Deactivated') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Account Deactivation Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.metadata?.target_user_name || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Action:</span><span style={{ color: 'var(--red)', fontWeight: 600 }}>Officer Account Deactivated</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Performed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'User Updated') {
                        const isRoleChange = log.metadata?.old_role || log.metadata?.new_role || log.metadata?.role || log.metadata?.updates?.role;
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Officer Update Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                {isRoleChange && (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginBottom: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                                    <span style={{ color: 'var(--text)', fontWeight: 700, fontSize: '12px' }}>Role Changed</span>
                                    <span style={{ color: 'var(--text3)', fontSize: '11px' }}>Previous Role: {log.metadata?.old_role || 'Investigator'}</span>
                                    <span style={{ color: 'var(--text2)', fontSize: '11px', fontWeight: 600 }}>New Role: {log.metadata?.new_role || log.metadata?.role || log.metadata?.updates?.role || 'Admin'}</span>
                                  </div>
                                )}
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.metadata?.target_user_name || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Performed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            {log.metadata?.description && (
                              <div>
                                <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Change Summary</div>
                                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', color: 'var(--text2)', minHeight: '50px' }}>
                                  {log.metadata.description}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      } else if (action === 'Reset Access') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Credential Recovery Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '180px', color: 'var(--text3)' }}>Officer:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.metadata?.target_user_name || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '180px', color: 'var(--text3)' }}>Password Recovery:</span><span style={{ color: 'var(--amber)', fontWeight: 600 }}>Password Recovery Initiated</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '180px', color: 'var(--text3)' }}>Performed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '180px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'Evidence Upload') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Evidence Upload Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Case:</span><span style={{ color: 'var(--text)' }}>{caseInfo}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Evidence ID:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{log.metadata?.evidence_id || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Uploaded By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>SHA-256 Hash Signature</div>
                              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text)', wordBreak: 'break-all' }}>
                                {log.file_hash || 'N/A'}
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'Hash Verified' || action === 'Tamper Detected') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Cryptographic Verification</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '130px', color: 'var(--text3)' }}>Case:</span><span style={{ color: 'var(--text)' }}>{caseInfo}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '130px', color: 'var(--text3)' }}>Evidence ID:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{log.metadata?.evidence_id || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '130px', color: 'var(--text3)' }}>Verification Result:</span><span><StatusBadge status={log.status} /></span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '130px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Recomputed SHA-256 Hash</div>
                              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text)', wordBreak: 'break-all' }}>
                                {log.file_hash || 'N/A'}
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'Case Created') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>New Case Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Case Number:</span><span style={{ color: 'var(--text)', fontFamily: 'var(--mono)', fontWeight: 600 }}>{log.case_number}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Case Title:</span><span style={{ color: 'var(--text)' }}>{log.case_title}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Created By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'YOLO Scan') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>AI Forensic YOLO Analysis</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Case:</span><span style={{ color: 'var(--text)' }}>{caseInfo}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Evidence ID:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{log.metadata?.evidence_id || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Executed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Model Used:</span><span style={{ color: 'var(--text)' }}>YOLOv8 Weapon Detection</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Result Summary</div>
                              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', color: 'var(--text2)', minHeight: '50px' }}>
                                {log.metadata?.objects_found ?? 0} weapon(s) / suspicious object(s) detected in evidence file.
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'BNS Classified') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Legal BNS Classifier</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Case:</span><span style={{ color: 'var(--text)' }}>{caseInfo}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Executed By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Model Used:</span><span style={{ color: 'var(--text)' }}>BNS Legal Classifier</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Result Summary</div>
                              <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', color: 'var(--text2)', minHeight: '50px' }}>
                                Classified crime type: <strong>{log.metadata?.crime_type ?? 'Unknown'}</strong> with {log.metadata?.sections_count ?? 0} BNS sections matching the facts.
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'Login Successful' || action === 'Logout Successful') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Authentication Activity</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer Name:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Email:</span><span style={{ color: 'var(--text2)' }}>{log.metadata?.email || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Role:</span><span style={{ color: 'var(--text)' }}>{log.user_role}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Action:</span><span style={{ color: 'var(--green)', fontWeight: 500 }}>{action}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'Password Changed') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Security Settings Change</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer Name:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Email:</span><span style={{ color: 'var(--text2)' }}>{log.metadata?.email || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Action:</span><span style={{ color: 'var(--blue)', fontWeight: 500 }}>Password Changed</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else if (action === 'User Created') {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Officer Registration Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer Created:</span><span style={{ color: 'var(--text)', fontWeight: 600 }}>{log.metadata?.target_user_name || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Assigned Role:</span><span style={{ color: 'var(--text)' }}>{log.metadata?.target_user_role || 'N/A'}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Created By:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                          </div>
                        )
                      } else {
                        detailContent = (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Forensic Accountability Details</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Officer Name:</span><span style={{ color: 'var(--text)' }}>{log.user_name}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Role:</span><span style={{ color: 'var(--text)' }}>{log.user_role}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Action:</span><span style={{ color: 'var(--text)' }}>{log.action}</span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Status:</span><span><StatusBadge status={log.status} /></span></div>
                                <div style={{ display: 'flex' }}><span style={{ minWidth: '120px', color: 'var(--text3)' }}>Timestamp:</span><span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{log.created_at}</span></div>
                              </div>
                            </div>
                            {log.metadata && Object.keys(log.metadata).length > 0 && (
                              <div>
                                <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '.4px', fontSize: '10px' }}>Additional Context</div>
                                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '6px', padding: '10px 12px', color: 'var(--text2)', minHeight: '50px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                  {log.metadata?.is_active === false || log.metadata?.updates?.is_active === false ? (
                                    <span style={{ color: 'var(--red)', fontWeight: 600 }}>Officer Account Deactivated</span>
                                  ) : log.metadata?.is_active === true || log.metadata?.updates?.is_active === true ? (
                                    <span style={{ color: 'var(--green)', fontWeight: 600 }}>Officer Account Activated</span>
                                  ) : log.metadata?.must_change_password === true || log.metadata?.updates?.must_change_password === true ? (
                                    <span style={{ color: 'var(--amber)', fontWeight: 600 }}>Password Recovery Initiated</span>
                                  ) : (log.metadata?.role !== undefined || log.metadata?.updates?.role !== undefined) ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                      <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '12px', marginBottom: '2px' }}>Role Changed</div>
                                      <div style={{ fontSize: '11px', color: 'var(--text3)' }}>Previous Role: {log.metadata?.old_role || 'Investigator'}</div>
                                      <div style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600 }}>New Role: {log.metadata?.new_role || log.metadata?.role || log.metadata?.updates?.role || 'Admin'}</div>
                                    </div>
                                  ) : (
                                    log.metadata?.description || `Operation metadata: ${Object.entries(log.metadata).map(([k, v]) => `${k}: ${v}`).join(', ')}`
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      }

                      return (
                        <tr style={{ background: 'var(--bg2)' }}>
                          <td colSpan={8} style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
                            <div style={{ fontSize: '12px' }}>
                              {detailContent}
                            </div>
                          </td>
                        </tr>
                      )
                    })()}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
        {total > 20 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
            <Btn size="xs" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Prev</Btn>
            <span style={{ fontSize: '12px', color: 'var(--text3)', alignSelf: 'center' }}>Page {page}</span>
            <Btn size="xs" disabled={logs.length < 20} onClick={() => setPage((p) => p + 1)}>Next</Btn>
          </div>
        )}
      </Card>
    </AppShell>
  )
}




// ── PERSONAL SPACE ────────────────────────────────────────────────────────
import { useTheme } from '../context/ThemeContext'
import type { AuditLog } from '../types'
import { Excalidraw } from '@excalidraw/excalidraw'
import '@excalidraw/excalidraw/index.css'

export function PersonalPage() {
  const { user } = useAuth()
  const { theme } = useTheme()
  const [notes, setNotes] = useState<import('../types').PersonalNote[]>([])
  const [selectedNote, setSelectedNote] = useState<import('../types').PersonalNote | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [saving, setSaving] = useState(false)
  const [excalidrawAPI, setExcalidrawAPI] = useState<any>(null)

  useEffect(() => {
    api.getNotes().then((res) => setNotes(res.data)).catch(() => { })
  }, [])

  const openNote = (note: import('../types').PersonalNote) => {
    setSelectedNote(note); setTitle(note.title); setContent(note.content); setTags(note.tags.join(', '))
  }

  const saveNote = async () => {
    setSaving(true)
    try {
      let sketchData = ""
      if (excalidrawAPI) {
        const { exportToBlob } = await import('@excalidraw/excalidraw')
        const blob = await exportToBlob({
          elements: excalidrawAPI.getSceneElements(),
          appState: excalidrawAPI.getAppState(),
          files: excalidrawAPI.getFiles(),
          mimeType: 'image/png'
        })
        const base64 = await new Promise<string>((resolve) => {
          const reader = new FileReader()
          reader.onloadend = () => resolve(reader.result as string)
          reader.readAsDataURL(blob!)
        })
        sketchData = base64
      }

      if (selectedNote) {
        const res = await api.updateNote(selectedNote.id, { title, content, tags: tags.split(',').map((t) => t.trim()).filter(Boolean), sketch_data: sketchData })
        setNotes((prev) => prev.map((n) => n.id === selectedNote.id ? res.data : n))
      } else {
        const res = await api.createNote({ title, content, tags: tags.split(',').map((t) => t.trim()).filter(Boolean), sketch_data: sketchData })
        setNotes((prev) => [res.data, ...prev])
        setSelectedNote(res.data)
      }
    } catch { /* error */ }
    finally { setSaving(false) }
  }

  const newNote = () => { setSelectedNote(null); setTitle(''); setContent(''); setTags('') }

  return (
    <AppShell title="Personal Space">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', alignItems: 'start' }}>
        {/* LEFT COLUMN: Notes list + Editor stacked */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardHeader>
              <CardTitle>Personal Notes <span style={{ fontSize: '9px', color: 'var(--amber)', fontWeight: 400 }}>Private</span></CardTitle>
              <Btn size="xs" variant="primary" onClick={newNote}>+ New</Btn>
            </CardHeader>
            {notes.length === 0 && <div style={{ fontSize: '12px', color: 'var(--text3)', textAlign: 'center', padding: '20px' }}>No notes yet</div>}
            {notes.map((note) => (
              <div
                key={note.id}
                onClick={() => openNote(note)}
                style={{ border: '1px solid var(--border)', borderRadius: 'var(--r2)', padding: '10px 12px', marginBottom: '8px', cursor: 'pointer', transition: 'all .12s', background: selectedNote?.id === note.id ? 'var(--blue-dim)' : 'var(--bg3)' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border2)' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }}>{note.title || 'Untitled'}</div>
                <div style={{ fontSize: '11px', color: 'var(--text3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: '6px' }}>{note.content.slice(0, 60)}</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '4px' }}>
                  {note.tags.map((t) => <span key={t} style={{ fontSize: '9px', padding: '1px 6px', borderRadius: '10px', background: 'var(--bg4)', color: 'var(--text3)' }}>{t}</span>)}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text3)' }}>Edited: {format(new Date(note.updated_at), 'dd MMM yyyy HH:mm')}</div>
              </div>
            ))}
          </Card>

          {/* Note editor sits below the list */}
          <Card>
            <CardTitle>{selectedNote ? 'Edit Note' : 'New Note'} <span style={{ fontSize: '9px', color: 'var(--amber)', fontWeight: 400 }}>Not in audit log</span></CardTitle>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Note title..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', marginBottom: '10px' }} />
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} placeholder="Write your observations, rough notes, preliminary ideas..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', resize: 'vertical', marginBottom: '10px', lineHeight: 1.6 }} />
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="Tags: witness, vehicle, suspect..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', marginBottom: '12px' }} />
            <div style={{ display: 'flex', gap: '8px' }}>
              <Btn variant="primary" size="sm" loading={saving} onClick={saveNote}>Save Note</Btn>
              {selectedNote && <Btn size="sm">Add to Case</Btn>}
            </div>
          </Card>
        </div>

        {/* RIGHT COLUMN: Excalidraw canvas — full height */}
        <Card style={{ height: '100%' }}>
          <CardTitle>Sketch Canvas <span style={{ fontSize: '9px', color: 'var(--text3)', fontWeight: 400 }}>Freehand · Shapes · Arrows · Sticky notes</span></CardTitle>
          <div style={{ height: 'calc(100vh - 200px)', minHeight: '550px', border: '1px solid var(--border)', borderRadius: 'var(--r)', overflow: 'hidden' }}>
            <Excalidraw
              excalidrawAPI={(api) => setExcalidrawAPI(api)}
              theme={theme === 'dark' ? 'dark' : 'light'}
              UIOptions={{
                canvasActions: {
                  export: false,
                  saveAsImage: false,
                  loadScene: false
                }
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <Btn size="xs" full onClick={saveNote}>Save Sketch with Note</Btn>
          </div>
        </Card>
      </div>
    </AppShell>
  )
}

// ── POLE GRAPH ────────────────────────────────────────────────────────────
import { ReactFlow, Background, Controls, MiniMap, Node, Edge, NodeTypes, Handle, Position } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

const CaseNode = ({ data }: { data: any }) => (
  <div style={{ padding: '10px 14px', background: 'var(--blue-bg)', border: '2px solid var(--blue)', borderRadius: '10px', minWidth: '120px', textAlign: 'center' }}>
    <Handle type="target" position={Position.Top} style={{ background: 'var(--blue)' }} />
    <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--blue)', fontFamily: 'var(--mono)' }}>{data.label}</div>
    <div style={{ fontSize: '10px', color: 'var(--text2)', marginTop: '3px' }}>{data.subtitle}</div>
    <Handle type="source" position={Position.Bottom} style={{ background: 'var(--blue)' }} />
  </div>
)

const PersonNode = ({ data }: { data: any }) => {
  const isVictim = data.role === 'victim'
  return (
    <div style={{ padding: '8px 12px', background: isVictim ? 'var(--green-bg)' : 'var(--red-bg)', border: `2px solid ${isVictim ? 'var(--green)' : 'var(--red)'}`, borderRadius: '50%', width: '90px', height: '90px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
      <Handle type="target" position={Position.Top} />
      <div style={{ fontSize: '11px', fontWeight: 600, color: isVictim ? 'var(--green)' : 'var(--red)' }}>{data.label}</div>
      <div style={{ fontSize: '9px', color: 'var(--text3)', marginTop: '2px' }}>{data.subtitle}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const ObjectNode = ({ data }: { data: any }) => (
  <div style={{ padding: '8px 12px', background: 'var(--amber-bg)', border: '2px solid var(--amber)', borderRadius: '8px', minWidth: '100px', textAlign: 'center' }}>
    <Handle type="target" position={Position.Top} />
    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--amber)' }}>{data.label}</div>
    <div style={{ fontSize: '9px', color: 'var(--text3)', marginTop: '2px' }}>{data.subtitle}</div>
    <Handle type="source" position={Position.Bottom} />
  </div>
)

const LocationNode = ({ data }: { data: any }) => (
  <div style={{ padding: '8px 12px', background: 'var(--purple-bg)', border: '2px solid var(--purple)', borderRadius: '8px', minWidth: '100px', textAlign: 'center' }}>
    <Handle type="target" position={Position.Top} />
    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--purple)' }}>{data.label}</div>
    <div style={{ fontSize: '9px', color: 'var(--text3)', marginTop: '2px' }}>{data.subtitle}</div>
    <Handle type="source" position={Position.Bottom} />
  </div>
)

const EventNode = ({ data }: { data: any }) => (
  <div style={{ padding: '8px 12px', background: 'var(--teal-bg)', border: '2px solid var(--teal)', borderRadius: '6px', minWidth: '100px', textAlign: 'center' }}>
    <Handle type="target" position={Position.Top} />
    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--teal)' }}>{data.label}</div>
    <div style={{ fontSize: '9px', color: 'var(--text3)', marginTop: '2px' }}>{data.subtitle}</div>
    <Handle type="source" position={Position.Bottom} />
  </div>
)

const nodeTypes: NodeTypes = {
  case: CaseNode,
  person: PersonNode,
  object: ObjectNode,
  location: LocationNode,
  event: EventNode
}

export function GraphPage() {
  const { id: routeId } = useParams()
  const [selectedCaseId, setSelectedCaseId] = useState<string | undefined>(routeId)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [loading, setLoading] = useState(true)
  const [caseSearch, setCaseSearch] = useState('')
  const [caseResults, setCaseResults] = useState<import('../types').Case[]>([])

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    const res = await api.getCases({ search: q, per_page: 5 })
    setCaseResults(res.data)
  }

  useEffect(() => {
    if (!selectedCaseId) {
      setLoading(false)
      setNodes([])
      setEdges([])
      return
    }
    setLoading(true)
    api.getCaseGraph(selectedCaseId).then((res: any) => {
      setNodes(res.data.nodes)
      setEdges(res.data.edges)
    }).finally(() => setLoading(false))
  }, [selectedCaseId])

  return (
    <AppShell title="POLE Relationship Graph">
      {!routeId && (
        <div style={{ marginBottom: '16px', position: 'relative', zIndex: 10 }}>
          <input
            value={caseSearch}
            onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
            placeholder="Search case by ID, title, or victim name to view graph..."
            style={{ width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 14px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
          />
          {caseResults.length > 0 && (
            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px', overflow: 'hidden' }}>
              {caseResults.map((c) => (
                <div key={c.id} onClick={() => { setSelectedCaseId(c.id); setCaseSearch(''); setCaseResults([]) }} style={{ padding: '8px 14px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                  <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{c.case_number}</span> — {c.title}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!selectedCaseId ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text3)', border: '1px dashed var(--border)', borderRadius: 'var(--r2)' }}>
          Please select a case above to visualize its POLE relationship graph.
        </div>
      ) : (
        <div style={{ height: routeId ? '80vh' : '70vh', border: '1px solid var(--border)', borderRadius: 'var(--r2)', overflow: 'hidden' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes as any}
            fitView
            style={{ background: 'var(--bg3)' }}
          >
            <Background gap={24} />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const colors: Record<string, string> = { case: '#4d84f5', person: '#e05252', object: '#e8a030', location: '#9d75f0', event: '#38c4c4' }
                return colors[n.type || ''] || '#596070'
              }}
              style={{ background: 'var(--bg2)', border: '1px solid var(--border)' }}
            />
          </ReactFlow>
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', gap: '16px', marginTop: '12px', flexWrap: 'wrap' }}>
        {[['Case', 'var(--blue)'], ['Person', 'var(--red)'], ['Object / Evidence', 'var(--amber)'], ['Location', 'var(--purple)'], ['Event / FIR', 'var(--teal)']].map(([l, c]) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text2)' }}>
            <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: c }} />
            {l}
          </div>
        ))}
      </div>
    </AppShell>
  )
}
