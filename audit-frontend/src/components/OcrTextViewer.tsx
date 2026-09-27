import React, { useEffect, useState } from 'react'
import { Btn, AlertBox, Spinner } from './UI'

export const TRANSLATION_LANGUAGES: [string, string][] = [
  ['en', 'English'], ['hi', 'Hindi'], ['kn', 'Kannada'], ['te', 'Telugu'], ['ta', 'Tamil'], ['ml', 'Malayalam'],
]

interface OcrTextViewerProps {
  result: any
  downloadName: string
  /** Fetches the translation (OCR is served from cache) and replaces `result`. */
  onTranslate: (targetLanguage: string) => Promise<void>
}

const selectStyle: React.CSSProperties = {
  background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '4px 8px',
  fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none',
}

/**
 * Page-wise OCR text with an Original / Translated switch.
 * The original OCR text is never replaced; translations are shown beside it.
 */
export function OcrTextViewer({ result, downloadName, onTranslate }: OcrTextViewerProps) {
  const [view, setView] = useState<'original' | 'translated'>('original')
  const [target, setTarget] = useState('en')
  const [activePage, setActivePage] = useState(1)
  const [translating, setTranslating] = useState(false)
  const [error, setError] = useState('')

  const pages: any[] = result.pages || []
  const multiPage = pages.length > 1
  const translation = result.translation
  const hasTranslation = translation?.target_language === target && result.translated_text != null

  useEffect(() => { setActivePage(1) }, [result.evidence_id])

  const requestTranslation = async (language: string) => {
    setTranslating(true)
    setError('')
    try {
      await onTranslate(language)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Translation request failed.')
    } finally {
      setTranslating(false)
    }
  }

  const showTranslated = () => {
    setView('translated')
    if (!hasTranslation && !translating) requestTranslation(target)
  }

  const changeTarget = (language: string) => {
    setTarget(language)
    if (view === 'translated') requestTranslation(language)
  }

  const page = pages.find((p) => p.page_number === activePage)
  const translatedView = view === 'translated' && hasTranslation
  const displayed = translatedView
    ? (multiPage ? page?.translated_text : result.translated_text) ?? ''
    : (multiPage ? page?.text : result.text) ?? ''
  const fullText = translatedView ? result.translated_text || '' : result.text || ''
  const suffix = translatedView ? `_${target}` : ''

  const toggle = (value: 'original' | 'translated', label: string, onClick: () => void) => (
    <button
      onClick={onClick}
      style={{
        border: '1px solid var(--border)', padding: '4px 10px', fontSize: '11px', cursor: 'pointer',
        background: view === value ? 'var(--blue)' : 'var(--bg3)', color: view === value ? '#fff' : 'var(--text2)',
        fontWeight: view === value ? 600 : 400,
        borderRadius: value === 'original' ? 'var(--r) 0 0 var(--r)' : '0 var(--r) var(--r) 0',
      }}
    >
      {label}
    </button>
  )

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <div style={{ display: 'flex' }}>
          {toggle('original', 'Original Text', () => setView('original'))}
          {toggle('translated', 'Translated Text', showTranslated)}
        </div>
        <label style={{ fontSize: '11px', color: 'var(--text3)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          Translate to
          <select value={target} onChange={(e) => changeTarget(e.target.value)} style={selectStyle} disabled={translating}>
            {TRANSLATION_LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
        </label>
        {view === 'translated' && !hasTranslation && !translating && (
          <Btn size="xs" variant="primary" onClick={() => requestTranslation(target)}>Translate</Btn>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
          <Btn size="xs" onClick={() => { navigator.clipboard.writeText(displayed); alert('Text copied to clipboard!') }}>
            Copy Page
          </Btn>
          <Btn
            size="xs"
            onClick={() => {
              const link = document.createElement('a')
              link.href = URL.createObjectURL(new Blob([fullText], { type: 'text/plain' }))
              link.download = `${downloadName}${suffix}.txt`
              document.body.appendChild(link)
              link.click()
              document.body.removeChild(link)
            }}
          >
            Download Full Text
          </Btn>
        </div>
      </div>

      {view === 'translated' && (
        <div style={{ marginBottom: '10px' }}>
          {translating && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text3)' }}>
              <Spinner size={14} /> Translating…
            </div>
          )}
          {!translating && error && <AlertBox type="error">{error} The original text is unchanged.</AlertBox>}
          {!translating && !error && translation?.target_language === target && translation.status === 'failed' && (
            <AlertBox type="error">Translation failed: {translation.error} The original OCR text is still available.</AlertBox>
          )}
          {!translating && hasTranslation && translation.status === 'partial' && (
            <AlertBox type="warning">{translation.error}</AlertBox>
          )}
          {!translating && hasTranslation && translation.message && translation.status !== 'skipped' && (
            <div style={{ marginBottom: '6px' }}><AlertBox type="info">{translation.message}</AlertBox></div>
          )}
          {!translating && hasTranslation && translation.status === 'skipped' && (
            <AlertBox type="info">The text is already in {translation.target_language_name}.</AlertBox>
          )}
          {!translating && hasTranslation && translation.status !== 'skipped' && (
            <div style={{ fontSize: '10px', color: 'var(--text3)' }}>
              Machine translation{translation.providers?.length ? ` via ${translation.providers.join(', ')}` : ''} — verify against the original before relying on it.
            </div>
          )}
        </div>
      )}

      {multiPage && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '12px' }}>
          {pages.map((p) => (
            <button
              key={p.page_number}
              onClick={() => setActivePage(p.page_number)}
              style={{
                border: '1px solid var(--border)', borderRadius: '4px', padding: '3px 8px', fontSize: '10px',
                fontFamily: 'var(--mono)', cursor: 'pointer',
                background: activePage === p.page_number ? 'var(--blue)' : 'var(--bg3)',
                color: activePage === p.page_number ? '#fff' : 'var(--text2)',
                fontWeight: activePage === p.page_number ? 600 : 400,
              }}
            >
              Page {p.page_number}
            </button>
          ))}
        </div>
      )}

      <div
        style={{
          fontSize: '12px', fontFamily: 'var(--mono)', color: 'var(--text2)', lineHeight: 1.6, padding: '12px',
          background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)',
          whiteSpace: 'pre-wrap', maxHeight: '400px', overflowY: 'auto',
        }}
      >
        {view === 'translated' && !hasTranslation
          ? (translating ? '' : '(No translation available)')
          : displayed || (multiPage ? '(Empty page)' : '(No text extracted)')}
      </div>
    </div>
  )
}
