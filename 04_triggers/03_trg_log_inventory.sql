-- triggers log inventory

-- Purpose: Writes a record in the inventory_logs table for EVERY stock change.
-- It acts as an ultimate audit trail. It knows WHY the stock changed 
-- (Order, Restock, Cancellation, or Manual Adjustment) by reading the hidden 
-- messages passed by the other triggers, and it records the exact previous_qty and new_qty.

CREATE OR REPLACE FUNCTION fn_trg_log_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- 1. Handle brand new products
	
    IF TG_OP = 'INSERT' THEN
        IF NEW.stock_qty > 0 THEN
            INSERT INTO inventory_logs
                (product_id, change_qty, change_type, previous_qty, new_qty)
            VALUES
                (NEW.product_id, NEW.stock_qty, 'INITIAL', 0, NEW.stock_qty);
        END IF;

    -- 2. Handle any stock change (orders, cancellations, restocks)
	
    ELSIF NEW.stock_qty <> OLD.stock_qty THEN
        INSERT INTO inventory_logs
            (product_id, change_qty, change_type, previous_qty, new_qty, reference_id, note)
        VALUES
            (NEW.product_id,
             NEW.stock_qty - OLD.stock_qty,
             COALESCE(NULLIF(current_setting('inventory.change_type', true), ''), 'ADJUSTMENT'),
             OLD.stock_qty,
             NEW.stock_qty,
             NULLIF(current_setting('inventory.reference_id', true), '')::INT,
             NULLIF(current_setting('inventory.note', true), ''));
    END IF;
    
    RETURN NULL;
END;
$$;

-- Create the trigger
DROP TRIGGER IF EXISTS trg_log_inventory ON products;
CREATE TRIGGER trg_log_inventory
AFTER INSERT OR UPDATE OF stock_qty ON products
FOR EACH ROW
EXECUTE FUNCTION fn_trg_log_inventory();