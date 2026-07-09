# Capstone — The Planner Agent 



**State-driven orchestration.** You give the agent one big goal. It breaks the goal into ordered sub-tasks, writes them to a local JSON file, and then works through them one at a time — reading its own state from disk, executing the next step, writing the result back, and advancing. Kill the program mid-run and start it again: it picks up exactly where it left off.



> The one sentence to internalize: **`plan.json` is the agent's brain. The Python process is disposable.** All memory of what to do and what's done lives on disk, never only in RAM.



---



## The stack (unchanged)



Same as every week. Nothing new to install.



```python

import os

from dotenv import load_dotenv

from groq import Groq



load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])



MODEL = "llama-3.3-70b-versatile"

```



Your key stays in `.env`. Run `git status` and confirm `.env` is **not** listed before every push.



---



## The mental model: a state machine on disk



A state machine is just: *a current state, and rules for moving to the next one.* Your `plan.json` holds the state. Your loop is the rule for advancing it.



```

                    ┌──────────────────────────────────────────┐

                    │              plan.json  (state)           │

                    │  goal, status, current_step, [ steps ]    │

                    └──────────────────────────────────────────┘

                          ▲                              │

                   write result,                    read next

                   advance step                     pending step

                          │                              ▼

      ┌───────────────────────────────────────────────────────────┐

      │  THE LOOP (stateless — safe to crash and restart)           │

      │                                                             │

      │  1. load plan.json                                          │

      │  2. no plan yet?  →  make_plan(goal)  →  save               │

      │  3. find first step whose status != "done"                  │

      │  4. all done?  →  print summary, exit                       │

      │  5. execute that ONE step (tools allowed here)              │

      │  6. save result, mark step "done", advance current_step     │

      │  7. save plan.json  →  go to 1                              │

      └───────────────────────────────────────────────────────────┘

```



Notice what step 7 buys you: because the state is flushed to disk after **every** step, a crash, a rate-limit, a laptop closing, or `Ctrl-C` costs you at most one step of progress. That is the whole point of the pattern.



---



## `plan.json` — the schema



Start the file as a valid empty object `{}` (never a blank file), and grow it into this shape once a goal is set:



```json

{

  "goal": "Plan my week of study for final exams",

  "status": "in_progress",

  "current_step": 2,

  "steps": [

    {

      "id": 1,

      "task": "List every subject with an exam and its date",

      "status": "done",

      "result": "5 subjects: DBMS (Jul 12), OS (Jul 14), CN (Jul 16)..."

    },

    {

      "id": 2,

      "task": "Estimate study hours needed per subject",

      "status": "in_progress",

      "result": null

    },

    {

      "id": 3,

      "task": "Build a day-by-day timetable from now until the last exam",

      "status": "pending",

      "result": null

    }

  ]

}

```



Field contract:



| Field | Type | Meaning |

|-------|------|---------|

| `goal` | string | The one big goal the user gave you. |

| `status` | `"in_progress"` \| `"done"` | Whole-plan status. |

| `current_step` | integer | `id` of the step being worked on. |

| `steps[].id` | integer | Stable, 1-based. Never renumber. |

| `steps[].task` | string | A single, self-contained instruction. |

| `steps[].status` | `"pending"` \| `"in_progress"` \| `"done"` | Per-step status — this is what makes it resumable. |

| `steps[].result` | string \| null | What executing the step produced. `null` until done. |



`make_plan(goal)` is one Groq call that returns a numbered list of tasks. Force clean JSON out of it (the `json_extractor.py` technique from Week 1: "respond with ONLY raw JSON, no markdown fences"), then write those tasks in as `pending` steps.



---



## Groq survival guide (free tier)



You have two hard constraints on the free tier: **requests that get rate-limited (HTTP 429)** and **your Tokens-Per-Minute budget**. Both are solvable, and solving them is part of the grade.



### 1 — the 429. Retry with exponential backoff.



A 429 means "you're going too fast, wait." Never let it crash your run. Wrap **every** Groq call in a retry that waits longer each time it's told to slow down.



```python

import time

from groq import Groq, RateLimitError



def call_llm(client, messages, tools=None, max_retries=5):

    """One Groq call, hardened against HTTP 429 with exponential backoff."""

    delay = 2  # seconds

    for attempt in range(max_retries):

        try:

            return client.chat.completions.create(

                model=MODEL,

                messages=messages,

                tools=tools,

                tool_choice="auto" if tools else None,

            )

        except RateLimitError:

            if attempt == max_retries - 1:

                raise  # give up after the last attempt

            print(f"    rate-limited (429). backing off {delay}s…")

            time.sleep(delay)

            delay *= 2  # 2s → 4s → 8s → 16s …

    raise RuntimeError("exhausted retries")

```



Exponential means the wait **doubles** each time (2 → 4 → 8 → 16). That's what stops you from hammering the API and getting stuck in a 429 loop. Every `chat.completions.create` in your project goes through this function — no exceptions.



> Stretch: read the `Retry-After` header off the exception when it's present and sleep for exactly that, falling back to the doubling delay when it isn't.



### 2 — the TPM limit. Never send the whole plan.



The single fastest way to blow your Tokens-Per-Minute budget is to paste the entire `plan.json` — every task and every accumulated result — into the prompt on every step. A 10-step plan would re-send all 10 results on step 10. Token cost grows with every step and you hit the ceiling.



**Send only what the current step actually needs:**



- ✅ the `goal` (one line)

- ✅ the **current** step's `task`

- ✅ a *short* summary of the **immediately previous** step's `result` (only if this step depends on it)

- ❌ **not** the full `steps` array

- ❌ **not** every past `result`



```python

def build_step_context(plan, step):

    """Minimal prompt context — bounded token cost no matter how long the plan is."""

    messages = [

        {"role": "system", "content": PLANNER_PERSONA},

        {"role": "user", "content": f"Overall goal: {plan['goal']}"},

    ]

    prev = get_step(plan, step["id"] - 1)  # None for the first step

    if prev and prev["result"]:

        summary = prev["result"][:300]  # cap it — one step back, trimmed

        messages.append({"role": "user",

                          "content": f"Result of the previous step: {summary}"})

    messages.append({"role": "user",

                     "content": f"Now do exactly this step, nothing else:\n{step['task']}"})

    return messages

```






Check your real numbers at **console.groq.com/settings/limits** — free-tier TPM/RPM/daily caps change, so read them off your own dashboard rather than trusting a number in a doc.



---



## Build it in stages (MVP first — this order matters)



Do **not** try to build the whole thing at once. Each stage runs on its own.



1. **`plan.json` round-trips.** A function that writes a hard-coded plan dict to disk and reads it back. Print it. This is your state layer — nothing else works without it.

2. **`make_plan(goal)`.** One Groq call → clean JSON list of tasks → written into `plan.json` as `pending` steps. No execution yet.

3. **The loop, MVP.** Load plan → find first non-`done` step → execute it with `build_step_context` → save result, mark `done`, advance → repeat until finished. **Stop, quit, re-run — confirm it resumes.** ← *This is the MVP finish line.*

4. **Wire in the four organs** (voice, hands, brain, self) and harden edge cases — see below.



If you can run stage 3, kill it halfway, run it again, and watch it continue from the next pending step, you have a working state-driven agent. Everything after that is polish.



---



## What the capstone must show



The planner is the new idea, but the capstone still has to wire in all four organs from the term:



| Organ | In the Planner Agent, this is… |

|-------|--------------------------------|

| **Voice**  | A persona it holds while planning and reporting — a terse project-manager voice, say. Same system-prompt trick as `persona_call.py`. |

| **Hands**  | At least one real tool a step can call to *do* work — a web search, the crypto tool, a file writer. A plan that only thinks isn't enough. |

| **Brain**  | The reason → act → observe loop from Week 3, running *inside* a single step's execution when that step needs a tool. |

| **Self**  | `plan.json` surviving a full restart. This organ is free — it's the core of the whole design. |

| **New idea**  | **Task decomposition + state-driven orchestration** — `make_plan`, ordered steps, resumable progress. |



---



## The deadlines — read the row that applies to you




### Group A — 3rd-year students · **MVP due July 9th**



You have campus placements and resume-verification deadlines bearing down. You do **not** need a perfect agent by the 9th. You need a **working MVP you can honestly put on your resume**:



- ✅ `make_plan(goal)` produces a step list into `plan.json`

- ✅ the loop executes steps one at a time and **saves state to disk after each**

- ✅ it resumes correctly after a restart

-  edge cases, extra tools, and persona polish — **later**, no penalty



Ship stages 1–3 above. That is a legitimate, demonstrable "autonomous planning agent with persistent state" line on your CV. Polish in the following week.



### Group B — 1st / 2nd-year & MSc / MTech students · **Final due July 20th**



-  **Checkpoint — July 14th (hard):** pushed to GitHub — an initialized `plan.json` (valid empty `{}` or `[]`), your `.env` wired up, and a basic Groq connection that makes one successful call. Miss this and you're flagged.

-  **Final — July 20th:** the complete capstone — all four organs, the 429 backoff, disciplined TPM context, and a `README`.



The checkpoint is deliberately small. It exists so that by the 14th you have already fought the setup battles (key, install, first call) and the only thing left is the actual build.



---



## Deliverable



- `capstone.py` (or `planner.py`) — the agent.

- `plan.json` — committed as a valid empty file; the agent grows it.

- Any tool files a step calls.

- A short `README.md`: what it does, how to run it, and **one example run** showing a goal going in and steps being checked off.

- `.env` stays out of git. No hardcoded keys, ever.



## Definition of done



You are finished when someone can:



1. run `python capstone.py` and hand it a goal,

2. watch it decompose the goal and start working through steps,

3. press `Ctrl-C` halfway,

4. run it again — and see it **resume from the next unfinished step** and drive the goal to completion.



That's an agent that finishes jobs.
