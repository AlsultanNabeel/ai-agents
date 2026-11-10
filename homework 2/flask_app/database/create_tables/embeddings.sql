-- embeddings.sql
-- One row per embedded record. (table_name, record_id) says which record it belongs to;
-- text is exactly what was embedded; vector is the list of numbers saved as JSON;
-- model is the embedding model that produced it (so old and new models are never mixed).
CREATE TABLE IF NOT EXISTS embeddings (
    table_name TEXT NOT NULL,
    record_id  INTEGER NOT NULL,
    text       TEXT NOT NULL,
    vector     TEXT NOT NULL,
    model      TEXT NOT NULL,
    PRIMARY KEY (table_name, record_id)
);
