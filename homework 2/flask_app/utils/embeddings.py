"""
embeddings.py — generate and validate text embeddings using OpenRouter.
"""

import os
import math
import requests
import json

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

class EmbeddingError(Exception):
    """Raised when an embedding cannot be generated or validated."""

def generate_embedding(text):
    """
    Generate a text embedding using the configured OpenRouter model.

    Returns:
        list[float]: A validated embedding vector.

    Raises:
        EmbeddingError: If configuration, API request, or validation fails.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("EMBEDDING_MODEL")

    if not api_key:
        raise EmbeddingError("OPENROUTER_API_KEY is not configured.")

    if not model:
        raise EmbeddingError("EMBEDDING_MODEL is not configured.")

    if not isinstance(text, str) or not text.strip():
        raise EmbeddingError("Cannot generate an embedding from empty text.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "input": text
    }

    try:
        response = requests.post(
            OPENROUTER_EMBEDDINGS_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

    except requests.exceptions.RequestException as error:
        raise EmbeddingError(
            f"OpenRouter request failed: {error}"
        ) from error

    except ValueError as error:
        raise EmbeddingError(
            "OpenRouter returned an invalid JSON response."
        ) from error

    if "error" in result:
        message = result["error"].get("message", "Unknown API error")
        raise EmbeddingError(f"OpenRouter error: {message}")

    try:
        vector = result["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError):
        raise EmbeddingError(
            "OpenRouter response did not contain an embedding."
        )

    if not isinstance(vector, list) or not vector:
        raise EmbeddingError("The returned embedding is empty or invalid.")

    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in vector
    ):
        raise EmbeddingError("The embedding contains invalid numeric values.")

    vector = [float(value) for value in vector]

    if all(value == 0.0 for value in vector):
        raise EmbeddingError("The returned embedding contains only zeros.")

    return vector

def build_embedded_text(source_table, record):
    """Convert a database record into descriptive text for embedding."""

    if source_table == "skills":
        parts = [
            f"Skill: {record['name']}",
            f"Skill level: {record['skill_level']} out of 10"
        ]

        if record.get("experience_name"):
            parts.append(f"Related experience: {record['experience_name']}")

    elif source_table == "experiences":
        parts = [
            f"Experience: {record['name']}",
            f"Description: {record['description']}",
            f"Position: {record['position_title']}",
            f"Institution: {record['institution_name']}"
        ]

    elif source_table == "positions":
        parts = [
            f"Position: {record['title']}",
            f"Responsibilities: {record['responsibilities']}",
            f"Institution: {record['institution_name']}"
        ]

        if record.get("institution_department"):
            parts.append(
                f"Department: {record['institution_department']}"
            )

    elif source_table == "institutions":
        parts = [
            f"Institution: {record['name']}",
            f"Type: {record['type']}"
        ]

        for field, label in [
            ("department", "Department"),
            ("city", "City"),
            ("state", "State")
        ]:
            if record.get(field):
                parts.append(f"{label}: {record[field]}")

    else:
        raise EmbeddingError(
            f"Unsupported source table: {source_table}"
        )

    return "\n".join(parts)

def embed_missing_records(db):
    """Generate and store embeddings for records that need them."""

    model = os.getenv("EMBEDDING_MODEL")
    if not model:
        raise EmbeddingError("EMBEDDING_MODEL is not configured.")

    table_methods = {
        "institutions": db.get_institutions_for_embedding,
        "positions": db.get_positions_for_embedding,
        "experiences": db.get_experiences_for_embedding,
        "skills": db.get_skills_for_embedding
    }

    results = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    for table, get_records in table_methods.items():
        records = get_records()

        for record in records:
            source_id = record[
                {
                    "institutions": "inst_id",
                    "positions": "position_id",
                    "experiences": "experience_id",
                    "skills": "skill_id"
                }[table]
            ]

            embedded_text = build_embedded_text(table, record)
            existing = db.get_embedding(table, source_id)

            if (
                existing
                and existing["embedded_text"] == embedded_text
                and existing["model"] == model
            ):
                results["skipped"] += 1
                continue

            is_update = existing is not None

            # Remove an outdated vector before attempting regeneration.
            if is_update:
                db.delete_embedding(table, source_id)

            try:
                vector = generate_embedding(embedded_text)
                db.save_embedding(
                    table, source_id, embedded_text, vector, model
                )

                if is_update:
                    results["updated"] += 1
                else:
                    results["created"] += 1

            except EmbeddingError as error:
                results["failed"] += 1
                print(
                    f"Embedding failed for {table} ID {source_id}: {error}"
                )

    print(f"Embedding results: {results}")
    return results

def cosine_similarity(vector_a, vector_b):
    """Calculate cosine similarity between two embedding vectors."""

    if len(vector_a) != len(vector_b) or not vector_a:
        raise EmbeddingError("Embedding dimensions do not match.")

    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))

    if magnitude_a == 0 or magnitude_b == 0:
        raise EmbeddingError("Cannot compare zero-magnitude vectors.")

    return dot_product / (magnitude_a * magnitude_b)


def semantic_search(db, query, source_tables=None, top_k=10):
    """
    Search stored embeddings by meaning and return ranked matches.

    Args:
        db: Database instance.
        query: User's natural-language search query.
        source_tables: Optional list of tables to search.
        top_k: Maximum number of results to return.

    Returns:
        A list of ranked matches with source details and similarity scores.
    """

    if not isinstance(query, str) or not query.strip():
        raise EmbeddingError("Search query cannot be empty.")

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise EmbeddingError("top_k must be a positive integer.")

    allowed_tables = {
        "skills",
        "experiences",
        "positions",
        "institutions"
    }

    if source_tables is not None:
        if (
            not isinstance(source_tables, list)
            or not source_tables
            or any(table not in allowed_tables for table in source_tables)
        ):
            raise EmbeddingError("Invalid source table filter.")

    query_vector = generate_embedding(query)
    stored_embeddings = db.get_all_embeddings()

    matches = []

    for item in stored_embeddings:
        if source_tables is not None and item["source_table"] not in source_tables:
            continue

        try:
            stored_vector = json.loads(item["vector"])

            if not isinstance(stored_vector, list) or not stored_vector:
                continue

            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in stored_vector
            ):
                continue

            if all(value == 0 for value in stored_vector):
                continue

            score = cosine_similarity(query_vector, stored_vector)

        except (json.JSONDecodeError, TypeError, EmbeddingError):
            continue

        matches.append({
            "source_table": item["source_table"],
            "source_id": item["source_id"],
            "embedded_text": item["embedded_text"],
            "similarity": score
        })

    matches.sort(
        key=lambda result: result["similarity"],
        reverse=True
    )

    MATCH_THRESHOLD = 0.40

    matches = [
        result for result in matches
        if result["similarity"] >= MATCH_THRESHOLD
    ]

    return matches[:top_k]