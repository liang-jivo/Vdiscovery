ALTER TABLE staging_factlink
    ADD COLUMN IF NOT EXISTS source_site TEXT DEFAULT 'fact-link-vietnam',
    ADD COLUMN IF NOT EXISTS source_category_id TEXT,
    ADD COLUMN IF NOT EXISTS source_category_label TEXT;
