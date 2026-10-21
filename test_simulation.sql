-- SIMULATION

-- 1. Clear old test orders
DELETE FROM orders;

-- 2. Run the simulation
DO $$
DECLARE
    o_id INT;
BEGIN
    -- ORDER 1: Alice (Customer 1) bought Electronics & Chair
    INSERT INTO orders (customer_id) VALUES (1) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 1, 1);  -- 1 Laptop
    CALL place_order(o_id, 5, 2);  -- 2 Monitors
    CALL place_order(o_id, 8, 1);  -- 1 Office Chair
    UPDATE customers SET total_spent = total_spent + 2050 WHERE customer_id = 1;

    -- ORDER 2: Bob (Customer 2) bought Bulk Mice & Speaker 
    INSERT INTO orders (customer_id) VALUES (2) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 2, 20); -- 20 Mice (Discount)
    CALL place_order(o_id, 18, 1); -- 1 Bluetooth Speaker
    UPDATE customers SET total_spent = total_spent + 510 WHERE customer_id = 2;

    -- ORDER 3: Charlie (Customer 3) bought Desk & SSD
    INSERT INTO orders (customer_id) VALUES (3) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 9, 1);  -- 1 Standing Desk
    CALL place_order(o_id, 17, 1); -- 1 External SSD
    UPDATE customers SET total_spent = total_spent + 600 WHERE customer_id = 3;

    -- ORDER 4: Diana (Customer 4) bought Accessories
    INSERT INTO orders (customer_id) VALUES (4) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 12, 2); -- 2 Mugs
    CALL place_order(o_id, 13, 1); -- 1 Backpack
    CALL place_order(o_id, 15, 1); -- 1 Laptop Sleeve
    CALL place_order(o_id, 20, 1); -- 1 Wireless Presenter
    UPDATE customers SET total_spent = total_spent + 129 WHERE customer_id = 4;

    -- ORDER 5: Ethan (Customer 5) bought Massive Mugs 
    INSERT INTO orders (customer_id) VALUES (5) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 12, 50); -- 50 Coffee Mugs (Discount)
    UPDATE customers SET total_spent = total_spent + 480 WHERE customer_id = 5;

    -- ORDER 6: Fatima (Customer 6) bought Headphones & Webcam
    INSERT INTO orders (customer_id) VALUES (6) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 4, 1);  -- 1 Headphones
    CALL place_order(o_id, 7, 1);  -- 1 Webcam
    UPDATE customers SET total_spent = total_spent + 330 WHERE customer_id = 6;

    -- ORDER 7: Jean Paul (Customer 7) bought Bulk Keyboards 
    INSERT INTO orders (customer_id) VALUES (7) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 3, 15); -- 15 Keyboards (Discount)
    CALL place_order(o_id, 6, 2);  -- 2 USB Hubs
    UPDATE customers SET total_spent = total_spent + 1237.50 WHERE customer_id = 7;

    -- ORDER 8: Marie Claire (Customer 8) bought Lamps & Stands 
    INSERT INTO orders (customer_id) VALUES (8) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 11, 1); -- 1 Desk Lamp
    CALL place_order(o_id, 16, 2); -- 2 Smartphone Stands
    UPDATE customers SET total_spent = total_spent + 60 WHERE customer_id = 8;

    -- ORDER 9: David (Customer 9) bought Bulk Chargers & Footrest 
    INSERT INTO orders (customer_id) VALUES (9) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 14, 12); -- 12 Wireless Chargers (Discount)
    CALL place_order(o_id, 19, 1);  -- 1 Ergonomic Footrest
    UPDATE customers SET total_spent = total_spent + 418 WHERE customer_id = 9;

    -- ORDER 10: Grace (Customer 10) bought Mixed products 
    INSERT INTO orders (customer_id) VALUES (10) RETURNING order_id INTO o_id;
    CALL place_order(o_id, 1, 1);  -- 1 Laptop
    CALL place_order(o_id, 2, 10); -- 10 Mice (Discount)
    CALL place_order(o_id, 12, 10); -- 10 Mugs (Discount)
    UPDATE customers SET total_spent = total_spent + 1533 WHERE customer_id = 10;

END $$;
