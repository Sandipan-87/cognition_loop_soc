import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

MODEL = "llama-3.3-70b-versatile"
BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "memory.json"
GOALS_FILE = BASE_DIR / "goals.json"

BASE_SYSTEM = (
    "You are Captain Vera, a sharp-witted retired starship navigator turned research aide. "
    "You speak in confident, warm sentences and call the user 'commander'. "
    "You have live web search, page reading, persistent memory, a quest log, and a clock. "
    "Use search_the_web for current facts; chain open_page when snippets are not enough. "
    "Call remember whenever the commander shares something worth keeping (name, preferences, goals). "
    "Call recall if you need a reminder of saved facts. "
    "Call add_goal when the commander mentions something they want to do; "
    "call list_goals before complete_goal so you mark the right quest. "
    "Mention unfinished quests when it fits naturally. "
    "Use current_time for greetings or time-sensitive questions. "
    "Stay in character after every tool result. Never break character."
)


def recall_list() -> list:
    if not MEMORY_FILE.exists():
        return []
    try:
        with MEMORY_FILE.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []


def remember(fact: str) -> str:
    """Save a fact about the user so it is not forgotten between sessions."""
    memory = recall_list()
    memory.append(fact.strip())
    with MEMORY_FILE.open("w", encoding="utf-8") as file:
        json.dump(memory, file, indent=2)
    return f"Saved: {fact.strip()}"


def recall() -> str:
    """Return everything the agent remembers about the user."""
    facts = recall_list()
    return "\n".join(facts) if facts else "I don't remember anything yet."


def _load_goals() -> list:
    if not GOALS_FILE.exists():
        return []
    try:
        with GOALS_FILE.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []


def _save_goals(goals: list) -> None:
    with GOALS_FILE.open("w", encoding="utf-8") as file:
        json.dump(goals, file, indent=2)


def add_goal(goal: str) -> str:
    """Log a new goal or task the user wants to pursue."""
    goals = _load_goals()
    goals.append({"goal": goal.strip(), "done": False})
    _save_goals(goals)
    return f"New quest logged: {goal.strip()}"


def list_goals() -> str:
    """Show the user's current goals and whether each is done."""
    goals = _load_goals()
    if not goals:
        return "No quests yet — ask the user what they want to aim for."
    lines = []
    for index, item in enumerate(goals, start=1):
        mark = "x" if item.get("done") else " "
        lines.append(f"{index}. [{mark}] {item['goal']}")
    return "\n".join(lines)


def complete_goal(number: int) -> str:
    """Mark the goal at the given list number as done."""
    goals = _load_goals()
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        return f"Quest complete: {goals[number - 1]['goal']}"
    return "There is no quest with that number."


def current_time() -> str:
    """Return the current local date and time for greetings or scheduling."""
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    return f"Local time is {now}."


def search_the_web(query: str) -> str:
    """Search the live web and return the top results as text."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://html.duckduckgo.com/html/", timeout=15000)
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            page.wait_for_selector(".result__body", timeout=10000)

            results = []
            for row in page.locator(".result__body").all()[:5]:
                title = row.locator(".result__title").inner_text().strip()
                snippet = row.locator(".result__snippet").inner_text().strip()
                link = row.locator(".result__a").first.get_attribute("href") or ""
                results.append(f"{title}\n{snippet}\nURL: {link}")

            browser.close()
    except PlaywrightTimeout:
        return "Search timed out. The page may be slow or the layout changed."
    except Exception as exc:
        return f"Search failed: {exc}"

    return "\n\n".join(results) or "No results found."


def open_page(url: str) -> str:
    """Open a URL and return its visible text (trimmed)."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
    except PlaywrightTimeout:
        return "Page load timed out. The site may be slow or blocking automated access."
    except Exception as exc:
        return f"Failed to open page: {exc}"

    return text[:3000]


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": (
                "Search the live web for current information. "
                "Use whenever the commander needs recent or factual data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": (
                "Open a URL and read its visible text. "
                "Use after search_the_web when a specific page needs a closer read."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to open."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Save a fact about the commander to long-term memory. "
                "Use when they share their name, preferences, or personal details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember."},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": (
                "Read all saved facts about the commander from long-term memory."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": (
                "Get the current local date and time. "
                "Use for greetings, scheduling, or time-of-day questions."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": (
                "Log a new quest or task the commander wants to pursue later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The goal to track."},
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
                "List all quests and whether each is done. "
                "Call before complete_goal to confirm the correct number."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark a quest as done using its list number from list_goals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {
                        "type": "integer",
                        "description": "The quest number to mark complete.",
                    },
                },
                "required": ["number"],
            },
        },
    },
]

AVAILABLE_TOOLS = {
    "search_the_web": search_the_web,
    "open_page": open_page,
    "remember": remember,
    "recall": recall,
    "current_time": current_time,
    "add_goal": add_goal,
    "list_goals": list_goals,
    "complete_goal": complete_goal,
}


def build_system_prompt() -> str:
    known = recall()
    quests = list_goals()
    return (
        f"{BASE_SYSTEM}\n\n"
        f"Here is what you already know about the commander:\n{known}\n\n"
        f"The commander's current quest log:\n{quests}"
    )


def run_react_turn(client: Groq, messages: list) -> str:
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content or ""

        for call in msg.tool_calls:
            print(f"[tool] {call.function.name}({call.function.arguments})")
            tool_fn = AVAILABLE_TOOLS.get(call.function.name)
            if tool_fn is None:
                result = f"Unknown tool: {call.function.name}"
            else:
                raw_args = call.function.arguments or "{}"
                args = json.loads(raw_args)
                if args is None:
                    args = {}
                result = tool_fn(**args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(result),
                }
            )


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment or .env file.")

    client = Groq(api_key=api_key)
    system_prompt = build_system_prompt()

    print("Captain Vera — your persistent research aide")
    print(f"[memory] {recall()}")
    print(f"[quests]\n{list_goals()}\n")
    print("Type 'quit' to exit.\n")

    messages = [{"role": "system", "content": system_prompt}]

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Captain Vera: Safe travels, commander.")
            break

        messages.append({"role": "user", "content": user_input})
        answer = run_react_turn(client, messages)
        print(f"Captain Vera: {answer}\n")


if __name__ == "__main__":
    main()
