# Design Notes

How the system works, the decisions behind it, and what changed from the first version.

![ER diagram](ER%20DIGRAM.png)

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
| Order lines could be edited directly | An edit changed the line without updating stock, the order total or the log | `trg_block_line_update` blocks edits; cancel and re-place instead |

## Possible extensions

- **Suppliers and purchase orders**, so replenishment links to a real purchase order instead of a text note.
- **Partial returns**, meaning returning some items from an order. Today only whole-order cancellation is supported.
- **Partitioning `inventory_logs` by month**, once the table reaches tens of millions of rows.
