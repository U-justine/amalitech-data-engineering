-- Stored Procedure place holder

-- Purpose: Places a whole order (with multiple products) in ONE call.
-- It checks stock, creates the order, and lets the triggers handle the math.

-- Helper function to turn the JSON shopping cart into a readable table

CREATE OR REPLACE FUNCTION fn_parse_order_items(p_items JSONB)
RETURNS TABLE (product_id INT, quantity INT)
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT (item ->> 'product_id')::INT,
           SUM((item ->> 'quantity')::INT)::INT
      FROM jsonb_array_elements(p_items) AS item
     GROUP BY (item ->> 'product_id')::INT;
$$;


CREATE OR REPLACE PROCEDURE sp_place_order(
    p_customer_id  INT,
    p_items        JSONB,
    INOUT p_order_id INT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_bad RECORD;
BEGIN
    -- 1. Validation checks
	
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = p_customer_id) THEN
        RAISE EXCEPTION 'Customer % does not exist', p_customer_id;
    END IF;

    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'Order must contain at least one item';
    END IF;

    -- Check for bad quantities
	
    SELECT * INTO v_bad
      FROM fn_parse_order_items(p_items) i
     WHERE i.product_id IS NULL OR i.quantity IS NULL OR i.quantity <= 0
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Every item needs a valid product_id and quantity > 0';
    END IF;

    -- Check if product exists
	
    SELECT i.product_id INTO v_bad
      FROM fn_parse_order_items(p_items) i
      LEFT JOIN products p ON p.product_id = i.product_id
     WHERE p.product_id IS NULL
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Product % does not exist', v_bad.product_id;
    END IF;

    -- 2. Lock products and check stock
	
    PERFORM 1
       FROM products
      WHERE product_id IN (SELECT i.product_id FROM fn_parse_order_items(p_items) i)
      ORDER BY product_id
        FOR UPDATE;

    SELECT p.name, p.stock_qty, i.quantity INTO v_bad
      FROM fn_parse_order_items(p_items) i
      JOIN products p ON p.product_id = i.product_id
     WHERE p.stock_qty < i.quantity
     ORDER BY p.product_id
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Insufficient stock for "%": requested %, available %',
                        v_bad.name, v_bad.quantity, v_bad.stock_qty;
    END IF;

    -- 3. Create the order and the line items
	
    INSERT INTO orders (customer_id)
    VALUES (p_customer_id)
    RETURNING order_id INTO p_order_id;

    INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount_pct, line_total)
    SELECT p_order_id,
           i.product_id,
           i.quantity,
           p.price_usd,
           fn_bulk_discount(i.quantity),
           ROUND(i.quantity * p.price_usd * (1 - fn_bulk_discount(i.quantity) / 100), 2)
      FROM fn_parse_order_items(p_items) i
      JOIN products p ON p.product_id = i.product_id
     ORDER BY i.product_id;

    RAISE NOTICE 'Order % placed for customer %', p_order_id, p_customer_id;
END;
$$;