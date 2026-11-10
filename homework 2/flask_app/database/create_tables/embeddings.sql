-- embeddings.sql
-- One row per embedded record: which table and row it came from,
-- the exact text that was embedded, and the vector stored as JSON.
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table  TEXT    NOT NULL,
    record_id     INTEGER NOT NULL,
    text          TEXT    NOT NULL,
    vector        TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    UNIQUE (source_table, record_id)
);
