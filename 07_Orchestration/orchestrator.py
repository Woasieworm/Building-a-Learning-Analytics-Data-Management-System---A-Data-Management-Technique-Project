"""
DSCD 606 Semester Project — AfiLearn Learning Analytics Office
Phase 11: Pipelines, Orchestration, Cloud/Grid/Cluster Computing

A minimal DAG-style orchestrator, in the spirit of Airflow/Prefect, without
requiring a heavy scheduler installation. Each task declares its dependencies,
the orchestrator runs them in topological order, retries once on failure, is
idempotent (skips a task if its target is already in the expected state), and
writes a structured, timestamped log — the same evidence an Airflow run log
or a cron job's output would provide.
"""

import subprocess
import time
import datetime
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SQL_DIR = os.path.join(PROJECT_ROOT, "02_SQL_Scripts")
CLEAN_DATA_DIR = os.path.join(PROJECT_ROOT, "03_ETL_Pipeline", "clean_data")
LOG_PATH = os.path.join(SCRIPT_DIR, "pipeline_run.log")
QUALITY_REPORT_PATH = os.path.join(SCRIPT_DIR, "quality_report.txt")

if not os.environ.get("PGPASSWORD"):
    raise RuntimeError("Set the PGPASSWORD environment variable before running this script (see .env.example).")


def log(msg):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def pg(query):
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics", "-tAc", query],
        capture_output=True, text=True
    )
    return result.stdout.strip(), result.returncode


def run_task(name, depends_on, check_fn, run_fn, max_retries=1):
    """Run a task if check_fn() says it isn't already satisfied, else skip. Retry on failure."""
    log(f"TASK START  : {name} (depends_on={depends_on or 'none'})")
    t0 = time.time()

    if check_fn():
        log(f"TASK SKIP   : {name} — target already satisfied (idempotent skip)")
        return True

    attempt = 0
    while attempt <= max_retries:
        attempt += 1
        try:
            run_fn()
            if check_fn():
                log(f"TASK SUCCESS: {name} — completed in {time.time()-t0:.1f}s (attempt {attempt})")
                return True
            else:
                raise RuntimeError("post-condition not met after run")
        except Exception as e:
            log(f"TASK ERROR  : {name} — attempt {attempt} failed: {e}")
            if attempt > max_retries:
                log(f"TASK FAILED : {name} — exceeded max retries, aborting DAG")
                return False
            time.sleep(2)


# --- DAG task definitions -------------------------------------------------

def check_schema_exists():
    out, _ = pg("SELECT 1 FROM information_schema.schemata WHERE schema_name='afilearn'")
    return out.strip() == "1"

def run_schema():
    subprocess.run(["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics",
                     "-f", os.path.join(SQL_DIR, "01_schema.sql")], check=True,
                    stdout=subprocess.DEVNULL)

def check_core_tables_loaded():
    out, _ = pg("SELECT COUNT(*) FROM afilearn.student_info")
    return out.strip() == "32593"

def run_core_load():
    # small/medium tables only — large studentVle load is a separate idempotent task
    cmds = [
        "\\copy afilearn.courses FROM 'courses.csv' WITH (FORMAT csv)",
        "\\copy afilearn.assessments (code_module, code_presentation, id_assessment, assessment_type, date, weight) FROM 'assessments.csv' WITH (FORMAT csv)",
        "\\copy afilearn.vle (id_site, code_module, code_presentation, activity_type, week_from, week_to) FROM 'vle.csv' WITH (FORMAT csv)",
        "\\copy afilearn.student_info (id_student, code_module, code_presentation, gender, region, highest_education, imd_band, age_band, num_of_prev_attempts, studied_credits, disability, final_result) FROM 'student_info.csv' WITH (FORMAT csv)",
        "\\copy afilearn.student_registration (id_student, code_module, code_presentation, date_registration, date_unregistration) FROM 'student_registration.csv' WITH (FORMAT csv)",
        "\\copy afilearn.student_assessment (id_assessment, id_student, date_submitted, is_banked, score) FROM 'student_assessment.csv' WITH (FORMAT csv)",
    ]
    for c in cmds:
        subprocess.run(["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics", "-c", c],
                       cwd=CLEAN_DATA_DIR, check=True, stdout=subprocess.DEVNULL)

def check_vle_loaded():
    out, _ = pg("SELECT COUNT(*) FROM afilearn.student_vle")
    return out.strip() == "8459320"

def run_vle_load():
    # idempotent-skip covers the common case; this branch only fires on a fresh database
    subprocess.run(["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics", "-c",
                     "\\copy afilearn.student_vle (id_student, code_module, code_presentation, id_site, date, sum_click) FROM 'student_vle.csv' WITH (FORMAT csv)"],
                    cwd=CLEAN_DATA_DIR, check=True, stdout=subprocess.DEVNULL, timeout=600)

def check_warehouse_built():
    out, _ = pg("SELECT COUNT(*) FROM warehouse.fact_student_presentation")
    return out.strip() == "32593"

def run_warehouse():
    subprocess.run(["psql", "-h", "localhost", "-U", "afilearn_admin", "-d", "afilearn_analytics",
                     "-f", os.path.join(SQL_DIR, "04_warehouse.sql")], check=True, stdout=subprocess.DEVNULL)

def check_quality_report_fresh():
    return os.path.exists(QUALITY_REPORT_PATH) and \
           (time.time() - os.path.getmtime(QUALITY_REPORT_PATH) < 3600)

def run_quality_report():
    out, _ = pg("SELECT COUNT(*) FROM afilearn.student_vle_staging")
    out2, _ = pg("SELECT COUNT(*) FROM afilearn.student_vle")
    with open(QUALITY_REPORT_PATH, "w") as f:
        f.write(f"staging_rows={out}\ncleaned_rows={out2}\ngenerated_at={datetime.datetime.now().isoformat()}\n")


if __name__ == "__main__":
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    os.makedirs(SCRIPT_DIR, exist_ok=True)

    log("=== DAG RUN START: schema -> core_load -> vle_load -> warehouse -> quality_report ===")
    ok = run_task("create_schema", None, check_schema_exists, run_schema)
    if ok: ok = run_task("load_core_tables", "create_schema", check_core_tables_loaded, run_core_load)
    if ok: ok = run_task("load_student_vle", "create_schema", check_vle_loaded, run_vle_load)
    if ok: ok = run_task("build_warehouse", "load_core_tables,load_student_vle", check_warehouse_built, run_warehouse)
    if ok: ok = run_task("quality_report", "build_warehouse", check_quality_report_fresh, run_quality_report)
    log(f"=== DAG RUN {'COMPLETE' if ok else 'FAILED'} ===")
