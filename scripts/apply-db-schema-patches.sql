-- Run once if the API errors on missing answers.stale_detected_at (older DB volume).
-- Restarting the backend after upgrade also applies these via app startup.

ALTER TABLE answers ADD COLUMN IF NOT EXISTS potentially_stale BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_detected_at TIMESTAMPTZ;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_reason TEXT;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS regeneration_backup JSONB;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS generation_source VARCHAR(32);
ALTER TABLE answers ADD COLUMN IF NOT EXISTS library_entry_id UUID;
