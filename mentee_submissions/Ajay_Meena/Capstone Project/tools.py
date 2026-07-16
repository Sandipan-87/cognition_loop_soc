import os
import json
import datetime
from playwright.sync_api import sync_playwright

MEMORY_FILE = "memory.json"
GOALS_FILE = "goals.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def load_goals():
    if not os.path.exists(GOALS_FILE):
        return []
    try:
        with open(GOALS_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def remember(fact: str):
    facts = load_memory()
    facts.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2)
    return "Stored."


def recall():
    facts = load_memory()
    if not facts:
        return "Nothing stored yet."
    return "Known facts:\n" + "\n".join(f"- {f}" for f in facts)


def add_goal(goal: str):
    goals = load_goals()
    goals.append({"goal": goal, "done": False})
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)
    return f"Goal added: {goal}"


def list_goals():
    goals = load_goals()
    if not goals:
        return "No goals yet."
    out = ""
    for i, g in enumerate(goals):
        status = "done" if g["done"] else "pending"
        out += f"{i+1}. [{status}] {g['goal']}\n"
    return out


def complete_goal(number: int):
    goals = load_goals()
    idx = number - 1
    if idx < 0 or idx >= len(goals):
        return "Invalid goal number."
    if goals[idx]["done"]:
        return f"Goal {number} was already marked done."
    goals[idx]["done"] = True
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)
    return f"Marked done: {goals[idx]['goal']}"


def search_the_web(query: str):
    with sync_playwright() as p:
        # headless=False keeps the browser visual during your demo
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        try:
            encoded = query.replace(" ", "+")
            page.goto(f"https://lite.duckduckgo.com/lite/?q={encoded}", timeout=15000)
            page.wait_for_timeout(2000)

            links = page.locator("a.result-link")
            snippets = page.locator("td.result-snippet")
            count = min(links.count(), 5)

            output = ""
            for i in range(count):
                try:
                    title = links.nth(i).inner_text()
                    link = links.nth(i).get_attribute("href")
                    try:
                        snippet = snippets.nth(i).inner_text()
                    except:
                        snippet = ""
                    output += f"{i+1}. {title}\n{snippet}\n{link}\n\n"
                except:
                    continue

            browser.close()
            return output if output else "No results found."
        except Exception as e:
            browser.close()
            return f"Search failed: {str(e)}"


def current_time():
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d %Y, %I:%M %p")


def dispatch_tool(name: str, args: dict):
    if name == "remember":
        return remember(args["fact"])
    elif name == "recall":
        return recall()
    elif name == "add_goal":
        return add_goal(args["goal"])
    elif name == "list_goals":
        return list_goals()
    elif name == "complete_goal":
        return complete_goal(args["number"])
    elif name == "search_the_web":
        return search_the_web(args["query"])
    elif name == "current_time":
        return current_time()
    return "Unknown tool."


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the web for live or current information. Use this whenever a step needs real data from the internet — news, prices, facts, research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save an important fact to persistent memory so it survives restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string"}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Read all saved facts from persistent memory.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Add a goal or task to the persistent quest log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"}
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": "List all goals and their completion status from the quest log.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark a goal as completed by its number. Always call list_goals first to confirm the right number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"}
                },
                "required": ["number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "Get the current date and time.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]