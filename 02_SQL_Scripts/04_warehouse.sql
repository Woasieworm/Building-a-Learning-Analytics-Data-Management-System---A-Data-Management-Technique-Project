-- Phase 7: Warehousing, dimensional modelling and analytics workloads
-- Star schema: one fact table at the grain (student x module presentation),
-- three dimensions: student, course/module presentation, and VLE activity type.

DROP SCHEMA IF EXISTS warehouse CASCADE;
CREATE SCHEMA warehouse;
SET search_path TO warehouse, afilearn;

CREATE TABLE warehouse.dim_student (
    student_key SERIAL PRIMARY KEY,
    id_student INTEGER NOT NULL,
    gender CHAR(1),
    region VARCHAR(50),
    highest_education VARCHAR(50),
    imd_band VARCHAR(10),
    age_band VARCHAR(10),
    disability CHAR(1),
    UNIQUE (id_student)
);

CREATE TABLE warehouse.dim_course (
    course_key SERIAL PRIMARY KEY,
    code_module VARCHAR(3) NOT NULL,
    code_presentation VARCHAR(5) NOT NULL,
    module_presentation_length INTEGER,
    UNIQUE (code_module, code_presentation)
);

CREATE TABLE warehouse.dim_vle_activity (
    activity_key SERIAL PRIMARY KEY,
    activity_type VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE warehouse.fact_student_presentation (
    fact_key SERIAL PRIMARY KEY,
    student_key INTEGER NOT NULL REFERENCES warehouse.dim_student (student_key),
    course_key INTEGER NOT NULL REFERENCES warehouse.dim_course (course_key),
    num_prev_attempts SMALLINT,
    studied_credits INTEGER,
    total_clicks BIGINT NOT NULL DEFAULT 0,
    num_assessments_submitted INTEGER NOT NULL DEFAULT 0,
    avg_score NUMERIC(5,2),
    final_result VARCHAR(11) NOT NULL,
    withdrawn_flag BOOLEAN NOT NULL,
    distinction_flag BOOLEAN NOT NULL,
    UNIQUE (student_key, course_key)
);

-- A secondary fact table at finer grain for VLE activity-level analysis
CREATE TABLE warehouse.fact_vle_engagement (
    fact_key SERIAL PRIMARY KEY,
    student_key INTEGER NOT NULL REFERENCES warehouse.dim_student (student_key),
    course_key INTEGER NOT NULL REFERENCES warehouse.dim_course (course_key),
    activity_key INTEGER NOT NULL REFERENCES warehouse.dim_vle_activity (activity_key),
    total_clicks BIGINT NOT NULL
);

-- Populate dimensions from the cleaned relational core.
-- Note: some students have differing demographic values across presentations
-- (e.g. region or highest_education changed between enrolments), so a naive
-- DISTINCT produces duplicate id_student keys. dim_student is built as a
-- Slowly Changing Dimension Type 1 snapshot, keeping only the most recent
-- presentation's attributes per student (code_presentation sorts correctly
-- as text since it is year + B/J, e.g. 2013B < 2013J < 2014B < 2014J).
INSERT INTO warehouse.dim_student (id_student, gender, region, highest_education, imd_band, age_band, disability)
SELECT DISTINCT ON (id_student) id_student, gender, region, highest_education, imd_band, age_band, disability
FROM afilearn.student_info
ORDER BY id_student, code_presentation DESC;

INSERT INTO warehouse.dim_course (code_module, code_presentation, module_presentation_length)
SELECT code_module, code_presentation, module_presentation_length FROM afilearn.courses;

INSERT INTO warehouse.dim_vle_activity (activity_type)
SELECT DISTINCT activity_type FROM afilearn.vle;

-- Populate the main fact table (grain: student x module presentation)
INSERT INTO warehouse.fact_student_presentation
    (student_key, course_key, num_prev_attempts, studied_credits, total_clicks,
     num_assessments_submitted, avg_score, final_result, withdrawn_flag, distinction_flag)
SELECT
    ds.student_key,
    dc.course_key,
    si.num_of_prev_attempts,
    si.studied_credits,
    COALESCE(clicks.total_clicks, 0),
    COALESCE(assess.n_submitted, 0),
    assess.avg_score,
    si.final_result,
    si.final_result = 'Withdrawn',
    si.final_result = 'Distinction'
FROM afilearn.student_info si
JOIN warehouse.dim_student ds ON ds.id_student = si.id_student
JOIN warehouse.dim_course dc ON dc.code_module = si.code_module AND dc.code_presentation = si.code_presentation
LEFT JOIN (
    SELECT id_student, code_module, code_presentation, SUM(sum_click) AS total_clicks
    FROM afilearn.student_vle
    GROUP BY id_student, code_module, code_presentation
) clicks ON clicks.id_student = si.id_student AND clicks.code_module = si.code_module
        AND clicks.code_presentation = si.code_presentation
LEFT JOIN (
    SELECT sa.id_student, a.code_module, a.code_presentation,
           COUNT(*) AS n_submitted, AVG(sa.score) AS avg_score
    FROM afilearn.student_assessment sa
    JOIN afilearn.assessments a ON a.id_assessment = sa.id_assessment
    GROUP BY sa.id_student, a.code_module, a.code_presentation
) assess ON assess.id_student = si.id_student AND assess.code_module = si.code_module
        AND assess.code_presentation = si.code_presentation;

-- Populate the secondary fact table (grain: student x module presentation x activity type)
INSERT INTO warehouse.fact_vle_engagement (student_key, course_key, activity_key, total_clicks)
SELECT ds.student_key, dc.course_key, da.activity_key, SUM(sv.sum_click)
FROM afilearn.student_vle sv
JOIN afilearn.vle v ON v.id_site = sv.id_site
JOIN warehouse.dim_student ds ON ds.id_student = sv.id_student
JOIN warehouse.dim_course dc ON dc.code_module = sv.code_module AND dc.code_presentation = sv.code_presentation
JOIN warehouse.dim_vle_activity da ON da.activity_type = v.activity_type
GROUP BY ds.student_key, dc.course_key, da.activity_key;

CREATE INDEX idx_fact_sp_course ON warehouse.fact_student_presentation (course_key);
CREATE INDEX idx_fact_sp_result ON warehouse.fact_student_presentation (final_result);
CREATE INDEX idx_fact_vle_activity ON warehouse.fact_vle_engagement (activity_key);
