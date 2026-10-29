-- Q2 (OLTP): Top Diagnosis-Procedure Pairs

-- Purpose: Finds the most common diagnosis + procedure combinations on the same visit.
-- Shows the ICD-10 code, CPT code, and encounter count for the top 10 pairs.

-- Tables: encounter_diagnoses, encounter_procedures, diagnoses, procedures (4 tables).
-- Cause: Joining the two junction tables pairs every diagnosis with every procedure
-- on the same visit, creating a massive "row explosion".

SET search_path = healthcare_oltp;

WITH encounter_pairs AS (
    -- Step 1: Pair every diagnosis with every procedure on the same visit.
    SELECT
        ed.encounter_id,
        ed.diagnosis_id,
        ep.procedure_id
    FROM encounter_diagnoses  ed
    JOIN encounter_procedures ep ON ep.encounter_id = ed.encounter_id
),
pair_counts AS (
    -- Step 2: Count visits per pair (using ID numbers only).
    -- DISTINCT is used so a visit isn't counted twice if it has duplicate codes.
    SELECT
        diagnosis_id,
        procedure_id,
        COUNT(DISTINCT encounter_id) AS encounter_count
    FROM encounter_pairs
    GROUP BY diagnosis_id, procedure_id
)
-- Step 3: Add descriptions and keep the top 10 pairs.
SELECT
    d.icd10_code,
    d.icd10_description,
    pr.cpt_code,
    pr.cpt_description,
    pc.encounter_count
FROM pair_counts pc
JOIN diagnoses  d  ON d.diagnosis_id  = pc.diagnosis_id
JOIN procedures pr ON pr.procedure_id = pc.procedure_id
ORDER BY pc.encounter_count DESC, d.icd10_code, pr.cpt_code
LIMIT 10;