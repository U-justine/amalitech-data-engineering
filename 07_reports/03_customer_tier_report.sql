-- Report: Customer Tier & Insights

-- Purpose: Shows customer spending, tier summaries, bulk discounts, 
-- and the top-spending customer in each product category.

-- 1. Every customer, highest spenders first
SELECT customer_id, customer_name, tier, order_count, total_spent,
       avg_order_value, favourite_category, spend_rank
  FROM vw_customer_spending
 ORDER BY total_spent DESC, customer_name;



-- 2. Tier summary
SELECT tier,
       COUNT(*) AS customers,
       SUM(total_spent) AS revenue,
       ROUND(100 * SUM(total_spent) / NULLIF((SELECT SUM(total_amount) FROM orders), 0), 1) AS pct_of_revenue,
       ROUND(AVG(total_spent), 2) AS avg_spend
  FROM vw_customer_spending
 GROUP BY tier
 ORDER BY CASE tier WHEN 'Gold' THEN 1 WHEN 'Silver' THEN 2 ELSE 3 END;


-- 3. How far each customer is from the next tier
SELECT customer_name, tier, total_spent,
       CASE tier WHEN 'Bronze' THEN 500 - total_spent
                 WHEN 'Silver' THEN 1000 - total_spent END AS spend_to_next_tier
  FROM vw_customer_spending
 WHERE tier <> 'Gold' AND order_count > 0
 ORDER BY spend_to_next_tier;



-- 4. Top customer per category (CTE inside a CTE)
-- Purpose: Finds the #1 highest spender in each product category.

-- How it works:
--   category_leaders (Outer CTE)
--     ├─ category_sales (Inner CTE: Total revenue per category)
--     └─ customer_category (Inner CTE: Spend per customer per category, ranked)

WITH category_leaders AS (
    WITH category_sales AS (
        SELECT p.category, SUM(od.line_total) AS category_revenue
          FROM order_details od
          JOIN products p ON p.product_id = od.product_id
         GROUP BY p.category
    ),
    customer_category AS (
        SELECT p.category,
               o.customer_id,
               SUM(od.line_total) AS customer_spent,
               ROW_NUMBER() OVER (PARTITION BY p.category
                                  ORDER BY SUM(od.line_total) DESC, o.customer_id) AS position
          FROM order_details od
          JOIN orders o   ON o.order_id   = od.order_id
          JOIN products p ON p.product_id = od.product_id
         GROUP BY p.category, o.customer_id
    )
    SELECT cs.category, cs.category_revenue, cc.customer_id, cc.customer_spent
      FROM category_sales cs
      JOIN customer_category cc
        ON cc.category = cs.category AND cc.position = 1
)
SELECT cl.category,
       cl.category_revenue,
       c.name AS top_customer,
       cl.customer_spent AS top_customer_spent,
       ROUND(100 * cl.customer_spent / cl.category_revenue, 1) AS pct_of_category
  FROM category_leaders cl
  JOIN customers c ON c.customer_id = cl.customer_id
 ORDER BY cl.category_revenue DESC;



-- 5. Bulk discounts applied
SELECT od.order_id,
       c.name AS customer,
       p.name AS product,
       od.quantity,
       od.discount_pct || '%' AS discount,
       od.quantity * od.unit_price AS list_value,
       od.line_total,
       od.quantity * od.unit_price - od.line_total AS customer_saved
  FROM order_details od
  JOIN orders o ON o.order_id = od.order_id
  JOIN customers c ON c.customer_id = o.customer_id
  JOIN products p ON p.product_id = od.product_id
 WHERE od.discount_pct > 0
 ORDER BY customer_saved DESC;