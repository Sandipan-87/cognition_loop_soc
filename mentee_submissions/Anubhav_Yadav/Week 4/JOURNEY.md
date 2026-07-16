# Cognition Loop — My Journey

## Weeks 1–3 (looking back)

- **Week 1:** Connected to the Gemini API, handled rate limits, shaped model behavior with personas, and extracted strict JSON from unstructured text.
- **Week 2:** Built a Groq tool-calling agent and two Playwright automations for news scraping and YouTube playback.
- **Week 3:** Wired Groq and Playwright into a ReAct loop (`research_agent.py`) and a multi-turn chat agent that chains search with page reading (`chat_agent.py`).

## Week 4 (looking forward — final project seed)

### The one-liner

**My final project is Captain Vera — a persistent research aide that remembers the commander, tracks their quests, and scouts the live web to help them finish what they started.**

Captain Vera keeps the starship-navigator persona from Week 4: warm, direct, and always in character. She is not a generic chatbot; she is an assistant with a job.

### Which organs it uses

| Organ | What it brings | From this project |
|-------|----------------|-------------------|
| **Voice** | Persona and tone | Week 1 `persona_call.py` → Captain Vera system prompt in `my_assistant.py` |
| **Hands** | Tools and browser actions | Week 2 `basic_tool.py` + Playwright; Week 3 `search_the_web` and `open_page` |
| **Brain** | ReAct reasoning loop | Week 3 `chat_agent.py` loop — search, read, reason, answer |
| **Self** | Memory and goals across sessions | Week 4 `remember`/`recall` (`memory.json`) and quest log (`goals.json`) |

### What still needs building

- **Smarter memory:** Summarize or rank facts when `memory.json` grows so the context window stays small.
- **One signature workflow:** e.g. "Research this topic, log follow-up tasks, and greet me tomorrow with what's still open."
- **Polish:** Better error handling when search is blocked, plus a single entry command that feels like launching one agent, not a script.

This plan turns four weekly demos into one agent that knows who I am, what I'm working on, and how to go find answers on the web.
