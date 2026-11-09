CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    embedded_text TEXT NOT NULL,
    vector TEXT NOT NULL,
    model TEXT NOT NULL,
    UNIQUE(source_table, source_id)
);
