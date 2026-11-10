-- skills.sql
-- Stores technical skills, optionally linked to a specific experience.
-- skill_level is a number from 1 (beginner) to 10 (expert).
--
-- experience_id can be NULL if the skill is not tied to a specific project —
-- for example, a general skill like 'Public Speaking'.

CREATE TABLE IF NOT EXISTS skills (
    skill_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id  INTEGER,             -- which experience used this skill (optional)
    name           TEXT    NOT NULL,    -- e.g. 'Python', 'JavaScript'
    skill_level    INTEGER NOT NULL,    -- 1 (beginner) to 10 (expert)
    FOREIGN KEY (experience_id) REFERENCES experiences(experience_id)
);
