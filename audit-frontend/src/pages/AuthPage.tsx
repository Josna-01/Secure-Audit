import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'
import { Btn, AlertBox } from '../components/UI'
import type { User } from '../types'

type Step = 'login' | 'otp' | 'register' | 'forgot' | 'pending'

function LogoHeader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px', justifyContent: 'center' }}>
      <div style={{ width: '36px', height: '36px', background: 'var(--blue)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
        <svg width="20" height="20" viewBox="0 0 24 24"><path d="M12 2L3 6v6c0 5.25 3.8 10.15 9 11.5 5.2-1.35 9-6.25 9-11.5V6L12 2z" fill="white"/></svg>
      </div>
      <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text)' }}>Secure Audits</div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--bg2)', border: '1px solid var(--border)',
  borderRadius: 'var(--r3)', padding: '32px', width: '430px', maxWidth: '100%'
}
const flbl: React.CSSProperties = { fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }
const finput: React.CSSProperties = { width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none' }

function PwInput({ id, placeholder, value, onChange }: { id: string; placeholder: string; value: string; onChange: (v: string) => void }) {
  const [show, setShow] = useState(false)
  return (
    <div style={{ position: 'relative' }}>
      <input id={id} type={show ? 'text' : 'password'} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ ...finput, paddingRight: '36px' }} />
      <span onClick={() => setShow((s) => !s)} style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--text3)', fontSize: '12px', userSelect: 'none' }}>
        {show ? 'Hide' : 'Show'}
      </span>
    </div>
  )
}

function PwStrength({ value }: { value: string }) {
  let score = 0
  if (value.length >= 8) score++
  if (/[A-Z]/.test(value)) score++
  if (/[0-9]/.test(value)) score++
  if (/[^A-Za-z0-9]/.test(value)) score++
  const colors = ['', 'var(--red)', 'var(--amber)', 'var(--amber)', 'var(--green)']
  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong']
  if (!value) return null
  return (
    <div style={{ marginTop: '4px' }}>
      <div style={{ height: '3px', borderRadius: '2px', background: 'var(--bg4)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score * 25}%`, background: colors[score], transition: 'all .3s' }} />
      </div>
      <div style={{ fontSize: '10px', color: colors[score], marginTop: '2px' }}>{labels[score]}</div>
    </div>
  )
}

export default function AuthPage() {
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuth()
  
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard')
    }
  }, [isAuthenticated, navigate])

  const [step, setStep] = useState<Step>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [regPw, setRegPw] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [otpSeconds, setOtpSeconds] = useState(120)
  const [resendSeconds, setResendSeconds] = useState(30)
  const otpRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (step !== 'otp') return
    const iv = setInterval(() => setOtpSeconds((s) => Math.max(0, s - 1)), 1000)
    const rv = setInterval(() => setResendSeconds((s) => Math.max(0, s - 1)), 1000)
    return () => { clearInterval(iv); clearInterval(rv) }
  }, [step])

  useEffect(() => { if (step === 'otp') setTimeout(() => otpRefs.current[0]?.focus(), 100) }, [step])

  const fmtTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const handleOtpInput = (i: number, val: string) => {
    const clean = val.replace(/\D/g, '').slice(0, 1)
    const next = [...otp]; next[i] = clean; setOtp(next)
    if (clean && i < 5) otpRefs.current[i + 1]?.focus()
  }

  const handleOtpKeyDown = (i: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[i] && i > 0) { otpRefs.current[i - 1]?.focus() }
  }

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    const arr = text.split('')
    setOtp(arr.concat(Array(6 - arr.length).fill('')))
  }

  const doSendOTP = async () => {
    setError('')
    if (!email) { setError('Please enter your official email.'); return }
    if (!email.includes('@')) { setError('Invalid email format.'); return }
    if (!password) { setError('Please enter your password.'); return }
    setLoading(true)
    try {
      await api.sendOTP(email, password)
      setOtpSeconds(120); setResendSeconds(30)
      setStep('otp')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Failed to send OTP. Check your credentials.')
    } finally { setLoading(false) }
  }

  const doVerifyOTP = async () => {
    const code = otp.join('')
    if (code.length < 6) { setError('Enter all 6 digits.'); return }
    setLoading(true); setError('')
    try {
      const res = await api.verifyOTP(email, code)
      login(res.data.token as string, res.data.user as User)
      navigate('/dashboard')
    } catch {
      setError('Invalid OTP. Please try again.')
    } finally { setLoading(false) }
  }

  const doRegister = async () => {
    const name = (document.getElementById('reg-name') as HTMLInputElement)?.value
    const badge = (document.getElementById('reg-badge') as HTMLInputElement)?.value
    const regEmail = (document.getElementById('reg-email') as HTMLInputElement)?.value
    const dept = (document.getElementById('reg-dept') as HTMLInputElement)?.value
    if (!name || !badge || !regEmail || !dept || !regPw) { setError('All fields are required.'); return }
    setLoading(true); setError('')
    try {
      await api.register({ name, badge_id: badge, email: regEmail, department: dept, password: regPw })
      setStep('pending')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Registration failed.')
    } finally { setLoading(false) }
  }

  const doForgot = async () => {
    const fEmail = (document.getElementById('forgot-email') as HTMLInputElement)?.value
    if (!fEmail) { setError('Enter your email.'); return }
    setLoading(true); setError('')
    try {
      await api.forgotPassword(fEmail)
      setEmail(fEmail)
      setSuccess('OTP sent to ' + fEmail + '. Redirecting...')
      setTimeout(() => { setSuccess(''); setOtpSeconds(120); setResendSeconds(30); setStep('otp') }, 1500)
    } catch {
      setError('Email not found.')
    } finally { setLoading(false) }
  }

  const authLink: React.CSSProperties = { color: 'var(--blue)', cursor: 'pointer', fontSize: '12px' }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg)', padding: '20px' }}>
      <div style={cardStyle}>
        <LogoHeader />

        {step === 'login' && (
          <>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px', textAlign: 'center' }}>Welcome Back</div>
            <div style={{ fontSize: '13px', color: 'var(--text3)', textAlign: 'center', marginBottom: '6px' }}>Sign in to your investigator account</div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '11px', color: 'var(--text3)', marginBottom: '20px' }}>
              <span>[Lock] Secure Authentication</span><span>·</span><span>[*] Authorized Personnel Only</span>
            </div>
            {error && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{error}</AlertBox></div>}
            <div style={{ marginBottom: '12px' }}>
              <label style={flbl}>Official Email</label>
              <input style={finput} type="email" placeholder="name@cid.gov.in" value={email} onChange={(e) => { setEmail(e.target.value); setError('') }} />
              <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '3px' }}>Only official department email addresses accepted</div>
            </div>
            <div style={{ marginBottom: '18px' }}>
              <label style={flbl}>Password</label>
              <PwInput id="login-pass" placeholder="Enter your password" value={password} onChange={(v) => { setPassword(v); setError('') }} />
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text3)', marginBottom: '8px', textAlign: 'center' }}>Step 1 of 2 — Enter credentials · Step 2 — Verify OTP</div>
            <Btn variant="primary" full loading={loading} onClick={doSendOTP} style={{ marginBottom: '12px' }}>Send OTP</Btn>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={authLink} onClick={() => { setError(''); setStep('forgot') }}>Forgot password?</span>
              <span style={authLink} onClick={() => { setError(''); setStep('register') }}>Register account</span>
            </div>
          </>
        )}

        {step === 'otp' && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '20px' }}>
              {[0, 1].map((i) => <div key={i} style={{ width: i === 1 ? '20px' : '8px', height: '8px', borderRadius: i === 1 ? '4px' : '50%', background: i === 0 ? 'var(--green)' : 'var(--blue)' }} />)}
            </div>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px', textAlign: 'center' }}>Verify OTP</div>
            <div style={{ fontSize: '13px', color: 'var(--text3)', textAlign: 'center', marginBottom: '20px' }}>
              6-digit code sent to <strong style={{ color: 'var(--text)' }}>{email.replace(/(.{2})(.*)(@.*)/, (_, a, b, c) => a + b.replace(/./g, '*') + c)}</strong>
            </div>
            {error && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{error}</AlertBox></div>}
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', margin: '16px 0' }} onPaste={handleOtpPaste}>
              {otp.map((v, i) => (
                <input
                  key={i}
                  ref={(el) => { otpRefs.current[i] = el }}
                  value={v}
                  maxLength={1}
                  inputMode="numeric"
                  onChange={(e) => handleOtpInput(i, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(i, e)}
                  style={{ width: '46px', height: '52px', background: 'var(--bg3)', border: `1px solid ${error ? 'var(--red)' : 'var(--border)'}`, borderRadius: 'var(--r)', fontSize: '22px', fontWeight: 600, textAlign: 'center', color: 'var(--text)', fontFamily: 'var(--mono)', outline: 'none' }}
                />
              ))}
            </div>
            <div style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text3)', marginBottom: '8px' }}>
              OTP expires in <span style={{ fontFamily: 'var(--mono)', color: otpSeconds < 30 ? 'var(--red)' : 'var(--amber)', fontWeight: 600 }}>{fmtTime(otpSeconds)}</span>
            </div>
            <Btn variant="primary" full loading={loading} onClick={doVerifyOTP} style={{ marginBottom: '12px' }}>Verify &amp; Login</Btn>
            <div style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text3)', marginBottom: '10px' }}>
              Didn't receive?{' '}
              <span style={{ ...authLink, opacity: resendSeconds > 0 ? 0.4 : 1, pointerEvents: resendSeconds > 0 ? 'none' : 'auto' }}
                onClick={() => { setOtpSeconds(120); setResendSeconds(30); api.sendOTP(email, password).catch(() => {}) }}>
                {resendSeconds > 0 ? `Resend OTP (${resendSeconds}s)` : 'Resend OTP'}
              </span>
            </div>
            <div style={{ textAlign: 'center' }}><span style={authLink} onClick={() => { setError(''); setStep('login') }}>Back to Login</span></div>
          </>
        )}

        {step === 'register' && (
          <>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px', textAlign: 'center' }}>Create Account</div>
            <div style={{ fontSize: '13px', color: 'var(--text3)', textAlign: 'center', marginBottom: '12px' }}>Register your investigator account</div>
            <div style={{ fontSize: '11px', color: 'var(--text3)', background: 'var(--bg3)', borderRadius: 'var(--r)', padding: '8px 12px', marginBottom: '16px' }}>
              Your account will be reviewed by an admin before access is granted. Estimated: 24-48 hours.
            </div>
            {error && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{error}</AlertBox></div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div><label style={flbl}>Full Name</label><input id="reg-name" style={finput} placeholder="Your full name" /></div>
              <div><label style={flbl}>Badge / ID</label><input id="reg-badge" style={finput} placeholder="CID-1234" /><div style={{ fontSize: '9px', color: 'var(--text3)', marginTop: '2px' }}>Format: CID-XXXX</div></div>
            </div>
            <div style={{ marginBottom: '12px' }}><label style={flbl}>Official Email</label><input id="reg-email" style={finput} type="email" placeholder="name@cid.gov.in" /></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div><label style={flbl}>Department</label><input id="reg-dept" style={finput} placeholder="e.g. CID, SIT" /></div>
              <div><label style={flbl}>Phone (Optional)</label><input style={finput} type="tel" placeholder="+91 XXXXX XXXXX" /></div>
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={flbl}>Password</label>
              <PwInput id="reg-pass" placeholder="Create a strong password" value={regPw} onChange={setRegPw} />
              <PwStrength value={regPw} />
            </div>
            <Btn variant="primary" full loading={loading} onClick={doRegister} style={{ marginBottom: '12px' }}>Submit for Admin Approval</Btn>
            <div style={{ textAlign: 'center' }}><span style={authLink} onClick={() => { setError(''); setStep('login') }}>Back to Login</span></div>
          </>
        )}

        {step === 'forgot' && (
          <>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px', textAlign: 'center' }}>Reset Password</div>
            <div style={{ fontSize: '13px', color: 'var(--text3)', textAlign: 'center', marginBottom: '20px' }}>Enter your official email to receive a reset OTP</div>
            {error && <div style={{ marginBottom: '12px' }}><AlertBox type="error">{error}</AlertBox></div>}
            {success && <div style={{ marginBottom: '12px' }}><AlertBox type="success">{success}</AlertBox></div>}
            <div style={{ marginBottom: '16px' }}><label style={flbl}>Official Email</label><input id="forgot-email" style={finput} type="email" placeholder="name@cid.gov.in" /></div>
            <Btn variant="primary" full loading={loading} onClick={doForgot} style={{ marginBottom: '8px' }}>Send Reset OTP</Btn>
            <div style={{ fontSize: '11px', color: 'var(--text3)', textAlign: 'center', marginBottom: '10px' }}>You will be redirected to OTP verification</div>
            <div style={{ textAlign: 'center' }}><span style={authLink} onClick={() => { setError(''); setStep('login') }}>Back to Login</span></div>
          </>
        )}

        {step === 'pending' && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>[Clock]</div>
            <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' }}>Pending Admin Approval</div>
            <div style={{ fontSize: '12px', color: 'var(--text2)', background: 'var(--bg3)', borderRadius: 'var(--r)', padding: '12px', marginBottom: '16px' }}>
              You will receive an email once approved.<br />
              <span style={{ color: 'var(--text3)', fontSize: '11px' }}>Estimated approval time: 24-48 hours</span>
            </div>
            <Btn full onClick={() => setStep('login')}>Back to Login</Btn>
          </div>
        )}
      </div>
    </div>
  )
}
