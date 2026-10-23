-- Triggers deduct stock

-- Purpose: Updates the stock quantity when an order is placed or cancelled.
-- It relies on the log trigger to record the change.

CREATE OR REPLACE FUNCTION fn_trg_deduct_stock()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- 1. Handle new orders (INSERT)
    IF TG_OP = 'INSERT' THEN
        -- Tell the log trigger what is happening
        PERFORM set_config('inventory.change_type', 'ORDER', true);
        PERFORM set_config('inventory.reference_id', NEW.order_id::TEXT, true);

        -- Deduct the stock
        UPDATE products
           SET stock_qty = stock_qty - NEW.quantity
         WHERE product_id = NEW.product_id;

    -- 2. Handle cancelled orders (DELETE)
    ELSIF TG_OP = 'DELETE' THEN
        -- Tell the log trigger what is happening
        PERFORM set_config('inventory.change_type', 'ORDER_CANCELLED', true);
        PERFORM set_config('inventory.reference_id', OLD.order_id::TEXT, true);

        -- Add the stock back
        UPDATE products
           SET stock_qty = stock_qty + OLD.quantity
         WHERE product_id = OLD.product_id;
    END IF;

    RETURN NULL;
END;
$$;

-- Create the trigger
DROP TRIGGER IF EXISTS trg_deduct_stock ON order_details;
CREATE TRIGGER trg_deduct_stock
AFTER INSERT OR DELETE ON order_details
FOR EACH ROW
EXECUTE FUNCTION fn_trg_deduct_stock();