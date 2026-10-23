-- Create customers table

DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id  SERIAL         PRIMARY KEY,
    name         VARCHAR(100)   NOT NULL,
    email        VARCHAR(100)   NOT NULL,
    phone        VARCHAR(20),
    total_spent  NUMERIC(12,2)  NOT NULL DEFAULT 0,
    tier         VARCHAR(10)    NOT NULL DEFAULT 'Bronze',
    created_at   TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);
