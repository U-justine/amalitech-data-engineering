-- Test: Replenishment System

-- Purpose: Tests manual restocking, auto-replenishment, and manual stock adjustments.
-- Proves that the system automatically logs every change.

BEGIN;

-- 1. Show current low-stock products
SELECT '--- 1. Current Low-Stock Products ---' AS step;
SELECT * FROM vw_low_stock ORDER BY shortfall DESC;


-- 2. Receive a manual delivery
SELECT '--- 2. Delivery: 25 Bookshelves arrive ---' AS step;
CALL sp_replenish_product(10, 25, 'PO-1001 delivery from supplier');
SELECT product_id, name, stock_qty, reorder_level FROM products WHERE product_id = 10;


-- 3. Auto-replenish everything still low
SELECT '--- 3. Auto-replenish everything still low (to 2x reorder level) ---' AS step;
CALL sp_auto_replenish(2);


-- 4. Check if the low-stock list is now empty
SELECT '--- 4. Is the low-stock list empty? ---' AS step;
SELECT COUNT(*) AS products_still_low FROM vw_low_stock;


-- 5. View the audit trail to prove the logs were written
SELECT '--- 5. Replenishment Audit Trail ---' AS step;
SELECT l.log_id, p.name, l.change_qty, l.previous_qty, l.new_qty, l.note, l.changed_by, l.changed_at
  FROM inventory_logs l
  JOIN products p ON p.product_id = l.product_id
 WHERE l.change_type = 'REPLENISHMENT'
 ORDER BY l.log_id;


-- 6. Test a manual adjustment (e.g., breaking an item)
SELECT '--- 6. Stock count finds 2 damaged Webcams (Adjustment) ---' AS step;
SELECT set_config('inventory.note', 'Stock count: 2 damaged units written off', true);
UPDATE products SET stock_qty = stock_qty - 2 WHERE product_id = 7;

-- Check that the log recorded the adjustment
SELECT log_id, product_id, change_type, change_qty, previous_qty, new_qty, note
  FROM inventory_logs WHERE product_id = 7 ORDER BY log_id DESC LIMIT 1;

ROLLBACK; -- Undo everything so the database stays clean!