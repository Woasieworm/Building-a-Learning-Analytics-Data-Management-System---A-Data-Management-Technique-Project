"""
DSCD 606 Semester Project — AfiLearn Learning Analytics Office
Phase 9: Distributed files, Hadoop ecosystem and MapReduce-style processing

DuckDB is used as the approved big-data processing environment (per the module
list: Spark, PySpark, Hive, Pig, Hadoop MapReduce, DuckDB, Dask). It processes
the studentVle table (10,655,280 raw rows) directly off disk using a columnar,
multi-threaded execution engine, without loading the file into memory first,
which is the same map/reduce-style principle (partition, process in parallel,
combine) that Spark or Hadoop MapReduce would apply to the same problem.
"""

import duckdb
import time
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

con = duckdb.connect()
RAW = os.path.join(PROJECT_ROOT, "open+university+learning+analytics+dataset", "studentVle.csv")

print("=== Task 1: weekly engagement trend per module presentation ===")
t0 = time.time()
result = con.execute(f"""
    SELECT code_module, code_presentation,
           (date / 7)::INT AS week_number,
           SUM(sum_click) AS total_clicks,
           COUNT(DISTINCT id_student) AS active_students
    FROM read_csv_auto('{RAW}', header=True, all_varchar=True,
                        columns={{'code_module':'VARCHAR','code_presentation':'VARCHAR',
                                  'id_student':'INT','id_site':'INT','date':'INT','sum_click':'INT'}})
    GROUP BY code_module, code_presentation, week_number
    ORDER BY code_module, code_presentation, week_number
""").fetchdf()
t1 = time.time()
print(f"Rows processed: 10,655,280 raw -> {len(result):,} weekly aggregates in {t1-t0:.2f}s")
print(result.head(8).to_string(index=False))

print("\n=== Task 2: top 20 most-clicked VLE resources across the entire dataset ===")
t0 = time.time()
top_resources = con.execute(f"""
    SELECT id_site, SUM(sum_click) AS total_clicks, COUNT(DISTINCT id_student) AS distinct_students
    FROM read_csv_auto('{RAW}', header=True, all_varchar=True,
                        columns={{'code_module':'VARCHAR','code_presentation':'VARCHAR',
                                  'id_student':'INT','id_site':'INT','date':'INT','sum_click':'INT'}})
    GROUP BY id_site
    ORDER BY total_clicks DESC
    LIMIT 20
""").fetchdf()
t1 = time.time()
print(f"Processed in {t1-t0:.2f}s")
print(top_resources.to_string(index=False))

print("\n=== Task 3: student engagement percentile ranking (window function over 10.6M rows) ===")
t0 = time.time()
percentiles = con.execute(f"""
    WITH student_totals AS (
        SELECT id_student, code_module, code_presentation, SUM(sum_click) AS total_clicks
        FROM read_csv_auto('{RAW}', header=True, all_varchar=True,
                            columns={{'code_module':'VARCHAR','code_presentation':'VARCHAR',
                                      'id_student':'INT','id_site':'INT','date':'INT','sum_click':'INT'}})
        GROUP BY id_student, code_module, code_presentation
    )
    SELECT code_module, code_presentation,
           MIN(total_clicks) AS min_clicks,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_clicks), 0) AS median_clicks,
           ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_clicks), 0) AS p90_clicks,
           MAX(total_clicks) AS max_clicks
    FROM student_totals
    GROUP BY code_module, code_presentation
    ORDER BY code_module, code_presentation
""").fetchdf()
t1 = time.time()
print(f"Processed in {t1-t0:.2f}s")
print(percentiles.head(8).to_string(index=False))

# Save outputs as evidence
result.to_csv(os.path.join(SCRIPT_DIR, "weekly_engagement_trend.csv"), index=False)
top_resources.to_csv(os.path.join(SCRIPT_DIR, "top_20_resources.csv"), index=False)
percentiles.to_csv(os.path.join(SCRIPT_DIR, "engagement_percentiles.csv"), index=False)
print("\nAll three outputs saved to bigdata/ as CSV evidence.")
