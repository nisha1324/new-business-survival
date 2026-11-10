-- Part 4, step 4: states after their industry x size mix (Part 3), and the state adjustment.

-- Entrants per state x size band from the state-total rows (they match data cube 1 exactly).
CREATE OR REPLACE VIEW state_bands AS
WITH c AS (
    SELECT state, band, sum(base) AS entrants, sum(survived) AS survived
    FROM detail_entrants
    WHERE level = 'total' AND size <> 'Total' AND state IN (SELECT state FROM states)
    GROUP BY ALL
), r AS (
    SELECT c.*, floored_rate(c.survived, c.entrants) AS rate, w.weight
    FROM c JOIN national_bands w ON w.band = c.band AND w.cohort = detail_cohort()
)
SELECT s.state_order, state,
       sum(entrants) AS entrants,
       sum(entrants) FILTER (WHERE band = 'Non-employing') / sum(entrants) AS non_employing_share,
       100.0 * sum(survived) / sum(entrants) AS rate_all,
       max(rate) FILTER (WHERE band = 'Non-employing') AS "rate_Non-employing",
       max(rate) FILTER (WHERE band = '1-4') AS "rate_1-4",
       max(rate) FILTER (WHERE band = '5+') AS "rate_5+",
       CASE WHEN count(rate) = 3 THEN sum(rate * weight) END AS std
FROM r JOIN states s USING (state)
GROUP BY ALL
ORDER BY state_order;

-- The 8 states' subdivision x size cells (unknown industry and Other Territories left out),
-- with how many of each cell's entrants sit in cells of 20 or fewer (heavily perturbed).
CREATE OR REPLACE VIEW state_cells AS
SELECT state, division, subdivision_code, size, band, base AS entrants, survived,
       CASE WHEN base <= small_base() THEN base ELSE 0 END AS entrants_in_small_cells
FROM detail_entrants
WHERE level = 'group' AND division <> 'X' AND size <> 'Total' AND state IN (SELECT state FROM states);

-- National survival per division x band over the 8 states: the cell rates the expected rate is built on.
CREATE OR REPLACE VIEW national_cells AS
SELECT division, band, sum(entrants) AS entrants, sum(survived) AS survived,
       sum(entrants_in_small_cells) AS entrants_in_small_cells,
       100.0 * sum(survived) / sum(entrants) AS rate
FROM state_cells
GROUP BY ALL;

-- Indirect standardisation: each state's expected rate if its division x band cells survived at the national rate.
CREATE OR REPLACE VIEW state_expected AS
WITH sc AS (
    SELECT state, division, band, sum(entrants) AS entrants, sum(survived) AS survived
    FROM state_cells GROUP BY ALL
)
SELECT state,
       sum(sc.entrants) AS cell_base,
       sum(sc.entrants * n.rate) / sum(sc.entrants) AS expected,
       100.0 * sum(sc.survived) / sum(sc.entrants) AS cells_actual,
       (SELECT 100.0 * sum(survived) / sum(entrants) FROM national_cells) AS national_cells
FROM sc JOIN national_cells n USING (division, band)
GROUP BY state;

-- Each state's gap to the published national rate = mix + local + residual.
-- local (actual - expected) is the state adjustment the benchmark uses.
CREATE OR REPLACE VIEW state_mix AS
WITH nat AS (
    SELECT rate_pub FROM entry_cohorts
    WHERE dimension = 'state' AND "group" = 'Australia' AND cohort = detail_cohort()
)
SELECT b.state_order, b.state, b.rate_all AS actual, e.expected,
       b.rate_all - nat.rate_pub AS gap,
       e.expected - e.national_cells AS mix,
       b.rate_all - e.expected AS local,
       (b.rate_all - nat.rate_pub) - (e.expected - e.national_cells) - (b.rate_all - e.expected) AS residual,
       rank() OVER (ORDER BY b.rate_all - e.expected) AS rank_local
FROM state_bands b JOIN state_expected e USING (state), nat
ORDER BY b.state_order;
