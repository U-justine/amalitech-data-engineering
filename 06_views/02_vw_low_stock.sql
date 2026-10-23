-- View: Low Stock Products

-- Purpose: Shows products whose stock has fallen below their reorder level.
-- It calculates how many are missing (shortfall), suggests an order quantity, 
-- and labels the urgency (OUT OF STOCK, CRITICAL, or LOW).

CREATE OR REPLACE VIEW vw_low_stock AS
SELECT
    p.product_id,
    p.name,
    p.category,
    p.stock_qty,
    p.reorder_level,
    -- Calculate how many items are missing to reach the reorder level
    p.reorder_level - p.stock_qty AS shortfall,
    -- Suggest ordering enough to reach 2x the reorder level
    GREATEST(p.reorder_level * 2 - p.stock_qty, 0) AS suggested_order_qty,
    -- Label the urgency based on current stock
    CASE
        WHEN p.stock_qty = 0 THEN 'OUT OF STOCK'
        WHEN p.stock_qty < p.reorder_level / 2 THEN 'CRITICAL'
        ELSE 'LOW'
    END AS stock_status
FROM products p
WHERE p.stock_qty < p.reorder_level;

SELECT * FROM vw_low_stock;