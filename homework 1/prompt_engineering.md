### Prompt Engineering Concepts

Use this file to explain 3 different prompt engineering concepts that you tried and their effectiveness. You can include screenshots of your prompts and the AI's responses if you like.

1 - Few Shot
first concept I used is the few shot, the orchestrator has and an example without quotes ("), and the Model copied the example and write the plan without it, so the code couldn't read it and the app give me an error message.
Then I added quotes to the example, and everything worked correctly.


2 - Style Prompting
second concept I used is the style prompting, the orchestrator put the plan inside a markdown code block (```python), so the code couldn't read it and the app give me "Sorry, I couldn't plan a response to that."
Then I added "No markdown, no code fences, no explanation — the Python list only." to the orchestrator instructions, and the model returned only the list and everything worked correctly.



3 - Decomposition
third concept I used is the decomposition, I asked (Does he know React? If not, add it to Freelance Projects.) and the orchestrator broke it into two smaller steps, first the Database Read Expert checked if React is there, then the Database Write Expert added it.
The two steps ran in the right order, and the app give me (New React added to the skills table) and everything worked correctly.




*note* Honestly, I didn't plan to try these techniques, they kind of tried themselves on me 😄 while I was fixing bugs, I found out I already used 3 concepts, so I didn't need to sit and experiment 😄
