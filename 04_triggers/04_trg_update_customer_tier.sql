-- triggers update customer's tier

-- Purpose: Automatically recalculates a customer's total_spent and 
-- upgrades their tier (Bronze/Silver/Gold) whenever an order is updated or deleted. 
-- It recalculates from scratch to prevent double-counting bugs.

-- 1. Helper function: Returns the tier based on the total spent amount.
CREATE OR REPLACE FUNCTION fn_customer_tier(p_total_spent NUMERIC)
RETURNS VARCHAR(10)
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_total_spent >= 1000 THEN 'Gold'
        WHEN p_total_spent >=  500 THEN 'Silver'
        ELSE 'Bronze'
    END;
$$;


-- 2. Helper function: Recalculates the total spent for a specific customer.
-- It adds up all their orders and updates the customer's tier.
CREATE OR REPLACE FUNCTION fn_refresh_customer(p_customer_id INT)
RETURNS VOID
LANGUAGE sql
AS $$
    UPDATE customers c
       SET total_spent = s.total,
           tier        = fn_customer_tier(s.total)
      FROM (SELECT COALESCE(SUM(total_amount), 0) AS total
              FROM orders
             WHERE customer_id = p_customer_id) s
     WHERE c.customer_id = p_customer_id;
$$;


-- 3. The Trigger Function: Fires when an order changes.
CREATE OR REPLACE FUNCTION fn_trg_update_customer_tier()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- If an order is updated or deleted, recalculate the OLD customer's tier
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM fn_refresh_customer(OLD.customer_id);
    END IF;
    
    -- If an order is moved to a NEW customer, recalculate that new customer too
    IF TG_OP = 'UPDATE' AND NEW.customer_id <> OLD.customer_id THEN
        PERFORM fn_refresh_customer(NEW.customer_id);
    END IF;
    
    RETURN NULL;
END;
$$;

-- 4. Attach the trigger to the orders table.
DROP TRIGGER IF EXISTS trg_update_customer_tier ON orders;
CREATE TRIGGER trg_update_customer_tier
AFTER UPDATE OF total_amount, customer_id OR DELETE ON orders
FOR EACH ROW
EXECUTE FUNCTION fn_trg_update_customer_tier();