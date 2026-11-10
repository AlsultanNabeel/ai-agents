"""
embeddings.py - turn text into embeddings (lists of numbers) through OpenRouter.

Settings are read from .env (never hard-coded):
    OPENROUTER_API_KEY   your key
    EMBEDDING_MODEL      the model name announced by the course team

RULE: a failed embedding must never look like a real one. Every vector goes through
validate_vector(); anything wrong raises EmbeddingError, so the caller can report it
and must NOT store or use that vector.
"""
import math
import os

EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


class EmbeddingError(Exception):
    """An embedding could not be produced, or is not trustworthy."""


def current_model():
    model = os.environ.get("EMBEDDING_MODEL")
    if not model:
        raise EmbeddingError("EMBEDDING_MODEL is not set in .env")
    return model


def validate_vector(vector):
    """Return the vector as a list of floats, or raise EmbeddingError."""
    if not isinstance(vector, (list, tuple)) or len(vector) == 0:
        raise EmbeddingError("embedding is empty")
    try:
        numbers = [float(x) for x in vector]
    except (TypeError, ValueError):
        raise EmbeddingError("embedding contains something that is not a number") from None
    if any(math.isnan(x) or math.isinf(x) for x in numbers):
        raise EmbeddingError("embedding contains NaN or infinity")
    if not any(numbers):
        raise EmbeddingError("embedding is all zeros")
    return numbers


def embed_texts(texts):
    """Embed a list of strings. Returns a list of validated vectors, in the same order."""
    import requests

    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = current_model()
    if not api_key:
        raise EmbeddingError("OPENROUTER_API_KEY is not set in .env")
    if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
        raise EmbeddingError("cannot embed empty text")

    try:
        response = requests.post(
            EMBED_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": texts},
            timeout=30,
        )
    except requests.RequestException as error:
        raise EmbeddingError(f"could not reach the embeddings API ({type(error).__name__})") from None

    if response.status_code != 200:
        # The response body explains the problem (bad model name, no credits...). It never contains the key.
        raise EmbeddingError(f"embeddings API returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        items = sorted(response.json()["data"], key=lambda item: item["index"])
    except (ValueError, KeyError, TypeError):
        raise EmbeddingError(f"unexpected response from the embeddings API: {response.text[:200]}") from None

    if len(items) != len(texts):
        raise EmbeddingError("the API returned the wrong number of embeddings")
    return [validate_vector(item.get("embedding")) for item in items]


# ======================================================================
# Part 2: which text represents each record, and storing the embeddings
# ======================================================================
import json


def _join(*parts, sep=", "):
    """Join the non-empty parts into one line of text."""
    return sep.join(str(p).strip() for p in parts if p is not None and str(p).strip())


# For each table: a SELECT that returns an `id` column plus the descriptive columns,
# and a function that turns one row into the text to embed.
# Left out on purpose: IDs, dates, hyperlinks and skill_level (they carry no meaning).
SOURCES = {
    "institutions": (
        "SELECT inst_id AS id, name, type, department, city, state FROM institutions",
        lambda r: _join(r["name"], r["type"], r["department"], r["city"], r["state"]),
    ),
    "positions": (
        "SELECT p.position_id AS id, p.title, p.responsibilities, i.name AS inst "
        "FROM positions p LEFT JOIN institutions i ON p.inst_id = i.inst_id",
        lambda r: _join(_join(r["title"], r["inst"], sep=" at "), r["responsibilities"], sep=". "),
    ),
    "experiences": (
        "SELECT experience_id AS id, name, description FROM experiences",
        lambda r: _join(r["name"], r["description"], sep=". "),
    ),
    "skills": (
        "SELECT s.skill_id AS id, s.name, e.name AS exp "
        "FROM skills s LEFT JOIN experiences e ON s.experience_id = e.experience_id",
        lambda r: _join(r["name"], ("skill used in " + r["exp"]) if r["exp"] else None, sep=" - "),
    ),
}


def save_embedding(db, table, record_id, text, vector, model):
    """Store one embedding. The vector is validated again here, so a bad one can never be saved."""
    vector = validate_vector(vector)
    db.query("INSERT OR REPLACE INTO embeddings (table_name, record_id, text, vector, model) "
             "VALUES (?, ?, ?, ?, ?)", (table, record_id, text, json.dumps(vector), model))


def remove_embedding(db, table, record_id):
    db.query("DELETE FROM embeddings WHERE table_name = ? AND record_id = ?", (table, record_id))


def backfill(db, batch_size=50):
    """
    Bring the embeddings table up to date with the records. Safe to run on every start:
      - records with no embedding, or whose text/model changed -> embedded (stale ones are replaced)
      - embeddings whose record no longer exists               -> removed
      - everything already correct                            -> left alone (no API call)
    A failed call is reported in the result and nothing is stored for those records.
    """
    model = current_model()
    report = {"embedded": 0, "unchanged": 0, "removed": 0, "failed": []}
    stored = {(r["table_name"], r["record_id"]): (r["text"], r["model"])
              for r in db.query("SELECT table_name, record_id, text, model FROM embeddings")}

    for table, (sql, build_text) in SOURCES.items():
        live_ids, todo = set(), []
        for row in db.query(sql):
            live_ids.add(row["id"])
            text = build_text(row)
            if not text:
                continue
            if stored.get((table, row["id"])) == (text, model):
                report["unchanged"] += 1
            else:
                todo.append((row["id"], text))

        for (t, record_id) in list(stored):            # embeddings of deleted records
            if t == table and record_id not in live_ids:
                remove_embedding(db, table, record_id)
                report["removed"] += 1

        for i in range(0, len(todo), batch_size):
            chunk = todo[i:i + batch_size]
            try:
                vectors = embed_texts([text for _, text in chunk])
            except EmbeddingError as error:
                report["failed"].append({"table": table, "ids": [rid for rid, _ in chunk],
                                         "reason": str(error)})
                for rid, _ in chunk:                 # never keep a stale embedding
                    remove_embedding(db, table, rid)
                continue
            for (record_id, text), vector in zip(chunk, vectors):
                try:
                    save_embedding(db, table, record_id, text, vector, model)
                    report["embedded"] += 1
                except EmbeddingError as error:      # a bad vector is reported, never stored
                    remove_embedding(db, table, record_id)   # ...and no stale one is kept
                    report["failed"].append({"table": table, "ids": [record_id], "reason": str(error)})
    return report


# ======================================================================
# Part 3: search by meaning
# ======================================================================

def cosine(a, b):
    """Cosine similarity: 1.0 = same direction (same meaning), near 0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def rank(query_vector, items, top_k=5, min_score=0.0):
    """
    Generic ranking, independent of the resume. `items` are dicts with a 'vector' plus any
    other keys (for the resume: table, id, text). Returns the items WITHOUT their vector but
    WITH a 'score', best first, dropping anything below min_score.
    HW3 can reuse this for other text, e.g. web-search snippets: {"table": "web", "id": url, ...}.
    """
    scored = []
    for item in items:
        if len(item["vector"]) != len(query_vector):     # vectors from a different model
            continue
        result = {k: v for k, v in item.items() if k != "vector"}
        result["score"] = round(cosine(query_vector, item["vector"]), 4)
        scored.append(result)
    scored.sort(key=lambda r: r["score"], reverse=True)
    return [r for r in scored if r["score"] >= min_score][:top_k]


def search(db, question, tables=None, top_k=5, min_score=None):
    """
    Search the stored embeddings by meaning.
      tables:    which tables to compare against (None = all of them)
      min_score: the 'no match' cut-off; defaults to SEARCH_MIN_SCORE from .env
    Returns [{'table', 'id', 'text', 'score'}, ...] best first; [] means "nothing relevant".
    """
    if min_score is None:
        value = os.environ.get("SEARCH_MIN_SCORE")
        if not value:
            raise EmbeddingError("SEARCH_MIN_SCORE is not set in .env - run score_check.py to choose it")
        min_score = float(value)
    tables = list(tables) if tables else list(SOURCES)
    unknown = [t for t in tables if t not in SOURCES]
    if unknown:
        raise ValueError(f"unknown table(s): {unknown}")

    query_vector = embed_texts([question])[0]
    marks = ",".join("?" * len(tables))
    rows = db.query(f"SELECT table_name, record_id, text, vector FROM embeddings "
                    f"WHERE table_name IN ({marks}) AND model = ?", (*tables, current_model()))
    # Safety net: ignore any embedding whose record no longer exists (e.g. a deleted skill),
    # so a leftover embedding can never be returned as a match.
    live = {t: {r["id"] for r in db.query(SOURCES[t][0])} for t in tables}
    items = [{"table": r["table_name"], "id": r["record_id"], "text": r["text"],
              "vector": json.loads(r["vector"])}
             for r in rows if r["record_id"] in live[r["table_name"]]]
    return rank(query_vector, items, top_k, min_score)


def suggest_cutoff(hit_scores, miss_scores):
    """
    hit_scores:  best score of each query that SHOULD match
    miss_scores: best score of each query that should NOT match
    Returns (cutoff, explanation). The cut-off sits between the worst hit and the best miss.
    """
    worst_hit, best_miss = min(hit_scores), max(miss_scores)
    if worst_hit <= best_miss:
        return None, (f"No clean cut-off: a query that should match scored {worst_hit:.3f} but one that "
                      f"should not match scored {best_miss:.3f}. Add better test queries or improve the embedded text.")
    midpoint = round((worst_hit + best_miss) / 2, 2)
    return midpoint, (f"worst hit {worst_hit:.3f}, best miss {best_miss:.3f}; the middle of that gap is {midpoint}")
