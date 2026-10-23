-- Report: Order Summary per Customer

-- Purpose: Shows order details per customer, a customer spending leaderboard, 
-- and monthly revenue (including months with no sales).


-- 1. Every order, grouped by customer

SELECT customer_name, order_id, order_date::DATE AS order_date,
       total_amount, distinct_products, total_items, discount_given
  FROM vw_order_summary
 ORDER BY customer_name, order_date;


-- 2. One line per customer (CTE inside a CTE)

-- Purpose: Calculates the total money spent, total items bought, and average 
-- order value for each customer, then ranks them from highest spender to lowest.

-- How it works:
--   customer_summary (Outer CTE)
--     └─ per_order   (Inner CTE: Groups all orders by customer first)

WITH customer_summary AS (
    WITH per_order AS (
        SELECT customer_id, customer_name, order_id, order_date,
               total_amount, total_items
          FROM vw_order_summary
    )
    SELECT customer_id,
           customer_name,
           COUNT(*)                       AS orders,
           SUM(total_items)               AS items_bought,
           SUM(total_amount)              AS total_spent,
           ROUND(AVG(total_amount), 2)    AS avg_order_value,
           MIN(order_date)::DATE          AS first_order,
           MAX(order_date)::DATE          AS latest_order
      FROM per_order
     GROUP BY customer_id, customer_name
)
SELECT RANK() OVER (ORDER BY total_spent DESC) AS rank, *
  FROM customer_summary
 ORDER BY total_spent DESC;


-- 3. Monthly revenue, incl. months with no sales (CTE inside a CTE) --
--   monthly                   (outer)
--     └─ months               (inner: every month from first order to now)

WITH monthly AS (
    WITH months AS (
        SELECT generate_series(
                   date_trunc('month', (SELECT MIN(order_date) FROM orders)),
                   date_trunc('month', CURRENT_DATE),
                   INTERVAL '1 month')::DATE AS month_start
    )
    SELECT m.month_start,
           COUNT(o.order_id)                 AS total_orders,
           COALESCE(SUM(o.total_amount), 0)  AS total_revenue
      FROM months m
      LEFT JOIN orders o
        ON o.order_date >= m.month_start
       AND o.order_date <  m.month_start + INTERVAL '1 month'
     GROUP BY m.month_start
)
SELECT TO_CHAR(month_start, 'YYYY-MM')                            AS month,
       total_orders,
       total_revenue,
       SUM(total_revenue) OVER (ORDER BY month_start)             AS running_revenue,
       total_revenue - LAG(total_revenue) OVER (ORDER BY month_start) AS change_vs_last_month
  FROM monthly
 ORDER BY month_start;
