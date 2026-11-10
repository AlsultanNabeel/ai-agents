"""
database.py — manages all interactions with the SQLite database.

A database is an organized way to store and retrieve data. We use SQLite,
which stores everything in a single file (resume.db) — no server needed.

This file is organized as a class called `database`. You learned about classes
in your OOP course: a class bundles related data and functions together.
Here, the class bundles all database operations (creating tables, inserting
data, querying data) into one place.

HOW THE DATA IS ORGANIZED:
  institutions  (e.g. Michigan State University)
      └── positions  (e.g. Instructor)
              └── experiences  (e.g. CSE 491)
                      └── skills  (e.g. Python, level 10)
"""

import sqlite3
import csv
import os
from io import StringIO
from flask_app.utils import embeddings

# Path to the SQLite database file — created automatically on first run
DB_PATH = 'flask_app/database/resume.db'

# Tables must be created in this order because of foreign key relationships.
# For example, 'positions' references 'institutions', so institutions must exist first.
TABLE_ORDER = ['institutions', 'positions', 'experiences', 'skills', 'llm_roles', 'embeddings']

class database:
    """
    Manages all interactions with the SQLite resume database.

    Usage:
        db = database()
        db.createTables(purge=True)   # sets up tables and loads CSV data
        data = db.getResumeData()     # returns the full resume as a dict
    """

    # A deletion waiting for the user's yes/no (None = nothing waiting)
    pending = None  

    def __init__(self):
        """
        Store the path to the database file.
        Unlike PostgreSQL, SQLite needs no username, password, or host —
        just a file path.
        """
        self.db_path = DB_PATH

    # ------------------------------------------------------------------
    # CORE QUERY FUNCTION
    # ------------------------------------------------------------------

    def query(self, sql, params=()):
        """
        Execute any SQL statement and return results as a list of dicts.

        Args:
            sql    (str):   The SQL statement to run.
            params (tuple): Values to safely substitute into the SQL.

        Returns:
            list: A list of dicts for SELECT queries; empty list otherwise.

        WHY params INSTEAD OF F-STRINGS?
            Never put user input directly into SQL like:
                f"SELECT * FROM users WHERE name = '{name}'"
            A malicious user could type  '; DROP TABLE users; --  as their name.
            Using params=() tells SQLite to treat the value as data, not code.
            This is called "parameterized queries" and prevents SQL injection.
        """
        # Connect to the database file (creates it if it doesn't exist)
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")

        # row_factory lets us access columns by name: row['title']
        # instead of by index: row[0]
        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()
        cursor.execute(sql, params)

        # Only fetch rows for queries that return data
        results = []
        if sql.strip().upper().startswith(('SELECT', 'PRAGMA')):
            results = [dict(row) for row in cursor.fetchall()]

        connection.commit()
        connection.close()
        return results

    # ------------------------------------------------------------------
    # TABLE SETUP
    # ------------------------------------------------------------------

    def createTables(self, purge=False):
        """
        Create all tables and load initial data from the CSV files.

        purge=True  -> drop everything and start fresh (test reset only).
        purge=False -> keep the existing database. Each table is filled from its CSV
                       ONCE (tracked in seeded_tables), so rows you delete stay deleted.
                       The llm_roles prompts are the exception: they are re-read from
                       their CSV on every start, so prompt edits take effect.
        """
        data_folder = 'flask_app/database/'

        if purge:
            # Drop tables in reverse order so foreign keys don't block deletion
            for table in reversed(TABLE_ORDER):
                self.query(f"DROP TABLE IF EXISTS {table}")
            self.query("DROP TABLE IF EXISTS seeded_tables")

        # Remembers which tables have already been filled from their CSV
        self.query("CREATE TABLE IF NOT EXISTS seeded_tables (name TEXT PRIMARY KEY)")
        seeded = {row['name'] for row in self.query("SELECT name FROM seeded_tables")}

        for table in TABLE_ORDER:
            self._create_table(data_folder, table)
            if table == 'llm_roles':
                self._sync_llm_roles(data_folder)
            elif table not in seeded:
                # A table that already holds data (from before this change) is just
                # marked as loaded, so deleted rows are not brought back.
                if not self.query(f"SELECT 1 AS found FROM {table} LIMIT 1"):
                    self._seed_table(data_folder, table)
                self.query("INSERT OR IGNORE INTO seeded_tables (name) VALUES (?)", (table,))

    def _create_table(self, data_folder, table):
        """Read the .sql file for a table and execute it."""
        sql_file = os.path.join(data_folder, 'create_tables', f'{table}.sql')
        with open(sql_file) as f:
            self.query(f.read())

    def _sync_llm_roles(self, data_folder):
        """Copy the prompts from llm_roles.csv into the table on EVERY start (update or insert)."""
        csv_file = os.path.join(data_folder, 'initial_data', 'llm_roles.csv')
        if not os.path.exists(csv_file):
            return
        with open(csv_file, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            self.query("""INSERT INTO llm_roles
                              (role, domain, specific_instructions, background_context, few_shot_examples)
                          VALUES (?, ?, ?, ?, ?)
                          ON CONFLICT(role) DO UPDATE SET
                              domain = excluded.domain,
                              specific_instructions = excluded.specific_instructions,
                              background_context = excluded.background_context,
                              few_shot_examples = excluded.few_shot_examples""",
                       (r['role'], r['domain'], r['specific_instructions'],
                        r['background_context'], r['few_shot_examples']))
        names = [r['role'] for r in rows]
        if names:   # roles removed from the CSV are removed from the table
            self.query(f"DELETE FROM llm_roles WHERE role NOT IN ({','.join('?' * len(names))})",
                       tuple(names))

    def _seed_table(self, data_folder, table):
        """
        Load initial data from a CSV file into a table.

        The CSV files in flask_app/database/initial_data/ are where you
        customize the resume content. Each file corresponds to one table.

        # NOTE: Edit these CSV files to add your own resume data!
        #       Restart the app after editing to reload the database.
        """
        csv_file = os.path.join(data_folder, 'initial_data', f'{table}.csv')

        if not os.path.exists(csv_file):
            return

        with open(csv_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return

        columns = list(rows[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        sql = f"INSERT OR IGNORE INTO {table} ({column_names}) VALUES ({placeholders})"

        # Convert "NULL" strings from CSV into Python None values
        values = [
            tuple(None if cell == 'NULL' else cell for cell in row.values())
            for row in rows
        ]

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.executemany(sql, values)
        connection.commit()
        connection.close()
        print(f"  Loaded data for table: {table}")

    # ------------------------------------------------------------------
    # RESUME DATA
    # ------------------------------------------------------------------

    def getResumeData(self):
        """
        Return the full resume as a nested dictionary.

        Structure:
            {
              inst_id: {
                'name': '...', 'type': '...',
                'positions': {
                  position_id: {
                    'title': '...', 'start_date': '...',
                    'experiences': {
                      experience_id: {
                        'name': '...', 'description': '...',
                        'skills': { skill_id: {'name': '...', 'skill_level': 7} }
                      }
                    }
                  }
                }
              }
            }

        This nested structure is passed directly to the resume.html template,
        where Jinja2 loops over it to render the page.
        """
        resume = {}

        for institution in self.query("SELECT * FROM institutions"):
            inst_id = institution['inst_id']
            resume[inst_id] = dict(institution)
            resume[inst_id]['positions'] = {}

            positions = self.query(
                "SELECT * FROM positions WHERE inst_id = ? ORDER BY start_date DESC",
                (inst_id,)
            )

            for position in positions:
                pos_id = position['position_id']
                resume[inst_id]['positions'][pos_id] = dict(position)
                resume[inst_id]['positions'][pos_id]['experiences'] = {}

                experiences = self.query(
                    "SELECT * FROM experiences WHERE position_id = ? ORDER BY start_date DESC",
                    (pos_id,)
                )

                for experience in experiences:
                    exp_id = experience['experience_id']
                    resume[inst_id]['positions'][pos_id]['experiences'][exp_id] = dict(experience)
                    resume[inst_id]['positions'][pos_id]['experiences'][exp_id]['skills'] = {}

                    skills = self.query(
                        "SELECT * FROM skills WHERE experience_id = ?",
                        (exp_id,)
                    )

                    for skill in skills:
                        skill_id = skill['skill_id']
                        resume[inst_id]['positions'][pos_id]['experiences'][exp_id]['skills'][skill_id] = dict(skill)

        self._format_dates(resume)
        return resume

    def _format_dates(self, resume):
        """
        Convert raw date strings like '2019-01-01' to 'YYYY-MM' format.
        None end_dates become 'Present'.
        Modifies the resume dict in place.
        """
        for institution in resume.values():
            for position in institution['positions'].values():
                position['start_date'] = self._short_date(position['start_date'])
                position['end_date'] = self._short_date(position['end_date']) or 'Present'

                for experience in position['experiences'].values():
                    experience['start_date'] = self._short_date(experience['start_date'])
                    experience['end_date'] = self._short_date(experience['end_date']) or ''

    def _short_date(self, date_string):
        """Return just the 'YYYY-MM' part of a date string, or None."""
        if date_string:
            return str(date_string)[:7]
        return None

    def getResumeText(self):
        """
        Return the resume as a plain-text string, used as context for the AI.

        # NOTE: This is exactly what the AI reads about you before answering
        #       questions. Edit your CSV files to change what it knows.
        # QUESTION: What information would you add to make the AI more helpful?
        """
        resume = self.getResumeData()
        lines = []

        for institution in resume.values():
            lines.append(f"\nInstitution: {institution['name']} ({institution['type']}) — {institution.get('city', '')}, {institution.get('state', '')}")

            for position in institution['positions'].values():
                lines.append(f"  Position: {position['title']} ({position['start_date']} to {position['end_date']})")
                lines.append(f"  Responsibilities: {position.get('responsibilities', '')}")

                for experience in position['experiences'].values():
                    lines.append(f"    Experience: {experience['name']} — {experience.get('description', '')}")

                    for skill in experience['skills'].values():
                        lines.append(f"      Skill: {skill['name']} (level {skill['skill_level']}/10)")
                        
        return '\n'.join(lines)
    
    def getLLMRoles(self):
        """
        Return every row of llm_roles as a dict keyed by role name, e.g.
            {"Database Read Expert": {"role": ..., "domain": ..., ...}, ...}
        This is what each expert's config gets looked up from in llm.py.
        """
        rows = self.query("SELECT * FROM llm_roles")
        return {row['role']: row for row in rows}

    # ======================================================================
    # DATA MODIFICATION (INSERT, DELETE, UPDATE)
    # ======================================================================

    def insertRows(self, table, columns, values):
        """
        Insert one row into `table`. Any value that starts with "(SELECT" is
        inlined directly into the SQL instead of bound as a parameter, so the
        Database Write Expert's generated code can resolve a foreign key by
        name instead of needing to know the numeric ID, e.g.
            "(SELECT experience_id FROM experiences WHERE name = 'MSU Research')"
        """
        value_sql, bound_params = [], []
        for value in values:
            if isinstance(value, str) and value.strip().startswith("(SELECT"):
                value_sql.append(value)
            else:
                value_sql.append("?")
                bound_params.append(value)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(value_sql)})"
        self.query(sql, tuple(bound_params))

    def addSkill(self, experience_name, name, skill_level):
        """Add one skill to the experience with this exact name. Returns the message to show."""
        exps = self.query("SELECT experience_id FROM experiences WHERE lower(name) = lower(?)",
                          (experience_name,))
        if len(exps) != 1:
            return f"I couldn't find exactly one experience named '{experience_name}'."
        experience_id = exps[0]['experience_id']
        if self.query("SELECT 1 AS found FROM skills WHERE experience_id = ? AND lower(name) = lower(?)",
                      (experience_id, name)):
            return "Element already exists in the skills table."
        self.query("INSERT INTO skills (experience_id, name, skill_level) VALUES (?, ?, ?)",
                   (experience_id, name, skill_level))
        return f"New {name} added to the skills table."

    def deleteAllSkills(self):
        """PREVIEW ONLY - deletes nothing. Remembers every skill as the pending deletion."""
        rows = self.query("SELECT s.skill_id, s.name, s.skill_level, e.name AS experience "
                          "FROM skills s JOIN experiences e ON s.experience_id = e.experience_id "
                          "ORDER BY s.skill_id")
        if not rows:
            self.pending = None
            return "There are no skills to delete."
        lines = [f"- skill '{r['name']}' (id {r['skill_id']}, level {r['skill_level']}) "
                 f"in experience '{r['experience']}'" for r in rows]
        message = (f"This will delete ALL {len(rows)} skills:\n" + "\n".join(lines) +
                   "\n\nReply 'yes' to delete, or 'no' to cancel.")
        self.pending = {"skill_ids": [r['skill_id'] for r in rows], "message": message}
        return message        

    def deleteSkill(self, name, experience_name=None):
        """
        PREVIEW ONLY - deletes nothing. Finds the matching skills, remembers them as the
        pending deletion, and returns the message to show the user.
        experience_name may be an experience name or a position title.
        """
        sql = ("SELECT s.skill_id, s.name, s.skill_level, e.name AS experience "
               "FROM skills s "
               "JOIN experiences e ON s.experience_id = e.experience_id "
               "LEFT JOIN positions p ON e.position_id = p.position_id "
               "WHERE lower(s.name) = lower(?)")
        params = [name]
        if experience_name:
            sql += " AND (lower(e.name) = lower(?) OR lower(p.title) = lower(?))"
            params += [experience_name, experience_name]
        rows = self.query(sql, tuple(params))

        if not rows:
            self.pending = None
            return "Element not found in the skills table."

        lines = [f"- skill '{r['name']}' (id {r['skill_id']}, level {r['skill_level']}) "
                 f"in experience '{r['experience']}'" for r in rows]
        message = (f"This will delete {len(rows)} skill(s):\n" + "\n".join(lines) +
                   "\n\nReply 'yes' to delete, or 'no' to cancel.")
        self.pending = {"skill_ids": [r['skill_id'] for r in rows], "message": message}
        return message

    def confirmDelete(self):
        """Delete EXACTLY the skills that were previewed (by ID). Returns the message to show."""
        pending = self.pending
        self.pending = None                      # used up: a second 'yes' does nothing
        if not pending:
            return "Nothing is waiting for confirmation."
        for skill_id in pending["skill_ids"]:
            self.query("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
            self.query("DELETE FROM embeddings WHERE table_name = 'skills' AND record_id = ?", (skill_id,))
        return f"Deleted {len(pending['skill_ids'])} skill(s)."

    def cancelDelete(self):
        """Forget the pending deletion without deleting anything."""
        self.pending = None

    def syncEmbeddings(self):
        """Bring the embeddings up to date after the data changed. Never crashes the chat."""
        try:
            return embeddings.backfill(self)
        except embeddings.EmbeddingError as error:
            print(f"WARNING: embeddings not updated: {error}")    