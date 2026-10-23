-- Report: Inventory Audit History

-- Purpose: A complete audit trail of every stock change. It calculates 
-- running balances, summarizes movements, and checks for missing logs.


-- 1. Filtered history with a running stock balance (CTE inside a CTE)

-- Purpose: Shows a timeline of stock changes for a specific product
-- and calculates the running balance after every single change.

-- How it works:
--   history (Outer CTE)
--     ├─ params (Inner CTE: Your filters for product and date)
--     └─ filtered (Inner CTE: Log rows matching the filters)
-- ==========================================
WITH history AS (
    WITH params AS (
        SELECT NULL::INT AS product_id,                     
               CURRENT_DATE - INTERVAL '1 year' AS date_from,  -- Start date
               CURRENT_DATE + INTERVAL '1 day'  AS date_to     -- End date
    ),
    filtered AS (
        SELECT l.*
          FROM inventory_logs l, params pr
         WHERE (pr.product_id IS NULL OR l.product_id = pr.product_id)
           AND l.changed_at >= pr.date_from
           AND l.changed_at <  pr.date_to
    )
    SELECT f.*,
           SUM(f.change_qty) OVER (PARTITION BY f.product_id ORDER BY f.log_id) AS running_balance
      FROM filtered f
)
SELECT h.log_id,
       h.changed_at,
       p.name AS product,
       h.change_type,
       h.change_qty,
       h.previous_qty,
       h.new_qty,
       h.running_balance,
       h.reference_id AS order_id,
       h.note,
       h.changed_by
  FROM history h
  JOIN products p ON p.product_id = h.product_id
 ORDER BY h.product_id, h.log_id;



-- 2. Movement summary per product
SELECT p.product_id,
       p.name,
       SUM(l.change_qty) FILTER (WHERE l.change_type = 'INITIAL') AS opening,
       -SUM(l.change_qty) FILTER (WHERE l.change_type = 'ORDER') AS sold,
       SUM(l.change_qty) FILTER (WHERE l.change_type = 'ORDER_CANCELLED') AS returned,
       SUM(l.change_qty) FILTER (WHERE l.change_type = 'REPLENISHMENT') AS replenished,
       SUM(l.change_qty) FILTER (WHERE l.change_type = 'ADJUSTMENT') AS adjusted,
       SUM(l.change_qty) AS net_from_log,
       p.stock_qty AS current_stock
  FROM products p
  LEFT JOIN inventory_logs l ON l.product_id = p.product_id
 GROUP BY p.product_id, p.name, p.stock_qty
 ORDER BY p.product_id;



-- 3. Reconciliation: rows here mean stock changed without a log entry
SELECT p.product_id, p.name, p.stock_qty,
       COALESCE(SUM(l.change_qty), 0) AS net_from_log
  FROM products p
  LEFT JOIN inventory_logs l ON l.product_id = p.product_id
 GROUP BY p.product_id, p.name, p.stock_qty
HAVING p.stock_qty <> COALESCE(SUM(l.change_qty), 0);



-- 4. Everything that happened in one order
-- (You can change the ID number 1 at the bottom to check a different order)
SELECT l.log_id, l.change_type, p.name, l.change_qty, l.changed_at
  FROM inventory_logs l
  JOIN products p ON p.product_id = l.product_id
 WHERE l.reference_id = 1
 ORDER BY l.log_id;