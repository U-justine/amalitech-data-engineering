-- Create order_details table

DROP TABLE IF EXISTS order_details CASCADE;

CREATE TABLE order_details (
    order_detail_id  SERIAL         PRIMARY KEY,
    order_id         INT            NOT NULL
                     REFERENCES orders (order_id) ON DELETE CASCADE,
    product_id       INT            NOT NULL
                     REFERENCES products (product_id) ON DELETE RESTRICT,
    quantity         INT            NOT NULL,
    unit_price       NUMERIC(10,2)  NOT NULL,
    discount_pct     NUMERIC(5,2)   NOT NULL DEFAULT 0,
    line_total       NUMERIC(12,2)  NOT NULL
);
