# Inventory and Order Management System

A PostgreSQL database for an e-commerce company. It manages products, customers and orders, and keeps stock levels correct automatically. Every inventory change is logged for auditing, customers are grouped into Bronze, Silver and Gold tiers by spending, bulk discounts are applied to large orders, and low stock can be replenished in one call.

![ER diagram](docs/ER%20DIAGRAM.png)

## Features

- **One call places a whole order.** [`sp_place_order`](03_order_processing/01_sp_place_order.sql) takes a list of products and checks stock for every one first. If anything is short, nothing is saved and the error names the product.
- **Automatic calculations.** [Triggers](04_triggers/) deduct stock, calculate each order's total, and update each customer's total spent and tier. Bulk discounts are applied when the order is placed. No totals are typed by hand.
- **Audit trail.** [Every stock change](04_triggers/03_trg_log_inventory.sql) is written to `inventory_logs`, including opening stock, orders, cancellations, replenishments and manual corrections. Each row records the quantity before and after.
- **Cancelling an order** puts its stock back and lowers the customer's spend and tier.
- **Protected data.** [Constraints](01_schema/07_constraints.sql) and triggers block negative stock, duplicate emails and edits to existing order lines.
- **Replenishment.** [Restock one product](05_replenishment/01_sp_replenish_product.sql), or [every product below its reorder level](05_replenishment/02_sp_auto_replenish.sql) at once.
- **Views and reports.** [Views](06_views/) and [reports](07_reports/) cover order summaries, low stock, customer spending and inventory history. Several are built as a CTE inside a CTE.
- **Indexes.** [Each one](08_optimization/01_indexes.sql) comes with [before/after timings](08_optimization/02_explain_plans.sql) measured on 500,000 test rows.
- **Tests.** [14 automated checks](09_tests/) cover order placement, replenishment, data protection and recalculation. Each check prints **PASS** or **FAIL** in pgAdmin's Messages tab. Every test script rolls back its changes afterwards, except `01_test_customer_orders.sql`, which saves the 10 sample orders.

## Requirements

PostgreSQL 14 or later. Developed in pgAdmin on PostgreSQL 18, and also tested on PostgreSQL 16.

## Project structure

```
inventory-order-management/
├── README.md
│
├── 01_schema/              Database, 5 tables, constraints
├── 02_seed_data/           20 products, 20 customers
├── 03_order_processing/    sp_place_order, fn_bulk_discount
├── 04_triggers/            Stock, order totals, inventory log, customer tier
├── 05_replenishment/       Restock one product / all low products
├── 06_views/               Order summary, low stock, customer spending
├── 07_reports/             Order, stock, tier and audit reports
├── 08_optimization/        Indexes, before/after EXPLAIN plans
├── 09_tests/               Sample orders, tests, screenshots, exported results
│   ├── outputs images/
│   └── tables/
├── Initial tables/         Exports of the data before any orders
├── Graphs/                 Charts of the reports, captured in pgAdmin
│
└── docs/
    ├── design_notes.md     How it works, decisions, changes
    └── ER DIAGRAM.png      ER diagram (pgAdmin)
```

Every numbered folder has its own `README.md` explaining its files.

## Setup (pgAdmin)

1. Open the Query Tool on the default **postgres** database and run [`01_schema/01_create_database.sql`](01_schema/01_create_database.sql). This creates the **inventory** database.
2. Refresh **Databases**, then open the Query Tool on **inventory**.
3. Open and run (F5) each file below **in this order**:

| # | File | # | File |
|---|---|---|---|
| 1 | [`01_schema/02_products.sql`](01_schema/02_products.sql) | 11 | [`04_triggers/02_trg_update_order_total.sql`](04_triggers/02_trg_update_order_total.sql) |
| 2 | [`01_schema/03_customers.sql`](01_schema/03_customers.sql) | 12 | [`04_triggers/03_trg_log_inventory.sql`](04_triggers/03_trg_log_inventory.sql) |
| 3 | [`01_schema/04_orders.sql`](01_schema/04_orders.sql) | 13 | [`04_triggers/04_trg_update_customer_tier.sql`](04_triggers/04_trg_update_customer_tier.sql) |
| 4 | [`01_schema/05_order_details.sql`](01_schema/05_order_details.sql) | 14 | [`05_replenishment/01_sp_replenish_product.sql`](05_replenishment/01_sp_replenish_product.sql) |
| 5 | [`01_schema/06_inventory_logs.sql`](01_schema/06_inventory_logs.sql) | 15 | [`05_replenishment/02_sp_auto_replenish.sql`](05_replenishment/02_sp_auto_replenish.sql) |
| 6 | [`01_schema/07_constraints.sql`](01_schema/07_constraints.sql) | 16 | [`06_views/01_vw_order_summary.sql`](06_views/01_vw_order_summary.sql) |
| 7 | [`08_optimization/01_indexes.sql`](08_optimization/01_indexes.sql) | 17 | [`06_views/02_vw_low_stock.sql`](06_views/02_vw_low_stock.sql) |
| 8 | [`03_order_processing/02_fn_bulk_discount.sql`](03_order_processing/02_fn_bulk_discount.sql) | 18 | [`06_views/03_vw_customer_spending.sql`](06_views/03_vw_customer_spending.sql) |
| 9 | [`03_order_processing/01_sp_place_order.sql`](03_order_processing/01_sp_place_order.sql) | 19 | [`02_seed_data/01_products_data.sql`](02_seed_data/01_products_data.sql) |
| 10 | [`04_triggers/01_trg_deduct_stock.sql`](04_triggers/01_trg_deduct_stock.sql) | 20 | [`02_seed_data/02_customers_data.sql`](02_seed_data/02_customers_data.sql) |
| | | 21 | [`09_tests/01_test_customer_orders.sql`](09_tests/01_test_customer_orders.sql) |

After that, run the [tests](#tests), [reports](#reports) and [explain plans](#optimization) in any order. Test results appear in pgAdmin's **Messages** tab.

**Why this order:** the sample orders in `09_tests/01_test_customer_orders.sql` go through `sp_place_order`. The procedure, triggers and views must therefore exist first. Otherwise stock wouldn't be deducted and nothing would be logged.

> Run `09_tests/01_test_customer_orders.sql` only **once**. It saves its orders permanently, so running it again places every order a second time.

## All SQL files and queries

Links ending in `#L…` jump straight to that query's lines.

### Schema

| File | Creates |
|---|---|
| [`01_create_database.sql`](01_schema/01_create_database.sql) | The `inventory` database |
| [`02_products.sql`](01_schema/02_products.sql) | `products`: name, category, `price_usd`, `stock_qty`, `reorder_level` |
| [`03_customers.sql`](01_schema/03_customers.sql) | `customers`: name, email, phone, `total_spent`, `tier` |
| [`04_orders.sql`](01_schema/04_orders.sql) | `orders`: `customer_id` → customers, `order_date`, `total_amount` |
| [`05_order_details.sql`](01_schema/05_order_details.sql) | `order_details`: `order_id` → orders, `product_id` → products, quantity, price, discount, line total |
| [`06_inventory_logs.sql`](01_schema/06_inventory_logs.sql) | `inventory_logs`: one row per stock change, with before/after quantities |
| [`07_constraints.sql`](01_schema/07_constraints.sql) | `CHECK` and `UNIQUE` rules for all five tables |

### Seed data

| File | Loads |
|---|---|
| [`01_products_data.sql`](02_seed_data/01_products_data.sql) | 20 products. 4 start below their reorder level on purpose |
| [`02_customers_data.sql`](02_seed_data/02_customers_data.sql) | 20 customers, all at 0 spent and Bronze |

### Order processing

| File | Creates |
|---|---|
| [`01_sp_place_order.sql`](03_order_processing/01_sp_place_order.sql) | `sp_place_order`: validates, locks products, checks stock, creates the order and its lines |
| [`02_fn_bulk_discount.sql`](03_order_processing/02_fn_bulk_discount.sql) | `fn_bulk_discount`: 10+ units 10%, 50+ units 20% |

### Triggers

| File | Does |
|---|---|
| [`01_trg_deduct_stock.sql`](04_triggers/01_trg_deduct_stock.sql) | Stock down for a new order line, back up for a deleted one; blocks editing order lines |
| [`02_trg_update_order_total.sql`](04_triggers/02_trg_update_order_total.sql) | Recalculates `orders.total_amount` from its lines |
| [`03_trg_log_inventory.sql`](04_triggers/03_trg_log_inventory.sql) | Writes an `inventory_logs` row for every stock change |
| [`04_trg_update_customer_tier.sql`](04_triggers/04_trg_update_customer_tier.sql) | Recalculates `customers.total_spent` and `tier` |

### Replenishment

| File | Creates |
|---|---|
| [`01_sp_replenish_product.sql`](05_replenishment/01_sp_replenish_product.sql) | `sp_replenish_product`: adds stock to one product |
| [`02_sp_auto_replenish.sql`](05_replenishment/02_sp_auto_replenish.sql) | `sp_auto_replenish`: restocks every low product to 2x its reorder level |

### Views

| File | View | One row per |
|---|---|---|
| [`01_vw_order_summary.sql`](06_views/01_vw_order_summary.sql) | `vw_order_summary`: customer name, date, total, number of items, discount | Order |
| [`02_vw_low_stock.sql`](06_views/02_vw_low_stock.sql) | `vw_low_stock`: shortfall, suggested order quantity, status | Low-stock product |
| [`03_vw_customer_spending.sql`](06_views/03_vw_customer_spending.sql) | `vw_customer_spending`: tier, spend, favourite category, rank (CTE inside a CTE) | Customer |

### Reports

¹ Built with a CTE inside a CTE.

**[`01_order_summary_per_customer.sql`](07_reports/01_order_summary_per_customer.sql)**

| # | Query |
|---|---|
| 1 | [Every order, grouped by customer](07_reports/01_order_summary_per_customer.sql#L7-L13) |
| 2 | [One line per customer, ranked by spend](07_reports/01_order_summary_per_customer.sql#L15-L44) ¹ |
| 3 | [Monthly revenue, including months with no sales](07_reports/01_order_summary_per_customer.sql#L46-L72) ¹ |

**[`02_low_stock_report.sql`](07_reports/02_low_stock_report.sql)**

| # | Query |
|---|---|
| 1 | [Products below reorder level](07_reports/02_low_stock_report.sql#L7-L9) |
| 2 | [Early warning: within 25% above reorder level](07_reports/02_low_stock_report.sql#L11-L17) |
| 3 | [Top 5 best-selling products](07_reports/02_low_stock_report.sql#L19-L31) |
| 4 | [Days of stock left at the 90-day sales rate](07_reports/02_low_stock_report.sql#L33-L73) ¹ |

**[`03_customer_tier_report.sql`](07_reports/03_customer_tier_report.sql)**

| # | Query |
|---|---|
| 1 | [Every customer, highest spenders first](07_reports/03_customer_tier_report.sql#L6-L12) |
| 2 | [Tier summary with share of revenue](07_reports/03_customer_tier_report.sql#L14-L23) |
| 3 | [How far each customer is from the next tier](07_reports/03_customer_tier_report.sql#L25-L33) |
| 4 | [Top customer per category](07_reports/03_customer_tier_report.sql#L35-L75) ¹ |
| 5 | [Bulk discounts applied](07_reports/03_customer_tier_report.sql#L77-L90) |

**[`04_inventory_audit_history.sql`](07_reports/04_inventory_audit_history.sql)**

| # | Query |
|---|---|
| 1 | [Filtered history with running stock balance](07_reports/04_inventory_audit_history.sql#L7-L49) ¹ |
| 2 | [Movement summary per product](07_reports/04_inventory_audit_history.sql#L51-L66) |
| 3 | [Reconciliation check (should return no rows)](07_reports/04_inventory_audit_history.sql#L68-L76) |
| 4 | [Everything that happened in one order](07_reports/04_inventory_audit_history.sql#L78-L83) |

### Optimization

| File | Does |
|---|---|
| [`01_indexes.sql`](08_optimization/01_indexes.sql) | 8 indexes, including a partial index for low stock |
| [`02_explain_plans.sql`](08_optimization/02_explain_plans.sql) | Before/after timings on 500,000 temporary rows, then rolls them back |

Sections of [`02_explain_plans.sql`](08_optimization/02_explain_plans.sql):
- [add bulk test data](08_optimization/02_explain_plans.sql#L9-L40)
- [low-stock lookup](08_optimization/02_explain_plans.sql#L42-L51)
- [customer history](08_optimization/02_explain_plans.sql#L53-L66)
- [product audit history](08_optimization/02_explain_plans.sql#L68-L81)
- [revenue by date](08_optimization/02_explain_plans.sql#L83-L94)
- [cleanup](08_optimization/02_explain_plans.sql#L96-L100)

### Tests

| File | Type | What it does |
|---|---|---|
| [`01_test_customer_orders.sql`](09_tests/01_test_customer_orders.sql) | Sample data (saved) | Places the 10 sample orders. Run once |
| [`02_test_place_order.sql`](09_tests/02_test_place_order.sql) | 10 checks | Order placement, validation, discounts, cancellation |
| [`03_test_replenishment.sql`](09_tests/03_test_replenishment.sql) | Demo | Restocking step by step |
| [`04_test_database_protection.sql`](09_tests/04_test_database_protection.sql) | 2 checks | Negative stock and editing order lines are blocked |
| [`05_test_recalculation.sql`](09_tests/05_test_recalculation.sql) | 2 checks | No double counting after re-placing orders |
| [`06_final_database_state.sql`](09_tests/06_final_database_state.sql) | Snapshot | Customers, recent orders, discounts, log, stock |

Sections of [`02_test_place_order.sql`](09_tests/02_test_place_order.sql):
- [valid order](09_tests/02_test_place_order.sql#L9-L22)
- [insufficient stock](09_tests/02_test_place_order.sql#L24-L38)
- [bad data](09_tests/02_test_place_order.sql#L40-L60)
- [discount thresholds](09_tests/02_test_place_order.sql#L62-L66)
- [cancellation](09_tests/02_test_place_order.sql#L68-L80)

Steps of [`03_test_replenishment.sql`](09_tests/03_test_replenishment.sql):
1. [low-stock list](09_tests/03_test_replenishment.sql#L8-L11)
2. [manual delivery](09_tests/03_test_replenishment.sql#L13-L17)
3. [auto-replenish](09_tests/03_test_replenishment.sql#L19-L22)
4. [check list is empty](09_tests/03_test_replenishment.sql#L24-L27)
5. [audit trail](09_tests/03_test_replenishment.sql#L29-L36)
6. [manual adjustment](09_tests/03_test_replenishment.sql#L38-L46)

Queries in [`06_final_database_state.sql`](09_tests/06_final_database_state.sql):
1. [customers](09_tests/06_final_database_state.sql#L5-L9)
2. [recent orders](09_tests/06_final_database_state.sql#L11-L20)
3. [order lines](09_tests/06_final_database_state.sql#L22-L25)
4. [audit log](09_tests/06_final_database_state.sql#L27-L30)
5. [product stock](09_tests/06_final_database_state.sql#L32-L34)

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
| Bulk discount | 10+ units: 10%, 50+ units: 20% (per product line) | [`02_fn_bulk_discount.sql`](03_order_processing/02_fn_bulk_discount.sql) |
| Customer tier | Bronze below 500, Silver from 500, Gold from 1,000 total spent | `fn_customer_tier` in [`04_trg_update_customer_tier.sql`](04_triggers/04_trg_update_customer_tier.sql) |
| Low stock | `stock_qty` below `reorder_level` | [`02_vw_low_stock.sql`](06_views/02_vw_low_stock.sql) |
| Auto-replenish target | 2x reorder level | Argument to [`sp_auto_replenish`](05_replenishment/02_sp_auto_replenish.sql) |

## Results

The 10 sample orders produce these totals:

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

All 20 customers together: 3 Gold, 2 Silver, 15 Bronze.

All 14 tests pass:
- [`02_test_place_order.sql`](09_tests/02_test_place_order.sql): 10 checks
- [`04_test_database_protection.sql`](09_tests/04_test_database_protection.sql): 2 checks
- [`05_test_recalculation.sql`](09_tests/05_test_recalculation.sql): 2 checks

Screenshots and exported tables are in [`09_tests/`](09_tests/README.md), and index timings are in [`08_optimization/`](08_optimization/README.md).

## Deliverables

| Deliverable | Files |
|---|---|
| Database schema | [`01_schema/`](01_schema/), [`docs/ER DIAGRAM.png`](docs/ER%20DIAGRAM.png) |
| Order placement & stock updates | [`01_sp_place_order.sql`](03_order_processing/01_sp_place_order.sql), [`01_trg_deduct_stock.sql`](04_triggers/01_trg_deduct_stock.sql), [`02_trg_update_order_total.sql`](04_triggers/02_trg_update_order_total.sql) |
| Inventory tracking | [`03_trg_log_inventory.sql`](04_triggers/03_trg_log_inventory.sql), [`04_inventory_audit_history.sql`](07_reports/04_inventory_audit_history.sql) |
| Customer categorization | [`04_trg_update_customer_tier.sql`](04_triggers/04_trg_update_customer_tier.sql), [`03_customer_tier_report.sql`](07_reports/03_customer_tier_report.sql) |
| Bulk discounts | [`02_fn_bulk_discount.sql`](03_order_processing/02_fn_bulk_discount.sql), [bulk discount report](07_reports/03_customer_tier_report.sql#L77-L90) |
| Views | [`06_views/`](06_views/) |
| Replenishment system | [`05_replenishment/`](05_replenishment/), [`03_test_replenishment.sql`](09_tests/03_test_replenishment.sql) |
| Report summaries | [`07_reports/`](07_reports/) |
| Performance | [`08_optimization/`](08_optimization/) |
| Tests | [`09_tests/`](09_tests/) |

For how the pieces fit together and why, see [`docs/design_notes.md`](docs/design_notes.md).