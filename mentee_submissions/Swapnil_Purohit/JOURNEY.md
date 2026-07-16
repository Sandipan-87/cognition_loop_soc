# AI Agent Journey

## Midterm Reflection
Over the first three weeks, I built the foundational organs of my AI agent:
- **Voice:** Implemented a persona and learned to extract clean JSON.
- **Hands:** Integrated Playwright to interact with live web pages (e.g. YouTube automation).
- **Brain:** Created a ReAct loop enabling the agent to reason about web search results and navigate pages autonomously.

## The Forward Look: Capstone Project
**My final project is a Planner Agent that acts as a highly systematic Project Manager for organizing complex tasks and goals.**

It will combine all the organs I have built so far:
- **Voice:** A concise, structured Project Manager persona.
- **Hands:** Custom tools like exact time stamping, deadline calculation, ticket ID generation, and web research if needed.
- **Brain:** The ReAct loop running inside execution steps to solve problems when a task requires external interaction.
- **Self:** State-driven orchestration. It will track all progress in a persistent `plan.json` file so that progress survives restarts.

The biggest new capability will be **task decomposition**: taking one massive goal, breaking it into an ordered list of smaller steps, and autonomously executing them sequentially while managing its own token budget and rate limits.
