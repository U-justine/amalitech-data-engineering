-- View: Order Summary

-- Purpose: Shows one row per order with customer name, date, total amount, 
-- number of distinct products, total physical items, and discount given.

CREATE OR REPLACE VIEW vw_order_summary AS
SELECT
    o.order_id,
    c.customer_id,
    c.name                                         AS customer_name,
    o.order_date,
    o.total_amount,
    COUNT(od.order_detail_id)                      AS distinct_products,
    COALESCE(SUM(od.quantity), 0)                  AS total_items,
    COALESCE(SUM(od.quantity * od.unit_price - od.line_total), 0) AS discount_given
FROM orders o
JOIN customers c           ON c.customer_id = o.customer_id
LEFT JOIN order_details od ON od.order_id   = o.order_id
GROUP BY o.order_id, c.customer_id, c.name, o.order_date, o.total_amount;

SELECT * FROM vw_order_summary ORDER BY order_date DESC;