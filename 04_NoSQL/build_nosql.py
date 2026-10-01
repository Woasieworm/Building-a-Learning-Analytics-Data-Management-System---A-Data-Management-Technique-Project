"""
DSCD 606 Semester Project — AfiLearn Learning Analytics Office
Phase 8: NoSQL representations

1. Document store (TinyDB): one JSON document per student, combining demographics
   and a rolled-up performance/engagement profile across all their presentations.
2. Key-value store (Redis): fast lookups for the two things a student portal or
   dashboard would query most often — a student's final result, and a per-module
   summary card.
3. Graph (NetworkX): a bipartite student-resource interaction graph for one
   module presentation, used to find hub resources and engagement structure.
"""

import psycopg2
import redis
import networkx as nx
from tinydb import TinyDB, Query
import json
import os

PG_PASSWORD = os.environ.get("PGPASSWORD")
if not PG_PASSWORD:
    raise RuntimeError("Set the PGPASSWORD environment variable before running this script (see .env.example).")

conn = psycopg2.connect(host="localhost", dbname="afilearn_analytics", user="afilearn_admin", password=PG_PASSWORD)
cur = conn.cursor()

# ---------------------------------------------------------------------------
# 1. DOCUMENT STORE — student learning profiles
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(SCRIPT_DIR, exist_ok=True)
doc_path = os.path.join(SCRIPT_DIR, "student_profiles.json")
if os.path.exists(doc_path):
    os.remove(doc_path)
doc_db = TinyDB(doc_path)

cur.execute("""
    SELECT ds.id_student, ds.gender, ds.region, ds.highest_education, ds.imd_band,
           ds.age_band, ds.disability,
           COUNT(*) AS num_presentations,
           SUM(fsp.total_clicks) AS lifetime_clicks,
           ROUND(AVG(fsp.avg_score), 1) AS overall_avg_score,
           BOOL_OR(fsp.distinction_flag) AS ever_distinction,
           BOOL_OR(fsp.withdrawn_flag) AS ever_withdrawn,
           ARRAY_AGG(DISTINCT dc.code_module || '-' || dc.code_presentation) AS presentations
    FROM warehouse.dim_student ds
    JOIN warehouse.fact_student_presentation fsp ON fsp.student_key = ds.student_key
    JOIN warehouse.dim_course dc ON dc.course_key = fsp.course_key
    GROUP BY ds.id_student, ds.gender, ds.region, ds.highest_education, ds.imd_band, ds.age_band, ds.disability
    LIMIT 2000
""")
rows = cur.fetchall()
cols = [desc[0] for desc in cur.description]
docs = []
for row in rows:
    d = dict(zip(cols, row))
    d["lifetime_clicks"] = int(d["lifetime_clicks"] or 0)
    d["overall_avg_score"] = float(d["overall_avg_score"]) if d["overall_avg_score"] is not None else None
    docs.append(d)
doc_db.insert_multiple(docs)
print(f"Document store: {len(docs)} student profile documents written to {doc_path}")

# Example query: find distinction students with disability, region East Midlands Region
Student = Query()
example = doc_db.search((Student.ever_distinction == True) & (Student.disability == 'Y'))
print(f"Example document query — distinction students with a declared disability: {len(example)} found")
if example:
    print(json.dumps(example[0], indent=2, default=str))

# ---------------------------------------------------------------------------
# 2. KEY-VALUE STORE — fast lookups (Redis)
# ---------------------------------------------------------------------------
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
r.flushdb()

cur.execute("""
    SELECT si.id_student, si.code_module, si.code_presentation, si.final_result
    FROM afilearn.student_info si
""")
count = 0
for id_student, code_module, code_presentation, final_result in cur.fetchall():
    key = f"result:{id_student}:{code_module}:{code_presentation}"
    r.set(key, final_result)
    count += 1
print(f"\nKey-value store: {count} student result lookups loaded into Redis")

cur.execute("""
    SELECT dc.code_module, dc.code_presentation,
           ROUND(AVG(fsp.avg_score), 1) AS avg_score,
           ROUND(100.0 * COUNT(*) FILTER (WHERE fsp.withdrawn_flag) / COUNT(*), 1) AS withdrawal_pct,
           ROUND(AVG(fsp.total_clicks), 0) AS avg_clicks
    FROM warehouse.fact_student_presentation fsp
    JOIN warehouse.dim_course dc ON dc.course_key = fsp.course_key
    GROUP BY dc.code_module, dc.code_presentation
""")
for code_module, code_presentation, avg_score, withdrawal_pct, avg_clicks in cur.fetchall():
    key = f"module_summary:{code_module}:{code_presentation}"
    r.hset(key, mapping={
        "avg_score": str(avg_score) if avg_score is not None else "",
        "withdrawal_pct": str(withdrawal_pct),
        "avg_clicks": str(avg_clicks),
    })
print(f"Key-value store: {len(r.keys('module_summary:*'))} module summary cards loaded into Redis")

# Example lookups
print("Example lookup — result:11391:AAA:2013J ->", r.get("result:11391:AAA:2013J"))
print("Example lookup — module_summary:CCC:2014B ->", r.hgetall("module_summary:CCC:2014B"))

# ---------------------------------------------------------------------------
# 3. GRAPH — student-resource interaction network for one module presentation
# ---------------------------------------------------------------------------
TARGET_MODULE, TARGET_PRES = "CCC", "2014B"  # the highest withdrawal-rate presentation from Phase 7
cur.execute("""
    SELECT sv.id_student, sv.id_site, SUM(sv.sum_click) AS clicks
    FROM afilearn.student_vle sv
    WHERE sv.code_module = %s AND sv.code_presentation = %s
    GROUP BY sv.id_student, sv.id_site
""", (TARGET_MODULE, TARGET_PRES))

G = nx.Graph()
for id_student, id_site, clicks in cur.fetchall():
    G.add_edge(f"student_{id_student}", f"resource_{id_site}", weight=clicks)

print(f"\nGraph: bipartite network for {TARGET_MODULE}-{TARGET_PRES}")
print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

resource_nodes = [n for n in G.nodes if n.startswith("resource_")]
degree_sorted = sorted(resource_nodes, key=lambda n: G.degree(n), reverse=True)[:5]
print("Top 5 hub resources by number of connected students:")
for n in degree_sorted:
    print(f"  {n}: {G.degree(n)} students connected")

nx.write_graphml(G, os.path.join(SCRIPT_DIR, "cc_2014b_interaction_graph.graphml"))
print("Graph saved to nosql/cc_2014b_interaction_graph.graphml")

cur.close()
conn.close()
