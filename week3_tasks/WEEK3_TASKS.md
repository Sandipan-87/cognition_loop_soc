# Week 3 Coding Tasks

This week you build an agent that researches the live web on its own. It reasons with Groq and acts with Playwright, looping until it can answer. You already have the pieces from Week 2 — now you wire them together.

Read `README.md` first.

These are goals, not strict recipes. Pick your own search source, prompts, and questions — make it your own as long as each file hits its goal.

## What you will build

| # | File | What it does | Concepts you learn |
|---|------|--------------|-------------------|
| 1 | `research_agent.py` | Agent with a `search_the_web` tool. Groq decides to search; Playwright scrapes live results; the agent answers from them. | The real ReAct loop |
| 2 | `chat_agent.py` | A continuous chat that remembers the conversation and can chain two tools (search, then open a page). | Memory + tool chaining |
| 3 (stretch) | error handling | The agent survives failed searches and crashes by reasoning about them instead of dying. | Robustness |

By the end you can ask "What's trending on Hacker News today?" and the agent goes and finds out.

## Setup

Same as Week 2. Same `.env`, same Groq key, same model. If your environment is fresh:

```
pip install groq python-dotenv playwright
playwright install chromium
```

Reminder: the key lives in `.env`, never in your code, and `.env` is already in your `.gitignore`. Run `git status` and confirm `.env` is not listed.

## The tasks

### File 1 — `research_agent.py`

Goal: ask one question, let Groq decide to search, scrape a real search source with Playwright, and answer from what came back.

This is your Week 2 `basic_tool.py`, but with two changes:
- The tool is now a Playwright function instead of an API call.
- The single round becomes the `while` loop from `README_RESOURCES.md`.

**You choose the search source.** DuckDuckGo HTML (`https://html.duckduckgo.com/html/`) is the easiest — no heavy JavaScript (turn off `headless=True` to see if they triggered a bot-blocker). Or reuse your Hacker News scraper from Week 2. Each site lays out HTML differently, so finding the selectors is part of the task.

Hints:

<details>
<summary>The Playwright tool — returns a string the model can read</summary>

```python
from playwright.sync_api import sync_playwright

def search_the_web(query: str) -> str:
    """Search the live web and return the top results as text."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://html.duckduckgo.com/html/")
        page.fill('input[name="q"]', query)
        page.press('input[name="q"]', "Enter")
        page.wait_for_selector(".result__body", timeout=10000)

        results = []
        for row in page.locator(".result__body").all()[:5]:
            title = row.locator(".result__title").inner_text()
            snippet = row.locator(".result__snippet").inner_text()
            results.append(f"{title.strip()}\n{snippet.strip()}")
        browser.close()

    return "\n\n".join(results) or "No results found."
```
Selectors change — inspect the page if `.result__body` stops matching.
</details>

<details>
<summary>Describe the tool to Groq (same schema shape as basic_tool.py)</summary>

```python
tools = [{
    "type": "function",
    "function": {
        "name": "search_the_web",
        "description": "Search the live web for current information. "
                       "Use it whenever the question needs recent or factual data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
}]

available_tools = {"search_the_web": search_the_web}
```
</details>

<details>
<summary>System prompt — tell it to search</summary>

```python
SYSTEM = (
    "You are a research assistant with a live web search tool. "
    "When a question needs current or real-world facts, call search_the_web "
    "before answering. Base your answer on the results, and say so if they "
    "don't contain the answer."
)
```
</details>

Test with questions a plain LLM cannot answer.

### File 2 — `chat_agent.py`

Goal: turn the one-shot agent into a conversation that remembers, and give it a second tool so it can chain steps.

Your `basic_tool.py` already had a chat `while` loop. The new parts:
- **Memory:** keep one `messages` list outside the chat loop so follow-ups like "and who wrote it?" work.
- **A second tool:** add `open_page(url)` that opens a result and returns its text. Now the agent can chain: search, pick a link, open it, then answer. This is where the loop earns its keep.

Hints:

<details>
<summary>Two nested loops — memory lives outside</summary>

```python
messages = [{"role": "system", "content": SYSTEM}]   # persists across turns

while True:                                  # chat loop
    user_input = input("You: ").strip()
    if user_input.lower() in {"quit", "exit", "q"}:
        break
    messages.append({"role": "user", "content": user_input})

    while True:                              # ReAct loop (from RESOURCES)
        msg = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools).choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            print(f"Agent: {msg.content}")
            break
        # run each tool, append a "role": "tool" message, loop again
```
If you reset `messages` inside the chat loop, every turn forgets the last — keep it outside.
</details>

<details>
<summary>The second tool — open a page and read it</summary>

```python
def open_page(url: str) -> str:
    """Open a URL and return its visible text (trimmed)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=15000)
        text = page.locator("body").inner_text()
        browser.close()
    return text[:3000]   # keep it short so you don't blow the context window
```
Add it to `available_tools` and to the `tools` schema, just like `search_the_web`.
</details>


## Before you submit

- `.env` holds your Groq key and is in `.gitignore`; `git status` does not show it.
- No hardcoded keys, no Gemini — Groq and `llama-3.3-70b-versatile`.
- `research_agent.py` answers a live question a plain LLM cannot, and prints its tool calls.
- `chat_agent.py` remembers the conversation and answers a follow-up that depends on an earlier turn.
- `quit` exits cleanly.
- (Stretch) No crash on empty results or timeouts.

## Additional notes

- As you're approaching towards  midterm , I'm intentionally keeping this week a bit lite so that you can finish up your past submissions. Make sure to understand all these concepts clearly, it'll help you wrap up things real quick during the final submissions.

~Good luck 
