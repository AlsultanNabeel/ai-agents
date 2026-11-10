***what happens to an embedding when its record is edited or deleted***



1. when a record is deleted remove its embedding immediately, on startup also removes any leftover embeddings of records that no longer exist.
Why: Search results always point to records and an embedding survival after its record deletion would return a “match” for something that no longer exists.
2. when a record is edited re-embed only if the text that was embedded has changed, which means when the record’s current text differs from the stored text, the embedding is replaced, and When it’s identical, nothing happens, so no API call and no cost.
Why: Because comparing texts catches every kind of edit
3. IF re-embedding fails remove the Old embedding and report the failure instantly. Don’t keep the old one.
Why: the old vector describes the old text. Keeping it would return the record for the wrong meaning and look like a valid embedding, which is exactly what the assignment says must not happen.





***Search by meaning, Which tables to search, and What counts as “no match”***



1. Which tables to search

Recommended option: search only the skills table when the question is about skills, and all tables otherwise.

Why:

A skill is stored as a short text, while experiences and positions have long descriptions that mention many topics. Long texts tend to score decently against many queries, so on all tables they can crowd out the skill records the user asked about.
A question about skills expects skill records, and the answer is built from what was retrieved. Returning an experience description in place of a skill makes the answer less precise.

For questions that aren’t about skills (“city planning”, an abbreviation for an institution), the answer could be in any table, so all tables are searched.

Who decides “about skills”: in Step 4 the Orchestrator will choose the table when it builds the search step. Step 3 only needs search to accept the tables argument.



2\. What counts as “no match”

A fixed cut-off, SEARCH\_MIN\_SCORE, chosen from measured scores. Take the gap between the worst score of a query that should match and the best score of one that shouldn’t. Set the cut-off in the middle of that gap, or slightly above the middle.

Why:

A too-low cut-off returns weakly related records for questions that have no answer, such as “Harvard”. The agent would then build an answer from them, which is worse than saying “not found”.

A too-high cut-off makes real matches disappear. That failure is milder, because the agent says it couldn’t find something and the user can rephrase.





***Choose the right search, and handle two-step requests***



How the design works:

Exact questions: counts, “list all”, and dates go to the Database Read Expert, which writes SQL.
Fuzzy questions: abbreviations, names, categories and topics go to one of two search experts. Both call embeddings.search with the SEARCH\_MIN\_SCORE cut-off:
Skill Search Expert: searches only the skills table.
Semantic Search Expert: searches every table.

