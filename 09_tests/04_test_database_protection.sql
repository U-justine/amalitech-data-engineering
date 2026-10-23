-- Test: Database Protection
-- Tests that the database blocks negative stock and prevents editing order lines.

BEGIN;

-- 1. Try to set stock to a negative number (should fail)
DO $$
DECLARE 
    v_blocked BOOLEAN := FALSE;
BEGIN
    BEGIN 
        UPDATE products SET stock_qty = -1 WHERE product_id = 1;
    EXCEPTION WHEN check_violation THEN 
        v_blocked := TRUE; 
    END;
    
    RAISE NOTICE 'Test 1 (Negative stock blocked): %', CASE WHEN v_blocked THEN 'PASS' ELSE 'FAIL' END;
END $$;

-- 2. Try to edit an existing order line (should fail)
DO $$
DECLARE 
    v_blocked BOOLEAN := FALSE;
    v_id INT;
BEGIN
    -- Grab a real order line from the database
    SELECT order_detail_id INTO v_id FROM order_details LIMIT 1;

    -- If no order lines exist, skip the test
    IF v_id IS NULL THEN
        RAISE NOTICE 'Test 2 (Editing order lines blocked): SKIPPED (No order lines to test)';
    ELSE
        -- Try to update it (the trigger should block this)
        BEGIN 
            UPDATE order_details SET quantity = 99 WHERE order_detail_id = v_id;
        EXCEPTION WHEN OTHERS THEN 
            v_blocked := TRUE; 
        END;
        
        RAISE NOTICE 'Test 2 (Editing order lines blocked): %', CASE WHEN v_blocked THEN 'PASS' ELSE 'FAIL' END;
    END IF;
END $$;

ROLLBACK;