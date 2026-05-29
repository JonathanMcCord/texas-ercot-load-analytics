-- ============================================================
-- ERCOT Hourly Load — Reusable SQL Aggregations
-- ============================================================
-- These queries target the cleaned `ercot_hourly_load_long`
-- dataset (one row per (timestamp, zone) pair) loaded into a
-- table named `load_data`.
--
-- To use locally:
--   1. Load `ercot_hourly_load_long.csv` into SQLite / DuckDB /
--      Postgres as a table named `load_data` with columns:
--        timestamp (TIMESTAMP), is_dst_duplicate (BOOLEAN),
--        zone (TEXT), load_mw (NUMERIC)
--   2. Run any of the queries below.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Annual peak demand by year (ERCOT total only)
-- ------------------------------------------------------------
SELECT
    EXTRACT(YEAR FROM timestamp) AS year,
    MAX(load_mw)                 AS peak_mw,
    MIN(load_mw)                 AS min_mw,
    AVG(load_mw)                 AS avg_mw
FROM load_data
WHERE zone = 'ERCOT'
  AND is_dst_duplicate = FALSE
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY year;


-- ------------------------------------------------------------
-- 2. Monthly average load — reveals seasonality
-- ------------------------------------------------------------
SELECT
    EXTRACT(YEAR  FROM timestamp) AS year,
    EXTRACT(MONTH FROM timestamp) AS month,
    AVG(load_mw)                  AS avg_load_mw,
    MAX(load_mw)                  AS peak_load_mw
FROM load_data
WHERE zone = 'ERCOT'
  AND is_dst_duplicate = FALSE
GROUP BY EXTRACT(YEAR FROM timestamp), EXTRACT(MONTH FROM timestamp)
ORDER BY year, month;


-- ------------------------------------------------------------
-- 3. Hour-of-day load profile by season (ERCOT total)
--    Useful for showing daily demand curves shift across seasons
-- ------------------------------------------------------------
SELECT
    CASE
        WHEN EXTRACT(MONTH FROM timestamp) IN (12, 1, 2)  THEN 'Winter'
        WHEN EXTRACT(MONTH FROM timestamp) IN (3, 4, 5)   THEN 'Spring'
        WHEN EXTRACT(MONTH FROM timestamp) IN (6, 7, 8)   THEN 'Summer'
        ELSE 'Fall'
    END                              AS season,
    EXTRACT(HOUR FROM timestamp)     AS hour_of_day,
    AVG(load_mw)                     AS avg_load_mw
FROM load_data
WHERE zone = 'ERCOT'
  AND is_dst_duplicate = FALSE
GROUP BY season, EXTRACT(HOUR FROM timestamp)
ORDER BY season, hour_of_day;


-- ------------------------------------------------------------
-- 4. Top 25 peak demand hours (all-time)
-- ------------------------------------------------------------
SELECT
    timestamp,
    load_mw AS ercot_load_mw,
    EXTRACT(YEAR  FROM timestamp) AS year,
    EXTRACT(MONTH FROM timestamp) AS month,
    EXTRACT(HOUR  FROM timestamp) AS hour_of_day
FROM load_data
WHERE zone = 'ERCOT'
  AND is_dst_duplicate = FALSE
ORDER BY load_mw DESC
LIMIT 25;


-- ------------------------------------------------------------
-- 5. Weather zone share of total demand
--    Which Texas regions consume the most electricity?
-- ------------------------------------------------------------
SELECT
    zone,
    AVG(load_mw)                                  AS avg_load_mw,
    AVG(load_mw) / (SELECT AVG(load_mw)
                    FROM load_data
                    WHERE zone = 'ERCOT')         AS share_of_total
FROM load_data
WHERE zone <> 'ERCOT'
  AND is_dst_duplicate = FALSE
GROUP BY zone
ORDER BY avg_load_mw DESC;


-- ------------------------------------------------------------
-- 6. Winter Storm Uri (Feb 13-19, 2021) — hourly load
--    The headline case study
-- ------------------------------------------------------------
SELECT
    timestamp,
    load_mw AS ercot_load_mw
FROM load_data
WHERE zone = 'ERCOT'
  AND timestamp >= '2021-02-13'
  AND timestamp <  '2021-02-20'
ORDER BY timestamp;


-- ------------------------------------------------------------
-- 7. Year-over-year peak demand growth
-- ------------------------------------------------------------
WITH annual_peaks AS (
    SELECT
        EXTRACT(YEAR FROM timestamp) AS year,
        MAX(load_mw)                 AS peak_mw
    FROM load_data
    WHERE zone = 'ERCOT'
      AND is_dst_duplicate = FALSE
    GROUP BY EXTRACT(YEAR FROM timestamp)
)
SELECT
    year,
    peak_mw,
    LAG(peak_mw) OVER (ORDER BY year)                       AS prior_year_peak,
    peak_mw - LAG(peak_mw) OVER (ORDER BY year)             AS yoy_change_mw,
    (peak_mw - LAG(peak_mw) OVER (ORDER BY year))
        / LAG(peak_mw) OVER (ORDER BY year) * 100           AS yoy_change_pct
FROM annual_peaks
ORDER BY year;
