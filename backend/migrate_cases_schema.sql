-- 1. Add missing columns to cases table (status is deferred)
ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_number TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_by UUID;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_by_name TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Backfill sequential case numbers (SA-YYYY-XXXX) based on created_at year and order
WITH numbered_cases AS (
    SELECT 
        id,
        created_at,
        EXTRACT(YEAR FROM created_at) AS case_year,
        ROW_NUMBER() OVER (PARTITION BY EXTRACT(YEAR FROM created_at) ORDER BY created_at ASC) AS seq
    FROM cases
)
UPDATE cases
SET case_number = 'SA-' || numbered_cases.case_year || '-' || TO_CHAR(numbered_cases.seq, 'FM0000')
FROM numbered_cases
WHERE cases.id = numbered_cases.id AND cases.case_number IS NULL;

-- 3. Create a unique index on case_number to prevent duplicate generation
CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_cases_is_archived ON cases(is_archived);
