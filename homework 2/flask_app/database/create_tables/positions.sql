-- positions.sql
-- Stores job titles held at each institution.
-- One institution can have many positions (e.g. you could be both a
-- researcher and an instructor at the same university).
--
-- The FOREIGN KEY constraint means: every position must belong to an
-- institution that already exists. You can't have a job without a workplace.

CREATE TABLE IF NOT EXISTS positions (
    position_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    inst_id          INTEGER NOT NULL,
    title            TEXT    NOT NULL,   -- e.g. 'Instructor', 'Researcher'
    responsibilities TEXT    NOT NULL,   -- brief description of the role
    start_date       TEXT    NOT NULL,   -- stored as 'YYYY-MM-DD'
    end_date         TEXT,               -- NULL means the position is current
    FOREIGN KEY (inst_id) REFERENCES institutions(inst_id)
);
