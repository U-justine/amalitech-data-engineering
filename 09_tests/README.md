# 09 · Tests

Sample orders, automated checks, a replenishment demo and a final snapshot. Results appear in pgAdmin's **Messages** tab as `NOTICE: Test n (...): PASS`.

| File | Type | Saves changes? | What it does |
|---|---|---|---|
| `01_test_customer_orders.sql` | Sample data | **Yes** | Places the 10 sample orders through `sp_place_order` and spreads them 12 days apart. Run **once** |
| `02_test_place_order.sql` | 10 checks | No (rolled back) | Order placement, validation, discounts, cancellation |
| `03_test_replenishment.sql` | Demo | No (rolled back) | Restocks step by step and shows the log |
| `04_test_database_protection.sql` | 2 checks | No (rolled back) | Negative stock and editing order lines |
| `05_test_recalculation.sql` | 2 checks | No (rolled back) | No double counting after deleting and re-placing orders |
| `06_final_database_state.sql` | Snapshot | No | Customers, recent orders, discounts, log, stock |

## Run order

Run `01` first, once, after everything in folders 01–06 has been created. After that, run `02`–`06` in any order, as often as you like.

## Results

### 01 · Sample orders

![Sample orders](outputs%20images/test_orders.png)

| # | Customer | Order | Expected total |
|---:|---|---|---:|
| 1 | Alice Smith | Laptop, 2 monitors, office chair | 2,050.00 |
| 2 | Bob Johnson | 20 mice (10% off), speaker | 510.00 |
| 3 | Charlie Brown | Standing desk, SSD | 600.00 |
| 4 | Diana Prince | 2 mugs, backpack, sleeve, presenter | 129.00 |
| 5 | Ethan Hunt | 50 mugs (20% off) | 480.00 |
| 6 | Fatima Al-Sayed | Headphones, webcam | 330.00 |
| 7 | Jean Paul Nkurunziza | 15 keyboards (10% off), 2 USB hubs | 1,237.50 |
| 8 | Marie Claire Uwase | Desk lamp, 2 phone stands | 60.00 |
| 9 | David Ochieng | 12 chargers (10% off), footrest | 418.00 |
| 10 | Grace Mukamana | Laptop, 10 mice (10% off), 10 mugs (10% off) | 1,533.00 |

### 02 · Order placement and validation: 10 / 10 PASS

| # | Check |
|---|---|
| 1 | Placing an order deducts stock |
| 2 | The order writes one matching inventory log row |
| 3 | The order total is calculated (2 × 85 = 170) |
| 4 | The customer's total spent and tier update |
| 5 | An order with too little stock is rejected and nothing is saved |
| 6 | An unknown customer is rejected |
| 7 | An empty order is rejected |
| 8 | A zero quantity is rejected |
| 9 | Bulk discount thresholds (9 units 0%, 10 units 10%, 50 units 20%) |
| 10 | Cancelling an order restores stock and customer spend |

### 03 · Replenishment demo

![Replenishment demo](outputs%20images/replenishment_test_results.png)

The demo runs these steps, then rolls everything back:
1. Lists low-stock products.
2. Delivers 25 bookshelves.
3. Auto-replenishes the 3 other low products to 2x their reorder level.
4. Confirms the low-stock list is empty.
5. Shows the `REPLENISHMENT` log rows.
6. Writes off 2 damaged webcams, which are logged as `ADJUSTMENT`.

### 04 · Database protection: 2 / 2 PASS

![Database protection results](outputs%20images/database_protection_test_results.png)

| # | Check |
|---|---|
| 1 | Setting stock below zero is blocked by a `CHECK` constraint |
| 2 | Editing an existing order line is blocked by a trigger |

### 05 · Recalculation: 2 / 2 PASS

![Recalculation results](outputs%20images/recalculation_test_results.png)

| # | Check |
|---|---|
| 1 | Deleting all orders resets every customer to 0 spent, Bronze |
| 2 | Re-placing Alice's order gives 2,050, not double |

This guards against the bug from the first version, where re-running the simulation doubled every customer's total.

### 06 · Final state: exported tables

Exported from pgAdmin into [`tables/`](tables/):

| File | Contents |
|---|---|
| `Customer_orders.csv` | Total spent and tier for customers 1–10 |
| `customer_tier_leaderboard.csv` | The same, sorted by spend |
| `recent_orders.csv` | The 5 most recent orders |
| `orders_discounts.csv` | The 5 most recent order lines, with discounts |
| `inventory_audit_log.csv` | The 10 most recent log rows |
| `current_product_stock.csv` | Stock for all 20 products |

![Customer spending](outputs%20images/customer_spending.png)

![Revenue by date](outputs%20images/revenue_by_date_pie.png)

Customer tiers after the sample orders:

| Customer | Total spent | Tier |
|---|---:|---|
| Alice Smith | 2,050.00 | Gold |
| Grace Mukamana | 1,533.00 | Gold |
| Jean Paul Nkurunziza | 1,237.50 | Gold |
| Charlie Brown | 600.00 | Silver |
| Bob Johnson | 510.00 | Silver |
| Ethan Hunt | 480.00 | Bronze |
| David Ochieng | 418.00 | Bronze |
| Fatima Al-Sayed | 330.00 | Bronze |
| Diana Prince | 129.00 | Bronze |
| Marie Claire Uwase | 60.00 | Bronze |

## Note on IDs

Rolled-back tests still use up a few ID numbers. The next real order may therefore skip a few IDs. That's normal in PostgreSQL and harmless, because IDs are never reused.
