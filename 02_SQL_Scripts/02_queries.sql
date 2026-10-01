SET search_path TO afilearn;

-- Q1: withdrawal/failure rate by module presentation and by demographic group
SELECT code_module, code_presentation,
       COUNT(*) FILTER (WHERE final_result = 'Withdrawn') AS withdrawn,
       COUNT(*) FILTER (WHERE final_result = 'Fail') AS failed,
       COUNT(*) AS total,
       ROUND(100.0 * COUNT(*) FILTER (WHERE final_result IN ('Withdrawn','Fail')) / COUNT(*), 1) AS pct_withdrawn_or_failed
FROM student_info
GROUP BY code_module, code_presentation
ORDER BY pct_withdrawn_or_failed DESC
LIMIT 10;

-- Q1b: same, broken down by disability status
SELECT disability,
       COUNT(*) FILTER (WHERE final_result IN ('Withdrawn','Fail')) AS neg_outcome,
       COUNT(*) AS total,
       ROUND(100.0 * COUNT(*) FILTER (WHERE final_result IN ('Withdrawn','Fail')) / COUNT(*), 1) AS pct
FROM student_info
GROUP BY disability;

-- Q2: early-weeks VLE engagement (first 28 days) vs final result
SELECT si.final_result,
       ROUND(AVG(early.clicks), 1) AS avg_early_clicks
FROM student_info si
JOIN (
    SELECT id_student, code_module, code_presentation, SUM(sum_click) AS clicks
    FROM student_vle
    WHERE date BETWEEN 0 AND 28
    GROUP BY id_student, code_module, code_presentation
) early ON early.id_student = si.id_student
       AND early.code_module = si.code_module
       AND early.code_presentation = si.code_presentation
GROUP BY si.final_result
ORDER BY avg_early_clicks DESC;

-- Q3: score distribution by assessment type, and late submission vs score
SELECT a.assessment_type,
       ROUND(AVG(sa.score), 1) AS avg_score,
       ROUND(STDDEV(sa.score), 1) AS stddev_score,
       COUNT(*) AS n
FROM student_assessment sa
JOIN assessments a ON a.id_assessment = sa.id_assessment
WHERE sa.score IS NOT NULL
GROUP BY a.assessment_type
ORDER BY stddev_score DESC;

SELECT CASE WHEN sa.date_submitted > a.date THEN 'late' ELSE 'on_time' END AS submission_status,
       ROUND(AVG(sa.score), 1) AS avg_score,
       COUNT(*) AS n
FROM student_assessment sa
JOIN assessments a ON a.id_assessment = sa.id_assessment
WHERE sa.score IS NOT NULL AND a.date IS NOT NULL AND sa.date_submitted IS NOT NULL
GROUP BY submission_status;

-- Q4: prior attempts vs withdrawal/failure probability
SELECT num_of_prev_attempts,
       COUNT(*) FILTER (WHERE final_result IN ('Withdrawn','Fail')) AS neg_outcome,
       COUNT(*) AS total,
       ROUND(100.0 * COUNT(*) FILTER (WHERE final_result IN ('Withdrawn','Fail')) / COUNT(*), 1) AS pct
FROM student_info
GROUP BY num_of_prev_attempts
ORDER BY num_of_prev_attempts;

-- Q5: VLE resource usage by activity type, split by pass/fail
SELECT v.activity_type,
       si.final_result,
       SUM(sv.sum_click) AS total_clicks
FROM student_vle sv
JOIN vle v ON v.id_site = sv.id_site
JOIN student_info si ON si.id_student = sv.id_student
    AND si.code_module = sv.code_module AND si.code_presentation = sv.code_presentation
WHERE si.final_result IN ('Pass', 'Fail')
GROUP BY v.activity_type, si.final_result
ORDER BY v.activity_type, si.final_result;
