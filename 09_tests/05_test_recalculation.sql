-- Test: Recalculation & Double-Counting

-- Purpose: Proves that deleting all orders resets customers, 
-- and re-running the simulation doesn't double their totals.

BEGIN;

DO $$
DECLARE v_id INT;
BEGIN
    -- 1. Delete all orders (simulating a fresh start)
    DELETE FROM orders;
    
    RAISE NOTICE 'Test 1 (Delete resets customers): %', 
        CASE WHEN NOT EXISTS (SELECT 1 FROM customers WHERE total_spent <> 0 OR tier <> 'Bronze') THEN 'PASS' ELSE 'FAIL' END;

    -- 2. Re-place Alice's massive order
    CALL sp_place_order(1, '[{"product_id":1,"quantity":1},{"product_id":5,"quantity":2},{"product_id":8,"quantity":1}]', v_id);
    
    -- 3. Check if her total is exactly 2050 (and not double-counted)
    RAISE NOTICE 'Test 2 (Re-placed order not double-counted): %', 
        CASE WHEN (SELECT total_spent FROM customers WHERE customer_id = 1) = 2050 THEN 'PASS' ELSE 'FAIL' END;
END $$;

ROLLBACK;