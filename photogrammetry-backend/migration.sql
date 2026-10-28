-- Create photogrammetry_models table
CREATE TABLE IF NOT EXISTS photogrammetry_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
    model_url TEXT,
    point_cloud_url TEXT,
    status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Processing', 'Completed', 'Failed')),
    frame_count INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE photogrammetry_models ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE photogrammetry_models ADD COLUMN IF NOT EXISTS current_step INT DEFAULT 0;
ALTER TABLE photogrammetry_models ALTER COLUMN status SET DEFAULT 'Pending';
-- Older deployments used PostgreSQL's auto-generated constraint name.
-- Drop it as well as the named form before installing the current status set.
ALTER TABLE photogrammetry_models DROP CONSTRAINT IF EXISTS photogrammetry_models_status_check;
ALTER TABLE photogrammetry_models DROP CONSTRAINT IF EXISTS chk_photogrammetry_models_status;
ALTER TABLE photogrammetry_models ADD CONSTRAINT chk_photogrammetry_models_status CHECK (status IN ('Pending', 'Processing', 'Completed', 'Failed'));

-- Disable Row Level Security (RLS) to match other tables in this project
ALTER TABLE photogrammetry_models DISABLE ROW LEVEL SECURITY;
