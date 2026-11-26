-- PulseGuard database.
-- Docker runs this file automatically the first time PostgreSQL starts.

-- The clinic's patient register. Each patient has their own heart rate limits.
-- (The lab calls the patient id "customer_id", so that name is used everywhere.)
CREATE TABLE IF NOT EXISTS patients (
    customer_id  VARCHAR(32)  PRIMARY KEY,                 -- e.g. PT-0007
    profile      VARCHAR(10)  NOT NULL CHECK (profile IN ('athlete', 'adult', 'senior')),
    age          SMALLINT     NOT NULL CHECK (age BETWEEN 0 AND 120),
    resting_bpm  SMALLINT     NOT NULL,
    low_limit    SMALLINT     NOT NULL,                    -- below this -> "low"
    high_limit   SMALLINT     NOT NULL,                    -- above this -> "high"
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (low_limit < high_limit)
);

-- Every good reading. "status" uses the patient's own limits.
CREATE TABLE IF NOT EXISTS readings (
    id           BIGSERIAL    PRIMARY KEY,
    customer_id  VARCHAR(32)  NOT NULL,
    recorded_at  TIMESTAMPTZ  NOT NULL,              -- when the watch took the reading
    heart_rate   SMALLINT     NOT NULL CHECK (heart_rate BETWEEN 25 AND 230),
    status       VARCHAR(6)   NOT NULL CHECK (status IN ('normal', 'low', 'high')),

    -- Timing: when the reading passed each step of the pipeline
    sent_at      TIMESTAMPTZ,                                   -- producer sent it to Kafka
    received_at  TIMESTAMPTZ,                                   -- consumer got it from Kafka
    saved_at     TIMESTAMPTZ  NOT NULL DEFAULT clock_timestamp(), -- row written to the database

    -- Seconds taken by each step (worked out automatically by PostgreSQL)
    kafka_seconds  NUMERIC(10, 3) GENERATED ALWAYS AS
                   (extract(epoch FROM received_at - sent_at)) STORED,     -- producer -> consumer
    save_seconds   NUMERIC(10, 3) GENERATED ALWAYS AS
                   (extract(epoch FROM saved_at - received_at)) STORED,    -- consumer -> database
    total_seconds  NUMERIC(10, 3) GENERATED ALWAYS AS
                   (extract(epoch FROM saved_at - sent_at)) STORED,        -- producer -> database

    -- One reading per customer per moment: stops duplicates if Kafka resends a message.
    UNIQUE (customer_id, recorded_at)
);

-- Index on time, so "readings from the last 5 minutes" is fast.
-- (The UNIQUE rule above also creates an index on customer_id + recorded_at,
--  which makes "one customer's history" fast.)
CREATE INDEX IF NOT EXISTS readings_time_idx ON readings (recorded_at);

-- Messages that failed the checks, kept so we can see what went wrong.
CREATE TABLE IF NOT EXISTS rejected_readings (
    id           BIGSERIAL    PRIMARY KEY,
    raw_message  TEXT         NOT NULL,
    reason       VARCHAR(40)  NOT NULL,
    rejected_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Shortcut: the newest reading for each customer.
CREATE OR REPLACE VIEW latest_readings AS
SELECT DISTINCT ON (customer_id) customer_id, recorded_at, heart_rate, status
FROM readings
ORDER BY customer_id, recorded_at DESC;

-- Shortcut: average seconds per step, for each minute.
CREATE OR REPLACE VIEW timing_per_minute AS
SELECT date_trunc('minute', saved_at)  AS minute,
       count(*)                        AS readings,
       round(avg(kafka_seconds), 3)    AS avg_kafka_seconds,
       round(avg(save_seconds), 3)     AS avg_save_seconds,
       round(avg(total_seconds), 3)    AS avg_total_seconds,
       max(total_seconds)              AS slowest_total_seconds
FROM readings
GROUP BY 1
ORDER BY 1 DESC;

-- Health alert episodes: a patient was above or below their limits for
-- EPISODE_MIN_SECONDS (30 s) or longer. One row per episode, not per reading.
CREATE TABLE IF NOT EXISTS alert_episodes (
    episode_id      VARCHAR(80)  PRIMARY KEY,               -- patient id + start time
    customer_id     VARCHAR(32)  NOT NULL,
    kind            VARCHAR(4)   NOT NULL CHECK (kind IN ('high', 'low')),
    severity        VARCHAR(8)   NOT NULL CHECK (severity IN ('warning', 'critical')),
    limit_bpm       SMALLINT     NOT NULL,                  -- the limit that was crossed
    peak_bpm        SMALLINT     NOT NULL,                  -- furthest from normal
    reading_count   INT          NOT NULL,
    started_at      TIMESTAMPTZ  NOT NULL,                  -- first reading out of range
    ended_at        TIMESTAMPTZ,                            -- NULL while still going on
    opened_email_at TIMESTAMPTZ,                            -- when the alert email was sent
    closed_email_at TIMESTAMPTZ,                            -- when the "back to normal" email was sent
    emailed_severity VARCHAR(8)                             -- severity in the last email (warning -> critical = new email)
);
-- Databases made before emailed_severity existed get the column too.
ALTER TABLE alert_episodes ADD COLUMN IF NOT EXISTS emailed_severity VARCHAR(8);
CREATE INDEX IF NOT EXISTS episodes_open_idx ON alert_episodes (customer_id) WHERE ended_at IS NULL;

-- Shortcut: health alerts still going on.
CREATE OR REPLACE VIEW open_alerts AS
SELECT e.customer_id, p.profile, p.age, e.kind, e.severity, e.limit_bpm, e.peak_bpm,
       e.started_at, round(extract(epoch FROM now() - e.started_at)) AS seconds_so_far,
       e.opened_email_at IS NOT NULL AS emailed
FROM alert_episodes e
LEFT JOIN patients p USING (customer_id)
WHERE e.ended_at IS NULL
ORDER BY e.started_at;
