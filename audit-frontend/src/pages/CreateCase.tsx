import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/Layout'
import { Card, CardHeader, CardTitle, Btn, Input, Textarea, Select, AlertBox, StepWizard } from '../components/UI'
import { api } from '../services/api'
import type { Victim, Suspect } from '../types'

const OFFENCE_TYPES = [
  { value: '', label: 'Select offence type...' },
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
    <AppShell title="Create Investigation Case">
      <Card style={{ maxWidth: '780px', margin: '0 auto', padding: '28px 32px' }}>
        {step < 5 && (
          <div style={{ marginBottom: '28px' }}>
            <StepWizard steps={['Investigation Basics', 'Persons & Witnesses', 'FIR Narrative', 'Verification & Review']} current={step} />
          </div>
        )}

        {error && <div style={{ marginBottom: '20px' }}><AlertBox type="error">{error}</AlertBox></div>}

        {/* Step 1 */}
        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text3)', display: 'block', marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                System Reference Identifier (Auto-generated)
              </label>
              <input
                value={autoId}
                disabled
                style={{
                  width: '100%',
                  background: 'var(--bg3)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--r)',
                  padding: '9px 12px',
                  fontSize: '13px',
                  color: 'var(--blue)',
                  fontFamily: 'var(--mono)',
                  fontWeight: 600,
                  opacity: 0.85,
                  outline: 'none'
                }}
              />
            </div>

            <Input
              label="Investigation Title *"
              placeholder="e.g. Armed Robbery at Downtown Jewelry Exchange"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />

            <div>
              <Select
                label="Offence Category *"
                options={OFFENCE_TYPES}
                value={offenceType}
                onChange={(e) => setOffenceType(e.target.value)}
              />
              {offenceType === 'Other' && (
                <input
                  value={offenceCustom}
                  onChange={(e) => setOffenceCustom(e.target.value)}
                  placeholder="Specify custom offence classification..."
                  style={{
                    marginTop: '8px',
                    width: '100%',
                    background: 'var(--bg3)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--r)',
                    padding: '8px 12px',
                    fontSize: '13px',
                    color: 'var(--text)',
                    outline: 'none'
                  }}
                />
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <Input
                label="Incident Date"
                type="date"
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
              />
              <Input
                label="Incident Time"
                type="time"
                value={incidentTime}
                onChange={(e) => setIncidentTime(e.target.value)}
              />
            </div>

            <Input
              label="Incident Location"
              placeholder="Full landmark, Sector, District, City"
              value={incidentLocation}
              onChange={(e) => setIncidentLocation(e.target.value)}
            />
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)', marginBottom: '10px' }}>
                Victim(s) Details <span style={{ fontSize: '11px', color: 'var(--text3)', fontWeight: 400 }}>— add all injured or affected parties</span>
              </div>
              {victims.map((v, i) => (
                <div key={i} style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                  <input
                    value={v.name}
                    onChange={(e) => updateVictim(i, e.target.value)}
                    placeholder="Victim name, age, contact, residential details..."
                    style={{
                      flex: 1,
                      background: 'var(--bg3)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r)',
                      padding: '8px 12px',
                      fontSize: '13px',
                      color: 'var(--text)',
                      outline: 'none'
                    }}
                  />
                  {i === victims.length - 1 ? (
                    <Btn size="sm" variant="green" onClick={addVictim}>+ Add Victim</Btn>
                  ) : (
                    <Btn size="sm" variant="danger" onClick={() => removeVictim(i)}>Remove</Btn>
                  )}
                </div>
              ))}
            </div>

            <div style={{ height: '1px', background: 'var(--border)' }} />

            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)', marginBottom: '10px' }}>
                Suspect(s) Information <span style={{ fontSize: '11px', color: 'var(--text3)', fontWeight: 400 }}>— optional, or marked as 'Unknown Suspect'</span>
              </div>
              {suspects.map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                  <input
                    value={s.name}
                    onChange={(e) => updateSuspect(i, e.target.value)}
                    placeholder="Suspect identity, alias, physical description, or Unknown..."
                    style={{
                      flex: 1,
                      background: 'var(--bg3)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r)',
                      padding: '8px 12px',
                      fontSize: '13px',
                      color: 'var(--text)',
                      outline: 'none'
                    }}
                  />
                  {i === suspects.length - 1 ? (
                    <Btn size="sm" variant="green" onClick={addSuspect}>+ Add Suspect</Btn>
                  ) : (
                    <Btn size="sm" variant="danger" onClick={() => removeSuspect(i)}>Remove</Btn>
                  )}
                </div>
              ))}
            </div>

            <div style={{ height: '1px', background: 'var(--border)' }} />

            <Input
              label="Complainant Name *"
              placeholder="Officer, witness, or citizen filing the complaint"
              value={complainant}
              onChange={(e) => setComplainant(e.target.value)}
            />
            <Input
              label="Complainant Contact Information"
              placeholder="+91 XXXXX XXXXX or official email address"
              value={complainantContact}
              onChange={(e) => setComplainantContact(e.target.value)}
            />
          </div>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 700 }}>
                  FIR / Comprehensive Incident Narrative *
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text3)' }}>Language:</span>
                  <Select
                    options={LANGUAGES}
                    value={firLanguage}
                    onChange={(e) => setFirLanguage(e.target.value)}
                    style={{ width: '130px', padding: '4px 10px', fontSize: '12px' }}
                  />
                </div>
              </div>
              <textarea
                value={firText}
                onChange={(e) => setFirText(e.target.value)}
                rows={12}
                placeholder="Transcribe the verbatim statement or full sequence of events: who was present, weapon details, monetary loss, injuries inflicted, timeline of actions..."
                style={{
                  width: '100%',
                  background: 'var(--bg3)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--r2)',
                  padding: '12px 16px',
                  fontSize: '13.5px',
                  color: 'var(--text)',
                  fontFamily: 'var(--font)',
                  outline: 'none',
                  resize: 'vertical',
                  lineHeight: 1.7
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text3)' }}>
                  Supports multilingual OCR & FIR text (translated for AI classification)
                </span>
                <span style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                  {firText.length} characters
                </span>
              </div>
            </div>

            <div style={{
              padding: '14px 16px',
              background: 'var(--blue-bg)',
              border: '1px solid var(--blue-border)',
              borderRadius: 'var(--r2)',
              fontSize: '12.5px',
              color: 'var(--blue)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <path d="M12 2a6 6 0 0 0-6 6c0 2.2 1.2 3.8 2 5 .8 1.2 1 2 1 3h6c0-1 .2-1.8 1-3 .8-1.2 2-2.8 2-5a6 6 0 0 0-6-6z"/>
                <path d="M9 18h6"/>
                <path d="M10 21h4"/>
              </svg>
              <span>This narrative feeds directly into the <strong>Bharatiya Nyaya Sanhita (BNS) AI legal classifier</strong> and <strong>Evidence integrity graph</strong>.</span>
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{
              padding: '20px',
              background: 'var(--bg3)',
              borderRadius: 'var(--r2)',
              border: '1px solid var(--border)'
            }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text)', marginBottom: '14px' }}>
                Case Summary
              </div>
              {[
                ['Investigation Title', title],
                ['Offence Classification', offenceType === 'Other' ? offenceCustom : offenceType],
                ['Incident Timeline', [incidentDate, incidentTime].filter(Boolean).join(' at ') || '—'],
                ['Incident Location', incidentLocation || '—'],
                ['Complainant', complainant],
                ['Victims Listed', victims.filter((v) => v.name).map((v) => v.name).join(', ') || '—'],
                ['Suspects Listed', suspects.filter((s) => s.name).map((s) => s.name).join(', ') || '—'],
                ['Narrative Word Count', `${firText.split(/\s+/).filter(Boolean).length} words (${firText.length} chars)`],
                ['Language Mode', firLanguage === 'auto' ? 'Auto Detect' : firLanguage.toUpperCase()]
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '12.5px', color: 'var(--text3)', fontWeight: 500 }}>{k}</span>
                  <span style={{ fontSize: '12.5px', color: 'var(--text)', fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>

            <div style={{
              padding: '12px 16px',
              background: 'var(--amber-bg)',
              border: '1px solid var(--amber-border)',
              borderRadius: 'var(--r)',
              fontSize: '12px',
              color: 'var(--amber)',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <path d="M12 3v18"/>
                <path d="M6 8l-4 6h8l-4-6z"/>
                <path d="M18 8l-4 6h8l-4-6z"/>
                <path d="M3 8h18"/>
              </svg>
              <span>Upon creation, this case will be recorded with an immutable SHA-256 genesis hash and logged to the central audit ledger.</span>
            </div>
          </div>
        )}

        {/* Step 5: Success */}
        {step === 5 && (
          <div style={{ textAlign: 'center', padding: '32px 16px' }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'var(--green-bg)',
              border: '2px solid var(--green)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
              fontSize: '28px',
              color: 'var(--green)',
              boxShadow: '0 0 20px rgba(16, 185, 129, 0.25)'
            }}>
              ✓
            </div>
            <h3 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text)', marginBottom: '8px' }}>
              Investigation Created
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text3)', maxWidth: '440px', margin: '0 auto 28px' }}>
              Case has been officially indexed in PostgreSQL and timestamped in the security audit trail.
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Btn variant="primary" size="lg" onClick={() => navigate(`/cases/${createdCaseId}`)}>
                Open Case
              </Btn>
              <Btn size="lg" variant="default" onClick={() => navigate('/evidence')}>
                Upload Evidence Files
              </Btn>
              <Btn size="lg" variant="ghost" onClick={() => navigate('/dashboard')}>
                Return to Dashboard
              </Btn>
            </div>
          </div>
        )}

        {/* Wizard Action Footer */}
        {step < 5 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '28px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
            {step > 1 ? (
              <Btn size="md" variant="default" onClick={() => { setError(''); setStep((s) => s - 1) }}>
                ← Back
              </Btn>
            ) : (
              <Btn size="md" variant="ghost" onClick={() => navigate('/cases')}>
                Cancel
              </Btn>
            )}

            {step < 4 ? (
              <Btn variant="primary" size="md" onClick={nextStep}>
                Continue Step →
              </Btn>
            ) : (
              <Btn variant="primary" size="lg" loading={loading} onClick={submit}>
                Register & Sign Case
              </Btn>
            )}
          </div>
        )}
      </Card>
    </AppShell>
  )
}
