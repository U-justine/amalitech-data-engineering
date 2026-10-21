-- BUSINESS REPORTS

-- 1. Customer Spending & Tier Report
-- Shows how much every customer has spent and their current tier.

SELECT 
    customer_id, 
    name, 
    total_spent, 
    tier
FROM customers
ORDER BY total_spent DESC;

-- 2. Top 5 Best-Selling Products
-- Shows which products have been ordered the most.

SELECT 
    p.name AS product_name,
    SUM(od.quantity) AS total_quantity_sold
FROM order_details od
JOIN products p ON od.product_id = p.product_id
GROUP BY p.name
ORDER BY total_quantity_sold DESC
LIMIT 5;

-- 3. Monthly Revenue Summary
-- Shows how many orders were placed and how much money was made each month.

SELECT 
    TO_CHAR(order_date, 'YYYY-MM') AS month,
    COUNT(order_id) AS total_orders,
    SUM(total_amount) AS total_revenue
FROM orders
GROUP BY TO_CHAR(order_date, 'YYYY-MM')
ORDER BY month DESC;

-- 4. Bulk Discount Report
-- Shows which orders received a discount (line total is less than unit_price * quantity).

SELECT 
    order_id,
    product_id,
    quantity,
    unit_price,
    line_total
FROM order_details
WHERE line_total < (unit_price * quantity);