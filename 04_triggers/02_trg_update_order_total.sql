-- Triggers update order total

-- Purpose: Recalculates the order's total_amount whenever a line item is added or removed.
-- Note: We explicitly block UPDATEs to prevent infinite trigger loops.

CREATE OR REPLACE FUNCTION fn_trg_update_order_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_order_id INT;
BEGIN
    -- Get the order_id based on the action
    IF TG_OP = 'INSERT' THEN
        v_order_id := NEW.order_id;
    ELSIF TG_OP = 'DELETE' THEN
        v_order_id := OLD.order_id;
    ELSE
        RETURN NULL; 
    END IF;

    -- Recalculate the total amount for this order
    UPDATE orders
       SET total_amount = (
           SELECT COALESCE(SUM(line_total), 0)
           FROM order_details
           WHERE order_id = v_order_id
       )
     WHERE order_id = v_order_id;

    RETURN NULL;
END;
$$;

-- Create the trigger
DROP TRIGGER IF EXISTS trg_update_order_total ON order_details;
CREATE TRIGGER trg_update_order_total
AFTER INSERT OR DELETE ON order_details
FOR EACH ROW
EXECUTE FUNCTION fn_trg_update_order_total();