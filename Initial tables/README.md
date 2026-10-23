# Initial Tables

Exports of the data straight after loading the seed data, **before any orders were placed**. Compare them with [`../09_tests/tables/`](../09_tests/README.md#06--final-state-exported-tables) to see what the orders changed.

| File | Source | Shows |
|---|---|---|
| `insert_into_products_table.csv` | `products` | All 20 products with price, stock and reorder level |
| `insert_into_customer_table.csv` | `customers` | All 20 customers, every one at 0.00 spent and Bronze |
| `initial_customer_spending.csv` | `vw_customer_spending` | Every customer with 0 orders, before the triggers have done anything |
| `Low_products.csv` | `vw_low_stock` | The 4 products that start below their reorder level |
| `initial_low_stock_table.csv` | `07_reports/02_low_stock_report.sql` (days of stock left) | Every product as "NO RECENT SALES", except the 4 low ones as "REORDER NOW" |

## Products that start low

| Product | Stock | Reorder level | Shortfall | Suggested order |
|---|---:|---:|---:|---:|
| HD Webcam | 12 | 15 | 3 | 18 |
| Bookshelf | 8 | 10 | 2 | 12 |
| Desk Lamp LED | 14 | 15 | 1 | 16 |
| Wireless Presenter | 10 | 12 | 2 | 14 |

They're low on purpose, so the low-stock view and replenishment have something to show from the start.
