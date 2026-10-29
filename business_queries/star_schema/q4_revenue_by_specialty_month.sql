-- Q4 (Star Schema): Revenue by Specialty and Month

-- Purpose: Calculates the total allowed billing amount per month, per
-- medical specialty, and also shows the overall top-earning specialties.

-- Tables: fact_encounters, dim_date, dim_specialty (3 tables, 2 joins).

-- Fast because: billing was already summed per visit by the ETL
-- (total_allowed_amount, claim_count, claim_date_key), and specialty_key
-- is stored on the fact. The billing -> encounters -> providers -> specialties chain (3 joins over ~2M rows) is gone.

SET search_path = healthcare_analysis_data_warehouse;

-- Query 1: Revenue by specialty for each month
SELECT 
    d.year_month                     AS claim_month,
    s.specialty_name,
    SUM(f.total_allowed_amount)      AS total_allowed,
    SUM(f.claim_count)               AS claim_count
FROM fact_encounters f
JOIN dim_date d      ON f.claim_date_key = d.date_key
JOIN dim_specialty s ON f.specialty_key  = s.specialty_key
WHERE f.claim_date_key <> -1         -- skip visits that were never billed
GROUP BY d.year_month, s.specialty_name
ORDER BY claim_month, total_allowed DESC;

-- Query 2: Overall revenue by specialty (to find the highest earner)
SELECT
    s.specialty_name,
    SUM(f.total_allowed_amount)                             AS total_allowed,
    RANK() OVER (ORDER BY SUM(f.total_allowed_amount) DESC) AS revenue_rank
FROM fact_encounters f
JOIN dim_specialty s ON f.specialty_key = s.specialty_key
GROUP BY s.specialty_name
ORDER BY total_allowed DESC;