"""
DSCD 606 Semester Project — AfiLearn Learning Analytics Office
Phase 6: ETL/ELT pipeline

Extract:   read the seven raw OULAD CSV files exactly as delivered
Transform: cast every column to its correct type, convert the '?' missing-value
           marker to true NULL, and resolve the studentVle grain issue found in
           Phase 1 by deduplicating and summing sum_click per (student, site, date)
Load:      write the raw extract to a staging table (append-only, no constraints)
           and the transformed result to the cleaned, constrained table

Run with: python3 pipeline.py
"""

import duckdb
import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, "open+university+learning+analytics+dataset")
CLEAN_DIR = os.path.join(SCRIPT_DIR, "clean_data")
PG_CONN = ["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics"]

if not os.environ.get("PGPASSWORD"):
    raise RuntimeError("Set the PGPASSWORD environment variable before running this script (see .env.example).")


def transform():
    """Extract raw CSVs and transform into cleaned, type-cast CSVs ready to load."""
    os.makedirs(CLEAN_DIR, exist_ok=True)
    con = duckdb.connect()

    def nz(col):
        return f"NULLIF(\"{col}\", '?')"

    jobs = {
        "courses.csv": f"""
            SELECT code_module, code_presentation, CAST(module_presentation_length AS INT)
            FROM read_csv_auto('{RAW_DIR}/courses.csv', header=True, all_varchar=True)
        """,
        "assessments.csv": f"""
            SELECT code_module, code_presentation, CAST(id_assessment AS INT), assessment_type,
                   CAST({nz('date')} AS INT), CAST(weight AS DECIMAL(5,2))
            FROM read_csv_auto('{RAW_DIR}/assessments.csv', header=True, all_varchar=True)
        """,
        "vle.csv": f"""
            SELECT CAST(id_site AS INT), code_module, code_presentation, activity_type,
                   CAST({nz('week_from')} AS SMALLINT), CAST({nz('week_to')} AS SMALLINT)
            FROM read_csv_auto('{RAW_DIR}/vle.csv', header=True, all_varchar=True)
        """,
        "student_info.csv": f"""
            SELECT CAST(id_student AS INT), code_module, code_presentation, gender, region,
                   highest_education, {nz('imd_band')}, age_band,
                   CAST(num_of_prev_attempts AS SMALLINT), CAST(studied_credits AS INT),
                   disability, final_result
            FROM read_csv_auto('{RAW_DIR}/studentInfo.csv', header=True, all_varchar=True)
        """,
        "student_registration.csv": f"""
            SELECT CAST(id_student AS INT), code_module, code_presentation,
                   CAST({nz('date_registration')} AS INT), CAST({nz('date_unregistration')} AS INT)
            FROM read_csv_auto('{RAW_DIR}/studentRegistration.csv', header=True, all_varchar=True)
        """,
        "student_assessment.csv": f"""
            SELECT CAST(id_assessment AS INT), CAST(id_student AS INT),
                   CAST({nz('date_submitted')} AS INT), CAST(is_banked AS INT)::BOOLEAN,
                   CAST({nz('score')} AS SMALLINT)
            FROM read_csv_auto('{RAW_DIR}/studentAssessment.csv', header=True, all_varchar=True)
        """,
        "student_vle_staging.csv": f"""
            SELECT code_module, code_presentation, CAST(id_student AS INT), CAST(id_site AS INT),
                   CAST(date AS INT), CAST(sum_click AS INT)
            FROM read_csv_auto('{RAW_DIR}/studentVle.csv', header=True, all_varchar=True)
        """,
        "student_vle.csv": f"""
            SELECT id_student, code_module, code_presentation, id_site, date, SUM(sum_click) AS sum_click
            FROM (SELECT code_module, code_presentation, CAST(id_student AS INT) AS id_student,
                         CAST(id_site AS INT) AS id_site, CAST(date AS INT) AS date,
                         CAST(sum_click AS INT) AS sum_click
                  FROM read_csv_auto('{RAW_DIR}/studentVle.csv', header=True, all_varchar=True))
            GROUP BY id_student, code_module, code_presentation, id_site, date
        """,
    }

    for outfile, query in jobs.items():
        con.execute(f"COPY ({query}) TO '{CLEAN_DIR}/{outfile}' (HEADER false, FORMAT csv)")
    print("Transform stage complete: 8 cleaned CSVs written to", CLEAN_DIR)


def load():
    """Load the cleaned CSVs into the PostgreSQL staging and cleaned tables."""
    schema_sql = os.path.join(PROJECT_ROOT, "02_SQL_Scripts", "01_schema.sql")
    subprocess.run(PG_CONN + ["-f", schema_sql], check=True)

    copy_cmds = {
        "courses": "\\copy afilearn.courses FROM 'courses.csv' WITH (FORMAT csv)",
        "assessments": "\\copy afilearn.assessments (code_module, code_presentation, id_assessment, assessment_type, date, weight) FROM 'assessments.csv' WITH (FORMAT csv)",
        "vle": "\\copy afilearn.vle (id_site, code_module, code_presentation, activity_type, week_from, week_to) FROM 'vle.csv' WITH (FORMAT csv)",
        "student_info": "\\copy afilearn.student_info (id_student, code_module, code_presentation, gender, region, highest_education, imd_band, age_band, num_of_prev_attempts, studied_credits, disability, final_result) FROM 'student_info.csv' WITH (FORMAT csv)",
        "student_registration": "\\copy afilearn.student_registration (id_student, code_module, code_presentation, date_registration, date_unregistration) FROM 'student_registration.csv' WITH (FORMAT csv)",
        "student_assessment": "\\copy afilearn.student_assessment (id_assessment, id_student, date_submitted, is_banked, score) FROM 'student_assessment.csv' WITH (FORMAT csv)",
        "student_vle_staging": "\\copy afilearn.student_vle_staging (code_module, code_presentation, id_student, id_site, date, sum_click) FROM 'student_vle_staging.csv' WITH (FORMAT csv)",
        "student_vle": "\\copy afilearn.student_vle (id_student, code_module, code_presentation, id_site, date, sum_click) FROM 'student_vle.csv' WITH (FORMAT csv)",
    }
    for table, cmd in copy_cmds.items():
        subprocess.run(PG_CONN + ["-c", cmd], cwd=CLEAN_DIR, check=True)
        print(f"Loaded {table}")


def quality_report():
    """Compare raw vs cleaned row counts to quantify what the pipeline changed."""
    con = duckdb.connect()
    raw_vle = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{RAW_DIR}/studentVle.csv', header=True, all_varchar=True)").fetchone()[0]
    clean_vle = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{CLEAN_DIR}/student_vle.csv', header=False)").fetchone()[0]
    print("\n=== DATA QUALITY REPORT ===")
    print(f"studentVle raw rows:        {raw_vle:,}")
    print(f"studentVle cleaned rows:    {clean_vle:,}")
    print(f"Rows removed by dedup/agg:  {raw_vle - clean_vle:,} ({100*(raw_vle-clean_vle)/raw_vle:.1f}%)")


if __name__ == "__main__":
    transform()
    load()
    quality_report()
