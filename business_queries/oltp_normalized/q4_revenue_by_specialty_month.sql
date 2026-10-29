-- Q4 (OLTP): Revenue by Specialty and Month

-- Calculates the total allowed billing amount per month, per 
-- medical specialty, and also shows the overall top-earning specialties.


-- Tables: billing, encounters, providers, specialties (4 tables, 3 joins).

-- Slow because: The database has to build a hash table of all 1,000,004 
-- encounters just to find each claim's provider. Encounters and providers 
-- add no columns to the result; they are only there to translate keys. 
-- That is the exact problem the Star Schema fixes.

SET search_path = healthcare_oltp;

-- Query 1: Revenue by specialty for each month
WITH claim_specialty AS (
    -- Step 1: Attach the specialty and month to every billing claim.
    SELECT 
        TO_CHAR(b.claim_date, 'YYYY-MM') AS claim_month,
        s.specialty_name,
        b.allowed_amount
    FROM billing b
    JOIN encounters  e ON b.encounter_id = e.encounter_id
    JOIN providers   p ON e.provider_id  = p.provider_id
    JOIN specialties s ON p.specialty_id = s.specialty_id
)
-- Step 2: Sum the revenue and count claims per month/specialty.
SELECT 
    claim_month,
    specialty_name,
    SUM(allowed_amount) AS total_allowed,
    COUNT(*)            AS claim_count
FROM claim_specialty
GROUP BY claim_month, specialty_name
ORDER BY claim_month, total_allowed DESC;


--  Overall Top-Earning Specialties

-- Purpose: Shows which specialty generates the most revenue overall.
-- Uses RANK() to show the order.

-- Query 2: Overall revenue by specialty
SELECT
    s.specialty_name,
    SUM(b.allowed_amount)                             AS total_allowed,
    RANK() OVER (ORDER BY SUM(b.allowed_amount) DESC) AS revenue_rank
FROM billing b
JOIN encounters  e ON b.encounter_id = e.encounter_id
JOIN providers   p ON e.provider_id  = p.provider_id
JOIN specialties s ON p.specialty_id = s.specialty_id
GROUP BY s.specialty_name
ORDER BY total_allowed DESC;