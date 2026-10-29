-- ETL Script: Moves data from OLTP (source) to Star Schema (warehouse)

-- Full reload: run 04_create_star_schema.sql first (it drops and recreates the empty
-- warehouse tables), then run this script.

SET search_path = healthcare_analysis_data_warehouse, healthcare_oltp;

-- Start transaction. If anything fails, nothing gets saved.
BEGIN;

-- 1. Load Date Dimension (2015 to 2035)
-- Generates a row for every single day in this range.
INSERT INTO dim_date (
    date_key, calendar_date, year, quarter, quarter_label, month, month_name, 
    year_month, month_start_date, week_of_year, day_of_month, day_of_week, 
    day_name, is_weekend, fiscal_year, fiscal_quarter
)
SELECT 
    to_char(d,'YYYYMMDD')::int, 
    d, 
    EXTRACT(year FROM d)::smallint, 
    EXTRACT(quarter FROM d)::smallint,
    to_char(d,'YYYY') || '-Q' || EXTRACT(quarter FROM d),
    EXTRACT(month FROM d)::smallint, 
    trim(to_char(d,'Month')), 
    to_char(d,'YYYY-MM'),
    date_trunc('month', d)::date, 
    EXTRACT(week FROM d)::smallint, 
    EXTRACT(day FROM d)::smallint,
    EXTRACT(isodow FROM d)::smallint, 
    trim(to_char(d,'Day')), 
    EXTRACT(isodow FROM d) IN (6,7),
    EXTRACT(year FROM d + INTERVAL '3 months')::smallint,
    EXTRACT(quarter FROM d + INTERVAL '3 months')::smallint
FROM generate_series(DATE '2015-01-01', DATE '2035-12-31', INTERVAL '1 day') AS g(d)
ON CONFLICT (date_key) DO NOTHING;

-- 2. Load small reference dimensions
-- Copies specialties, departments, visit types, diagnoses, and procedures.
INSERT INTO dim_specialty (specialty_id, specialty_name, specialty_code)
SELECT specialty_id, specialty_name, specialty_code FROM healthcare_oltp.specialties
ON CONFLICT (specialty_id) DO UPDATE SET 
    specialty_name = EXCLUDED.specialty_name, specialty_code = EXCLUDED.specialty_code;

INSERT INTO dim_department (department_id, department_name, floor, capacity)
SELECT department_id, department_name, floor, capacity FROM healthcare_oltp.departments
ON CONFLICT (department_id) DO UPDATE SET 
    department_name = EXCLUDED.department_name, floor = EXCLUDED.floor, capacity = EXCLUDED.capacity;

INSERT INTO dim_encounter_type (encounter_type_key, encounter_type_name, care_setting, is_inpatient) VALUES
  (1,'Outpatient','Ambulatory',FALSE), (2,'Inpatient','Acute',TRUE), (3,'ER','Emergency',FALSE)
ON CONFLICT DO NOTHING;

INSERT INTO dim_diagnosis (diagnosis_id, icd10_code, icd10_description, icd10_chapter)
SELECT diagnosis_id, icd10_code, icd10_description, left(icd10_code,1) FROM healthcare_oltp.diagnoses
ON CONFLICT (diagnosis_id) DO UPDATE SET 
    icd10_code = EXCLUDED.icd10_code, icd10_description = EXCLUDED.icd10_description;

INSERT INTO dim_procedure (procedure_id, cpt_code, cpt_description)
SELECT procedure_id, cpt_code, cpt_description FROM healthcare_oltp.procedures
ON CONFLICT (procedure_id) DO UPDATE SET 
    cpt_code = EXCLUDED.cpt_code, cpt_description = EXCLUDED.cpt_description;

-- 3. Load Patient Dimension
-- Copies patient info, cleans up names (initcap), and calculates age group.
INSERT INTO dim_patient (patient_id, mrn, first_name, last_name, full_name, gender, date_of_birth, age_group, row_hash)
SELECT p.patient_id, p.mrn,
       initcap(trim(p.first_name)), initcap(trim(p.last_name)),
       initcap(trim(p.first_name)) || ' ' || initcap(trim(p.last_name)),
       CASE WHEN upper(p.gender) IN ('M','F') THEN upper(p.gender) ELSE 'U' END,
       p.date_of_birth,
       CASE WHEN p.date_of_birth IS NULL THEN 'Unknown'
            WHEN age(current_date, p.date_of_birth) < INTERVAL '18 years' THEN '0-17'
            WHEN age(current_date, p.date_of_birth) < INTERVAL '40 years' THEN '18-39'
            WHEN age(current_date, p.date_of_birth) < INTERVAL '65 years' THEN '40-64'
            WHEN age(current_date, p.date_of_birth) < INTERVAL '80 years' THEN '65-79'
            ELSE '80+' END,
       md5(concat_ws('|', p.mrn, p.first_name, p.last_name, p.gender, p.date_of_birth))
FROM healthcare_oltp.patients p
ON CONFLICT (patient_id) DO UPDATE SET 
    mrn = EXCLUDED.mrn, first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name,
    full_name = EXCLUDED.full_name, gender = EXCLUDED.gender, date_of_birth = EXCLUDED.date_of_birth,
    age_group = EXCLUDED.age_group, row_hash = EXCLUDED.row_hash, updated_at = now()
WHERE dim_patient.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

-- 4. Load Provider Dimension (SCD Type 2)
-- Tracks doctor history. Cleans up names and links to their specialty.
INSERT INTO dim_provider (provider_id, first_name, last_name, full_name, credential, specialty_key, specialty_name, department_key, department_name, row_hash, effective_from)
SELECT pr.provider_id, 
       initcap(trim(pr.first_name)), 
       initcap(trim(pr.last_name)), 
       initcap(trim(pr.first_name)) || ' ' || initcap(trim(pr.last_name)), 
       pr.credential,
       COALESCE(s.specialty_key, -1), COALESCE(s.specialty_name, 'Unknown'),
       COALESCE(d.department_key, -1), COALESCE(d.department_name, 'Unknown'),
       md5(concat_ws('|', pr.first_name, pr.last_name, pr.credential, pr.specialty_id, pr.department_id)),
       DATE '1900-01-01'
FROM healthcare_oltp.providers pr
LEFT JOIN dim_specialty  s ON s.specialty_id  = pr.specialty_id
LEFT JOIN dim_department d ON d.department_id = pr.department_id;

-- 5. Create Staging Tables
-- Calculates the hard math (counts, sums) ONCE here to save query time later.

-- Count diagnoses per visit
CREATE TEMP TABLE stg_dx_counts ON COMMIT DROP AS
SELECT encounter_id, COUNT(DISTINCT diagnosis_id) AS diagnosis_count,
       MIN(diagnosis_id) FILTER (WHERE diagnosis_sequence = 1) AS primary_diagnosis_id
FROM healthcare_oltp.encounter_diagnoses GROUP BY encounter_id;

-- Count procedures per visit
CREATE TEMP TABLE stg_px_counts ON COMMIT DROP AS
SELECT encounter_id, COUNT(*) AS procedure_count
FROM healthcare_oltp.encounter_procedures GROUP BY encounter_id;

-- Sum billing amounts per visit
CREATE TEMP TABLE stg_billing ON COMMIT DROP AS
SELECT encounter_id, COUNT(*) AS claim_count, 
       MIN(claim_date) AS first_claim_date, 
       SUM(claim_amount) AS total_claim_amount, SUM(allowed_amount) AS total_allowed_amount
FROM healthcare_oltp.billing GROUP BY encounter_id;

-- Create a fast temporary table of encounters for readmission math
CREATE TEMP TABLE stg_enc ON COMMIT DROP AS
SELECT encounter_id, patient_id, encounter_date, discharge_date, encounter_type
FROM healthcare_oltp.encounters;
CREATE INDEX ON stg_enc (patient_id, encounter_date);
ANALYZE stg_enc;

-- Calculate readmissions: did the patient come back as an INPATIENT within 30 days?
CREATE TEMP TABLE stg_readmit ON COMMIT DROP AS
SELECT i.encounter_id,
       (nx.next_start::date - i.discharge_date::date) AS days_to_next_admission,
       (nx.next_start IS NOT NULL AND nx.next_start <= i.discharge_date + INTERVAL '30 days') AS is_readmitted_30d
FROM stg_enc i
CROSS JOIN LATERAL (
    SELECT MIN(r.encounter_date) AS next_start
    FROM   stg_enc r
    WHERE  r.patient_id = i.patient_id 
      AND  r.encounter_type = 'Inpatient'   -- Must be a new inpatient stay
      AND  r.encounter_date > i.discharge_date 
      AND  r.encounter_id <> i.encounter_id
) nx
WHERE i.encounter_type = 'Inpatient' AND i.discharge_date IS NOT NULL;

-- 6. Load Fact Table
-- Grabs the keys from dimensions and pulls in all the pre-calculated math.
INSERT INTO fact_encounters (
    encounter_id, encounter_date_key, discharge_date_key, claim_date_key, patient_key, provider_key,
    specialty_key, department_key, encounter_type_key, primary_diagnosis_key,
    encounter_ts, discharge_ts, patient_age_at_encounter, length_of_stay_hours, length_of_stay_days,
    diagnosis_count, procedure_count, claim_count, total_claim_amount, total_allowed_amount,
    is_index_inpatient_stay, is_readmitted_30d, days_to_next_admission
)
SELECT e.encounter_id, 
       COALESCE(to_char(e.encounter_date,'YYYYMMDD')::int, -1),
       COALESCE(to_char(e.discharge_date,'YYYYMMDD')::int, -1),
       COALESCE(to_char(b.first_claim_date,'YYYYMMDD')::int, -1),
       COALESCE(dp.patient_key, -1),
       COALESCE(pv.provider_key, -1),
       COALESCE(pv.specialty_key, -1),
       COALESCE(dd.department_key, pv.department_key, -1),
       COALESCE(et.encounter_type_key, -1),
       COALESCE(dg.diagnosis_key, -1),
       e.encounter_date, e.discharge_date,
       date_part('year', age(e.encounter_date::date, p.date_of_birth))::smallint,
       CASE WHEN e.discharge_date >= e.encounter_date THEN round(EXTRACT(epoch FROM e.discharge_date - e.encounter_date)/3600.0, 2) END,
       CASE WHEN e.discharge_date >= e.encounter_date THEN e.discharge_date::date - e.encounter_date::date END,
       COALESCE(dx.diagnosis_count, 0), COALESCE(px.procedure_count, 0),
       COALESCE(b.claim_count, 0), COALESCE(b.total_claim_amount, 0), COALESCE(b.total_allowed_amount, 0),
       (rd.encounter_id IS NOT NULL),
       COALESCE(rd.is_readmitted_30d, FALSE),
       rd.days_to_next_admission
FROM healthcare_oltp.encounters e
LEFT JOIN healthcare_oltp.patients p ON p.patient_id = e.patient_id
LEFT JOIN dim_patient dp ON dp.patient_id = e.patient_id
LEFT JOIN dim_provider pv ON pv.provider_id = e.provider_id
                         AND e.encounter_date::date >= pv.effective_from
                         AND e.encounter_date::date < pv.effective_to
LEFT JOIN dim_department dd ON dd.department_id = e.department_id
LEFT JOIN dim_encounter_type et ON et.encounter_type_name = e.encounter_type
LEFT JOIN stg_dx_counts dx ON dx.encounter_id = e.encounter_id
LEFT JOIN dim_diagnosis dg ON dg.diagnosis_id = dx.primary_diagnosis_id
LEFT JOIN stg_px_counts px ON px.encounter_id = e.encounter_id
LEFT JOIN stg_billing b ON b.encounter_id = e.encounter_id
LEFT JOIN stg_readmit rd ON rd.encounter_id = e.encounter_id;

-- 7. Load Bridge Tables
-- Connects the visits to their specific diagnoses and procedures.
INSERT INTO bridge_encounter_diagnoses (encounter_key, diagnosis_key, diagnosis_sequence, is_primary)
SELECT f.encounter_key, COALESCE(dg.diagnosis_key, -1),
       MIN(ed.diagnosis_sequence), MIN(ed.diagnosis_sequence) = 1
FROM healthcare_oltp.encounter_diagnoses ed
JOIN fact_encounters f ON f.encounter_id = ed.encounter_id
LEFT JOIN dim_diagnosis dg ON dg.diagnosis_id = ed.diagnosis_id
GROUP BY f.encounter_key, COALESCE(dg.diagnosis_key, -1);

INSERT INTO bridge_encounter_procedures (encounter_key, procedure_key, first_procedure_date_key, quantity)
SELECT f.encounter_key, COALESCE(dp.procedure_key, -1),
       COALESCE(to_char(MIN(ep.procedure_date),'YYYYMMDD')::int, -1), COUNT(*)
FROM healthcare_oltp.encounter_procedures ep
JOIN fact_encounters f ON f.encounter_id = ep.encounter_id
LEFT JOIN dim_procedure dp ON dp.procedure_id = ep.procedure_id
GROUP BY f.encounter_key, COALESCE(dp.procedure_key, -1);

-- 8. Load Aggregation Table
-- Pre-calculates the top diagnosis/procedure pairs for Question 2.
INSERT INTO agg_dx_px_pair (diagnosis_key, procedure_key, encounter_count, first_date_key, last_date_key)
SELECT bd.diagnosis_key, bp.procedure_key, COUNT(*), MIN(f.encounter_date_key), MAX(f.encounter_date_key)
FROM bridge_encounter_diagnoses bd
JOIN bridge_encounter_procedures bp ON bp.encounter_key = bd.encounter_key
JOIN fact_encounters f ON f.encounter_key = bd.encounter_key
GROUP BY bd.diagnosis_key, bp.procedure_key;

-- Save all the data to the database
COMMIT;

-- Update database statistics so queries run fast
ANALYZE fact_encounters;
ANALYZE bridge_encounter_diagnoses;
ANALYZE bridge_encounter_procedures;
ANALYZE agg_dx_px_pair;

-- 9. Verification Checks
-- Makes sure the data in the warehouse matches the source.
SELECT 'fact rows = oltp encounters' AS check, 
       (SELECT COUNT(*) FROM fact_encounters) = (SELECT COUNT(*) FROM healthcare_oltp.encounters) AS ok
UNION ALL
SELECT 'allowed $ reconciles', 
       (SELECT SUM(total_allowed_amount) FROM fact_encounters) = (SELECT SUM(allowed_amount) FROM healthcare_oltp.billing)
UNION ALL
SELECT 'no unknown specialty keys', 
       NOT EXISTS (SELECT 1 FROM fact_encounters WHERE specialty_key = -1);