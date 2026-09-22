-- =============================================================================
-- SOVEREIGN CHARITY CARE ENGINE: POSTGRESQL SCHEMA
-- Phase 1: Texas Hospital Financial Assistance Policy (FAP) Thresholds
-- =============================================================================
-- This schema implements the immutable data layer for hospital FAP compliance.
-- It enforces the mathematical logic defined in charity_care_engine.py at the
-- database level, ensuring auditability and referential integrity.
-- =============================================================================

-- Enable UUID extension for secure identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- TABLE: hospitals
-- Stores registered hospital entities participating in the sovereign network
-- -----------------------------------------------------------------------------
CREATE TABLE hospitals (
    hospital_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(50) CHECK (facility_type IN ('Acute Care', 'Critical Access', 'Children\'s', 'Psychiatric', 'Rehabilitation')),
    county VARCHAR(100) NOT NULL,
    state_code CHAR(2) DEFAULT 'TX',
    cms_certification_number VARCHAR(10) UNIQUE,
    is_nonprofit BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast county-based queries (regional analysis)
CREATE INDEX idx_hospitals_county ON hospitals(county);
CREATE INDEX idx_hospitals_state ON hospitals(state_code);

-- -----------------------------------------------------------------------------
-- TABLE: hospital_fap_thresholds
-- Core table: Defines the sliding scale discounts and MOOP caps per hospital
-- Mirrors the HOSPITAL_FAP_THRESHOLDS dictionary in Python engine
-- -----------------------------------------------------------------------------
CREATE TABLE hospital_fap_thresholds (
    threshold_id SERIAL PRIMARY KEY,
    hospital_id UUID NOT NULL REFERENCES hospitals(hospital_id) ON DELETE CASCADE,
    tier_name VARCHAR(50) NOT NULL,
    max_fpl_percent NUMERIC(5,2) NOT NULL CHECK (max_fpl_percent > 0),
    discount_percentage NUMERIC(5,2) NOT NULL CHECK (discount_percentage BETWEEN 0 AND 100),
    moop_cap NUMERIC(12,2) NOT NULL CHECK (moop_cap >= 0),
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiration_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique tier per hospital within active date range
    UNIQUE (hospital_id, tier_name, effective_date)
);

-- Index for fast eligibility lookups
CREATE INDEX idx_fap_hospital_active ON hospital_fap_thresholds(hospital_id, is_active) WHERE is_active = TRUE;
CREATE INDEX idx_fap_max_fpl ON hospital_fap_thresholds(max_fpl_percent);

-- -----------------------------------------------------------------------------
-- TABLE: patient_applications
-- Records individual charity care applications processed through the engine
-- -----------------------------------------------------------------------------
CREATE TABLE patient_applications (
    application_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospitals(hospital_id),
    patient_household_size INTEGER NOT NULL CHECK (patient_household_size > 0),
    patient_annual_income NUMERIC(12,2) NOT NULL CHECK (patient_annual_income >= 0),
    total_medical_bill NUMERIC(12,2) NOT NULL CHECK (total_medical_bill > 0),
    calculated_fpl_percent NUMERIC(5,2) NOT NULL,
    assigned_tier VARCHAR(50),
    discount_applied NUMERIC(5,2),
    moop_cap_enforced NUMERIC(12,2),
    final_patient_liability NUMERIC(12,2) NOT NULL,
    total_savings NUMERIC(12,2) NOT NULL,
    application_status VARCHAR(30) CHECK (application_status IN ('PENDING', 'APPROVED', 'DENIED', 'APPEAL')),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewer_notes TEXT
);

-- Index for status tracking and hospital reporting
CREATE INDEX idx_applications_hospital ON patient_applications(hospital_id);
CREATE INDEX idx_applications_status ON patient_applications(application_status);
CREATE INDEX idx_applications_submitted ON patient_applications(submitted_at);

-- -----------------------------------------------------------------------------
-- TABLE: audit_log
-- Immutable ledger of all state transitions (complements SHA3 blockchain)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'APPLICATION', 'THRESHOLD', 'HOSPITAL'
    entity_id UUID NOT NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('INSERT', 'UPDATE', 'DELETE', 'VERIFY')),
    old_values JSONB,
    new_values JSONB,
    sha3_hash VARCHAR(64), -- Stores SHA3-256 hash of the state transition
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for audit trail reconstruction
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_timestamp ON audit_log(changed_at);

-- -----------------------------------------------------------------------------
-- VIEW: current_fap_policies
-- Simplified view for real-time eligibility queries
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW current_fap_policies AS
SELECT 
    h.hospital_id,
    h.hospital_name,
    h.county,
    ft.tier_name,
    ft.max_fpl_percent,
    ft.discount_percentage,
    ft.moop_cap,
    ft.effective_date
FROM hospitals h
JOIN hospital_fap_thresholds ft ON h.hospital_id = ft.hospital_id
WHERE ft.is_active = TRUE 
  AND (ft.expiration_date IS NULL OR ft.expiration_date >= CURRENT_DATE)
ORDER BY h.hospital_name, ft.max_fpl_percent;

-- -----------------------------------------------------------------------------
-- TRIGGER FUNCTION: Log changes to audit_log with SHA3 placeholder
-- In production, this would call a PL/Python or external service for SHA3
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION log_fap_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (entity_type, entity_id, action_type, old_values, new_values, changed_by)
        VALUES ('THRESHOLD', NEW.hospital_id, 'INSERT', NULL, to_jsonb(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (entity_type, entity_id, action_type, old_values, new_values, changed_by)
        VALUES ('THRESHOLD', NEW.hospital_id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (entity_type, entity_id, action_type, old_values, new_values, changed_by)
        VALUES ('THRESHOLD', OLD.hospital_id, 'DELETE', to_jsonb(OLD), NULL, current_user);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to fap_thresholds table
CREATE TRIGGER trg_fap_audit
AFTER INSERT OR UPDATE OR DELETE ON hospital_fap_thresholds
FOR EACH ROW EXECUTE FUNCTION log_fap_changes();

-- -----------------------------------------------------------------------------
-- SEED DATA: Example Texas Hospital FAP Policies
-- Mirrors the Python HOSPITAL_FAP_THRESHOLDS constants
-- -----------------------------------------------------------------------------
INSERT INTO hospitals (hospital_id, hospital_name, facility_type, county, cms_certification_number, is_nonprofit)
VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Texas Memorial Hospital', 'Acute Care', 'Harris County', '450001', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'Austin Community Health', 'Critical Access', 'Travis County', '450002', TRUE),
    ('00000000-0000-0000-0000-000000000003', 'Dallas Regional Medical Center', 'Acute Care', 'Dallas County', '450003', FALSE);

-- Insert Standard FAP Tiers (Same across network for consistency)
INSERT INTO hospital_fap_thresholds (hospital_id, tier_name, max_fpl_percent, discount_percentage, moop_cap)
SELECT 
    h.hospital_id,
    tiers.tier_name,
    tiers.max_fpl_percent,
    tiers.discount_percentage,
    tiers.moop_cap
FROM hospitals h
CROSS JOIN (
    VALUES 
        ('Tier_1_Full_Charity', 200.00, 100.00, 0.00),
        ('Tier_2_Partial_Charity', 300.00, 80.00, 500.00),
        ('Tier_3_Sliding_Scale', 400.00, 50.00, 2500.00),
        ('Tier_4_Standard', 600.00, 20.00, 5000.00)
) AS tiers(tier_name, max_fpl_percent, discount_percentage, moop_cap);

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERY: Test the View
-- -----------------------------------------------------------------------------
-- SELECT * FROM current_fap_policies WHERE hospital_name LIKE '%Memorial%';
