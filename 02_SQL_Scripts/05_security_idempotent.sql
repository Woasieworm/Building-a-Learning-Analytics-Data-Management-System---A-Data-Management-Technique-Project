-- Phase 12: Privacy, security, access control (idempotent version)
-- Safe to run any number of times, in any order relative to schema rebuilds.
-- Creates the roles only if they don't already exist; the view and grants
-- are naturally idempotent (CREATE OR REPLACE, and re-granting is harmless).
--
-- SETUP: before running, replace CHANGE_ME_ANALYST_PASSWORD and
-- CHANGE_ME_DPO_PASSWORD below with real passwords (or generate them,
-- e.g. `openssl rand -base64 24`). Do not commit real values.

SET search_path TO afilearn, warehouse;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'afilearn_analyst') THEN
        CREATE ROLE afilearn_analyst LOGIN PASSWORD 'CHANGE_ME_ANALYST_PASSWORD';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'afilearn_dpo') THEN
        CREATE ROLE afilearn_dpo LOGIN PASSWORD 'CHANGE_ME_DPO_PASSWORD';
    END IF;
END
$$;

-- Masked view: safe to recreate every time, always reflects the current student_info
CREATE OR REPLACE VIEW afilearn.student_info_analyst_view AS
SELECT id_student, code_module, code_presentation, gender, region, highest_education,
       CASE WHEN age_band = '0-35' THEN 'under_35' ELSE '35_and_over' END AS age_bucket,
       num_of_prev_attempts, studied_credits, final_result
FROM afilearn.student_info;

-- Grants: re-running these is always safe, Postgres just confirms the same privilege
GRANT USAGE ON SCHEMA afilearn TO afilearn_analyst;
GRANT USAGE ON SCHEMA warehouse TO afilearn_analyst;
GRANT SELECT ON afilearn.student_info_analyst_view TO afilearn_analyst;
GRANT SELECT ON afilearn.courses, afilearn.assessments, afilearn.student_assessment,
                afilearn.vle, afilearn.student_vle TO afilearn_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA warehouse TO afilearn_analyst;
REVOKE ALL ON afilearn.student_info FROM afilearn_analyst;

GRANT USAGE ON SCHEMA afilearn TO afilearn_dpo;
GRANT SELECT ON ALL TABLES IN SCHEMA afilearn TO afilearn_dpo;
