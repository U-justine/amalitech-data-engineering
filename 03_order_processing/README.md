# 03 · Order Processing

| File | Creates |
|---|---|
| `01_sp_place_order.sql` | `sp_place_order` procedure, plus the `fn_parse_order_items` helper |
| `02_fn_bulk_discount.sql` | `fn_bulk_discount(quantity)`, which returns the discount % |

Run `02` before `01`, because the procedure uses the discount function.

## Placing an order

```sql
CALL sp_place_order(1, '[{"product_id": 1, "quantity": 1},
                         {"product_id": 5, "quantity": 2}]');
```

The first argument is the customer id. The second is a JSON list of products and quantities. A product listed twice is merged into one line.

`sp_place_order` does the following:

1. Checks that the customer exists, that the list isn't empty, and that every quantity is above 0.
2. Checks that every product exists.
3. Locks those products and checks there's enough stock for every line.
4. Creates the order and one line per product. Each line gets the current price, `fn_bulk_discount` and the line total.

The triggers in `04_triggers` then deduct stock, write the log, and update the order total and the customer's tier.

If any check fails, the order is rejected with a clear message and **nothing is saved**, for example:

```
ERROR:  Insufficient stock for "Bookshelf": requested 999, available 8
```

## Bulk discount

| Quantity of one product | Discount |
|---|---|
| 1 – 9 | 0% |
| 10 – 49 | 10% |
| 50 or more | 20% |

```sql
SELECT fn_bulk_discount(12);   -- 10.00
```
