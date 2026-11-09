-- llm_roles.sql
-- Stores the configuration for each AI expert.

CREATE TABLE IF NOT EXISTS llm_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    specific_instructions TEXT NOT NULL,
    background_context TEXT,
    few_shot_examples TEXT
);