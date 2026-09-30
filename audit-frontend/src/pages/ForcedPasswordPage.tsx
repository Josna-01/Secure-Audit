import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'
import { Btn, AlertBox } from '../components/UI'

export default function ForcedPasswordPage() {
  const navigate = useNavigate()
  const { user, updateUser, logout } = useAuth()

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await api.changePassword(password)
      if (user) {
        updateUser({ ...user, must_change_password: false })
      }
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update password. Please try again.')
    } finally {
      setLoading(false)
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

      {/* Floating Header */}
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
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
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

      {/* Main Form Card */}
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
        <form onSubmit={handleSubmit}>
          {/* Badge */}
          <div style={{ marginBottom: '10px', display: 'flex' }}>
            <span style={{
              background: 'var(--red-bg)',
              border: '1px solid var(--red)',
              color: 'var(--red)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '9px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              fontFamily: 'var(--mono)'
            }}>First Sign In Required Action</span>
          </div>

          <h2 style={{
            fontSize: '20px',
            fontWeight: 700,
            color: 'var(--text)',
            marginBottom: '6px',
            letterSpacing: '-0.2px'
          }}>Update Temporary Password</h2>

          <p style={{
            fontSize: '13px',
            color: 'var(--text2)',
            marginBottom: '24px'
          }}>For security compliance, you must choose a personal password to activate your credentials.</p>

          {error && <div style={{ marginBottom: '18px' }}><AlertBox type="error">{error}</AlertBox></div>}

          {/* New Password input */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{
              fontSize: '11px',
              color: 'var(--text2)',
              fontWeight: 600,
              display: 'block',
              marginBottom: '6px',
              textTransform: 'uppercase',
              letterSpacing: '0.4px'
            }}>New Passphrase</label>
            <input
              type="password"
              required
              minLength={8}
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '10px 12px',
                fontSize: '13px',
                color: 'var(--text)',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            />
          </div>

          {/* Confirm Password input */}
          <div style={{ marginBottom: '28px' }}>
            <label style={{
              fontSize: '11px',
              color: 'var(--text2)',
              fontWeight: 600,
              display: 'block',
              marginBottom: '6px',
              textTransform: 'uppercase',
              letterSpacing: '0.4px'
            }}>Confirm Passphrase</label>
            <input
              type="password"
              required
              minLength={8}
              placeholder="Confirm new passphrase"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg3)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--r)',
                padding: '10px 12px',
                fontSize: '13px',
                color: 'var(--text)',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
            />
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <Btn
              type="submit"
              variant="primary"
              full
              loading={loading}
              style={{ padding: '12px 20px', fontSize: '13px' }}
            >
              Update Passphrase & Continue
            </Btn>

            <Btn
              type="button"
              variant="default"
              full
              onClick={() => logout()}
              style={{ padding: '10px 20px', fontSize: '12px', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text2)' }}
            >
              Cancel & Sign Out
            </Btn>
          </div>
        </form>
      </div>

      <div style={{
        fontSize: '11px',
        color: 'var(--text3)',
        fontFamily: 'var(--mono)',
        textAlign: 'center',
        zIndex: 5
      }}>
        © 2026 Secure Audits. Security Compliance Enforcement.
      </div>
    </div>
  )
}
