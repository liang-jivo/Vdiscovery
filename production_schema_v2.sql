-- ============================================================================
-- JIVO Supplier Discovery Platform — Production Schema v2.0
-- Postgres 14+ (Supabase / Railway compatible)
--
-- v2.0 changes vs v1.0:
--   SUPPLY SIDE (revised)
--   * companies: registration_number now nullable (partial unique index),
--     added domain dedup key, name_normalized, soft delete, full-text search
--   * NEW facilities table (multi-site suppliers)
--   * company_capabilities: optional facility_id, soft delete
--   * certifications: optional facility_id, soft delete
--   PLATFORM SIDE (new)
--   * users, claims (vendor claim workflow)
--   * buyer_profiles, inquiries (leads — the monetization spine)
--   * buyer_searches (demand signal + vocabulary gap detection)
--   INFRASTRUCTURE (new)
--   * audit_log (change history)
--   * pg_trgm full-text/fuzzy search indexes
--   * soft-delete convention (deleted_at + partial indexes)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy name search & dedup
CREATE EXTENSION IF NOT EXISTS unaccent;     -- normalize accented names

-- ============================================================================
-- SECTION A: SUPPLY SIDE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- A1. companies — core supplier identity
-- ----------------------------------------------------------------------------
CREATE TABLE companies (
  id SERIAL PRIMARY KEY,

  -- Identity
  legal_name VARCHAR(500) NOT NULL,
  name_normalized VARCHAR(500),           -- lowercased, unaccented, suffix-stripped
                                          -- ("Precision Dynamics Sdn Bhd" -> "precision dynamics")
                                          -- populated by ingestion; used for fuzzy dedup candidates
  aliases TEXT[],
  registration_number VARCHAR(100),       -- NULLABLE now: scraped rows often lack it.
                                          -- Uniqueness enforced via partial index below.
  domain VARCHAR(255),                    -- normalized website domain ("precisiondynamics.com.my")
                                          -- secondary dedup key
  country VARCHAR(2) NOT NULL,
  website VARCHAR(500),

  -- Firmographics
  year_founded INT,
  headcount_band VARCHAR(20),
  annual_revenue_band VARCHAR(20),
  ownership VARCHAR(50),

  -- Export readiness
  export_markets VARCHAR(500),
  customer_references_count INT DEFAULT 0,
  has_english_documentation BOOLEAN DEFAULT FALSE,
  incoterms_experience VARCHAR(500),

  -- Clustering & navigation
  primary_cluster VARCHAR(50),
  primary_output VARCHAR(50)
    CHECK (primary_output IS NULL OR primary_output IN
      ('machined_parts','molded_parts','stamped_parts','cast_parts','forged_parts',
       'tooling','assemblies','machines_equipment','complete_products')),
  secondary_clusters VARCHAR(500),

  -- Claim & verification (state derived from claims table; cached here for fast filtering)
  claim_status VARCHAR(20) DEFAULT 'unclaimed'
    CHECK (claim_status IN ('unclaimed','claimed','verified')),

  -- Provenance
  source_url TEXT,
  extracted_at TIMESTAMP DEFAULT NOW(),
  last_verified TIMESTAMP,
  confidence_score DECIMAL(3,2) DEFAULT 0.5,
  data_quality_notes TEXT,

  -- Full-text search vector (name + aliases), maintained by trigger below
  search_vec TSVECTOR,

  -- Lifecycle
  deleted_at TIMESTAMP,                   -- soft delete: NULL = live
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Dedup: registration number unique WHEN present and row is live
CREATE UNIQUE INDEX uq_companies_registration
  ON companies (country, registration_number)
  WHERE registration_number IS NOT NULL AND deleted_at IS NULL;

-- Dedup: domain unique when present (corporate groups sharing a domain: resolve
-- in pipeline, or drop this index and rely on pipeline-level review)
CREATE UNIQUE INDEX uq_companies_domain
  ON companies (domain)
  WHERE domain IS NOT NULL AND deleted_at IS NULL;

-- Fuzzy dedup candidates + name search
CREATE INDEX idx_companies_name_trgm
  ON companies USING GIN (name_normalized gin_trgm_ops);
CREATE INDEX idx_companies_search_vec ON companies USING GIN (search_vec);

-- Filtering (partial: exclude soft-deleted rows from hot paths)
CREATE INDEX idx_companies_country ON companies(country) WHERE deleted_at IS NULL;
CREATE INDEX idx_companies_cluster ON companies(primary_cluster) WHERE deleted_at IS NULL;
CREATE INDEX idx_companies_output ON companies(primary_output) WHERE deleted_at IS NULL;
CREATE INDEX idx_companies_claim ON companies(claim_status) WHERE deleted_at IS NULL;

-- Maintain search_vec automatically
CREATE OR REPLACE FUNCTION companies_search_vec_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vec :=
    setweight(to_tsvector('simple', unaccent(coalesce(NEW.legal_name,''))), 'A') ||
    setweight(to_tsvector('simple', unaccent(coalesce(array_to_string(NEW.aliases,' '),''))), 'B');
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_companies_search_vec
  BEFORE INSERT OR UPDATE OF legal_name, aliases ON companies
  FOR EACH ROW EXECUTE FUNCTION companies_search_vec_update();

-- ----------------------------------------------------------------------------
-- A2. facilities — physical sites (capabilities live where the machines are)
-- ----------------------------------------------------------------------------
-- MVP rule: every company gets ONE facility auto-created at ingestion
-- (is_primary = true, copied from company address fields). Multi-site suppliers
-- get additional rows as discovered. This keeps ingestion simple while making
-- the schema correct from day one.
CREATE TABLE facilities (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

  name VARCHAR(255),                      -- "HQ / Penang plant" (NULL ok for single-site)
  is_primary BOOLEAN DEFAULT TRUE,
  address TEXT,
  city VARCHAR(200),
  country VARCHAR(2),
  geo_cluster VARCHAR(100),               -- Penang, Rayong, Batam, VSIP...
  latitude DECIMAL(9,6),
  longitude DECIMAL(9,6),
  floor_area_sqm INT,
  cleanroom_class VARCHAR(20),

  deleted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_facilities_company ON facilities(company_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_facilities_geo ON facilities(geo_cluster) WHERE deleted_at IS NULL;
-- One primary facility per live company
CREATE UNIQUE INDEX uq_facilities_primary
  ON facilities (company_id) WHERE is_primary = TRUE AND deleted_at IS NULL;

-- ----------------------------------------------------------------------------
-- A3. capabilities — controlled vocabulary (unchanged from v1.0)
-- ----------------------------------------------------------------------------
CREATE TABLE capabilities (
  id SERIAL PRIMARY KEY,
  cluster VARCHAR(50) NOT NULL,
  name VARCHAR(255) NOT NULL UNIQUE,
  category VARCHAR(100) NOT NULL
    CHECK (category IN ('process','capability_attribute','material','certification',
                        'specialization','equipment','integration_scope')),
  description TEXT,
  synonyms VARCHAR(1000),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_capabilities_cluster ON capabilities(cluster) WHERE is_active;

-- ----------------------------------------------------------------------------
-- A4. company_capabilities — capability claims (junction with attributes)
-- ----------------------------------------------------------------------------
CREATE TABLE company_capabilities (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  facility_id INT REFERENCES facilities(id) ON DELETE SET NULL,
      -- NULL = "company-level claim, site unknown" (typical for scraped data)
      -- set when we know which plant has the capability
  capability_id INT NOT NULL REFERENCES capabilities(id) ON DELETE RESTRICT,

  parameters JSONB DEFAULT '{}',
  evidence_type VARCHAR(50)
    CHECK (evidence_type IN ('equipment_list','website_claim','customer_reference',
                             'cert_required','scraped_inference','vendor_claimed')),
  evidence_url TEXT,

  verified BOOLEAN DEFAULT FALSE,
  verified_by INT,                        -- users.id (FK added after users table)
  verified_at TIMESTAMP,
  source_confidence DECIMAL(3,2) DEFAULT 0.5,

  deleted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- One claim per (company, capability, site) — NULL site treated as one bucket
CREATE UNIQUE INDEX uq_company_capability
  ON company_capabilities (company_id, capability_id, COALESCE(facility_id, 0))
  WHERE deleted_at IS NULL;

CREATE INDEX idx_cc_company ON company_capabilities(company_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cc_capability ON company_capabilities(capability_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cc_params ON company_capabilities USING GIN (parameters);

-- ----------------------------------------------------------------------------
-- A5. certifications — time-indexed, verifiable credentials
-- ----------------------------------------------------------------------------
CREATE TABLE certifications (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  facility_id INT REFERENCES facilities(id) ON DELETE SET NULL,  -- certs are often site-scoped

  cert_type VARCHAR(100) NOT NULL,        -- controlled list in app config:
                                          -- ISO_9001, IATF_16949, AS9100, ISO_13485,
                                          -- ASME_U, ASME_U2, ASME_S, NB_R, ASME_IX,
                                          -- UL508A, UL_RECOGNIZED, IPC_JSTD001,
                                          -- IEC_61439, ATEX_IECEX, PED_CE, FDA_REG, NADCAP
  issuer VARCHAR(200),
  issued_date DATE,
  expiry_date DATE,
  -- "is currently valid" is NOT a stored/generated column: STORED generated
  -- columns require an IMMUTABLE expression (NOW() isn't), and even if they
  -- allowed it, a stored value wouldn't flip on its own the moment expiry_date
  -- passes. Compute it at query time instead: expiry_date IS NULL OR
  -- expiry_date > CURRENT_DATE (see D1 below).

  certificate_url TEXT,
  scope TEXT,
  verified BOOLEAN DEFAULT FALSE,
  verified_by INT,
  verified_at TIMESTAMP,

  deleted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cert_company ON certifications(company_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cert_type ON certifications(cert_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_cert_expiry ON certifications(expiry_date) WHERE deleted_at IS NULL;

-- ----------------------------------------------------------------------------
-- A6. sources + company_sources — crawl freshness (unchanged from v1.0)
-- ----------------------------------------------------------------------------
CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  source_type VARCHAR(50) NOT NULL
    CHECK (source_type IN ('company_website','gov_registry','directory_listing',
                           'customs_import','cert_registry','manual')),
  country VARCHAR(2),
  last_crawled_at TIMESTAMP,
  is_stale BOOLEAN DEFAULT FALSE,
  crawl_interval_days INT DEFAULT 30,
  extraction_method VARCHAR(50),
  companies_found INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE company_sources (
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  source_id INT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  PRIMARY KEY (company_id, source_id)
);

-- ============================================================================
-- SECTION B: PLATFORM SIDE (users, claims, buyers, leads, demand signal)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- B1. users — everyone who logs in (vendors, buyers, admins)
-- ----------------------------------------------------------------------------
-- NOTE (Supabase): if using Supabase Auth, auth.users holds credentials;
-- make this a "profiles" table with id UUID REFERENCES auth.users(id) and
-- drop password_hash. Structure below assumes self-managed auth on Railway.
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(320) NOT NULL,
  password_hash VARCHAR(255),             -- NULL if using external auth provider
  full_name VARCHAR(255),
  role VARCHAR(20) NOT NULL DEFAULT 'buyer'
    CHECK (role IN ('buyer','vendor','admin')),
  email_verified BOOLEAN DEFAULT FALSE,
  company_id INT REFERENCES companies(id) ON DELETE SET NULL,
      -- set for vendor users after an approved claim
  last_login_at TIMESTAMP,
  deleted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_users_email ON users (lower(email)) WHERE deleted_at IS NULL;

-- Now wire up the verified_by FKs deferred earlier
ALTER TABLE company_capabilities
  ADD CONSTRAINT fk_cc_verified_by FOREIGN KEY (verified_by) REFERENCES users(id);
ALTER TABLE certifications
  ADD CONSTRAINT fk_cert_verified_by FOREIGN KEY (verified_by) REFERENCES users(id);

-- ----------------------------------------------------------------------------
-- B2. claims — vendor claim workflow (replaces bare claim_status mutation)
-- ----------------------------------------------------------------------------
-- Flow: vendor user submits claim -> admin reviews evidence -> approve/reject.
-- On approval: users.company_id set, companies.claim_status updated to 'claimed'
-- (and later 'verified' after data verification).
CREATE TABLE claims (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  status VARCHAR(20) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','rejected')),
  evidence TEXT,                          -- "email domain matches website", uploaded doc ref, etc.
  requested_at TIMESTAMP DEFAULT NOW(),
  reviewed_by INT REFERENCES users(id),
  reviewed_at TIMESTAMP,
  review_notes TEXT
);

CREATE INDEX idx_claims_company ON claims(company_id);
CREATE INDEX idx_claims_status ON claims(status);
-- Only one pending claim per company at a time
CREATE UNIQUE INDEX uq_claims_pending ON claims(company_id) WHERE status = 'pending';

-- ----------------------------------------------------------------------------
-- B3. buyer_profiles — who is sourcing (demand-side identity)
-- ----------------------------------------------------------------------------
CREATE TABLE buyer_profiles (
  user_id INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  company_name VARCHAR(255),
  country VARCHAR(2),
  industry VARCHAR(100),
  sourcing_categories TEXT[],             -- clusters they source: ['precision_metal', ...]
  headcount_band VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- B4. inquiries — leads: buyer contacts supplier (THE monetization spine)
-- ----------------------------------------------------------------------------
CREATE TABLE inquiries (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,   -- the supplier
  buyer_user_id INT REFERENCES users(id) ON DELETE SET NULL,            -- NULL = anonymous/email-only
  buyer_email VARCHAR(320),               -- captured even for non-registered buyers

  subject VARCHAR(500),
  message TEXT,
  attachments JSONB DEFAULT '[]',         -- [{name, url}] if you add uploads later

  -- Attribution: how did this lead originate? (powers "3 RFQs this month" vendor pitch)
  search_id INT,                          -- buyer_searches.id (FK added below)
  origin VARCHAR(30) DEFAULT 'listing_page'
    CHECK (origin IN ('listing_page','search_results','direct_link','outbound')),

  status VARCHAR(20) DEFAULT 'new'
    CHECK (status IN ('new','viewed','responded','closed','spam')),
  responded_at TIMESTAMP,

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inquiries_company ON inquiries(company_id);
CREATE INDEX idx_inquiries_status ON inquiries(status);
CREATE INDEX idx_inquiries_created ON inquiries(created_at DESC);

-- ----------------------------------------------------------------------------
-- B5. buyer_searches — demand signal + vocabulary gap detection
-- ----------------------------------------------------------------------------
-- Log every search (registered or anonymous). Two payoffs:
--   1. Demand data no competitor has for this region ("42 US buyers searched
--      'ASME U-stamp Malaysia' last quarter")
--   2. Zero-result searches = vocabulary gaps or supply gaps -> ingestion targets
CREATE TABLE buyer_searches (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE SET NULL,   -- NULL = anonymous
  session_id VARCHAR(64),                                -- anonymous session tracking

  query_text VARCHAR(500),                -- free-text portion, if any
  filters JSONB DEFAULT '{}',             -- {"country":"MY","cluster":"precision_metal",
                                          --  "capability_ids":[1,14],"cert_types":["ISO_9001"]}
  results_count INT,
  zero_results BOOLEAN GENERATED ALWAYS AS (results_count = 0) STORED,

  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_searches_created ON buyer_searches(created_at DESC);
CREATE INDEX idx_searches_zero ON buyer_searches(zero_results) WHERE zero_results;

ALTER TABLE inquiries
  ADD CONSTRAINT fk_inquiries_search FOREIGN KEY (search_id) REFERENCES buyer_searches(id);

-- ============================================================================
-- SECTION C: INFRASTRUCTURE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- C1. audit_log — who changed what, when, why
-- ----------------------------------------------------------------------------
-- Populated by application code (or triggers later) on UPDATE/DELETE of
-- companies, company_capabilities, certifications, claims.
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  table_name VARCHAR(64) NOT NULL,
  row_id INT NOT NULL,
  field VARCHAR(64),
  old_value TEXT,
  new_value TEXT,
  changed_by INT REFERENCES users(id),    -- NULL = pipeline/system change
  change_source VARCHAR(30) DEFAULT 'app'
    CHECK (change_source IN ('app','pipeline','admin','vendor_edit','migration')),
  reason TEXT,
  changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_row ON audit_log(table_name, row_id);
CREATE INDEX idx_audit_time ON audit_log(changed_at DESC);

-- ----------------------------------------------------------------------------
-- C2. updated_at maintenance (apply to all tables with updated_at)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['companies','facilities','capabilities',
    'company_capabilities','certifications','sources','users',
    'buyer_profiles','inquiries']
  LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t, t);
  END LOOP;
END $$;

-- ============================================================================
-- SECTION D: OPERATIONAL QUERIES (reference)
-- ============================================================================

-- D1. Buyer search: MY precision metal shops, 5-axis, current ISO 9001, live rows only
-- SELECT c.id, c.legal_name, c.confidence_score
-- FROM companies c
-- JOIN company_capabilities cc ON cc.company_id = c.id AND cc.deleted_at IS NULL
-- JOIN capabilities cap ON cap.id = cc.capability_id AND cap.name = 'CNC milling — 5-axis'
-- JOIN certifications ct ON ct.company_id = c.id AND ct.deleted_at IS NULL
--   AND ct.cert_type = 'ISO_9001' AND (ct.expiry_date IS NULL OR ct.expiry_date > CURRENT_DATE)
-- WHERE c.country = 'MY' AND c.deleted_at IS NULL
-- ORDER BY c.confidence_score DESC;

-- D2. Vendor dashboard: "your leads this month" (the renewal pitch)
-- SELECT count(*) FROM inquiries
-- WHERE company_id = $1 AND created_at > date_trunc('month', now());

-- D3. Vocabulary gaps: top zero-result searches last 30 days
-- SELECT query_text, filters, count(*) AS times
-- FROM buyer_searches
-- WHERE zero_results AND created_at > now() - interval '30 days'
-- GROUP BY query_text, filters ORDER BY times DESC LIMIT 20;

-- D4. Fuzzy dedup candidates for a new ingested name
-- SELECT id, legal_name, similarity(name_normalized, $1) AS sim
-- FROM companies
-- WHERE deleted_at IS NULL AND name_normalized % $1   -- pg_trgm similarity operator
-- ORDER BY sim DESC LIMIT 5;

-- D5. Free-text company search (name/alias)
-- SELECT id, legal_name FROM companies
-- WHERE deleted_at IS NULL
--   AND search_vec @@ plainto_tsquery('simple', unaccent($1))
-- LIMIT 20;

-- ============================================================================
-- DEPLOYMENT ORDER
-- 1. Extensions -> Section A -> Section B -> Section C (this file runs top-to-bottom)
-- 2. Seed capabilities vocabulary (~103 launch terms)
-- 3. Create one admin user
-- 4. Ingestion pipeline writes: companies -> facilities (auto primary) ->
--    company_capabilities -> certifications -> sources/company_sources
-- 5. App enforces: cert_type list, cluster names (app-level constants)
-- ============================================================================
