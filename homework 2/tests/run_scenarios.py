"""
Runs the HW2 scenarios S1-S11 on the course test data (fixtures/) and prints
PASS or FAIL for each one.

Run from the homework 2 folder:
    python tests/run_scenarios.py

Every scenario talks to OpenRouter (chat model and/or embedding model), so
all of them need the real API and a working .env.

The tests use their own database (tests/test_resume.db), loaded from
fixtures/, so your real resume database is never touched.
"""
import contextlib
import csv
import io
import os
import sys

HW2_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(HW2_FOLDER)
sys.path.insert(0, HW2_FOLDER)

from dotenv import load_dotenv
load_dotenv()

import flask_app.utils.database as database_module

# Point the app at a separate test database before anything opens it
TEST_DB_PATH = 'tests/test_resume.db'
database_module.DB_PATH = TEST_DB_PATH

from flask_app.utils.embeddings import sync_embeddings, search, get_embedding, EmbeddingError

RESUME_TABLES = ['institutions', 'positions', 'experiences', 'skills']
results = []


def quiet(function, *args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        value = function(*args)
    return value, output.getvalue()


def load_fixtures():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db = database_module.database()
    quiet(db.createTables, True)
    db.query("DELETE FROM embeddings")
    for table in reversed(RESUME_TABLES):
        db.query(f"DELETE FROM {table}")
    for table in RESUME_TABLES:
        with open(f'fixtures/{table}.csv') as file:
            for row in csv.DictReader(file):
                columns = ', '.join(row)
                placeholders = ', '.join('?' for _ in row)
                values = tuple(None if value == 'NULL' else value for value in row.values())
                db.query(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
    _, output = quiet(sync_embeddings, db)
    failed = output.count('FAILED')
    if failed:
        print(f"WARNING: {failed} fixture embeddings failed (network?). Search scenarios may fail.")


def skills(db):
    rows = db.query(
        "SELECT s.name, e.name AS experience FROM skills s "
        "LEFT JOIN experiences e ON s.experience_id = e.experience_id"
    )
    return sorted(f"{row['name']} @ {row['experience']}" for row in rows)


def say(client, message):
    def send():
        client.emit('send_message', {'message': message})
        received = client.get_received()
        return received[-1]['args'][0]['response'] if received else ''
    return quiet(send)


def score_lines(trace):
    return [line.strip() for line in trace.splitlines() if line.startswith('    0.')]


def record(scenario, passed, detail):
    results.append((scenario, passed))
    print(f"{scenario}  {'PASS' if passed else 'FAIL'}  (needs API)  {detail}")


def main():
    print("Loading fixtures into the test database...")
    load_fixtures()
    from flask_app import create_app
    (app, socketio), _ = quiet(create_app)
    db = app.db
    client = socketio.test_client(app)

    # S1: abbreviation finds Michigan State University, with scores in the trace
    reply, trace = say(client, "Find my MSU experience")
    hits = score_lines(trace)
    record("S1 ", any('Michigan State University' in hit for hit in hits[:3]),
           f"top results: {hits[:2]}")

    # S2: AI skills returns Machine Learning; Public Speaking absent or lower
    reply, trace = say(client, "What AI skills do I have?")
    hits = score_lines(trace)
    names = [hit.split('  ', 2)[-1] for hit in hits]
    ml = next((i for i, hit in enumerate(hits) if 'Machine Learning' in hit), None)
    speaking = next((i for i, hit in enumerate(hits) if 'Public Speaking' in hit), None)
    record("S2 ", ml is not None and (speaking is None or speaking > ml), f"results: {names}")

    # S3: exact question goes to the Database Read Expert, with a reason
    reply, trace = say(client, "List all my skills")
    record("S3 ", 'step 1: Database Read Expert' in trace and 'Semantic Search Expert' not in trace
           and '| reason:' in trace, f"reply: {reply[:70]!r}")

    # S4: two dependent steps; the SQL uses the name found by the search
    reply, trace = say(client, "What did I do at MSU?")
    record("S4 ", 'step 1: Semantic Search Expert' in trace and 'step 2: Database Read Expert' in trace
           and "'Michigan State University'" in trace, f"reply: {reply[:70]!r}")

    # S5: a skill added through the chat survives a restart and is found by meaning
    say(client, "Add Rust to CSE 847")
    restarted = database_module.database()
    quiet(restarted.createTables, False)
    quiet(sync_embeddings, restarted)
    stored = restarted.query("SELECT 1 FROM embeddings WHERE source_table = 'skills' AND text = 'Rust'")
    found, _ = quiet(search, restarted, "Do I know the Rust programming language?", ['skills'])
    record("S5 ", 'Rust @ CSE 847' in skills(restarted) and bool(stored)
           and any(result['text'] == 'Rust' for result in found),
           f"in skills: {'Rust @ CSE 847' in skills(restarted)}, embedding: {bool(stored)}")

    # S6: deletion shows the exact action; "no" changes nothing
    before = skills(db)
    shown, _ = say(client, "Remove Python from CSE 847")
    reply, _ = say(client, "no")
    record("S6 ", "delete skill 'Python' from experience 'CSE 847'" in shown and skills(db) == before,
           f"shown: {shown[:70]!r}")

    # S7: same deletion, "yes" runs exactly that one action
    before = skills(db)
    say(client, "Remove Python from CSE 847")
    say(client, "yes")
    removed = set(before) - set(skills(db))
    added = set(skills(db)) - set(before)
    record("S7 ", removed == {'Python @ CSE 847'} and not added, f"removed: {sorted(removed)}")

    # S8: "maybe" and changing the subject approve nothing, even with a later "yes"
    before = skills(db)
    say(client, "Remove HTML from CSE 847")
    say(client, "maybe")
    say(client, "yes")
    maybe_ok = skills(db) == before
    say(client, "Remove CSS from CSE 847")
    say(client, "How many skills do I have?")
    say(client, "yes")
    record("S8 ", maybe_ok and skills(db) == before,
           f"maybe: unchanged={maybe_ok}, change of subject: unchanged={skills(db) == before}")

    # S9: no danger word, still paused for approval
    before = skills(db)
    shown, _ = say(client, "Clean up my skills so the list is empty")
    unchanged = skills(db) == before
    say(client, "no")
    record("S9 ", 'delete ALL skills' in shown and unchanged, f"shown: {shown[:70]!r}")

    # S10: a broken embedding model gives a clear error, stores nothing, and the app keeps working
    real_model = os.environ.get('EMBEDDING_MODEL', '')
    os.environ['EMBEDDING_MODEL'] = 'not-a-real/model'
    count_before = db.query("SELECT COUNT(*) AS n FROM embeddings")[0]['n']
    try:
        get_embedding("test")
        raised = False
    except EmbeddingError:
        raised = True
    reply, _ = say(client, "Find my MSU experience")
    count_after = db.query("SELECT COUNT(*) AS n FROM embeddings")[0]['n']
    os.environ['EMBEDDING_MODEL'] = real_model
    after_reply, _ = say(client, "How many positions do I have?")
    record("S10", raised and 'Michigan State' not in reply and count_after == count_before
           and '4' in after_reply,
           f"reply while broken: {reply[:60]!r}; afterwards: {after_reply[:40]!r}")

    # S11: nothing in the data matches Harvard
    reply, trace = say(client, "Find my Harvard experience")
    record("S11", 'Semantic Search Expert' in trace and not score_lines(trace), f"reply: {reply[:70]!r}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} scenarios passed")


if __name__ == '__main__':
    main()
