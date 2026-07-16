# AI Trip Planner Agent

A state-driven planning agent. Give it a trip goal (start city, destination, number of days) and it breaks the goal into ordered sub-tasks (transit legs, hotel stays, sightseeing), writes them to `plan.json`, and works through them one at a time — using live web search and page scraping for steps that need current data. Kill it mid-run and restart: it resumes from the next unfinished step.

## What it does

1. **Timeline draft** — `make_brief_city_timeline_plan()` makes one Groq call to turn your prompt into a brief city-by-city route (stops, stay days, transit legs).
2. **Structured plan** — `make_plan()` converts that timeline into `plan.json`, using a strict JSON schema so every step has a stable `id`, a `task`, a `status` (`pending` / `in_progress` / `done`), and a `result` (`null` until completed).
3. **Step execution** — `run_loop()` walks the steps in order. For each non-`done` step, `complete_task()` runs a reason → act → observe loop: it decides whether the task needs live data, and if so calls the `extract_links` tool (DuckDuckGo search via Playwright) and `extract_info` tool (scrapes a page's text) until it has enough to answer, then returns a short (≤150 char) result.
4. **Persistence** — after **every single step**, the updated plan is written back to `plan.json`. This is what makes the agent resumable: a crash, a rate limit, or a Ctrl-C costs at most one step of progress.
5. **Summary** — once every step is `done`, `summarize()` sends the full plan to Groq and writes a clean final itinerary to `summary.md`.

### The four organs
| Organ | Where it lives |
|---|---|
| Voice | System prompts for timeline planning, JSON planning, and task completion each hold a distinct persona/role. |
| Hands | `extract_links` and `extract_info` tools (Playwright-driven DuckDuckGo search + page scraping). |
| Brain | The tool-calling loop inside `complete_task()` — call a tool, observe the result, decide whether to continue or answer. |
| Self | `plan.json` — written to disk after every step, so the process itself is disposable. |

### Reliability details
- **429 handling** — `call_llm()` wraps every Groq call in exponential backoff (2s → 4s → 8s → 16s…) up to 5 retries.
- **Token discipline** — step results are capped at ~150 characters, and the plan's steps array is never dumped whole into a prompt, so token cost per step stays flat no matter how long the plan grows.
- **Resumability** — on startup, if `plan.json` already holds an `in_progress` plan, the agent skips regeneration and calls `run_loop()` directly, continuing from the first step whose status isn't `done`.

## Setup

```bash
pip install groq python-dotenv playwright
playwright install chromium
```

Create a `.env` file (never committed — check `git status` before every push):

```
GROQ_API_KEY=your_key_here
```

## How to run

```bash
python planner.py
```

You'll be prompted for a trip goal:

```
Which trip U want to plan (say Initial Place and Destination and No of days)? : Mumbai to Japan, 10 days
```

The agent then:
1. Prints a brief timeline (e.g. `Mumbai TO Tokyo - 0.4 days (flight)` / `Tokyo - STAY - 4` / …).
2. Builds `plan.json` with transit/stay/around steps for each leg.
3. Executes each step, printing `using tool extract_links` / `using tool extract_info` when it searches the web.
4. Saves `plan.json` to disk after each completed step.
5. Writes the final trip plan to `summary.md`.

**To test resumability:** press `Ctrl-C` partway through a run, then run `python planner.py` again with the same prompt. Since `plan.json` still has `status: "in_progress"`, the agent skips planning and picks up exactly where it left off — resuming from the first step that isn't `done`.

## Example run

Input:
```
Mumbai to Japan, 10 days
```

`plan.json` right after planning (all 10 steps present up front, `status: "pending"` and `result: null` until each one is executed):
```json
{
  "goal": "Mumbai to Japan, 10 days ...",
  "status": "in_progress",
  "current_step": 1,
  "steps": [
    { "id": 1, "task": "Find transport from Mumbai to Tokyo", "status": "pending", "result": null },
    { "id": 2, "task": "Find hotels and stay in Tokyo for 4 days", "status": "pending", "result": null },
    { "id": 3, "task": "Find places to go around in Tokyo in 4 days", "status": "pending", "result": null },
    { "id": 4, "task": "Find transport from Tokyo to Kyoto", "status": "pending", "result": null },
    ...
    { "id": 9, "task": "Find places to go around in Hakone in 2 days", "status": "pending", "result": null },
    { "id": 10, "task": "Find transport from Hakone to Mumbai", "status": "pending", "result": null }
  ]
}
```

Same file after the agent has worked through a couple of steps — `result` fills in and `status` flips to `"done"` one at a time, in place, while the rest stay `pending`:
```json
{
  "goal": "Mumbai to Japan, 10 days ...",
  "status": "in_progress",
  "current_step": 1,
  "steps": [
    { "id": 1, "task": "Find transport from Mumbai to Tokyo", "status": "done",
      "result": "Direct flight, ~9h15m, Air India AI-302 / ANA, approx ₹53k-65k" },
    { "id": 2, "task": "Find hotels and stay in Tokyo for 4 days", "status": "done",
      "result": "Mercure Tokyo Haneda ₹32k/night; Tokyo East Side Kaie ₹62k/night" },
    { "id": 3, "task": "Find places to go around in Tokyo in 4 days", "status": "pending", "result": null },
    ...
    { "id": 10, "task": "Find transport from Hakone to Mumbai", "status": "pending", "result": null }
  ]
}
```

Final `summary.md` (excerpt — full markdown table version with per-day breakdown, cost overview, and packing checklist is generated by the agent):

```
10-Day Mumbai → Japan Trip – Summary

Day 0: Mumbai → Tokyo, direct flight (~9h15m)
Days 1-4: Tokyo — Shibuya/Harajuku, Asakusa/Akihabara, Shinjuku/Tokyo Tower, Odaiba/teamLab
Day 5: Tokyo → Kyoto via Shinkansen (~2h07m)
Days 5-7: Kyoto — Kinkaku-ji, Fushimi Inari, Arashiyama
Day 8: Kyoto → Hakone via Shinkansen + local train
Days 8-9: Hakone — Ropeway/Lake Ashi, museums/onsens
Day 10: Hakone → Mumbai, one-stop return flight

Approx total cost: ₹350k–1,500k depending on hotel tier.
```

## Files

| File | Purpose |
|---|---|
| `planner.py` | The agent — planning, execution loop, tools, summarization. |
| `plan.json` | Agent's persistent state. Starts as a valid empty file; the agent grows it. |
| `summary.md` | Final human-readable itinerary, written once the plan is complete. |
| `.env` | Holds `GROQ_API_KEY_final`. Not committed to git. |

## Notes on process
Prompt design (system prompts for the timeline planner, JSON schema planner, and task-completion loop) was iterated on through testing, with AI assistance used to refine prompt structure and cut redundant instructions.

## Known limitations / next steps
- Playwright runs with `headless=False` — switch to `headless=True` for unattended/server runs.
- `extract_links`/`extract_info` don't currently retry on their own errors beyond returning an `"ERROR:"` string for the LLM to react to.
- Cost figures and hotel names in results are only as reliable as the scraped pages — always double-check before booking.