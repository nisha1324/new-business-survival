-- Part 4, step 5: growth in business numbers by local government area, June 2023 to June 2025 (Part 3).

CREATE OR REPLACE MACRO lga_floor() AS 1000; -- LGA league tables: at least 1,000 businesses in June 2023

-- Places only: no national rows, no "No usual address", no Other Territories.
CREATE OR REPLACE VIEW lga_places AS
SELECT * FROM lga_counts
WHERE lga_code <> 'TOT' AND lga <> 'No usual address' AND state IN (SELECT state FROM states);

CREATE OR REPLACE VIEW lga_growth AS
WITH t AS (
    SELECT state, lga_code, lga,
           coalesce(sum(count) FILTER (WHERE size = 'Total' AND june = 2023), 0) AS businesses_2023,
           coalesce(sum(count) FILTER (WHERE size = 'Total' AND june = 2025), 0) AS businesses_2025,
           coalesce(sum(count) FILTER (WHERE size NOT IN ('Total', 'Non employing') AND june = 2023), 0) AS employing_2023,
           coalesce(sum(count) FILTER (WHERE size NOT IN ('Total', 'Non employing') AND june = 2025), 0) AS employing_2025,
           coalesce(sum(count) FILTER (WHERE size = 'Non employing' AND june = 2023), 0) AS non_employing_2023,
           coalesce(sum(count) FILTER (WHERE size = 'Non employing' AND june = 2025), 0) AS non_employing_2025
    FROM lga_places
    WHERE division = 'TOT'
    GROUP BY ALL
), d AS (   -- the industry that added the most businesses (ties: alphabetical)
    SELECT state, lga_code, lga, industry,
           coalesce(sum(count) FILTER (WHERE june = 2025), 0) - coalesce(sum(count) FILTER (WHERE june = 2023), 0) AS chg
    FROM lga_places
    WHERE division <> 'TOT' AND size = 'Total' AND june IN (2023, 2025)
    GROUP BY state, lga_code, lga, industry
    QUALIFY row_number() OVER (PARTITION BY state, lga_code, lga ORDER BY chg DESC, industry) = 1
)
SELECT t.*,
       businesses_2025 - businesses_2023 AS change,
       (businesses_2025 - businesses_2023) / businesses_2023 AS growth,
       employing_2025 - employing_2023 AS employing_change,
       CASE WHEN employing_2023 > small_base()
            THEN (employing_2025 - employing_2023) / employing_2023 END AS employing_growth,
       d.industry AS top_division, d.chg AS top_division_change,
       businesses_2023 >= lga_floor() AS above_floor
FROM t LEFT JOIN d USING (state, lga_code, lga)
ORDER BY growth DESC, lga;
