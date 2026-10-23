-- Insert products_data into Products table

INSERT INTO products (name, category, price_usd, stock_qty, reorder_level) VALUES
    ('Laptop Pro 15"',              'Electronics', 1200.00,  50,  10),
    ('Wireless Mouse',              'Electronics',   25.00, 200,  50),
    ('Mechanical Keyboard',         'Electronics',   85.00, 100,  20),
    ('Noise Cancelling Headphones', 'Electronics',  250.00,  30,  15),
    ('4K Monitor 27"',              'Electronics',  350.00,  20,   5),
    ('USB-C Hub',                   'Electronics',   45.00, 150,  30),
    ('HD Webcam',                   'Electronics',   80.00,  12,  15),   -- LOW STOCK
    ('Office Chair Ergonomic',      'Furniture',    150.00,  40,  10),
    ('Standing Desk',               'Furniture',    450.00,  15,   5),
    ('Bookshelf',                   'Furniture',    120.00,   8,  10),   -- LOW STOCK
    ('Desk Lamp LED',               'Accessories',   30.00,  14,  15),   -- LOW STOCK
    ('Coffee Mug',                  'Accessories',   12.00, 300, 100),
    ('Leather Backpack',            'Accessories',   45.00,  80,  25),
    ('Wireless Charger',            'Accessories',   35.00,  60,  20),
    ('Laptop Sleeve 15"',           'Accessories',   25.00,  90,  30),
    ('Smartphone Stand',            'Accessories',   15.00, 120,  40),
    ('External SSD 1TB',            'Electronics',  150.00,  45,  15),
    ('Bluetooth Speaker',           'Electronics',   60.00,  75,  20),
    ('Ergonomic Footrest',          'Furniture',     40.00,  35,  10),
    ('Wireless Presenter',          'Electronics',   35.00,  10,  12);   -- LOW STOCK

SELECT * FROM products ORDER BY product_id;
