-- =====================================================================
-- postgres_setup.sql
-- Creates the database, application user and tables for the
-- real-time e-commerce event pipeline.
--
-- Run as a PostgreSQL superuser (safe to re-run):
--     sudo -u postgres psql < postgres_setup.sql      (Ubuntu / WSL)
--     psql -h localhost -U postgres -f postgres_setup.sql
-- =====================================================================

-- 1. Application role --------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spark_user') THEN
        CREATE ROLE spark_user LOGIN PASSWORD 'spark_pass';
    END IF;
END
$$;

-- 2. Database (CREATE DATABASE can't run inside DO, so use \gexec) -----
SELECT 'CREATE DATABASE ecommerce_stream OWNER spark_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'ecommerce_stream')\gexec

\connect ecommerce_stream

SET ROLE spark_user;

-- 3. Main fact table: one row per cleaned event ------------------------
CREATE TABLE IF NOT EXISTS user_events (
    event_id         UUID           PRIMARY KEY,           -- dedup key
    user_id          VARCHAR(20)    NOT NULL,
    session_id       VARCHAR(32)    NOT NULL,
    event_type       VARCHAR(20)    NOT NULL
                     CHECK (event_type IN ('view', 'add_to_cart', 'purchase')),
    product_id       VARCHAR(10)    NOT NULL,
    product_name     VARCHAR(100)   NOT NULL,
    category         VARCHAR(50)    NOT NULL,
    price            NUMERIC(10,2)  NOT NULL CHECK (price >= 0),
    quantity         INTEGER        NOT NULL CHECK (quantity > 0),
    total_amount     NUMERIC(12,2)  NOT NULL,              -- price * quantity
    device           VARCHAR(20),
    event_timestamp  TIMESTAMP      NOT NULL,              -- when the event happened (UTC)
    source_file      TEXT,                                 -- CSV the row came from
    batch_id         BIGINT,                               -- Spark micro-batch id
    processed_at     TIMESTAMP      NOT NULL,              -- when Spark processed it (UTC)
    inserted_at      TIMESTAMP      NOT NULL DEFAULT (now() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS idx_user_events_ts       ON user_events (event_timestamp);
CREATE INDEX IF NOT EXISTS idx_user_events_type     ON user_events (event_type);
CREATE INDEX IF NOT EXISTS idx_user_events_user     ON user_events (user_id);
CREATE INDEX IF NOT EXISTS idx_user_events_category ON user_events (category);

-- 4. Rows that failed validation (kept for auditing, never silently lost)
CREATE TABLE IF NOT EXISTS rejected_events (
    id               BIGSERIAL      PRIMARY KEY,
    raw_event_id     TEXT,
    raw_user_id      TEXT,
    raw_event_type   TEXT,
    raw_price        TEXT,
    raw_quantity     TEXT,
    raw_timestamp    TEXT,
    reject_reason    TEXT           NOT NULL,
    source_file      TEXT,
    batch_id         BIGINT,
    rejected_at      TIMESTAMP      NOT NULL DEFAULT (now() AT TIME ZONE 'UTC')
);

-- 5. Staging table: Spark bulk-loads each micro-batch here, then an
--    INSERT ... ON CONFLICT moves it into user_events (idempotent).
CREATE UNLOGGED TABLE IF NOT EXISTS user_events_staging
    (LIKE user_events INCLUDING DEFAULTS);

-- 6. Per-batch performance log written by the Spark job ----------------
CREATE TABLE IF NOT EXISTS pipeline_batch_metrics (
    batch_id             BIGINT       PRIMARY KEY,
    input_rows           INTEGER      NOT NULL,
    valid_rows           INTEGER      NOT NULL,   -- unique valid rows in the batch
    rejected_rows        INTEGER      NOT NULL,
    duplicate_rows       INTEGER      NOT NULL,   -- dropped: duplicate event_id (in batch or already stored)
    inserted_rows        INTEGER      NOT NULL,   -- after dedup against existing rows
    files_in_batch       INTEGER,
    write_duration_ms    INTEGER      NOT NULL,   -- time spent writing to PostgreSQL
    batch_started_at     TIMESTAMP    NOT NULL,
    batch_finished_at    TIMESTAMP    NOT NULL
);

RESET ROLE;

-- 7. Handy view for quick checks --------------------------------------
CREATE OR REPLACE VIEW v_event_summary AS
SELECT event_type,
       COUNT(*)                         AS events,
       COUNT(DISTINCT user_id)          AS users,
       ROUND(SUM(total_amount), 2)      AS total_amount
FROM user_events
GROUP BY event_type;

ALTER VIEW v_event_summary OWNER TO spark_user;
