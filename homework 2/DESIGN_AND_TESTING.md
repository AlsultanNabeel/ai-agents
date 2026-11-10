# Design and Testing Report — Homework 2

**Name:** Dima  
**GitHub fork/branch URL:** [HM2/dima](https://github.com/AlsultanNabeel/ai-agents/tree/HM2/dima)  
**Demo video link:** [Watch the demo](https://drive.google.com/file/d/1Kfzttkb8RY27L6epnk4osl_WrRwvZqIL/view?usp=sharing)  
**Command that runs my tests:** `python tests/run_scenarios.py`

## 0. Starting point

HW1 provided the Flask resume application and SQLite database. HW2 extended it with persistent semantic embeddings, specialized expert routing, request tracing, and approval-controlled database writes.

**Before-start checks:** [Document the actual HW1 restart, embedding, and `eval()`/`exec()` checks you completed, including any fixes.]

## 1. How my system works

### Architecture

```mermaid
flowchart TD
    U[User] --> F[Flask + Socket.IO]
    F --> O[Orchestrator]
    O --> R[Database Read Expert]
    O --> S[Semantic Search Expert]
    R --> DB[(SQLite Database)]
    S --> E[Embedding Generation]
    E --> API[OpenRouter Embeddings API]
    E --> DB
    DB --> T[Trace Output]
    O --> T
    O --> P[Pending Approval]
    P --> A{User approval?}
    A -->|No| C[Cancel]
    A -->|Unclear| W[Wait for clarification]
    A -->|Yes| G[Approval Grant]
    G --> D[Database Write Boundary]
    D --> DB

    subgraph Database Tables
        DB1[institutions]
        DB2[positions]
        DB3[experiences]
        DB4[skills]
        DB5[embeddings]
        DB6[llm_roles]
    end
```

### Main components

- **Flask and Socket.IO:** Handle the web application and real-time chat communication.
- **Orchestrator:** Interprets the request and routes it to the appropriate expert.
- **Database Read Expert:** Handles structured database questions and exact lookups.
- **Semantic Search Expert:** Searches resume information using stored embeddings and cosine similarity.
- **SQLite:** Stores resume records, expert instructions, and embeddings.
- **Approval mechanism:** Holds proposed destructive actions until the user confirms them. The database validates a one-time approval grant before executing the deletion.
- **Request tracing:** Records routing decisions, approval states, and operation outcomes.

**What changed from HW1:** HW1 provided the basic resume application and AI interaction. HW2 introduced specialized expert routing, semantic search, persistent embeddings, request tracing, and approval-controlled destructive operations.

## 2. Where to find things in my code

| What | File / function / table |
|---|---|
| Search by meaning | `flask_app/utils/embeddings.py` — `semantic_search()` |
| Cosine similarity | `flask_app/utils/embeddings.py` — `cosine_similarity()` |
| Embedding generation | `flask_app/utils/embeddings.py` — `generate_embedding()` |
| Trace output | `flask_app/utils/socket_events.py` — `log_request_trace()` |
| Test command | `tests/run_scenarios.py` |
| Settings | `.env.example` |
| Approval handling | `flask_app/utils/socket_events.py` — `handle_message()`, `handle_approve_write()` |
| Approval validation | `flask_app/utils/database.py` — `ApprovalGrant`, `build_deletion_fingerprint()` |
| Allowed deletion operations | `flask_app/utils/database.py` — `delete_skill_records()` |
| Embedding storage | SQLite `embeddings` table |
| Resume data | SQLite `institutions`, `positions`, `experiences`, and `skills` tables |

## 3. Three decisions I made

| Decision | Options I considered | What I chose | Why, and the trade-off | What would make me choose differently |
|---|---|---|---|---|
| 1. Embedding storage | External vector database, in-memory vectors, SQLite | Store embeddings in SQLite | Keeps resume records and their embeddings persistent in one database without introducing another service. The trade-off is that searching and comparing vectors in Python is less efficient at larger scales. | A much larger dataset or higher search latency would justify a dedicated vector database. |
| 2. Similarity threshold | Return all ranked results or filter by a minimum similarity score | Use a threshold of `0.40` | Prevents weak matches from being presented as relevant. The trade-off is that some valid but differently worded queries may be excluded. | A larger evaluation dataset showing frequent missed matches would justify tuning the threshold or using hybrid lexical and semantic search. |
| 3. Destructive-action approval | Execute immediately, regenerate the action after confirmation, or preserve the exact proposed action | Store the pending action and require a one-time fingerprint-matched approval grant | Ensures that confirmation applies to the exact proposed operation and skill IDs. It also prevents grant reuse. The trade-off is additional state management and approval-flow complexity. | A multi-user or multi-worker deployment would require durable, shared approval state rather than in-memory session storage. |


## 4. Testing

Testing was performed using a combination of automated checks and manual application-level scenarios.

The automated test runner uses an isolated temporary SQLite database to avoid modifying the actual resume database. Some tests use mocked embedding responses to verify application behavior deterministically without depending on external API availability.

| Scenario | What was tested | Result | Evidence |
|---|---|---|---|
| S1 — Search by meaning | Retrieved AUC institution information using the Semantic Search Expert, with a deterministic query embedding and the actual similarity calculation. | PASS | Automated test output and semantic search assertions. |
| S2 — Search by abbreviation/category | Checked that AI-related skill data exists in the database. This does not fully verify semantic retrieval or ranking. | PARTIAL | Automated test output. |
| S3 — Structured database query | Verified that exact database read queries return the expected data. Full expert-routing behavior is not covered by this automated check. | PARTIAL | Automated test output. |
| S4 — Dependent expert steps | Verified the relationships between AUC institutions, positions, and experiences through database joins. Full multi-expert orchestration is not covered by this check. | PARTIAL | Automated test output and database query results. |
| S5 — Restart persistence | Manually added a skill, approved the change, restarted the application, and verified that the skill remained available through a semantic search query. | PASS | Database records, stored embedding, and application response after restart. |
| S6 — Reject a proposed deletion | Rejected a proposed skill deletion and verified that the skill remained in the database. | PASS | Automated test output and manual application test. |
| S7 — Approve a proposed deletion | Approved a proposed deletion and verified that the exact proposed skill was deleted. The trace reported a completed operation. | PASS | Automated test output, database verification, and request trace. |
| S8 — Ambiguous reply and request invalidation | Verified that an ambiguous reply does not execute a pending operation and that a new request invalidates the previous proposal. | PASS | Automated test output and manual application test. |
| S9 — Grounded response and bulk deletion safety | Manually tested a request to delete all skills. The application presented a proposal, and rejecting it left the database unchanged. The automated check only verifies that the database remains populated. | PASS (manual); PARTIAL (automated) | Manual application response, pending-action state, and database check. |
| S10 — Embedding generation failure | Simulated an embedding API failure and verified that the error was handled and the database remained usable. | PASS | Automated test output showing the handled `EmbeddingError`. |
| S11 — API or operation failure | Manually queried for a nonexistent Harvard experience. The application returned no matching records instead of inventing an experience. The automated check verifies that no Harvard records exist in the database. | PASS (manual); PARTIAL (automated) | Application response and database check. |

### Test results

The latest automated test run reported:

- S1–S11: 11 checks passed.
- 0 automated check failures.

The test command was:

```bash
python tests/run_scenarios.py
```

The 11/11 result refers to the checks implemented in the test runner. It does not mean that every original scenario has complete automated end-to-end coverage. In particular, S2–S4 have database-level checks, while S9 and S11 have limited automated checks supplemented by manual testing.

Manual application testing was also used to verify persistence after restarting the application, approval and rejection behavior, proposal invalidation, and honest handling of missing information.

### Surprises and fixes

During testing, I found that the approval write method returned a status field, while the Socket.IO handler checked a different field to determine whether the operation succeeded. This caused the trace to report an incorrect outcome even when the database operation succeeded.

I corrected the trace condition to check `result.get("status") == "success"` and reran the test. S7 then reported the correct `completed` outcome.

## 5. Limitations

1. **Limitation:** The fixed semantic similarity threshold can exclude relevant queries. For example, a query about Python programming skills may receive a maximum score below `0.40`.
   **Impact:** Some relevant information may not be returned.
   **How I'd improve it:** Evaluate more representative queries, tune the threshold, and consider combining semantic and keyword search.

2. **Limitation:** Pending approvals are stored in an in-memory dictionary associated with a Socket.IO session.
   **Impact:** Pending proposals are not durable across application restarts and are not shared between multiple application workers.
   **How I'd improve it:** Store pending approvals in a persistent database or shared state store with expiration and session validation.

## 6. My work and the help I used

I worked on extending the existing Flask and SQLite application with semantic search, embedding persistence, expert routing, approval handling, request tracing, and scenario tests.

I used Python libraries including Flask, Flask-SocketIO, SQLite, requests, and python-dotenv, along with OpenRouter's chat and embedding APIs.

I also used documentation and AI assistance to review implementation details, troubleshoot errors, improve test coverage, and organize the design report. I checked the resulting changes against the application code and reran the relevant tests.

## 7. How to run it

### Requirements

- Python and pip
- An OpenRouter API key
- An embedding model available through OpenRouter

### Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure the following settings in `.env`:

- `OPENROUTER_API_KEY`
- `EMBEDDING_MODEL`
- `RESUME_DB_PATH` (optional; overrides the default database location)

### Run the application

```bash
python app.py
```

### Run tests

```bash
python tests/run_scenarios.py
```

The scenario runner uses an isolated temporary SQLite database so that test operations do not modify the actual resume database.

### Reset test data

The test runner creates a fresh temporary database for each run. Its temporary database is removed when the test process exits. No manual deletion of the actual resume database is required.

**Important:** Do not delete `flask_app/database/resume.db` to reset tests. That is the application's resume database, not the isolated test database.