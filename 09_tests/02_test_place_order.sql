-- Test: 02 Order Placement & Validation

-- Purpose: Tests order placement, bulk discounts, and ensures the database 
-- rejects bad data (insufficient stock, unknown customers, invalid quantities).
-- Also tests that cancelling an order restores the stock.

BEGIN;

-- 1. Test a valid order (Trigger check)
DO $$
DECLARE
    v_stock_before INT := (SELECT stock_qty FROM products WHERE product_id = 3);
    v_order_id     INT;
BEGIN
    -- Place order for customer 13, buying 2 keyboards (product 3)
    CALL sp_place_order(13, '[{"product_id":3,"quantity":2}]', v_order_id);
    
    RAISE NOTICE 'Test 1 (Order deducts stock): %', CASE WHEN (SELECT stock_qty FROM products WHERE product_id = 3) = v_stock_before - 2 THEN 'PASS' ELSE 'FAIL' END;
    RAISE NOTICE 'Test 2 (Order writes log): %', CASE WHEN (SELECT COUNT(*) = 1 AND MIN(change_qty) = -2 FROM inventory_logs WHERE change_type = 'ORDER' AND reference_id = v_order_id) THEN 'PASS' ELSE 'FAIL' END;
    RAISE NOTICE 'Test 3 (Order total calculated): %', CASE WHEN (SELECT total_amount FROM orders WHERE order_id = v_order_id) = 170 THEN 'PASS' ELSE 'FAIL' END;
    RAISE NOTICE 'Test 4 (Tier updated): %', CASE WHEN (SELECT total_spent = 170 AND tier = 'Bronze' FROM customers WHERE customer_id = 13) THEN 'PASS' ELSE 'FAIL' END;
END $$;

-- 2. Test rejection of insufficient stock
DO $$
DECLARE
    v_orders_before INT := (SELECT COUNT(*) FROM orders);
    v_msg           TEXT;
    v_id            INT;
BEGIN
    BEGIN 
        CALL sp_place_order(14, '[{"product_id":2,"quantity":1},{"product_id":1,"quantity":100000}]', v_id);
    EXCEPTION WHEN OTHERS THEN 
        v_msg := SQLERRM; 
    END;
    
    RAISE NOTICE 'Test 5 (Insufficient stock rejected): %', CASE WHEN v_msg LIKE 'Insufficient stock%' AND (SELECT COUNT(*) FROM orders) = v_orders_before THEN 'PASS' ELSE 'FAIL' END;
END $$;

-- 3. Test rejection of bad data
DO $$
DECLARE
    v_msg TEXT;
    v_id  INT;
BEGIN
    -- Unknown customer
    BEGIN CALL sp_place_order(99999, '[{"product_id":2,"quantity":1}]', v_id);
    EXCEPTION WHEN OTHERS THEN v_msg := SQLERRM; END;
    RAISE NOTICE 'Test 6 (Unknown customer rejected): %', CASE WHEN v_msg = 'Customer 99999 does not exist' THEN 'PASS' ELSE 'FAIL' END;

    -- Empty order
    BEGIN CALL sp_place_order(1, '[]', v_id);
    EXCEPTION WHEN OTHERS THEN v_msg := SQLERRM; END;
    RAISE NOTICE 'Test 7 (Empty order rejected): %', CASE WHEN v_msg = 'Order must contain at least one item' THEN 'PASS' ELSE 'FAIL' END;

    -- Zero quantity
    BEGIN CALL sp_place_order(1, '[{"product_id":2,"quantity":0}]', v_id);
    EXCEPTION WHEN OTHERS THEN v_msg := SQLERRM; END;
    RAISE NOTICE 'Test 8 (Zero quantity rejected): %', CASE WHEN v_msg LIKE 'Every item needs%' THEN 'PASS' ELSE 'FAIL' END;
END $$;

-- 4. Test bulk discount thresholds
DO $$
BEGIN
    RAISE NOTICE 'Test 9 (Discount logic): %', CASE WHEN fn_bulk_discount(9) = 0 AND fn_bulk_discount(10) = 10 AND fn_bulk_discount(50) = 20 THEN 'PASS' ELSE 'FAIL' END;
END $$;

-- 5. Test order cancellation
DO $$
DECLARE
    v_stock INT := (SELECT stock_qty FROM products WHERE product_id = 8);
    v_order INT;
BEGIN
    -- Place order, then cancel it
    CALL sp_place_order(15, '[{"product_id":8,"quantity":4}]', v_order);
    DELETE FROM orders WHERE order_id = v_order;
    
    RAISE NOTICE 'Test 10 (Cancel restores stock): %', CASE WHEN (SELECT stock_qty FROM products WHERE product_id = 8) = v_stock AND (SELECT total_spent = 0 FROM customers WHERE customer_id = 15) THEN 'PASS' ELSE 'FAIL' END;
END $$;

ROLLBACK; -- Undo all test changes so the database stays clean!