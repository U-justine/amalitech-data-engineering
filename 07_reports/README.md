# 07 · Reports

Ready-made reports. Each file holds several queries, and each query can be run on its own.

| File | Queries |
|---|---|
| `01_order_summary_per_customer.sql` | Every order by customer · one-line summary per customer, ranked by spend ¹ · monthly revenue including months with no sales, with running total and month-on-month change ¹ |
| `02_low_stock_report.sql` | Products below reorder level · early warning (within 25% above reorder level) · top 5 best sellers · days of stock left at the 90-day sales rate, with a suggested action ¹ |
| `03_customer_tier_report.sql` | Customers by spend · tier summary with share of revenue · how far each customer is from the next tier · top customer per category ¹ · bulk discounts applied |
| `04_inventory_audit_history.sql` | Filtered history with running stock balance ¹ · movement summary per product · reconciliation check · everything that happened in one order |

¹ Built with a CTE inside a CTE.

## Filtering the audit history

In `04_inventory_audit_history.sql`, edit the `params` CTE at the top of query 1:

```sql
SELECT 12::INT                          AS product_id,   -- NULL = all products
       CURRENT_DATE - INTERVAL '30 days' AS date_from,
       CURRENT_DATE + INTERVAL '1 day'   AS date_to
```

## Reconciliation check

Query 3 in `04_inventory_audit_history.sql` should return **no rows**. A row there would mean a product's stock doesn't match the sum of its logged changes, which is what an auditor would look for.
