-- Q3 (Star Schema): 30-Day Readmission Rate by Specialty

-- Purpose: Finds which specialty has the highest 30-day readmission rate.

-- Tables: fact_encounters, dim_specialty (1 join).

-- Fast because: The self-join was done ONCE in the ETL and saved as flags:
-- is_index_inpatient_stay and is_readmitted_30d.
-- This query just counts the flags using a partial index.

SET search_path = healthcare_analysis_data_warehouse;

WITH by_specialty AS (
    -- Step 1: Count stays and readmissions per specialty.
    SELECT
        f.specialty_key,
        COUNT(*)                                    AS inpatient_discharges,
        COUNT(*) FILTER (WHERE f.is_readmitted_30d) AS readmissions_30d
    FROM fact_encounters f
    WHERE f.is_index_inpatient_stay
    GROUP BY f.specialty_key
)
-- Step 2: Add specialty names and calculate the rate.
SELECT
    s.specialty_name,
    b.inpatient_discharges,
    b.readmissions_30d,
    ROUND(100.0 * b.readmissions_30d / b.inpatient_discharges, 2) AS readmission_rate_pct
FROM by_specialty b
JOIN dim_specialty s ON s.specialty_key = b.specialty_key
ORDER BY readmission_rate_pct DESC, s.specialty_name;