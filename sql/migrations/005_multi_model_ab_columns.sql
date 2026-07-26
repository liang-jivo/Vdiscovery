-- 005_multi_model_ab_columns.sql
-- Supports A/B testing enrichment across multiple models (gpt-5.4-nano,
-- gpt-5.4-mini, gpt-5.6-luna) instead of only gpt-4o-mini.
--
-- reasoning_tokens: GPT-5.x are reasoning models. Verified 2026-07-26 against
--   the live API: usage.completion_tokens_details.reasoning_tokens is present
--   on all three. Reasoning tokens bill at the OUTPUT rate, so they must be
--   visible before committing to a full 5,400-company run.
--   (gpt-4o-mini reports the field too, but always 0.)
--
-- gate_result_note: side-channel for problems that are not classification
--   outcomes. Currently only 'pricing_unknown' -- written when the model that
--   actually ran has no MODEL_PROFILES entry, in which case cost_usd is left
--   NULL rather than guessed at another model's rates.

ALTER TABLE enrichment_runs
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS gate_result_note TEXT;

-- Rebuilt rather than CREATE OR REPLACE: replace can only append columns at the
-- end, and the new ones belong beside their siblings. Nothing depends on this
-- view, so the drop is safe.
DROP VIEW IF EXISTS enrichment_analysis;

CREATE VIEW enrichment_analysis AS
SELECT er.id AS run_id,
       er.created_at,
       er.prompt_version,
       er.model,
       stb.company_name,
       stb.country,
       stb.source_table,
       stb.input_type,
       er.input_sources,
       er.gate_result,
       er.gate_result_note,
       er.input_tokens,
       er.output_tokens,
       er.reasoning_tokens,
       er.cache_read_tokens,
       er.cache_creation_tokens,
       er.cost_usd,
       er.parsed_capabilities ->> 'company_type'   AS company_type,
       jsonb_array_length(COALESCE(er.parsed_capabilities -> 'capabilities_passed', '[]'::jsonb)) AS n_passed,
       jsonb_array_length(COALESCE(er.parsed_capabilities -> 'capabilities_below',  '[]'::jsonb)) AS n_below,
       jsonb_array_length(COALESCE(er.parsed_capabilities -> 'unmatched_claims',    '[]'::jsonb)) AS n_unmatched,
       er.parsed_capabilities
FROM enrichment_runs er
JOIN staging_test_batch stb ON stb.id = er.staging_row_id;
