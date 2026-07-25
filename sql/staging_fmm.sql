CREATE TABLE IF NOT EXISTS staging_fmm (
    id                BIGSERIAL PRIMARY KEY,
    registration_no   TEXT UNIQUE NOT NULL,
    company_name      TEXT,
    phone             TEXT,
    address           TEXT,
    website           TEXT,
    source_site       TEXT DEFAULT 'fmm-malaysia',
    raw_html_path     TEXT,
    raw               JSONB,
    scraped_at        TIMESTAMP DEFAULT NOW(),
    enrichment_status TEXT DEFAULT 'pending'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_fmm_registration_no
    ON staging_fmm (registration_no);
