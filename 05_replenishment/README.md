# 05 · Replenishment

| File | Creates |
|---|---|
| `01_sp_replenish_product.sql` | `sp_replenish_product`: adds stock to one product |
| `02_sp_auto_replenish.sql` | `sp_auto_replenish`: restocks every product below its reorder level |

Every replenishment is logged automatically as `REPLENISHMENT`, with a note. A step-by-step demo is in [`../09_tests/03_test_replenishment.sql`](../09_tests/README.md).

## Usage

```sql
-- 1. What needs restocking?
SELECT * FROM vw_low_stock;

-- 2. A delivery arrives: product id, quantity, note
CALL sp_replenish_product(10, 25, 'PO-1001 delivery from supplier');

-- 3. Restock everything still low, up to 2x its reorder level
CALL sp_auto_replenish();      -- default multiplier 2
CALL sp_auto_replenish(3);     -- or 3x

-- 4. Check the audit trail
SELECT * FROM inventory_logs WHERE change_type = 'REPLENISHMENT' ORDER BY log_id;
```

`sp_auto_replenish` returns `p_restocked`, the number of products it restocked. Both procedures reject a quantity or multiplier that doesn't make sense, and an unknown product.

## Why "2x reorder level"

Filling each product relative to its own reorder level means fast-moving items get more stock than slow ones:

| Product | Reorder level | Auto-replenish fills to |
|---|---:|---:|
| Bookshelf | 10 | 20 |
| HD Webcam | 15 | 30 |
| Coffee Mug | 100 | 200 |
