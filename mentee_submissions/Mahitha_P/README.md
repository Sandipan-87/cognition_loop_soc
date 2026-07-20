# Atlas — The Planner Agent (Capstone)

A state-driven orchestration agent. You hand it **one big goal**; it decomposes
the goal into ordered sub-tasks, writes them to `plan.json`, then works through
them **one at a time** — reading its state from disk, executing the next step,
writing the result back, and advancing.

> **`plan.json` is the agent's brain. The Python process is disposable.**
> All memory of what to do and what's done lives on disk, never only in RAM.

Kill it mid-run (`Ctrl-C`) and start it again — it resumes from the next
unfinished step, because state is flushed to disk after **every** step.

## The four organs

| Organ | In Atlas |
|-------|----------|
| **Voice** | `Atlas`, a terse project-foreman persona (system prompt). |
| **Hands** | Real tools a step can call: `search_the_web`, `save_note` (writes an artifact to `outputs/`), `current_time`. |
| **Brain** | A reason → act → observe loop running *inside* a single step's execution when that step needs a tool, plus `make_plan` for task decomposition. |
| **Self**  | `plan.json` surviving a full restart. |
| **New idea** | Task decomposition + resumable, state-driven orchestration. |

## `plan.json` schema

```json
{
  "goal": "Plan my week of study for final exams",
  "status": "in_progress",
  "current_step": 2,
  "steps": [
    { "id": 1, "task": "List every subject with an exam and its date",
      "status": "done", "result": "5 subjects: DBMS, OS, CN..." },
    { "id": 2, "task": "Estimate study hours per subject",
      "status": "in_progress", "result": null }
  ]
}
```

Per-step `status` (`pending` / `in_progress` / `done`) is what makes the plan
resumable. `id`s are stable and never renumbered.

## Setup

```bash
pip install groq python-dotenv playwright
playwright install chromium          # only needed for the search_the_web tool
```

Create a `.env` file (never commit it — it is in `.gitignore`):

```
GROQ_API_KEY=your_key_here
```

Check your live free-tier limits at https://console.groq.com/settings/limits.

## Run it

```bash
python capstone.py
```

- First run: it asks for a goal, decomposes it, and starts working.
- Later runs with a `plan.json` in progress: it **resumes** automatically.
- Finished plan: it prints the summary and offers to start a new goal.

To start over, reset the state file to `{}`.

## Free-tier hardening

- **429 backoff.** Every Groq call goes through `call_llm()`, which retries with
  exponential backoff (2 → 4 → 8 → 16s) and honours `Retry-After` when present.
- **TPM discipline.** `build_step_context()` sends only the goal, the current
  step's task, and a trimmed (≤300 char) summary of the *previous* step — never
  the whole plan or every past result — so token cost stays bounded as the plan
  grows.
- **Tool-call recovery.** If the Llama model leaks a tool call as text or triggers
  `tool_use_failed`, the call is salvaged so a step never silently loses a tool.

## Example run

```
$ python capstone.py
============================================================
  ATLAS — the Planner Agent
============================================================

Give Atlas a goal: Plan a 3-day revision schedule for my DBMS exam

Decomposing goal into a plan...

-> Step 1: List the major DBMS topics to revise
   done: Normalization, transactions & ACID, indexing, SQL joins, concurrency control...

-> Step 2: Estimate revision hours per topic
   done: Normalization 2h, Transactions 3h, Indexing 2h, SQL 2h, Concurrency 3h (12h total)

-> Step 3: Build a day-by-day timetable and save it
      tool: current_time({})
      tool: save_note({'filename': 'dbms_schedule.txt', 'content': 'Day 1...'})
   done: Wrote 412 chars to outputs/dbms_schedule.txt

# ... press Ctrl-C here on a longer plan ...
^C
Interrupted. Progress is saved in plan.json — run again to resume.

$ python capstone.py     # <-- resumes from the next unfinished step
Resuming existing plan: Plan a 3-day revision schedule for my DBMS exam
-> Step 4: ...
```

## Files

- `capstone.py` — the agent.
- `plan.json` — the state file (committed as an empty `{}`; the agent grows it).
- `outputs/` — artifacts produced by the `save_note` tool.
- `.env` — your Groq key (git-ignored, never committed).
