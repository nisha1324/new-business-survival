-- Part 4, step 3: industry divisions within size bands (data cube 5 summed over states), as in Part 2.

-- 2021-22 entrants per division x band, summed over every state row (including Other Territories).
-- 'Total' comes from the published Total cells; because cells are perturbed, the bands need not add to it.
CREATE OR REPLACE VIEW division_band_counts AS
SELECT division, band, sum(base) AS entrants, sum(survived) AS survived
FROM detail_entrants
WHERE level = 'group' AND division <> 'X'
GROUP BY ALL;

-- One row per division: rate overall and per band, and the rate at the national size mix of 2021-22 entrants.
-- std is blank if any band's rate is blank; mix_effect > 0 means the size mix flatters the overall rate.
CREATE OR REPLACE VIEW division_bands AS
WITH r AS (
    SELECT c.division, c.band, c.entrants, c.survived, floored_rate(c.survived, c.entrants) AS rate, w.weight
    FROM division_band_counts c
    LEFT JOIN national_bands w ON w.band = c.band AND w.cohort = detail_cohort()
), d AS (
    SELECT division,
           sum(entrants) FILTER (WHERE band = 'Total')            AS entrants,
           sum(entrants) FILTER (WHERE band = 'Non-employing')
               / sum(entrants) FILTER (WHERE band <> 'Total')     AS non_employing_share,
           max(rate) FILTER (WHERE band = 'Total')                AS rate_all,
           max(rate) FILTER (WHERE band = 'Non-employing')        AS "rate_Non-employing",
           max(rate) FILTER (WHERE band = '1-4')                  AS "rate_1-4",
           max(rate) FILTER (WHERE band = '5+')                   AS "rate_5+",
           sum(entrants) FILTER (WHERE band = '5+')               AS "base_5+",
           CASE WHEN count(rate) FILTER (WHERE band <> 'Total') = 3
                THEN sum(rate * weight) FILTER (WHERE band <> 'Total') END AS std
    FROM r
    GROUP BY division
)
SELECT d.division, v.industry, d.* EXCLUDE (division), rate_all - std AS mix_effect,
       rank() OVER (ORDER BY std) AS rank_std,
       rank() OVER (ORDER BY rate_all) AS rank_rate_all
FROM d JOIN divisions v USING (division)
ORDER BY std;
