# CSE 491 — AI Agents: Homework 2 Rubric

This assignment is graded on a 100 point scale, plus an optional bonus of up to 10 points. Grading is based on your demo video, your test command, your code and your `DESIGN_AND_TESTING.md`. Scenario IDs (S1–S11, R1–R3) refer to the README.

## Functional Requirements (75 points)

| # | Requirement | Points | How to demonstrate |
|---|-------------|--------|--------------------|
| 1 | **Search by meaning**: abbreviation and category questions | 12 | S1 and S2: the right records come back ranked, with their scores visible in the trace |
| 2 | **Data survives a restart**, and new records get embeddings | 8 | S5: add a skill, restart, show the skill and its embedding are still there and that a search by meaning finds it |
| 3 | **Honest failures** | 5 | S10 (embedding call fails) and S11 (nothing matches): a clear message, no invented answer, the app keeps working |
| 4 | **Picks the right kind of search** | 10 | S3 goes to the Database Read Expert; S1/S2 use search by meaning; the trace shows the reason each time |
| 5 | **Two dependent steps** | 7 | S4: the second step uses what the first step found, both visible in the trace |
| 6 | **Answers come from retrieved data** | 3 | Replies match what was actually retrieved; "not found" when nothing matched |
| 7 | **Pauses before a destructive change** and keeps the exact action | 6 | S6 and S7: the exact action is shown before anything runs |
| 8 | **Handles yes / no / unclear / change of subject** | 6 | S6–S8 with the database shown before and after |
| 9 | **The check can't be skipped** | 8 | S9 is paused; in your code, deletions only run through your allowed operations, the approval check sits where the write happens, and no model output goes to `eval()` or `exec()` |
| 10 | **Runs from a fresh copy and is easy to test** | 10 | README setup steps, `.env.example` and how to reset the test data (3); one command that runs the scenarios and prints PASS/FAIL, including at least one failure scenario (5); no secrets in the repo, and the app still works after a failed operation (2) |

## Design and Testing Report (25 points)

| # | Requirement | Points | What we look for |
|---|-------------|--------|------------------|
| 11 | **Architecture and decisions** | 10 | An accurate diagram and what changed from HW1 (4); three real decisions with the options, the trade-off and what would change your mind (6) |
| 12 | **Test analysis** | 10 | At least five scenarios with what you expected, what happened and the evidence, including at least one failure, and an explanation of anything that didn't work |
| 13 | **Limitations and your own work** | 5 | Two specific limitations with improvements (3); what you wrote yourself and what help you used (2) |

## Bonus: ReAct Orchestration (up to +10)

| # | Requirement | Points | How to demonstrate |
|---|-------------|--------|--------------------|
| B1 | **Thought → Action → Observation loop** with a round limit | 4 | Every round's Thought, Action and Observation visible in the trace |
| B2 | **Next step chosen from what was observed** | 3 | R1 |
| B3 | **Stops honestly and stays safe** | 3 | R2 stops with "not found"; R3 still waits for `yes` |

The bonus is real extra credit: it is added on top of your score, so HW2 can reach 110. It only counts if the safety rules in requirement 9 still hold inside your loop.

## Grading Policy

- **Partial credit is possible** for every requirement. This is different from HW0 and HW1: a requirement that mostly works earns part of its points.
- We grade **what your agent does and how well you explain it**, not one particular design. A separate Semantic Search Expert and an extended Read Expert are equally valid.
- A confirmation message in the chat alone does not earn the safety points (requirements 7–9) if the deletion could still run without approval.
- Even if your app works, a requirement that can't be seen in your video, your test output or your code can't earn points.
- **Live check:** after the deadline you'll run your app live for about 5–7 minutes with new wording and answer one or two questions about your choices. It doesn't add points; it confirms them. If something that worked in your video doesn't work live, that requirement is re-graded from what we see. If you can't explain a decision from your report, you may lose the points for that decision.
- Suspected academic-integrity issues follow the course policy.

## Demo Video Structure

- State your full name at the start
- Say: *"I will now demonstrate the functional requirements for CSE 491 Homework 2"*
- Announce each requirement before demonstrating it
- Keep the terminal (your trace) visible while you demonstrate
- Show S1, S2, S3 or S4, S6 (`no`), S7 (`yes`), S8, S9 and one failure scenario (S10 or S11), plus R1–R3 if you did the bonus
- Show the database or the resume page before and after the deletion scenarios
- Aim for under 8 minutes; clear audio and video required

## Submission Checklist

- [ ] Data and embeddings survive a restart; there's a documented way to reset the test data
- [ ] Search by meaning returns ranked results with table, ID, text and score
- [ ] The Orchestrator's plan is read as data; no model output goes to `eval()` or `exec()`
- [ ] Deletions only run through your allowed operations, after a `yes` that matches the action shown
- [ ] Every message produces a trace (route and reason, steps, approval state, outcome)
- [ ] One test command runs S1–S11 and prints PASS/FAIL
- [ ] `.env.example` lists every setting (names only); no `.env` or keys committed
- [ ] `DESIGN_AND_TESTING.md` completed
- [ ] Code pushed to your fork: `git push origin main`
- [ ] Fork URL and demo video submitted via the homework submission form
