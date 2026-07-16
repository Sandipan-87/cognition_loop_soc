"""
my_assistant.py — Week 4
AXIOM: A precise, observational intelligence.

Tools (8 total):
  Week-3 (kept) : search_the_web, open_page
  Memory        : remember, recall            → memory.json
  Quest log     : add_goal, list_goals,
                  complete_goal               → goals.json
  Custom        : get_datetime
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────
# 1. Setup
# ─────────────────────────────────────────────────────────────────
load_dotenv()
client = Groq()
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

MEMORY_FILE = "memory.json"
GOALS_FILE  = "goals.json"


# ─────────────────────────────────────────────────────────────────
# 2. Week-3 Tools (kept verbatim from chat_agent.py)
# ─────────────────────────────────────────────────────────────────
def search_the_web() -> str:
    """Scrape the Hacker News front page for trending stories and their URLs."""
    print("\n[AXIOM] Scanning Hacker News...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.goto("https://news.ycombinator.com/")
            page.wait_for_selector(".titleline > a", timeout=10000)

            results = []
            for row in page.locator(".titleline > a").all()[:5]:
                title = row.inner_text()
                url   = row.get_attribute("href")
                results.append(f"Title: {title.strip()}\nURL: {url}")

            browser.close()
        return "\n\n".join(results) or "No results found."
    except Exception as e:
        return f"Error scraping Hacker News: {str(e)}"


def open_page(url: str) -> str:
    """Open a URL and return its visible text content."""
    print(f"\n[AXIOM] Reading: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
        return text[:3000]  # keep context window safe
    except Exception as e:
        return f"Failed to read page. Error: {str(e)}"


# ─────────────────────────────────────────────────────────────────
# 3. Memory Tools — File 2
#    Backend: memory.json  →  ["fact one", "fact two", ...]
# ─────────────────────────────────────────────────────────────────
def _load_memory() -> list:
    """Internal helper — read memory.json safely."""
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []   # half-written file — start fresh


def remember(fact: str) -> str:
    """
    Save a fact about the operator to long-term memory.
    Call whenever the operator shares their name, a preference,
    a goal, or anything personal worth keeping.
    """
    memory = _load_memory()
    memory.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)
    print(f"\n[AXIOM] Stored: {fact}")

    # Warn if memory is getting large (context-window hygiene)
    if len(memory) > 20:
        print(f"[AXIOM] Note: {len(memory)} facts in memory. "
              "Consider pruning memory.json if responses slow down.")
    return f"Stored: {fact}"


def recall() -> str:
    """Return everything remembered about the operator."""
    facts = _load_memory()
    return "\n".join(f"- {f}" for f in facts) if facts else "No memory on file."


# ─────────────────────────────────────────────────────────────────
# 4. Custom Tool — File 3
#    get_datetime: lets AXIOM be time-aware
# ─────────────────────────────────────────────────────────────────
def get_datetime() -> str:
    """Return the current date and local time."""
    now = datetime.now()
    return now.strftime("Date: %A, %d %B %Y\nTime: %H:%M")


# ─────────────────────────────────────────────────────────────────
# 5. Quest-Log Tools — File 4
#    Backend: goals.json  →  [{"goal": "...", "done": false}, ...]
# ─────────────────────────────────────────────────────────────────
def _load_goals() -> list:
    """Internal helper — read goals.json safely."""
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_goals(goals: list) -> None:
    """Internal helper — write goals list to goals.json."""
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)


def add_goal(goal: str) -> str:
    """
    Log a new goal or task the operator wants to accomplish.
    Call whenever the operator mentions something they intend to do.
    """
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    print(f"\n[AXIOM] Goal logged: {goal}")
    return f"Goal logged: {goal}"


def list_goals() -> str:
    """
    Show the operator's goals and their completion status.
    ALWAYS call this before calling complete_goal — never guess a number.
    """
    goals = _load_goals()
    if not goals:
        return "No goals on record."
    lines = []
    for i, g in enumerate(goals, 1):
        mark = "x" if g["done"] else " "
        lines.append(f"{i}. [{mark}] {g['goal']}")
    return "\n".join(lines)


def complete_goal(number: int) -> str:
    """
    Mark the goal at position `number` as done.
    ALWAYS call list_goals first to confirm the correct number.
    """
    goals = _load_goals()
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        completed = goals[number - 1]["goal"]
        print(f"\n[AXIOM] Marked complete: {completed}")
        return f"Marked complete: {completed}"
    return f"No goal at position {number}. Call list_goals to check the current list."


# ─────────────────────────────────────────────────────────────────
# 6. Tool Schema — all 8 tools registered for the LLM
# ─────────────────────────────────────────────────────────────────
tools = [
    # ── Week-3 tools ──────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": (
                "Scrape Hacker News front page for trending tech stories and links. "
                "Use when asked about current tech news or what is trending."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": (
                "Open a specific URL and return its full text. "
                "Only call when the operator explicitly asks to read or open an article."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The exact URL to open.",
                    },
                },
                "required": ["url"],
            },
        },
    },

    # ── Memory tools ──────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Save a fact about the operator to long-term memory. "
                "Call immediately when the operator shares their name, "
                "a preference, a project they are working on, or anything personal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to store, written as a complete sentence.",
                    },
                },
                "required": ["fact"],
            },
        },
    },

    # ── Quest-log tools ───────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": (
                "Log a new goal or task to the operator's quest log. "
                "Call when the operator says they want to do, finish, or work on something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The goal, written as a clear action statement.",
                    },
                },
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": (
                "Show the operator's current goals and completion status. "
                "ALWAYS call this before complete_goal — never assume a goal's number."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": (
                "Mark a goal as done by its 1-indexed position in the list. "
                "You MUST call list_goals first to confirm the correct number "
                "before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {
                        "type": "integer",
                        "description": "The 1-indexed position of the goal to mark complete.",
                    },
                },
                "required": ["number"],
            },
        },
    },
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page":      open_page,
    "remember":       remember,
    "get_datetime":   get_datetime,
    "add_goal":       add_goal,
    "list_goals":     list_goals,
    "complete_goal":  complete_goal,
}


# ─────────────────────────────────────────────────────────────────
# 7. Persona + System Prompt
#    Built fresh every run from live file state — this is what
#    makes persistence work.
# ─────────────────────────────────────────────────────────────────
PERSONA = (
    "You are AXIOM, a precise and observational intelligence. "
    "You speak in short, unhurried sentences. No filler, no padding. "
    "You address the user as 'operator' until you learn their name — "
    "once you know it, use it. "
    "When you encounter a genuinely hard problem, you say so, briefly. "
    "You never break character — including after tool results. "
    "After every tool call, respond to the operator in character as AXIOM. "
    "Never narrate or mention the tool call itself in your reply.\n\n"

    "TOOL RULES — follow these exactly:\n"
    "1. When the operator shares their name, a preference, or anything personal: "
    "call remember() immediately, then continue your reply.\n"
    "2. When the operator says they want to do or finish something: "
    "call add_goal() immediately.\n"
    "3. When the operator says they completed something: "
    "call list_goals() first to confirm the number, then call complete_goal(n).\n"
    "4. For trending tech news: call search_the_web(), list the headlines clearly, "
    "then ask if the operator wants any article opened.\n"
    "5. Only call open_page() when the operator explicitly asks to read a specific article.\n"
    "6. Use get_datetime() when giving a time-aware greeting or when asked the date or time.\n"
)


def build_system_prompt() -> str:
    """
    Assemble the full system prompt:
      PERSONA  +  known memory (from file)  +  open quest log (from file)

    Called once at startup — layers 3 and 4 are empty on first run
    and fill automatically as the operator talks to AXIOM.
    """
    system = PERSONA
    now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
    system += f"\nCurrent date and time: {now}\n"
    memory_block = recall()
    if memory_block != "No memory on file.":
        system += f"\nWhat you already know about the operator:\n{memory_block}\n"

    goals_block = list_goals()
    if goals_block != "No goals on record.":
        system += (
            f"\nOperator's current quest log:\n{goals_block}\n"
            "When appropriate — especially at session start — note any unfinished goals.\n"
        )

    return system


# ─────────────────────────────────────────────────────────────────
# 8. Chat Loop  (structure from chat_agent.py, unchanged)
# ─────────────────────────────────────────────────────────────────
def start_chat():
    print("\n[ AXIOM online. Type 'quit' to disconnect. ]\n")

    # Build system prompt fresh from file state — this is the boot sequence
    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]

    while True:
        user_input = input("Operator: ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            print("\n[ AXIOM offline. ]\n")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # Inner ReAct loop — runs until model gives a final text response
        while True:
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )

                msg = response.choices[0].message
                messages.append(msg)

                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        function_name = tool_call.function.name

                        # Bulletproof arg parsing (carried from chat_agent.py)
                        args_string   = tool_call.function.arguments
                        function_args = {}
                        if args_string:
                            parsed = json.loads(args_string)
                            if isinstance(parsed, dict):
                                function_args = parsed

                        function_to_call = available_tools[function_name]
                        tool_result      = function_to_call(**function_args)

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role":         "tool",
                            "name":         function_name,
                            "content":      tool_result,
                        })
                    # loop repeats — model reads tool results and decides next step

                else:
                    # No tool calls → final answer
                    print(f"\nAXIOM: {msg.content}\n")
                    break

            except Exception as e:
                print(f"\n[System Error] {e}")
                break


if __name__ == "__main__":
    start_chat()