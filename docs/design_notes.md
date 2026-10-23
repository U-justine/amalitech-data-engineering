# Design Notes

How the system works, the decisions behind it, what changed from the first version, and what's still open.

![ER diagram](er_diagram.png)

## Tables

| Table | Holds | Maintained automatically |
|---|---|---|
| `products` | Catalogue, price, current stock, reorder level | `stock_qty` (by orders and replenishment) |
| `customers` | Contact details, spending, tier | `total_spent`, `tier` |
| `orders` | One row per order | `total_amount` |
| `order_details` | One row per product per order, with price, discount and line total | `unit_price`, `discount_pct` and `line_total` are set by `sp_place_order` |
| `inventory_logs` | Every stock change | Whole table (written by a trigger) |

## What happens when an order is placed

```
CALL sp_place_order(customer_id, items)
 ├─ validate customer, items and products
 ├─ lock the products and check stock   (fails with a clear message if short)
 ├─ INSERT orders
 └─ INSERT order_details                (price snapshot + fn_bulk_discount)
      ├─ trg_deduct_stock                → products.stock_qty goes down
      │    └─ trg_log_inventory          → inventory_logs row (ORDER)
      └─ trg_update_order_total          → orders.total_amount recalculated
           └─ trg_update_customer_tier   → customers.total_spent and tier recalculated
```

A `CALL` is a single transaction, so if any step fails, nothing is saved.

Deleting an order runs the same chain in reverse:
- its lines are removed by `ON DELETE CASCADE`
- stock goes back, logged as `ORDER_CANCELLED`
- the customer's spend and tier are recalculated

## Key decisions

**Totals are recalculated, never added to.** `orders.total_amount` and `customers.total_spent` are always rebuilt from the rows beneath them. A re-run, a cancellation or a deleted line can't leave them wrong. This is what fixed the doubling bug in the first version.

**Each kind of stock change has one owner.** Orders change stock only through `trg_deduct_stock`. Replenishment changes it only through the two replenishment procedures. `sp_place_order` never touches stock itself, so nothing is subtracted twice.

**Every stock change is logged, and labelled with why.** The log trigger sits on `products`, so even a hand-typed `UPDATE` is recorded. Whatever changes stock passes the reason to the log trigger through transaction-local settings (`inventory.change_type`, `inventory.reference_id`, `inventory.note`). Anything unlabelled is recorded as `ADJUSTMENT`.

| Cause | `change_type` |
|---|---|
| New product with stock | `INITIAL` |
| Order line added | `ORDER` (with the order id) |
| Order deleted | `ORDER_CANCELLED` (with the order id) |
| `sp_replenish_product`, `sp_auto_replenish` | `REPLENISHMENT` (with a note) |
| Any other `UPDATE` of `stock_qty` | `ADJUSTMENT` |

Opening stock is logged as `INITIAL`, so for every product `SUM(change_qty)` equals its current stock. The audit report checks this.

**Several layers stop overselling:**
- The procedure checks stock and returns a readable error.
- Product rows are locked (`FOR UPDATE`), so two simultaneous orders can't both take the last unit.
- `CHECK (stock_qty >= 0)` blocks negative stock even from direct updates.

**Prices are snapshotted** in `order_details.unit_price`, so later price changes don't alter past orders.

**Low stock means strictly below the reorder level** (`<`), as the brief says. A partial index holds only the low-stock products, so this check stays fast however large the catalogue grows.

**Constraints protect the data however it arrives.** These are set in `01_schema/07_constraints.sql`:
- unique product names and customer emails
- positive prices and quantities
- discounts between 0 and 100
- fixed lists for `tier` and `change_type`
- one line per product per order
- each log row's arithmetic is checked (`new_qty = previous_qty + change_qty`)

**Tests clean up after themselves.** Every file in `09_tests/` except `01_test_customer_orders.sql` runs inside `BEGIN … ROLLBACK`, so testing never changes the data.

## Assumptions

- Prices are in USD.
- A tier is based on lifetime spend, and can go down if orders are cancelled.
- Discounts apply per product line, based on that line's quantity.
- Auto-replenishment fills each product to 2x its reorder level by default. A flat target, such as 100 units for everything, would overstock slow items like the bookshelf (reorder level 10) and barely cover fast ones like the coffee mug (reorder level 100).

## Changes from the first version

| First version | Problem | Now |
|---|---|---|
| `UPDATE customers SET total_spent = total_spent + 2050` after each order | Spending was typed by hand, and re-running doubled it (Alice showed 4,100 instead of 2,050) | Calculated by trigger from the orders |
| `DELETE FROM orders` to reset the simulation | Stock stayed reduced, and the log pointed at deleted orders | Deleting an order restores stock and logs `ORDER_CANCELLED` |
| `place_order(order_id, product_id, qty)`, called once per product | No stock check, and the order had to be created separately | One `CALL` per order, with validation and a clear error |
| `fn_log_restock` logged increases only | Manual decreases left no trace | Every change is logged |
| No opening stock in the log | History couldn't be reconciled with current stock | `INITIAL` rows, plus a reconciliation report |
| `vw_top_category_customer`: two CTEs side by side, grouped by name | Not actually nested, and same-name customers would merge | A true nested CTE in `07_reports/03`, grouped by `customer_id` |
| `vw_low_stock` used `<=` | Flagged products sitting exactly at their reorder level | Uses `<` |
| No `DROP ... IF EXISTS` | Scripts failed on a second run | Table, trigger and function scripts can be re-run |

## Known issues

These were found by building a fresh database from the files in this repository. Some don't show up in a database that was built from earlier versions of the scripts, because older objects are still in it.

### 1. Order lines can be edited

`04_triggers/01_trg_deduct_stock.sql` no longer creates `trg_block_line_update`. Because of that, a statement like `UPDATE order_details SET quantity = 40 WHERE order_detail_id = 1` succeeds. It changes the line without changing stock, the line total, the order total or the log. On a fresh database, `09_tests/04_test_database_protection.sql` Test 2 reports **FAIL**.

**Fix:** add this to the end of `04_triggers/01_trg_deduct_stock.sql`:

```sql
CREATE OR REPLACE FUNCTION fn_trg_block_line_update()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Order lines cannot be edited. Delete the order and place it again.';
END;
$$;

DROP TRIGGER IF EXISTS trg_block_line_update ON order_details;
CREATE TRIGGER trg_block_line_update
BEFORE UPDATE ON order_details
FOR EACH ROW EXECUTE FUNCTION fn_trg_block_line_update();
```

The comment in `04_triggers/02_trg_update_order_total.sql` that says UPDATEs are blocked becomes true once this is in place.

### 2. Stock changes can be mislabelled

`fn_trg_deduct_stock` sets `inventory.change_type` and `inventory.reference_id` but doesn't clear them afterwards. A manual stock correction made later in the same transaction is therefore logged as `ORDER`, with the previous order's id, instead of `ADJUSTMENT`.

**Fix:** in `fn_trg_deduct_stock`, just before `RETURN NULL;`, add:

```sql
    PERFORM set_config('inventory.change_type',  '', true);
    PERFORM set_config('inventory.reference_id', '', true);
```

### 3. One test can pass by mistake

In `09_tests/02_test_place_order.sql`, section 3, `v_msg` isn't reset between the three checks. If one of the calls were wrongly accepted, the previous check's error message would still be in `v_msg`, and the check could still print PASS.

**Fix:** add `v_msg := NULL;` before each of the three `BEGIN CALL ...` lines.

### 4. `run_all.sql` is out of date

It refers to four files that don't exist in this layout:
- `02_seed_data/03_sample_orders.sql`
- `03_order_processing/03_demo_place_order.sql`
- `05_replenishment/03_demo_replenishment.sql`
- `09_tests/test_scenarios.sql`

It also mentions the old database name `inventory_db`, and `01_create_database.sql` has no `\c`. So psql would stop at the first missing file, and the tables would be built in the `postgres` database. Until it's updated, use the pgAdmin order in the README.

**Fix:** point `run_all.sql` at `09_tests/01_test_customer_orders.sql` through `06_final_database_state.sql`. Add `DROP DATABASE IF EXISTS inventory;` before, and `\c inventory` after, `\ir 01_schema/01_create_database.sql`.

### 5. Exported results come from a database with an extra order

The files in `09_tests/tables/` and `09_tests/outputs images/customer_spending.png` show **Alice Smith at 3,250**. On a fresh database she is at **2,050**. The database they were exported from had one extra order for Alice (a laptop, 1,200). That also shifted the order ids, so orders 11 and 12 kept today's date instead of being spread out. This is why `revenue_by_date_pie.png` shows two slices both labelled 2026-10-23.

**Fix:** rebuild the database, run `09_tests/01_test_customer_orders.sql` once, then re-export the tables and charts.

## Possible extensions

- **Suppliers and purchase orders**, so replenishment links to a real purchase order instead of a text note.
- **Partial returns**, meaning returning some items from an order. Today only whole-order cancellation is supported.
- **Partitioning `inventory_logs` by month**, once the table reaches tens of millions of rows.
