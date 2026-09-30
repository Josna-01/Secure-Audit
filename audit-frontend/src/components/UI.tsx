import React from 'react'

// ── BUTTON ────────────────────────────────────────────────────────────────
interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'danger' | 'green' | 'ghost' | 'outline'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  full?: boolean
  loading?: boolean
}

const btnBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '7px',
  borderRadius: 'var(--r)',
  border: '1px solid transparent',
  fontFamily: 'var(--font)',
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
  userSelect: 'none',
  outline: 'none',
  lineHeight: 1.2,
  whiteSpace: 'nowrap'
}

const btnSizes = {
  xs: { padding: '4px 10px', fontSize: '11px', borderRadius: '6px' },
  sm: { padding: '6px 13px', fontSize: '12px', borderRadius: '8px' },
  md: { padding: '8px 16px', fontSize: '13px', borderRadius: '8px' },
  lg: { padding: '10px 20px', fontSize: '14px', borderRadius: '10px' }
}

const btnVariants = {
  default: {
    background: 'var(--bg3)',
    borderColor: 'var(--border)',
    color: 'var(--text)',
    boxShadow: 'var(--shadow-xs)'
  },
  primary: {
    background: 'var(--blue)',
    borderColor: 'var(--blue-hover)',
    color: '#ffffff',
    boxShadow: '0 2px 8px rgba(37, 99, 235, 0.28)'
  },
  danger: {
    background: 'var(--red)',
    borderColor: 'var(--red-hover)',
    color: '#ffffff',
    boxShadow: '0 2px 8px rgba(220, 38, 38, 0.25)'
  },
  green: {
    background: 'var(--green)',
    borderColor: 'var(--green-hover)',
    color: '#ffffff',
    boxShadow: '0 2px 8px rgba(16, 185, 129, 0.25)'
  },
  ghost: {
    background: 'transparent',
    borderColor: 'transparent',
    color: 'var(--text2)'
  },
  outline: {
    background: 'transparent',
    borderColor: 'var(--border2)',
    color: 'var(--text)'
  }
}

export function Btn({ variant = 'default', size = 'md', full, loading, children, style, disabled, ...rest }: BtnProps) {
  const [hovered, setHovered] = React.useState(false)
  const [active, setActive] = React.useState(false)

  const getHoverStyle = (): React.CSSProperties => {
    if (disabled || loading) return {}
    if (variant === 'primary') return { background: 'var(--blue-hover)', transform: hovered ? 'translateY(-1px)' : 'none' }
    if (variant === 'danger') return { background: 'var(--red-hover)', transform: hovered ? 'translateY(-1px)' : 'none' }
    if (variant === 'green') return { background: 'var(--green-hover)', transform: hovered ? 'translateY(-1px)' : 'none' }
    if (variant === 'ghost') return { background: 'var(--bg3)', color: 'var(--text)' }
    if (variant === 'outline') return { borderColor: 'var(--blue)', color: 'var(--blue)', background: 'var(--blue-bg)' }
    return { background: 'var(--bg4)', borderColor: 'var(--border2)', color: 'var(--text)', transform: hovered ? 'translateY(-1px)' : 'none' }
  }

  return (
    <button
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setActive(false) }}
      onMouseDown={() => setActive(true)}
      onMouseUp={() => setActive(false)}
      style={{
        ...btnBase,
        ...btnSizes[size],
        ...btnVariants[variant],
        ...getHoverStyle(),
        ...(active && !disabled ? { transform: 'scale(0.98)' } : {}),
        ...(full ? { width: '100%', justifyContent: 'center' } : {}),
        ...(disabled || loading ? { opacity: 0.5, cursor: 'not-allowed', pointerEvents: 'none' } : {}),
        ...style
      }}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner size={13} />}
      {loading ? 'Processing...' : children}
    </button>
  )
}

// ── CARD ─────────────────────────────────────────────────────────────────
export function Card({ children, style, hoverable }: { children: React.ReactNode; style?: React.CSSProperties; hoverable?: boolean }) {
  const [hover, setHover] = React.useState(false)
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: 'var(--bg2)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r3)',
        padding: '20px',
        boxShadow: hover && hoverable ? 'var(--shadow-lg)' : 'var(--shadow-sm)',
        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        transform: hover && hoverable ? 'translateY(-2px)' : 'none',
        ...style
      }}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children, subtitle }: { children: React.ReactNode; subtitle?: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{
        fontSize: '11px',
        fontWeight: 700,
        color: 'var(--text3)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        display: 'flex',
        alignItems: 'center',
        gap: '6px'
      }}>
        {children}
      </div>
      {subtitle && <div style={{ fontSize: '12px', color: 'var(--text2)', marginTop: '2px', fontWeight: 400 }}>{subtitle}</div>}
    </div>
  )
}

export function CardHeader({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', gap: '12px', ...style }}>
      {children}
    </div>
  )
}

// ── BADGE ─────────────────────────────────────────────────────────────────
const badgeMap: Record<string, { bg: string; color: string; border: string }> = {
  Active: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  Inactive: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  Open: { bg: 'var(--blue-bg)', color: 'var(--blue)', border: 'var(--blue-border)' },
  Pending: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Critical: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  Closed: { bg: 'var(--bg4)', color: 'var(--text3)', border: 'var(--border2)' },
  Verified: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  Tampered: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  Processing: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Unregistered: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Missing: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  'Verification Failed': { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Registered: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  'Not registered': { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Consistent: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  Inconsistent: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  Warning: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  SUCCESS: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  FAILED: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  PENDING: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Live: { bg: 'var(--green-bg)', color: 'var(--green)', border: 'var(--green-border)' },
  'Planned v2': { bg: 'var(--bg4)', color: 'var(--text3)', border: 'var(--border2)' },
  High: { bg: 'var(--red-bg)', color: 'var(--red)', border: 'var(--red-border)' },
  Medium: { bg: 'var(--amber-bg)', color: 'var(--amber)', border: 'var(--amber-border)' },
  Low: { bg: 'var(--blue-bg)', color: 'var(--blue)', border: 'var(--blue-border)' }
}

export function Badge({ label }: { label: string }) {
  const colors = badgeMap[label] || { bg: 'var(--bg4)', color: 'var(--text2)', border: 'var(--border2)' }
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      fontSize: '11px',
      padding: '3px 10px',
      borderRadius: 'var(--r-pill)',
      fontWeight: 600,
      whiteSpace: 'nowrap',
      background: colors.bg,
      color: colors.color,
      border: `1px solid ${colors.border}`,
      lineHeight: 1.2
    }}>
      <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: colors.color }} />
      {label}
    </span>
  )
}

// ── INPUT ─────────────────────────────────────────────────────────────────
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: string
  error?: string
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'var(--bg3)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--r)',
  padding: '8px 12px',
  fontSize: '13.5px',
  color: 'var(--text)',
  fontFamily: 'var(--font)',
  outline: 'none',
  transition: 'border-color 0.15s, box-shadow 0.15s, background 0.15s'
}

export function Input({ label, hint, error, style, ...rest }: InputProps) {
  return (
    <div style={{ width: '100%' }}>
      {label && (
        <label style={{
          fontSize: '11.5px',
          fontWeight: 600,
          color: 'var(--text2)',
          display: 'block',
          marginBottom: '5px',
          letterSpacing: '0.01em'
        }}>
          {label}
        </label>
      )}
      <input
        style={{
          ...inputStyle,
          ...(error ? { borderColor: 'var(--red)' } : {}),
          ...style
        }}
        {...rest}
      />
      {hint && !error && <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '4px' }}>{hint}</div>}
      {error && <div style={{ fontSize: '11px', color: 'var(--red)', marginTop: '4px', fontWeight: 500 }}>{error}</div>}
    </div>
  )
}

// ── SELECT ────────────────────────────────────────────────────────────────
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options: { value: string; label: string }[]
}

export function Select({ label, options, style, ...rest }: SelectProps) {
  return (
    <div style={{ width: '100%' }}>
      {label && (
        <label style={{
          fontSize: '11.5px',
          fontWeight: 600,
          color: 'var(--text2)',
          display: 'block',
          marginBottom: '5px',
          letterSpacing: '0.01em'
        }}>
          {label}
        </label>
      )}
      <select
        style={{
          ...inputStyle,
          appearance: 'auto',
          cursor: 'pointer',
          ...style
        }}
        {...rest}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

// ── TEXTAREA ──────────────────────────────────────────────────────────────
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  hint?: string
}

export function Textarea({ label, hint, style, ...rest }: TextareaProps) {
  return (
    <div style={{ width: '100%' }}>
      {label && (
        <label style={{
          fontSize: '11.5px',
          fontWeight: 600,
          color: 'var(--text2)',
          display: 'block',
          marginBottom: '5px',
          letterSpacing: '0.01em'
        }}>
          {label}
        </label>
      )}
      <textarea
        style={{
          ...inputStyle,
          resize: 'vertical',
          lineHeight: '1.6',
          minHeight: '80px',
          ...style
        }}
        {...rest}
      />
      {hint && <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '4px' }}>{hint}</div>}
    </div>
  )
}

// ── PROGRESS BAR ──────────────────────────────────────────────────────────
export function ProgressBar({ value, color = 'var(--blue)', height = 6 }: { value: number; color?: string; height?: number }) {
  return (
    <div style={{ background: 'var(--bg4)', borderRadius: 'var(--r-pill)', overflow: 'hidden', height, width: '100%' }}>
      <div
        style={{
          height: '100%',
          borderRadius: 'var(--r-pill)',
          background: color,
          width: `${Math.min(100, Math.max(0, value))}%`,
          transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)'
        }}
      />
    </div>
  )
}

// ── SPINNER ───────────────────────────────────────────────────────────────
export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: '50%',
      border: '2px solid var(--border2)',
      borderTopColor: 'var(--blue)',
      animation: 'spin 0.75s linear infinite',
      flexShrink: 0
    }} />
  )
}

// ── UPLOAD ZONE ───────────────────────────────────────────────────────────
export function UploadZone({ title, sub, onClick, onDropFile }: { title: string; sub: string; onClick?: () => void; onDropFile?: (file: File) => void }) {
  const [hover, setHover] = React.useState(false)
  const [isDragging, setIsDragging] = React.useState(false)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (onDropFile) {
        onDropFile(e.dataTransfer.files[0])
      }
    }
  }

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${isDragging ? 'var(--blue)' : hover ? 'var(--blue)' : 'var(--border2)'}`,
        borderRadius: 'var(--r3)',
        padding: '36px 24px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        marginBottom: '16px',
        background: isDragging ? 'var(--blue-bg)' : hover ? 'var(--blue-bg)' : 'var(--bg2)',
        boxShadow: hover ? 'var(--shadow-md)' : 'none'
      }}
    >
      <div style={{
        width: '44px',
        height: '44px',
        borderRadius: '50%',
        background: 'var(--blue-dim)',
        color: 'var(--blue)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '0 auto 12px auto'
      }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      </div>
      <div style={{ fontSize: '14px', color: 'var(--text)', fontWeight: 600, marginBottom: '4px' }}>
        {isDragging ? 'Drop file to upload immediately' : title}
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text3)' }}>{sub}</div>
    </div>
  )
}

// ── FUTURE NOTICE ─────────────────────────────────────────────────────────
export function FutureNotice({ text }: { text?: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '12px 16px',
      background: 'var(--amber-bg)',
      border: '1px solid var(--amber-border)',
      borderRadius: 'var(--r2)',
      fontSize: '12.5px',
      color: 'var(--amber)',
      marginBottom: '16px',
      fontWeight: 500
    }}>
      <span style={{ fontWeight: 700, padding: '2px 6px', background: 'var(--amber)', color: '#ffffff', borderRadius: '4px', fontSize: '10px' }}>
        PLANNED v2
      </span>
      {text || 'UI shown for stakeholder review and future scope demonstration'}
    </div>
  )
}

// ── HASH CHIP ─────────────────────────────────────────────────────────────
export function HashChip({ hash }: { hash: string }) {
  return (
    <span style={{
      fontFamily: 'var(--mono)',
      fontSize: '11px',
      color: 'var(--blue)',
      background: 'var(--blue-bg)',
      border: '1px solid var(--blue-border)',
      padding: '3px 8px',
      borderRadius: '6px',
      fontWeight: 500
    }}>
      SHA-256: {hash.slice(0, 10)}...{hash.slice(-6)}
    </span>
  )
}

// ── INFO ROW ─────────────────────────────────────────────────────────────
export function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 0',
      borderBottom: '1px solid var(--border)'
    }}>
      <span style={{ fontSize: '12.5px', color: 'var(--text3)', fontWeight: 500 }}>{label}</span>
      <span style={{
        fontSize: '13px',
        fontWeight: 600,
        color: 'var(--text)',
        ...(mono ? { fontFamily: 'var(--mono)', color: 'var(--blue)', fontSize: '12px' } : {})
      }}>
        {value}
      </span>
    </div>
  )
}

// ── ALERT BOX ─────────────────────────────────────────────────────────────
export function AlertBox({ type, children }: { type: 'error' | 'success' | 'info' | 'warning'; children: React.ReactNode }) {
  const styles = {
    error: { bg: 'var(--red-bg)', border: 'var(--red-border)', color: 'var(--red)' },
    success: { bg: 'var(--green-bg)', border: 'var(--green-border)', color: 'var(--green)' },
    info: { bg: 'var(--blue-bg)', border: 'var(--blue-border)', color: 'var(--blue)' },
    warning: { bg: 'var(--amber-bg)', border: 'var(--amber-border)', color: 'var(--amber)' }
  }
  const s = styles[type]
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: '10px',
      padding: '12px 16px',
      background: s.bg,
      border: `1px solid ${s.border}`,
      borderRadius: 'var(--r2)',
      fontSize: '13px',
      color: s.color,
      lineHeight: 1.5,
      fontWeight: 500
    }}>
      {children}
    </div>
  )
}

// ── TABS ─────────────────────────────────────────────────────────────────
export function Tabs({ tabs, activeIndex, onChange }: { tabs: string[]; activeIndex: number; onChange: (i: number) => void }) {
  return (
    <div style={{
      display: 'flex',
      borderBottom: '1px solid var(--border)',
      marginBottom: '20px',
      gap: '4px',
      overflowX: 'auto'
    }}>
      {tabs.map((tab, i) => {
        const isActive = activeIndex === i
        return (
          <div
            key={i}
            onClick={() => onChange(i)}
            style={{
              padding: '10px 18px',
              fontSize: '13px',
              fontWeight: isActive ? 600 : 500,
              cursor: 'pointer',
              color: isActive ? 'var(--blue)' : 'var(--text3)',
              borderBottom: `2.5px solid ${isActive ? 'var(--blue)' : 'transparent'}`,
              transition: 'all 0.15s ease',
              whiteSpace: 'nowrap',
              borderRadius: '6px 6px 0 0'
            }}
          >
            {tab}
          </div>
        )
      })}
    </div>
  )
}

// ── STEP WIZARD ───────────────────────────────────────────────────────────
export function StepWizard({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: '28px', overflowX: 'auto', padding: '4px 0' }}>
      {steps.map((label, i) => {
        const num = i + 1
        const isDone = num < current
        const isActive = num === current
        return (
          <React.Fragment key={i}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'var(--text3)', fontWeight: isActive || isDone ? 600 : 500, whiteSpace: 'nowrap' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
                flexShrink: 0,
                border: `2px solid ${isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'var(--border2)'}`,
                background: isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'var(--bg3)',
                color: (isDone || isActive) ? '#ffffff' : 'var(--text3)',
                boxShadow: isActive ? '0 0 10px rgba(37, 99, 235, 0.3)' : 'none'
              }}>
                {isDone ? '✓' : num}
              </div>
              <span>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, minWidth: '24px', height: '2px', background: isDone ? 'var(--green)' : 'var(--border)', margin: '0 12px' }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ── MODAL ─────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer, maxWidth = '560px' }: {
  open: boolean
  onClose: () => void
  title: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  maxWidth?: string
}) {
  if (!open) return null
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      background: 'rgba(0, 0, 0, 0.65)',
      backdropFilter: 'blur(4px)',
      animation: 'fadeIn 0.2s ease forwards'
    }}>
      <div style={{
        background: 'var(--bg2)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r3)',
        boxShadow: 'var(--shadow-xl)',
        width: '100%',
        maxWidth,
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>{title}</div>
          <button
            onClick={onClose}
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text3)',
              cursor: 'pointer',
              background: 'var(--bg3)',
              border: '1px solid var(--border)'
            }}
          >
            ✕
          </button>
        </div>
        {/* Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          {children}
        </div>
        {/* Footer */}
        {footer && (
          <div style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border)',
            background: 'var(--bg3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '10px'
          }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
