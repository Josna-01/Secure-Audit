import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'
import { Btn, AlertBox } from '../components/UI'
import type { User } from '../types'

export default function AuthPage() {
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard')
    }
  }, [isAuthenticated, navigate])

  // Form states
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('Investigator')
  const [password, setPassword] = useState('')
  const [tokenInput, setTokenInput] = useState('')
  
  // Transition states
  const [tokenSent, setTokenSent] = useState(false)
  const [tokenLoading, setTokenLoading] = useState(false)
  const [signInLoading, setSignInLoading] = useState(false)
  
  // Reset password states
  const [isResetMode, setIsResetMode] = useState(false)
  const [resetLoading, setResetLoading] = useState(false)
  const [newPasswordInput, setNewPasswordInput] = useState('')

  // UI states
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const handleGetToken = async (e: React.MouseEvent) => {
    e.preventDefault()
    setError('')
    setSuccessMsg('')
    
    if (!email) {
      setError('Official email or Officer ID is required to request a token.')
      return
    }
    
    setTokenLoading(true)
    try {
      const res = await api.sendOTP(email)
      setTokenSent(true)
      setSuccessMsg(res.message || 'Verification token sent successfully. Please check your inbox.')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send token. Please check email address.')
    } finally {
      setTokenLoading(false)
    }
  }


  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccessMsg('')

    if (!email) {
      setError('Official email is required.')
      return
    }
    if (!tokenInput) {
      setError('Verification token is required.')
      return
    }
    if (!newPasswordInput || newPasswordInput.length < 6) {
      setError('New passphrase must be at least 6 characters long.')
      return
    }

    setResetLoading(true)
    try {
      const res = await api.resetPassword(email, tokenInput, newPasswordInput)
      setSuccessMsg('Passphrase reset successfully! Click "Get Token" to receive a fresh access token for sign-in.')
      setIsResetMode(false)
      setPassword(newPasswordInput)
      setNewPasswordInput('')
      setTokenSent(false)
      setTokenInput('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset passphrase. Check your email and verification token.')
    } finally {
      setResetLoading(false)
    }
  }

  const handleSecureSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!email) {
      setError('Official email or Officer ID is required.')
      return
    }
    if (!password) {
      setError('Security passphrase is required.')
      return
    }
    if (!tokenInput) {
      setError('Access token is required.')
      return
    }
    
    setSignInLoading(true)
    try {
      const res = await api.verifyOTP(email, tokenInput, password)
      
      // Save session start time
      localStorage.setItem('sa_session_start', new Date().toISOString())

      // Login context update
      login(res.data.token, {
        ...res.data.user,
        role: role
      } as User)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed. Please verify credentials and role.')
    } finally {
      setSignInLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#080c10',
      color: 'var(--text)',
      fontFamily: 'var(--font)',
      padding: '40px 20px',
      position: 'relative',
      overflowX: 'hidden'
    }}>
      
      {/* Background grid accent */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: 'radial-gradient(var(--border) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
        opacity: 0.15,
        pointerEvents: 'none'
      }} />

      {/* Floating Logo & Header Above Card */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        marginBottom: '28px',
        textAlign: 'center',
        zIndex: 5
      }}>
        <div style={{
          width: '48px',
          height: '48px',
          background: 'var(--blue-bg)',
          border: '1.5px solid var(--blue)',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--blue)',
          marginBottom: '10px',
          boxShadow: '0 0 15px rgba(77, 132, 245, 0.2)'
        }}>
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <h1 style={{
          fontSize: '24px',
          fontWeight: 700,
          letterSpacing: '0.8px',
          color: 'var(--text)',
          margin: 0
        }}>SECURE AUDITS</h1>
        <div style={{
          fontSize: '10px',
          fontWeight: 600,
          color: 'var(--text2)',
          textTransform: 'uppercase',
          letterSpacing: '1.5px',
          marginTop: '4px'
        }}>DIGITAL EVIDENCE & INVESTIGATION SYSTEM</div>
      </div>

      {/* Centered Login Card */}
      <div style={{
        width: '460px',
        maxWidth: '100%',
        background: '#161b27',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r3)',
        padding: '36px 40px',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
        backdropFilter: 'blur(10px)',
        position: 'relative',
        zIndex: 5,
        marginBottom: '32px'
      }}>
        <form onSubmit={isResetMode ? handleResetPassword : handleSecureSignIn}>
          
          {/* Badge text */}
          <div style={{ marginBottom: '10px', display: 'flex' }}>
            <span style={{
              background: isResetMode ? 'rgba(245,158,11,0.1)' : 'var(--blue-bg)',
              border: `1px solid ${isResetMode ? '#f59e0b' : 'var(--blue)'}`,
              color: isResetMode ? '#f59e0b' : 'var(--blue)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '9px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              fontFamily: 'var(--mono)'
            }}>{isResetMode ? 'RESET PASSPHRASE' : 'SYSTEM SIGN IN'}</span>
          </div>

          <h2 style={{
            fontSize: '20px',
            fontWeight: 700,
            color: 'var(--text)',
            marginBottom: '6px',
            letterSpacing: '-0.2px'
          }}>{isResetMode ? 'Reset Your Passphrase' : 'Authorized Access Portal'}</h2>
          
          <p style={{
            fontSize: '13px',
            color: 'var(--text2)',
            marginBottom: '24px'
          }}>{isResetMode ? 'Enter your email, get a token, then set a new passphrase.' : 'Provide official credentials to authenticate.'}</p>

          {/* Feedback Alerts */}
          {error && <div style={{ marginBottom: '18px' }}><AlertBox type="error">{error}</AlertBox></div>}
          {successMsg && <div style={{ marginBottom: '18px' }}><AlertBox type="success">{successMsg}</AlertBox></div>}

          {/* Email input field */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label style={{
                fontSize: '11px',
                color: 'var(--text2)',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.4px'
              }}>OFFICIAL EMAIL / OFFICER ID</label>
              {tokenSent && (
                <span
                  onClick={() => {
                    setTokenSent(false)
                    setPassword('')
                    setTokenInput('')
                    setSuccessMsg('')
                    setError('')
                  }}
                  style={{
                    fontSize: '11px',
                    color: 'var(--blue)',
                    cursor: 'pointer',
                    fontWeight: 600,
                    userSelect: 'none'
                  }}
                >
                  Change Email
                </span>
              )}
            </div>
            <input
              type="email"
              required
              disabled={tokenSent}
              autoComplete="username"
              placeholder="inspector.sharma@ksp.gov.in"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(''); setSuccessMsg('') }}
              style={{
                width: '100%',
                background: tokenSent ? 'var(--bg4)' : 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '10px 12px',
                fontSize: '13px',
                color: tokenSent ? 'var(--text3)' : 'var(--text)',
                outline: 'none',
                transition: 'border-color 0.2s',
                cursor: tokenSent ? 'not-allowed' : 'text'
              }}
              onFocus={(e) => !tokenSent && (e.target.style.borderColor = 'var(--blue)')}
              onBlur={(e) => !tokenSent && (e.target.style.borderColor = 'var(--border)')}
            />
          </div>

          {isResetMode ? (
            <>
              {/* --- RESET MODE --- */}
              <Btn type="button" variant="default" full onClick={handleGetToken} loading={tokenLoading}
                style={{ padding: '11px 20px', fontSize: '13px', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', background: 'var(--bg4)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--r)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px' }}
              >Send Reset Token to Email</Btn>
              <p style={{ fontSize: '11px', color: 'var(--text3)', marginBottom: '20px', textAlign: 'center' }}>Token sent to your email. Valid for 5 minutes.</p>

              <div style={{ marginBottom: '16px', opacity: tokenSent ? 1 : 0.45, pointerEvents: tokenSent ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
                <label style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600, display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>RESET TOKEN (FROM EMAIL)</label>
                <input type="text" disabled={!tokenSent} placeholder="Enter 6-digit token" value={tokenInput}
                  onChange={(e) => { setTokenInput(e.target.value); setError('') }}
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none' }}
                  onFocus={(e) => e.target.style.borderColor = 'var(--blue)'} onBlur={(e) => e.target.style.borderColor = 'var(--border)'} />
              </div>

              <div style={{ marginBottom: '24px', opacity: tokenSent ? 1 : 0.45, pointerEvents: tokenSent ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
                <label style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600, display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>NEW PASSPHRASE</label>
                <input type="password" disabled={!tokenSent} placeholder="Min 6 characters" value={newPasswordInput}
                  onChange={(e) => { setNewPasswordInput(e.target.value); setError('') }}
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none' }}
                  onFocus={(e) => e.target.style.borderColor = '#f59e0b'} onBlur={(e) => e.target.style.borderColor = 'var(--border)'} />
              </div>

              <Btn type="submit" variant="primary" full loading={resetLoading} disabled={!tokenSent}
                style={{ padding: '12px 20px', fontSize: '13px', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', background: tokenSent ? '#f59e0b' : 'rgba(245,158,11,0.3)', border: 'none', color: '#000', borderRadius: 'var(--r)', cursor: tokenSent ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >Reset Passphrase</Btn>
            </>
          ) : (
            <>
              {/* --- SIGN IN MODE --- */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600, display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>SECURITY CLEARANCE ROLE</label>
                <div style={{ position: 'relative' }}>
                  <select value={role} onChange={(e) => setRole(e.target.value)}
                    style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none', cursor: 'pointer', appearance: 'none', backgroundImage: `url("data:image/svg+xml;utf8,<svg fill='gray' height='24' viewBox='0 0 24 24' width='24' xmlns='http://www.w3.org/2000/svg'><path d='M7 10l5 5 5-5z'/><path d='M0 0h24v24H0z' fill='none'/></svg>")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 8px center' }}
                  >
                    <option value="Admin">Admin</option>
                    <option value="lead_investigator">Lead Investigator</option>
                    <option value="Investigator">Investigator</option>
                    <option value="analyst">Forensic Analyst</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
              </div>

              <Btn type="button" variant="default" full onClick={handleGetToken} loading={tokenLoading}
                style={{ padding: '11px 20px', fontSize: '13px', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', background: 'var(--bg4)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--r)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >Get Token</Btn>
              <p style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '8px', marginBottom: '24px', textAlign: 'center' }}>Token will be sent to your registered email. Valid for 5 minutes.</p>

              <div style={{ marginBottom: '16px', opacity: tokenSent ? 1 : 0.45, pointerEvents: tokenSent ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
                <label style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600, display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>SECURITY PASSPHRASE</label>
                <div style={{ position: 'relative' }}>
                  <input type={showPassword ? 'text' : 'password'} disabled={!tokenSent} required={tokenSent} placeholder="Enter security passphrase" value={password}
                    onChange={(e) => { setPassword(e.target.value); setError('') }}
                    style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 60px 10px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none', transition: 'border-color 0.2s' }}
                    onFocus={(e) => e.target.style.borderColor = 'var(--blue)'} onBlur={(e) => e.target.style.borderColor = 'var(--border)'} />
                  <span onClick={() => tokenSent && setShowPassword(!showPassword)} style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', cursor: tokenSent ? 'pointer' : 'default', color: 'var(--blue)', fontSize: '11px', userSelect: 'none', fontWeight: 600 }}>{showPassword ? 'HIDE' : 'SHOW'}</span>
                </div>
              </div>

              <div style={{ marginBottom: '28px', opacity: tokenSent ? 1 : 0.45, pointerEvents: tokenSent ? 'auto' : 'none', transition: 'opacity 0.3s' }}>
                <label style={{ fontSize: '11px', color: 'var(--text2)', fontWeight: 600, display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.4px' }}>ACCESS TOKEN</label>
                <input type="text" disabled={!tokenSent} required={tokenSent} placeholder="Enter access token" value={tokenInput}
                  onChange={(e) => { setTokenInput(e.target.value); setError('') }}
                  style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px', fontSize: '13px', color: 'var(--text)', outline: 'none', transition: 'border-color 0.2s' }}
                  onFocus={(e) => e.target.style.borderColor = 'var(--blue)'} onBlur={(e) => e.target.style.borderColor = 'var(--border)'} />
              </div>

              <Btn type="submit" variant="primary" full loading={signInLoading} disabled={!tokenSent}
                style={{ padding: '12px 20px', fontSize: '13px', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', background: tokenSent ? 'var(--blue)' : 'var(--blue-dim)', border: 'none', color: '#ffffff', borderRadius: 'var(--r)', boxShadow: tokenSent ? '0 4px 12px rgba(77, 132, 245, 0.3)' : 'none', cursor: tokenSent ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                Secure Sign In
              </Btn>
            </>
          )}

        
          <div style={{ marginTop: '16px', textAlign: 'center' }}>
            <span
              onClick={() => {
                setIsResetMode(!isResetMode)
                setError('')
                setSuccessMsg('')
                setTokenSent(false)
                setTokenInput('')
                setNewPasswordInput('')
              }}
              style={{
                fontSize: '12px',
                color: 'var(--blue)',
                cursor: 'pointer',
                fontWeight: 600,
                userSelect: 'none'
              }}
            >
              {isResetMode ? '← Back to Sign In' : 'Forgot Passphrase? Reset via Email Token'}
            </span>
          </div>

        </form>
      </div>

      {/* Footer */}
      <div style={{
        fontSize: '11px',
        color: 'var(--text3)',
        fontFamily: 'var(--mono)',
        textAlign: 'center',
        zIndex: 5
      }}>
        © 2026 Secure Audits. Built for Indian Law Enforcement.
      </div>

    </div>
  )
}
