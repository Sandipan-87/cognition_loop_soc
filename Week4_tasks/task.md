# Week 4 tasks

New to anything below? Read `RESOURCES_WEEK4.md` first.

These are goals, not strict recipes. Pick your own personality, your own tools, your own memory format — make it your own as long as each file hits its goal.

## The journey so far (read this — it is the whole idea)

You did not learn four random things:

| Week | What you gave the agent | The file that taught it |
|------|-------------------------|-------------------------|
| 1 | A voice — it could talk, take on a persona, and return clean structured data | `basic_call.py`, `persona_call.py`, `json_extractor.py` |
| 2 | Hands — it could call a tool and drive a real browser | `basic_tool.py`, `browser_test.py`, `Youtube.py` |
| 3 | A brain loop — it could reason, act, observe, and remember a conversation | `research_agent.py`, `chat_agent.py` |
| 4 | A self — a personality, a memory that survives being switched off, and goals it holds for you | this week |
| ★ Final | A purpose — all four organs wired into one agent that does something genuinely useful | your capstone |

Week 3 gave your agent memory that lasts as long as the program is running. Close it, and everything is gone. This week fixes that — and then goes one step further: an agent that not only remembers *you*, but keeps track of what you are trying to *do*.

## Your final project

Picture the finish line. Your final project is **one agent that combines every organ you built**: it talks in a character you chose (voice), reaches out to the live web or a custom tool (hands), reasons in a loop until it has an answer (brain), and remembers you and your goals across days (self). Not four demos — one creature with a job.

You do not have to know exactly what it is yet. But starting this week, every task is a piece of it:

```
   voice  ─┐
   hands  ─┤
   brain  ─┼──►  YOUR FINAL AGENT  ──►  does one thing, genuinely well, and remembers you
   self   ─┘
```

The last task this week (the quest log) and the deliverable (a forward-looking section added to your `JOURNEY.md`) exist purely to point you at that finish line while it is still cheap to experiment.

## What you will build

| # | File | What it does | Concept you learn |
|---|------|--------------|-------------------|
| 1 | `my_assistant.py` | Your Week 3 chat agent, given a personality and your favourite tool(s) from Weeks 2–3. | Composition — reusing what you built |
| 2 | `remember()` / `recall()` tools | The agent saves facts to a file and reads them back, so it remembers you across restarts. | Persistence beyond the context window |
| 3 | one tool of your choice | Anything that makes the assistant more *you*. | Designing your own tool |
| 4 | a quest log (`goals.json`) | The agent tracks goals you give it, lists them, and checks them off — across sessions. | Structured memory + multi-tool coordination |

Plus one short, forward-looking section added to your existing `JOURNEY.md`, that becomes the seed of your final project.

## Setup

Nothing new. Same `.env`, same Groq key, same model, same Playwright if you reuse a web tool. If your environment is fresh:

```
pip install groq python-dotenv playwright
playwright install chromium
```

Reminder: the key lives in `.env`, never in your code, and `.env` is in your `.gitignore`. Run `git status` and confirm `.env` is not listed.

## The tasks

### File 1 — `my_assistant.py`

Goal: copy your Week 3 `chat_agent.py`, give it a personality, and keep one or two tools you already wrote. This is mostly a rename and a stronger system prompt — that is on purpose. The point is to feel how little code separates "a generic bot" from "a character with abilities."

Bring back the persona idea from Week 1's `persona_call.py`, Pick something you would actually enjoy talking to — you will be living with it for the rest of the project.

Hints:

<details>
<summary>The persona lives in the system message — the same slot as your tools agent</summary>

```python
SYSTEM = (
    "You are a Captain, a retired pirate turned research assistant. "
    "You speak in short, gruff sentences and call the user 'matey'. "
    "You have a live web search tool — use it whenever a question needs "
    "current facts, then answer in character. Never break character."
)

messages = [{"role": "system", "content": SYSTEM}]
```

The persona is just words. The tools are the same `tools=` schema you already have. Nothing else about your Week 3 loop changes.
</details>

The whole task: take a working agent, change who it is, keep what it can do. If it runs and stays in character while still using a tool, you are done with File 1.

### File 2 — give it a memory that survives (the headline task)

Goal: add two tools, `remember(fact)` and `recall()`, backed by a small file like `memory.json`. The agent writes facts it learns about you to the file, and reads them back at the start of a conversation. Close the program, reopen it tomorrow, and it greets you knowing what it knew.

A few lines of `json` turn a forgetful chatbot into something that builds up a relationship — and it is the exact mechanism your final project will use to feel personal.

Hints:

<details>
<summary>Two tiny tools — read and write a JSON file</summary>

```python
import json, os

MEMORY_FILE = "memory.json"

def remember(fact: str) -> str:
    """Save a fact about the user so it is not forgotten between sessions."""
    memory = recall_list()
    memory.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)
    return f"Saved: {fact}"

def recall_list() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []   # empty or half-written file — start fresh instead of crashing

def recall() -> str:
    """Return everything the agent remembers about the user."""
    facts = recall_list()
    return "\n".join(facts) if facts else "I don't remember anything yet."
```

Add both `remember` and `recall` to your `tools` schema and to `available_tools`, exactly like you added `open_page` in Week 3.
</details>

<details>
<summary>Make it load its memory at the start of every run</summary>

The simplest trick: before the chat loop, read the file and drop what it knows into the system prompt, so the agent walks in already knowing you.

```python
known = recall()
SYSTEM = SYSTEM + f"\n\nHere is what you already know about the user:\n{known}"
messages = [{"role": "system", "content": SYSTEM}]
```

Tell the agent in its system prompt to call `remember` whenever the user shares something worth keeping — their name, their goals, what they are working on.

Note: be careful here. If your memory file grows huge, injecting all of it into the system prompt every run will eat up your context window and slow the Groq API down. A handful of facts is fine for now; if it ever gets long, that is a real engineering problem worth a paragraph in your `JOURNEY.md`.
</details>

To see: run it, tell it your name and one thing you like. Quit. Run it again. Ask "what's my name?" If it answers without you repeating yourself, you built persistent memory from scratch.

### File 3 — one tool that makes it yours

Add a single tool that fits your assistant's character. Ideas:

- `roll_dice(sides)` or `flip_coin()` — for a chaotic gremlin assistant.
- `current_time()` — so it can say good morning correctly.

The skill here is writing a tool description clear enough that the model knows when to reach for it. That is real prompt engineering, and the tool you pick here is very likely the seed of your final project's signature feature — so pick something you would be proud to demo.

### File 4 — a quest log your agent keeps for you

Goal: give the assistant three small tools — `add_goal(goal)`, `list_goals()`, and `complete_goal(number)` — backed by a `goals.json` file. Now your agent does not just remember *facts* about you; it remembers what you are *trying to do*, and it can check things off as you finish them.

This is the moment your assistant crosses a line. Remembering your name is nice. Holding your goals across days, reminding you what is unfinished, and celebrating when you complete one — that is an assistant that shows up *for* you. It is also the most "final-project-shaped" thing you will build this week: almost every great agentic AI is, underneath, something that tracks state and helps you move it forward.

It is genuinely fun to use. Tell it "remind me to finish the memory task" today, quit, come back tomorrow, and ask "what's on my list?" — it knows. Mark one done and watch it react in character.

Hints:

<details>
<summary>Three tiny tools over one JSON file (structured this time, not a flat list)</summary>

Notice the step up from Week 2's memory: each goal is now a small object with a `done` flag, not just a string. That is your first taste of *structured* state — the shape real agents store.

```python
import json, os

GOALS_FILE = "goals.json"

def _load_goals() -> list:
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_goals(goals: list) -> None:
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)

def add_goal(goal: str) -> str:
    """Log a new goal or task the user wants to pursue."""
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    return f"New quest logged: {goal}"

def list_goals() -> str:
    """Show the user's current goals and whether each is done."""
    goals = _load_goals()
    if not goals:
        return "No quests yet — ask the user what they want to aim for."
    lines = []
    for i, g in enumerate(goals, 1):
        mark = "x" if g["done"] else " "
        lines.append(f"{i}. [{mark}] {g['goal']}")
    return "\n".join(lines)

def complete_goal(number: int) -> str:
    """Mark the goal at the given list number as done."""
    goals = _load_goals()
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        return f"Quest complete: {goals[number - 1]['goal']}"
    return "There is no quest with that number."
```

Add all three to your `tools` schema and `available_tools`, same as every tool before.
</details>

<details>
<summary>Let the agent chain them — and tell it to greet you with your open quests</summary>

The fun comes from chaining. When you say "I finished the second one," the model has to call `list_goals()` to see what number 2 is, reason about it, then call `complete_goal(2)`. That is the ReAct loop from Week 3 earning its keep on *your* data.

Drop your open quests into the system prompt at startup, just like memory, so it can open with "Welcome back — you've still got 2 quests on the board":

```python
SYSTEM = SYSTEM + f"\n\nThe user's current quest log:\n{list_goals()}"
```

In the system prompt, tell it: when the user mentions something they want to do, call `add_goal`; when they say they finished something, find it with `list_goals` and call `complete_goal`; and bring up unfinished quests when it makes sense. Then stay in character the whole time.
</details>

You are done with File 4 when you can add a goal in one run, quit, and have the agent greet you with it still on the board in the next.

## Deliverable — a forward-looking section in `JOURNEY.md` (your final-project seed)

For the midterm, your `JOURNEY.md` looked *backward* at what you built. Now add one short new section to the same file that looks *forward*. Keep it to a page:

- **The one-liner.** "My final project is an agent that ______ for ______." Name it. Give it a persona.
- **Which organs it uses.** Voice, hands, brain, self — which tools from Weeks 1–4 does it combine, and what new one does it need?

Write it for yourself. When the final project officially opens, this section means you start from a plan instead of a blank page.

## Before you submit

- `.env` holds your Groq key and is in `.gitignore`; `git status` does not show it.
- No hardcoded keys
- `my_assistant.py` stays in character and still uses at least one tool.
- After a full restart, the agent recalls a fact you told it in an earlier run.
- `memory.json` is created on first run and grows as you talk to it.
- The agent can log a goal, list it after a restart, and check it off (`goals.json`).
- `JOURNEY.md` has a new forward-looking section that reads like a plan you would actually follow.

## If you get stuck

- `FileNotFoundError` on a `.json` file — check `os.path.exists` before reading; create it on first write.
- `JSONDecodeError` reading a file — it is empty or half-written; the `try/except` returns `[]`. If you skipped it, add it back.
- Agent never calls a memory/goal tool — strengthen the system prompt: tell it explicitly *when* to save, list, and complete.
- Agent forgets after restart — you are not loading the file into the system prompt before the chat loop, or you reset the file each run.
- `complete_goal` marks the wrong quest — the model guessed a number instead of calling `list_goals()` first; tell it in the prompt to list before completing.
- It drops character when using a tool — remind it in the system prompt to answer in character *after* reading the tool result.

This phase is meant to feel good — make something you would actually want to keep, because you are about to build the rest of it. Good luck ^~^
