-- Stored Procedure: Auto Replenish

-- Purpose: Restocks every product that has fallen below its reorder level.
-- It fills stock up to (reorder_level * multiplier) so fast-moving items get more stock.
-- Default is 2x the reorder level, but you can pass a different number.

CREATE OR REPLACE PROCEDURE sp_auto_replenish(
    p_target_multiplier NUMERIC DEFAULT 2,
    INOUT p_restocked   INT     DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_target_multiplier IS NULL OR p_target_multiplier < 1 THEN
        RAISE EXCEPTION 'Target multiplier must be at least 1';
    END IF;

    PERFORM set_config('inventory.change_type', 'REPLENISHMENT', true);
    PERFORM set_config('inventory.note',
                       'Auto-replenish to ' || p_target_multiplier || 'x reorder level', true);

    UPDATE products
       SET stock_qty = CEIL(reorder_level * p_target_multiplier)
     WHERE stock_qty < reorder_level;

    GET DIAGNOSTICS p_restocked = ROW_COUNT;

    PERFORM set_config('inventory.change_type', '', true);
    PERFORM set_config('inventory.note', '', true);

    RAISE NOTICE '% product(s) restocked', p_restocked;
END;
$$;
