-- institutions.sql
-- Stores places where a person has worked or studied.
-- This is the top level of the resume hierarchy:
--   institutions → positions → experiences → skills
--
-- Each institution gets a unique ID automatically (AUTOINCREMENT).
-- You never need to set inst_id yourself — SQLite handles it.

CREATE TABLE IF NOT EXISTS institutions (
    inst_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,   -- e.g. 'Academia', 'Industry', 'Government'
    name        TEXT NOT NULL,   -- e.g. 'Michigan State University'
    department  TEXT,            -- e.g. 'Computer Science' (optional)
    address     TEXT,
    city        TEXT,
    state       TEXT,
    zip         TEXT
);
