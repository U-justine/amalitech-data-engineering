-- Normalized (3NF) OLTP schema for Healthcare Analytics

DROP SCHEMA IF EXISTS oltp CASCADE;
CREATE SCHEMA oltp;
SET search_path = oltp;

-- Table for patient demographics
CREATE TABLE patients (
    patient_id    INT PRIMARY KEY,
    first_name    VARCHAR(100),
    last_name     VARCHAR(100),
    date_of_birth DATE,
    gender        CHAR(1),
    mrn           VARCHAR(20) UNIQUE
);

-- Table for medical specialties
CREATE TABLE specialties (
    specialty_id   INT PRIMARY KEY,
    specialty_name VARCHAR(100),
    specialty_code VARCHAR(10)
);

-- Table for hospital departments
CREATE TABLE departments (
    department_id   INT PRIMARY KEY,
    department_name VARCHAR(100),
    floor           INT,
    capacity        INT
);

-- Table for doctors and nurses
CREATE TABLE providers (
    provider_id   INT PRIMARY KEY,
    first_name    VARCHAR(100),
    last_name     VARCHAR(100),
    credential    VARCHAR(20),
    specialty_id  INT REFERENCES specialties(specialty_id),
    department_id INT REFERENCES departments(department_id)
);

-- Table for patient visits
CREATE TABLE encounters (
    encounter_id   INT PRIMARY KEY,
    patient_id     INT REFERENCES patients(patient_id),
    provider_id    INT REFERENCES providers(provider_id),
    encounter_type VARCHAR(50),          -- 'Outpatient', 'Inpatient', 'ER'
    encounter_date TIMESTAMP,
    discharge_date TIMESTAMP,
    department_id  INT REFERENCES departments(department_id)
);

-- Index to speed up searching visits by date
CREATE INDEX idx_encounter_date ON encounters(encounter_date);

-- Table for illness codes
CREATE TABLE diagnoses (
    diagnosis_id      INT PRIMARY KEY,
    icd10_code        VARCHAR(10),
    icd10_description VARCHAR(200)
);

-- Table linking visits to multiple illnesses
CREATE TABLE encounter_diagnoses (
    encounter_diagnosis_id INT PRIMARY KEY,
    encounter_id           INT REFERENCES encounters(encounter_id),
    diagnosis_id           INT REFERENCES diagnoses(diagnosis_id),
    diagnosis_sequence     INT
);

-- Table for medical procedures
CREATE TABLE procedures (
    procedure_id    INT PRIMARY KEY,
    cpt_code        VARCHAR(10),
    cpt_description VARCHAR(200)
);

-- Table linking visits to multiple procedures
CREATE TABLE encounter_procedures (
    encounter_procedure_id INT PRIMARY KEY,
    encounter_id           INT REFERENCES encounters(encounter_id),
    procedure_id           INT REFERENCES procedures(procedure_id),
    procedure_date         DATE
);

-- Table for medical billing and claims
CREATE TABLE billing (
    billing_id     INT PRIMARY KEY,
    encounter_id   INT REFERENCES encounters(encounter_id),
    claim_amount   DECIMAL(12,2),
    allowed_amount DECIMAL(12,2),
    claim_date     DATE,
    claim_status   VARCHAR(50)
);

-- Index to speed up searching claims by date
CREATE INDEX idx_claim_date ON billing(claim_date);

-- ==========================================
-- FOREIGN KEY INDEXES
-- (PostgreSQL does not create these automatically)
-- ==========================================

-- Index to speed up provider lookups
CREATE INDEX idx_providers_specialty    ON providers (specialty_id);
CREATE INDEX idx_providers_department   ON providers (department_id);

-- Index to speed up encounter lookups
CREATE INDEX idx_encounters_patient     ON encounters (patient_id);
CREATE INDEX idx_encounters_provider    ON encounters (provider_id);
CREATE INDEX idx_encounters_department  ON encounters (department_id);

-- Index to speed up diagnosis lookups
CREATE INDEX idx_enc_dx_encounter       ON encounter_diagnoses (encounter_id);
CREATE INDEX idx_enc_dx_diagnosis       ON encounter_diagnoses (diagnosis_id);

-- Index to speed up procedure lookups
CREATE INDEX idx_enc_px_encounter       ON encounter_procedures (encounter_id);
CREATE INDEX idx_enc_px_procedure       ON encounter_procedures (procedure_id);

-- Index to speed up billing lookups
CREATE INDEX idx_billing_encounter      ON billing (encounter_id);