# Capstone — The Planner Agent (Captain Vera)

An autonomous **planning agent with persistent state**. You give it one big
goal; it decomposes the goal into ordered sub-tasks, writes them to
`plan.json`, then works through them one at a time. All memory of what to do
and what is done lives on disk — so if you `Ctrl-C` it (or it crashes, or your
laptop closes) and run it again, it **resumes from the next unfinished step**.

> `plan.json` is the agent's brain. The Python process is disposable.

## The four organs

| Organ | In this agent |
|-------|---------------|
| **Voice** | *Captain Vera* — a terse starship-navigator project-manager persona. |
| **Hands** | Real tools a step can call: `web_search` (live DuckDuckGo scrape) and `save_file`. |
| **Brain** | A reason → act → observe loop that runs *inside* a single step when it needs a tool. |
| **Self**  | `plan.json` survives a full restart. |
| **New idea** | Task decomposition + resumable, state-driven orchestration (`make_plan`, ordered steps, per-step status). |

## How to run

```bash
# from the project root (same .env with your Groq key)
pip install groq python-dotenv playwright
playwright install chromium        # only needed if a step uses web_search

python capstone.py
```

The script auto-discovers the `.env` (walking up parent folders) and reads
`GROQ_API_KEY`. Model: `llama-3.3-70b-versatile`. No keys are ever hardcoded.

## Design notes

- **429 backoff.** Every Groq call goes through `call_llm()`, which retries with
  exponential backoff (2 → 4 → 8 → 16 s) and honours a `Retry-After` header when
  the SDK exposes one.
- **TPM discipline.** `build_step_context()` sends only the goal, the *current*
  step's task, and a 300-char summary of the *immediately previous* result —
  never the whole `steps` array or every past result. Token cost stays bounded
  no matter how long the plan grows.
- **State flushed after every step.** `plan.json` is saved *before* the risky
  work (step marked `in_progress`) and *after* it (`done` + result), so a crash
  costs at most one step of progress.

## `plan.json` schema

```json
{
  "goal": "string",
  "status": "in_progress | done",
  "current_step": 2,
  "steps": [
    { "id": 1, "task": "string", "status": "done",        "result": "string" },
    { "id": 2, "task": "string", "status": "in_progress", "result": null }
  ]
}
```

`plan.json` ships as a valid empty object `{}`; the agent grows it on first run.

## Example run

```
=== Captain Vera :: The Planner Agent ===
Hand me a goal. Ctrl-C anytime -- I resume from where I stopped.

Captain Vera: What is the mission, commander?
Goal: Plan a 3-day beginner study schedule for Python

Captain Vera: Plotting the course...

  Mission: Plan a 3-day beginner study schedule for Python  [in_progress]
    1. [ ] List the core beginner Python topics to cover
    2. [ ] Estimate study hours needed per topic
    3. [ ] Build a day-by-day timetable across 3 days

  -> Step 1: List the core beginner Python topics to cover
     done. Core topics: variables & types, control flow, functions...

  -> Step 2: Estimate study hours needed per topic
     done. ~2h variables, 3h control flow, 3h functions...
^C

Captain Vera: Holding position, commander. Progress saved to plan.json -- run me again to resume.
```

Run it again and it picks up at **Step 3** — the finished steps are already
`done` on disk.

## Definition of done

1. `python capstone.py` takes a goal,
2. decomposes it and works through the steps,
3. `Ctrl-C` halfway → progress is on disk,
4. re-run → resumes from the next unfinished step and drives the goal to completion.
