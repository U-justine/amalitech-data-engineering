-- Synthetic Test Data Generator

SET search_path = oltp;

-- Set seed to ensure the data is the same every time
SELECT setseed(0.42);

-- Add 9 more specialties
INSERT INTO specialties
SELECT 3 + g, s, upper(left(replace(s, ' ', ''), 4))
FROM unnest(ARRAY['Orthopedics','Neurology','Oncology','Pediatrics','Pulmonology',
                  'Gastroenterology','Nephrology','Endocrinology','Psychiatry'])
     WITH ORDINALITY AS t(s, g);

-- Add 9 more departments
INSERT INTO departments
SELECT 3 + g, s || ' Unit', 1 + (g % 6), 15 + (g * 7) % 40
FROM unnest(ARRAY['Orthopedics','Neurology','Oncology','Pediatrics','Pulmonology',
                  'Gastroenterology','Nephrology','Endocrinology','Psychiatry'])
     WITH ORDINALITY AS t(s, g);

-- Add 600 providers
INSERT INTO providers
SELECT g, 'ProvFirst' || g, 'ProvLast' || g,
       (ARRAY['MD','DO','NP','PA'])[1 + g % 4],
       1 + g % 12,
       1 + g % 12
FROM generate_series(104, 700) AS g;

-- Add 100,000 patients
INSERT INTO patients
SELECT g, 'First' || g, 'Last' || g,
       DATE '1930-01-01' + (random() * 33000)::INT,
       CASE WHEN random() < 0.5 THEN 'M' ELSE 'F' END,
       'MRN' || LPAD(g::TEXT, 6, '0')
FROM generate_series(1004, 101000) AS g;

-- Add 2,000 diagnoses
INSERT INTO diagnoses
SELECT g,
       chr(65 + g % 26) || LPAD((g % 99)::TEXT, 2, '0') || '.' || (g % 10),
       'Diagnosis ' || g
FROM generate_series(3004, 5000) AS g;

-- Add 1,000 procedures
INSERT INTO procedures
SELECT g, (10000 + g * 37)::TEXT, 'Procedure ' || g
FROM generate_series(4004, 5000) AS g;

-- Add 1,000,000 encounters (dates between 2023 and 2025)
INSERT INTO encounters
SELECT encounter_id, patient_id, provider_id, encounter_type, encounter_date,
       encounter_date + CASE encounter_type
                            WHEN 'Outpatient' THEN INTERVAL '1 hour' * (0.5 + random() * 2)
                            WHEN 'ER'         THEN INTERVAL '1 hour' * (2 + random() * 10)
                            ELSE                   INTERVAL '1 day'  * (1 + random() * 9)
                        END AS discharge_date,
       1 + provider_id % 12 AS department_id
FROM (
    SELECT g AS encounter_id,
           1001 + CASE WHEN random() < 0.7 THEN floor(random() * 100000)
                       ELSE floor(random() * 15000) END::INT AS patient_id,
           104 + floor(random() * 597)::INT AS provider_id,
           CASE WHEN r < 0.60 THEN 'Outpatient'
                WHEN r < 0.85 THEN 'ER'
                ELSE 'Inpatient' END AS encounter_type,
           TIMESTAMP '2023-01-01'
             + random() * (TIMESTAMP '2025-12-31' - TIMESTAMP '2023-01-01') AS encounter_date
    FROM (SELECT g, random() AS r FROM generate_series(7005, 1007004) AS g) s
) x;

-- Add ~2.5 million encounter diagnoses (1 to 4 per encounter)
INSERT INTO encounter_diagnoses
SELECT 8006 + row_number() OVER (),
       e.encounter_id,
       3001 + floor(power(random(), 3) * 2000)::INT,
       s
FROM encounters e
CROSS JOIN LATERAL generate_series(1, 1 + floor(random() * 4 + 0 * e.encounter_id)::INT) AS s
WHERE e.encounter_id >= 7005;

-- Add ~2 million encounter procedures (0 to 4 per encounter)
INSERT INTO encounter_procedures
SELECT 9004 + row_number() OVER (),
       e.encounter_id,
       4001 + floor(power(random(), 3) * 1000)::INT,
       e.encounter_date::DATE
FROM encounters e
CROSS JOIN LATERAL generate_series(1, floor(random() * 5 + 0 * e.encounter_id)::INT) AS s
WHERE e.encounter_id >= 7005;

-- Add ~900,000 billing records (90% of encounters have a bill)
INSERT INTO billing
SELECT 14002 + row_number() OVER (),
       encounter_id,
       claim_amount,
       round(claim_amount * (0.6 + random() * 0.3)::NUMERIC, 2),
       discharge_date::DATE + (1 + floor(random() * 20))::INT,
       (ARRAY['Paid','Paid','Paid','Pending','Denied'])[1 + floor(random() * 5)::INT]
FROM (
    SELECT encounter_id, discharge_date,
           round((CASE encounter_type
                      WHEN 'Inpatient' THEN 5000 + random() * 25000
                      WHEN 'ER'        THEN 800  + random() * 4000
                      ELSE                  100  + random() * 600
                  END)::NUMERIC, 2) AS claim_amount
    FROM encounters
    WHERE encounter_id >= 7005
      AND random() < 0.9
) b;

-- Update database statistics for faster queries
ANALYZE;

-- Print row counts to verify the load
SELECT 'patients' AS table_name, COUNT(*) AS row_count FROM patients
UNION ALL SELECT 'providers',            COUNT(*) FROM providers
UNION ALL SELECT 'encounters',           COUNT(*) FROM encounters
UNION ALL SELECT 'encounter_diagnoses',  COUNT(*) FROM encounter_diagnoses
UNION ALL SELECT 'encounter_procedures', COUNT(*) FROM encounter_procedures
UNION ALL SELECT 'billing',              COUNT(*) FROM billing;