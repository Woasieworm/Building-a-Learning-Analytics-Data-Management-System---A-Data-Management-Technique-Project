# AfiLearn Pulse — Polyglot Data Warehouse & Early-Warning Retention Pipeline

**Gilbert Woasieworm Adjei · Philip Adiboye · Emmanuel Barima Nyamekye · Isaac Sam Annor**
(Team: Data Plumbers)
Department of Computer Science, University of Ghana
DSCD 606 — Data Management Techniques, 2026

---

## Overview

AfiLearn University's learning analytics office runs on disconnected flat files,
making it hard to answer basic operational questions — which students are at risk,
how many are eligible to graduate, which modules have the highest withdrawal rates.
This project builds an integrated data platform on top of the **Open University
Learning Analytics Dataset (OULAD)** that takes those flat files through a full
data management lifecycle: relational modelling, ETL/ELT, warehousing, NoSQL,
distributed big-data processing, orchestration, security, and disaster recovery.

The submission is organised as thirteen phases (see `01_Report/`), each with its
own deliverable folder in this repo.

---

## Dataset

**Open University Learning Analytics Dataset (OULAD)** — publicly available at
[analyse.kmi.open.ac.uk/open_dataset](https://analyse.kmi.open.ac.uk/open_dataset).

- 7 raw CSV files: courses, assessments, studentInfo, studentRegistration, vle,
  studentVle, studentAssessment
- `studentVle.csv` alone is 10,655,280 raw rows (~432 MB) — by far the largest table
- Not included in this repo due to size; download it from the link above and place
  the extracted files in `open+university+learning+analytics+dataset/` at the repo
  root (this path is what `pipeline.py`, `big_data_task.py`, `build_nosql.py`, and
  the notebook all expect — see `.gitignore`).

---

## Environment setup

1. Copy `.env.example` to `.env` and fill in your PostgreSQL password:
   ```bash
   cp .env.example .env
   ```
2. Export it before running any script that touches Postgres (`build_nosql.py`,
   `orchestrator.py`, `backup.ps1`, `pipeline.py`):
   ```bash
   # macOS/Linux
   export PGPASSWORD=$(grep PGPASSWORD .env | cut -d '=' -f2)
   # Windows PowerShell
   $env:PGPASSWORD = "your_postgres_password_here"
   ```
3. Before running `02_SQL_Scripts/05_security_idempotent.sql`, open it and replace
   `CHANGE_ME_ANALYST_PASSWORD` / `CHANGE_ME_DPO_PASSWORD` with real values — Postgres
   role creation can't read these from the environment, so they have to be edited
   directly in the script (don't commit real values).

Python dependencies used across the scripts and notebook: `duckdb`, `psycopg2`,
`redis`, `networkx`, `tinydb`, `pandas`, `pyspark`.

---

## Project structure

```
.
├── .env.example                      # Template for required environment variables
├── 01_Report/                        # Full 13-phase written report
├── 02_SQL_Scripts/                   # Schema, queries, transactions, warehouse, security
├── 03_ETL_Pipeline/                  # Phase 6: Extract/Transform/Load (DuckDB + PostgreSQL)
├── 04_NoSQL/                         # Phase 8: TinyDB, Redis, NetworkX (document/KV/graph)
├── 05_BigData/                       # Phase 9: DuckDB-based distributed processing
├── 06_Notebook/                      # Phase 10: executed big-data notebook
├── 07_Orchestration/                 # Phase 11: DAG-style pipeline orchestrator
├── 08_Backup/                        # Phase 12: PostgreSQL disaster-recovery backup script
└── 09_Diagrams/                      # ER diagrams (logical and physical), .drawio format
```

---

## Phase-by-phase summary

| Phase | Folder | What it covers |
|---|---|---|
| 1 | `01_Report/` | Dataset inventory, row counts, missingness audit, problem statement |
| 2 | `01_Report/` | Data models, lifecycle, metadata, governance matrix |
| 3 | `09_Diagrams/` | Conceptual and logical ER design |
| 4 | `02_SQL_Scripts/01_schema.sql`, `02_queries.sql`, `03_transaction_example.sql` | 3NF relational schema, SQL queries, ACID transaction example |
| 5 | `01_Report/` | Query optimisation, B-Tree indexing, storage tuning (2.4–3.0x speedups) |
| 6 | `03_ETL_Pipeline/pipeline.py` | Extract/Transform/Load: type casting, missing-value handling, studentVle deduplication |
| 7 | `02_SQL_Scripts/04_warehouse.sql` | Star Schema dimensional warehouse |
| 8 | `04_NoSQL/build_nosql.py` | TinyDB document store, Redis key-value store, NetworkX interaction graph |
| 9 | `05_BigData/big_data_task.py` | DuckDB-based distributed-style processing over 10.6M rows |
| 10 | `06_Notebook/phase10_bigdata_notebook.ipynb` | Interactive notebook version of the big-data analysis |
| 11 | `07_Orchestration/orchestrator.py` | DAG-style pipeline orchestration (Airflow-like), idempotent retries, structured logging |
| 12 | `02_SQL_Scripts/05_security_idempotent.sql`, `08_Backup/backup.ps1` | RBAC, dynamic PII masking, disaster-recovery backups |
| 13 | `01_Report/` | System architecture and conclusion |

---

## Running the pipeline end to end

```bash
# 1. Download OULAD and place it at ./open+university+learning+analytics+dataset/
# 2. Set PGPASSWORD (see Environment setup above)
# 3. Run the orchestrator — it runs schema creation, core-table load,
#    studentVle load, warehouse build, and a data-quality report, in
#    dependency order, skipping any step whose target already exists:
python 07_Orchestration/orchestrator.py

# Or run individual phases directly:
python 03_ETL_Pipeline/pipeline.py      # ETL only
python 04_NoSQL/build_nosql.py          # NoSQL layer only
python 05_BigData/big_data_task.py      # Big-data analysis only
```

Check `07_Orchestration/pipeline_run.log` and `quality_report.txt` for evidence
of the last run.

---

## Key results

- Diagnosed PostgreSQL query bottlenecks with `EXPLAIN (ANALYZE, BUFFERS)` and
  designed three targeted B-Tree indexes (temporal, selective, composite),
  achieving **2.4–3.0x query speedups** and eliminating full sequential scans
  across the 8.4M-row interaction table.
- Resolved the `studentVle` grain issue (duplicate `(student, site, date)` rows)
  by deduplicating and summing `sum_click` during the ETL transform stage.
- Implemented role-based access control with a masked analyst-facing view
  (age banded, no raw PII) alongside full DPO access to the underlying table.
- Automated daily disaster-recovery backups with 7-day retention via
  `pg_dump`/`pg_restore`.

Full details, including the data-quality audit and all phase write-ups, are in
`01_Report/DSCD_606_DMS_Final_Project.docx`.
