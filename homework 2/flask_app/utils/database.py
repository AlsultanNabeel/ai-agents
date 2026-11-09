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
import json
import math
from io import StringIO

# Path to the SQLite database file — created automatically on first run
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'resume.db')
DATA_FOLDER = os.path.join(BASE_DIR, 'database')

# Tables must be created in this order because of foreign key relationships.
# For example, 'positions' references 'institutions', so institutions must exist first.
TABLE_ORDER = ['institutions', 'positions', 'experiences', 'skills', 'llm_roles', 'embeddings']
class ApprovalGrant:
    """One-time authorization for an exact database deletion."""

    def __init__(self, action_fingerprint, secret):
        if secret is not _APPROVAL_SECRET:
            raise PermissionError("Approval grants cannot be created directly.")

        self.action_fingerprint = action_fingerprint
        self.used = False

    def consume(self, action_fingerprint):
        """Validate and consume this grant exactly once."""
        if self.used:
            raise PermissionError("This approval grant has already been used.")

        if self.action_fingerprint != action_fingerprint:
            raise PermissionError("Approval does not match the requested action.")

        self.used = True


_APPROVAL_SECRET = object()


def create_approval_grant(action_fingerprint):
    """Create a grant for use after the chat approval has been verified."""
    if not isinstance(action_fingerprint, str) or not action_fingerprint:
        raise ValueError("Invalid approval fingerprint.")

    return ApprovalGrant(action_fingerprint, _APPROVAL_SECRET)

def build_deletion_fingerprint(operation, skill_ids):
    """Build a stable fingerprint for an exact skill deletion."""
    if operation not in {"delete_skill", "delete_all_skills"}:
        raise ValueError("Unsupported deletion operation.")

    if not isinstance(skill_ids, list) or not skill_ids:
        raise ValueError("No skill records were specified.")

    if any(
        isinstance(skill_id, bool)
        or not isinstance(skill_id, int)
        or skill_id <= 0
        for skill_id in skill_ids
    ):
        raise ValueError("Invalid skill ID.")

    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("Duplicate skill IDs are not allowed.")

    return json.dumps(
        {
            "operation": operation,
            "skill_ids": sorted(skill_ids)
        },
        sort_keys=True,
        separators=(",", ":")
    )

class database:
    """
    Manages all interactions with the SQLite resume database.

    Usage:
        db = database()
        db.createTables(purge=True)   # sets up tables and loads CSV data
        data = db.getResumeData()     # returns the full resume as a dict
    """

    def __init__(self, db_path=DB_PATH):
        """
        Store the path to the database file.
        Unlike PostgreSQL, SQLite needs no username, password, or host —
        just a file path.
        """
        self.db_path = db_path

    # ------------------------------------------------------------------
    # CORE QUERY FUNCTION
    # ------------------------------------------------------------------

    def query(self, sql, params=(), return_lastrowid=False):
        """
        Execute any SQL statement.

        Returns:
            - SELECT / PRAGMA: list of dictionaries containing query results.
            - Other statements: empty list by default.
            - INSERT with return_lastrowid=True: ID of the inserted row.
        """
        # Connect to the database file (creates it if it doesn't exist)
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")

        # Access columns by name instead of index
        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()
        cursor.execute(sql, params)

        # Fetch rows only for queries that return data
        results = []
        if sql.strip().upper().startswith(("SELECT", "PRAGMA")):
            results = [dict(row) for row in cursor.fetchall()]

        # Return the inserted row's ID when explicitly requested
        if return_lastrowid:
            result = cursor.lastrowid
        else:
            result = results

        connection.commit()
        connection.close()

        return result

    # ------------------------------------------------------------------
    # TABLE SETUP
    # ------------------------------------------------------------------

    def createTables(self, purge=False):
        """
        Create tables, load initial resume data once, and sync LLM roles.

        Resume CSV files are loaded only on first initialization.
        LLM role prompts are synchronized on every startup.
        """
        data_folder = DATA_FOLDER
        resume_tables = ['institutions', 'positions', 'experiences', 'skills']

        if purge:
            for table in reversed(TABLE_ORDER):
                self.query(f"DROP TABLE IF EXISTS {table}")
            self.query("DROP TABLE IF EXISTS app_metadata")

        # Create all application tables.
        for table in TABLE_ORDER:
            self._create_table(data_folder, table)

        # Track whether initial resume data has already been loaded.
        self.query("""
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        initialized = self.query(
            "SELECT value FROM app_metadata WHERE key = ?",
            ("resume_csv_seeded",)
        )

        if not initialized:
            print("Loading initial resume data...")
            for table in resume_tables:
                self._seed_table(data_folder, table)

            self.query(
                "INSERT INTO app_metadata (key, value) VALUES (?, ?)",
                ("resume_csv_seeded", "true")
            )

        # LLM prompts are synchronized on every startup.
        self._sync_llm_roles(data_folder)

    def _sync_llm_roles(self, data_folder):
        """Insert new LLM roles and update existing role instructions."""
        csv_file = os.path.join(data_folder, 'initial_data', 'llm_roles.csv')

        if not os.path.exists(csv_file):
            return

        with open(csv_file, newline='', encoding='utf-8') as f:
            rows = csv.DictReader(f)

            for row in rows:
                values = [
                    None if row.get(column) in (None, 'NULL') else row[column]
                    for column in (
                        'role',
                        'domain',
                        'specific_instructions',
                        'background_context',
                        'few_shot_examples'
                    )
                ]

                self.query("""
                    INSERT INTO llm_roles (
                        role, domain, specific_instructions,
                        background_context, few_shot_examples
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(role) DO UPDATE SET
                        domain = excluded.domain,
                        specific_instructions = excluded.specific_instructions,
                        background_context = excluded.background_context,
                        few_shot_examples = excluded.few_shot_examples
                """, tuple(values))

        print("LLM roles synchronized.")

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
        Return every row of llm_roles as a dictionary keyed by role name.
        """
        rows = self.query("SELECT * FROM llm_roles")
        return {row['role']: row for row in rows}

    def insertRows(self, table, columns, values):
        """
        Insert one row into a table and return its ID.

        Values beginning with "(SELECT" are inserted as SQL expressions
        to allow looking up foreign keys by name.
        """
        value_sql = []
        bound_params = []

        for value in values:
            if isinstance(value, str) and value.strip().startswith("(SELECT"):
                value_sql.append(value)
            else:
                value_sql.append("?")
                bound_params.append(value)

        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join(value_sql)})"
        )

        return self.query(
            sql,
            tuple(bound_params),
            return_lastrowid=True
        )

    def insert_approved_record(self, table, values):
        """
        Insert a validated record using allow-listed table and column names.
        This method never executes SQL supplied by the LLM.
        """
        allowed_columns = {
            "institutions": {
                "type", "name", "department", "address",
                "city", "state", "zip"
            },
            "positions": {
                "inst_id", "title", "responsibilities",
                "start_date", "end_date"
            },
            "experiences": {
                "position_id", "name", "description",
                "hyperlink", "start_date", "end_date"
            },
            "skills": {
                "experience_id", "name", "skill_level"
            }
        }

        if table not in allowed_columns:
            raise ValueError("Table is not allowed.")

        if not isinstance(values, dict) or not values:
            raise ValueError("Invalid record values.")

        columns = list(values.keys())

        if not set(columns).issubset(allowed_columns[table]):
            raise ValueError("One or more columns are not allowed.")

        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)

        sql = (
            f"INSERT INTO {table} ({column_sql}) "
            f"VALUES ({placeholders})"
        )

        connection = sqlite3.connect(self.db_path)

        try:
            connection.execute("PRAGMA foreign_keys = ON")

            with connection:
                cursor = connection.execute(
                    sql,
                    tuple(values[column] for column in columns)
                )
                record_id = cursor.lastrowid

            return record_id

        finally:
            connection.close()


    def save_embedding(self, source_table, source_id, embedded_text, vector, model):
        """Insert or update an embedding for a source record."""
        if not isinstance(vector, list) or not vector:
            raise ValueError("Embedding vector must be a non-empty list.")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError("Embedding vector contains invalid values.")

        if all(value == 0 for value in vector):
            raise ValueError("Embedding vector cannot contain only zeros.")

        self.query("""
            INSERT INTO embeddings (
                source_table, source_id, embedded_text, vector, model
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_table, source_id) DO UPDATE SET
                embedded_text = excluded.embedded_text,
                vector = excluded.vector,
                model = excluded.model
        """, (
            source_table,
            source_id,
            embedded_text,
            json.dumps(vector),
            model
        ))

    def get_embedding(self, source_table, source_id):
        """Retrieve an embedding and decode its vector."""
        rows = self.query("""
            SELECT * FROM embeddings
            WHERE source_table = ? AND source_id = ?
        """, (source_table, source_id))

        if not rows:
            return None

        record = rows[0]
        record["vector"] = json.loads(record["vector"])
        return record

    def get_all_embeddings(self):
        """Retrieve all stored embeddings."""
        return self.query("SELECT * FROM embeddings")

    def delete_embedding(self, source_table, source_id):
        """Delete the embedding associated with a source record."""
        self.query("""
            DELETE FROM embeddings
            WHERE source_table = ? AND source_id = ?
        """, (source_table, source_id))

    def get_skills_for_embedding(self):
        """Retrieve skills with their related experience names."""
        return self.query("""
            SELECT
                s.skill_id,
                s.name,
                s.skill_level,
                s.experience_id,
                e.name AS experience_name
            FROM skills s
            LEFT JOIN experiences e
                ON s.experience_id = e.experience_id
        """)

    def get_skill_with_context(self, skill_id):
        """Retrieve one skill with its full resume context."""
        results = self.query("""
            SELECT
                s.skill_id,
                s.name AS skill_name,
                s.skill_level,
                s.experience_id,
                e.name AS experience_name,
                p.title AS position_title,
                i.name AS institution_name
            FROM skills s
            LEFT JOIN experiences e
                ON s.experience_id = e.experience_id
            LEFT JOIN positions p
                ON e.position_id = p.position_id
            LEFT JOIN institutions i
                ON p.inst_id = i.inst_id
            WHERE s.skill_id = ?
        """, (skill_id,))

        return results[0] if results else None

    def delete_skill_records(self, skill_ids, operation, approval_grant):
        """
        Delete an exact set of skills and their embeddings.

        A matching, unused approval grant is required.
        """

        if operation not in {"delete_skill", "delete_all_skills"}:
            raise ValueError("Unsupported deletion operation.")

        if not isinstance(skill_ids, list) or not skill_ids:
            raise ValueError("No skill records were specified.")

        if any(
            isinstance(skill_id, bool)
            or not isinstance(skill_id, int)
            or skill_id <= 0
            for skill_id in skill_ids
        ):
            raise ValueError("Invalid skill ID.")

        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Duplicate skill IDs are not allowed.")

        fingerprint_data = {
            "operation": operation,
            "skill_ids": sorted(skill_ids)
        }

        fingerprint = json.dumps(
            fingerprint_data,
            sort_keys=True,
            separators=(",", ":")
        )

        if not isinstance(approval_grant, ApprovalGrant):
            raise PermissionError("A valid approval grant is required.")

        approval_grant.consume(fingerprint)

        placeholders = ",".join("?" for _ in skill_ids)

        connection = sqlite3.connect(self.db_path)

        try:
            connection.execute("PRAGMA foreign_keys = ON")

            with connection:
                existing = connection.execute(
                    f"""
                    SELECT skill_id
                    FROM skills
                    WHERE skill_id IN ({placeholders})
                    """,
                    skill_ids
                ).fetchall()

                existing_ids = {row[0] for row in existing}

                if existing_ids != set(skill_ids):
                    raise ValueError(
                        "One or more approved skills no longer exist."
                    )

                connection.execute(
                    f"""
                    DELETE FROM embeddings
                    WHERE source_table = 'skills'
                    AND source_id IN ({placeholders})
                    """,
                    skill_ids
                )

                connection.execute(
                    f"""
                    DELETE FROM skills
                    WHERE skill_id IN ({placeholders})
                    """,
                    skill_ids
                )

        finally:
            connection.close()

        return True

    def get_experiences_for_embedding(self):
        """Retrieve experiences with their position and institution context."""
        return self.query("""
            SELECT
                e.experience_id,
                e.name,
                e.description,
                p.title AS position_title,
                i.name AS institution_name
            FROM experiences e
            JOIN positions p
                ON e.position_id = p.position_id
            JOIN institutions i
                ON p.inst_id = i.inst_id
        """)

    def get_positions_for_embedding(self):
        """Retrieve positions with their institution context."""
        return self.query("""
            SELECT
                p.position_id,
                p.title,
                p.responsibilities,
                i.name AS institution_name,
                i.department AS institution_department
            FROM positions p
            JOIN institutions i
                ON p.inst_id = i.inst_id
        """)

    def get_institutions_for_embedding(self):
        """Retrieve institutions and prepare their information for embedding."""
        return self.query("""
            SELECT
                inst_id,
                type,
                name,
                department,
                city,
                state
            FROM institutions
        """)
