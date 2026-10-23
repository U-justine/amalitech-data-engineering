-- Stored Procedure: Replenish Product

-- Purpose: Adds stock to ONE product (e.g., when a delivery arrives).
-- The inventory log will automatically record this as 'REPLENISHMENT'.

CREATE OR REPLACE PROCEDURE sp_replenish_product(
    p_product_id INT,
    p_quantity   INT,
    p_note       TEXT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_quantity IS NULL OR p_quantity <= 0 THEN
        RAISE EXCEPTION 'Replenishment quantity must be greater than 0';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM products WHERE product_id = p_product_id) THEN
        RAISE EXCEPTION 'Product % does not exist', p_product_id;
    END IF;

    PERFORM set_config('inventory.change_type', 'REPLENISHMENT', true);
    PERFORM set_config('inventory.note', COALESCE(p_note, 'Manual replenishment'), true);

    UPDATE products
       SET stock_qty = stock_qty + p_quantity
     WHERE product_id = p_product_id;

    PERFORM set_config('inventory.change_type', '', true);
    PERFORM set_config('inventory.note', '', true);

    RAISE NOTICE 'Added % units to product %', p_quantity, p_product_id;
END;
$$;
