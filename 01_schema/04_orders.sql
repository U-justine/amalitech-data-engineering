-- Create orders table

DROP TABLE IF EXISTS orders CASCADE;

CREATE TABLE orders (
    order_id      SERIAL         PRIMARY KEY,
    customer_id   INT            NOT NULL
                  REFERENCES customers (customer_id) ON DELETE RESTRICT,
    order_date    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_amount  NUMERIC(12,2)  NOT NULL DEFAULT 0
);
