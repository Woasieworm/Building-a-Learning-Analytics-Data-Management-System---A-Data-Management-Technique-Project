-- DSCD 606 Semester Project — AfiLearn Learning Analytics Office
-- Phase 4: Relational DBMS, SQL and transaction foundations
-- Schema implements the Phase 3 logical design on PostgreSQL 16

DROP SCHEMA IF EXISTS afilearn CASCADE;
CREATE SCHEMA afilearn;
SET search_path TO afilearn;

-- Reference table: module/presentation structure
CREATE TABLE courses (
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    module_presentation_length INTEGER NOT NULL CHECK (module_presentation_length > 0),
    PRIMARY KEY (code_module, code_presentation)
);

-- Assessment definitions per module presentation
CREATE TABLE assessments (
    id_assessment INTEGER PRIMARY KEY,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    assessment_type VARCHAR(4) NOT NULL CHECK (assessment_type IN ('TMA', 'CMA', 'Exam')),
    date INTEGER,
    weight NUMERIC(5,2) NOT NULL CHECK (weight >= 0 AND weight <= 100),
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);

-- One row per student per module presentation: demographics and outcome
CREATE TABLE student_info (
    id_student INTEGER NOT NULL,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    region VARCHAR(50),
    highest_education VARCHAR(50),
    imd_band VARCHAR(10),
    age_band VARCHAR(10),
    num_of_prev_attempts SMALLINT NOT NULL DEFAULT 0 CHECK (num_of_prev_attempts >= 0),
    studied_credits INTEGER NOT NULL CHECK (studied_credits > 0),
    disability CHAR(1) NOT NULL CHECK (disability IN ('Y', 'N')),
    final_result VARCHAR(11) NOT NULL CHECK (final_result IN ('Pass', 'Withdrawn', 'Fail', 'Distinction')),
    PRIMARY KEY (id_student, code_module, code_presentation),
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);

-- Registration and (optional) withdrawal dates
CREATE TABLE student_registration (
    id_student INTEGER NOT NULL,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    date_registration INTEGER,
    date_unregistration INTEGER,
    PRIMARY KEY (id_student, code_module, code_presentation),
    FOREIGN KEY (id_student, code_module, code_presentation)
        REFERENCES student_info (id_student, code_module, code_presentation)
);

-- Per-student assessment submissions and scores
CREATE TABLE student_assessment (
    id_assessment INTEGER NOT NULL,
    id_student INTEGER NOT NULL,
    date_submitted INTEGER,
    is_banked BOOLEAN NOT NULL DEFAULT FALSE,
    score SMALLINT CHECK (score >= 0 AND score <= 100),
    PRIMARY KEY (id_assessment, id_student),
    FOREIGN KEY (id_assessment) REFERENCES assessments (id_assessment)
);

-- VLE resource catalogue
CREATE TABLE vle (
    id_site INTEGER PRIMARY KEY,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    activity_type VARCHAR(20) NOT NULL,
    week_from SMALLINT,
    week_to SMALLINT,
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);

-- RAW staging table for VLE interactions: no PK, append-only, mirrors the file exactly
-- (see Phase 3 justification — the natural key is not unique in the source data)
CREATE TABLE student_vle_staging (
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    id_student INTEGER NOT NULL,
    id_site INTEGER NOT NULL,
    date INTEGER NOT NULL,
    sum_click INTEGER NOT NULL CHECK (sum_click > 0)
);

-- CLEANED analytics table: deduplicated and aggregated, this is what gets queried
CREATE TABLE student_vle (
    id_student INTEGER NOT NULL,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    id_site INTEGER NOT NULL,
    date INTEGER NOT NULL,
    sum_click INTEGER NOT NULL CHECK (sum_click > 0),
    PRIMARY KEY (id_student, id_site, date),
    FOREIGN KEY (id_student, code_module, code_presentation)
        REFERENCES student_info (id_student, code_module, code_presentation),
    FOREIGN KEY (id_site) REFERENCES vle (id_site)
);

-- Indexes supporting the case-study questions (baseline; tuned further in Phase 5)
CREATE INDEX idx_student_info_final_result ON student_info (final_result);
CREATE INDEX idx_student_info_module_pres ON student_info (code_module, code_presentation);
CREATE INDEX idx_student_vle_student ON student_vle (id_student);
CREATE INDEX idx_student_assessment_student ON student_assessment (id_student);
