import React from 'react'

// ── BUTTON ────────────────────────────────────────────────────────────────
interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'danger' | 'green'
  size?: 'xs' | 'sm' | 'md'
  full?: boolean
  loading?: boolean
}

const btnBase: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  borderRadius: 'var(--r)', border: '1px solid var(--border)',
  background: 'var(--bg3)', color: 'var(--text2)',
  fontFamily: 'var(--font)', fontWeight: 500, cursor: 'pointer', transition: 'all .15s'
}
const btnSizes = {
  xs: { padding: '3px 8px', fontSize: '10px' },
  sm: { padding: '5px 11px', fontSize: '11px' },
  md: { padding: '7px 14px', fontSize: '12px' }
}
const btnVariants = {
  default: {},
  primary: { background: 'var(--blue)', borderColor: 'var(--blue)', color: 'white' },
  danger:  { background: 'var(--red)',  borderColor: 'var(--red)',  color: 'white' },
  green:   { background: 'var(--green)',borderColor: 'var(--green)',color: 'white' }
}

export function Btn({ variant = 'default', size = 'md', full, loading, children, style, disabled, ...rest }: BtnProps) {
  return (
    <button
      style={{
        ...btnBase,
        ...btnSizes[size],
        ...btnVariants[variant],
        ...(full ? { width: '100%', justifyContent: 'center' } : {}),
        ...(disabled || loading ? { opacity: 0.45, cursor: 'not-allowed', pointerEvents: 'none' } : {}),
        ...style
      }}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? 'Loading...' : children}
    </button>
  )
}

// ── CARD ─────────────────────────────────────────────────────────────────
export function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', padding: '16px', ...style }}>
      {children}
    </div>
  )
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: '14px' }}>
      {children}
    </div>
  )
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
      {children}
    </div>
  )
}

// ── BADGE ─────────────────────────────────────────────────────────────────
const badgeMap: Record<string, { bg: string; color: string }> = {
  Active:     { bg: 'var(--green-bg)',  color: 'var(--green)'  },
  Inactive:   { bg: 'var(--red-bg)',    color: 'var(--red)'    },
  Open:       { bg: 'var(--blue-bg)',   color: 'var(--blue)'   },
  Pending:    { bg: 'var(--amber-bg)',  color: 'var(--amber)'  },
  Critical:   { bg: 'var(--red-bg)',    color: 'var(--red)'    },
  Closed:     { bg: 'var(--bg4)',       color: 'var(--text3)'  },
  Verified:   { bg: 'var(--green-bg)',  color: 'var(--green)'  },
  Tampered:   { bg: 'var(--red-bg)',    color: 'var(--red)'    },
  Processing: { bg: 'var(--amber-bg)',  color: 'var(--amber)'  },
  Live:       { bg: 'var(--green-bg)',  color: 'var(--green)'  },
  'Planned v2': { bg: 'var(--bg4)',     color: 'var(--text3)'  }
}

export function Badge({ label }: { label: string }) {
  const colors = badgeMap[label] || { bg: 'var(--bg4)', color: 'var(--text3)' }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: '10px', padding: '2px 8px', borderRadius: '20px', fontWeight: 500, whiteSpace: 'nowrap', background: colors.bg, color: colors.color }}>
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
  width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 'var(--r)', padding: '7px 10px', fontSize: '13px',
  color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', transition: 'border .15s'
}

export function Input({ label, hint, error, style, ...rest }: InputProps) {
  return (
    <div>
      {label && <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>{label}</label>}
      <input style={{ ...inputStyle, ...(error ? { borderColor: 'var(--red)' } : {}), ...style }} {...rest} />
      {hint && !error && <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '3px' }}>{hint}</div>}
      {error && <div style={{ fontSize: '10px', color: 'var(--red)', marginTop: '3px' }}>{error}</div>}
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
    <div>
      {label && <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>{label}</label>}
      <select style={{ ...inputStyle, ...style }} {...rest}>
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
    <div>
      {label && <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '.4px' }}>{label}</label>}
      <textarea style={{ ...inputStyle, resize: 'vertical', lineHeight: '1.6', ...style }} {...rest} />
      {hint && <div style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '3px' }}>{hint}</div>}
    </div>
  )
}

// ── PROGRESS BAR ──────────────────────────────────────────────────────────
export function ProgressBar({ value, color = 'var(--blue)', height = 5 }: { value: number; color?: string; height?: number }) {
  return (
    <div style={{ background: 'var(--bg4)', borderRadius: '2px', overflow: 'hidden', height }}>
      <div style={{ height: '100%', borderRadius: '2px', background: color, width: `${Math.min(100, value)}%`, transition: 'width .5s' }} />
    </div>
  )
}

// ── SPINNER ───────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      border: '2px solid var(--border2)', borderTopColor: 'var(--blue)',
      animation: 'spin 0.8s linear infinite'
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
        borderRadius: 'var(--r2)', padding: '28px 20px', textAlign: 'center',
        cursor: 'pointer', transition: 'all .2s', marginBottom: '12px',
        background: isDragging ? 'rgba(0, 112, 243, 0.1)' : hover ? 'var(--blue-dim)' : 'transparent'
      }}
    >
      <div style={{ fontSize: '13px', color: isDragging ? 'var(--blue)' : 'var(--text2)', fontWeight: 500, marginBottom: '4px' }}>
        {isDragging ? 'Drop file to upload' : title}
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text3)' }}>{sub}</div>
    </div>
  )
}

// ── FUTURE NOTICE ─────────────────────────────────────────────────────────
export function FutureNotice({ text }: { text?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'var(--amber-bg)', border: '1px solid var(--amber)', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--amber)', marginBottom: '16px' }}>
      [Planned v2] {text || 'UI shown for stakeholder review and future scope demonstration'}
    </div>
  )
}

// ── HASH CHIP ─────────────────────────────────────────────────────────────
export function HashChip({ hash }: { hash: string }) {
  return (
    <span style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)', background: 'var(--bg4)', padding: '2px 6px', borderRadius: '4px' }}>
      SHA-256: {hash.slice(0, 8)}...
    </span>
  )
}

// ── INFO ROW ─────────────────────────────────────────────────────────────
export function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: '12px', color: 'var(--text3)' }}>{label}</span>
      <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text)', ...(mono ? { fontFamily: 'var(--mono)', color: 'var(--blue)' } : {}) }}>{value}</span>
    </div>
  )
}

// ── ALERT BOX ─────────────────────────────────────────────────────────────
export function AlertBox({ type, children }: { type: 'error' | 'success' | 'info' | 'warning'; children: React.ReactNode }) {
  const styles = {
    error:   { bg: 'var(--red-bg)',    border: 'var(--red)',    color: 'var(--red)'    },
    success: { bg: 'var(--green-bg)',  border: 'var(--green)',  color: 'var(--green)'  },
    info:    { bg: 'var(--blue-dim)',  border: 'var(--blue)',   color: 'var(--blue)'   },
    warning: { bg: 'var(--amber-bg)',  border: 'var(--amber)',  color: 'var(--amber)'  }
  }
  const s = styles[type]
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '10px 12px', background: s.bg, border: `1px solid ${s.border}`, borderRadius: 'var(--r)', fontSize: '12px', color: s.color }}>
      {children}
    </div>
  )
}

// ── TABS ─────────────────────────────────────────────────────────────────
export function Tabs({ tabs, activeIndex, onChange }: { tabs: string[]; activeIndex: number; onChange: (i: number) => void }) {
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: '16px', gap: '2px' }}>
      {tabs.map((tab, i) => (
        <div
          key={i}
          onClick={() => onChange(i)}
          style={{
            padding: '8px 14px', fontSize: '12px', fontWeight: 500, cursor: 'pointer',
            color: activeIndex === i ? 'var(--blue)' : 'var(--text3)',
            borderBottom: `2px solid ${activeIndex === i ? 'var(--blue)' : 'transparent'}`,
            transition: 'all .12s'
          }}
        >
          {tab}
        </div>
      ))}
    </div>
  )
}

// ── STEP WIZARD ───────────────────────────────────────────────────────────
export function StepWizard({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: '24px' }}>
      {steps.map((label, i) => {
        const num = i + 1
        const isDone = num < current
        const isActive = num === current
        return (
          <React.Fragment key={i}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'var(--text3)' }}>
              <div style={{
                width: '24px', height: '24px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '11px', fontWeight: 600, flexShrink: 0,
                border: `1.5px solid ${isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'var(--border)'}`,
                background: isDone ? 'var(--green)' : isActive ? 'var(--blue)' : 'transparent',
                color: (isDone || isActive) ? 'white' : 'var(--text3)'
              }}>
                {isDone ? '✓' : num}
              </div>
              <span>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: '1px', background: isDone ? 'var(--green)' : 'var(--border)', margin: '0 8px' }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// inject spinner keyframe
const styleEl = document.createElement('style')
styleEl.textContent = '@keyframes spin{to{transform:rotate(360deg)}}'
document.head.appendChild(styleEl)
