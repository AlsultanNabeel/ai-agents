-- llm_roles.sql
-- Stores each AI expert's prompt-template parameters. All four experts
-- (and the Orchestrator) are the same underlying model — only these rows
-- differ between them.
CREATE TABLE IF NOT EXISTS llm_roles (
    role_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    role                   TEXT NOT NULL UNIQUE,
    domain                 TEXT NOT NULL,
    specific_instructions  TEXT NOT NULL,
    background_context     TEXT,
    few_shot_examples      TEXT
);