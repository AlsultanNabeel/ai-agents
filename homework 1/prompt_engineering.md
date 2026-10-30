# Prompt Engineering – CSE 491 Homework 1

1. Role-Based Prompting

The AI system uses different roles for different responsibilities: Database Read Expert, Database Write Expert, Content Expert, and Orchestrator.

Effectiveness: Separating responsibilities helped organize database operations and conversational responses. The Read Expert successfully generated SQL to retrieve the Python skill level.

2. Structured Output Instructions

The prompts guide the experts to return information in a format that the Python application can process, such as skill names, skill levels, and experience names.

Effectiveness: The Write Expert successfully extracted TypeScript, level 7, and the target experience, allowing the application to save the skill after confirmation. However, an extra word in an experience name caused one failed lookup, showing that structured outputs still need validation.

3. Task Decomposition and Orchestration

The Orchestrator identifies whether a user request requires reading, writing, or both. Compound requests are divided into smaller steps, such as checking whether a skill exists before adding it.

Effectiveness: The system successfully handled a compound TypeScript request, checked the database, requested confirmation, and saved the new skill. The result remained visible after refreshing the resume page.

Conclusion

These techniques improved task organization and made the AI easier to integrate with database operations. Testing also revealed that exact database-name matching can limit reliability, suggesting that input normalization would be a useful future improvement.