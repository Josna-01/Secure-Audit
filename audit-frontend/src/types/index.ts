// ── AUTH ──────────────────────────────────────────────────────────────────
export interface User {
  id: string
  name: string
  full_name?: string
  email: string
  badge_id: string
  badge_number?: string
  department: string
  role: string
  is_active?: boolean
  clearance_level?: string | number
  status: 'active' | 'pending' | 'suspended' | string
  phone?: string
  last_login?: string
  last_sign_in_at?: string
  created_at: string
  must_change_password?: boolean
  can_create_case?: boolean
}


export interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
}

// ── CASES ─────────────────────────────────────────────────────────────────
export type CaseStatus = 'Active' | 'Open' | 'Pending' | 'Critical' | 'Closed'
export type CasePriority = 'Critical' | 'High' | 'Medium' | 'Low'

export interface Victim {
  id?: string
  name: string
  age?: string
  contact?: string
}

export interface Suspect {
  id?: string
  name: string
  description?: string
  address?: string
}

export interface Case {
  id: string
  case_number: string
  title: string
  offence_type: string
  status: CaseStatus
  priority: CasePriority
  fir_description: string
  fir_description_original?: string
  fir_language?: string
  complainant_name: string
  complainant_contact?: string
  victims: Victim[]
  suspects: Suspect[]
  incident_date?: string
  incident_time?: string
  incident_location?: string
  investigator_id: string
  investigator_name?: string
  created_by: string
  created_by_name?: string
  created_at: string
  updated_at: string
}

export interface CreateCasePayload {
  title: string
  offence_type: string
  fir_description: string
  fir_language?: string
  complainant_name: string
  complainant_contact?: string
  victims: Victim[]
  suspects: Suspect[]
  incident_date?: string
  incident_time?: string
  incident_location?: string
}

// ── EVIDENCE ──────────────────────────────────────────────────────────────
export type EvidenceStatus = 'Verified' | 'Tampered' | 'Processing'
export type EvidenceType = 'Image' | 'Video' | 'Audio' | 'Document' | 'FIR'

export interface Evidence {
  id: string
  case_id: string
  case_title?: string
  file_name: string
  file_type: EvidenceType
  file_size: number
  file_path: string
  sha256_hash: string
  status: EvidenceStatus
  uploaded_by: string
  uploaded_at: string
  description?: string
  language?: string
}

// ── DETECTION ─────────────────────────────────────────────────────────────
export interface DetectionObject {
  label: string
  confidence: number
  bbox: [number, number, number, number]
}

export interface DetectionResult {
  id: string
  case_id: string
  evidence_id: string
  objects: DetectionObject[]
  annotated_image_path?: string
  image_url?: string
  processed_at: string
  model_version: string
}

// ── BNS ───────────────────────────────────────────────────────────────────
export interface BNSSection {
  section_id: string
  name: string
  meaning: string
}

export interface BNSResult {
  crime_type: string
  bns?: BNSSection[]
  sections?: BNSSection[]
}

// ── AUDIT LOG ─────────────────────────────────────────────────────────────
export interface AuditLog {
  id: string
  user_id: string
  user_name: string
  user_role?: string
  action: string
  status?: string
  case_id?: string
  case_number?: string
  case_title?: string
  file_hash?: string
  metadata?: Record<string, unknown>
  created_at: string
  date?: string
  time?: string
}

// ── NOTIFICATIONS ─────────────────────────────────────────────────────────
export type NotificationType = 'tamper' | 'bns' | 'upload' | 'yolo' | 'system'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  description: string
  case_id?: string
  read: boolean
  created_at: string
}

// ── PERSONAL NOTES ────────────────────────────────────────────────────────
export interface PersonalNote {
  id: string
  user_id: string
  title: string
  content: string
  tags: string[]
  sketch_data?: string
  created_at: string
  updated_at: string
}

// ── STORYBOARD ────────────────────────────────────────────────────────────
export interface StoryboardStep {
  step: number
  label: string
  content: string
}

export interface Storyboard {
  case_id: string
  steps: StoryboardStep[]
  conclusion: string
  evidence_insights: string[]
  generated_at: string
}

// ── API ───────────────────────────────────────────────────────────────────
export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}
