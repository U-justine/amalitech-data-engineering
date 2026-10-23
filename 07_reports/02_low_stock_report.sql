-- Report: Low Stock & Best Sellers

-- Purpose: Shows products that need replenishing immediately, products that are about to run out, 
-- the top 5 best sellers, and calculates how many days of stock are left based on recent sales.


-- 1. Flagged: below reorder level
SELECT * FROM vw_low_stock ORDER BY stock_status, shortfall DESC;


-- 2. Early warning: within 25% above the reorder level
SELECT product_id, name, category, stock_qty, reorder_level
  FROM products
 WHERE stock_qty >= reorder_level
   AND stock_qty <  reorder_level * 1.25
 ORDER BY stock_qty::NUMERIC / NULLIF(reorder_level, 0);


-- 3. Top 5 best-selling products

SELECT p.name AS product_name,
       p.category,
       SUM(od.quantity) AS total_quantity_sold,
       SUM(od.line_total) AS revenue
  FROM order_details od
  JOIN products p ON p.product_id = od.product_id
 GROUP BY p.product_id, p.name, p.category
 ORDER BY total_quantity_sold DESC
 LIMIT 5;



-- 4. Days of stock left at the current sales rate (CTE inside a CTE)

-- Purpose: Calculates how many days the current stock will last based on 
-- sales from the last 90 days, and flags if action is needed.

-- How it works:
--   stock_cover (Outer CTE)
--     ├─ sales_90d (Inner CTE: Calculates units sold in the last 90 days)
--     └─ restocks  (Inner CTE: Finds the last time each product was restocked)
-- ==========================================
WITH stock_cover AS (
    WITH sales_90d AS (
        SELECT od.product_id, SUM(od.quantity) AS units_sold
          FROM order_details od
          JOIN orders o ON o.order_id = od.order_id
         WHERE o.order_date >= CURRENT_DATE - INTERVAL '90 days'
         GROUP BY od.product_id
    ),
    restocks AS (
        SELECT product_id, MAX(changed_at) AS last_restocked
          FROM inventory_logs
         WHERE change_type = 'REPLENISHMENT'
         GROUP BY product_id
    )
    SELECT p.product_id, p.name, p.stock_qty, p.reorder_level,
           COALESCE(s.units_sold, 0) AS units_sold_90d,
           r.last_restocked
      FROM products p
      LEFT JOIN sales_90d s ON s.product_id = p.product_id
      LEFT JOIN restocks  r ON r.product_id = p.product_id
)
SELECT name, stock_qty, reorder_level, units_sold_90d,
       CASE WHEN units_sold_90d = 0 THEN NULL
            ELSE FLOOR(stock_qty * 90.0 / units_sold_90d) END AS days_of_stock_left,
       last_restocked::DATE AS last_restocked,
       CASE WHEN stock_qty < reorder_level THEN 'REORDER NOW'
            WHEN units_sold_90d > 0
             AND stock_qty * 90.0 / units_sold_90d < 30 THEN 'REORDER SOON'
            WHEN units_sold_90d = 0 THEN 'NO RECENT SALES'
            ELSE 'OK' END AS action
  FROM stock_cover
 ORDER BY days_of_stock_left NULLS LAST;