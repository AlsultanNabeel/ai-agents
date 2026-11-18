# Design and Testing Report — Homework [2]

**Name:** Zaina Al Najjar
**GitHub fork/branch URL:** To be added after pushing Homework 2
**Demo video link:** To be added after recording
**Command that runs my tests:** To be confirmed after creating the tests

> Keep it short and specific. A few clear sentences about *your* system are worth more than long general explanations.

## 0. Starting point

- **HW2:** Did your HW1 pass the "Before You Start" checks (works, restart test, where `eval()`/`exec()` were, embedding test)? What did you have to fix first?

## 1. How my system works

Add a simple diagram (Mermaid, a drawing exported as an image, or a photo of a clear sketch). Show the experts/agents, the database tables, where the approval check happens (HW2).

Then explain each main part in one or two sentences, and say **what changed from the previous homework**.

## 2. Where to find things in my code


| What                                               | File / function / table |
| -------------------------------------------------- | ----------------------- |
| Search by meaning (returns table, ID, text, score) |                         |
| Trace output                                       |                         |
| Test command                                       |                         |
| Settings (`.env.example`)                          |                         |
| Approval check and allowed operations (HW2)        |                         |




## 3. Three decisions I made

Fill this in for **at least three** real choices. "Because it was easier" is not enough. Say what you gained and what you gave up.


| Decision | Options I considered | What I chose | Why, and the trade-off | What would make me choose differently |
| -------- | -------------------- | ------------ | ---------------------- | ------------------------------------- |
| 1        |                      |              |                        |                                       |
| 2        |                      |              |                        |                                       |
| 3        |                      |              |                        |                                       |


Ideas for HW2: separate Semantic Search Expert vs. extending the Read Expert; what text you embed; when embeddings are updated; how startup keeps data; exact vs. search by meaning; which tables a search covers and how you chose the cut-off score; how `yes` is matched to the action; your allowed operations. If you did the bonus: ReAct vs. planning up front, and your round limit.

## 4. Testing

Use the scenario IDs from the README: **S1–S11** (plus **R1–R3** if you did the bonus) for HW2. Analyze at least **5** including at least one failure scenario.


| Scenario / what I typed | What should happen | What actually happened | Pass / fail | Evidence (test output, screenshot, log) |
| ----------------------- | ------------------ | ---------------------- | ----------- | --------------------------------------- |
|                         |                    |                        |             |                                         |
|                         |                    |                        |             |                                         |
|                         |                    |                        |             |                                         |
|                         |                    |                        |             |                                         |
|                         |                    |                        |             |                                         |
|                         |                    |                        |             |                                         |


Describe anything that surprised you: how you found the cause, and whether you fixed it. If something still fails, say what the impact is. Don't hide it.


## 5. Limitations

1. **Limitation:** Semantic search currently uses simple keyword-based routing for some questions.
   **Impact:** Unusual wording may be routed to SQL instead of semantic search.
   **How I'd improve it:** Use a more flexible Orchestrator that selects the appropriate search method based on user intent.

2. **Limitation:** The approval system currently supports deleting one specifically named skill, but not every possible destructive operation.
   **Impact:** Bulk deletion and record overwriting are not fully implemented.
   **How I'd improve it:** Introduce a unified approval mechanism for all destructive database actions and verify the exact pending operation before execution.

## 6. My work and the help I used

I extended the starter AI Resume Agent by adding embedding storage, semantic search, cosine similarity, search routing, and confirmation handling for database changes.

I reused the Flask application, SQLite database structure, and existing AI experts from the starter project. I used ChatGPT for guidance, code suggestions, and debugging.

After applying changes, I tested the functions and chatbot behavior. I fixed Python indentation errors and a deletion cancellation bug discovered during testing. I also used a separate SQLite test database to avoid modifying my original resume during deletion tests.

## 7. How to run it

1. Open the Homework 2 folder in a terminal.
2. Activate the Python virtual environment.
3. Install the dependencies from the repository's requirements.txt.
4. Configure OPENROUTER_API_KEY and EMBEDDING_MODEL in the local .env file.
5. Start the application using python app.py.
6. Open http://localhost:8080/resume.

For safe testing, use a separate SQLite database selected with RESUME_DB_PATH. Test data can be reset by restoring a clean copy of the test database. Do not reset or delete the original resume.db.
