-- Part 4, step 2: the four entry cohorts from data cube 1 (not perturbed).
-- Same figures as Part 1 (headline), Part 2 (division_trend) and Part 3 (state_cohorts).

-- Entrants still trading three Junes after the entry year, by industry division and by state.
-- Each cohort is published in exactly one release, so no de-duplication is needed.
CREATE OR REPLACE VIEW entry_cohorts AS
SELECT dimension, "group", level, start AS cohort, release, base AS entrants, survived,
       100.0 * survived / base AS rate, rate_pub
FROM survival
WHERE cohort = 'entries' AND years_after = 3 AND dimension IN ('industry', 'state');

-- Rank of each industry division in each cohort (1 = lowest survival), and the cohort-to-cohort change.
CREATE OR REPLACE VIEW division_cohorts AS
SELECT "group" AS industry, cohort, entrants, rate_pub,
       rank() OVER (PARTITION BY cohort ORDER BY rate_pub) AS rank_low,
       rate_pub - first_value(rate_pub) OVER (PARTITION BY "group" ORDER BY cohort) AS change_since_first
FROM entry_cohorts
WHERE dimension = 'industry' AND level = 'group';

-- National entrants by size band for each cohort: the weights of the common size mix (Part 2).
CREATE OR REPLACE VIEW national_bands AS
WITH b AS (
    SELECT start AS cohort, size_band("group") AS band, sum(base) AS entrants, sum(survived) AS survived
    FROM survival
    WHERE dimension = 'size' AND cohort = 'entries' AND years_after = 3
      AND "group" IN ('Non employing', '1-4', '5-19', '20-199', '200+')
    GROUP BY ALL
)
SELECT cohort, band, entrants, survived,
       entrants / sum(entrants) OVER (PARTITION BY cohort) AS weight,
       100.0 * survived / entrants AS rate
FROM b;
