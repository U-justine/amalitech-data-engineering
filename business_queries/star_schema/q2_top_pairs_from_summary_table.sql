-- Q2 (Star Schema, summary table): Top Diagnosis-Procedure Pairs

-- =====================================================================
-- Q2 (Star Schema, fastest): Top Diagnosis-Procedure Pairs
--                            from the summary table agg_dx_px_pair
-- =====================================================================
-- Purpose: Same question and same result as q2_top_diagnosis_procedure_pairs,
-- but read from the pre-calculated summary table.
--
-- Tables: agg_dx_px_pair, dim_diagnosis, dim_procedure.
-- Fast because: the ETL already joined the two bridge tables and counted
-- every pair ONCE (last step of the ETL). The index on encounter_count DESC
-- lets PostgreSQL read the top 10 rows straight from the index.
-- Trade-off: the table is only as fresh as the last ETL run.

SET search_path = healthcare_analysis_data_warehouse;

SELECT
    dx.icd10_code,
    dx.icd10_description,
    px.cpt_code,
    px.cpt_description,
    a.encounter_count
FROM agg_dx_px_pair a
JOIN dim_diagnosis dx ON dx.diagnosis_key = a.diagnosis_key
JOIN dim_procedure px ON px.procedure_key = a.procedure_key
ORDER BY a.encounter_count DESC, dx.icd10_code, px.cpt_code
LIMIT 10;