# Design Notes

How the system works, how the files connect to each other, and why it is built this way.

![ER diagram](ER%20DIAGRAM.png)

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

## How the files connect

Each folder builds on the ones before it. Tables come first, then the code that writes to them, then the code that reads from them.

```
01_schema            tables, keys, constraints
   │
   ├── 08_optimization/01_indexes      indexes on those tables
   │
   ├── 03_order_processing
   │     fn_bulk_discount ──► used by sp_place_order
   │     sp_place_order   ──► INSERT orders, order_details
   │
   ├── 04_triggers       react to those inserts and updates
   │     order_details ──► trg_deduct_stock        ──► products.stock_qty
   │     order_details ──► trg_update_order_total  ──► orders.total_amount
   │     products      ──► trg_log_inventory       ──► inventory_logs
   │     orders        ──► trg_update_customer_tier ──► customers.total_spent, tier
   │
   ├── 05_replenishment  UPDATE products.stock_qty (logged by trg_log_inventory)
   │
   ├── 06_views          read the tables
   │
   ├── 02_seed_data      products and customers
   │
   ├── 09_tests          call the procedures, check the results
   │
   └── 07_reports        read the tables and views
```

| Folder | Depends on | Used by | Why it sits here |
|---|---|---|---|
| `01_schema` | Nothing | Everything | Every other file reads or writes these tables. Foreign keys and constraints live here, so bad data is blocked no matter which file writes it. |
| `08_optimization/01_indexes.sql` | `01_schema` | Views, reports, procedures | Indexes only need the tables, so they're created straight after them and every later query can use them. |
| `03_order_processing` | `01_schema` | `09_tests` | `fn_bulk_discount` must exist before `sp_place_order`, which calls it. The procedure only inserts rows; it leaves stock and totals to the triggers. |
| `04_triggers` | `01_schema` | Every insert, update and delete | Triggers are what keep stock, totals, tiers and the log correct automatically, so they must be in place before any data arrives. |
| `05_replenishment` | `01_schema`, `04_triggers` | `09_tests` | The procedures label the change as `REPLENISHMENT` and `trg_log_inventory` records it. |
| `06_views` | `01_schema` | `07_reports`, `09_tests` | Views only read data, so they can be created on empty tables. |
| `02_seed_data` | `01_schema`, `04_triggers` | `09_tests`, `07_reports` | Loaded **after** the triggers, so each product's opening stock is logged as `INITIAL`. Without that, the log could never add up to the current stock. |
| `09_tests` | Everything above | — | `01_test_customer_orders.sql` places the sample orders through `sp_place_order`, so the triggers fire and the log is written. The other test files check the results and roll back. |
| `07_reports` | Tables, views, sample orders | — | Reports only read, so they need data to show. |

This dependency order is the reason for the setup order in the main [README](../README.md#setup), and it's the order [`run_all.sql`](../run_all.sql) follows.

## Key decisions

**Totals are recalculated, never added to.** `orders.total_amount` and `customers.total_spent` are always rebuilt from the rows beneath them. A re-run, a cancellation or a deleted line can't leave them wrong, and a customer's spending is never counted twice.

**Each kind of stock change has one owner.** Orders change stock only through `trg_deduct_stock`. Replenishment changes it only through the two replenishment procedures. `sp_place_order` never touches stock itself, so nothing is subtracted twice.

**Every stock change is logged, and labelled with why.** The log trigger sits on `products`, so even a hand-typed `UPDATE` is recorded. Whatever changes stock passes the reason to the log trigger through transaction-local settings (`inventory.change_type`, `inventory.reference_id`, `inventory.note`), then clears them. Anything unlabelled is recorded as `ADJUSTMENT`.

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

**Order lines can't be edited.** A trigger blocks `UPDATE` on `order_details`, because an edit would change the line without updating stock, the order total or the log. To change an order, delete it and place it again.

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

## Possible extensions

- **Suppliers and purchase orders**, so replenishment links to a real purchase order instead of a text note.
- **Partial returns**, meaning returning some items from an order. Today only whole-order cancellation is supported.
- **Partitioning `inventory_logs` by month**, once the table reaches tens of millions of rows.