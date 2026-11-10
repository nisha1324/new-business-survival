-- Part 4, step 7: the survival benchmark for lenders and advisers.
--
-- One row per state x industry division x size band (8 x 19 x 3 = 456) for businesses
-- that entered in 2021-22: the share still trading three Junes later (June 2025).
--
--   observed          the rate in this state, summed from data cube 5's cells
--   national_rate     the same industry and band over the 8 states
--   state_adjustment  Part 3's local effect: the state's actual rate minus the rate its
--                     industry x size mix would give at national cell rates (points)
--   benchmark         observed if it is reliable; otherwise national_rate + state_adjustment
--                     if the national rate is reliable; otherwise blank
--
-- Reliability: no rate on 20 entrants or fewer; "reliable" needs 100+ entrants and at most
-- 10% of them in perturbed cells of 20 or fewer (see perturbation_check); else "use with care".

CREATE OR REPLACE MACRO reliability(entrants, small_share) AS
    CASE WHEN entrants <= small_base() THEN 'no rate'
         WHEN entrants >= reliable_base() AND small_share <= max_small_share() THEN 'reliable'
         ELSE 'use with care' END;

CREATE OR REPLACE VIEW benchmark AS
WITH c AS (
    SELECT state, division, band, sum(entrants) AS entrants, sum(survived) AS survived,
           sum(entrants_in_small_cells) / sum(entrants) AS small_share
    FROM state_cells GROUP BY ALL
), n AS (
    SELECT division, band, entrants, survived, entrants_in_small_cells / entrants AS small_share
    FROM national_cells
), b AS (
    SELECT s.state_order, s.state, s.abbr, c.division, v.industry, c.band, band_order(c.band) AS band_order,
           c.entrants, c.survived, c.small_share,
           floored_rate(c.survived, c.entrants) AS observed,
           reliability(c.entrants, c.small_share) AS observed_flag,
           n.entrants AS national_entrants, n.small_share AS national_small_share,
           floored_rate(n.survived, n.entrants) AS national_rate,
           reliability(n.entrants, n.small_share) AS national_flag,
           m.local AS state_adjustment
    FROM c
    JOIN states s USING (state)
    JOIN divisions v USING (division)
    JOIN n USING (division, band)
    JOIN state_mix m USING (state)
)
SELECT b.* EXCLUDE (band_order),
       CASE WHEN observed_flag = 'reliable' THEN observed
            WHEN national_flag = 'reliable' THEN national_rate + state_adjustment END AS benchmark,
       CASE WHEN observed_flag = 'reliable' THEN 'this state'
            WHEN national_flag = 'reliable' THEN 'national + state adjustment'
            ELSE 'none' END AS benchmark_source,
       observed - national_rate AS observed_vs_national
FROM b
ORDER BY state_order, division, band_order;

-- How well "national rate + state adjustment" reproduces the cells that can be measured directly
-- (both the state's and the national rate reliable). An in-sample fit check on the one cohort, not a forecast test.
CREATE OR REPLACE VIEW benchmark_fit AS
SELECT coalesce(abbr, 'All states') AS state, count(*) AS cells, sum(entrants) AS entrants,
       avg(abs(observed - national_rate)) AS mae_national,
       avg(abs(observed - national_rate - state_adjustment)) AS mae_adjusted,
       sum(entrants * abs(observed - national_rate)) / sum(entrants) AS wmae_national,
       sum(entrants * abs(observed - national_rate - state_adjustment)) / sum(entrants) AS wmae_adjusted,
       avg(CASE WHEN abs(observed - national_rate - state_adjustment) < abs(observed - national_rate)
                THEN 1.0 ELSE 0.0 END) AS share_closer,
       avg(observed - national_rate) AS mean_gap,
       CASE WHEN grouping(abbr) = 0 THEN any_value(state_adjustment) END AS state_adjustment,
       CASE WHEN grouping(abbr) = 0 THEN min(state_order) END AS state_order
FROM benchmark
WHERE observed_flag = 'reliable' AND national_flag = 'reliable'
GROUP BY ROLLUP (abbr)
ORDER BY state_order NULLS LAST;
