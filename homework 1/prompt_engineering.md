### Prompt Engineering Concepts

Prompt Engineering Concepts

In Homework 1, I used three prompt engineering techniques while working with the AI experts.

1. Role Prompting

Role Prompting means giving the AI a specific role and responsibility.

I used it with the Database Read Expert and Database Write Expert. The Read Expert generates SQL queries, while the Write Expert updates the database.

Effectiveness: This helped each expert focus on its task. During testing, the Read Expert generated SQL queries to retrieve information from the database.

2. One-Shot Prompting

One-Shot Prompting means providing one example to guide the AI's response.

I used this technique in the "few_shot_examples" column of "llm_roles.csv", where I provided a sample question and its expected SQL query.

Effectiveness: During testing, the Read Expert returned SQL queries in the expected format. However, I did not compare the results without the example, so I cannot measure its exact effect.

3. Task Decomposition

Task Decomposition means breaking a complex request into smaller steps.

I used this with the Orchestrator when asking it to check whether Docker was already a skill and add it if missing.

The Orchestrator divided the request into two steps: Database Read first, then Database Write.

Effectiveness: This helped coordinate the two experts. During testing, Docker was added to the resume.

Conclusion

Role Prompting helped the experts focus on their responsibilities, One-Shot Prompting guided the response format, and Task Decomposition helped the experts work together.