import axios, { AxiosInstance } from 'axios'
import type {
  Case, CreateCasePayload, Evidence, DetectionResult,
  BNSResult, AuditLog, Notification, PersonalNote, Storyboard,
  ApiResponse, PaginatedResponse
} from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

class ApiService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,

      timeout: 120000,
      headers: { 'Content-Type': 'application/json' }
    })

    // Attach JWT on every request
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('sa_token')
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })

    // Handle 401 and deactivated 403 globally
    this.client.interceptors.response.use(
      (res) => res,
      (err) => {
        const status = err.response?.status
        const detail = err.response?.data?.detail || ''
        const isAuth = err.config?.url?.includes('/auth/');
        if (!isAuth && (status === 401 || (status === 403 && typeof detail === 'string' && detail.toLowerCase().includes('deactivated')))) {
          localStorage.removeItem('sa_token')
          window.location.href = '/login'
        }
        return Promise.reject(err)
      }
    )
  }

  // ── AUTH ────────────────────────────────────────────────────────────────
  async login(payload: { email: string; password: string; department?: string; role?: string }) {
    const { data } = await this.client.post<ApiResponse<{ token: string; user: object }>>('/auth/login', payload)
    return data
  }

  async sendOTP(email: string, password?: string) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/send-otp', { email, password })
    return data
  }

  async verifyOTP(email: string, otp: string, password?: string) {
    const { data } = await this.client.post<ApiResponse<{ token: string; user: object }>>('/auth/verify-otp', { email, otp, password })
    return data
  }

  async register(payload: {
    name: string; badge_id: string; email: string;
    department: string; phone?: string; password: string
  }) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/register', payload)
    return data
  }

  async forgotPassword(email: string) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/forgot-password', { email })
    return data
  }

  async getMe() {
    const { data } = await this.client.get<ApiResponse<object>>('/auth/me')
    return data
  }

  async logout() {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/logout')
    return data
  }

  async resetPassword(email: string, otp: string, newPassword: string) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/reset-password', { email, otp, new_password: newPassword })
    return data
  }

  async changePassword(newPassword: string) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>('/auth/change-password', { new_password: newPassword })
    return data
  }

  // ── CASES ───────────────────────────────────────────────────────────────
  async getCases(params?: { status?: string; search?: string; page?: number; per_page?: number }) {
    const { data } = await this.client.get<PaginatedResponse<Case>>('/cases', { params })
    return data
  }

  async getCase(id: string) {
    const { data } = await this.client.get<ApiResponse<Case>>(`/cases/${id}`)
    return data
  }

  async createCase(payload: CreateCasePayload) {
    const { data } = await this.client.post<ApiResponse<Case>>('/cases', payload)
    return data
  }

  async updateCase(id: string, payload: Partial<CreateCasePayload>) {
    const { data } = await this.client.patch<ApiResponse<Case>>(`/cases/${id}`, payload)
    return data
  }

  async getCaseStats() {
    const { data } = await this.client.get<ApiResponse<{
      active: number; total_evidence: number; tamper_alerts: number; bns_classified: number
    }>>('/cases/stats')
    return data
  }



  // ── EVIDENCE ────────────────────────────────────────────────────────────
  async getEvidence(caseId?: string) {
    const { data } = await this.client.get<ApiResponse<Evidence[]>>('/evidence', {
      params: caseId ? { case_id: caseId } : undefined
    })
    return data
  }

  async uploadEvidence(caseId: string, file: File, meta: { description?: string; evidence_type: string; language?: string }) {
    const form = new FormData()
    form.append('file', file)
    form.append('case_id', caseId)
    form.append('evidence_type', meta.evidence_type)
    if (meta.description) form.append('description', meta.description)
    if (meta.language) form.append('language', meta.language)
    const { data } = await this.client.post<ApiResponse<Evidence>>('/evidence/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return data
  }

  async verifyHash(evidenceId: string) {
    const { data } = await this.client.post<ApiResponse<{
      verified: boolean; stored_hash: string; computed_hash: string; status: string;
      databaseHash?: string | null; blockchainHash?: string; databaseMatchesBlockchain?: boolean; warnings?: string[]
    }>>(`/evidence/${evidenceId}/verify`)
    return data
  }

  async getEvidenceBlockchain(evidenceId: string) {
    const { data } = await this.client.get<ApiResponse<{ status: any; evidence: import('../types').BlockchainEvidence; custodyHistory: import('../types').CustodyRecord[] }>>(`/evidence/${evidenceId}/blockchain`)
    return data
  }

  async getBlockchainDashboard() {
    const { data } = await this.client.get<ApiResponse<any>>('/blockchain/dashboard')
    return data
  }

  async getBlockchainLedger(params: { search?: string; status?: string; limit?: number; offset?: number } = {}) {
    const { data } = await this.client.get<{ data: import('../types').LedgerRow[]; total: number; limit: number; offset: number }>('/blockchain/ledger', { params })
    return data
  }

  async getBlockchainEvidence(evidenceId: string) {
    const { data } = await this.client.get<ApiResponse<import('../types').LedgerEvidenceDetail>>(`/blockchain/evidence/${evidenceId}`)
    return data
  }

  async getBlockchainTransaction(txHash: string) {
    const { data } = await this.client.get<ApiResponse<import('../types').BlockchainTransaction>>(`/blockchain/transaction/${txHash}`)
    return data
  }

  async getBlockchainNetwork() {
    const { data } = await this.client.get<ApiResponse<any>>('/blockchain/network')
    return data
  }

  async runIntegrityScan() {
    const { data } = await this.client.post<ApiResponse<{ summary: Record<string, number>; items: any[] }>>('/blockchain/integrity-scan')
    return data
  }

  /** Authenticated, audited download; returns the file plus the server's integrity headers. */
  async downloadEvidence(evidenceId: string) {
    const res = await this.client.get<Blob>(`/evidence/${evidenceId}/download`, { responseType: 'blob' })
    return { blob: res.data, sha256: res.headers['x-evidence-sha256'] as string | undefined, integrity: res.headers['x-evidence-integrity'] as string | undefined }
  }

  async redeployEvidenceRegistry() {
    const { data } = await this.client.post<ApiResponse<any>>('/admin/blockchain/redeploy')
    return data
  }

  // ── DETECTION ───────────────────────────────────────────────────────────
  async runDetection(evidenceId: string, caseId: string) {
    const { data } = await this.client.post<ApiResponse<DetectionResult>>('/ai/detect', { evidence_id: evidenceId, case_id: caseId })
    return data
  }

  async getDetectionResults(caseId: string) {
    const { data } = await this.client.get<ApiResponse<DetectionResult[]>>(`/ai/detect/case/${caseId}`)
    return data
  }

  // ── GRAPH ───────────────────────────────────────────────────────────────
  async getCaseGraph(caseId: string) {
    const { data } = await this.client.get<any>(`/cases/${caseId}/graph`)
    return data
  }

  // ── OCR ─────────────────────────────────────────────────────────────────
  async runOCR(evidenceId: string, language?: string,
               options: { translate?: boolean; target_language?: string; force?: boolean } = {}) {
    const { data } = await this.client.post<ApiResponse<{
      success: boolean;
      evidence_id: string;
      language: string;
      confidence: number;
      text: string;
      extracted_text?: string;
      detected_languages?: { code: string; name: string; ratio: number; char_count: number }[];
      total_pages?: number;
      processing_time_ms?: number;
      warnings?: string[];
      cached?: boolean;
      translated_text?: string | null;
      translation?: {
        status: 'success' | 'partial' | 'failed' | 'skipped'; target_language: string; target_language_name?: string;
        source_languages: string[]; providers: string[]; error: string | null; cached?: boolean;
      } | null;
      pages?: {
        page_number: number; text: string; confidence: number; language: string;
        status?: 'success' | 'empty' | 'failed'; warnings?: string[]; translated_text?: string | null;
        raw_text?: string;
        tables?: { rows: string[][]; row_count: number; column_count: number }[];
      }[];
    }>>(`/ai/ocr/${evidenceId}`, { language, ...options }, { timeout: 300000 })
    return data
  }

  async searchOCR(q: string) {
    const { data } = await this.client.get<ApiResponse<any[]>>('/ocr/search', { params: { q } })
    return data
  }

  // ── BNS ─────────────────────────────────────────────────────────────────
  async predictBNS(firText: string, threshold: number = 0.35) {
    const { data } = await this.client.post<any>('/bns/predict', { fir_text: firText, threshold })
    return data
  }

  async storeBNS(caseId: string, result: any, firText: string) {
    const { data } = await this.client.post<any>('/bns/store', { 
      case_id: caseId, 
      crime_type: result.crime_type, 
      sections: result.bns || result.sections,
      fir_text: firText
    })
    return data
  }

  async getBNSResults(caseId: string) {
    const { data } = await this.client.get<any>(`/bns/case/${caseId}`)
    return data
  }

  // ── AUDIO FORENSICS ──────────────────────────────────────────────────────
  async analyzeAudio(file: File) {
    const AUDIO_BASE_URL = import.meta.env.VITE_AUDIO_API_BASE_URL || 'http://localhost:8002'
    const formData = new FormData()
    formData.append('audio', file)
    formData.append('file', file)
    try {
      const res = await axios.post(`${AUDIO_BASE_URL}/audio/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000
      })
      return res.data
    } catch (err: any) {
      if (err.response && err.response.status !== 404) {
        throw err
      }
      // Fallback if backend uses legacy /transcribe route
      const res = await axios.post(`${AUDIO_BASE_URL}/transcribe`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000
      })
      return res.data
    }
  }

  // ── STORYBOARD ──────────────────────────────────────────────────────────
  async generateStoryboard(caseId: string) {
    const { data } = await this.client.post<ApiResponse<Storyboard>>('/ai/storyboard', { case_id: caseId })
    return data
  }

  // ── AUDIT LOG ───────────────────────────────────────────────────────────
  async getAuditLogs(params?: {
    action?: string
    user_id?: string
    case_id?: string
    page?: number
    role?: string
    start_date?: string
    end_date?: string
    search?: string
  }) {
    const { data } = await this.client.get<PaginatedResponse<AuditLog>>('/audit', { params })
    return data
  }

  // ── USER MANAGEMENT (Admin Only) ─────────────────────────────────────────
  async getUsers() {
    const { data } = await this.client.get<ApiResponse<any[]>>('/users')
    return data
  }

  async updateUserAdmin(userId: string, payload: { role?: string; is_active?: boolean; full_name?: string; department?: string; badge_number?: string; clearance_level?: number; can_create_case?: boolean }) {
    const { data } = await this.client.patch<ApiResponse<any>>(`/users/${userId}`, payload)
    return data
  }

  async resetAccess(userId: string) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>(`/users/${userId}/reset-access`)
    return data
  }

  async createUserAdmin(payload: { email: string; password: string; full_name: string; role: string; department: string; badge_number: string; clearance_level?: number }) {
    const { data } = await this.client.post<ApiResponse<any>>('/users', payload)
    return data
  }

  // ── NOTIFICATIONS ────────────────────────────────────────────────────────
  async getNotifications() {
    const { data } = await this.client.get<ApiResponse<Notification[]>>('/notifications')
    return data
  }

  async markNotificationRead(id: string) {
    const { data } = await this.client.patch<ApiResponse<{ message: string }>>(`/notifications/${id}/read`)
    return data
  }

  async markAllNotificationsRead() {
    const { data } = await this.client.patch<ApiResponse<{ message: string }>>('/notifications/read-all')
    return data
  }

  // ── PERSONAL NOTES ───────────────────────────────────────────────────────
  async getNotes() {
    const { data } = await this.client.get<ApiResponse<PersonalNote[]>>('/notes')
    return data
  }

  async createNote(payload: { title: string; content: string; tags: string[]; sketch_data?: string }) {
    const { data } = await this.client.post<ApiResponse<PersonalNote>>('/notes', payload)
    return data
  }

  async updateNote(id: string, payload: Partial<{ title: string; content: string; tags: string[]; sketch_data?: string }>) {
    const { data } = await this.client.patch<ApiResponse<PersonalNote>>(`/notes/${id}`, payload)
    return data
  }

  async deleteNote(id: string) {
    const { data } = await this.client.delete<ApiResponse<{ message: string }>>(`/notes/${id}`)
    return data
  }

  async addNoteToCaseAsNote(noteId: string, caseId: string, options: { include_notes: boolean; include_sketch: boolean; destination: string }) {
    const { data } = await this.client.post<ApiResponse<{ message: string }>>(`/notes/${noteId}/link-to-case`, { case_id: caseId, ...options })
    return data
  }

  // ── PHOTOGRAMMETRY ────────────────────────────────────────────────────────
  async triggerPhotogrammetry(caseId: string, evidenceId: string) {
    // This proxy deliberately returns the microservice job envelope directly.
    const { data } = await this.client.post<{ job_id: string; status: string }>(
      `/photogrammetry/trigger/${caseId}`,
      { evidence_id: evidenceId }
    )
    return data
  }

  async getPhotogrammetryStatus(jobId: string) {
    const { data } = await this.client.get<{
      status: string
      model_url?: string
      point_cloud_url?: string
      frame_count?: number
      created_at?: string
      completed_at?: string
      error_message?: string
      job_id: string
      evidence_id?: string
      current_step?: number
    }>(`/photogrammetry/status/job/${jobId}`)
    return data
  }

  async getPhotogrammetryStatusByCase(caseId: string) {
    const { data } = await this.client.get<{
      status: string
      model_url?: string
      point_cloud_url?: string
      frame_count?: number
      created_at?: string
      completed_at?: string
      error_message?: string
      job_id: string
      evidence_id?: string
      current_step?: number
    }>(`/photogrammetry/status/${caseId}`)
    return data
  }
}

export const api = new ApiService()

/** Human-readable result of POST /evidence/{id}/verify (success or error). */
export function describeVerification(result: { verified: boolean; databaseMatchesBlockchain?: boolean } | null, error?: any): string {
  if (error) {
    const body = error.response?.data
    const detail = typeof body?.detail === 'string' ? body.detail : (error.message || 'Verification failed')
    // Structured failures carry status + reason (e.g. "Verification Failed · BLOCKCHAIN_UNAVAILABLE").
    return body?.status && body?.reason ? `${body.status}: ${detail}` : detail
  }
  if (!result) return 'Verification failed'
  const message = result.verified ? '✓ Integrity verified on-chain' : '⚠ Hash mismatch — tampering detected'
  return result.databaseMatchesBlockchain === false
    ? `${message} · ⚠ Database hash differs from the blockchain record`
    : message
}
