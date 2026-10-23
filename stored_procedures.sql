-- STORED PROCEDURES

-- It automatically calculates order totals and applies bulk discounts based on the quantity the customer buys.

CREATE OR REPLACE PROCEDURE place_order(
    p_order_id INT,      
    p_product_id INT,    
    p_quantity INT       
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_price DECIMAL(10,2); 
    v_total DECIMAL(10,2); 
BEGIN
    -- Step 1: Look up the price of the item in the products table
    SELECT price_usd INTO v_price FROM products WHERE product_id = p_product_id;
    
    -- Step 2: Do the initial math (Price multiplied by Quantity)
    v_total := v_price * p_quantity;
    
    -- Step 3: Check for bulk discount rules (Phase 3)
    IF p_quantity >= 50 THEN
        v_total := v_total * 0.80; 
    ELSIF p_quantity >= 10 THEN
        v_total := v_total * 0.90;
    END IF;
    
    -- Step 4: Write the item into the order_details table
 
    INSERT INTO order_details (order_id, product_id, quantity, unit_price, line_total)
    VALUES (p_order_id, p_product_id, p_quantity, v_price, v_total);
    
    -- Step 5: Add this new total to the main order receipt (orders table)
    UPDATE orders SET total_amount = total_amount + v_total WHERE order_id = p_order_id;
END;
$$;