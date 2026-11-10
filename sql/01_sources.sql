-- Part 4, step 1: typed views over the committed snapshot, plus the shared rules.
--
-- The views read data/*.csv.gz directly, so nothing is copied into a database
-- file. Set DuckDB's file_search_path to the data/ folder first, e.g.
--   duckdb -c "SET file_search_path = 'data'; .read sql/01_sources.sql" ...
-- or use cabee.sql.connect(), which runs every file in sql/ in order.

-- ---------------------------------------------------------------- rules (Part 1)
CREATE OR REPLACE MACRO small_base() AS 20;        -- no rate on a base of 20 businesses or fewer (rule 6)
CREATE OR REPLACE MACRO reliable_base() AS 100;    -- benchmark: "reliable" needs 100+ entrants ...
CREATE OR REPLACE MACRO max_small_share() AS 0.10::DOUBLE; -- ... and at most 10% of them in perturbed cells of 20 or fewer
CREATE OR REPLACE MACRO detail_cohort() AS '2021-22'; -- the one entry cohort data cubes 4 and 5 cover

-- Employment size folded into the three bands used from Part 2 on.
CREATE OR REPLACE MACRO size_band(s) AS
    CASE s WHEN 'Non employing' THEN 'Non-employing'
           WHEN '1-4' THEN '1-4'
           WHEN 'Total' THEN 'Total'
           ELSE '5+' END;
CREATE OR REPLACE MACRO band_order(b) AS
    CASE b WHEN 'Non-employing' THEN 1 WHEN '1-4' THEN 2 WHEN '5+' THEN 3 ELSE 4 END;

-- A rate (%) from counts, blank on a base at or under the floor.
CREATE OR REPLACE MACRO floored_rate(survived, base) AS
    CASE WHEN base > small_base() THEN 100.0 * survived / base END;

-- ---------------------------------------------------------------- lookups
CREATE OR REPLACE TABLE states AS
SELECT * FROM (VALUES
    (1, 'New South Wales', 'NSW'), (2, 'Victoria', 'Vic'), (3, 'Queensland', 'Qld'),
    (4, 'South Australia', 'SA'), (5, 'Western Australia', 'WA'), (6, 'Tasmania', 'Tas'),
    (7, 'Northern Territory', 'NT'), (8, 'Australian Capital Territory', 'ACT')
) AS t(state_order, state, abbr);

CREATE OR REPLACE TABLE divisions AS
SELECT * FROM (VALUES
    ('A', 'Agriculture, Forestry and Fishing'), ('B', 'Mining'), ('C', 'Manufacturing'),
    ('D', 'Electricity, Gas, Water and Waste Services'), ('E', 'Construction'), ('F', 'Wholesale Trade'),
    ('G', 'Retail Trade'), ('H', 'Accommodation and Food Services'), ('I', 'Transport, Postal and Warehousing'),
    ('J', 'Information Media and Telecommunications'), ('K', 'Financial and Insurance Services'),
    ('L', 'Rental, Hiring and Real Estate Services'), ('M', 'Professional, Scientific and Technical Services'),
    ('N', 'Administrative and Support Services'), ('O', 'Public Administration and Safety'),
    ('P', 'Education and Training'), ('Q', 'Health Care and Social Assistance'),
    ('R', 'Arts and Recreation Services'), ('S', 'Other Services')
) AS t(division, industry);

-- ---------------------------------------------------------------- the snapshot
-- data cube 1 (four releases): survival of operating businesses and of entrants
CREATE OR REPLACE VIEW survival AS
SELECT * FROM read_csv('survival.csv.gz', header = true, columns = {
    'release': 'VARCHAR', 'dimension': 'VARCHAR', 'cohort': 'VARCHAR', 'start': 'VARCHAR',
    'cohort_june': 'INTEGER', 'section': 'VARCHAR', 'group': 'VARCHAR', 'level': 'VARCHAR',
    'base': 'BIGINT', 'survived_to': 'INTEGER', 'years_after': 'INTEGER', 'survived': 'BIGINT',
    'rate_pub': 'DOUBLE'});

-- data cube 1: businesses operating, entries and exits per financial year
CREATE OR REPLACE VIEW flows AS
SELECT * FROM read_csv('flows.csv.gz', header = true, columns = {
    'release': 'VARCHAR', 'dimension': 'VARCHAR', 'fin_year': 'VARCHAR', 'group': 'VARCHAR', 'level': 'VARCHAR',
    'operating_start': 'BIGINT', 'births': 'BIGINT', 'entries_other': 'BIGINT', 'entries': 'BIGINT',
    'cancellations': 'BIGINT', 'exits_other': 'BIGINT', 'exits': 'BIGINT', 'net_movement': 'BIGINT',
    'operating_end': 'BIGINT'});

-- data cubes 4 and 5 (perturbed): state x ANZSIC subdivision x employment size
CREATE OR REPLACE VIEW subdivision_survival AS
SELECT * FROM read_csv('subdivision_survival.csv.gz', header = true, columns = {
    'cohort': 'VARCHAR', 'cohort_june': 'INTEGER', 'state': 'VARCHAR', 'subdivision_code': 'VARCHAR',
    'subdivision': 'VARCHAR', 'division': 'VARCHAR', 'level': 'VARCHAR', 'size': 'VARCHAR', 'base': 'BIGINT',
    'survived_to': 'INTEGER', 'years_after': 'INTEGER', 'survived': 'BIGINT', 'rate_pub': 'DOUBLE'});

-- data cube 10: businesses operating in each LGA, June 2023-2025, by industry division and size
CREATE OR REPLACE VIEW lga_counts AS
SELECT * FROM read_csv('lga_counts.csv.gz', header = true, columns = {
    'june': 'INTEGER', 'state': 'VARCHAR', 'lga_code': 'VARCHAR', 'lga': 'VARCHAR', 'division': 'VARCHAR',
    'industry': 'VARCHAR', 'size': 'VARCHAR', 'count': 'BIGINT'});

-- 2021-22 entrants still trading three Junes on (to June 2025), the rows every later view starts from.
CREATE OR REPLACE VIEW detail_entrants AS
SELECT *, size_band(size) AS band
FROM subdivision_survival
WHERE cohort = 'entries' AND years_after = 3;
