-- The same company can legitimately appear under multiple FACT-LINK
-- categories (e.g. both "Machining" and "Stamping"); each such listing
-- should be its own row, not overwrite the other. Replace the profile_id-only
-- uniqueness with a composite (profile_id, source_category_id) uniqueness.
--
-- After this migration, COUNT(*) on staging_factlink means "category
-- listings", not "unique companies" -- use COUNT(DISTINCT profile_id) for
-- unique company counts.

ALTER TABLE staging_factlink
    DROP CONSTRAINT IF EXISTS staging_factlink_profile_id_key;

DROP INDEX IF EXISTS idx_staging_factlink_profile_id;

ALTER TABLE staging_factlink
    ADD CONSTRAINT staging_factlink_profile_category_key UNIQUE (profile_id, source_category_id);
