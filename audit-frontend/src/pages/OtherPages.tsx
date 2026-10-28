// ── EVIDENCE UPLOAD ───────────────────────────────────────────────────────
import React, { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, Badge, HashChip, AlertBox, FutureNotice, UploadZone, InfoRow, Spinner, Tabs } from '../components/UI'
import { OcrTextViewer } from '../components/OcrTextViewer'
import { api, describeVerification } from '../services/api'
import type { Evidence, Case } from '../types'
import { format } from 'date-fns'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

const CASE_ROLE_OPTIONS = ['All Roles', 'Admin', 'Investigator', 'Unassigned']

function filterCasesByCreatorRole(cases: Case[], role: string) {
  return role === 'All Roles' ? cases : cases.filter((item) => (item.created_by_role || 'Unassigned') === role)
}

function CaseCreatorRoleFilter({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { user } = useAuth()
  if (user?.role?.toLowerCase() !== 'admin') return null
  return <div style={{ marginBottom: '8px' }}>
    <label style={{ fontSize: '10px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Creator Role</label>
    <select value={value} onChange={(event) => onChange(event.target.value)} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
      {CASE_ROLE_OPTIONS.map((role) => <option key={role}>{role}</option>)}
    </select>
  </div>
}

function CaseSearchResult({ item }: { item: Case }) {
  return <>
    <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)', fontWeight: 600 }}>{item.case_number}</span> — {item.title}
    <div style={{ marginTop: '2px', fontSize: '10px', color: 'var(--text3)' }}>{item.created_by_role || 'Unassigned'} · {item.created_by_name || 'Unknown user'}</div>
  </>
}

// ── EVIDENCE ──────────────────────────────────────────────────────────────
export function EvidencePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role?.toLowerCase() === 'admin'
  // Set when opened from a notification link: /evidence?evidence_id=…&case_id=…
  const [searchParams] = useSearchParams()
  const focusCaseId = searchParams.get('case_id')
  const focusEvidenceId = searchParams.get('evidence_id')
  const fetchSeq = useRef(0)
  const [caseSearch, setCaseSearch] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const [evidenceType, setEvidenceType] = useState('Image')
  const [language, setLanguage] = useState('auto')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [evidenceSearch, setEvidenceSearch] = useState('')
  const [evidenceTypeFilter, setEvidenceTypeFilter] = useState('All Types')
  const [evidenceStatusFilter, setEvidenceStatusFilter] = useState('All Statuses')
  const [err, setErr] = useState('')
  const [verifyResult, setVerifyResult] = useState<Record<string, string>>({})
  const fileRef = useRef<HTMLInputElement>(null)
  const visibleCaseResults = filterCasesByCreatorRole(caseResults, caseRoleFilter)
  const evidenceTypes = Array.from(new Set(evidence.map((item) => item.file_type))).sort()
  const evidenceStatuses = Array.from(new Set(evidence.map((item) => item.status))).sort()
  const normalizedEvidenceSearch = evidenceSearch.trim().toLowerCase()
  const filteredEvidence = evidence.filter((item) => {
    const matchesSearch = !normalizedEvidenceSearch || [item.file_name, item.file_type, item.status, item.sha256_hash]
      .some((value) => value?.toLowerCase().includes(normalizedEvidenceSearch))
    return matchesSearch
      && (evidenceTypeFilter === 'All Types' || item.file_type === evidenceTypeFilter)
      && (evidenceStatusFilter === 'All Statuses' || item.status === evidenceStatusFilter)
  })
  const hasEvidenceFilters = Boolean(evidenceSearch || evidenceTypeFilter !== 'All Types' || evidenceStatusFilter !== 'All Statuses')

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    try {
      const res = await api.getCases({ search: q, per_page: 5 })
      setCaseResults(res.data)
    } catch { /* ignore */ }
  }

  const fetchEvidence = async () => {
    const seq = ++fetchSeq.current
    try {
      const res = await api.getEvidence(selectedCase?.id)
      if (seq === fetchSeq.current) setEvidence(res.data)  // ignore a slower, older response
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchEvidence() }, [selectedCase])

  useEffect(() => {
    if (!focusCaseId || selectedCase?.id === focusCaseId) return
    api.getCase(focusCaseId).then((res) => setSelectedCase(res.data)).catch(() => {})
  }, [focusCaseId])

  useEffect(() => {
    if (!focusEvidenceId) return
    document.getElementById(`evidence-${focusEvidenceId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focusEvidenceId, evidence])

  const verifyHash = async (evidenceId: string) => {
    setVerifyResult((current) => ({ ...current, [evidenceId]: 'Verifying integrity on Ethereum…' }))
    try {
      const res = await api.verifyHash(evidenceId)
      setVerifyResult((current) => ({ ...current, [evidenceId]: describeVerification(res.data) }))
    } catch (error: any) {
      setVerifyResult((current) => ({ ...current, [evidenceId]: describeVerification(null, error) }))
    }
    await fetchEvidence()  // status may have changed (Tampered / Missing / Unregistered)
  }

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
              <CaseCreatorRoleFilter value={caseRoleFilter} onChange={setCaseRoleFilter} />
              <div style={{ position: 'relative' }}>
                <input
                  value={caseSearch}
                  onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
                  placeholder="Case ID, title, victim name..."
                  style={{ width: '100%', paddingLeft: '10px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                />
              </div>
              {visibleCaseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px', overflow: 'hidden' }}>
                  {visibleCaseResults.map((c) => (
                    <div key={c.id} onClick={() => { setSelectedCase(c); setCaseSearch(''); setCaseResults([]) }}
                      style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                      <CaseSearchResult item={c} />
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
        <Card style={{ display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 108px)', minHeight: 0 }}>
          <CardHeader>
            <CardTitle>Evidence Files{selectedCase ? ` · ${selectedCase.case_number}` : ''}</CardTitle>
            <span style={{ fontSize: '11px', color: 'var(--text3)' }}>{filteredEvidence.length}{hasEvidenceFilters ? ` of ${evidence.length}` : ''} files</span>
          </CardHeader>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 120px 120px', gap: '8px', marginBottom: '12px' }}>
            <input
              value={evidenceSearch}
              onChange={(event) => setEvidenceSearch(event.target.value)}
              placeholder="Search file or hash..."
              aria-label="Search evidence files"
              style={{ minWidth: 0, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 9px', fontSize: '12px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
            />
            <select value={evidenceTypeFilter} onChange={(event) => setEvidenceTypeFilter(event.target.value)} aria-label="Filter by evidence type" style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 8px', fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
              <option>All Types</option>
              {evidenceTypes.map((type) => <option key={type}>{type}</option>)}
            </select>
            <select value={evidenceStatusFilter} onChange={(event) => setEvidenceStatusFilter(event.target.value)} aria-label="Filter by verification status" style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 8px', fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
              <option>All Statuses</option>
              {evidenceStatuses.map((status) => <option key={status}>{status}</option>)}
            </select>
          </div>
          {hasEvidenceFilters && <div style={{ marginTop: '-5px', marginBottom: '10px', textAlign: 'right' }}><span onClick={() => { setEvidenceSearch(''); setEvidenceTypeFilter('All Types'); setEvidenceStatusFilter('All Statuses') }} style={{ color: 'var(--blue)', cursor: 'pointer', fontSize: '11px' }}>Clear filters</span></div>}
          {evidence.length === 0 && <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)', fontSize: '12px' }}>No evidence uploaded yet</div>}
          {evidence.length > 0 && filteredEvidence.length === 0 && <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)', fontSize: '12px' }}>No evidence matches these filters.</div>}
          <div style={{ overflowY: 'auto', flex: 1, minHeight: 0, paddingRight: '4px' }}>
          {filteredEvidence.map((f) => (
            <div key={f.id} id={`evidence-${f.id}`} style={{ border: '1px solid var(--border)', borderLeft: `3px solid ${f.status === 'Tampered' || f.status === 'Missing' ? 'var(--red)' : f.status === 'Unregistered' ? 'var(--amber)' : 'var(--green)'}`, borderRadius: 'var(--r)', padding: '10px 12px', background: 'var(--bg3)', marginBottom: '8px', boxShadow: f.id === focusEvidenceId ? '0 0 0 2px var(--blue)' : undefined }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.file_name}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>{f.file_type} · {(f.file_size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
                <Badge label={f.status} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                {isAdmin && <HashChip hash={f.sha256_hash} />}
                <div style={{ flex: 1 }} />
                {f.file_type === 'Audio' && (
                  <Btn size="xs" onClick={() => navigate(f.case_id ? `/audio?case_id=${f.case_id}&evidence_id=${f.id}` : `/audio?evidence_id=${f.id}`)}>Analyze Audio</Btn>
                )}
                {f.file_type === 'Video' && f.case_id && (
                  <Btn size="xs" onClick={() => navigate(`/photo3d?case_id=${f.case_id}&evidence_id=${f.id}`)}>3D Reconstruct</Btn>
                )}
                {f.file_type === 'Image' && f.case_id && (
                  <Btn size="xs" onClick={() => navigate(`/detection?case_id=${f.case_id}&evidence_id=${f.id}`)}>Object Detection</Btn>
                )}
                {f.file_type === 'Document' && (
                  <Btn size="xs" onClick={() => navigate(`/ocr?case_id=${encodeURIComponent(f.case_id)}`)}>OCR Extract</Btn>
                )}
                {f.file_type === 'FIR' && (
                  <Btn size="xs" onClick={() => navigate(`/bns?case_id=${encodeURIComponent(f.case_id)}`)}>BNS Classification</Btn>
                )}
                <Btn size="xs" onClick={() => verifyHash(f.id)}>Verify Hash</Btn>
              </div>
              {f.status === 'Tampered' && <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--red)', padding: '4px 8px', background: 'var(--red-bg)', borderRadius: '4px' }}>Hash mismatch detected</div>}
              {f.status === 'Missing' && <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--red)', padding: '4px 8px', background: 'var(--red-bg)', borderRadius: '4px' }}>Evidence file is missing from storage</div>}
              {f.status === 'Unregistered' && <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--amber)', padding: '4px 8px', background: 'var(--amber-bg)', borderRadius: '4px' }}>Not registered on the blockchain — integrity cannot be verified</div>}
              {verifyResult[f.id] && <div style={{ marginTop: '6px', fontSize: '11px', color: verifyResult[f.id].startsWith('✓') && !verifyResult[f.id].includes('⚠') ? 'var(--green)' : verifyResult[f.id].startsWith('Verifying') ? 'var(--text2)' : 'var(--red)' }}>{verifyResult[f.id]}</div>}
            </div>
          ))}
          </div>
        </Card>
      </div>
    </AppShell>
  )
}

// ── OBJECT DETECTION ──────────────────────────────────────────────────────
export function DetectionPage() {
  const [searchParams] = useSearchParams()
  const requestedCaseId = searchParams.get('case_id')
  const requestedEvidenceId = searchParams.get('evidence_id')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseSearch, setCaseSearch] = useState('')
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const [evidenceFiles, setEvidenceFiles] = useState<Evidence[]>([])
  const [selectedEvidence, setSelectedEvidence] = useState<string>('')
  const [imgSource, setImgSource] = useState<'upload' | 'evidence'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<import('../types').DetectionResult | null>(null)
  const [err, setErr] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const visibleCaseResults = filterCasesByCreatorRole(caseResults, caseRoleFilter)

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

  // An evidence-row action can open detection with its case and image already selected.
  useEffect(() => {
    if (!requestedCaseId || selectedCase?.id === requestedCaseId) return
    let active = true
    Promise.all([api.getCase(requestedCaseId), api.getEvidence(requestedCaseId)])
      .then(([caseResult, evidenceResult]) => {
        if (!active) return
        const detectionEvidence = evidenceResult.data.filter((item) => item.file_type === 'Image')
        setSelectedCase(caseResult.data)
        setEvidenceFiles(detectionEvidence)
        if (requestedEvidenceId && detectionEvidence.some((item) => item.id === requestedEvidenceId)) {
          setSelectedEvidence(requestedEvidenceId)
          setImgSource('evidence')
        }
      })
      .catch(() => {
        if (active) setErr('Unable to load the selected evidence for object detection.')
      })
    return () => { active = false }
  }, [requestedCaseId, requestedEvidenceId, selectedCase?.id])

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
      // The annotated image is stored in R2 and requires the current JWT to
      // retrieve it. Turn the authenticated response into a temporary browser
      // URL for preview; the permanent R2 key remains in PostgreSQL.
      let storedPreviewUrl = res.data.image_url
      if (res.data.id) {
        const annotatedImage = await api.downloadDetectionOutput(res.data.id)
        storedPreviewUrl = URL.createObjectURL(annotatedImage)
      }
      setResult({ ...res.data, image_url: storedPreviewUrl })
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
              <CaseCreatorRoleFilter value={caseRoleFilter} onChange={setCaseRoleFilter} />
              <input value={caseSearch} onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }} placeholder="Search case..." style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
              {visibleCaseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px' }}>
                  {visibleCaseResults.map((c) => <div key={c.id} onClick={() => selectCase(c)} style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}><CaseSearchResult item={c} /></div>)}
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
                    <img
                      src={result.image_url}
                      alt="Annotated Detection Output"
                      style={{ display: 'block', maxWidth: '100%', maxHeight: '550px', objectFit: 'contain' }}
                      onError={async (e) => {
                        try {
                          if (file) {
                            (e.target as HTMLImageElement).src = URL.createObjectURL(file)
                            return
                          }
                          const evId = imgSource === 'evidence' ? selectedEvidence : ''
                          if (evId) {
                            const dl = await api.downloadEvidence(evId)
                            if (dl && dl.blob) {
                              ;(e.target as HTMLImageElement).src = URL.createObjectURL(dl.blob)
                            }
                          }
                        } catch (err) {
                          console.warn("Fallback evidence image fetch failed:", err)
                        }
                      }}
                    />
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
  const [searchParams] = useSearchParams()
  const requestedCaseId = searchParams.get('case_id')
  const [caseSearch, setCaseSearch] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const [firText, setFirText] = useState('')
  const [threshold, setThreshold] = useState<number>(0.35)
  const [language, setLanguage] = useState('auto')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<import('../types').BNSResult | null>(null)
  const [expandedSection, setExpandedSection] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const [accepted, setAccepted] = useState(false)
  const [err, setErr] = useState('')
  const visibleCaseResults = filterCasesByCreatorRole(caseResults, caseRoleFilter)

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    const res = await api.getCases({ search: q, per_page: 5 })
    setCaseResults(res.data)
  }

  const selectCase = (c: Case) => {
    setSelectedCase(c); setCaseSearch(''); setCaseResults([])
    setFirText(c.fir_description || '')
  }

  // A case-page action opens BNS with its case and FIR narrative already linked.
  useEffect(() => {
    if (!requestedCaseId || selectedCase?.id === requestedCaseId) return
    let active = true
    api.getCase(requestedCaseId)
      .then((res) => {
        if (!active) return
        const requestedCase = res.data
        setSelectedCase(requestedCase)
        setCaseSearch('')
        setCaseResults([])
        setFirText(requestedCase.fir_description || '')
      })
      .catch(() => {
        if (active) setErr('Unable to load the selected case for BNS classification.')
      })
    return () => { active = false }
  }, [requestedCaseId, selectedCase?.id])

  const classify = async () => {
    if (!selectedCase) { setErr('Select a case first.'); return }
    if (!firText.trim()) { setErr('FIR description is required.'); return }
    setRunning(true); setErr(''); setResult(null); setAccepted(false); setExpandedSection(null)
    try {
      const res = await api.predictBNS(firText, threshold)
      const data = res.data || res
      setResult(data)
      if (data.bns && data.bns.length > 0) {
        setExpandedSection(data.bns[0].section_id)
      }
    } catch {
      setErr('Classification failed. The BNS prediction service is unavailable. Please ensure the BNS server is running (uvicorn app.main:app --port 8001 in bns-backend/).')
    }
    finally { setRunning(false) }
  }

  const accept = async () => {
    if (!result || !selectedCase) return
    try {
      await api.storeBNS(selectedCase.id, result, firText)
      setAccepted(true)
    } catch {
      setErr('Failed to store BNS sections in database.')
    }
  }

  // Filter sections by confidence threshold and sort from highest to lowest
  const rawSections = (result?.bns || result?.sections || [])
  const thresholdPassedSections = rawSections
    .filter((s: any) => {
      const sc = s.confidence !== undefined ? s.confidence : (s.score || 0)
      return sc >= threshold
    })
    .sort((a: any, b: any) => {
      const scA = a.confidence !== undefined ? a.confidence : (a.score || 0)
      const scB = b.confidence !== undefined ? b.confidence : (b.score || 0)
      return scB - scA
    })

  // Dynamic available categories from current threshold predictions
  const availableCategories: string[] = Array.from(
    new Set(thresholdPassedSections.map((s: any) => s.category).filter(Boolean))
  )

  // Displayed sections based on category selection
  const displayedSections = thresholdPassedSections.filter((s: any) => {
    if (filterCategory === 'all') return true
    return s.category === filterCategory
  })

  return (
    <AppShell title="BNS Multi-Label Legal Classification & Explainability">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3.8fr) minmax(0, 6.2fr)', gap: '16px', alignItems: 'start', width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
        {/* Left Column: FIR Input & Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0, width: '100%' }}>
          <Card>
            <CardTitle>FIR Narrative Input</CardTitle>
            {err && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{err}</AlertBox></div>}

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Case Reference</label>
              <CaseCreatorRoleFilter value={caseRoleFilter} onChange={setCaseRoleFilter} />
              <input
                value={caseSearch}
                onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
                placeholder="Search case number or title to auto-fill FIR..."
                style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
              />
              {visibleCaseResults.length > 0 && !selectedCase && (
                <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px', maxHeight: '180px', overflowY: 'auto' }}>
                  {visibleCaseResults.map((c) => (
                    <div
                      key={c.id}
                      onClick={() => selectCase(c)}
                      style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                    >
                      <CaseSearchResult item={c} />
                    </div>
                  ))}
                </div>
              )}
              {selectedCase && (
                <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <span>Linked:</span>
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{selectedCase.case_number}</span>
                  <span style={{ color: 'var(--text2)' }}>— {selectedCase.title}</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px' }}>FIR Comprehensive Narrative</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '3px 8px', fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}>
                {[['auto', 'Auto Detect'], ['en', 'English'], ['hi', 'Hindi'], ['kn', 'Kannada']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>

            <textarea
              value={firText}
              onChange={(e) => setFirText(e.target.value)}
              rows={16}
              placeholder="Paste full First Information Report (FIR) narrative. The multi-label engine will analyze all sentences to identify every applicable BNS section..."
              style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', resize: 'vertical', lineHeight: 1.6, marginBottom: '14px' }}
            />

            {/* Configurable Threshold Slider */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', marginBottom: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '.3px' }}>Confidence Cutoff Threshold</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 700, color: 'var(--purple)' }}>{Math.round(threshold * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.20"
                max="0.80"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--purple)', cursor: 'pointer', marginBottom: '8px' }}
              />
              <div style={{ display: 'flex', gap: '6px', justifyContent: 'space-between' }}>
                {[0.30, 0.40, 0.50, 0.60].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setThreshold(t)}
                    style={{
                      padding: '3px 8px',
                      fontSize: '10px',
                      fontFamily: 'var(--mono)',
                      background: threshold === t ? 'var(--purple)' : 'var(--bg3)',
                      color: threshold === t ? '#fff' : 'var(--text3)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r)',
                      cursor: 'pointer'
                    }}
                  >
                    {Math.round(t * 100)}%
                  </button>
                ))}
              </div>
            </div>

            <Btn variant="primary" full loading={running} onClick={classify}>
              {running ? 'Analyzing Multi-Offence Narrative...' : 'Run Multi-Label BNS Classification'}
            </Btn>
          </Card>
        </div>

        {/* Right Column: Multi-Label Predictions & Explainability Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0, width: '100%' }}>
          <Card>
            <CardHeader>
              <CardTitle>BNS Legal Classification Results</CardTitle>
              <span style={{ fontSize: '11px', color: result ? 'var(--green)' : 'var(--text3)', fontWeight: 500 }}>
                {result ? `${displayedSections.length} ${displayedSections.length === 1 ? 'Applicable Section Identified' : 'Applicable Sections Identified'}` : 'Awaiting FIR Analysis'}
              </span>
            </CardHeader>

            {!result && !running && (
              <div style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--text3)', fontSize: '13px', lineHeight: 1.6 }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: 'var(--bg3)',
                  border: '1px solid var(--border)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text3)',
                  marginBottom: '12px'
                }}>
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3v18"/>
                    <path d="M6 8l-4 6h8l-4-6z"/>
                    <path d="M18 8l-4 6h8l-4-6z"/>
                    <path d="M3 8h18"/>
                  </svg>
                </div>
                <br />
                Enter FIR facts and execute classification.<br />
                The system will automatically detect every applicable BNS section with confidence scores, triggering evidentiary sentences, and legal explanations.
              </div>
            )}

            {running && (
              <div style={{ padding: '30px 20px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginBottom: '14px', textAlign: 'center' }}>
                  Processing Multi-Scale Legal Analysis
                </div>
                {[
                  'Discourse sentence segmentation & paragraph parsing',
                  'Dense RAG statutory matching (sentence-transformers / all-MiniLM-L6-v2)',
                  'Actus Reus & Mens Rea legal element verification',
                  'Independent multi-label calibrated probability scoring',
                  'Explainable AI (XAI) synthesis & evidentiary citation extraction'
                ].map((s, i) => (
                  <div key={i} style={{ marginBottom: '12px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text2)', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{s}</span>
                      <span style={{ fontSize: '10px', color: 'var(--purple)', fontFamily: 'var(--mono)' }}>active</span>
                    </div>
                    <div style={{ background: 'var(--bg4)', borderRadius: '3px', height: '6px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', background: 'linear-gradient(90deg, var(--blue), var(--purple))', width: `${95 - i * 15}%`, transition: 'width .4s' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {result && (
              <div style={{ width: '100%', minWidth: 0, boxSizing: 'border-box' }}>
                {/* Header Summary Banner */}
                <div style={{ padding: '12px 14px', background: 'var(--purple-bg)', border: '1px solid var(--purple)', borderRadius: 'var(--r)', marginBottom: '16px', boxSizing: 'border-box' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', flexWrap: 'wrap', gap: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--purple)', textTransform: 'uppercase', letterSpacing: '.4px' }}>
                      Primary Incident Classification
                    </span>
                    <span style={{ fontSize: '11px', fontFamily: 'var(--mono)', color: 'var(--purple)', fontWeight: 700 }}>
                      {thresholdPassedSections.length} {thresholdPassedSections.length === 1 ? 'Section Applicable' : 'Sections Applicable'}
                    </span>
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text)', marginBottom: '6px', wordBreak: 'break-word' }}>
                    {result.crime_type}
                  </div>
                  {availableCategories && availableCategories.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px', alignItems: 'center' }}>
                      {availableCategories.slice(0, 4).map((cat: string, idx: number) => (
                        <span key={idx} style={{ fontSize: '10px', background: 'var(--bg2)', color: 'var(--text2)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 6px', wordBreak: 'break-word' }}>
                          {cat}
                        </span>
                      ))}
                      {availableCategories.length > 4 && (
                        <span style={{ fontSize: '10px', color: 'var(--purple)', fontFamily: 'var(--mono)', fontWeight: 600, padding: '2px 4px' }}>
                          +{availableCategories.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Filter / Category Selector Dropdown */}
                {availableCategories && availableCategories.length > 1 && (
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '8px 12px', boxSizing: 'border-box', width: '100%' }}>
                    <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px', whiteSpace: 'nowrap' }}>
                      Filter by Category:
                    </label>
                    <select
                      value={filterCategory}
                      onChange={(e) => setFilterCategory(e.target.value)}
                      style={{
                        flex: 1,
                        background: 'var(--bg3)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--r)',
                        padding: '6px 10px',
                        fontSize: '12px',
                        color: 'var(--text)',
                        fontFamily: 'var(--font)',
                        outline: 'none',
                        cursor: 'pointer',
                        minWidth: 0
                      }}
                    >
                      <option value="all">All Categories ({thresholdPassedSections.length} Sections)</option>
                      {availableCategories.map((cat: string, i: number) => {
                        const count = thresholdPassedSections.filter((s: any) => s.category === cat).length
                        return (
                          <option key={i} value={cat}>{cat} ({count})</option>
                        )
                      })}
                    </select>
                  </div>
                )}

                {/* Ranked Section Predictions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                  {displayedSections.length === 0 && (
                    <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>
                      No sections meet the {Math.round(threshold * 100)}% threshold. Lower the threshold slider to view secondary predictions.
                    </div>
                  )}

                  {displayedSections.map((s: any, idx: number) => {
                    const isExpanded = expandedSection === s.section_id
                    const confVal = s.confidence !== undefined ? s.confidence : (s.score || 0)
                    const confPct = s.confidence_percent || `${Math.round(confVal * 100)}%`

                    // Color code confidence badges
                    let badgeColor = 'var(--text3)'
                    let badgeBg = 'var(--bg3)'
                    let progressColor = 'var(--purple)'
                    if (confVal >= 0.85) {
                      badgeColor = '#10b981' // Green
                      badgeBg = 'rgba(16, 185, 129, 0.12)'
                      progressColor = '#10b981'
                    } else if (confVal >= 0.70) {
                      badgeColor = '#3b82f6' // Blue
                      badgeBg = 'rgba(59, 130, 246, 0.12)'
                      progressColor = '#3b82f6'
                    } else if (confVal >= 0.50) {
                      badgeColor = '#f59e0b' // Amber
                      badgeBg = 'rgba(245, 158, 11, 0.12)'
                      progressColor = '#f59e0b'
                    }

                    return (
                      <div
                        key={s.section_id}
                        style={{
                          border: isExpanded ? '1px solid var(--purple)' : '1px solid var(--border)',
                          borderRadius: 'var(--r)',
                          background: 'var(--bg2)',
                          overflow: 'hidden',
                          transition: 'all .2s ease',
                          width: '100%',
                          boxSizing: 'border-box'
                        }}
                      >
                        {/* Section Header Card Bar */}
                        <div
                          onClick={() => setExpandedSection(isExpanded ? null : s.section_id)}
                          style={{
                            padding: '10px 14px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                            background: isExpanded ? 'var(--bg3)' : 'transparent',
                            boxSizing: 'border-box',
                            width: '100%'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0, overflow: 'hidden' }}>
                            <span style={{
                              fontFamily: 'var(--mono)',
                              fontSize: '12px',
                              fontWeight: 700,
                              color: 'var(--purple)',
                              minWidth: '65px',
                              background: 'var(--purple-bg)',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              textAlign: 'center',
                              flexShrink: 0
                            }}>
                              BNS {s.section_id}
                            </span>
                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                                {s.title || s.name}
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--text3)', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                                {s.category || 'Statutory Offence'}
                              </div>
                            </div>
                          </div>

                          {/* Confidence Gauge Badge */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                            <div style={{ width: '50px', height: '6px', background: 'var(--bg4)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ width: `${Math.min(100, Math.round(confVal * 100))}%`, height: '100%', background: progressColor }} />
                            </div>
                            <span style={{
                              fontFamily: 'var(--mono)',
                              fontSize: '12px',
                              fontWeight: 700,
                              color: badgeColor,
                              background: badgeBg,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              minWidth: '40px',
                              textAlign: 'right'
                            }}>
                              {confPct}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--text3)' }}>
                              {isExpanded ? '▲' : '▼'}
                            </span>
                          </div>
                        </div>

                        {/* Expandable Accordion Body */}
                        {isExpanded && (
                          <div style={{ padding: '14px', borderTop: '1px solid var(--border)', background: 'var(--bg1)', boxSizing: 'border-box', width: '100%' }}>
                            {/* AI Explanation / Rationale Box */}
                            {s.explanation && (
                              <div style={{ marginBottom: '12px', padding: '10px 12px', background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: 'var(--r)', wordBreak: 'break-word' }}>
                                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--blue)', textTransform: 'uppercase', letterSpacing: '.4px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M12 2a6 6 0 0 0-6 6c0 2.2 1.2 3.8 2 5 .8 1.2 1 2 1 3h6c0-1 .2-1.8 1-3 .8-1.2 2-2.8 2-5a6 6 0 0 0-6-6z" />
                                    <path d="M9 18h6" />
                                    <path d="M10 21h4" />
                                  </svg>
                                  AI Legal Explanation &amp; Rationale
                                </div>
                                <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: 1.5, wordBreak: 'break-word' }}>
                                  {s.explanation}
                                </div>
                              </div>
                            )}

                            {/* Triggering Sentences from FIR */}
                            {s.trigger_sentences && s.trigger_sentences.length > 0 && (
                              <div style={{ marginBottom: '12px' }}>
                                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px', marginBottom: '4px' }}>
                                  Evidentiary Trigger Citations from FIR
                                </div>
                                {s.trigger_sentences.map((sent: string, sIdx: number) => (
                                  <div key={sIdx} style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text2)', background: 'var(--bg3)', borderLeft: '3px solid var(--purple)', padding: '6px 10px', borderRadius: '0 4px 4px 0', marginBottom: '4px', wordBreak: 'break-word' }}>
                                    "{sent}"
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Statutory Definition / Meaning */}
                            <div style={{ marginBottom: '12px' }}>
                              <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.4px', marginBottom: '4px' }}>
                                Statutory Meaning &amp; Definition
                              </div>
                              <div style={{ fontSize: '12px', color: 'var(--text2)', lineHeight: 1.5, wordBreak: 'break-word' }}>
                                {s.description || s.meaning}
                              </div>
                            </div>

                            {/* Metadata Pills: Severity, Cognizable, Bailable, Punishment */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', paddingTop: '8px', borderTop: '1px dashed var(--border)' }}>
                              {s.severity && (
                                <span style={{ fontSize: '11px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 8px', color: s.severity === 'high' ? 'var(--red)' : 'var(--text2)' }}>
                                  Severity: <strong style={{ textTransform: 'capitalize' }}>{s.severity}</strong>
                                </span>
                              )}
                              {s.cognizable !== undefined && (
                                <span style={{ fontSize: '11px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 8px', color: 'var(--text2)' }}>
                                  {typeof s.cognizable === 'boolean' ? (s.cognizable ? 'Cognizable' : 'Non-Cognizable') : String(s.cognizable)}
                                </span>
                              )}
                              {s.bailable !== undefined && (
                                <span style={{ fontSize: '11px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 8px', color: 'var(--text2)' }}>
                                  {typeof s.bailable === 'boolean' ? (s.bailable ? 'Bailable' : 'Non-Bailable') : String(s.bailable)}
                                </span>
                              )}
                              {s.punishment && (
                                <span style={{ fontSize: '11px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 8px', color: 'var(--text2)', wordBreak: 'break-word' }}>
                                  Punishment: <strong>{typeof s.punishment === 'string' ? s.punishment : JSON.stringify(s.punishment)}</strong>
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Action Save Button */}
                <div style={{ marginTop: '20px' }}>
                  {!accepted ? (
                    <Btn variant="primary" full onClick={accept}>
                      Accept Multi-Label Predictions &amp; Save to Case Records
                    </Btn>
                  ) : (
                    <AlertBox type="success">
                      All {displayedSections.length} BNS sections securely recorded to database and audit log generated
                    </AlertBox>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  )
}

// ── OCR ───────────────────────────────────────────────────────────────────
export function OCRPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedCaseId = searchParams.get('case_id')
  const [subTab, setSubTab] = useState(0)

  // Extract Tab States
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('auto')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [ocrError, setOcrError] = useState('')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [ocrRunLang, setOcrRunLang] = useState('auto')
  const fileRef = useRef<HTMLInputElement>(null)

  // Case Select States
  const [caseSearch, setCaseSearch] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [caseResults, setCaseResults] = useState<Case[]>([])
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const visibleCaseResults = filterCasesByCreatorRole(caseResults, caseRoleFilter)


  // Search Tab States
  const [searchQuery, setSearchQuery] = useState('')
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchResults, setSearchResults] = useState<any[]>([])

  useEffect(() => {
    let active = true
    if (requestedCaseId) {
      api.getCase(requestedCaseId).then((res) => {
        if (active) setSelectedCase(res.data)
      }).catch(() => { })
    } else {
      api.getCases({ per_page: 1 }).then((res) => {
        if (active && res.data?.[0]) setSelectedCase(res.data[0])
      }).catch(() => { })
    }

    return () => { active = false }
  }, [requestedCaseId])

  useEffect(() => {
    if (!file || !file.type.startsWith('image/')) {
      setPreviewUrl(null)
      return
    }
    const objectUrl = URL.createObjectURL(file)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])

  const searchCases = async (q: string) => {
    if (q.length < 2) { setCaseResults([]); return }
    const res = await api.getCases({ search: q, per_page: 5 })
    setCaseResults(res.data)
  }

  const runExtract = async () => {
    if (!selectedCase) { setOcrError('Please search and select a case reference first.'); return }
    if (!file) { setOcrError('Please upload a scanned document or image.'); return }
    setRunning(true)
    setResult(null)
    setOcrError('')
    try {
      // 1. Upload file as case evidence first
      let evidenceId: string
      try {
        const uploadRes = await api.uploadEvidence(selectedCase.id, file, {
          evidence_type: file.type.includes('pdf') ? 'Document' : 'Image',
          description: 'Uploaded for OCR text extraction.'
        })
        evidenceId = uploadRes.data.id
      } catch (uploadErr: any) {
        // 409 = duplicate file — the backend tells us the existing evidence ID.
        // Parse it out and re-use it so OCR still runs on the same file.
        if (uploadErr.response?.status === 409) {
          const respData = uploadErr.response?.data
          const dupId = respData?.evidence_id
          const detail: string = typeof respData === 'string' ? respData : (respData?.detail || '')
          const match = detail.match(/evidence ID:\s*([\w-]+)/i)
          if (dupId) {
            evidenceId = dupId
          } else if (match) {
            evidenceId = match[1]
          } else {
            // Cannot extract existing ID — surface the conflict message
            setOcrError('This file was already uploaded. Please select it from the evidence list or upload a different file.')
            return
          }
        } else {
          throw uploadErr
        }
      }

      // 2. Execute OCR processing on evidence ID
      const res = await api.runOCR(evidenceId, language)
      // Keep compatibility with older OCR responses while immediately
      // rendering the text returned by the PaddleOCR endpoint.
      const ocr = res.data as any
      setResult({ ...ocr, text: ocr.text ?? ocr.extracted_text ?? '' })
      setOcrRunLang(language)
    } catch (err: any) {
      console.error(err)
      const detail = err.response?.data?.detail || 'OCR extraction failed. Check backend configuration.'
      setOcrError(detail)
    } finally {
      setRunning(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearchLoading(true)
    try {
      const res = await api.searchOCR(searchQuery)
      setSearchResults(res.data || [])
    } catch {
      alert('Search failed.')
    } finally {
      setSearchLoading(false)
    }
  }

  return (
    <AppShell title="OCR Scanned Evidence Manager">
      <div style={{ marginBottom: '16px' }}>
        <Tabs tabs={['Scanned Document OCR', 'Search Scanned Evidence']} activeIndex={subTab} onChange={setSubTab} />
      </div>

      {subTab === 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardTitle>Case Link & Configuration</CardTitle>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Case Reference</label>
                <CaseCreatorRoleFilter value={caseRoleFilter} onChange={setCaseRoleFilter} />
                <input
                  value={caseSearch}
                  onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
                  placeholder="Search case by title or number..."
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
                />
                {visibleCaseResults.length > 0 && !selectedCase && (
                  <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px' }}>
                    {visibleCaseResults.map((c) => (
                      <div
                        key={c.id}
                        onClick={() => { setSelectedCase(c); setCaseSearch(''); setCaseResults([]) }}
                        style={{ padding: '8px 10px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg3)' }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                      >
                        <CaseSearchResult item={c} />
                      </div>
                    ))}
                  </div>
                )}
                {selectedCase && (
                  <div style={{ marginTop: '6px', padding: '6px 10px', background: 'var(--blue-dim)', border: '1px solid var(--blue)', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--blue)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{selectedCase.case_number} — {selectedCase.title}</span>
                    <span style={{ cursor: 'pointer', fontSize: '11px' }} onClick={() => setSelectedCase(null)}>Clear</span>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>OCR Language Mode</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
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

              <input ref={fileRef} type="file" accept="image/*,.pdf" style={{ display: 'none' }} onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); setOcrError('') }} />
              <UploadZone
                title={file ? file.name : 'Upload scanned FIR or evidence document'}
                sub="PDF · PNG · JPG · JPEG · Max 50MB"
                onClick={() => fileRef.current?.click()}
                onDropFile={(f) => { setFile(f); setResult(null); setOcrError('') }}
              />

              {previewUrl && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', marginBottom: '6px' }}>UPLOADED IMAGE PREVIEW</div>
                  <img src={previewUrl} alt="Uploaded evidence preview" style={{ width: '100%', maxHeight: '190px', objectFit: 'contain', border: '1px solid var(--border)', borderRadius: 'var(--r)', background: 'var(--bg3)' }} />
                </div>
              )}
              {ocrError && <div style={{ marginTop: '12px' }}><AlertBox type="error">{ocrError}</AlertBox></div>}

              <Btn variant="primary" full loading={running} onClick={runExtract}>
                Process Scanned Document
              </Btn>
            </Card>
          </div>

          <Card style={{ minHeight: '400px' }}>
            <CardTitle>Extracted Document Content</CardTitle>

            {!result && !running && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', color: 'var(--text3)', fontSize: '12px' }}>
                Extracted page content will be displayed here after processing.
              </div>
            )}

            {running && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', gap: '12px' }}>
                <Spinner size={24} />
                <div style={{ fontSize: '11px', color: 'var(--text3)' }}>Detecting page layout, languages and text...</div>
              </div>
            )}

            {result && !running && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '4px', padding: '6px 12px', fontSize: '11px', color: 'var(--text3)', marginBottom: '12px' }}>
                  <span>Language: <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)' }}>{result.language}</span></span>
                  <span>Confidence: <span style={{ fontWeight: 600, color: 'var(--green)' }}>{Math.round(result.confidence * 100)}%</span></span>
                </div>
                <OcrTextViewer
                  result={result}
                  downloadName={`ocr_extract_${selectedCase?.case_number || 'export'}`}
                  onTranslate={async (target) => {
                    const res = await api.runOCR(result.evidence_id, ocrRunLang, { translate: true, target_language: target })
                    const ocr = res.data as any
                    setResult({ ...ocr, text: ocr.text ?? ocr.extracted_text ?? '' })
                  }}
                />
              </div>
            )}
          </Card>
        </div>
      )}

      {subTab === 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card>
            <CardTitle>Search OCR Content across Scanned Evidence</CardTitle>
            <div style={{ display: 'flex', gap: '12px' }}>
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
                placeholder="Enter keywords to search in OCR extracted records (e.g. 'weapon', 'fir', 'theft')..."
                style={{ flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
              />
              <Btn variant="primary" loading={searchLoading} onClick={handleSearch}>
                Search Records
              </Btn>
            </div>
          </Card>

          {searchResults.length === 0 && !searchLoading && searchQuery && (
            <Card style={{ textAlign: 'center', padding: '40px', color: 'var(--text3)' }}>
              No matching OCR evidence records found for keyword "{searchQuery}".
            </Card>
          )}

          {searchLoading && (
            <Card style={{ textAlign: 'center', padding: '40px' }}>
              <div style={{ margin: '0 auto 12px', display: 'flex', justifyContent: 'center' }}><Spinner size={24} /></div>
              <div style={{ fontSize: '12px', color: 'var(--text3)' }}>Searching immutable OCR database...</div>
            </Card>
          )}

          {searchResults.map((ev: any) => (
            <Card key={ev.id} style={{ borderLeft: '4px solid var(--blue)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                    {ev.file_name} <span style={{ fontSize: '11px', color: 'var(--text3)', fontWeight: 400 }}>({ev.file_type})</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '2px' }}>
                    Case: <span
                      onClick={() => navigate(`/cases/${ev.case_id}`)}
                      style={{ color: 'var(--blue)', cursor: 'pointer', fontWeight: 500 }}
                    >
                      {ev.case_title || 'View Case Detail'}
                    </span> · uploaded by {ev.uploaded_by_name || 'Officer'}
                  </div>
                </div>
                <Btn size="xs" onClick={() => navigate(`/cases/${ev.case_id}`)}>View Case</Btn>
              </div>

              {ev.ocr_matches && ev.ocr_matches.map((m: any, idx: number) => (
                <div key={idx} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '10px', fontFamily: 'var(--mono)', color: 'var(--blue)', fontWeight: 600 }}>MATCH ON PAGE {m.page_number}</span>
                    <Btn
                      size="xs"
                      onClick={() => {
                        navigator.clipboard.writeText(m.snippet);
                        alert('Snippet copied!');
                      }}
                    >
                      Copy Snippet
                    </Btn>
                  </div>
                  <div style={{ fontSize: '12px', fontFamily: 'var(--mono)', color: 'var(--text2)', whiteSpace: 'pre-wrap', maxHeight: '120px', overflowY: 'auto', lineHeight: 1.5 }}>
                    {m.snippet}
                  </div>
                </div>
              ))}
            </Card>
          ))}
        </div>
      )}
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

function GLBViewer({ modelUrl, jobId, wireframe, resetKey }: { modelUrl?: string, jobId?: string, wireframe: boolean, resetKey: number }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [viewerError, setViewerError] = useState('')
  const maxViewportDimension = 4096

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    setViewerError('')

    let blobUrlToRevoke: string | null = null
    let active = true

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x111827)
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.0
    renderer.domElement.style.display = 'block'
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    host.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    // Balanced studio lighting: ambient + key + fill + top
    scene.add(new THREE.AmbientLight(0xffffff, 1.2))
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.8)
    keyLight.position.set(5, 8, 5)
    scene.add(keyLight)
    const fillLight = new THREE.DirectionalLight(0xffffff, 1.0)
    fillLight.position.set(-5, -3, -5)
    scene.add(fillLight)
    const topLight = new THREE.DirectionalLight(0xffffff, 0.6)
    topLight.position.set(0, 10, 0)
    scene.add(topLight)

    let model: THREE.Object3D | undefined
    const frameModel = () => {
      if (!model) return
      const box = new THREE.Box3().setFromObject(model)
      const size = box.getSize(new THREE.Vector3()).length()
      const center = box.getCenter(new THREE.Vector3())
      model.position.sub(center)
      camera.position.set(size || 3, size || 3, size || 3)
      camera.near = Math.max((size || 3) / 1000, 0.001)
      camera.far = Math.max((size || 3) * 100, 100)
      camera.updateProjectionMatrix()
      controls.target.set(0, 0, 0)
      controls.update()
    }

    const loader = new GLTFLoader()

    const loadModel = async () => {
      try {
        let loadTarget = modelUrl || ''
        if (jobId) {
          try {
            const blob = await api.getPhotogrammetryModelBlob(jobId, 'glb')
            if (!active) return
            blobUrlToRevoke = URL.createObjectURL(blob)
            loadTarget = blobUrlToRevoke
          } catch (fetchErr) {
            console.warn('Could not retrieve model blob via authenticated API, falling back to URL:', fetchErr)
          }
        }
        if (!loadTarget) {
          setViewerError('No model source available.')
          return
        }
        loader.load(
          loadTarget,
          (gltf: any) => {
            if (!active) return
            model = gltf?.scene
            if (!model) return
            model.traverse((child: any) => {
              if (child instanceof THREE.Mesh) {
                const materials = Array.isArray(child.material) ? child.material : [child.material]
                materials.forEach((material: any) => {
                  material.wireframe = wireframe
                  if (child.geometry.getAttribute('color')) {
                    material.vertexColors = true
                    if ('metalness' in material) material.metalness = 0.0
                    if ('roughness' in material) material.roughness = 0.8
                  }
                  material.side = THREE.DoubleSide
                  material.needsUpdate = true
                })
              }
            })
            scene.add(model)
            frameModel()
          },
          undefined,
          () => {
            if (active) setViewerError('The GLB could not be loaded. Check storage access.')
          }
        )
      } catch (err: any) {
        if (active) setViewerError(`Failed to load model: ${err.message || err}`)
      }
    }

    loadModel()

    const resize = () => {
      const bounds = host.getBoundingClientRect()
      const width = Math.min(Math.max(Math.floor(bounds.width), 1), maxViewportDimension)
      const height = Math.min(Math.max(Math.floor(bounds.height), 1), maxViewportDimension)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()
    let animationFrame = 0
    const animate = () => {
      animationFrame = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()
    return () => {
      active = false
      if (blobUrlToRevoke) {
        URL.revokeObjectURL(blobUrlToRevoke)
      }
      cancelAnimationFrame(animationFrame)
      observer.disconnect()
      controls.dispose()
      renderer.dispose()
      host.replaceChildren()
    }
  }, [modelUrl, jobId, wireframe, resetKey])

  return <div ref={hostRef} style={{ width: '100%', height: '100%', minWidth: 0, minHeight: 0, position: 'relative' }}>
    {viewerError && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', padding: '24px', color: 'var(--red)', textAlign: 'center', zIndex: 2 }}>{viewerError}</div>}
  </div>
}

// ── 3D SCENE RECONSTRUCTION (PHOTOGRAMMETRY) PAGE ────────────────────────
export function Photo3DPage() {
  const { user } = useAuth()
  const isAdmin = user?.role?.toLowerCase() === 'admin'
  const [searchParams] = useSearchParams()
  const urlCaseId = searchParams.get('case_id')
  const urlEvidenceId = searchParams.get('evidence_id')

  const [cases, setCases] = useState<Case[]>([])
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const [selectedCaseId, setSelectedCaseId] = useState<string>('')
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([])
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string>('')

  const [status, setStatus] = useState<'Waiting' | 'Pending' | 'Processing' | 'Completed' | 'Failed'>('Waiting')
  const [jobDetails, setJobDetails] = useState<{
    job_id?: string
    evidence_id?: string
    model_url?: string
    point_cloud_url?: string
    frame_count?: number
    created_at?: string
    completed_at?: string
    error_message?: string
  }>({})
  const [evaluationData, setEvaluationData] = useState<any>(null)
  const [loadingEvaluation, setLoadingEvaluation] = useState(false)

  const [pipelineStep, setPipelineStep] = useState<number>(1)
  const [isLogOpen, setIsLogOpen] = useState(false) // Default state: Collapsed
  const [viewMode, setViewMode] = useState<'orbit' | 'wireframe' | 'pointcloud'>('orbit')
  const [viewerReset, setViewerReset] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsExpanded(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const caseRoles = Array.from(new Set(cases.map((item) => item.created_by_role || 'Unassigned'))).sort()
  const visibleCases = !isAdmin || caseRoleFilter === 'All Roles'
    ? cases
    : cases.filter((item) => (item.created_by_role || 'Unassigned') === caseRoleFilter)

  useEffect(() => {
    if (!isAdmin || caseRoleFilter === 'All Roles') return
    if (!visibleCases.some((item) => item.id === selectedCaseId)) {
      setSelectedCaseId(visibleCases[0]?.id || '')
    }
  }, [caseRoleFilter, cases, isAdmin])

  useEffect(() => {
    if (isExpanded) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isExpanded])

  const [logs, setLogs] = useState<string[]>([])
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Pipeline steps definition
  const pipelineSteps = [
    { title: 'Video Upload', desc: 'Source media' },
    { title: 'Frame Extraction', desc: '1 fps sampling' },
    { title: 'Frame Selection', desc: 'Keyframe filter' },
    { title: 'Feature Matching', desc: 'SIFT descriptors' },
    { title: 'Sparse Reconstruction', desc: 'Structure from Motion' },
    { title: 'Dense Reconstruction', desc: 'Multi-view stereo' },
    { title: 'Mesh Generation', desc: 'Poisson surface' },
    { title: 'Completed', desc: 'GLB & PLY exported' }
  ]

  // 1. Fetch Cases on mount
  useEffect(() => {
    async function loadCases() {
      try {
        const res = await api.getCases({ per_page: 50 })
        const caseData = res.data || []
        setCases(caseData)
        if (caseData.length > 0) {
          const matchCase = urlCaseId && caseData.find(c => c.id === urlCaseId)
          setSelectedCaseId(matchCase ? matchCase.id : caseData[0].id)
        }
      } catch (err) {
        console.error('Failed to load cases:', err)
      }
    }
    loadCases()
  }, [])

  // Function to query status
  const checkCurrentStatus = async (jobId: string, expectedEvidenceId?: string) => {
    try {
      const res = await api.getPhotogrammetryStatus(jobId)
      if (res && res.status) {
        if (expectedEvidenceId && res.evidence_id && res.evidence_id !== expectedEvidenceId) {
          return
        }
        setStatus(res.status as any)
        setJobDetails(res)
        if (res.status === 'Completed') {
          setPipelineStep(8)
        } else if (res.status === 'Processing' || res.status === 'Pending') {
          const step = (res as any).current_step
          if (step && step > 0) setPipelineStep(step)
          startPolling(jobId, expectedEvidenceId)
        } else if (res.status === 'Failed') {
          setPipelineStep(1)
          setErrorMsg(`Reconstruction failed.${res.error_message ? ` ${res.error_message}` : ''}`)
        }
      }
    } catch {
      // 404 or no job found yet
    }
  }

  // Polling function (every 3 seconds)
  const startPolling = (jobId: string, expectedEvidenceId?: string) => {
    stopPolling()
    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await api.getPhotogrammetryStatus(jobId)
        if (!res) return
        if (expectedEvidenceId && res.evidence_id && res.evidence_id !== expectedEvidenceId) {
          stopPolling()
          return
        }
        setStatus(res.status as any)
        setJobDetails(res)

        const timeStr = new Date().toLocaleTimeString()

        if (res.status === 'Processing' || res.status === 'Pending') {
          const step = (res as any).current_step
          if (step && step > 0) setPipelineStep(step)
          setLogs(prev => [...prev, `[${timeStr}] Pipeline ${res.status.toLowerCase()}... (step ${step ?? 1}/8)`])
        } else if (res.status === 'Completed') {
          setPipelineStep(8)
          setLogs(prev => [...prev, `[${timeStr}] Model Generated Successfully. Saved GLB & PLY.`])
          stopPolling()
        } else if (res.status === 'Failed') {
          const step = (res as any).current_step || 1
          setPipelineStep(step)
          const reason = res.error_message ? ` ${res.error_message}` : ''
          setErrorMsg(`Reconstruction failed.${reason}`)
          setLogs(prev => [...prev, `[${timeStr}] Reconstruction failed.${reason}`])
          stopPolling()
        }
      } catch (err) {
        console.error('Status polling error:', err)
      }
    }, 3000)
  }

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }

  useEffect(() => {
    return () => stopPolling()
  }, [])

  // 2. Fetch Evidence when selectedCaseId changes
  useEffect(() => {
    if (!selectedCaseId) {
      setEvidenceList([])
      setSelectedEvidenceId('')
      return
    }
    async function loadEvidence() {
      try {
        const res = await api.getEvidence(selectedCaseId)
        const evData = res.data || []
        const videoEvidence = evData.filter(ev => {
          const type = (ev.evidence_type || ev.file_type || '').toLowerCase()
          return type === 'video' || /\.(mp4|mov|avi|mkv)$/i.test(ev.file_name || '')
        })
        setEvidenceList(videoEvidence)
        if (videoEvidence.length > 0) {
          const matchEv = urlEvidenceId && videoEvidence.find(ev => ev.id === urlEvidenceId)
          setSelectedEvidenceId(matchEv ? matchEv.id : videoEvidence[0].id)
        } else {
          setSelectedEvidenceId('')
        }
      } catch (err) {
        console.error('Failed to load evidence:', err)
        setEvidenceList([])
        setSelectedEvidenceId('')
      }
    }
    loadEvidence()
  }, [selectedCaseId])

  // 2.5. Fetch reconstruction status specifically for the selected evidence item
  useEffect(() => {
    stopPolling()

    if (!selectedCaseId || !selectedEvidenceId) {
      setStatus('Waiting')
      setJobDetails({})
      setPipelineStep(1)
      setLogs([])
      setErrorMsg('')
      setEvaluationData(null)
      return
    }

    let active = true

    async function loadStatusForEvidence() {
      setErrorMsg('')
      try {
        const job = await api.getPhotogrammetryStatusByCase(selectedCaseId, selectedEvidenceId)
        if (!active) return

        if (job && job.status) {
          // Safety verification: Ensure the job returned strictly belongs to the selected evidence
          if (job.evidence_id && job.evidence_id !== selectedEvidenceId) {
            console.warn('Received job for different evidence item, ignoring.')
            setStatus('Waiting')
            setJobDetails({})
            setPipelineStep(1)
            return
          }

          setStatus(job.status as any)
          setJobDetails(job)

          if (job.status === 'Completed') {
            setPipelineStep(8)
            setLogs([
              `[${new Date().toLocaleTimeString()}] Loaded existing 3D reconstruction for selected evidence.`,
              `[${new Date().toLocaleTimeString()}] Job ID: ${job.job_id} | Created: ${job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A'}`
            ])
          } else if (job.status === 'Processing' || job.status === 'Pending') {
            const step = job.current_step || 1
            setPipelineStep(step)
            setLogs([
              `[${new Date().toLocaleTimeString()}] Pipeline is currently ${job.status.toLowerCase()} (step ${step}/8). Resuming monitoring...`
            ])
            startPolling(job.job_id, selectedEvidenceId)
          } else if (job.status === 'Failed') {
            const step = job.current_step || 1
            setPipelineStep(step)
            const reason = job.error_message ? ` ${job.error_message}` : ''
            setErrorMsg(`Reconstruction failed.${reason}`)
            setLogs([`[${new Date().toLocaleTimeString()}] Reconstruction failed.${reason}`])
          }
        } else {
          setStatus('Waiting')
          setJobDetails({})
          setPipelineStep(1)
        }
      } catch (err: any) {
        if (!active) return
        // 404 means no reconstruction job exists yet for this specific evidence item
        setStatus('Waiting')
        setJobDetails({})
        setPipelineStep(1)
      }
    }

    loadStatusForEvidence()

    return () => {
      active = false
      stopPolling()
    }
  }, [selectedCaseId, selectedEvidenceId])

  // Fetch evaluation metrics when a job completes or is loaded
  useEffect(() => {
    if (jobDetails.job_id && status === 'Completed') {
      setLoadingEvaluation(true)
      api.getPhotogrammetryEvaluation(jobDetails.job_id)
        .then(data => setEvaluationData(data))
        .catch(() => setEvaluationData(null))
        .finally(() => setLoadingEvaluation(false))
    } else {
      setEvaluationData(null)
    }
  }, [jobDetails.job_id, status])

  // Currently selected evidence item object
  const currentEvidence = evidenceList.find(e => e.id === selectedEvidenceId)

  // 3. Handle Start Reconstruction
  const handleStartReconstruction = async () => {
    if (!selectedCaseId) {
      setErrorMsg('Please select a valid case.')
      return
    }
    if (!currentEvidence) {
      setErrorMsg('Please select an uploaded video evidence item.')
      return
    }

    setErrorMsg('')
    setStatus('Pending')
    setPipelineStep(1)
    const timeStr = new Date().toLocaleTimeString()
    setLogs([
      `[${timeStr}] Triggering photogrammetry pipeline...`,
      `[${timeStr}] Evidence ID: ${currentEvidence.id}`
    ])

    try {
      const job = await api.triggerPhotogrammetry(selectedCaseId, currentEvidence.id)
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Pipeline triggered successfully. Starting polling...`])
      checkCurrentStatus(job.job_id, currentEvidence.id)
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Trigger failed'
      setStatus('Failed')
      setErrorMsg(`Failed to trigger photogrammetry: ${detail}`)
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Trigger error: ${detail}`])
    }
  }

  // Get status color for pipeline step
  const getStepStatus = (index: number) => {
    const stepNum = index + 1
    if (status === 'Failed' && stepNum === pipelineStep) return { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red)', label: 'Failed' }
    if (stepNum < pipelineStep || (status === 'Completed' && stepNum === 8)) return { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green)', label: 'Completed' }
    if (stepNum === pipelineStep && status === 'Processing') return { bg: 'var(--blue-bg)', color: 'var(--blue)', border: 'var(--blue)', label: 'Processing' }
    return { bg: 'var(--bg4)', color: 'var(--text3)', border: 'var(--border)', label: 'Waiting' }
  }

  return (
    <AppShell title="3D Scene Reconstruction">
      {/* SECTION 1 — HEADER */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-flex', padding: '6px', borderRadius: 'var(--r)', background: 'var(--blue-bg)', color: 'var(--blue)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                  <line x1="12" y1="22" x2="12" y2="12" />
                  <polyline points="22 8.5 12 12 2 8.5" />
                </svg>
              </span>
              3D Crime Scene Reconstruction
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text3)' }}>
              Generate an interactive 3D reconstruction of a crime scene from uploaded video evidence using photogrammetry.
            </div>
          </div>
          <Badge label={status} />
        </div>
      </div>

      {errorMsg && (
        <div style={{ marginBottom: '16px' }}>
          <AlertBox type="error">{errorMsg}</AlertBox>
        </div>
      )}

      {/* SECTION 2 — OVERVIEW */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <Card style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
              Reconstruction Status
            </span>
            <span style={{
              color: status === 'Completed' ? 'var(--green)' : status === 'Processing' ? 'var(--blue)' : status === 'Failed' ? 'var(--red)' : 'var(--text3)'
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
            <Badge label={status} />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)' }}>
            {status === 'Completed' ? 'Finished successfully' : status === 'Processing' ? 'Pipeline processing' : status === 'Failed' ? 'Reconstruction failed' : 'Awaiting evidence selection'}
          </div>
        </Card>

        <Card style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
              Selected Frames
            </span>
            <span style={{ color: 'var(--blue)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            </span>
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
            {jobDetails.frame_count ? jobDetails.frame_count : (status === 'Waiting' ? '0' : 'Extracting...')}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)' }}>
            {status === 'Waiting' ? 'No frames sampled' : 'Keyframes sampled'}
          </div>
        </Card>

        <Card style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
              Point Cloud
            </span>
            <span style={{ color: status === 'Completed' ? 'var(--green)' : 'var(--text3)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
              </svg>
            </span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
            {status === 'Completed' ? (jobDetails.point_cloud_url ? 'Available (.ply)' : 'Generated') : 'Not Generated'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)' }}>
            {status === 'Completed' ? 'Point cloud created' : 'Awaiting dense reconstruction'}
          </div>
        </Card>

        <Card style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
              3D Model
            </span>
            <span style={{ color: status === 'Completed' ? 'var(--green)' : 'var(--text3)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              </svg>
            </span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
            {status === 'Completed' ? (jobDetails.model_url ? 'Available (.glb)' : 'Generated') : 'Not Available'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text3)' }}>
            {status === 'Completed' ? 'Textured Poisson mesh' : 'Awaiting mesh generation'}
          </div>
        </Card>
      </div>

      {/* SECTION 3 — SELECT EVIDENCE */}
      <Card style={{ marginBottom: '24px' }}>
        <CardTitle>Select Evidence</CardTitle>
        <div style={{ display: 'grid', gridTemplateColumns: isAdmin ? '0.7fr 1.3fr 1.3fr' : '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          {isAdmin && <div>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>
              Creator Role
            </label>
            <select
              value={caseRoleFilter}
              onChange={(e) => setCaseRoleFilter(e.target.value)}
              style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none' }}
            >
              <option>All Roles</option>
              {caseRoles.map((role) => <option key={role}>{role}</option>)}
            </select>
          </div>}
          <div>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>
              Select Case
            </label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              style={{
                width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
                borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none'
              }}
            >
              {visibleCases.length === 0 ? (
                <option value="">No cases found</option>
              ) : (
                visibleCases.map(c => <option key={c.id} value={c.id}>{c.case_number} — {c.title} — {c.created_by_role || 'Unassigned'}: {c.created_by_name || 'Unknown user'}</option>)
              )}
            </select>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>
              Select Uploaded Video Evidence
            </label>
            <select
              value={selectedEvidenceId}
              onChange={(e) => setSelectedEvidenceId(e.target.value)}
              style={{
                width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
                borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none'
              }}
            >
              {evidenceList.length === 0 ? (
                <option value="">No video evidence found for selected case</option>
              ) : (
                evidenceList.map(ev => (
                  <option key={ev.id} value={ev.id}>
                    {ev.file_name || ev.description || ev.id} ({ev.evidence_type})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        {/* Evidence Metadata */}
        {currentEvidence && (
          <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '14px', marginBottom: '20px' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--blue)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              Selected Evidence Details
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div>
                <span style={{ fontSize: '10px', color: 'var(--text3)', display: 'block', textTransform: 'uppercase' }}>Evidence Name</span>
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', fontFamily: 'var(--mono)' }}>
                  {currentEvidence.file_name || 'N/A'}
                </span>
              </div>
              <div>
                <span style={{ fontSize: '10px', color: 'var(--text3)', display: 'block', textTransform: 'uppercase' }}>Evidence Type</span>
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)' }}>{currentEvidence.evidence_type}</span>
              </div>
              <div>
                <span style={{ fontSize: '10px', color: 'var(--text3)', display: 'block', textTransform: 'uppercase' }}>Status</span>
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)' }}>{currentEvidence.status}</span>
              </div>
              <div>
                <span style={{ fontSize: '10px', color: 'var(--text3)', display: 'block', textTransform: 'uppercase' }}>File Size</span>
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)' }}>
                  {currentEvidence.file_size ? `${(currentEvidence.file_size / (1024 * 1024)).toFixed(1)} MB` : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Generate Button */}
        <div style={{ textAlign: 'center' }}>
          <Btn
            variant="primary"
            size="md"
            full
            loading={status === 'Pending' || status === 'Processing'}
            disabled={status === 'Pending' || status === 'Processing' || !currentEvidence}
            onClick={handleStartReconstruction}
            style={{ padding: '12px 20px', fontSize: '14px', fontWeight: 600, justifyContent: 'center' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            {status === 'Pending' || status === 'Processing' ? 'Processing COLMAP Pipeline...' : 'Generate 3D Reconstruction'}
          </Btn>
          <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '8px' }}>
            Estimated Processing Time: Approx. 2–5 minutes
          </div>
        </div>
      </Card>

      {/* SECTION 4 — RECONSTRUCTION PIPELINE */}
      <Card style={{ marginBottom: '24px' }}>
        <CardTitle>Reconstruction Pipeline</CardTitle>
        <div style={{ overflowX: 'auto', paddingBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', minWidth: '850px', justifyContent: 'space-between', position: 'relative' }}>
            {pipelineSteps.map((step, idx) => {
              const st = getStepStatus(idx)
              return (
                <React.Fragment key={idx}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', flex: 1, zIndex: 2 }}>
                    <div style={{
                      width: '36px', height: '36px', borderRadius: '50%',
                      background: st.bg, border: `2px solid ${st.border}`, color: st.color,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '12px', fontWeight: 700, marginBottom: '8px',
                      boxShadow: st.label === 'Processing' ? '0 0 12px var(--blue)' : 'none',
                      transition: 'all .3s'
                    }}>
                      {idx + 1}
                    </div>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text)', marginBottom: '2px' }}>{step.title}</div>
                    <div style={{ fontSize: '9px', color: 'var(--text3)' }}>{step.desc}</div>
                    <span style={{ fontSize: '9px', fontWeight: 600, color: st.color, marginTop: '4px' }}>{st.label}</span>
                  </div>
                  {idx < pipelineSteps.length - 1 && (
                    <div style={{
                      height: '2px', flex: 0.8,
                      background: (idx + 1) < pipelineStep ? 'var(--green)' : (idx + 1) === pipelineStep ? 'var(--blue)' : 'var(--border)',
                      marginTop: '-24px', transition: 'background .3s'
                    }} />
                  )}
                </React.Fragment>
              )
            })}
          </div>
        </div>
      </Card>

      {/* SECTION 5 — RESULTS */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2.2fr', gap: '20px', marginBottom: '24px', alignItems: 'stretch' }}>
        {/* LEFT COLUMN: Reconstruction Metrics */}
        <Card style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <CardTitle>Reconstruction Metrics</CardTitle>
            <InfoRow label="Status" value={<Badge label={status} />} />
            <InfoRow label="Frame Count" value={jobDetails.frame_count ? `${jobDetails.frame_count} keyframes` : (status === 'Waiting' ? '0' : 'Extracting...')} />
            <InfoRow label="Created Time" value={jobDetails.created_at ? new Date(jobDetails.created_at).toLocaleTimeString() : 'N/A'} />
            <InfoRow label="Completed Time" value={jobDetails.completed_at ? new Date(jobDetails.completed_at).toLocaleTimeString() : 'N/A'} />
            <InfoRow label="Point Cloud URL" value={jobDetails.point_cloud_url ? 'Available' : 'N/A'} mono />
            <InfoRow label="Model Format" value="glTF 2.0 / GLB & PLY" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '24px' }}>
            <Btn
              variant="green"
              size="md"
              full
              disabled={status !== 'Completed' || (!jobDetails.model_url && !jobDetails.job_id)}
              onClick={async () => {
                if (jobDetails.job_id) {
                  try {
                    await api.downloadPhotogrammetryModel(jobDetails.job_id, 'glb')
                  } catch (e: any) {
                    setErrorMsg(`Failed to download GLB: ${e.message || e}`)
                  }
                }
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download GLB
            </Btn>
            <Btn
              variant="default"
              size="md"
              full
              disabled={status !== 'Completed' || (!jobDetails.point_cloud_url && !jobDetails.job_id)}
              onClick={async () => {
                if (jobDetails.job_id) {
                  try {
                    await api.downloadPhotogrammetryModel(jobDetails.job_id, 'ply')
                  } catch (e: any) {
                    setErrorMsg(`Failed to download PLY: ${e.message || e}`)
                  }
                }
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download PLY
            </Btn>
          </div>
        </Card>

        {/* RIGHT COLUMN: Large 3D Model Viewer with Expandable Fullscreen Mode */}
        <Card
          style={isExpanded ? {
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            width: '100vw',
            height: '100vh',
            borderRadius: 0,
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg)',
            boxShadow: '0 0 50px rgba(0,0,0,0.85)'
          } : {
            display: 'flex',
            flexDirection: 'column',
            height: 'clamp(440px, 55vh, 720px)',
            minHeight: 0,
            minWidth: 0
          }}
        >
          <CardHeader style={isExpanded ? {
            padding: '12px 24px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          } : undefined}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <CardTitle>
                {isExpanded ? '3D Scene Reconstruction — Fullscreen Inspection' : '3D Model Viewer'}
              </CardTitle>
              {isExpanded && (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(34, 197, 94, 0.15)',
                  color: 'var(--green)',
                  border: '1px solid rgba(34, 197, 94, 0.3)'
                }}>
                  Live 3D View
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <Btn size="xs" variant={viewMode === 'orbit' ? 'primary' : 'default'} onClick={() => setViewMode('orbit')}>Orbit</Btn>
              <Btn size="xs" variant={viewMode === 'wireframe' ? 'primary' : 'default'} onClick={() => setViewMode('wireframe')}>Wireframe</Btn>
              <Btn size="xs" variant={viewMode === 'pointcloud' ? 'primary' : 'default'} onClick={() => setViewMode('pointcloud')}>Points</Btn>
              <Btn size="xs" variant="default" onClick={() => setViewerReset(prev => prev + 1)}>Reset</Btn>
              <Btn
                size="xs"
                variant={isExpanded ? 'danger' : 'primary'}
                onClick={() => setIsExpanded(prev => !prev)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '28px',
                  height: '24px',
                  padding: 0,
                  color: '#ffffff'
                }}
                title={isExpanded ? 'Exit Fullscreen (Esc)' : 'Expand 3D Scene View'}
              >
                {isExpanded ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="15 3 21 3 21 9" />
                    <polyline points="9 21 3 21 3 15" />
                    <line x1="21" y1="3" x2="14" y2="10" />
                    <line x1="3" y1="21" x2="10" y2="14" />
                  </svg>
                )}
              </Btn>
            </div>
          </CardHeader>

          {/* Viewport Canvas Area */}
          <div style={{
            flex: '1 1 0', minHeight: 0, minWidth: 0, borderRadius: isExpanded ? 0 : 'var(--r)',
            background: 'radial-gradient(circle at center, var(--bg3) 0%, var(--bg2) 100%)',
            border: isExpanded ? 'none' : '1px dashed var(--border2)', position: 'relative',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden', padding: isExpanded ? 0 : '24px'
          }}>
            {/* Engineering Grid Pattern */}
            <div style={{
              position: 'absolute', inset: 0, opacity: 0.15, pointerEvents: 'none',
              backgroundImage: 'linear-gradient(var(--text3) 1px, transparent 1px), linear-gradient(90deg, var(--text3) 1px, transparent 1px)',
              backgroundSize: '24px 24px'
            }} />


            {/* Bottom HUD Navigation Guide in Fullscreen */}
            {isExpanded && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '24px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  zIndex: 20,
                  background: 'rgba(15, 23, 42, 0.78)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '24px',
                  padding: '7px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  fontSize: '11.5px',
                  letterSpacing: '0.2px',
                  color: 'rgba(255, 255, 255, 0.8)',
                  pointerEvents: 'none',
                  boxShadow: '0 12px 36px -4px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.12)'
                }}
              >
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.9 }}>
                    <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                  </svg>
                  <span><strong style={{ color: '#fff', fontWeight: 600 }}>Rotate:</strong> Left Click</span>
                </div>

                <span style={{ width: '1px', height: '14px', background: 'rgba(255, 255, 255, 0.15)' }} />

                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.9 }}>
                    <polyline points="5 9 2 12 5 15" />
                    <polyline points="9 5 12 2 15 5" />
                    <polyline points="15 19 12 22 9 19" />
                    <polyline points="19 9 22 12 19 15" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <line x1="12" y1="2" x2="12" y2="22" />
                  </svg>
                  <span><strong style={{ color: '#fff', fontWeight: 600 }}>Pan:</strong> Right Click</span>
                </div>

                <span style={{ width: '1px', height: '14px', background: 'rgba(255, 255, 255, 0.15)' }} />

                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.9 }}>
                    <circle cx="11" cy="11" r="7" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    <line x1="11" y1="8" x2="11" y2="14" />
                    <line x1="8" y1="11" x2="14" y2="11" />
                  </svg>
                  <span><strong style={{ color: '#fff', fontWeight: 600 }}>Zoom:</strong> Scroll</span>
                </div>

                <span style={{ width: '1px', height: '14px', background: 'rgba(255, 255, 255, 0.15)' }} />

                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <kbd style={{
                    padding: '1px 6px',
                    borderRadius: '4px',
                    background: 'rgba(255, 255, 255, 0.12)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    color: '#fff'
                  }}>
                    ESC
                  </kbd>
                  <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Exit</span>
                </div>
              </div>
            )}

            {status !== 'Completed' ? (
              <div style={{ textAlign: 'center', zIndex: 2, padding: '30px' }}>
                <div style={{
                  width: '60px', height: '60px', borderRadius: '50%', background: 'var(--bg4)',
                  border: '1px solid var(--border)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  color: status === 'Failed' ? 'var(--red)' : status === 'Processing' ? 'var(--blue)' : 'var(--text3)', marginBottom: '16px'
                }}>
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                    <line x1="12" y1="22" x2="12" y2="12" />
                    <polyline points="22 8.5 12 12 2 8.5" />
                  </svg>
                </div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>
                  {status === 'Failed' ? 'Reconstruction Failed' : status === 'Processing' ? 'Reconstruction In Progress...' : '3D Model Viewer'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text3)', maxWidth: '340px' }}>
                  {status === 'Failed' ? 'Check backend pipeline logs for error details.' : status === 'Processing' ? 'Processing frames and generating point cloud...' : '3D reconstruction will appear here after processing.'}
                </div>
              </div>
            ) : (
              (jobDetails.model_url || jobDetails.job_id) &&
              (!jobDetails.evidence_id || jobDetails.evidence_id === selectedEvidenceId) && (
                <GLBViewer
                  modelUrl={jobDetails.model_url}
                  jobId={jobDetails.job_id}
                  wireframe={viewMode === 'wireframe'}
                  resetKey={viewerReset}
                />
              )
            )}
          </div>
        </Card>
      </div>

      {/* SECTION 5.5 — RESEARCH EVALUATION & RECONSTRUCTION METRICS */}
      {status === 'Completed' && (
        <Card style={{ marginBottom: '24px' }}>
          <CardHeader>
            <CardTitle>Research Evaluation &amp; Accuracy Metrics</CardTitle>
            <span style={{ fontSize: '11px', color: 'var(--text3)' }}>
              {evaluationData ? 'Empirical Reconstruction Audit' : loadingEvaluation ? 'Evaluating artifacts...' : 'Available on completed jobs'}
            </span>
          </CardHeader>
          
          {evaluationData ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                <div style={{ background: 'var(--bg3)', padding: '12px', borderRadius: 'var(--r)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Registration Rate</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--blue)' }}>
                    {evaluationData.colmap_sfm?.registered_images ?? evaluationData.registered_images ?? 'N/A'} / {evaluationData.frame_processing?.selected_frames_count ?? evaluationData.selected_frames ?? 'N/A'}
                    <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text3)', marginLeft: '6px' }}>
                      ({evaluationData.colmap_sfm?.registration_percentage ?? evaluationData.registration_percent ?? 0}%)
                    </span>
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', padding: '12px', borderRadius: 'var(--r)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Mean Reprojection Error</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--green)' }}>
                    {evaluationData.colmap_sfm?.mean_reprojection_error_px ?? evaluationData.reprojection_error_px ?? 'N/A'}
                    <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text3)', marginLeft: '4px' }}>px</span>
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', padding: '12px', borderRadius: 'var(--r)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Dense Points (Cleaned)</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
                    {(evaluationData.geometry_and_mesh?.cleaned_point_count ?? evaluationData.cleaned_points ?? 0).toLocaleString()}
                    <span style={{ fontSize: '11px', color: 'var(--text3)', marginLeft: '6px' }}>
                      (-{evaluationData.geometry_and_mesh?.points_removed_percent ?? evaluationData.points_removed_percent ?? 0}% outliers)
                    </span>
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', padding: '12px', borderRadius: 'var(--r)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Mesh Triangles / Vertices</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
                    {(evaluationData.geometry_and_mesh?.mesh_triangle_count ?? evaluationData.mesh_triangles ?? 0).toLocaleString()}
                    <span style={{ fontSize: '11px', color: 'var(--text3)', marginLeft: '6px' }}>
                      ({(evaluationData.geometry_and_mesh?.mesh_vertex_count ?? evaluationData.mesh_vertices ?? 0).toLocaleString()} vtx)
                    </span>
                  </div>
                </div>
              </div>

              {evaluationData.physical_dimension_accuracy && evaluationData.physical_dimension_accuracy.status === 'evaluated' && (
                <div style={{ background: 'var(--bg3)', padding: '12px 14px', borderRadius: 'var(--r)', border: '1px solid var(--blue)', marginBottom: '14px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--blue)', marginBottom: '6px' }}>
                    Physical Dimension Accuracy Evaluation
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                    <div>Mean Absolute Error (MAE): <strong>{evaluationData.physical_dimension_accuracy.mean_absolute_error} {evaluationData.physical_dimension_accuracy.unit}</strong></div>
                    <div>Mean Absolute Percentage Error (MAPE): <strong>{evaluationData.physical_dimension_accuracy.mean_absolute_percentage_error}%</strong></div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '12px', fontSize: '12px', color: 'var(--text3)', textAlign: 'center' }}>
              {loadingEvaluation ? 'Analyzing reconstruction logs and point cloud geometry...' : 'No evaluation data loaded for this reconstruction.'}
            </div>
          )}
        </Card>
      )}

      {/* SECTION 6 — PROCESSING LOG (Collapsible, Default: Collapsed) */}
      <Card>
        <div
          onClick={() => setIsLogOpen(!isLogOpen)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px' }}>
              Processing Log
            </span>
            <span style={{ fontSize: '10px', fontFamily: 'var(--mono)', color: 'var(--text3)' }}>
              ({logs.length} entries)
            </span>
          </div>
          <span style={{ color: 'var(--text3)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
            {isLogOpen ? 'Hide Log' : 'Show Log'}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: isLogOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </span>
        </div>

        {isLogOpen && (
          <div style={{
            marginTop: '14px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)',
            padding: '14px', fontFamily: 'var(--mono)', fontSize: '11px', lineHeight: '1.7',
            maxHeight: '220px', overflowY: 'auto', color: 'var(--text2)'
          }}>
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text3)' }}>No log entries yet. Click "Generate 3D Reconstruction" to start.</div>
            ) : (
              logs.map((log, i) => (
                <div key={i} style={{ color: log.includes('Successfully') || log.includes('Completed') ? 'var(--green)' : log.includes('Triggering') || log.includes('Processing') ? 'var(--blue)' : log.includes('Failed') || log.includes('error') ? 'var(--red)' : 'var(--text2)' }}>
                  {log}
                </div>
              ))
            )}
          </div>
        )}
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
  const [caseRoleFilter, setCaseRoleFilter] = useState('All Roles')
  const visibleCaseResults = filterCasesByCreatorRole(caseResults, caseRoleFilter)

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
          <CaseCreatorRoleFilter value={caseRoleFilter} onChange={setCaseRoleFilter} />
          <input
            value={caseSearch}
            onChange={(e) => { setCaseSearch(e.target.value); searchCases(e.target.value) }}
            placeholder="Search case by ID, title, or victim name to view graph..."
            style={{ width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 14px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }}
          />
          {visibleCaseResults.length > 0 && (
            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', marginTop: '4px', overflow: 'hidden' }}>
              {visibleCaseResults.map((c) => (
                <div key={c.id} onClick={() => { setSelectedCaseId(c.id); setCaseSearch(''); setCaseResults([]) }} style={{ padding: '8px 14px', cursor: 'pointer', fontSize: '12px', borderBottom: '1px solid var(--border)' }} onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg4)' }} onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
                  <CaseSearchResult item={c} />
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
