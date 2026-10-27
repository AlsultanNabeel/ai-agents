# CSE 491 — AI Agents: Homework 1

## What You're Building

In Homework 0, your app had **one** AI personality: a resume reviewer that answered every question the same way. In Homework 1, you'll turn that single chatbot into a **multi-expert agent system** — four specialized AI "experts" that share one underlying model but behave completely differently depending on the job they're given:

- **Database Read Expert** — turns a question into a SQL query and answers from the database
- **Database Write Expert** — turns a request into code that updates the database
- **Content Expert** — answers questions about the resume content itself
- **Orchestrator** — reads the user's message, decides *which* experts are needed and *in what order*, runs them, and stitches their results into one clean answer

This is the core idea behind most real-world "AI agent" systems: instead of one prompt trying to do everything, you build focused specialists and a coordinator that routes work between them.

This guide gives you working code for every piece — your job is to follow along, type it in, understand what each part does, and test it. You are not expected to invent this from scratch.

---



## How It Works

```
You (browser)
     |  type a message → JavaScript emits 'send_message' over WebSocket
     v
Flask + Socket.IO   (flask_app/utils/socket_events.py)
     |  calls handle_ai_chat_request(db, role="Orchestrator", message=...)
     v
llm.py: Orchestrator
     |  decides which experts are needed, in what order
     |  returns a plan, e.g.
     |    ["handle_ai_chat_request(role=\"Database Read Expert\", message=\"...\")",
     |     "handle_ai_chat_request(role=\"Database Write Expert\", message=\"...\")"]
     v
llm.py: run_orchestrator_plan()
     |  runs each expert call in order, collecting results
     |     Database Read Expert  → generates SQL   → queries the DB
     |     Database Write Expert → generates Python → updates the DB
     |     Content Expert        → answers from the resume text directly
     |  makes ONE final call to turn the raw results into a clean answer
     v
Flask emits 'receive_message' back over WebSocket
     |
     v
JavaScript displays the reply AND refreshes the resume panel
```

Every expert is the **same underlying model** — what makes them behave differently is the *system prompt* each one gets, built from a shared template. That's the idea you're implementing in Step 1.

---



## Example Flows

The diagram above is the general shape. Here's what actually happens, step by step, for four real messages — these are traced from real runs, not hypothetical.

**Example 1 — a plain read ("How long did they work at Michigan State University?")**

```
User message
     v
Orchestrator generates a 1-step plan:
     ["handle_ai_chat_request(role=\"Database Read Expert\", message=\"How long did they work at Michigan State University?\")"]
     v
run_orchestrator_plan() executes that one call:
     v
Database Read Expert generates SQL:
     SELECT p.start_date, p.end_date FROM positions p
     JOIN institutions i ON p.inst_id = i.inst_id
     WHERE i.name = 'Michigan State University';
     v
execute_read_query() runs it against the DB, returns the raw rows
     v
Orchestrator's final synthesis call turns the raw rows into:
     "They've worked at Michigan State University since January 2019."
     v
Chat panel shows that one sentence. Nothing else changes (no write, no refresh needed).
```

Even a single-expert question always passes through the Orchestrator first — there's no shortcut that skips it (see "all messages first go to the Orchestrator" below).

**Example 2 — a write ("Add TensorFlow as a skill to his BRAINWORKS experience")**

```
User message
     v
Orchestrator generates a 1-step plan naming the Write Expert
     v
Database Write Expert generates Python:
     existing = db.query("SELECT * FROM skills WHERE name = 'TensorFlow'
                           AND experience_id = (SELECT experience_id FROM
                           experiences WHERE name = 'BRAINWORKS')")
     if existing:
         outcome = "Element already exists in the skills table."
     else:
         db.insertRows('skills', ['experience_id', 'name', 'skill_level'],
             ["(SELECT experience_id FROM experiences WHERE name = 'BRAINWORKS')",
              'TensorFlow', 8])
         outcome = "New TensorFlow added to the skills table."
     v
execute_write_action() runs that code with exec() -- the INSERT actually happens here
     v
Orchestrator's synthesis call reuses outcome verbatim (it's already the exact message)
     v
Chat panel shows: "New TensorFlow added to the skills table."
     v
Browser calls refreshResumeContent() -- the skill badge appears on the resume
     panel immediately, without a full page reload
```

**Example 3 — a compound request ("Does he know Rust? If not, add it to his most recent experience.")**

```
User message
     v
Orchestrator generates a 2-step plan:
     ["handle_ai_chat_request(role=\"Database Read Expert\", message=\"Does he have Rust listed as a skill?\")",
      "handle_ai_chat_request(role=\"Database Write Expert\", message=\"Add Rust as a skill to his most recent experience\")"]
     v
run_orchestrator_plan() executes them IN ORDER:
     v
  Step 1: Database Read Expert
     generates: SELECT 1 FROM skills WHERE name = 'Rust' LIMIT 1;
     returns: [] (empty -- he doesn't have it yet)
     v
  Step 2: Database Write Expert
     generates code that checks again, finds nothing, inserts a row,
     sets outcome = "New Rust added to the skills table."
     v
Orchestrator's synthesis call sees both steps' results, reuses the Write
Expert's outcome message verbatim
     v
Chat panel shows: "New Rust added to the skills table."
     v
Browser refreshes the resume panel -- Rust now appears as a skill
```

Ask the exact same question again afterward, and Step 2's Write Expert code finds the existing row this time, sets `outcome = "Element already exists in the skills table."`, and nothing gets inserted twice.

**Example 4 — a content question ("What is this page about?")**

```
User message
     v
Orchestrator generates a 1-step plan naming the Content Expert
     v
handle_ai_chat_request() sees role == "Content Expert" and appends
db.getResumeText() to the background_context BEFORE building the prompt
     v
Content Expert answers directly from that resume text -- no SQL, no exec(),
just a normal LLM response
     v
Orchestrator's synthesis call passes it through (nothing to reuse or fix up)
     v
Chat panel shows a plain-language summary of the resume
```

No database query happens anywhere in this one — it's the only expert whose answer never touches `db.query()` or `exec()`.

---



## Project File Map

You're extending the Homework 0 codebase, not starting over. Copy your working `homework 0/flask_app` and `app.py` into a new `homework 1/` folder in your fork, then make these changes:

```
homework 1/
├── app.py                              ← unchanged, copy as-is
│
└── flask_app/
    ├── __init__.py                     ← MODIFY: attach db to the app instance (Step 1)
    ├── routes.py                       ← MODIFY: read db via current_app (Step 1)
    │
    ├── utils/
    │   ├── llm.py                      ← MODIFY: add the template + all four experts
    │   ├── socket_events.py            ← MODIFY: read db via current_app + route chat through the Orchestrator
    │   └── database.py                 ← MODIFY: add getLLMRoles() and insertRows()
    │
    ├── templates/
    │   └── resume.html                 ← MODIFY: refresh resume panel after AI replies
    │
    └── database/
        ├── create_tables/
        │   └── llm_roles.sql           ← NEW: schema for the four expert configs
        └── initial_data/
            └── llm_roles.csv           ← NEW: the four experts' actual configs
```

No changes to `requirements.txt` — everything below uses the Python standard library (`re`) plus `jinja2`, which is already installed as a Flask dependency (it's what renders your HTML templates).

---



## Building It



### Step 0: Clean up how `db` is shared and change the model usage

This isn't required for the multi-expert system to work — skip it if you want to get straight to Step 1. But Homework 0 shares the database connection with `routes.py`/`socket_events.py` in a slightly awkward way: both files declare `db = None` at the top and rely on `create_app()` reaching into the module afterward (`routes.db = db`) to fill it in. It works, but it's easy to find confusing — nothing about reading `db = None` in the file tells you it becomes a real object later.

The more idiomatic Flask fix: attach `db` to the Flask **app instance** itself, and read it back via `current_app` (Flask's proxy for "the app handling the current request") instead of a bare module variable.

In `flask_app/__init__.py`, replace the `routes.db = db` / `socket_events.db = db` lines with one line, set right after `db.createTables(purge=True)`:

```python
app.db = db
```

In `flask_app/routes.py`, delete the `db = None` line, and change `resume()`'s body from `resume_data = db.getResumeData()` to `resume_data = app.db.getResumeData()` — this file already imports `current_app as app` for the `@app.route(...)` decorator, so `app.db` is just reusing that.

In `flask_app/utils/socket_events.py`, delete the `db = None` line, add `from flask import current_app` at the top, and inside `handle_message()`, grab it locally before using it:

```python
db = current_app.db
ai_response = handle_ai_chat_request(db, role="Orchestrator", message=user_message)
```

(Flask-SocketIO runs event handlers inside an app context automatically, so `current_app` works here too, not just in HTTP routes.)

In `flask_app/utils/llm.py` change the model defaul to DEFAULT_MODEL = "openai/gpt-4o-mini".

### Step 1: The master prompt template

Every expert's system prompt is built from one shared template with placeholders. Add this near the top of `flask_app/utils/llm.py`, right below `DEFAULT_MODEL`:

```python
from jinja2 import Template

# One shared template for every expert's system prompt. Each expert just
# fills in different values for role/domain/instructions/context/examples.
#
# We use Jinja2 here (not manual string replacement) because it's already a
# Flask dependency — it's the exact same {{ }} / {% if %} syntax you've been
# reading in resume.html, just rendering a prompt string instead of a page.
MASTER_TEMPLATE = Template("""\
You are a {{ role }}, an expert in {{ domain }}.

{{ specific_instructions }}
{% if background_context %}
Context:
{{ background_context }}
{% endif %}
{% if few_shot_examples %}
Examples:
{{ few_shot_examples }}
{% endif %}
Request: {{ request }}
""", trim_blocks=True, lstrip_blocks=True)


def fill_template(role, domain, specific_instructions, request,
                   background_context="", few_shot_examples=""):
    """
    Render MASTER_TEMPLATE into one expert's full system prompt.

    background_context and few_shot_examples are optional: the {% if %}
    blocks above drop the whole section — header included — when the
    argument is empty, instead of leaving a dangling "Context:" with
    nothing underneath it.
    """
    return MASTER_TEMPLATE.render(
        role=role,
        domain=domain,
        specific_instructions=specific_instructions,
        background_context=background_context,
        few_shot_examples=few_shot_examples,
        request=request,
    ).strip()
```

**Try it in isolation before moving on** — add a temporary line at the bottom of `llm.py` like `print(fill_template("Tester", "testing", "Say hi.", "Hello?"))`, run `python -c "from flask_app.utils.llm import *"` from the `homework 1` folder, and confirm you get a clean prompt with no leftover `{{ }}` or blank "Context:" lines. Remove the test line once it works.

### Step 2: Write the four expert configs

Each expert is defined by five pieces of text. Use this table as your actual content — you'll type these into a CSV in Step 3:


| Field                     | Database Read Expert                                                                                                                                                                                                                                                                                              | Database Write Expert                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Content Expert                                               | Orchestrator                                                                                                                                                                                                                                                                                         |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **domain**                | SQL query generation for a resume database                                                                                                                                                                                                                                                                        | generating Python code that modifies a resume database                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | answering questions about the resume currently on screen     | decomposing user requests into a plan of expert calls                                                                                                                                                                                                                                                |
| **specific_instructions** | Respond with a single valid SQLite `SELECT` query only. No markdown, no explanation — SQL only.                                                                                                                                                                                                                   | Respond with executable Python only, calling `db.insertRows(table, columns, values)`. First use `db.query(...)` to check whether the item already exists. End your code by assigning a variable named `outcome` to the **exact message to show the user**: `"New <element> added to the <table> table."` if you inserted a row, or `"Element already exists in the <table> table."` if you found it already there and skipped the insert — filling in `<element>` and `<table>` with the real values you used. No markdown, no explanation.                                                        | Answer using only the resume content given below as context. | Respond with a Python list of strings, each an exact call in the form `handle_ai_chat_request(role="<Expert Name>", message="<message>")`. Order matters — later calls can depend on earlier results. Only use these role names: Database Read Expert, Database Write Expert, Content Expert.        |
| **background_context**    | Schema: institutions(inst_id, type, name, department, address, city, state, zip); positions(position_id, inst_id, title, responsibilities, start_date, end_date); experiences(experience_id, position_id, name, description, hyperlink, start_date, end_date); skills(skill_id, experience_id, name, skill_level) | Same schema as the Read Expert, plus: db.insertRows(table, columns, values) inserts one row. A value may be a nested (SELECT ...) string to look up a foreign key by name, e.g. (SELECT experience_id FROM experiences WHERE name = 'MSU Research'). `db.query(sql)` **returns a LIST OF DICTS**, e.g. `[{'experience_id': 5}, {'experience_id': 9}]` — never a list of tuples. To loop over IDs from a query: `for row in db.query(sql): experience_id = row['experience_id']`. **This code runs as real Python, not SQL** — for a missing/unknown value use Python's `None`, never SQL's `NULL`. | *(leave blank — see note below)*                             | Available experts: Database Read Expert (answers questions from the DB), Database Write Expert (modifies the DB), Content Expert (answers from the currently visible resume content).                                                                                                                |
| **few_shot_examples**     | Q: How long did they work at MSU? -> SELECT p.start_date, p.end_date FROM positions p JOIN institutions i ON p.inst_id = i.inst_id WHERE i.name = 'MSU';                                                                                                                                                          | Request: Add Python as a skill to his MSU research experience -> `existing = db.query("SELECT * FROM skills WHERE name = 'Python' AND experience_id = (SELECT experience_id FROM experiences WHERE name = 'MSU Research')")` then `if existing: outcome = "Element already exists in the skills table."` else `db.insertRows('skills', ['experience_id', 'name', 'skill_level'], ["(SELECT experience_id FROM experiences WHERE name = 'MSU Research')", 'Python', 5]); outcome = "New Python added to the skills table."`                                                                         | *(leave blank)*                                              | Request: Does he know React? If not, add it to his most recent experience. -> ["handle_ai_chat_request(role=Database Read Expert, message=Does he have React listed as a skill?)", "handle_ai_chat_request(role=Database Write Expert, message=Add React as a skill to his most recent experience)"] |


**Why does** `outcome` **hold the full message instead of a short status like** `'inserted'`**?** Only the generated code actually knows which table and value it touched. If `outcome` were just a bare status, a later step would have to *guess* the table name from the user's wording to build the final message — and in testing, that guess was sometimes wrong (e.g. "added to the experience table" instead of "skills table"), or even left the literal `<table>` placeholder unfilled. Having the Write Expert build its own accurate message avoids that entirely.

**Why is the Content Expert's context blank?** Homework 0's stack has no page-scraping (no BeautifulSoup, no Vue) — so instead of parsing HTML off the page, "current page content" is just defined as the resume data already available server-side via `db.getResumeText()` (you built this in Homework 0). That gets added in automatically at request time, not stored in the config — see Step 4.

### Step 3: Create the `llm_roles` table

Create `flask_app/database/create_tables/llm_roles.sql`:

```sql
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
```

Create `flask_app/database/initial_data/llm_roles.csv` with header row `role_id,role,domain,specific_instructions,background_context,few_shot_examples`, then one row per expert using the content from the Step 2 table. Two practical tips that will save you debugging time:

- **Keep every field on a single line** — write instructions/examples as one continuous line (use spaces instead of line breaks) rather than a real multi-line cell. This CSV loader wasn't built to handle embedded newlines inside a field, and single-line text avoids the issue entirely.
- Any field containing a comma **must** be wrapped in double quotes (standard CSV rule) — editing the file in a spreadsheet program (Excel, Google Sheets, then exporting as CSV) handles this for you automatically.

Then, in `flask_app/utils/database.py`, add `'llm_roles'` to the `TABLE_ORDER` list near the top of the file (same mechanism that already creates and seeds `institutions`, `positions`, `experiences`, and `skills` — no other changes needed for it to be auto-created on startup).

**One more required fix to** `database.py`**'s existing** `query()` **method.** The schema files already declare `FOREIGN KEY` constraints (e.g. `skills.experience_id -> experiences.experience_id`), but SQLite does not enforce them unless a connection explicitly turns that on — and Homework 0's `query()` never did, because it never needed to (it only ever read). That's about to matter: if the Write Expert's generated code ever inserts a bad `experience_id` (a realistic mistake — see "Known Limitations" below), an unenforced foreign key means the bad row gets inserted silently instead of raising an error you can catch. Add this one line right after `connection = sqlite3.connect(self.db_path)` in `query()`:

```python
connection.execute("PRAGMA foreign_keys = ON")
```

Add this method to the `database` class, near `getResumeText()`:

```python
def getLLMRoles(self):
    """
    Return every row of llm_roles as a dict keyed by role name, e.g.
        {"Database Read Expert": {"role": ..., "domain": ..., ...}, ...}
    This is what each expert's config gets looked up from in llm.py.
    """
    rows = self.query("SELECT * FROM llm_roles")
    return {row['role']: row for row in rows}
```

Also add `insertRows` — Homework 0 was read-only, so this doesn't exist yet:

```python
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
```

Restart the app once and check the startup log — you should see `Loaded data for table: llm_roles` alongside the existing four tables.

### Step 4: Route requests to each expert

This is the core of `llm.py`. Add `handle_ai_chat_request` — this is the one function everything else calls into:

```python
def handle_ai_chat_request(db, role, message):
    """
    Route a chat message to the named expert. role=None keeps Homework 0's
    original single-prompt behavior as a fallback, so nothing about the
    basic chat flow breaks while you're building this out.
    """
    if role is None:
        return send_message(message)

    config = db.getLLMRoles()[role]
    background_context = config['background_context'] or ""
    if role == "Content Expert":
        # No page-scraping in this stack -- "current page content" is the
        # resume data itself, fetched fresh on every request.
        background_context += "\n" + db.getResumeText()

    system_prompt = fill_template(
        role=config['role'],
        domain=config['domain'],
        specific_instructions=config['specific_instructions'],
        background_context=background_context,
        few_shot_examples=config['few_shot_examples'] or "",
        request=message,
    )
    output = send_message(message, system_prompt).strip()
    print(f"[{role}] generated:\n{output}\n")   # the rubric checks this output

    if role == "Database Read Expert":
        return execute_read_query(db, output)
    if role == "Database Write Expert":
        return execute_write_action(db, output)
    if role == "Orchestrator":
        return run_orchestrator_plan(db, message, output)
    return output   # Content Expert -- output is already the final answer
```

Now add the three helper functions it calls:

```python
def execute_read_query(db, sql):
    """
    Run the Database Read Expert's generated SQL. We refuse anything that
    isn't a SELECT -- this expert is read-only by design, so there's never
    a legitimate reason to run anything else, even if a user's message
    somehow tricks the model into generating something else.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Sorry, I couldn't safely answer that question."
    try:
        return str(db.query(sql))
    except Exception as error:
        print(f"Read Expert query failed: {error}")
        return "Sorry, that question couldn't be answered."


def execute_write_action(db, generated_code):
    """
    Run the Database Write Expert's generated Python. This genuinely
    executes model-generated code with exec() -- see "Questions to Think
    About" below for why that's worth pausing on. `db` is the only thing
    exposed to it.

    `outcome` is how the generated code reports back what happened -- it's
    already the full, exact message to show the user (see Step 2), not a
    bare status, because only the generated code knows which table/element
    it actually touched.

    NULL=None is a compatibility shim: the model sometimes writes SQL's
    NULL instead of Python's None for a missing value. Python has no NULL,
    so without this, that one habit would crash otherwise-correct code
    with a NameError.
    """
    local_vars = {}
    try:
        exec(generated_code, {"db": db, "NULL": None}, local_vars)
    except Exception as error:
        print(f"Write Expert code failed: {error}")
        return "Operation was unsuccessful."
    return local_vars.get("outcome", "Operation was unsuccessful.")


def run_orchestrator_plan(db, original_request, plan_text):
    """
    Parse the Orchestrator's plan (a Python list of call strings), run each
    expert call in order, then make one final call to turn the raw results
    into a single clean reply for the chat UI.
    """
    try:
        call_strings = eval(plan_text)   # the Orchestrator's own list literal
    except Exception:
        print(f"Orchestrator returned an unparseable plan: {plan_text}")
        return "Sorry, I couldn't plan a response to that."

    results = []
    for call_string in call_strings:
        print(f"[Orchestrator] executing: {call_string}")
        match = re.search(r'role="([^"]*)",\s*message="([^"]*)"', call_string)
        role, message = match.group(1), match.group(2)
        response = handle_ai_chat_request(db, role, message)
        results.append((role, message, response))

    steps_summary = "\n".join(f"{r}: {resp}" for r, m, resp in results)
    synthesis_prompt = (
        f'The user asked: "{original_request}"\n\n'
        f"Here is what each expert found or did:\n{steps_summary}\n\n"
        "Write ONE short, clear reply. A Database Write Expert step's result "
        "is already the exact message to show the user (e.g. 'New Python "
        "added to the skills table.') -- if one is present, reuse it "
        "verbatim rather than rephrasing it. Otherwise, summarize the "
        "other results in plain language. Never mention SQL, Python, code, "
        "or these internal steps."
    )
    return send_message(original_request, synthesis_prompt)
```

Add `import re` at the top of `llm.py` alongside the existing imports (needed by `run_orchestrator_plan` above).

**A note on what this code is actually doing:** `eval(plan_text)` and `exec(generated_code, ...)` both run model-generated text as real Python. This matches how the assignment is designed — the Orchestrator and Write Expert genuinely produce code that gets executed, not just data that gets displayed. It's worth sitting with that for a second before moving on; "Questions to Think About" #4 comes back to it.

### Step 5: Wire the Orchestrator into chat

In `flask_app/utils/socket_events.py`, find the existing `@socketio.on('send_message')` handler — this stack is WebSocket-only (no separate `/chat/ai` HTTP route), so this is the one place chat logic lives. Replace the body that calls `build_resume_system_prompt` + `send_message` with:

```python
@socketio.on('send_message')
def handle_message(data):
    user_message = data.get('message', '').strip()
    if not user_message:
        return
    try:
        ai_response = handle_ai_chat_request(db, role="Orchestrator", message=user_message)
    except Exception as error:
        print(f"LLM error: {error}")
        ai_response = "Sorry, something went wrong answering that."
    emit('receive_message', {'response': ai_response})
```

Update the import at the top of the file from `from flask_app.utils.llm import send_message` to `from flask_app.utils.llm import handle_ai_chat_request`. `build_resume_system_prompt` is no longer called from here — its job is now split between the `llm_roles` table (static schema/domain context) and the Content Expert's dynamic `db.getResumeText()` lookup, so you can delete it or leave it in place, your call.

### Step 6: Refresh the resume panel after AI replies

Right now, a successful database write happens on the server but the resume panel on screen doesn't know about it. In `flask_app/templates/resume.html`, find the existing `socket.on('receive_message', ...)` handler near the bottom of the `<script>` block and add a refresh call:

```javascript
async function refreshResumeContent() {
  // Re-fetch /resume and swap in just the resume content, so DB writes
  // made by the AI show up immediately without wiping the chat log.
  const html = await (await fetch('/resume')).text();
  const newContent = new DOMParser().parseFromString(html, 'text/html').querySelector('.resume-content');
  if (newContent) document.querySelector('.resume-content').innerHTML = newContent.innerHTML;
}

socket.on('receive_message', function(data) {
  removeTypingIndicator();
  displayMessage('AI', data.response);
  refreshResumeContent();   // <-- new line
});
```

This reuses your existing `/resume` route unchanged — no new API endpoint needed.

### Step 7: Test it end to end

Work through these four prompts in order — each one exercises a different part of what you just built:


| Test input                                              | Expert(s) invoked                         | What you should see                                                                                                                        |
| ------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| "How long did they work at [institution]?"              | Database Read Expert                      | Console prints a `SELECT` query; chat reply states an accurate duration                                                                    |
| "Add '[skill]' as a skill to [experience]"              | Database Write Expert                     | Console prints generated Python; the skill appears on the resume page right after the reply, and is still there after a manual page reload |
| "Does he know [skill]? If not, add it to [experience]." | Orchestrator → Read Expert → Write Expert | Console prints an ordered plan naming both experts; both actually run, in that order                                                       |
| "What is this page about?"                              | Content Expert                            | Answer grounded in the resume text; no SQL/DB query involved                                                                               |


If a step fails, the console output (the `print()` lines you added in Step 4) is your first debugging tool — it shows you exactly what the model generated before it was executed.

> **Watch your API usage while testing.** Homework 0 made one model call per chat message. Homework 1's Orchestrator makes *several* — one to plan, one per expert it calls, one to synthesize — so a single compound question can cost 3-5x what Homework 0 did. OpenRouter's free tier caps requests **per day, per account, shared across every** `:free` **model** — switching `DEFAULT_MODEL` to a different free model does not reset or bypass this cap. If `send_message` starts returning `⚠️ OpenRouter error: Rate limit exceeded: free-models-per-day`, that's what's happening; 

---



## Known Limitations

This design was built and tested against a real model before being written up. Three real bugs turned up during that testing and are already fixed in the steps above — they're documented here so you understand *why* the code looks the way it does, not because you need to fix them again:

- **Write outcomes used to be ungrounded.** An earlier version had `outcome` hold a bare status like `'inserted'`, and asked the synthesis step to guess the table name from the user's phrasing to build the final message. In testing, that guess was sometimes wrong ("added to the *experience* table" instead of *skills*), and once left the literal `<table>` placeholder unfilled in the reply the user would have seen. Fixed by having the Write Expert's own code produce the complete, accurate message (Step 2) — it's the only thing that actually knows what it wrote.
- **Foreign keys weren't enforced.** SQLite ignores `FOREIGN KEY` declarations unless a connection turns that on. Without the `PRAGMA foreign_keys = ON` fix in Step 3, a Write Expert bug (e.g. looping over `db.query()` results as if they were tuples instead of dicts — an easy mistake, since that's a common pattern with other SQL libraries) silently inserted a row with a garbage `experience_id` while still reporting success. With the fix, the same bug now raises a catchable error instead of corrupting data quietly.
- `NULL` **vs** `None`**.** The Write Expert's generated code is fluent in SQL, where `NULL` is normal — and occasionally reaches for `NULL` instead of Python's `None` for a missing value, which crashes with `NameError: name 'NULL' is not defined` since this code runs as real Python, not SQL. Fixed two ways: the Write Expert's `background_context` now explicitly says to use `None`, and `execute_write_action` binds `NULL = None` in the `exec()` globals as a compatibility shim, so even if the model slips up again, the code still runs.

A few more things you should expect, not fix — they're inherent to this design, not bugs in it:

- **Exact-name matching, not semantic understanding.** The Read Expert generates literal SQL like `WHERE name = 'Michigan State University'`. If a user says "MSU" but the database stores the full name (or vice versa), the query returns nothing — the AI doesn't "know" they're the same institution unless the exact string matches. (Teaching resolving *paraphrased* references like this is what a later homework in this course builds toward, once you have vector embeddings — nothing to do here.)
- **The call-string parser is fragile in one specific way.** `run_orchestrator_plan`'s regex assumes a call string's `message="..."` value contains no literal `"` character. If it does, the regex silently matches a *truncated* message instead of failing — e.g. a message containing `He said "hi"` gets cut off right before the embedded quote. This is rare in practice (short, specific expert instructions rarely produce embedded quotes) but worth knowing about if an Orchestrator step ever behaves as if it only got half of what you asked.
- **"Reuse verbatim" isn't always obeyed.** The synthesis prompt tells the model to reuse a Write Expert's exact outcome message rather than rephrasing it. Most of the time it does. Occasionally it paraphrases anyway (e.g. "Yes, he already knows Rust." instead of "Element already exists in the skills table."). This is a general property of LLM instruction-following, not something more/better instructions can fully eliminate — free-tier models in particular are less consistent about this than larger ones.

---



## Questions to Think About

You don't need to submit answers, but you'll be asked about these:

1. **Prompt templates as reusable configs.** What would it take to add a fifth expert — say, a "Skills Coach" that suggests skills to add — with zero changes to `llm.py`?
2. **Why decompose at all?** Why does the Orchestrator break a compound request into ordered steps instead of one prompt trying to do everything at once?
3. **What changed from Homework 0?** What's gained, and what's lost, going from one system prompt to four coordinated experts?
4. `eval()` **and** `exec()` **on model output.** The Orchestrator's plan and the Write Expert's code are both executed directly. What could a strange, confused, or deliberately adversarial user message cause the model to generate — and what would actually happen if that ran? What would you change here if this were a production system instead of a classroom exercise?
5. **Few-shot examples matter.** Edit one of the examples in your `llm_roles` data and see how the generated SQL/code/plans change. What does that tell you about how much of an LLM's behavior comes from its instructions versus its examples?
6. **From lecture, what prompt engineering techniques could you use?** How would you apply them to this multi-expert system?

---



## Submitting

Push your work to your fork:

```bash
cd "homework 1"
git add .
git commit -m "Homework 1"
git push origin [BranchName]
```

Then record a short demo video (see `documentation/rubric.md` for exactly what to show and how it's graded), and submit **both** of the following via the course submission form:

1. Your demo video
2. Your fork's GitHub URL (e.g. `https://github.com/YOUR-USERNAME/ai-agents`) **OR** the URL of your Pull Request (PR) on your team lead's repository. So the grader can view your code

