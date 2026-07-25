CREATE TABLE staging_test_batch (
  id                BIGSERIAL PRIMARY KEY,
  input_type        TEXT NOT NULL CHECK (input_type IN ('directory','domain_only')),
  source_table      TEXT,          -- 'staging_factlink' | 'staging_fmm' | 'manual'
  source_row_id     BIGINT,        -- null for manual entries
  company_name      TEXT NOT NULL,
  country           TEXT,
  website           TEXT,
  staging_text      TEXT,          -- description + produce_list, null for domain_only
  enrichment_status TEXT NOT NULL DEFAULT 'pending' CHECK (enrichment_status IN
    ('pending','in_progress','enriched','low_confidence','no_signal','failed')),
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON staging_test_batch (enrichment_status);

CREATE TABLE crawl_cache (
  url          TEXT PRIMARY KEY,
  markdown     TEXT,
  fetched_at   TIMESTAMPTZ DEFAULT NOW(),
  fetch_status TEXT           -- 'ok' | 'failed'
);

CREATE TABLE enrichment_runs (
  id                    BIGSERIAL PRIMARY KEY,
  staging_table         TEXT NOT NULL,
  staging_row_id        BIGINT NOT NULL,
  input_text            TEXT,
  input_sources         JSONB,        -- {"staging_text": bool, "website_crawl": bool}
  model                 TEXT,
  prompt_version        TEXT,
  raw_response          JSONB,        -- full Claude response body
  parsed_capabilities   JSONB,        -- {capabilities_passed, capabilities_below, certifications, unmatched_claims, company_type, notes}
  gate_result           TEXT CHECK (gate_result IN
    ('passed','below_threshold','parse_failed','api_error','no_signal')),
  input_tokens          INTEGER,
  output_tokens         INTEGER,
  cache_read_tokens      INTEGER,
  cache_creation_tokens  INTEGER,
  cost_usd              NUMERIC(12,8),
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON enrichment_runs (staging_row_id);
CREATE INDEX ON enrichment_runs (prompt_version, gate_result);
