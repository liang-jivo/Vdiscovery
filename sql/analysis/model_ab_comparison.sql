-- model_ab_comparison.sql
-- A/B analysis for the enrichment pipeline across models, at a fixed
-- prompt_version. Reads the enrichment_analysis view (see migration 005).
--
-- Both queries share two guards:
--   latest -- one row per (company, model). A re-run of the same company on the
--             same model would otherwise double-count. Newest wins.
--   common -- restricts to companies EVERY model in the set actually processed.
--             Without this, a model that errored on the hard companies looks
--             cheaper and more accurate purely by having skipped them.
--
-- Edit the prompt_version in the params CTE of each query.


-- ============================================================================
-- QUERY 1 -- per-model summary
-- One row per model: volume, gate breakdown, extraction yield, tokens, cost.
-- ============================================================================

WITH params AS (
    SELECT 'v2'::text AS prompt_version
),
latest AS (
    SELECT DISTINCT ON (ea.company_name, ea.model) ea.*
    FROM enrichment_analysis ea, params p
    WHERE ea.prompt_version = p.prompt_version
    ORDER BY ea.company_name, ea.model, ea.created_at DESC
),
common AS (
    SELECT company_name
    FROM latest
    GROUP BY company_name
    HAVING count(DISTINCT model) = (SELECT count(DISTINCT model) FROM latest)
)
SELECT l.model,
       count(*)                                                   AS n_companies,

       count(*) FILTER (WHERE l.gate_result = 'passed')           AS passed,
       count(*) FILTER (WHERE l.gate_result = 'below_threshold')  AS below_threshold,
       count(*) FILTER (WHERE l.gate_result = 'no_signal')        AS no_signal,
       count(*) FILTER (WHERE l.gate_result = 'parse_failed')     AS parse_failed,
       count(*) FILTER (WHERE l.gate_result = 'api_error')        AS api_error,

       -- 'truncated_max_tokens' here means the output cap cut the JSON off and it
       -- was logged as parse_failed. That is a config problem, not a model failure.
       count(*) FILTER (WHERE l.gate_result_note IS NOT NULL)     AS rows_with_note,

       round(avg(l.n_passed), 2)                                  AS avg_passed,
       round(avg(l.n_below), 2)                                   AS avg_below,
       round(avg(l.n_unmatched), 2)                               AS avg_unmatched,

       round(avg(l.input_tokens))                                 AS avg_input_tokens,
       round(avg(l.output_tokens))                                AS avg_output_tokens,
       -- reasoning tokens are already inside output_tokens and bill at the output
       -- rate. This column shows how much of the output spend was reasoning
       round(avg(l.reasoning_tokens))                             AS avg_reasoning_tokens,

       round(avg(l.cost_usd), 8)                                  AS avg_cost_usd,
       round(sum(l.cost_usd), 6)                                  AS total_cost_usd,
       round(avg(l.cost_usd) * 5400, 2)                           AS projected_5400_usd,
       count(*) FILTER (WHERE l.cost_usd IS NULL)                 AS cost_unknown_rows
FROM latest l
JOIN common c USING (company_name)
GROUP BY l.model
ORDER BY total_cost_usd;


-- ============================================================================
-- QUERY 2 -- per company x model, most-contested first
-- Sorted so companies the models disagree about float to the top: first by
-- disagreement on the gate outcome, then on how many capabilities each found.
-- by_model holds one JSON entry per model, including the exact passed terms,
-- so two models' extractions can be read side by side on one line.
-- ============================================================================

WITH params AS (
    SELECT 'v2'::text AS prompt_version
),
latest AS (
    SELECT DISTINCT ON (ea.company_name, ea.model) ea.*
    FROM enrichment_analysis ea, params p
    WHERE ea.prompt_version = p.prompt_version
    ORDER BY ea.company_name, ea.model, ea.created_at DESC
),
common AS (
    SELECT company_name
    FROM latest
    GROUP BY company_name
    HAVING count(DISTINCT model) = (SELECT count(DISTINCT model) FROM latest)
),
per_run AS (
    SELECT l.company_name,
           l.model,
           l.gate_result,
           l.n_passed,
           l.n_below,
           l.n_unmatched,
           l.company_type,
           l.cost_usd,
           COALESCE((SELECT array_agg(x ->> 'term' ORDER BY x ->> 'term')
                     FROM jsonb_array_elements(
                              COALESCE(l.parsed_capabilities -> 'capabilities_passed',
                                       '[]'::jsonb)) x),
                    ARRAY[]::text[]) AS passed_terms
    FROM latest l
    JOIN common c USING (company_name)
)
SELECT company_name,
       count(DISTINCT model)                                AS n_models,
       count(DISTINCT gate_result)                          AS distinct_gates,
       count(DISTINCT n_passed)                             AS distinct_n_passed,
       count(DISTINCT COALESCE(company_type, '~null'))      AS distinct_company_type,
       -- terms at least one model found but not all of them agreed on
       (SELECT count(*) FROM (
            SELECT unnest(passed_terms) AS t
            FROM per_run pr2
            WHERE pr2.company_name = pr.company_name
            GROUP BY 1
            HAVING count(*) <> (SELECT count(DISTINCT model)
                                FROM per_run pr3
                                WHERE pr3.company_name = pr.company_name)
       ) d)                                                 AS n_contested_terms,
       jsonb_object_agg(model, jsonb_build_object(
           'gate',        gate_result,
           'n_passed',    n_passed,
           'n_below',     n_below,
           'n_unmatched', n_unmatched,
           'type',        company_type,
           'cost_usd',    cost_usd,
           'terms',       to_jsonb(passed_terms)
       ) ORDER BY model)                                    AS by_model
FROM per_run pr
GROUP BY company_name
ORDER BY distinct_gates DESC,
         n_contested_terms DESC,
         distinct_n_passed DESC,
         company_name;
