-- Useful queries. Run them all with:
--   docker exec -i hb-postgres psql -U heartbeat -d heartbeat < sql/queries.sql

-- How many rows are in each table?
SELECT (SELECT count(*) FROM readings)                          AS readings,
       (SELECT count(*) FROM readings WHERE status <> 'normal') AS low_or_high,
       (SELECT count(*) FROM rejected_readings)                 AS rejected;

-- The 10 newest readings
SELECT customer_id, recorded_at, heart_rate, status
FROM readings
ORDER BY recorded_at DESC
LIMIT 10;

-- The newest reading for each customer
SELECT * FROM latest_readings;

-- Summary per customer for the last 10 minutes
SELECT customer_id,
       count(*)                                     AS readings,
       round(avg(heart_rate))                       AS average_bpm,
       min(heart_rate)                              AS lowest,
       max(heart_rate)                              AS highest,
       count(*) FILTER (WHERE status <> 'normal')   AS low_or_high
FROM readings
WHERE recorded_at > now() - interval '10 minutes'
GROUP BY customer_id
ORDER BY customer_id;

-- Latest low or high readings
SELECT customer_id, recorded_at, heart_rate, status
FROM readings
WHERE status <> 'normal'
ORDER BY recorded_at DESC
LIMIT 10;

-- Seconds taken by each step, for the 10 newest readings
SELECT customer_id, sent_at, received_at, saved_at,
       kafka_seconds,   -- producer -> consumer
       save_seconds,    -- consumer -> database
       total_seconds    -- producer -> database
FROM readings
ORDER BY saved_at DESC
LIMIT 10;

-- Average seconds per step for each minute
SELECT * FROM timing_per_minute LIMIT 10;

-- Average, fastest and slowest over the last 10 minutes
SELECT round(avg(kafka_seconds), 3) AS avg_kafka_seconds,
       round(avg(save_seconds), 3)  AS avg_save_seconds,
       round(avg(total_seconds), 3) AS avg_total_seconds,
       min(total_seconds)           AS fastest_total_seconds,
       max(total_seconds)           AS slowest_total_seconds
FROM readings
WHERE saved_at > now() - interval '10 minutes';

-- Why were messages rejected?
SELECT reason, count(*) FROM rejected_readings GROUP BY reason ORDER BY count(*) DESC;

-- Show that the time index is used
EXPLAIN SELECT * FROM readings
WHERE recorded_at > (SELECT max(recorded_at) FROM readings) - interval '5 seconds';

-- Patients and their personal limits
SELECT profile, count(*) AS patients, min(age) AS youngest, max(age) AS oldest,
       round(avg(high_limit)) AS avg_high_limit, min(low_limit) AS lowest_low_limit
FROM patients GROUP BY profile ORDER BY profile;

-- Health alerts going on right now
SELECT * FROM open_alerts;

-- All health alerts, newest first, and whether the emails went out
SELECT customer_id, kind, severity, limit_bpm, peak_bpm, started_at, ended_at,
       opened_email_at IS NOT NULL AS alert_emailed,
       closed_email_at IS NOT NULL AS resolved_emailed
FROM alert_episodes ORDER BY started_at DESC LIMIT 20;
