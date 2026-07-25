UPDATE staging_factlink
SET source_site = 'fact-link-vietnam',
    source_category_id = '012',
    source_category_label = 'Plastic Injection'
WHERE source_category_id IS NULL;
