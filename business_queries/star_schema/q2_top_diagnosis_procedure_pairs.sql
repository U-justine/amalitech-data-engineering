-- =====================================================================
-- Q2 (Star Schema): Top Diagnosis-Procedure Pairs
-- =====================================================================
-- Purpose: Same result as q2_top_diagnosis_procedure_pairs, but faster.
-- Trick: a pair can never be more frequent than its rarer code. We first
-- find a minimum count needed to reach the top 10, then skip every code
-- that is too rare to get there. The answer is still exact.

SET search_path = healthcare_analysis_data_warehouse;

WITH dx_freq AS (
    -- How many visits each diagnosis appears on
    SELECT diagnosis_key, COUNT(*) AS n
    FROM bridge_encounter_diagnoses
    GROUP BY diagnosis_key
),
px_freq AS (
    -- How many visits each procedure appears on
    SELECT procedure_key, COUNT(*) AS n
    FROM bridge_encounter_procedures
    GROUP BY procedure_key
),
threshold AS (
    -- Quick estimate: the 10th best pair among the 20 most common
    -- diagnoses x 20 most common procedures. The real top 10 must be
    -- at least this high.
    SELECT COALESCE(MIN(c), 0) AS t
    FROM (
        SELECT COUNT(*) AS c
        FROM bridge_encounter_diagnoses  bd
        JOIN bridge_encounter_procedures bp ON bp.encounter_key = bd.encounter_key
        WHERE bd.diagnosis_key IN (SELECT diagnosis_key FROM dx_freq ORDER BY n DESC LIMIT 20)
          AND bp.procedure_key IN (SELECT procedure_key FROM px_freq ORDER BY n DESC LIMIT 20)
        GROUP BY bd.diagnosis_key, bp.procedure_key
        ORDER BY c DESC
        LIMIT 10
    ) seed
),
pair_counts AS (
    -- Exact count, but only for codes common enough to reach the top 10
    SELECT bd.diagnosis_key, bp.procedure_key, COUNT(*) AS encounter_count
    FROM bridge_encounter_diagnoses  bd
    JOIN bridge_encounter_procedures bp ON bp.encounter_key = bd.encounter_key
    WHERE bd.diagnosis_key IN (SELECT diagnosis_key FROM dx_freq
                               WHERE n >= (SELECT t FROM threshold))
      AND bp.procedure_key IN (SELECT procedure_key FROM px_freq
                               WHERE n >= (SELECT t FROM threshold))
    GROUP BY bd.diagnosis_key, bp.procedure_key
),
top_pairs AS (
    SELECT diagnosis_key, procedure_key, encounter_count
    FROM pair_counts
    ORDER BY encounter_count DESC, diagnosis_key, procedure_key
    LIMIT 10
)
SELECT dx.icd10_code, dx.icd10_description,
       px.cpt_code,   px.cpt_description,
       tp.encounter_count
FROM top_pairs tp
JOIN dim_diagnosis dx ON dx.diagnosis_key = tp.diagnosis_key
JOIN dim_procedure px ON px.procedure_key = tp.procedure_key
ORDER BY tp.encounter_count DESC, dx.icd10_code, px.cpt_code;