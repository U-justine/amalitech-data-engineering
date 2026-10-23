# 06 · Views

A view is a saved query you can use like a table. It always shows live data.

| View | File | One row per | Shows |
|---|---|---|---|
| `vw_order_summary` | `01_vw_order_summary.sql` | Order | Customer name, order date, total, number of products, number of items, discount given |
| `vw_low_stock` | `02_vw_low_stock.sql` | Low-stock product | Stock, reorder level, shortfall, suggested order quantity, status (LOW / CRITICAL / OUT OF STOCK) |
| `vw_customer_spending` | `03_vw_customer_spending.sql` | Customer | Tier, order count, items, total and average spend, amount saved, favourite category, rank, % of revenue |

## Usage

```sql
SELECT * FROM vw_order_summary ORDER BY order_date DESC;
SELECT * FROM vw_low_stock ORDER BY shortfall DESC;
SELECT * FROM vw_customer_spending ORDER BY total_spent DESC;
```

In pgAdmin they appear under **inventory → Schemas → public → Views**. Each file also ends with a `SELECT` that shows the view straight after creating it.

## `vw_customer_spending`: a CTE inside a CTE

```
customer_orders                 (outer CTE)
  ├─ order_lines                (inner CTE: every order line with its category)
  └─ category_spend             (inner CTE: spend per customer per category, ranked)
ranked                          (outer CTE: spend rank and share of revenue)
final SELECT                    (adds customers with no orders)
```

The inner CTEs only exist inside `customer_orders`, which keeps each step self-contained.

## Notes

- **Low stock means strictly below the reorder level** (`<`). A product sitting exactly at its reorder level isn't flagged.
- **The views have no `ORDER BY`** inside them. Sort when you query them, because PostgreSQL doesn't guarantee the order of a view's rows.
