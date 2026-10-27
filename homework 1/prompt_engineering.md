### Prompt Engineering Concepts

Prompt Engineering Concepts

In Homework 1, I worked with four AI agents: Database Read Expert, Database Write Expert, Content Expert, and Orchestrator.

I used different prompting techniques to help each agent understand its task and give a better response. Here are three techniques I used and what I noticed while testing them.

1. Role Prompting

Role prompting means giving the AI a specific role so it knows what kind of task it should do.

I used this technique by giving each agent a different job. For example, the Database Read Expert was responsible for generating SQL queries, while the Database Write Expert was responsible for updating the resume database.

I also gave each agent instructions about how to respond. The Read Expert had to return SQL only, without extra explanations.

Effectiveness: This helped the agents focus on their own tasks instead of trying to do everything. During testing, the Read Expert generated a SQL query to check whether Rust was already listed as a skill.

2. One-Shot Prompting

One-shot prompting means giving the AI one example to show it how to complete a task.

I used this technique in the "few_shot_examples" column of the "llm_roles.csv" file.

For example, I gave the Database Read Expert a sample question about work experience at MSU, along with the SQL query that answers it.

This example showed the agent the type of output I expected.

Effectiveness: The example helped explain the required response format. During testing, the Read Expert returned SQL queries instead of normal text. However, I did not compare the results with and without the example, so I cannot say exactly how much it improved the performance.

3. Decomposition

Decomposition means breaking a larger task into smaller tasks.

I used this technique with the Orchestrator agent. Its job was to understand the user's request and decide which experts should handle it.

For example, I tested this request:

"Does this person know Rust? If not, add Rust with skill level 7."

The Orchestrator divided the request into two tasks:

1. Ask the Database Read Expert to check whether Rust is already listed.
2. Ask the Database Write Expert to add Rust to the resume.

Effectiveness: This worked during my test. The Orchestrator called the Read Expert and then the Write Expert, and Rust was successfully added to the resume with skill level 7.

Conclusion

In this homework, I learned how different prompting techniques can improve AI responses. Role prompting helped each agent focus on its task, one-shot prompting showed the expected output, and decomposition helped the agents work together.