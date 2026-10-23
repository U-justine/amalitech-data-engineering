-- Final Database State Check

-- Run this to see a clean summary of all the data currently in the database.

-- 1. Check Customers (Tiers & Spending)
SELECT customer_id, name, total_spent, tier 
FROM customers 
WHERE total_spent > 0 
ORDER BY total_spent DESC;

-- 2. Check recent Orders
SELECT 
    o.order_id, 
    c.name AS customer_name, 
    o.total_amount, 
    o.order_date::DATE AS order_date
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
ORDER BY o.order_id DESC 
LIMIT 5;

-- 3. Check recent Order Details (Discounts)
SELECT order_id, product_id, quantity, unit_price, discount_pct, line_total 
FROM order_details 
ORDER BY order_id DESC LIMIT 5;

-- 4. Check the Master Audit Log (Inventory History)
SELECT log_id, product_id, change_type, change_qty, previous_qty, new_qty, note 
FROM inventory_logs 
ORDER BY log_id DESC LIMIT 10;

-- 5. Check current Product Stock (Low Stock Alerts)
SELECT product_id, name, stock_qty, reorder_level 
FROM products 
ORDER BY product_id;