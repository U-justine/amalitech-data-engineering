-- INSERT DATA INTO TABLES

-- 1. Insert 20 Products (4 are intentionally low stock)

INSERT INTO products (name, category, price_usd, stock_qty, reorder_level) VALUES
('Laptop Pro 15"', 'Electronics', 1200.00, 50, 10),
('Wireless Mouse', 'Electronics', 25.00, 200, 50),
('Mechanical Keyboard', 'Electronics', 85.00, 100, 20),
('Noise Cancelling Headphones', 'Electronics', 250.00, 30, 15),
('4K Monitor 27"', 'Electronics', 350.00, 20, 5),
('USB-C Hub', 'Electronics', 45.00, 150, 30),
('HD Webcam', 'Electronics', 80.00, 12, 15),          -- LOW STOCK!
('Office Chair Ergonomic', 'Furniture', 150.00, 40, 10),
('Standing Desk', 'Furniture', 450.00, 15, 5),
('Bookshelf', 'Furniture', 120.00, 8, 10),            -- LOW STOCK!
('Desk Lamp LED', 'Accessories', 30.00, 14, 15),      -- LOW STOCK!
('Coffee Mug', 'Accessories', 12.00, 300, 100),
('Leather Backpack', 'Accessories', 45.00, 80, 25),
('Wireless Charger', 'Accessories', 35.00, 60, 20),
('Laptop Sleeve 15"', 'Accessories', 25.00, 90, 30),
('Smartphone Stand', 'Accessories', 15.00, 120, 40),
('External SSD 1TB', 'Electronics', 150.00, 45, 15),
('Bluetooth Speaker', 'Electronics', 60.00, 75, 20),
('Ergonomic Footrest', 'Furniture', 40.00, 35, 10),
('Wireless Presenter', 'Electronics', 35.00, 10, 12); -- LOW STOCK!

-- check the TABLE

SELECT * FROM products;

-- 2. Insert 20 Customers (Starts with 0 spending and Bronze tier)

INSERT INTO customers (name, email, phone) VALUES
('Alice Smith', 'alice.smith@gmail.com', '+250788111001'),
('Bob Johnson', 'bob.johnson@gmail.com', '+250788111002'),
('Charlie Brown', 'charlie.brown@gmail.com', '+250788111003'),
('Diana Prince', 'diana.prince@gmail.com', '+250788111004'),
('Ethan Hunt', 'ethan.hunt@gmail.com', '+250788111005'),
('Fatima Al-Sayed', 'fatima.alsayed@gmail.com', '+250788111006'),
('Jean Paul Nkurunziza', 'jeanpaul.nk@gmail.com', '+250788111007'),
('Marie Claire Uwase', 'marieclaire.uwase@gmail.com', '+250788111008'),
('David Ochieng', 'david.ochieng@gmail.com', '+250788111009'),
('Grace Mukamana', 'grace.mukamana@gmail.com', '+250788111010'),
('Hassan Abdi', 'hassan.abdi@gmail.com', '+250788111011'),
('Ivy Chen', 'ivy.chen@gmail.com', '+250788111012'),
('Jack O''Connor', 'jack.oconnor@gmail.com', '+250788111013'),
('Keziah Wambui', 'keziah.wambui@gmail.com', '+250788111014'),
('Liam Neeson', 'liam.neeson@gmail.com', '+250788111015'),
('Monica Geller', 'monica.geller@gmail.com', '+250788111016'),
('Nathan Drake', 'nathan.drake@gmail.com', '+250788111017'),
('Olivia Pope', 'olivia.pope@gmail.com', '+250788111018'),
('Peter Parker', 'peter.parker@gmail.com', '+250788111019'),
('Queen Latifah', 'queen.latifah@gmail.com', '+250788111020');

-- check the TABLE

SELECT * FROM customers;

-- count records in each TABLE

SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM customers;

