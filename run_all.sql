-- =====================================================================
-- RUN ALL SCRIPT
-- Builds the whole system in one go: tables, constraints, indexes,
-- functions, triggers, procedures, views, seed data and the 10 sample orders.
--
-- Run it with psql (or pgAdmin's PSQL Tool), connected to the inventory database:
--     psql -U postgres -d inventory -f run_all.sql
--
-- Not for pgAdmin's Query Tool: it doesn't understand \ir.
-- Safe to re-run: every table is dropped and recreated, so you always end
-- up with the same 10 orders.
-- =====================================================================

-- Stop at the first error instead of carrying on
\set ON_ERROR_STOP on

-- 1. Schema
\ir 01_schema/02_products.sql
\ir 01_schema/03_customers.sql
\ir 01_schema/04_orders.sql
\ir 01_schema/05_order_details.sql
\ir 01_schema/06_inventory_logs.sql
\ir 01_schema/07_constraints.sql

-- 2. Optimization
\ir 08_optimization/01_indexes.sql

-- 3. Order Processing Functions
\ir 03_order_processing/02_fn_bulk_discount.sql
\ir 03_order_processing/01_sp_place_order.sql

-- 4. Triggers
\ir 04_triggers/01_trg_deduct_stock.sql
\ir 04_triggers/02_trg_update_order_total.sql
\ir 04_triggers/03_trg_log_inventory.sql
\ir 04_triggers/04_trg_update_customer_tier.sql

-- 5. Replenishment Procedures
\ir 05_replenishment/01_sp_replenish_product.sql
\ir 05_replenishment/02_sp_auto_replenish.sql

-- 6. Views
\ir 06_views/01_vw_order_summary.sql
\ir 06_views/02_vw_low_stock.sql
\ir 06_views/03_vw_customer_spending.sql

-- 7. Seed Data (Load AFTER tables and functions are created)
\ir 02_seed_data/01_products_data.sql
\ir 02_seed_data/02_customers_data.sql

-- 8. Run the Simulation (This places the 10 sample orders)
\ir 09_tests/01_test_customer_orders.sql