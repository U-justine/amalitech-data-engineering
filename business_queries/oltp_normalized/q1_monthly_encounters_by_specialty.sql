-- Q1 (OLTP): Monthly Encounters by Specialty

-- Calculates monthly visits and unique patients by specialty.
-- Tables: encounters, providers, specialties (3 tables, 2 joins).

SET search_path = healthcare_oltp;

WITH encounter_specialty AS (

    -- Hop 1: encounter -> provider 
    -- Joins the visit to the doctor to find out which specialty_id the visit belongs to.
    WITH encounter_provider AS (
        SELECT
            e.encounter_date,
            e.encounter_type,
            e.patient_id,
            p.specialty_id
        FROM encounters e
        JOIN providers p ON p.provider_id = e.provider_id
    )

    -- Hop 2: specialty_id -> specialty name 
    -- Uses the specialty_id from Hop 1 to look up the actual name (e.g., 'Cardiology').
    SELECT
        date_trunc('month', ep.encounter_date)::date AS encounter_month,
        s.specialty_name,
        ep.encounter_type,
        ep.patient_id
    FROM encounter_provider ep
    JOIN specialties s ON s.specialty_id = ep.specialty_id
)
-- Final step: Count encounters and unique patients.
SELECT
    encounter_month,
    specialty_name,
    encounter_type,
    COUNT(*)                   AS total_encounters,
    COUNT(DISTINCT patient_id) AS unique_patients
FROM encounter_specialty
GROUP BY encounter_month, specialty_name, encounter_type
ORDER BY encounter_month, specialty_name, encounter_type;