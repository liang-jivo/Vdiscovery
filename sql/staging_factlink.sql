CREATE TABLE IF NOT EXISTS staging_factlink (
    id                    SERIAL PRIMARY KEY,
    profile_id            TEXT UNIQUE NOT NULL,
    company_name          TEXT,
    website               TEXT,
    phone                 TEXT,
    contact_name          TEXT,
    contact_email         TEXT,
    office_address        TEXT,
    factory_address       TEXT,
    business_description  TEXT,
    produce_list          TEXT,
    establish_date        TEXT,
    employee_count        INT,
    certifications        TEXT,
    capital_vnd           TEXT,
    shareholder_name      TEXT,
    parent_company        TEXT,
    raw_html_path         TEXT,
    raw                   JSONB,
    scraped_at            TIMESTAMP DEFAULT NOW(),
    enrichment_status     TEXT DEFAULT 'pending'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_factlink_profile_id
    ON staging_factlink (profile_id);
