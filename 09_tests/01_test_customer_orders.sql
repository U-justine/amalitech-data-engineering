-- Test: 01 Customer Orders Simulation

-- Purpose: Places 10 realistic JSON orders and verifies that the triggers 
-- automatically calculate the totals, apply discounts, and update customer tiers.


-- 1. Alice: laptop, 2 monitors, office chair
CALL sp_place_order(1,  '[{"product_id":1,"quantity":1},{"product_id":5,"quantity":2},{"product_id":8,"quantity":1}]');

-- 2. Bob: 20 mice (10% off) + speaker
CALL sp_place_order(2,  '[{"product_id":2,"quantity":20},{"product_id":18,"quantity":1}]');

-- 3. Charlie: standing desk + SSD
CALL sp_place_order(3,  '[{"product_id":9,"quantity":1},{"product_id":17,"quantity":1}]');

-- 4. Diana: accessories
CALL sp_place_order(4,  '[{"product_id":12,"quantity":2},{"product_id":13,"quantity":1},{"product_id":15,"quantity":1},{"product_id":20,"quantity":1}]');

-- 5. Ethan: 50 coffee mugs (20% off)
CALL sp_place_order(5,  '[{"product_id":12,"quantity":50}]');

-- 6. Fatima: headphones + webcam
CALL sp_place_order(6,  '[{"product_id":4,"quantity":1},{"product_id":7,"quantity":1}]');

-- 7. Jean Paul: 15 keyboards (10% off) + 2 USB hubs
CALL sp_place_order(7,  '[{"product_id":3,"quantity":15},{"product_id":6,"quantity":2}]');

-- 8. Marie Claire: desk lamp + 2 phone stands
CALL sp_place_order(8,  '[{"product_id":11,"quantity":1},{"product_id":16,"quantity":2}]');

-- 9. David: 12 wireless chargers (10% off) + footrest
CALL sp_place_order(9,  '[{"product_id":14,"quantity":12},{"product_id":19,"quantity":1}]');

-- 10. Grace: laptop, 10 mice (10% off), 10 mugs (10% off)
CALL sp_place_order(10, '[{"product_id":1,"quantity":1},{"product_id":2,"quantity":10},{"product_id":12,"quantity":10}]');

-- Spread the orders over the last few months so the monthly reports have data
UPDATE orders
   SET order_date = CURRENT_TIMESTAMP - ((11 - order_id) * INTERVAL '12 days')
 WHERE order_id BETWEEN 1 AND 10;

-- Results: Check that totals and tiers updated automatically
SELECT * FROM vw_order_summary ORDER BY order_id;
SELECT customer_id, name, total_spent, tier FROM customers WHERE customer_id <= 10 ORDER BY customer_id;