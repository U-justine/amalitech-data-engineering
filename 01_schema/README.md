# 01 · Schema

Creates the database and its five tables, then adds the business-rule constraints.

| File | Creates |
|---|---|
| `01_create_database.sql` | The `inventory` database |
| `02_products.sql` | `products`: name, category, `price_usd`, `stock_qty`, `reorder_level` |
| `03_customers.sql` | `customers`: name, email, phone, `total_spent`, `tier` |
| `04_orders.sql` | `orders`: `customer_id` → customers, `order_date`, `total_amount` |
| `05_order_details.sql` | `order_details`: `order_id` → orders, `product_id` → products, quantity, price, discount, line total |
| `06_inventory_logs.sql` | `inventory_logs`: one row per stock change, with before/after quantities |
| `07_constraints.sql` | `CHECK` and `UNIQUE` rules for all five tables |

## Relationships

- A customer has many orders. A customer with orders can't be deleted (`ON DELETE RESTRICT`).
- An order has many order lines. Deleting an order deletes its lines (`ON DELETE CASCADE`), and the stock trigger puts that stock back.
- A product appears in many order lines and many log rows. A product with history can't be deleted.

## Constraints (`07_constraints.sql`)

| Table | Rules |
|---|---|
| `products` | Unique name, price > 0, stock ≥ 0, reorder level ≥ 0 |
| `customers` | Unique email, basic email format, total spent ≥ 0, tier is Bronze, Silver or Gold |
| `orders` | Total ≥ 0 |
| `order_details` | One line per product per order, quantity > 0, unit price > 0, discount between 0 and 100, line total ≥ 0 |
| `inventory_logs` | Change type from a fixed list, `new_qty = previous_qty + change_qty`, change can't be 0 |

## Run order

Run `01` from the default `postgres` database, then run `02`–`07` on the new `inventory` database, in number order. The table scripts start with `DROP TABLE IF EXISTS … CASCADE`, so re-running them **erases all data**.

ER diagrams: [`../ER DIGRAM.png`](../ER%20DIGRAM.png) (pgAdmin) and [`../docs/er_diagram.png`](../docs/er_diagram.png) (with data types and constraints).
