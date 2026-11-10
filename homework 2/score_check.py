"""
Run from the project folder:  python score_check.py
Prints the real similarity scores so YOU can choose (a) which tables to search and
(b) the 'no match' cut-off. Edit the two query lists to fit your own resume data.
"""
from dotenv import load_dotenv
load_dotenv()
from flask_app.utils.database import database
from flask_app.utils import embeddings

# Queries that SHOULD find something in your data (use the wording a user would use,
# NOT the exact words stored in the database).
SHOULD_MATCH = [
    "city planning",
    "design software",
    "managing a team",
    "Gaza municipality",
]
# Queries that should find NOTHING (things that are not in your data).
SHOULD_NOT_MATCH = [
    "Harvard",
    "banana bread recipe",
    "quantum physics",
]
# A query about skills, to compare 'all tables' with 'skills only'.
SKILL_QUERIES = ["design software", "project management", "programming"]

db = database()


def top(query, tables=None, n=3):
    return embeddings.search(db, query, tables=tables, top_k=n, min_score=-1)   # -1 = no cut-off


def show(title, queries, tables=None):
    print(f"\n=== {title} ===")
    best = []
    for q in queries:
        hits = top(q, tables)
        best.append(hits[0]["score"] if hits else 0.0)
        print(f"\n  query: {q!r}")
        for h in hits:
            print(f"    {h['score']:.3f}  {h['table']}#{h['id']}  {h['text'][:70]}")
    return best

hit_best = show("SHOULD match (all tables)", SHOULD_MATCH)
miss_best = show("SHOULD NOT match (all tables)", SHOULD_NOT_MATCH)

print("\n=== Which tables? Same skill questions, all tables vs skills only ===")
for q in SKILL_QUERIES:
    print(f"\n  query: {q!r}")
    print("   all tables:")
    for h in top(q):
        print(f"    {h['score']:.3f}  {h['table']}#{h['id']}  {h['text'][:60]}")
    print("   skills only:")
    for h in top(q, ["skills"]):
        print(f"    {h['score']:.3f}  {h['table']}#{h['id']}  {h['text'][:60]}")

cutoff, why = embeddings.suggest_cutoff(hit_best, miss_best)
print("\n=== Suggested cut-off ===")
print(f"  {why}")
if cutoff is not None:
    print(f"  -> put SEARCH_MIN_SCORE={cutoff} in .env (then re-run this script after any model change)")
