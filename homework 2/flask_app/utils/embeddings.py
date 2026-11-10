import json
import os
import math
import requests

EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

# I chose it from measure of the wrong and true ones which is start from 0.15 for the true and the false ome reached only 0.13  
DEFAULT_MIN_SCORE = 0.15

# For each table: its ID column, and which columns make up the embedded text
TEXT_COLUMNS = {
    'institutions': ('inst_id', ['name', 'department', 'city']),
    'positions': ('position_id', ['title', 'responsibilities']),
    'experiences': ('experience_id', ['name', 'description']),
    'skills': ('skill_id', ['name']),
}


class EmbeddingError(Exception):
    pass


def get_embedding(text):
    model = os.getenv('EMBEDDING_MODEL')
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not model or not api_key:
        raise EmbeddingError("EMBEDDING_MODEL or OPENROUTER_API_KEY is missing from .env")

    try:
        response = requests.post(
            EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": text},
            timeout=30,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise EmbeddingError(f"request failed: {error}")

    if response.status_code != 200 or not body.get('data'):
        raise EmbeddingError(f"API error {response.status_code}: {body.get('error', body)}")

    vector = body['data'][0].get('embedding')
    if not vector:
        raise EmbeddingError("API returned an empty vector")
    # A zero vector would match nothing meaningfully, so it must never be stored
    if all(value == 0 for value in vector):
        raise EmbeddingError("API returned an all-zero vector")
    return vector


def build_text(table, row):
    _, columns = TEXT_COLUMNS[table]
    return ", ".join(str(row[column]) for column in columns if row.get(column))


def sync_embeddings(db):
    model = os.getenv('EMBEDDING_MODEL')
    stored = {
        (row['source_table'], row['record_id']): row
        for row in db.query("SELECT source_table, record_id, text, model FROM embeddings")
    }
    current = set()

    for table, (id_column, _) in TEXT_COLUMNS.items():
        for row in db.query(f"SELECT * FROM {table}"):
            key = (table, row[id_column])
            current.add(key)
            text = build_text(table, row)
            old = stored.get(key)

            # Skip rows whose text and model haven't changed since they were embedded
            if old and old['text'] == text and old['model'] == model:
                continue

            try:
                vector = get_embedding(text)
            except EmbeddingError as error:
                print(f"[Embeddings] FAILED {table} #{key[1]}: {error}")
                # Only drop the old vector if the row's text changed; a broken model
                # setting must not wipe embeddings that are still correct
                if old and old['text'] != text:
                    db.query("DELETE FROM embeddings WHERE source_table = ? AND record_id = ?", key)
                continue

            db.query(
                "INSERT OR REPLACE INTO embeddings (source_table, record_id, text, vector, model) "
                "VALUES (?, ?, ?, ?, ?)",
                (table, key[1], text, json.dumps(vector), model),
            )
            print(f"[Embeddings] stored {table} #{key[1]}: {text}")

    # Rows that were deleted lose their embedding too
    for key in set(stored) - current:
        db.query("DELETE FROM embeddings WHERE source_table = ? AND record_id = ?", key)
        print(f"[Embeddings] removed {key[0]} #{key[1]}")





def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def search(db, query, tables=None, top_k=5, min_score=None):
    if min_score is None:
        min_score = float(os.getenv('SEARCH_MIN_SCORE') or DEFAULT_MIN_SCORE)

    query_vector = get_embedding(query)

    sql = "SELECT source_table, record_id, text, vector FROM embeddings"
    params = ()
    if tables:
        sql += f" WHERE source_table IN ({', '.join('?' for _ in tables)})"
        params = tuple(tables)

    results = []
    for row in db.query(sql, params):
        score = cosine_similarity(query_vector, json.loads(row['vector']))
        if score < min_score:
            continue

        results.append({
            'table': row['source_table'],
            'id': row['record_id'],
            'text': row['text'],
            'score': round(score, 3),
        })

    results.sort(key=lambda result: result['score'], reverse=True)
    return results[:top_k]

