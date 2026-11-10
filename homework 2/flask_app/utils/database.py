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
import json
import os
from io import StringIO

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
        Create all database tables and load initial data from CSV files.

        Args:
            purge (bool): If True, drop existing tables first (fresh start).

        # QUESTION: What would happen if you ran the app twice without purge=True?
        #           The INSERT statements would try to insert duplicate IDs.
        #           Try it — comment out purge=True in __init__.py and restart.
        """
        data_folder = 'flask_app/database/'

                                                    # Check whether the database already exists
        is_new_database = (
                         not os.path.exists(self.db_path)
                        or os.path.getsize(self.db_path) == 0
                                                    )

        if purge:
            for table in reversed(TABLE_ORDER):
                self.query(f"DROP TABLE IF EXISTS {table}")

        for table in TABLE_ORDER:
            self._create_table(data_folder, table)

        if is_new_database or purge:
            for table in TABLE_ORDER:
                self._seed_table(data_folder, table)

    def _create_table(self, data_folder, table):
        """Read the .sql file for a table and execute it."""
        sql_file = os.path.join(data_folder, 'create_tables', f'{table}.sql')
        with open(sql_file) as f:
            self.query(f.read())

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
        if table == "institutions":
            from flask_app.utils.llm import get_embedding

            institutions = self.query(
                "SELECT inst_id, name, department, city FROM institutions"
            )

            for inst in institutions:
                text = " ".join(
                    str(inst[field])
                    for field in ("name", "department", "city")
                    if inst[field]
                )

                try:
                    embedding = get_embedding(text)
                    self.saveEmbedding(
                        "institutions",
                        inst["inst_id"],
                        embedding
                    )
                except Exception as error:
                    print(f"Embedding failed: {error}")
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
    def insertRows(self, table, columns, values):
        """
        Insert one row into table. Any value that starts with "(SELECT" is
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

    def saveEmbedding(self, record_type, record_id, embedding):
        if not embedding or not any(v != 0 for v in embedding):
            raise ValueError("Invalid embedding")

        self.query(
            """DELETE FROM embeddings
               WHERE record_type = ? AND record_id = ?""",
            (record_type, record_id)
        )

        self.query(
            """INSERT INTO embeddings
               (record_type, record_id, embedding)
               VALUES (?, ?, ?)""",
            (record_type, record_id, json.dumps(embedding))
        )

    def semanticSearch(self, question, top_k=5):
        import json
        import math
        from flask_app.utils.llm import get_embedding

        query_embedding = get_embedding(question)

        if not query_embedding or not any(query_embedding):
            raise ValueError("Invalid query embedding")

        stored = self.query(
            "SELECT record_type, record_id, embedding FROM embeddings"
        )

        results = []

        for row in stored:
            if row["record_type"] != "institutions":
                continue

            vector = json.loads(row["embedding"])

            if len(vector) != len(query_embedding):
                continue

            dot = sum(a * b for a, b in zip(query_embedding, vector))
            norm_a = math.sqrt(sum(a * a for a in query_embedding))
            norm_b = math.sqrt(sum(b * b for b in vector))

            if norm_a == 0 or norm_b == 0:
                continue

            score = dot / (norm_a * norm_b)
            if score < 0.50:
                continue

            records = self.query(
                "SELECT name, department, city FROM institutions WHERE inst_id = ?",
                (row["record_id"],)
            )

            if not records:
                continue

            record = records[0]
            text = " ".join(
                str(record[field])
                for field in ("name", "department", "city")
                if record[field]
            )

            results.append({
                "table": row["record_type"],
                "record_id": row["record_id"],
                "text": text,
                "score": round(score, 4)
            })

        return sorted(
            results,
            key=lambda item: item["score"],
            reverse=True
        )[:top_k]