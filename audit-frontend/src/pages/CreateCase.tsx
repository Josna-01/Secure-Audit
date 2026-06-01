import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, Btn, Input, Textarea, Select, AlertBox, StepWizard } from '../components/UI'
import { api } from '../services/api'
import type { Victim, Suspect } from '../types'

const OFFENCE_TYPES = [
  { value: '', label: 'Select type...' },
  { value: 'Robbery', label: 'Robbery' },
  { value: 'Assault', label: 'Assault' },
  { value: 'Murder', label: 'Murder' },
  { value: 'Theft', label: 'Theft' },
  { value: 'Cybercrime', label: 'Cybercrime' },
  { value: 'Extortion', label: 'Extortion' },
  { value: 'Kidnapping', label: 'Kidnapping' },
  { value: 'Fraud', label: 'Fraud' },
  { value: 'Other', label: 'Other (specify below)' }
]

const LANGUAGES = [
  { value: 'auto', label: 'Auto Detect' },
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'kn', label: 'Kannada' },
  { value: 'ml', label: 'Malayalam' }
]

export default function CreateCase() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null)

  // Step 1 fields
  const [title, setTitle] = useState('')
  const [offenceType, setOffenceType] = useState('')
  const [offenceCustom, setOffenceCustom] = useState('')
  const [incidentDate, setIncidentDate] = useState('')
  const [incidentTime, setIncidentTime] = useState('')
  const [incidentLocation, setIncidentLocation] = useState('')

  // Step 2 fields
  const [victims, setVictims] = useState<Victim[]>([{ name: '' }])
  const [suspects, setSuspects] = useState<Suspect[]>([{ name: '' }])
  const [complainant, setComplainant] = useState('')
  const [complainantContact, setComplainantContact] = useState('')

  // Step 3 fields
  const [firText, setFirText] = useState('')
  const [firLanguage, setFirLanguage] = useState('auto')

  const autoId = `SA-${new Date().getFullYear()}-XXXX`

  const nextStep = () => {
    setError('')
    if (step === 1) {
      if (!title.trim()) { setError('Case title is required.'); return }
      if (!offenceType) { setError('Offence type is required.'); return }
    }
    if (step === 2) {
      if (!complainant.trim()) { setError('Complainant name is required.'); return }
      if (victims.every((v) => !v.name.trim())) { setError('At least one victim is required.'); return }
    }
    if (step === 3) {
      if (!firText.trim()) { setError('FIR description is required.'); return }
    }
    setStep((s) => s + 1)
  }

  const submit = async () => {
    setLoading(true); setError('')
    try {
      const res = await api.createCase({
        title,
        offence_type: offenceType === 'Other' ? offenceCustom : offenceType,
        fir_description: firText,
        fir_language: firLanguage,
        complainant_name: complainant,
        complainant_contact: complainantContact || undefined,
        victims: victims.filter((v) => v.name.trim()),
        suspects: suspects.filter((s) => s.name.trim()),
        incident_date: incidentDate || undefined,
        incident_time: incidentTime || undefined,
        incident_location: incidentLocation || undefined
      })
      setCreatedCaseId(res.data.id)
      setStep(5)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Failed to create case.')
    } finally { setLoading(false) }
  }

  const addVictim = () => setVictims((v) => [...v, { name: '' }])
  const removeVictim = (i: number) => setVictims((v) => v.filter((_, idx) => idx !== i))
  const updateVictim = (i: number, val: string) => setVictims((v) => v.map((x, idx) => idx === i ? { ...x, name: val } : x))

  const addSuspect = () => setSuspects((s) => [...s, { name: '' }])
  const removeSuspect = (i: number) => setSuspects((s) => s.filter((_, idx) => idx !== i))
  const updateSuspect = (i: number, val: string) => setSuspects((s) => s.map((x, idx) => idx === i ? { ...x, name: val } : x))

  return (
    <AppShell title="Create Professional Case">
      <Card style={{ maxWidth: '720px', margin: '0 auto' }}>
        {step < 5 && <StepWizard steps={['Basics', 'People', 'FIR', 'Review']} current={step} />}

        {error && <div style={{ marginBottom: '16px' }}><AlertBox type="error">{error}</AlertBox></div>}

        {/* Step 1 */}
        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>Case Number (Auto-generated)</label>
              <input value={autoId} disabled style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text3)', fontFamily: 'var(--mono)', opacity: 0.6, outline: 'none' }} />
            </div>
            <Input label="Case Title *" placeholder="e.g. Robbery at City Bank" value={title} onChange={(e) => setTitle(e.target.value)} />
            <div>
              <Select label="Offence Type *" options={OFFENCE_TYPES} value={offenceType} onChange={(e) => setOffenceType(e.target.value)} />
              {offenceType === 'Other' && (
                <input value={offenceCustom} onChange={(e) => setOffenceCustom(e.target.value)} placeholder="Specify offence type" style={{ marginTop: '8px', width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
              )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <Input label="Date of Incident" type="date" value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
              <Input label="Time of Incident" type="time" value={incidentTime} onChange={(e) => setIncidentTime(e.target.value)} />
            </div>
            <Input label="Incident Location" placeholder="Street, Area, City" value={incidentLocation} onChange={(e) => setIncidentLocation(e.target.value)} />
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', marginBottom: '8px' }}>Victim(s) <span style={{ fontSize: '10px', color: 'var(--text3)' }}>— add multiple</span></div>
              {victims.map((v, i) => (
                <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                  <input value={v.name} onChange={(e) => updateVictim(i, e.target.value)} placeholder="Victim name, age, contact" style={{ flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
                  {i === victims.length - 1 ? <Btn size="xs" variant="green" onClick={addVictim}>+ Add</Btn> : <Btn size="xs" variant="danger" onClick={() => removeVictim(i)}>Remove</Btn>}
                </div>
              ))}
            </div>
            <div style={{ height: '1px', background: 'var(--border)' }} />
            <div>
              <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', marginBottom: '8px' }}>Suspect(s) <span style={{ fontSize: '10px', color: 'var(--text3)' }}>— optional, can be Unknown</span></div>
              {suspects.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                  <input value={s.name} onChange={(e) => updateSuspect(i, e.target.value)} placeholder="Suspect name or Unknown" style={{ flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }} />
                  {i === suspects.length - 1 ? <Btn size="xs" variant="green" onClick={addSuspect}>+ Add</Btn> : <Btn size="xs" variant="danger" onClick={() => removeSuspect(i)}>Remove</Btn>}
                </div>
              ))}
            </div>
            <div style={{ height: '1px', background: 'var(--border)' }} />
            <Input label="Complainant Name *" placeholder="Person filing the complaint" value={complainant} onChange={(e) => setComplainant(e.target.value)} />
            <Input label="Complainant Contact" placeholder="+91 XXXXX XXXXX or email" value={complainantContact} onChange={(e) => setComplainantContact(e.target.value)} />
          </div>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '11px', color: 'var(--red)', textTransform: 'uppercase', letterSpacing: '.4px', fontWeight: 600 }}>FIR / Complaint Description * (Most Important)</label>
                <Select options={LANGUAGES} value={firLanguage} onChange={(e) => setFirLanguage(e.target.value)} style={{ width: '130px', padding: '3px 8px', fontSize: '11px' }} />
              </div>
              <textarea
                value={firText}
                onChange={(e) => setFirText(e.target.value)}
                rows={12}
                placeholder="Describe the incident in full detail — what happened, when, where, who was involved, sequence of events, any witnesses..."
                style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '9px 12px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', resize: 'vertical', lineHeight: 1.7 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                <span style={{ fontSize: '10px', color: 'var(--text3)' }}>Supports multilingual input — translated to English for AI processing</span>
                <span style={{ fontSize: '10px', color: 'var(--text3)' }}>{firText.length} chars</span>
              </div>
            </div>
            <div style={{ padding: '10px 12px', background: 'var(--blue-dim)', border: '1px solid var(--blue)', borderRadius: 'var(--r)', fontSize: '11px', color: 'var(--blue)' }}>
              This FIR description will be the primary input for BNS Classification and AI Storyboard generation.
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ padding: '14px', background: 'var(--bg3)', borderRadius: 'var(--r2)' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginBottom: '10px' }}>Review Case Details</div>
              {[
                ['Title', title],
                ['Offence', offenceType === 'Other' ? offenceCustom : offenceType],
                ['Date / Time', [incidentDate, incidentTime].filter(Boolean).join(' · ') || '—'],
                ['Location', incidentLocation || '—'],
                ['Complainant', complainant],
                ['Victims', victims.filter((v) => v.name).map((v) => v.name).join(', ') || '—'],
                ['Suspects', suspects.filter((s) => s.name).map((s) => s.name).join(', ') || '—'],
                ['FIR Length', firText.length + ' characters'],
                ['FIR Language', firLanguage === 'auto' ? 'Auto Detect' : firLanguage.toUpperCase()]
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', gap: '10px', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text3)', minWidth: '100px' }}>{k}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text2)' }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ padding: '10px 12px', background: 'var(--amber-bg)', border: '1px solid var(--amber)', borderRadius: 'var(--r)', fontSize: '11px', color: 'var(--amber)' }}>
              Once created, the case will be assigned an auto-generated case number and all actions will be logged in the immutable audit trail.
            </div>
          </div>
        )}

        {/* Step 5: Success */}
        {step === 5 && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: 'var(--green-bg)', border: '2px solid var(--green)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontSize: '24px' }}>+</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>Case Created Successfully</div>
            <div style={{ fontSize: '12px', color: 'var(--text3)', marginBottom: '20px' }}>Your case has been created, SHA-256 hashed, and logged in the audit trail.</div>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <Btn variant="primary" onClick={() => navigate(`/cases/${createdCaseId}`)}>View Case</Btn>
              <Btn onClick={() => navigate('/evidence')}>Add Evidence</Btn>
              <Btn onClick={() => navigate('/dashboard')}>Dashboard</Btn>
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        {step < 5 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
            {step > 1 ? <Btn onClick={() => { setError(''); setStep((s) => s - 1) }}>Back</Btn> : <Btn onClick={() => navigate('/cases')}>Cancel</Btn>}
            {step < 4 ? (
              <Btn variant="primary" onClick={nextStep}>Continue</Btn>
            ) : (
              <Btn variant="primary" loading={loading} onClick={submit}>Create Case</Btn>
            )}
          </div>
        )}
      </Card>
    </AppShell>
  )
}
