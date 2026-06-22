-- Create photogrammetry_models table
CREATE TABLE IF NOT EXISTS photogrammetry_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
    model_url TEXT,
    point_cloud_url TEXT,
    status TEXT DEFAULT 'Processing' CHECK (status IN ('Processing', 'Completed', 'Failed')),
    frame_count INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Disable Row Level Security (RLS) to match other tables in this project
ALTER TABLE photogrammetry_models DISABLE ROW LEVEL SECURITY;
