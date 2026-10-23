-- Optimization: Explain Plans (Before vs After Indexes)

-- Purpose: Proves that our indexes actually make queries faster.
-- It temporarily adds 500,000 fake rows, tests the speed of the queries 
-- with and without indexes, and then deletes all the fake data.

BEGIN;

-- 1. Add Bulk Test Data

-- Add 100k fake products
INSERT INTO products (product_id, name, category, price_usd, stock_qty, reorder_level)
SELECT 900000000 + g,
       'Load test product ' || g,
       (ARRAY['Electronics','Furniture','Accessories'])[1 + g % 3],
       10 + (g % 500),
       CASE WHEN g % 1000 = 0 THEN 1 ELSE 200 END, -- 0.1% are low stock
       20
  FROM generate_series(1, 100000) g;

-- Add 100k fake orders
INSERT INTO orders (order_id, customer_id, order_date, total_amount)
SELECT 900000000 + g,
       1 + (g % 20),
       CURRENT_TIMESTAMP - (g % 730) * INTERVAL '1 day',
       (g % 900) + 10
  FROM generate_series(1, 100000) g;

-- Add 300k fake inventory logs
INSERT INTO inventory_logs (log_id, product_id, change_qty, change_type, previous_qty, new_qty, changed_at)
SELECT 900000000 + g,
       1 + (g % 20), -1,
       (ARRAY['ORDER','REPLENISHMENT','ADJUSTMENT'])[1 + g % 3],
       100, 99,
       CURRENT_TIMESTAMP - (g % 730) * INTERVAL '1 day'
  FROM generate_series(1, 300000) g;

-- Update statistics for the new data
ANALYZE products; ANALYZE orders; ANALYZE inventory_logs;


-- Test 1: Low-stock lookup (Partial Index)
SELECT '1. Low stock: BEFORE (no index)' AS test;
SAVEPOINT s1;
DROP INDEX idx_products_low_stock;
EXPLAIN ANALYZE SELECT * FROM products WHERE stock_qty < reorder_level;
ROLLBACK TO SAVEPOINT s1;

SELECT '1. Low stock: AFTER (partial index)' AS test;
EXPLAIN ANALYZE SELECT * FROM products WHERE stock_qty < reorder_level;


-- Test 2: Customer history (Composite Index)
SELECT '2. Customer history: BEFORE' AS test;
SAVEPOINT s2;
DROP INDEX idx_orders_customer_date;
EXPLAIN ANALYZE
SELECT order_id, order_date, total_amount FROM orders
 WHERE customer_id = 3 AND order_date >= CURRENT_DATE - INTERVAL '30 days';
ROLLBACK TO SAVEPOINT s2;

SELECT '2. Customer history: AFTER' AS test;
EXPLAIN ANALYZE
SELECT order_id, order_date, total_amount FROM orders
 WHERE customer_id = 3 AND order_date >= CURRENT_DATE - INTERVAL '30 days';


-- Test 3: Product audit history (Composite Index)
SELECT '3. Product audit: BEFORE' AS test;
SAVEPOINT s3;
DROP INDEX idx_inv_logs_product_time;
EXPLAIN ANALYZE
SELECT * FROM inventory_logs
 WHERE product_id = 5 AND changed_at >= CURRENT_DATE - INTERVAL '7 days';
ROLLBACK TO SAVEPOINT s3;

SELECT '3. Product audit: AFTER' AS test;
EXPLAIN ANALYZE
SELECT * FROM inventory_logs
 WHERE product_id = 5 AND changed_at >= CURRENT_DATE - INTERVAL '7 days';


-- Test 4: Revenue for last week (Date Index)
SELECT '4. Date range: BEFORE' AS test;
SAVEPOINT s4;
DROP INDEX idx_orders_date;
EXPLAIN ANALYZE
SELECT SUM(total_amount) FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '7 days';
ROLLBACK TO SAVEPOINT s4;

SELECT '4. Date range: AFTER' AS test;
EXPLAIN ANALYZE
SELECT SUM(total_amount) FROM orders WHERE order_date >= CURRENT_DATE - INTERVAL '7 days';


-- Cleanup: Rollback all fake data
ROLLBACK;

-- Verify nothing was left behind (Should show 20 products, 10 orders)
SELECT (SELECT COUNT(*) FROM products) AS products,
       (SELECT COUNT(*) FROM orders)   AS orders;