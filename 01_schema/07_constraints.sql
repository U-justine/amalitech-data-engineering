-- Create constraints

-- Purpose: Business rules the database enforces no matter how data arrives.
-- (Primary and foreign keys are already declared with each table in File 1).

-- products 

ALTER TABLE products
    ADD CONSTRAINT uq_products_name         UNIQUE (name),
    ADD CONSTRAINT chk_products_price       CHECK (price_usd > 0),
    ADD CONSTRAINT chk_products_stock       CHECK (stock_qty >= 0),
    ADD CONSTRAINT chk_products_reorder     CHECK (reorder_level >= 0);

-- customers 

ALTER TABLE customers
    ADD CONSTRAINT uq_customers_email       UNIQUE (email),
    ADD CONSTRAINT chk_customers_email      CHECK (email LIKE '%_@_%._%'),
    ADD CONSTRAINT chk_customers_spent      CHECK (total_spent >= 0),
    ADD CONSTRAINT chk_customers_tier       CHECK (tier IN ('Bronze', 'Silver', 'Gold'));

-- orders 

ALTER TABLE orders
    ADD CONSTRAINT chk_orders_total         CHECK (total_amount >= 0);

-- order_details 

ALTER TABLE order_details
    ADD CONSTRAINT uq_order_details_line    UNIQUE (order_id, product_id),   -- one line per product per order
    ADD CONSTRAINT chk_order_details_qty    CHECK (quantity > 0),
    ADD CONSTRAINT chk_order_details_price  CHECK (unit_price > 0),
    ADD CONSTRAINT chk_order_details_disc   CHECK (discount_pct BETWEEN 0 AND 100),
    ADD CONSTRAINT chk_order_details_total  CHECK (line_total >= 0);

-- inventory_logs 

ALTER TABLE inventory_logs
    ADD CONSTRAINT chk_inv_logs_type        CHECK (change_type IN
        ('INITIAL', 'ORDER', 'ORDER_CANCELLED', 'REPLENISHMENT', 'ADJUSTMENT')),
    ADD CONSTRAINT chk_inv_logs_math        CHECK (new_qty = previous_qty + change_qty),
    ADD CONSTRAINT chk_inv_logs_nonzero     CHECK (change_qty <> 0);
