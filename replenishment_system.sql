-- REPLENISHMENT SYSTEM

-- 1. Check which items are low on stock
SELECT * FROM vw_low_stock;

-- 2. Restock all low items to 100 units automatically
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT product_id FROM vw_low_stock) LOOP
        UPDATE products SET stock_qty = 100 WHERE product_id = r.product_id;
    END LOOP;
END $$;

-- 3. Check the logs to prove the database logged the restock automatically
SELECT * FROM inventory_logs WHERE change_type = 'REPLENISHMENT';

-- 4. Check which items are low on stock
SELECT * FROM vw_low_stock;


SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';

-- See all Orders
SELECT * FROM products;

-- See all Order Details (the items bought)
SELECT * FROM order_details;

-- See all Inventory Logs (the history of stock changes)
SELECT * FROM inventory_logs; SELECT * FROM inventory_logs

-- Look at the history of the Bookshelf
SELECT * FROM inventory_logs WHERE product_id = 10 ORDER BY changed_at;