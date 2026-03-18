-- =============================================================================
-- Migration 03 — Scrape jobs + auto_scrape sur sources
-- =============================================================================

ALTER TABLE sources ADD COLUMN IF NOT EXISTS auto_scrape            BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS scrape_interval_hours  INT     NOT NULL DEFAULT 24;

DO $$ BEGIN
  CREATE TYPE scrape_job_status AS ENUM ('pending', 'running', 'done', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS scrape_jobs (
  id           SERIAL PRIMARY KEY,
  source_id    INTEGER REFERENCES sources(id) ON DELETE SET NULL,
  url          TEXT,
  job_type     VARCHAR(50) NOT NULL DEFAULT 'url',   -- 'url' | 'youtube' | 'auto'
  status       scrape_job_status NOT NULL DEFAULT 'pending',
  nb_inserted  INTEGER NOT NULL DEFAULT 0,
  preview_text TEXT,          -- transcript YouTube avant confirmation
  error_msg    TEXT,
  started_at   TIMESTAMPTZ,
  finished_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status  ON scrape_jobs (status);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_source  ON scrape_jobs (source_id);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_created ON scrape_jobs (created_at DESC);
