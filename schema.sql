-- Enable pgcrypto extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- 1. USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID NOT NULL,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT,
    badge_number TEXT,
    clearance_level INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    can_create_case BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- ============================================================================
-- 2. CASES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cases (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    offence_type TEXT NOT NULL,
    fir_description TEXT,
    fir_language TEXT DEFAULT 'en',
    complainant_name TEXT,
    complainant_contact TEXT,
    victims JSONB,
    suspects JSONB,
    incident_date DATE,
    incident_time TIME WITHOUT TIME ZONE,
    incident_location TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    case_number TEXT,
    created_by UUID,
    created_by_name TEXT,
    CONSTRAINT pk_cases PRIMARY KEY (id),
    CONSTRAINT fk_cases_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Create unique index for case_number (as per migrate_cases_schema.sql)
CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_cases_created_by ON cases(created_by);

-- ============================================================================
-- 3. EVIDENCE TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS evidence (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    case_id UUID,
    evidence_type TEXT NOT NULL,
    description TEXT,
    file_url TEXT NOT NULL,
    file_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    file_name TEXT,
    file_size BIGINT,
    mime_type TEXT,
    uploaded_by UUID,
    uploaded_by_name TEXT,
    verified_at TIMESTAMPTZ,
    verified_by UUID,
    chain_of_custody_status TEXT DEFAULT 'Collected',
    status TEXT DEFAULT 'Verified',
    CONSTRAINT pk_evidence PRIMARY KEY (id),
    CONSTRAINT fk_evidence_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    CONSTRAINT fk_evidence_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_evidence_verified_by FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_uploaded_by ON evidence(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_evidence_verified_by ON evidence(verified_by);

-- ============================================================================
-- 4. AUDIT LOGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id TEXT, -- Stored as text to decouple from user deletions or external logins
    action TEXT NOT NULL,
    case_id UUID,
    file_hash TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT pk_audit_logs PRIMARY KEY (id),
    CONSTRAINT fk_audit_logs_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_case_id ON audit_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

-- ============================================================================
-- 5. OTP TOKENS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS otp_tokens (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID,
    token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT pk_otp_tokens PRIMARY KEY (id),
    CONSTRAINT fk_otp_tokens_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_otp_tokens_user_id ON otp_tokens(user_id);

-- ============================================================================
-- 6. DETECTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS detections (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    case_id UUID,
    evidence_id UUID,
    image_url TEXT,
    predictions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT pk_detections PRIMARY KEY (id),
    CONSTRAINT fk_detections_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    CONSTRAINT fk_detections_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_detections_case_id ON detections(case_id);
CREATE INDEX IF NOT EXISTS idx_detections_evidence_id ON detections(evidence_id);

-- ============================================================================
-- 7. OCR RESULTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS ocr_results (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    evidence_id UUID,
    extracted_text TEXT NOT NULL,
    language TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    page_number INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT pk_ocr_results PRIMARY KEY (id),
    CONSTRAINT fk_ocr_results_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ocr_results_evidence_id ON ocr_results(evidence_id);

-- ============================================================================
-- 8. BNS PREDICTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS bns_predictions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    crime_type TEXT NOT NULL,
    sections JSONB NOT NULL,
    fir_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT pk_bns_predictions PRIMARY KEY (id),
    CONSTRAINT fk_bns_predictions_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bns_predictions_case_id ON bns_predictions(case_id);

-- ============================================================================
-- 9. PHOTOGRAMMETRY MODELS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS photogrammetry_models (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    case_id UUID,
    evidence_id UUID,
    model_url TEXT,
    point_cloud_url TEXT,
    status TEXT DEFAULT 'Processing',
    frame_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT pk_photogrammetry_models PRIMARY KEY (id),
    CONSTRAINT fk_photogrammetry_models_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    CONSTRAINT fk_photogrammetry_models_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
    CONSTRAINT chk_photogrammetry_models_status CHECK (status IN ('Processing', 'Completed', 'Failed'))
);

CREATE INDEX IF NOT EXISTS idx_photogrammetry_models_case_id ON photogrammetry_models(case_id);
CREATE INDEX IF NOT EXISTS idx_photogrammetry_models_evidence_id ON photogrammetry_models(evidence_id);
