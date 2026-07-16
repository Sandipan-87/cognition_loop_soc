# Week 2: Coding Tasks

This week you will write three Python programs. The first uses the Groq API to build a small AI agent that can call a tool. The other two use Playwright to control a real browser. Build them one at a time and run each before moving on.

Read the main `README.md` first - it lists the videos, docs, and articles you need before you start coding.

## What you will build

| # | File | What it does | Concept you learn |
|---|------|--------------|-------------------|
| 1 | `basic_tool.py` | An AI agent that calls a tool to fetch live data | Tool / function calling with Groq |
| 2 | `browser_test.py` | Scrapes headlines from a news website of your choice | Browser scraping with Playwright |
| 3 | `youtube_autoplay.py` | Searches YouTube and auto-plays a video | Browser automation with Playwright |


## Setup (do this once)

1. Install the libraries:
   ```
   pip install groq python-dotenv requests playwright
   ```
2. Install the browser Playwright needs:
   ```
   playwright install chromium
   ```


## The tasks

You have freedom in how you build these. Pick your own topic, your own prompts, and your own inputs. The notes below are hints to get you unstuck, not steps you must copy.

### File 1: `basic_tool.py`

Goal: build a small AI agent that answers a question by calling a tool (a real Python function) and then explaining the result in plain language.

You decide what the tool does - for example live crypto prices, weather, currency conversion, or any free public API. The important part is the flow:
- The model decides whether your tool is needed.
- Your code runs the real function and sends the result back to the model.
- The model turns that result into a normal answer.

Hints: describe your function to Groq as a tool (JSON schema), send the question with `tools=...` and `tool_choice="auto"`, handle the `tool_calls`, reply with a `"role": "tool"` message, then call the model again for the final answer.(eg. You may use the free CoinGecko API for fetching live crypto market data )

### File 2: `browser_test.py`

Goal: open a news website, scrape its current headlines, and show them to the user.

**You choose the news source** — Hacker News, BBC, a tech blog, a sports site, anything with a list of headlines. Each site lays out its HTML differently, so part of the task is inspecting the page and finding the right selectors yourself.

Hints: launch Chromium with `sync_playwright()`, go to your chosen URL, locate the headline elements and read their text and links, then print a numbered list. A nice extra: let the user pick a headline to open in their browser.

### File 3: `youtube_autoplay.py`

Goal: take a search term from the user, find a video on YouTube, and play it automatically.

Hints: launch Chromium (use `headless=False` so you can watch it), type the query into the search box and press Enter, click a result, and let the video play. Handle real-world issues your own way. cookie pop-ups , skipping ads after 5 sec, or going fullscreen are good challenges to add.

## Before you submit

- All three files should run without errors.
- `basic_tool.py` uses your Groq key from `.env` - remember no Gemini API key or no hardcoded key.
- Playwright's Chromium is installed (`playwright install chromium`).
- Your code works for the topic and inputs you chose, not just one fixed example.

## If you get stuck

- `KeyError: 'GROQ_API_KEY'` — your `.env` is missing the key or you forgot `load_dotenv()`.
- `ModuleNotFoundError` — run the `pip install` line again.
- Playwright errors about a missing browser — run `playwright install chromium`.
- A selector finds nothing — the website's HTML changed or differs from what you expected; inspect the page and update the selector.

Good luck, stay chill and don't forget to enjoy ur summer :)

