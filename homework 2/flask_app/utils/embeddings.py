
import json
import math

from flask_app.utils.database import database
from flask_app.utils.llm import get_embedding


def cosine_similarity(vector1, vector2):
    dot = sum(a * b for a, b in zip(vector1, vector2))
    norm1 = math.sqrt(sum(a * a for a in vector1))
    norm2 = math.sqrt(sum(b * b for b in vector2))

    if len(vector1) != len(vector2) or norm1 == 0 or norm2 == 0:
        return 0

    return dot / (norm1 * norm2)


def save_embedding(source_table, record_id, content):
    vector = get_embedding(content)
    db = database()

    db.query(
        """
        INSERT INTO embeddings (source_table, record_id, content, vector)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_table, record_id)
        DO UPDATE SET content = excluded.content,
                      vector = excluded.vector
        """,
        (source_table, record_id, content, json.dumps(vector))
    )


def semantic_search(question, limit=5):
    db = database()
    question_vector = get_embedding(question)

    rows = db.query("SELECT * FROM embeddings")
    results = []

    for row in rows:
        stored_vector = json.loads(row["vector"])
        score = cosine_similarity(question_vector, stored_vector)

        results.append({
            "source_table": row["source_table"],
            "record_id": row["record_id"],
            "content": row["content"],
            "score": score
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
