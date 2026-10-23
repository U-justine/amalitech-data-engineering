# Graphs

Charts drawn in pgAdmin's Graph Visualiser from the report queries, after the 10 sample orders in [`09_tests/01_test_customer_orders.sql`](../09_tests/01_test_customer_orders.sql) were placed.

| Chart | Query that produces it | Shows |
|---|---|---|
| [`Best_selling_Products.png`](Best_selling_Products.png) | [`07_reports/02_low_stock_report.sql`](../07_reports/02_low_stock_report.sql), query 3 | Top 5 products by quantity sold |
| [`Customer Tiers.png`](Customer%20Tiers.png) | [`07_reports/03_customer_tier_report.sql`](../07_reports/03_customer_tier_report.sql), query 2 | Number of customers in each tier: 3 Gold, 2 Silver, 15 Bronze |
| [`low-stock-alerts.png`](low-stock-alerts.png) | [`06_views/02_vw_low_stock.sql`](../06_views/02_vw_low_stock.sql) | Stock against reorder level for the 4 low products |
| [`monthly_revenue.png`](monthly_revenue.png) | [`07_reports/01_order_summary_per_customer.sql`](../07_reports/01_order_summary_per_customer.sql), query 3 | Revenue per month |

The data behind the best-selling chart is exported in [`09_tests/tables/Best_selling_products.csv`](../09_tests/tables/Best_selling_products.csv), and the tier leaderboard in [`09_tests/tables/customer_tier_leaderboard.csv`](../09_tests/tables/customer_tier_leaderboard.csv).

> The sample orders are dated relative to the day they're run, so the month labels in `monthly_revenue.png` will differ if you rebuild the database. The total across all months is always 7,347.50.