-- Q3 (OLTP): 30-Day Readmission Rate by Specialty

-- The purpose is Finds which specialty has the highest readmission rate.
-- A readmission means a patient had an Inpatient stay, was discharged,
-- and came back for ANOTHER Inpatient stay within 30 days.

-- Tables: encounters (self-join), providers, specialties (3 joins).
-- Slow because: Every single stay must be compared against all other 
-- visits for that patient (a self-join on a massive table).

SET search_path = healthcare_oltp;

WITH index_stays AS (
    -- Step 1: Find every completed inpatient stay and its specialty.
    SELECT
        e.encounter_id,
        e.patient_id,
        e.discharge_date,
        s.specialty_name
    FROM encounters e
    JOIN providers   p ON p.provider_id  = e.provider_id
    JOIN specialties s ON s.specialty_id = p.specialty_id
    WHERE e.encounter_type = 'Inpatient'
      AND e.discharge_date IS NOT NULL        -- skip patients still admitted
)
-- Step 2: Self-join encounters to find the patient's next inpatient visit.
-- LEFT JOIN keeps stays that had no readmission so they stay in the denominator.
SELECT
    i.specialty_name,
    COUNT(DISTINCT i.encounter_id)                       AS inpatient_discharges,
    -- DISTINCT means a patient readmitted twice still only counts once
    COUNT(DISTINCT i.encounter_id)
        FILTER (WHERE r.encounter_id IS NOT NULL)        AS readmissions_30d,
    ROUND(100.0 * COUNT(DISTINCT i.encounter_id)
                      FILTER (WHERE r.encounter_id IS NOT NULL)
                / COUNT(DISTINCT i.encounter_id), 2)     AS readmission_rate_pct
FROM index_stays i
LEFT JOIN encounters r
       ON r.patient_id      = i.patient_id                          
      AND r.encounter_type  = 'Inpatient'                           
      AND r.encounter_id   <> i.encounter_id                        
      AND r.encounter_date  > i.discharge_date                      
      AND r.encounter_date <= i.discharge_date + INTERVAL '30 days' 
GROUP BY i.specialty_name
ORDER BY readmission_rate_pct DESC, i.specialty_name;