# Inventory and Order Management System

A PostgreSQL database for an e-commerce company. It manages products, customers and orders, and keeps stock levels correct automatically. Every inventory change is logged for auditing, customers are grouped into Bronze, Silver and Gold tiers by spending, bulk discounts are applied to large orders, and low stock can be replenished in one call.

![ER diagram](ER%20DIGRAM.png)

## Features

- **One call places a whole order.** `sp_place_order` takes a list of products and checks stock for every one first. If anything is short, nothing is saved and the error names the product.
- **Automatic calculations.** Triggers deduct stock, calculate each order's total, apply bulk discounts, and update each customer's total spent and tier. No totals are typed by hand.
- **Audit trail.** Every stock change is written to `inventory_logs`, including opening stock, orders, cancellations, replenishments and manual corrections. Each row records the quantity before and after.
- **Cancelling an order** puts its stock back and lowers the customer's spend and tier.
- **Replenishment.** Restock one product, or every product below its reorder level at once.
- **Views and reports.** These cover order summaries, low stock, customer spending and inventory history. Several queries are built as a CTE inside a CTE.
- **Indexes.** Each one comes with before/after timings measured on 500,000 test rows.
- **Tests.** 14 automated checks print PASS or FAIL, and roll back their changes afterwards.

## Requirements

PostgreSQL 14 or later. Developed in pgAdmin on PostgreSQL 18, and also tested on PostgreSQL 16.

## Project structure

```
inventory-order-management/
├── README.md
├── ER DIGRAM.png                        ER diagram (pgAdmin)
├── run_all.sql                          One-command build for psql (see Known issues)
│
├── 01_schema/                           Database, 5 tables, constraints
├── 02_seed_data/                        20 products, 20 customers
├── 03_order_processing/                 sp_place_order, fn_bulk_discount
├── 04_triggers/                         Stock, order totals, inventory log, customer tier
├── 05_replenishment/                    Restock one product / all low products
├── 06_views/                            Order summary, low stock, customer spending
├── 07_reports/                          Order, stock, tier and audit reports
├── 08_optimization/                     Indexes, before/after EXPLAIN plans
├── 09_tests/                            Sample orders, tests, screenshots, exported results
│   ├── outputs images/
│   └── tables/
├── Initial tables/                      Exports of the data before any orders
│
└── docs/
    ├── design_notes.md                  How it works, decisions, known issues
    └── er_diagram.png                   ER diagram with data types and constraints
```

Every folder has its own `README.md` explaining its files.

## Setup (pgAdmin)

1. Open the Query Tool on the default **postgres** database and run `01_schema/01_create_database.sql`. This creates the **inventory** database.
2. Refresh **Databases**, then open the Query Tool on **inventory**.
3. Open and run (F5) each file below **in this order**:

| # | File | # | File |
|---|---|---|---|
| 1 | `01_schema/02_products.sql` | 12 | `04_triggers/04_trg_update_customer_tier.sql` |
| 2 | `01_schema/03_customers.sql` | 13 | `05_replenishment/01_sp_replenish_product.sql` |
| 3 | `01_schema/04_orders.sql` | 14 | `05_replenishment/02_sp_auto_replenish.sql` |
| 4 | `01_schema/05_order_details.sql` | 15 | `06_views/01_vw_order_summary.sql` |
| 5 | `01_schema/06_inventory_logs.sql` | 16 | `06_views/02_vw_low_stock.sql` |
| 6 | `01_schema/07_constraints.sql` | 17 | `06_views/03_vw_customer_spending.sql` |
| 7 | `08_optimization/01_indexes.sql` | 18 | `02_seed_data/01_products_data.sql` |
| 8 | `03_order_processing/02_fn_bulk_discount.sql` | 19 | `02_seed_data/02_customers_data.sql` |
| 9 | `03_order_processing/01_sp_place_order.sql` | 20 | `09_tests/01_test_customer_orders.sql` |
| 10 | `04_triggers/01_trg_deduct_stock.sql` | 21+ | Remaining `09_tests/` files, `07_reports/`, `08_optimization/02_explain_plans.sql` |
| 11 | `04_triggers/02_trg_update_order_total.sql` | | |

**Why this order:** the sample orders in `09_tests/01_test_customer_orders.sql` go through `sp_place_order`. The procedure, triggers and views must therefore exist first. Otherwise stock wouldn't be deducted and nothing would be logged.

> Run `09_tests/01_test_customer_orders.sql` only **once**. It saves its orders permanently, so running it again places every order a second time.

Test results appear in pgAdmin's **Messages** tab.

## Command cheat sheet

### Orders

```sql
-- Place an order: customer id, then a list of products and quantities
CALL sp_place_order(1, '[{"product_id": 2, "quantity": 3}]');

-- Several products in one order
CALL sp_place_order(1, '[{"product_id": 2, "quantity": 3},
                         {"product_id": 12, "quantity": 50}]');

-- See orders, newest first
SELECT * FROM vw_order_summary ORDER BY order_date DESC;

-- Lines of one order
SELECT * FROM order_details WHERE order_id = 1;

-- Cancel an order (stock goes back, spend and tier update)
DELETE FROM orders WHERE order_id = 1;
```

### Stock

```sql
-- What needs restocking?
SELECT * FROM vw_low_stock;

-- Receive a delivery: product id, quantity, note
CALL sp_replenish_product(10, 25, 'PO-1001');

-- Restock every low product to 2x its reorder level
CALL sp_auto_replenish();

-- Manual correction with a note (logged as ADJUSTMENT)
BEGIN;
SELECT set_config('inventory.note', 'Stock count: 2 damaged', true);
UPDATE products SET stock_qty = stock_qty - 2 WHERE product_id = 7;
COMMIT;
```

### Inventory history

```sql
SELECT * FROM inventory_logs WHERE product_id = 12 ORDER BY log_id;   -- one product
SELECT * FROM inventory_logs WHERE reference_id = 5;                  -- one order
SELECT * FROM inventory_logs WHERE change_type = 'REPLENISHMENT';     -- all restocks
```

### Customers and products

```sql
SELECT * FROM vw_customer_spending ORDER BY total_spent DESC;
SELECT * FROM vw_customer_spending WHERE tier = 'Gold';

INSERT INTO customers (name, email, phone)
VALUES ('Jane Doe', 'jane@example.com', '+250788000000');

-- New product: opening stock is logged automatically
INSERT INTO products (name, category, price_usd, stock_qty, reorder_level)
VALUES ('Desk Mat', 'Accessories', 15.00, 100, 20);

-- Price change: past orders keep the price they were sold at
UPDATE products SET price_usd = 27.00 WHERE product_id = 2;
```

## Business rules

| Rule | Value | Where to change it |
|---|---|---|
| Bulk discount | 10+ units: 10%, 50+ units: 20% (per product line) | `03_order_processing/02_fn_bulk_discount.sql` |
| Customer tier | Bronze below 500, Silver from 500, Gold from 1,000 total spent | `fn_customer_tier` in `04_triggers/04_trg_update_customer_tier.sql` |
| Low stock | `stock_qty` below `reorder_level` | `06_views/02_vw_low_stock.sql` |
| Auto-replenish target | 2x reorder level | Argument to `sp_auto_replenish` |

## Results

The 10 sample orders produce these totals on a fresh database:

| Customer | Total spent | Tier |
|---|---:|---|
| Alice Smith | 2,050.00 | Gold |
| Grace Mukamana | 1,533.00 | Gold |
| Jean Paul Nkurunziza | 1,237.50 | Gold |
| Charlie Brown | 600.00 | Silver |
| Bob Johnson | 510.00 | Silver |
| Ethan Hunt | 480.00 | Bronze |
| David Ochieng | 418.00 | Bronze |
| Fatima Al-Sayed | 330.00 | Bronze |
| Diana Prince | 129.00 | Bronze |
| Marie Claire Uwase | 60.00 | Bronze |

Test screenshots and exported tables are in [`09_tests/`](09_tests/README.md). Index timings are in [`08_optimization/`](08_optimization/README.md).

## Deliverables

| Deliverable | Files |
|---|---|
| Database schema | `01_schema/`, `ER DIGRAM.png`, `docs/er_diagram.png` |
| Order placement & stock updates | `03_order_processing/`, `04_triggers/01_*`, `04_triggers/02_*` |
| Inventory tracking | `04_triggers/03_trg_log_inventory.sql`, `07_reports/04_inventory_audit_history.sql` |
| Customer categorization | `04_triggers/04_trg_update_customer_tier.sql`, `07_reports/03_customer_tier_report.sql` |
| Views | `06_views/` |
| Replenishment system | `05_replenishment/`, `09_tests/03_test_replenishment.sql` |
| Report summaries | `07_reports/` |
| Performance | `08_optimization/` |
| Tests | `09_tests/` |

## Known issues

A few things don't yet match the design. See [Known issues in docs/design_notes.md](docs/design_notes.md#known-issues) for details and fixes:
- `run_all.sql` points to files that don't exist.
- Order lines can currently be edited.
- One trigger doesn't clear its labels.
- The exported tables come from a database with one extra order.
