"""
my_assistant.py  —  Week 4 capstone-in-miniature.

One creature, four organs:
  * voice  -> a persona (Aldric the Archmage, a wizard mentor)
  * hands  -> a live web search tool (reused from Week 3)
  * brain  -> a reason -> act -> observe loop (ReAct, from Week 3)
  * self   -> memory that survives restarts + a quest log it keeps for you

Run it, tell it your name, quit, run it again -> it still knows you.
"""

import os
import re
import json
import asyncio
import datetime
from dotenv import load_dotenv
from groq import Groq
from playwright.async_api import async_playwright

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

MEMORY_FILE = "memory.json"
GOALS_FILE = "goals.json"


# ============================================================
# HANDS  —  live web search  (reused from Week 3)
# ============================================================

async def _search_the_web(query):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(
                f"https://html.duckduckgo.com/html/?q={query}",
                timeout=30000,
            )
            await page.wait_for_selector(".result", timeout=10000)

            items = await page.locator(".result").all()

            for item in items[:5]:
                title = await item.locator(".result__title").inner_text()
                link = await item.locator("a").get_attribute("href")

                try:
                    snippet = await item.locator(".result__snippet").inner_text()
                except Exception:
                    snippet = ""

                results.append({"title": title, "link": link, "snippet": snippet})

        except Exception as e:
            results.append({"error": str(e)})

        await browser.close()

    return results


def search_the_web(query):
    return asyncio.run(_search_the_web(query))


# ============================================================
# SELF (part 1)  —  memory that survives being switched off
# ============================================================

def _load_memory():
    """Read the fact list, tolerating a missing / empty / half-written file."""
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def remember(fact):
    """Save a fact about the user so it is not forgotten between sessions."""
    memory = _load_memory()
    if fact not in memory:                 # don't stockpile duplicates
        memory.append(fact)
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)
    return f"Committed to the spellbook: {fact}"


def recall():
    """Return everything the agent remembers about the user."""
    facts = _load_memory()
    if not facts:
        return "The spellbook holds nothing about this traveller yet."
    return "\n".join(f"- {fact}" for fact in facts)


# ============================================================
# SELF (part 2)  —  the quest log (structured state)
# ============================================================

def _load_goals():
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_goals(goals):
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)


def add_goal(goal):
    """Log a new goal or task the user wants to pursue."""
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    return f"New quest logged: {goal}"


def list_goals():
    """Show the user's current goals and whether each is done."""
    goals = _load_goals()
    if not goals:
        return "The quest board is empty — ask the traveller what they aim to achieve."
    lines = []
    for i, g in enumerate(goals, 1):
        mark = "x" if g["done"] else " "
        lines.append(f"{i}. [{mark}] {g['goal']}")
    return "\n".join(lines)


def complete_goal(number):
    """Mark the goal at the given list number as done."""
    goals = _load_goals()
    number = int(number)
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        return f"Quest complete! *staff glows* -> {goals[number - 1]['goal']}"
    return "There is no quest with that number on the board."


# ============================================================
# SELF (part 3)  —  a signature tool that makes it *mine*
# ============================================================

def current_time():
    """Return the current date and time so greetings and deadlines land correctly."""
    now = datetime.datetime.now()
    return now.strftime("%A, %d %B %Y, %I:%M %p")


# ============================================================
# TOOL SCHEMAS
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web for current facts, news, or anything you do not already know.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Save a lasting fact about the user (their name, what they like, what they "
                "are working on, preferences). Call this whenever the user shares something "
                "personal worth keeping across sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember, phrased clearly"}
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Read back everything you remember about the user. Use it when unsure what you already know.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "Get the current local date and time. Use it to greet correctly (morning/evening) or reason about deadlines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Log a new goal / task the user wants to pursue. Call this when the user mentions something they want to do or achieve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The goal in the user's own words"}
                },
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": "Show the user's current quests and whether each is done. ALWAYS call this before completing a goal so you know the right number.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark the quest at a given list number as done. Call list_goals first to find the correct number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "The 1-based number of the quest to complete"}
                },
                "required": ["number"],
            },
        },
    },
]

available_tools = {
    "search_the_web": lambda query: search_the_web(query),
    "remember": lambda fact: remember(fact),
    "recall": lambda: recall(),
    "current_time": lambda: current_time(),
    "add_goal": lambda goal: add_goal(goal),
    "list_goals": lambda: list_goals(),
    "complete_goal": lambda number: complete_goal(number),
}


# ============================================================
# VOICE  —  the persona, loaded up with what it already knows
# ============================================================

PERSONA = """
You are Aldric the Archmage — a wise, warm, faintly theatrical wizard who has taken
the user on as your apprentice. You speak in a mentor's voice: encouraging, a little
grand, fond of calling the user "young apprentice" or "traveller". You treat their
tasks as quests and small wins as victories worth celebrating. Keep replies fairly
short and human — one flourish, then get to the point. Never break character.

Your powers (tools) and when to reach for them:
- search_the_web  : whenever a question needs current, real-world facts you don't hold.
- current_time    : to greet correctly or reason about deadlines.
- remember        : the MOMENT the user reveals something lasting about themselves
                    (their name, what they enjoy, what they are building) — save it.
- recall          : if you are unsure what you already know about them.
- add_goal        : when the user says they want to do / finish / achieve something.
- list_goals      : to show the quest board — and ALWAYS call this before completing
                    a quest, so you mark the right one.
- complete_goal   : when the user says they finished something; find its number via
                    list_goals first, then complete it and celebrate in character.

Always read the result of a tool, THEN answer in character. Never expose raw JSON.
When it fits, gently remind the apprentice of unfinished quests on their board.
"""


def build_system_prompt():
    """Walk in already knowing the user: fold memory + quest board into the prompt."""
    known = recall()
    board = list_goals()
    return (
        PERSONA
        + "\n\nHere is what you already know about your apprentice:\n"
        + known
        + "\n\nTheir current quest log:\n"
        + board
    )


# ============================================================
# TOOL-CALL RECOVERY  —  Groq/Llama safety net
# ============================================================
# Llama-3.x on Groq usually returns native `tool_calls`, but it
# INTERMITTENTLY leaks the call into the text content instead, e.g.
#   <function=remember {"fact": "..."}></function>
#   <function/current_time/>
#   <|python_tag|>{"name": "remember", "arguments": {...}}
# When that happens `message.tool_calls` is empty, so the raw text would
# be printed as a "final answer" and the tool would never run. This parser
# recovers those leaked calls so every tool fires the same way.

def _safe_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_text_tool_calls(content):
    """Return [(name, args_dict), ...] recovered from text-leaked tool calls."""
    if not content:
        return []

    # Form A — <|python_tag|>{"name": "...", "arguments"/"parameters": {...}}
    py_calls = []
    for m in re.finditer(
        r'\{\s*"name"\s*:\s*"([A-Za-z_]\w*)"\s*,\s*'
        r'"(?:arguments|parameters)"\s*:\s*(\{.*?\})\s*\}',
        content,
        re.DOTALL,
    ):
        py_calls.append((m.group(1), _safe_json(m.group(2))))
    if py_calls:
        return py_calls

    # Form B — <function=NAME ...> / <function=NAME>{...}</function> / <function/NAME/>
    calls = []
    for m in re.finditer(r"<function[=/]\s*([A-Za-z_]\w*)", content):
        name = m.group(1)
        rest = content[m.end():]
        # end the block at the earliest tag terminator so we don't grab
        # JSON belonging to a later call
        enders = [rest.find(t) for t in ("</function>", "/>", "<function")]
        enders = [e for e in enders if e != -1]
        block = rest[: min(enders)] if enders else rest[:200]
        jm = re.search(r"\{.*\}", block, re.DOTALL)
        calls.append((name, _safe_json(jm.group(0)) if jm else {}))
    return calls


def _extract_failed_generation(err):
    """Pull the raw model output out of a Groq `tool_use_failed` error.

    When the model emits a MALFORMED tool call, Groq does not return a
    message — it raises a 400 whose body carries the offending text in a
    `failed_generation` field. We dig it out so the same recovery parser
    can salvage the call instead of the whole turn crashing.
    """
    candidates = []

    body = getattr(err, "body", None)
    if isinstance(body, dict):
        candidates.append(body)
        if isinstance(body.get("error"), dict):
            candidates.append(body["error"])

    resp = getattr(err, "response", None)
    if resp is not None:
        try:
            data = resp.json()
            if isinstance(data, dict):
                candidates.append(data)
                if isinstance(data.get("error"), dict):
                    candidates.append(data["error"])
        except Exception:
            pass

    for c in candidates:
        fg = c.get("failed_generation")
        if fg:
            return fg

    # last resort: scrape it out of the stringified error
    m = re.search(
        r"failed_generation['\"]?\s*[:=]\s*['\"](.+?)['\"]\s*[},]",
        str(err),
        re.DOTALL,
    )
    return m.group(1) if m else None


# ============================================================
# BRAIN  —  the reason / act / observe loop
# ============================================================

def main():
    messages = [{"role": "system", "content": build_system_prompt()}]

    print("=" * 60)
    print("  Aldric the Archmage awakens.  (type 'quit' to leave)")
    print("=" * 60)

    # Let Aldric open the session in character, aware of memory + quests.
    messages.append({
        "role": "user",
        "content": "(The apprentice has just entered. Greet them, using what you "
                   "remember about them and their open quests. Do not invent facts.)"
    })

    # Unique across the WHOLE session — Groq maps each tool result to its
    # call by tool_call_id, so recovered ids must never repeat.
    synthetic_seq = 0

    while True:
        # inner loop: keep acting on tools until the model produces a final reply
        while True:
            message = None
            leaked_text = ""

            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
                message = response.choices[0].message
                if not message.tool_calls:
                    leaked_text = message.content or ""
            except Exception as api_err:
                # Groq raises `tool_use_failed` (a 400) when the model emits a
                # malformed tool call. Recover the raw attempt from the error;
                # if there's nothing to recover, it's a real error — re-raise.
                leaked_text = _extract_failed_generation(api_err)
                if leaked_text is None:
                    raise

            # Normalise both paths to a list of (call_id, name, args).
            calls = []

            if message is not None and message.tool_calls:
                # Native path — the model used real tool calls.
                messages.append(message)
                for tc in message.tool_calls:
                    calls.append((
                        tc.id,
                        tc.function.name,
                        _safe_json(tc.function.arguments),
                    ))
            else:
                # Recovery path — a tool call was leaked into text content
                # (leaked_text from message.content) OR into a `tool_use_failed`
                # error (leaked_text from failed_generation).
                recovered = parse_text_tool_calls(leaked_text)
                if not recovered:
                    # No tool call to salvage — this is a genuine final reply.
                    if message is not None:
                        messages.append(message)
                    print("\nAldric:\n" + leaked_text)
                    break

                # Rebuild the assistant turn with proper tool_calls so the
                # history stays valid for the follow-up request.
                synthetic = []
                for name, args in recovered:
                    synthetic_seq += 1
                    cid = f"call_recovered_{synthetic_seq}"
                    calls.append((cid, name, args))
                    synthetic.append({
                        "id": cid,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    })
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": synthetic,
                })

            for call_id, name, args in calls:
                print(f"\n  ...casting {name}({args})")

                if name in available_tools:
                    try:
                        result = available_tools[name](**args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {name}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": json.dumps(result),
                })

        user = input("\nYou: ")
        if user.strip().lower() in ("quit", "exit"):
            print("\nAldric: Rest well, apprentice. Your quests will be waiting. *the tower dims*")
            break

        messages.append({"role": "user", "content": user})


if __name__ == "__main__":
    main()
