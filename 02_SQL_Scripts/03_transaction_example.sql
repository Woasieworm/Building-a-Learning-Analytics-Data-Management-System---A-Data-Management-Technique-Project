SET search_path TO afilearn;

-- Scenario: an exam remarking corrects a student's score for assessment 1752.
-- Before state
SELECT id_assessment, id_student, score FROM student_assessment
WHERE id_assessment = 1752 AND id_student = 11391;

BEGIN;

    -- Step 1: record the correction as an audit-friendly two-step update
    UPDATE student_assessment
    SET score = 82
    WHERE id_assessment = 1752 AND id_student = 11391;

    -- Step 2: verify the update inside the same transaction before committing
    SELECT id_assessment, id_student, score FROM student_assessment
    WHERE id_assessment = 1752 AND id_student = 11391;

COMMIT;

-- After state (persisted)
SELECT id_assessment, id_student, score FROM student_assessment
WHERE id_assessment = 1752 AND id_student = 11391;

-- Demonstrate that the CHECK constraint protects integrity even inside a transaction:
-- attempting an invalid correction (score above 100) must be rejected and rolled back.
BEGIN;
    UPDATE student_assessment
    SET score = 150
    WHERE id_assessment = 1752 AND id_student = 11391;
COMMIT;

-- Confirm the invalid attempt did not persist (score still 82, not 150)
SELECT id_assessment, id_student, score FROM student_assessment
WHERE id_assessment = 1752 AND id_student = 11391;
