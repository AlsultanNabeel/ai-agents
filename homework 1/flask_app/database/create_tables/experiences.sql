-- experiences.sql
-- Stores specific projects or achievements within a position.
-- One position can have many experiences (e.g. an Instructor might have
-- taught CSE 477 and CSE 491 — two separate experiences).
--
-- The hyperlink column lets you link to a project page, paper, or repo.

CREATE TABLE IF NOT EXISTS experiences (
    experience_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id    INTEGER NOT NULL,
    name           TEXT    NOT NULL,   -- e.g. 'CSE 491 — AI Agents'
    description    TEXT    NOT NULL,   -- one-sentence summary
    hyperlink      TEXT,               -- URL to project, paper, or repo (optional)
    start_date     TEXT,               -- stored as 'YYYY-MM-DD' (optional)
    end_date       TEXT,               -- NULL means ongoing (optional)
    FOREIGN KEY (position_id) REFERENCES positions(position_id)
);
