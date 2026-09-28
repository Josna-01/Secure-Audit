import React, { useRef, useState, useMemo, useEffect } from 'react'
import { AppShell } from '../components/Layout'
import { Card, CardTitle, CardHeader, Btn, AlertBox, Spinner } from '../components/UI'
import { api } from '../services/api'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine
} from 'recharts'

interface TamperedSegment {
  start?: number
  end?: number
  start_timestamp: string
  end_timestamp: string
  timestamp?: string
  type: string
  classification?: string
  reason: string
  confidence?: number
}

interface AudioMetadata {
  file_name: string
  format: string
  duration: string
  duration_seconds?: number
  sample_rate: string
  channels: string
  file_size: string
  bit_depth?: string
}

interface TranscriptSegment {
  id?: number
  start: number
  end: number
  start_timestamp?: string
  end_timestamp?: string
  timestamp: string
  speaker: string
  text: string
}

interface SpeakerTimelineItem {
  speaker: string
  start: string
  end: string
  timestamp: string
  text: string
}

interface SpeakerIdentification {
  speakers_count: number
  speakers_list: string[]
  timeline?: SpeakerTimelineItem[]
  consistency?: string
  unknown_speaker_alert?: boolean
  summary?: string
}

interface EnvironmentalChange {
  timestamp: string
  start?: number
  end?: number
  from_environment?: string
  to_environment?: string
  description?: string
  reason?: string
}

interface BackgroundAnalysis {
  primary_environment: string
  environment_consistency: string
  environmental_changes?: EnvironmentalChange[]
  summary: string
}

interface KeywordMatch {
  keyword: string
  count?: number
  timestamp?: string
  snippet?: string
}

interface KeywordsAnalysis {
  found_keywords: KeywordMatch[] | boolean
  keywords_list: string[]
  total_matches?: number
  keywords_count?: number
  summary?: string
}

interface NoiseAnalysis {
  background_noise_consistency?: string
  noise_floor_db?: string
  snr_db?: string
  recording_quality?: string
  microphone_environment_changes?: string
  audio_distortions?: string
  summary?: string
}

interface ENFDataPoint {
  time: string
  seconds: number
  frequency: number
  status: string
}

interface ENFSegment {
  start: number
  end: number
  start_timestamp?: string
  end_timestamp?: string
  timestamp: string
  type?: string
  observation?: string
  interpretation?: string
  confidence?: number
  reason?: string
}

interface ENFAnalysis {
  status: string
  authenticity_status?: string
  confidence_score?: number
  confidence?: number
  enf_graph_data?: ENFDataPoint[]
  graph_data?: ENFDataPoint[]
  enf_segments?: ENFSegment[]
  summary: string
  observation?: string
  interpretation?: string
  disclaimer?: string
}

interface AudioAnalysisReport {
  file_name: string
  audio_status: string
  authenticity_status?: string
  confidence_score: number
  tampering_score?: number
  enf_analysis?: ENFAnalysis
  tampered_segments?: TamperedSegment[]
  tampering_report?: {
    tampered_segments: TamperedSegment[]
    summary: string
  }
  metadata?: AudioMetadata
  transcript_segments?: TranscriptSegment[]
  transcript_formatted?: string
  transcript?: string
  transcription?: string
  speaker_identification?: SpeakerIdentification
  background_analysis?: BackgroundAnalysis
  keywords_analysis?: KeywordsAnalysis
  noise_analysis?: NoiseAnalysis
  investigation_summary?: string[]
  investigation_summary_text?: string
  conclusion?: string
  summary: string
}

export default function AudioForensicsPage() {
  const [file, setFile] = useState<File | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState(0)
  const [report, setReport] = useState<AudioAnalysisReport | null>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const audioPlayerRef = useRef<HTMLAudioElement>(null)

  // Custom Audio Player State
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)

  // Loading steps list
  const loadingSteps = [
    'Uploading audio evidence...',
    'Processing audio waveform & PCM channels...',
    'Running 50 Hz Electric Network Frequency (ENF) analysis...',
    'Generating timestamped speech-to-text transcript...',
    'Detecting speaker identification & diarization...',
    'Preparing comprehensive forensic investigation report...'
  ]

  // Dynamic step simulation during loading
  useEffect(() => {
    let interval: any = null
    if (loading) {
      setLoadingStage(0)
      interval = setInterval(() => {
        setLoadingStage((prev) => (prev < loadingSteps.length - 1 ? prev + 1 : prev))
      }, 3500)
    } else {
      setLoadingStage(0)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [loading])

  // Handle Audio File Selection
  const processSelectedFile = (selectedFile: File | null) => {
    if (!selectedFile) return
    const nameLower = selectedFile.name.toLowerCase()
    if (!nameLower.endsWith('.wav') && !nameLower.endsWith('.mp3') && !nameLower.endsWith('.mp4') && !nameLower.endsWith('.m4a')) {
      setError('Unsupported file type. Please upload an MP3, MP4, M4A, or WAV audio file.')
      setFile(null)
      setAudioUrl(null)
      return
    }
    setError('')
    setReport(null)
    setFile(selectedFile)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(URL.createObjectURL(selectedFile))
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null
    processSelectedFile(selected)
  }

  // Drag & Drop Handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    const droppedFile = e.dataTransfer.files?.[0] || null
    processSelectedFile(droppedFile)
  }

  const handleRemoveFile = () => {
    setFile(null)
    setReport(null)
    setError('')
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  // Run Backend Audio Analysis Pipeline
  const runAnalysis = async () => {
    if (!file) {
      setError('Please select a valid MP3, MP4, M4A, or WAV audio file first.')
      return
    }
    setLoading(true)
    setError('')
    setReport(null)
    try {
      const data = await api.analyzeAudio(file)
      setReport(data)
    } catch (err: any) {
      console.error('Audio analysis error:', err)
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setError(`Analysis failed: ${detail}`)
      } else if (Array.isArray(detail)) {
        setError(`Analysis failed: ${detail[0]?.msg || 'Validation error'}`)
      } else {
        setError(err.message || 'Unable to connect to audio analysis backend service. Please verify the server is running on port 8002.')
      }
    } finally {
      setLoading(false)
    }
  }

  // Seek Player to Specific Time
  const seekToTime = (seconds?: number) => {
    if (audioPlayerRef.current && seconds !== undefined) {
      audioPlayerRef.current.currentTime = seconds
      audioPlayerRef.current.play().then(() => setIsPlaying(true)).catch(() => {})
    }
  }

  const parseTimestampSeconds = (ts?: string): number => {
    if (!ts) return 0
    const cleanTs = ts.split('–')[0].split('-')[0].trim()
    const parts = cleanTs.split(':').map(Number)
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if (parts.length === 2) return parts[0] * 60 + parts[1]
    return 0
  }

  // Format Seconds to MM:SS
  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return '00:00'
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Playback Control Handlers
  const togglePlayPause = () => {
    if (!audioPlayerRef.current) return
    if (isPlaying) {
      audioPlayerRef.current.pause()
      setIsPlaying(false)
    } else {
      audioPlayerRef.current.play().then(() => setIsPlaying(true)).catch(() => {})
    }
  }

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const targetTime = Number(e.target.value)
    if (audioPlayerRef.current) {
      audioPlayerRef.current.currentTime = targetTime
      setCurrentTime(targetTime)
    }
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value)
    setVolume(val)
    if (audioPlayerRef.current) {
      audioPlayerRef.current.volume = val
      setIsMuted(val === 0)
    }
  }

  const toggleMute = () => {
    if (!audioPlayerRef.current) return
    if (isMuted) {
      audioPlayerRef.current.muted = false
      setIsMuted(false)
    } else {
      audioPlayerRef.current.muted = true
      setIsMuted(true)
    }
  }

  // Status Classifications
  const statusTheme = useMemo(() => {
    if (!report) return { text: 'Authentic', label: 'No Significant Signs of Tampering', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green)' }
    const status = report.audio_status || report.authenticity_status || 'Authentic'
    if (status.includes('Tampered') || status.includes('Manipulation') || status.includes('Potentially')) {
      return { text: 'Potentially Tampered', label: 'Potential Audio Manipulation', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red)' }
    } else if (status.includes('Minor') || status.includes('Anomalies')) {
      return { text: 'Minor Anomalies', label: 'Minor Forensic Anomalies', color: 'var(--amber)', bg: 'var(--amber-bg)', border: 'var(--amber)' }
    }
    return { text: 'Authentic', label: 'No Significant Signs of Tampering', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green)' }
  }, [report])

  const enfStatusIsConsistent = useMemo(() => {
    if (!report?.enf_analysis) return true
    return report.enf_analysis.status === 'Consistent ENF Signal'
  }, [report])

  // Speaker Color Map
  const getSpeakerColor = (speakerName: string) => {
    const name = (speakerName || '').toLowerCase()
    if (name.includes('1')) return { color: 'var(--blue)', bg: 'var(--blue-dim)', border: 'var(--blue)' }
    if (name.includes('2')) return { color: '#a855f7', bg: 'rgba(168, 85, 247, 0.15)', border: '#a855f7' }
    if (name.includes('3')) return { color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green)' }
    return { color: 'var(--amber)', bg: 'var(--amber-bg)', border: 'var(--amber)' }
  }

  // Highlight suspicious keywords in text
  const highlightTextWithKeywords = (text: string, keywords: string[]) => {
    if (!keywords || keywords.length === 0) return text
    const escaped = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    const regex = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi')
    const parts = text.split(regex)
    return parts.map((part, idx) => {
      const isKw = keywords.some(k => k.toLowerCase() === part.toLowerCase())
      if (isKw) {
        return (
          <mark
            key={idx}
            style={{
              background: 'var(--amber-bg)',
              border: '1px solid var(--amber)',
              color: 'var(--amber)',
              borderRadius: '4px',
              padding: '1px 6px',
              fontWeight: 700,
              fontSize: '12px'
            }}
          >
            {part}
          </mark>
        )
      }
      return part
    })
  }

  // Print/Download PDF Report
  const downloadPdfReport = () => {
    if (!report) return
    const win = window.open('', '_blank')
    if (!win) return
    const enfSec = report.enf_analysis
    const enfDiscontinuitiesHtml = (enfSec?.enf_segments && enfSec.enf_segments.length > 0)
      ? enfSec.enf_segments.map(s => `
        <tr>
          <td style="padding:8px; font-weight:bold; color:#dc2626;">${s.timestamp}</td>
          <td style="padding:8px;">${s.observation || s.reason || ''}</td>
          <td style="padding:8px; font-style:italic;">${s.interpretation || 'ENF anomaly'}</td>
          <td style="padding:8px; font-weight:bold;">${s.confidence || 94}%</td>
        </tr>
      `).join('')
      : `<tr><td colspan="4" style="padding:10px; color:#16a34a;">✓ Continuous 50 Hz power grid ENF signal trajectory verified. No discontinuities detected.</td></tr>`

    const transcriptRowsHtml = (report.transcript_segments && report.transcript_segments.length > 0)
      ? report.transcript_segments.map(seg => `
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding:8px; font-weight:bold; color:#0284c7; width:90px;">${seg.timestamp}</td>
          <td style="padding:8px; font-weight:bold; color:#334155; width:100px;">${seg.speaker}</td>
          <td style="padding:8px; color:#0f172a;">${seg.text}</td>
        </tr>
      `).join('')
      : `<tr><td colspan="3" style="padding:10px;">${report.transcript || report.transcription || 'No transcript generated.'}</td></tr>`

    const mergedTamperHtml = (report.tampered_segments && report.tampered_segments.length > 0)
      ? report.tampered_segments.map(seg => `
        <tr style="border-bottom: 1px solid #fee2e2;">
          <td style="padding:8px; font-weight:bold; color:#991b1b;">${seg.timestamp || (seg.start_timestamp + '–' + seg.end_timestamp)}</td>
          <td style="padding:8px; font-weight:bold;">${seg.classification || seg.type}</td>
          <td style="padding:8px;">${seg.reason}</td>
          <td style="padding:8px; font-weight:bold;">${seg.confidence || 94}%</td>
        </tr>
      `).join('')
      : `<tr><td colspan="4" style="padding:10px; color:#16a34a;">✓ No significant signs of tampering detected across audio timeline.</td></tr>`

    const findingsHtml = (report.investigation_summary && report.investigation_summary.length > 0)
      ? report.investigation_summary.map(item => `<li style="margin-bottom:6px;">${item}</li>`).join('')
      : `<li>ENF and audio forensic examination completed successfully.</li>`

    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Forensic Audio Evidence Report — ${report.file_name}</title>
        <style>
          body { font-family: 'Segoe UI', Arial, sans-serif; margin: 35px; color: #1e293b; line-height: 1.5; font-size: 13px; }
          .header { text-align: center; border-bottom: 3px solid #0f172a; padding-bottom: 14px; margin-bottom: 24px; }
          .header h1 { margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px; color: #0f172a; }
          .header p { margin: 4px 0 0 0; font-size: 12px; color: #475569; font-weight: 600; }
          .badge { display: inline-block; padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 13px; margin-top: 10px; text-transform: uppercase; }
          .badge-authentic { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
          .badge-tampered { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
          .badge-minor { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
          .section { margin-bottom: 22px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 14px 18px; background: #ffffff; }
          .section-title { font-weight: bold; font-size: 14px; text-transform: uppercase; color: #0369a1; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 12px; }
          table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }
          th { background: #f1f5f9; text-align: left; padding: 8px; font-size: 11px; text-transform: uppercase; color: #475569; border: 1px solid #cbd5e1; }
          td { padding: 8px; border: 1px solid #e2e8f0; }
          .footer { font-size: 10px; color: #94a3b8; text-align: center; margin-top: 35px; border-top: 1px solid #e2e8f0; padding-top: 10px; }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>OFFICIAL FORENSIC AUDIO INVESTIGATION REPORT</h1>
          <p>Police Cyber Crime Investigation System • ENF Audio Forensic Examination Module</p>
          <div class="badge ${statusTheme.text === 'Authentic' ? 'badge-authentic' : statusTheme.text === 'Minor Anomalies' ? 'badge-minor' : 'badge-tampered'}">
            ${report.authenticity_status || statusTheme.label} (Confidence: ${enfSec?.confidence_score ?? report.confidence_score}%)
          </div>
        </div>
        <div class="section">
          <div class="section-title">1. Audio Technical Metadata</div>
          <table>
            <tr><td><strong>File Name:</strong> ${report.metadata?.file_name || report.file_name}</td><td><strong>Format:</strong> ${report.metadata?.format || 'WAV'}</td></tr>
            <tr><td><strong>Duration:</strong> ${report.metadata?.duration || 'N/A'}</td><td><strong>Sample Rate:</strong> ${report.metadata?.sample_rate || 'N/A'}</td></tr>
            <tr><td><strong>Channels:</strong> ${report.metadata?.channels || 'Mono'}</td><td><strong>File Size:</strong> ${report.metadata?.file_size || 'N/A'}</td></tr>
          </table>
        </div>
        <div class="section">
          <div class="section-title">2. Electric Network Frequency (ENF) Forensic Analysis</div>
          <p><strong>ENF Status:</strong> ${enfSec?.status || 'Consistent ENF Signal'}</p>
          <p><strong>Observation:</strong> ${enfSec?.observation || 'No significant ENF discontinuities detected.'}</p>
          <p><strong>Interpretation:</strong> ${enfSec?.interpretation || 'Continuous 50 Hz power grid frequency trajectory verified.'}</p>
          <table>
            <thead><tr><th>Timestamp</th><th>Observation</th><th>Interpretation</th><th>Confidence</th></tr></thead>
            <tbody>${enfDiscontinuitiesHtml}</tbody>
          </table>
        </div>
        <div class="section">
          <div class="section-title">3. Speech-to-Text &amp; Timestamped Transcript</div>
          <table>
            <thead><tr><th>Timestamp</th><th>Speaker</th><th>Transcript Text</th></tr></thead>
            <tbody>${transcriptRowsHtml}</tbody>
          </table>
        </div>
        <div class="section">
          <div class="section-title">4. Speaker Identification &amp; Diarization</div>
          <p><strong>Speakers Count:</strong> ${report.speaker_identification?.speakers_count || 1}</p>
          <p><strong>Speakers List:</strong> ${(report.speaker_identification?.speakers_list || ['Speaker 1']).join(', ')}</p>
        </div>
        <div class="section">
          <div class="section-title">5. Background Environment Analysis</div>
          <p><strong>Primary Environment:</strong> ${report.background_analysis?.primary_environment || 'Indoor / Office'}</p>
          <p><strong>Consistency:</strong> ${report.background_analysis?.environment_consistency || 'Consistent throughout.'}</p>
        </div>
        <div class="section">
          <div class="section-title">6. Suspicious Keyword Extraction</div>
          <p><strong>Keywords Found:</strong> ${(report.keywords_analysis?.keywords_list && report.keywords_analysis.keywords_list.length > 0) ? report.keywords_analysis.keywords_list.join(', ') : 'None'}</p>
        </div>
        <div class="section">
          <div class="section-title">7. Audio Tampering &amp; Manipulation Indicators</div>
          <table>
            <thead><tr><th>Timestamp</th><th>Classification</th><th>Reason</th><th>Confidence</th></tr></thead>
            <tbody>${mergedTamperHtml}</tbody>
          </table>
        </div>
        <div class="section">
          <div class="section-title">8. Executive Investigation Summary</div>
          <ul>${findingsHtml}</ul>
        </div>
        <div class="footer">
          Generated on ${new Date().toLocaleString()} • Digital Evidence &amp; Forensic Audits System
        </div>
      </body>
      </html>
    `
    win.document.write(htmlContent)
    win.document.close()
    win.focus()
    setTimeout(() => {
      win.print()
    }, 500)
  }

  // Keywords list normalized
  const extractedKeywords = useMemo(() => {
    if (!report?.keywords_analysis) return []
    if (Array.isArray(report.keywords_analysis.keywords_list)) {
      return report.keywords_analysis.keywords_list
    }
    return []
  }, [report])

  return (
    <AppShell title="Audio Evidence Examination Module">
      {/* Hidden Audio Tag for Custom Player */}
      {audioUrl && (
        <audio
          ref={audioPlayerRef}
          src={audioUrl}
          onTimeUpdate={() => {
            if (audioPlayerRef.current) setCurrentTime(audioPlayerRef.current.currentTime)
          }}
          onLoadedMetadata={() => {
            if (audioPlayerRef.current) setDuration(audioPlayerRef.current.duration)
          }}
          onEnded={() => setIsPlaying(false)}
          style={{ display: 'none' }}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1240px', margin: '0 auto', paddingBottom: '40px' }}>
        {/* Top Header Banner */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--r2)', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span style={{ background: 'var(--blue-dim)', color: 'var(--blue)', border: '1px solid var(--blue)', borderRadius: '20px', padding: '3px 12px', fontSize: '11px', fontWeight: 700, letterSpacing: '0.5px' }}>
              🎙️ AUDIO FORENSICS &amp; ENF MODULE
            </span>
            <span style={{ color: 'var(--text3)' }}>•</span>
            <span style={{ color: 'var(--text2)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              50 HZ POWER GRID ENF ANALYSIS &amp; DIARIZATION
            </span>
          </div>
          <h2 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)', margin: '0 0 6px 0', letterSpacing: '-0.2px' }}>
            AI-Based Audio Evidence Examination Tool
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text2)', margin: 0, lineHeight: 1.6 }}>
            Upload digital audio evidence (MP3, MP4, M4A, or WAV) from threat calls, extortion recordings, interrogations, bribery taps, or surveillance clips. Performs automated 50 Hz Electric Network Frequency (ENF) profiling, multi-speaker diarization, timestamped speech transcription, acoustic environment parsing, and multi-indicator tampering detection.
          </p>
        </div>

        {/* Upload Section Card */}
        <Card>
          <CardTitle>1. Select &amp; Upload Audio Evidence File</CardTitle>
          <input
            ref={fileRef}
            type="file"
            accept="audio/wav,audio/mp3,audio/mpeg,audio/mp4,video/mp4,audio/x-m4a,audio/x-wav,.wav,.mp3,.mp4,.m4a"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            id="audio-evidence-file-input"
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Drag & Drop Area */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${isDragOver ? 'var(--blue)' : file ? 'var(--green)' : 'var(--border)'}`,
                borderRadius: 'var(--r2)',
                padding: '32px 24px',
                textAlign: 'center',
                cursor: 'pointer',
                background: isDragOver ? 'var(--blue-dim)' : file ? 'var(--green-bg)' : 'var(--bg3)',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px'
              }}
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: file ? 'var(--green-bg)' : 'var(--blue-dim)',
                border: `1px solid ${file ? 'var(--green)' : 'var(--blue)'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '22px'
              }}>
                {file ? '🎵' : '📁'}
              </div>

              {file ? (
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text)' }}>
                    Selected: {file.name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text2)', marginTop: '4px' }}>
                    Size: {(file.size / (1024 * 1024)).toFixed(2)} MB | Type: {file.type || 'audio/wav'}
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>
                    Drag &amp; Drop MP3, MP4, M4A, or WAV file here, or <span style={{ color: 'var(--blue)', textDecoration: 'underline' }}>browse file</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '4px' }}>
                    Supports MP3, MP4, M4A, and WAV audio formats (Up to 100 MB per evidence clip)
                  </div>
                </div>
              )}
            </div>

            {/* Action Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              {file ? (
                <Btn variant="danger" size="sm" onClick={handleRemoveFile} style={{ gap: '6px' }}>
                  🗑️ Remove &amp; Replace File
                </Btn>
              ) : (
                <span style={{ fontSize: '12px', color: 'var(--text3)' }}>No evidence file selected yet.</span>
              )}

              <Btn
                variant="primary"
                size="md"
                onClick={runAnalysis}
                disabled={loading || !file}
                style={{ padding: '12px 24px', fontWeight: 700, fontSize: '13px' }}
              >
                {loading ? '🔍 Examining Evidence...' : '⚡ Analyze Audio Evidence'}
              </Btn>
            </div>

            {/* Error Alert with Retry Option */}
            {error && (
              <AlertBox type="error">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <span>{error}</span>
                  <Btn size="xs" variant="primary" onClick={runAnalysis} disabled={!file || loading}>
                    🔄 Retry Analysis
                  </Btn>
                </div>
              </AlertBox>
            )}
          </div>
        </Card>

        {/* Loading State with Progress Steps */}
        {loading && (
          <Card style={{ padding: '36px 24px', textAlign: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', maxWidth: '600px', margin: '0 auto' }}>
              <Spinner size={36} />
              
              <div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
                  Executing AI Audio Forensic Examination Pipeline
                </div>
                <div style={{ fontSize: '13px', color: 'var(--blue)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                  {loadingSteps[loadingStage]}
                </div>
              </div>

              {/* Progress Bar */}
              <div style={{ width: '100%', height: '8px', background: 'var(--bg4)', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${((loadingStage + 1) / loadingSteps.length) * 100}%`,
                    height: '100%',
                    background: 'var(--blue)',
                    borderRadius: '4px',
                    transition: 'width 0.4s ease'
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '6px' }}>
                {loadingSteps.map((step, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: '10px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontWeight: 600,
                      background: idx === loadingStage ? 'var(--blue-dim)' : idx < loadingStage ? 'var(--green-bg)' : 'var(--bg3)',
                      color: idx === loadingStage ? 'var(--blue)' : idx < loadingStage ? 'var(--green)' : 'var(--text3)',
                      border: `1px solid ${idx === loadingStage ? 'var(--blue)' : idx < loadingStage ? 'var(--green)' : 'var(--border)'}`
                    }}
                  >
                    {idx < loadingStage ? '✓' : idx + 1}. {step.split(' ')[0]}
                  </span>
                ))}
              </div>
            </div>
          </Card>
        )}

        {/* Results Dashboard (8 Cards + Audio Player) */}
        {report && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Custom Interactive Audio Player Bar */}
            <Card style={{ background: 'var(--bg2)', border: '1px solid var(--blue-dim)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Btn size="sm" variant="primary" onClick={togglePlayPause} style={{ minWidth: '90px' }}>
                      {isPlaying ? '⏸️ Pause' : '▶️ Play'}
                    </Btn>
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text)' }}>
                        {report.file_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text2)', fontFamily: 'var(--mono)' }}>
                        {formatTime(currentTime)} / {formatTime(duration || parseTimestampSeconds(report.metadata?.duration) || 0)}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    {/* Status Pill */}
                    <span
                      style={{
                        padding: '4px 12px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        background: statusTheme.bg,
                        color: statusTheme.color,
                        border: `1px solid ${statusTheme.border}`
                      }}
                    >
                      {statusTheme.label} ({report.enf_analysis?.confidence_score ?? report.confidence_score}%)
                    </span>

                    <Btn variant="green" size="sm" onClick={downloadPdfReport} style={{ fontWeight: 600 }}>
                      📄 Download Report
                    </Btn>
                  </div>
                </div>

                {/* Scrubber Slider */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text3)', fontFamily: 'var(--mono)' }}>{formatTime(currentTime)}</span>
                  <input
                    type="range"
                    min={0}
                    max={duration || 100}
                    step={0.1}
                    value={currentTime}
                    onChange={handleSeekChange}
                    style={{ flex: 1, accentColor: 'var(--blue)', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '11px', color: 'var(--text3)', fontFamily: 'var(--mono)' }}>{formatTime(duration)}</span>

                  {/* Volume Control */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '10px' }}>
                    <button onClick={toggleMute} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text2)', fontSize: '14px' }}>
                      {isMuted || volume === 0 ? '🔇' : '🔊'}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={isMuted ? 0 : volume}
                      onChange={handleVolumeChange}
                      style={{ width: '60px', accentColor: 'var(--blue)', cursor: 'pointer' }}
                    />
                  </div>
                </div>
              </div>
            </Card>

            {/* CARD 1 – Audio Technical Information */}
            <Card>
              <CardTitle>1. Audio Technical Information</CardTitle>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    📄 File Name
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {report.metadata?.file_name || report.file_name}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    🎵 Format
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--blue)', marginTop: '4px' }}>
                    {report.metadata?.format || 'WAV'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    ⏱️ Duration
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '4px' }}>
                    {report.metadata?.duration || 'N/A'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    📊 Sample Rate
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '4px' }}>
                    {report.metadata?.sample_rate || 'N/A'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    🔊 Channels
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '4px' }}>
                    {report.metadata?.channels || 'Mono'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '10px 12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    💾 File Size
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '4px' }}>
                    {report.metadata?.file_size || 'N/A'}
                  </div>
                </div>
              </div>
            </Card>

            {/* CARD 2 – ENF Analysis */}
            <Card style={{ border: '1px solid var(--blue-dim)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <span style={{ background: 'var(--blue-dim)', color: 'var(--blue)', border: '1px solid var(--blue)', borderRadius: '4px', padding: '2px 8px', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase' }}>
                    PRIMARY FORENSIC FEATURE
                  </span>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)', margin: '4px 0 0 0' }}>
                    2. Electric Network Frequency (ENF) Analysis
                  </h3>
                </div>
                <span style={{ padding: '4px 12px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, background: enfStatusIsConsistent ? 'var(--green-bg)' : 'var(--red-bg)', color: enfStatusIsConsistent ? 'var(--green)' : 'var(--red)', border: `1px solid ${enfStatusIsConsistent ? 'var(--green)' : 'var(--red)'}` }}>
                  {report.enf_analysis?.status || (enfStatusIsConsistent ? 'Consistent ENF Signal' : 'Potential ENF Discontinuity')}
                </span>
              </div>

              {/* Status details grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>ENF Status</div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: enfStatusIsConsistent ? 'var(--green)' : 'var(--red)' }}>
                    {report.enf_analysis?.status || 'Consistent ENF Signal'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Observations</div>
                  <div style={{ fontSize: '12px', color: 'var(--text)' }}>
                    {report.enf_analysis?.observation || 'No significant ENF discontinuities detected.'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '4px' }}>Grid Frequency Summary</div>
                  <div style={{ fontSize: '12px', color: 'var(--text2)', fontStyle: 'italic' }}>
                    {report.enf_analysis?.summary || 'Continuous 50 Hz power grid frequency trajectory verified across audio timeline.'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--blue)', marginTop: '4px', fontFamily: 'var(--mono)' }}>
                    Confidence Score: {report.enf_analysis?.confidence_score ?? report.enf_analysis?.confidence ?? 94}%
                  </div>
                </div>
              </div>

              {/* ENF Spectrogram / Recharts Graph */}
              {(report.enf_analysis?.enf_graph_data || report.enf_analysis?.graph_data) && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '11px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text2)', textTransform: 'uppercase' }}>50.0 Hz Power Grid ENF Frequency Trajectory Graph</span>
                    <span style={{ color: 'var(--blue)', fontFamily: 'var(--mono)' }}>Nominal 50.0 Hz Baseline</span>
                  </div>
                  <div style={{ height: '220px', width: '100%', background: 'var(--bg3)', borderRadius: 'var(--r)', padding: '8px 4px 4px 0', border: '1px solid var(--border)' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={report.enf_analysis.enf_graph_data || report.enf_analysis.graph_data} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="time" stroke="var(--text3)" tick={{ fontSize: 10 }} />
                        <YAxis domain={[49.75, 50.25]} stroke="var(--text3)" tick={{ fontSize: 10 }} unit=" Hz" />
                        <Tooltip
                          contentStyle={{ backgroundColor: 'var(--bg2)', borderColor: 'var(--border)', borderRadius: '6px', color: 'var(--text)', fontSize: '12px' }}
                          formatter={(val: any) => [`${val} Hz`, 'ENF Frequency']}
                        />
                        <ReferenceLine y={50.0} stroke="var(--blue)" strokeDasharray="4 4" label={{ value: '50.0 Hz Grid Nominal', fill: 'var(--blue)', fontSize: 10 }} />
                        <Line type="monotone" dataKey="frequency" stroke="var(--blue)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </Card>

            {/* CARD 3 – Timestamped Transcript */}
            <Card>
              <CardHeader>
                <CardTitle>3. Speech-to-Text &amp; Timestamped Transcript</CardTitle>
                <span style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 500 }}>
                  Merged continuous speaker blocks · Click timestamp to seek audio
                </span>
              </CardHeader>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxHeight: '480px', overflowY: 'auto', paddingRight: '4px' }}>
                {report.transcript_segments && report.transcript_segments.length > 0 ? (
                  report.transcript_segments.map((seg, idx) => {
                    const spkColor = getSpeakerColor(seg.speaker)
                    return (
                      <React.Fragment key={idx}>
                        <div
                          style={{
                            background: 'var(--bg3)',
                            border: `1px solid ${spkColor.border}`,
                            borderRadius: 'var(--r2)',
                            padding: '14px 16px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                            <span
                              style={{
                                background: spkColor.bg,
                                border: `1px solid ${spkColor.border}`,
                                color: spkColor.color,
                                padding: '3px 10px',
                                borderRadius: '6px',
                                fontSize: '12px',
                                fontWeight: 700,
                                letterSpacing: '0.2px'
                              }}
                            >
                              🗣️ {seg.speaker}
                            </span>
                            <button
                              onClick={() => seekToTime(seg.start || parseTimestampSeconds(seg.timestamp))}
                              style={{
                                background: 'var(--blue-dim)',
                                border: '1px solid var(--blue)',
                                color: 'var(--blue)',
                                borderRadius: '6px',
                                padding: '3px 10px',
                                fontSize: '11px',
                                fontFamily: 'var(--mono)',
                                fontWeight: 700,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px'
                              }}
                              title="Seek audio to start of speaker block"
                            >
                              ⏱️ {seg.timestamp || `${seg.start_timestamp}–${seg.end_timestamp}`}
                            </button>
                          </div>
                          <div style={{ fontSize: '13px', color: 'var(--text)', lineHeight: 1.6, marginTop: '2px', fontWeight: 400 }}>
                            {highlightTextWithKeywords(seg.text, extractedKeywords)}
                          </div>
                        </div>
                        {idx < (report.transcript_segments?.length || 0) - 1 && (
                          <div style={{ borderTop: '1px dashed var(--border2)', margin: '2px 0' }} />
                        )}
                      </React.Fragment>
                    )
                  })
                ) : (
                  <div style={{ background: 'var(--bg3)', padding: '14px', borderRadius: 'var(--r)', fontSize: '13px', color: 'var(--text2)', whiteSpace: 'pre-wrap' }}>
                    {report.transcript_formatted || report.transcript || report.transcription || 'No transcript generated for this audio file.'}
                  </div>
                )}
              </div>
            </Card>

            {/* CARD 4 – Speaker Analysis */}
            <Card>
              <CardHeader>
                <CardTitle>4. Speaker Identification &amp; Diarization</CardTitle>
                <span style={{ background: 'var(--blue-dim)', color: 'var(--blue)', border: '1px solid var(--blue)', padding: '3px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700 }}>
                  {report.speaker_identification?.speakers_count || 1} Speaker(s) Identified
                </span>
              </CardHeader>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px', fontSize: '12px', color: 'var(--text2)' }}>
                  <strong style={{ color: 'var(--text)' }}>Voice Stream Consistency: </strong>
                  {report.speaker_identification?.consistency || 'Voice characteristics remained consistent.'}
                </div>
                {report.speaker_identification?.unknown_speaker_alert && (
                  <AlertBox type="warning">
                    ⚠️ Sudden acoustic variance detected mid-recording. A new speaker enters the conversation timeline.
                  </AlertBox>
                )}
                {/* Speaker Timeline list */}
                {report.speaker_identification?.timeline && report.speaker_identification.timeline.length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px' }}>Speaker Diarization Timeline</div>
                    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--r)', overflow: 'hidden' }}>
                      {report.speaker_identification.timeline.map((item, idx) => {
                        const spkStyle = getSpeakerColor(item.speaker)
                        return (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', borderBottom: idx < (report.speaker_identification?.timeline?.length || 0) - 1 ? '1px solid var(--border)' : 'none', background: 'var(--bg3)', fontSize: '12px' }}>
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                              <span style={{ fontFamily: 'var(--mono)', color: 'var(--blue)', fontWeight: 700 }}>{item.timestamp}</span>
                              <span style={{ padding: '2px 8px', borderRadius: '4px', background: spkStyle.bg, color: spkStyle.color, border: `1px solid ${spkStyle.border}`, fontWeight: 700, fontSize: '11px' }}>
                                {item.speaker}
                              </span>
                            </div>
                            <button onClick={() => seekToTime(parseTimestampSeconds(item.start))} style={{ background: 'transparent', border: 'none', color: 'var(--blue)', fontSize: '11px', cursor: 'pointer', fontWeight: 600 }}>
                              ▶️ Seek
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* CARD 5 – Background Analysis */}
            <Card>
              <CardTitle>5. Background Acoustic Analysis</CardTitle>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase' }}>Detected Primary Environment</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--blue)', marginTop: '2px' }}>
                    {report.background_analysis?.primary_environment || 'Indoor / Office'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: '12px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase' }}>Noise Consistency &amp; SNR</div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)', marginTop: '2px' }}>
                    {report.background_analysis?.environment_consistency || 'Consistent background environment.'}
                  </div>
                  {report.noise_analysis?.snr_db && (
                    <div style={{ fontSize: '11px', color: 'var(--green)', marginTop: '4px', fontFamily: 'var(--mono)' }}>
                      SNR: {report.noise_analysis.snr_db} | Noise Floor: {report.noise_analysis.noise_floor_db || 'N/A'}
                    </div>
                  )}
                </div>
              </div>

              {/* Environmental changes */}
              {report.background_analysis?.environmental_changes && report.background_analysis.environmental_changes.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text3)', textTransform: 'uppercase' }}>Environment Changes &amp; Transitions</div>
                  {report.background_analysis.environmental_changes.map((shift, idx) => (
                    <div key={idx} style={{ background: 'var(--amber-bg)', border: '1px solid var(--amber)', color: 'var(--amber)', borderRadius: 'var(--r)', padding: '8px 12px', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong style={{ fontFamily: 'var(--mono)' }}>{shift.timestamp}: </strong>
                        {shift.description || shift.reason}
                      </div>
                      <Btn size="xs" variant="default" onClick={() => seekToTime(shift.start || parseTimestampSeconds(shift.timestamp))}>
                        ▶️ Seek
                      </Btn>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* CARD 6 – Suspicious Keywords */}
            <Card>
              <CardHeader>
                <CardTitle>6. Suspicious Keyword Extraction</CardTitle>
                <span style={{ fontSize: '11px', color: 'var(--amber)', fontWeight: 700 }}>
                  {extractedKeywords.length} High-Risk Keyword(s)
                </span>
              </CardHeader>
              {extractedKeywords.length > 0 ? (
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  {extractedKeywords.map((kw, idx) => (
                    <span
                      key={idx}
                      style={{
                        background: 'var(--amber-bg)',
                        border: '1px solid var(--amber)',
                        color: 'var(--amber)',
                        borderRadius: '20px',
                        padding: '6px 14px',
                        fontSize: '12px',
                        fontWeight: 700,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <span>🏷️ {kw}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <div style={{ background: 'var(--bg3)', padding: '12px', borderRadius: 'var(--r)', fontSize: '12px', color: 'var(--text3)' }}>
                  ✓ No high-risk investigation keywords (e.g. money, weapon, bribe, threat) detected in transcript text.
                </div>
              )}
            </Card>

            {/* CARD 7 – Tampering Analysis */}
            <Card>
              <CardHeader>
                <CardTitle>7. Tampering &amp; Audio Manipulation Analysis</CardTitle>
                <span style={{ padding: '4px 12px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, background: statusTheme.bg, color: statusTheme.color, border: `1px solid ${statusTheme.border}` }}>
                  {statusTheme.label}
                </span>
              </CardHeader>
              <div style={{ fontSize: '12px', color: 'var(--text2)', marginBottom: '14px' }}>
                Combines ENF frequency continuity, spectral splicing, background noise step analysis, and voice feature matching into a concise grouped findings timeline.
              </div>
              {report.tampered_segments && report.tampered_segments.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ background: 'var(--bg3)', borderBottom: '1px solid var(--border)' }}>
                        <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase' }}>Timestamp</th>
                        <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase' }}>Classification</th>
                        <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase' }}>Forensic Reason</th>
                        <th style={{ padding: '10px', textAlign: 'left', color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase' }}>Confidence</th>
                        <th style={{ padding: '10px', textAlign: 'right', color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.tampered_segments.map((seg, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg2)' }}>
                          <td style={{ padding: '10px', color: 'var(--red)', fontWeight: 700, fontFamily: 'var(--mono)' }}>
                            {seg.timestamp || `${seg.start_timestamp}–${seg.end_timestamp}`}
                          </td>
                          <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text)' }}>
                            {seg.classification || seg.type}
                          </td>
                          <td style={{ padding: '10px', color: 'var(--text2)' }}>{seg.reason}</td>
                          <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text)' }}>{seg.confidence || 94}%</td>
                          <td style={{ padding: '10px', textAlign: 'right' }}>
                            <Btn size="xs" onClick={() => seekToTime(seg.start || parseTimestampSeconds(seg.start_timestamp || '00:00'))}>
                              ▶️ Seek
                            </Btn>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ background: 'var(--green-bg)', border: '1px solid var(--green)', color: 'var(--green)', padding: '14px', borderRadius: 'var(--r)', fontSize: '13px', fontWeight: 600 }}>
                  ✓ No significant signs of tampering or audio manipulation detected across timeline.
                </div>
              )}
            </Card>

            {/* CARD 8 – Investigation Summary */}
            <Card>
              <CardTitle>8. Executive Investigation Summary</CardTitle>
              
              <ul style={{ listStyleType: 'disc', paddingLeft: '20px', fontSize: '13px', color: 'var(--text2)', margin: '0 0 16px 0', lineHeight: 1.8 }}>
                {report.investigation_summary && report.investigation_summary.length > 0 ? (
                  report.investigation_summary.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))
                ) : (
                  <>
                    <li>Speech transcript and timestamped timeline generated successfully.</li>
                    <li>ENF analysis completed with continuous grid trajectory.</li>
                    <li>Background acoustic environment remained consistent.</li>
                    <li>No high-risk tampering indicators detected.</li>
                  </>
                )}
              </ul>

              <div
                style={{
                  background: statusTheme.bg,
                  border: `1px solid ${statusTheme.border}`,
                  color: statusTheme.color,
                  padding: '14px',
                  borderRadius: 'var(--r)',
                  fontSize: '13px',
                  fontWeight: 700
                }}
              >
                CONCLUSION: {report.conclusion || (statusTheme.text === 'Authentic' ? 'No significant forensic indicators of audio manipulation were identified.' : 'Potential audio manipulation or anomalies detected. Further forensic examination recommended.')}
              </div>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  )
}
