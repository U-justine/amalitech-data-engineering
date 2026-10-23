-- View: Customer Spending
-- Purpose: A full dashboard for every customer. Shows their tier, order count, 
-- total spend, average order value, favourite category, and their revenue rank.
-- It uses a CTE inside a CTE to handle the complex grouping.

CREATE OR REPLACE VIEW vw_customer_spending AS
WITH customer_orders AS (

    -- Inner CTEs: Find every line item and figure out the customer's favourite category
    WITH order_lines AS (
        SELECT o.customer_id,
               o.order_id,
               o.order_date,
               p.category,
               od.quantity,
               od.line_total,
               od.quantity * od.unit_price - od.line_total AS amount_saved
          FROM orders o
          JOIN order_details od ON od.order_id = o.order_id
          JOIN products p ON p.product_id = od.product_id
    ),
    category_spend AS (
        SELECT customer_id,
               category,
               ROW_NUMBER() OVER (PARTITION BY customer_id
                                  ORDER BY SUM(line_total) DESC, category) AS category_rank
          FROM order_lines
         GROUP BY customer_id, category
    )
	
    -- Combine the line items with the favourite category
    SELECT ol.customer_id,
           COUNT(DISTINCT ol.order_id) AS order_count,
           SUM(ol.quantity) AS items_bought,
           SUM(ol.line_total) AS total_spent,
           SUM(ol.amount_saved) AS total_saved,
           MAX(ol.order_date) AS last_order_date,
           cs.category AS favourite_category
      FROM order_lines ol
      JOIN category_spend cs
        ON cs.customer_id = ol.customer_id AND cs.category_rank = 1
     GROUP BY ol.customer_id, cs.category
),
ranked AS (

    -- Outer CTE: Rank the customers by how much they spent
    SELECT co.*,
           RANK() OVER (ORDER BY co.total_spent DESC) AS spend_rank,
           ROUND(100 * co.total_spent / SUM(co.total_spent) OVER (), 1) AS pct_of_revenue
      FROM customer_orders co
)

-- Final output: Join with the customers table to get names/tiers
SELECT c.customer_id,
       c.name AS customer_name,
       c.email,
       c.tier,
       COALESCE(r.order_count, 0) AS order_count,
       COALESCE(r.items_bought, 0) AS items_bought,
       COALESCE(r.total_spent, 0) AS total_spent,
       COALESCE(ROUND(r.total_spent / NULLIF(r.order_count, 0), 2), 0) AS avg_order_value,
       COALESCE(r.total_saved, 0) AS total_saved,
       r.favourite_category,
       r.last_order_date,
       r.spend_rank,
       COALESCE(r.pct_of_revenue, 0) AS pct_of_revenue
  FROM customers c
  LEFT JOIN ranked r ON r.customer_id = c.customer_id;


SELECT * FROM vw_customer_spending ORDER BY total_spent DESC;