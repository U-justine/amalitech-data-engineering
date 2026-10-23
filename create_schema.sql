-- CREATE SCHEMA

-- 1. Table: products
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price_usd DECIMAL(10, 2) NOT NULL CHECK (price_usd >= 0),
    stock_qty INT NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    reorder_level INT NOT NULL DEFAULT 10
);

-- 2. Table: customers
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    total_spent DECIMAL(10, 2) DEFAULT 0,
    tier VARCHAR(20) DEFAULT 'Bronze'
);

-- 3. Table: orders
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- 4. Table: order_details
CREATE TABLE order_details (
    order_detail_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL,
    line_total DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 5. Table: inventory_logs
CREATE TABLE inventory_logs (
    log_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL,
    change_qty INT NOT NULL, 
    change_type VARCHAR(20) NOT NULL, 
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reference_id INT, 
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 6. Indexes for Performance
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_order_details_order ON order_details(order_id);
CREATE INDEX idx_inventory_logs_product ON inventory_logs(product_id);