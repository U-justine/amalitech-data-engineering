# 02 · Seed Data

| File | Loads |
|---|---|
| `01_products_data.sql` | 20 products in 3 categories. HD Webcam, Bookshelf, Desk Lamp LED and Wireless Presenter start below their reorder level on purpose |
| `02_customers_data.sql` | 20 customers, all starting at 0 spent and Bronze |

Each file ends with a `SELECT` that shows the loaded rows. Exports of these tables are in [`../Initial tables/`](../Initial%20tables/README.md).

## Run order

Run these **after** the triggers exist (see the main README). Opening stock is then logged automatically as `INITIAL` in `inventory_logs`.

## Where are the orders?

The 10 sample orders are in [`../09_tests/01_test_customer_orders.sql`](../09_tests/README.md). They're placed through `sp_place_order`, so the procedure, triggers and views must exist before they run.

## Products

| Category | Products |
|---|---|
| Electronics | Laptop Pro 15", Wireless Mouse, Mechanical Keyboard, Noise Cancelling Headphones, 4K Monitor 27", USB-C Hub, HD Webcam, External SSD 1TB, Bluetooth Speaker, Wireless Presenter |
| Furniture | Office Chair Ergonomic, Standing Desk, Bookshelf, Ergonomic Footrest |
| Accessories | Desk Lamp LED, Coffee Mug, Leather Backpack, Wireless Charger, Laptop Sleeve 15", Smartphone Stand |
