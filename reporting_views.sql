-- REPORTING VIEWS

-- These views act as virtual tables to simplify complex data access for reporting and low-stock alerts.

-- 1. VIEW: Order Summary

-- Combines customers, orders, and details into one clean report.

CREATE OR REPLACE VIEW vw_order_summary AS
SELECT 
    o.order_id,
    c.name AS customer_name,
    o.order_date,
    o.total_amount,
    COUNT(od.order_detail_id) AS number_of_items
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_details od ON o.order_id = od.order_id
GROUP BY o.order_id, c.name, o.order_date, o.total_amount
ORDER BY o.order_date DESC;

-- 2. VIEW: Low Stock Products

-- Shows products where the stock has fallen to or below the reorder level.

CREATE OR REPLACE VIEW vw_low_stock AS
SELECT 
    product_id,
    name,
    category,
    stock_qty,
    reorder_level
FROM products
WHERE stock_qty <= reorder_level;

-- See the order summary
SELECT * FROM vw_order_summary;

-- See the low stock alerts
SELECT * FROM vw_low_stock;