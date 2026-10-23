-- Create products table

DROP TABLE IF EXISTS products CASCADE;

CREATE TABLE products (
    product_id     SERIAL         PRIMARY KEY,
    name           VARCHAR(100)   NOT NULL,
    category       VARCHAR(50)    NOT NULL,
    price_usd      NUMERIC(10,2)  NOT NULL,
    stock_qty      INT            NOT NULL DEFAULT 0,
    reorder_level  INT            NOT NULL DEFAULT 10,
    created_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);
