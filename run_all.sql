-- =====================================================================
-- run_all.sql
-- Builds the whole system from scratch, then runs the demos, reports,
-- performance checks and tests.
--
-- From inside the inventory-order-management folder:
--     psql -U postgres -f run_all.sql
--
-- (pgAdmin can't run this file because it uses psql's \ir command.
--  See README.md for the pgAdmin order.)
--
-- Scripts run in DEPENDENCY order, which is not always folder order:
-- the sample orders (02_seed_data) need the procedure and triggers to
-- exist first, so they run after 03 - 06.
-- WARNING: drops and recreates the inventory_db database.
-- =====================================================================

\set ON_ERROR_STOP on
\pset footer off

-- 1. Database and tables
\ir 01_schema/01_create_database.sql
\ir 01_schema/02_products.sql
\ir 01_schema/03_customers.sql
\ir 01_schema/04_orders.sql
\ir 01_schema/05_order_details.sql
\ir 01_schema/06_inventory_logs.sql
\ir 01_schema/07_constraints.sql

-- 2. Indexes
\ir 08_optimization/01_indexes.sql

-- 3. Functions, procedures and triggers
\ir 03_order_processing/02_fn_bulk_discount.sql
\ir 03_order_processing/01_sp_place_order.sql
\ir 04_triggers/01_trg_deduct_stock.sql
\ir 04_triggers/02_trg_update_order_total.sql
\ir 04_triggers/03_trg_log_inventory.sql
\ir 04_triggers/04_trg_update_customer_tier.sql
\ir 05_replenishment/01_sp_replenish_product.sql
\ir 05_replenishment/02_sp_auto_replenish.sql

-- 4. Views
\ir 06_views/01_vw_order_summary.sql
\ir 06_views/02_vw_low_stock.sql
\ir 06_views/03_vw_customer_spending.sql

-- 5. Sample data (orders go through sp_place_order)
\ir 02_seed_data/01_products_data.sql
\ir 02_seed_data/02_customers_data.sql
\ir 02_seed_data/03_sample_orders.sql

-- 6. Demonstrations
\ir 03_order_processing/03_demo_place_order.sql
\ir 05_replenishment/03_demo_replenishment.sql

-- 7. Reports
\ir 07_reports/01_order_summary_per_customer.sql
\ir 07_reports/02_low_stock_report.sql
\ir 07_reports/03_customer_tier_report.sql
\ir 07_reports/04_inventory_audit_history.sql

-- 8. Performance (bulk data is rolled back)
\ir 08_optimization/02_explain_plans.sql

-- 9. Tests (every row should say PASS; changes are rolled back)
\ir 09_tests/test_scenarios.sql
