# One-time helper: copies llm_roles.csv into the database WITHOUT touching your resume data.
import csv, sqlite3
c = sqlite3.connect("flask_app/database/resume.db")
for r in csv.DictReader(open("flask_app/database/initial_data/llm_roles.csv", encoding="utf-8")):
    c.execute("""INSERT INTO llm_roles (role, domain, specific_instructions, background_context, few_shot_examples)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(role) DO UPDATE SET
                     domain = excluded.domain,
                     specific_instructions = excluded.specific_instructions,
                     background_context = excluded.background_context,
                     few_shot_examples = excluded.few_shot_examples""",
              (r["role"], r["domain"], r["specific_instructions"], r["background_context"], r["few_shot_examples"]))
c.commit()
print("llm_roles now holds:", [row[0] for row in c.execute("SELECT role FROM llm_roles")])
