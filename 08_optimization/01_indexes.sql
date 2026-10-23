-- Optimization: Indexes

-- Purpose: Speeds up queries by creating indexes on Foreign Keys, 
-- date ranges, and frequently searched columns.


-- 1. Orders indexes

-- Speeds up finding orders by customer, sorted by date
CREATE INDEX IF NOT EXISTS idx_orders_customer_date
    ON orders (customer_id, order_date);

-- Speeds up date-range reports (monthly revenue)
CREATE INDEX IF NOT EXISTS idx_orders_date
    ON orders (order_date);


-- 2. Order Details indexes

-- Speeds up finding which orders contain a specific product
CREATE INDEX IF NOT EXISTS idx_order_details_product
    ON order_details (product_id);


-- 3. Inventory Logs indexes

-- Speeds up viewing the history of a specific product over time
CREATE INDEX IF NOT EXISTS idx_inv_logs_product_time
    ON inventory_logs (product_id, changed_at);

-- Speeds up filtering logs by type (e.g., all replenishments)
CREATE INDEX IF NOT EXISTS idx_inv_logs_type_time
    ON inventory_logs (change_type, changed_at);

-- Speeds up finding logs for a specific order
CREATE INDEX IF NOT EXISTS idx_inv_logs_reference
    ON inventory_logs (reference_id) WHERE reference_id IS NOT NULL;


-- 4. Products indexes

-- A partial index: ONLY indexes products that are low on stock.
-- Keeps the index tiny and super fast for the low_stock view.
CREATE INDEX IF NOT EXISTS idx_products_low_stock
    ON products (product_id) WHERE stock_qty < reorder_level;

-- Speeds up category reports
CREATE INDEX IF NOT EXISTS idx_products_category
    ON products (category);

-- Update the database statistics so the query planner is smart
ANALYZE;