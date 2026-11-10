-- Part 4, step 6: how far summing small perturbed cells pulls survival down.
--
-- The ABS perturbs data cube 5 so no business can be identified. In small cells,
-- survivor counts of 1 or 2 never appear (they become 0 or 3+), and summing many such
-- cells reads low. Two places publish both a sum of cells and an exact figure:
--   1. each state x size band: the subdivision cells vs the state-total rows;
--   2. each industry division: its cells summed over states vs data cube 1 (not perturbed).
-- small_share = share of the entrants that sit in cells of 20 or fewer.

CREATE OR REPLACE VIEW perturbation_check AS
WITH st_cells AS (   -- all subdivision cells, unknown industry included, to match the state-total rows
    SELECT state, band, sum(base) AS entrants, sum(survived) AS survived,
           sum(CASE WHEN base <= small_base() THEN base ELSE 0 END) / sum(base) AS small_share
    FROM detail_entrants
    WHERE level = 'group' AND size <> 'Total' AND state IN (SELECT state FROM states)
    GROUP BY ALL
), st_total AS (
    SELECT state, band, sum(base) AS entrants, sum(survived) AS survived
    FROM detail_entrants
    WHERE level = 'total' AND size <> 'Total' AND state IN (SELECT state FROM states)
    GROUP BY ALL
), dv_cells AS (
    SELECT division, sum(base) AS entrants, sum(survived) AS survived,
           sum(CASE WHEN base <= small_base() THEN base ELSE 0 END) / sum(base) AS small_share
    FROM detail_entrants
    WHERE level = 'group' AND division <> 'X' AND size <> 'Total'
    GROUP BY ALL
), dv_cube1 AS (
    SELECT v.division, e.entrants, e.survived
    FROM entry_cohorts e JOIN divisions v ON v.industry = e."group"
    WHERE e.dimension = 'industry' AND e.level = 'group' AND e.cohort = detail_cohort()
)
SELECT 'state x size band' AS check_type, s.abbr || ', ' || c.band AS label, c.band,
       c.entrants, c.small_share,
       100.0 * c.survived / c.entrants AS rate_cells,
       100.0 * t.survived / t.entrants AS rate_exact,
       100.0 * c.survived / c.entrants - 100.0 * t.survived / t.entrants AS bias
FROM st_cells c JOIN st_total t USING (state, band) JOIN states s USING (state)
UNION ALL
SELECT 'industry division', v.industry, 'All sizes',
       c.entrants, c.small_share,
       100.0 * c.survived / c.entrants,
       100.0 * x.survived / x.entrants,
       100.0 * c.survived / c.entrants - 100.0 * x.survived / x.entrants
FROM dv_cells c JOIN dv_cube1 x USING (division) JOIN divisions v USING (division)
ORDER BY check_type DESC, small_share;
