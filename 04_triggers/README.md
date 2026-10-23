# 04 · Triggers

These triggers keep stock, totals, the audit log and customer tiers correct without any manual updates.

| File | Trigger | Fires on | Does |
|---|---|---|---|
| `01_trg_deduct_stock.sql` | `trg_deduct_stock` | Insert / delete on `order_details` | Stock goes down for a new line, back up for a deleted line |
| `02_trg_update_order_total.sql` | `trg_update_order_total` | Insert / delete on `order_details` | Recalculates `orders.total_amount` from its lines |
| `03_trg_log_inventory.sql` | `trg_log_inventory` | Insert on `products`, or update of `stock_qty` | Writes an `inventory_logs` row for every stock change |
| `04_trg_update_customer_tier.sql` | `trg_update_customer_tier` | Update of total / delete on `orders` | Recalculates `customers.total_spent` and `tier` |

`04_trg_update_customer_tier.sql` also creates two helper functions:
- `fn_customer_tier(amount)`: Bronze below 500, Silver from 500, Gold from 1,000
- `fn_refresh_customer(id)`: recalculates one customer's total spent and tier

## How they chain together

```
INSERT order_details
 ├─ trg_deduct_stock        → UPDATE products.stock_qty
 │    └─ trg_log_inventory  → INSERT inventory_logs
 └─ trg_update_order_total  → UPDATE orders.total_amount
      └─ trg_update_customer_tier → UPDATE customers.total_spent, tier
```

## How the log knows why stock changed

Before changing stock, the code that makes the change sets a transaction-local label, and the log trigger reads it. The replenishment procedures clear their label afterwards; `trg_deduct_stock` currently doesn't (see Known issues below).

| Label set by | `change_type` logged |
|---|---|
| New product with stock | `INITIAL` |
| `trg_deduct_stock` on a new line | `ORDER` (with the order id) |
| `trg_deduct_stock` on a deleted line | `ORDER_CANCELLED` (with the order id) |
| `05_replenishment` procedures | `REPLENISHMENT` (with a note) |
| Nothing (a direct `UPDATE`) | `ADJUSTMENT` |

To add a note to a manual correction:

```sql
BEGIN;
SELECT set_config('inventory.note', 'Stock count: 2 damaged', true);
UPDATE products SET stock_qty = stock_qty - 2 WHERE product_id = 7;
COMMIT;
```

## Changing an order

To change an order, delete it (stock goes back automatically) and place it again. Don't `UPDATE` an order line: it would change the line without changing stock, the order total or the log.

## Known issues

- **Edits aren't blocked yet.** The trigger that blocks editing order lines (`trg_block_line_update`) isn't in `01_trg_deduct_stock.sql` at the moment, so an `UPDATE` on `order_details` is allowed.
- **Labels aren't cleared.** `trg_deduct_stock` doesn't clear its "why" labels after changing stock. A manual correction later in the same transaction is therefore logged as part of the order.

The fixes for both are in [`../docs/design_notes.md`](../docs/design_notes.md#known-issues).
