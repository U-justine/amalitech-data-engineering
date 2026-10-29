-- Q1 (Star Schema): Monthly Encounters by Specialty

-- Purpose: Calculates monthly visits and unique patients by specialty.
-- Same result as the OLTP version, but much faster.

-- Tables: fact_encounters, dim_date, dim_specialty, dim_encounter_type.
-- Fast because: specialty_key is on the fact table (no provider hop). 
-- Also, we group by patient first to avoid the slow COUNT(DISTINCT).

SET search_path = healthcare_analysis_data_warehouse;

WITH patient_month AS (
    -- Step 1: Group by patient first to get one row per patient per visit type.
    -- date_key / 100 turns 20240510 into 202405 (month).
    SELECT
        f.encounter_date_key / 100 AS yyyymm,
        f.specialty_key,
        f.encounter_type_key,
        f.patient_key,
        COUNT(*)                   AS encounters
    FROM fact_encounters f
    GROUP BY 1, 2, 3, 4
),
monthly_counts AS (
    -- Step 2: Roll up to month/specialty/type. 
    -- Because Step 1 gave us one row per patient, COUNT(*) is now the unique patient count.
    SELECT
        yyyymm,
        specialty_key,
        encounter_type_key,
        SUM(encounters) AS total_encounters,
        COUNT(*)        AS unique_patients
    FROM patient_month
    GROUP BY yyyymm, specialty_key, encounter_type_key
),
months AS (
    -- Step 3: Map YYYYMM to an actual date (e.g. 202405 -> 2024-05-01).
    SELECT DISTINCT
        date_key / 100 AS yyyymm,
        month_start_date
    FROM dim_date
    WHERE date_key <> -1
)
-- Step 4: Add readable names and sort.
SELECT
    m.month_start_date    AS encounter_month,
    s.specialty_name,
    t.encounter_type_name AS encounter_type,
    c.total_encounters,
    c.unique_patients
FROM monthly_counts c
JOIN months             m ON m.yyyymm             = c.yyyymm
JOIN dim_specialty      s ON s.specialty_key      = c.specialty_key
JOIN dim_encounter_type t ON t.encounter_type_key = c.encounter_type_key
ORDER BY encounter_month, s.specialty_name, encounter_type;