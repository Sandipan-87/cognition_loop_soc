import os
import json
import datetime
import random
import string
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = 'llama-3.1-8b-instant'

# --- EXISTING TOOLS (Week 3) ---

def search_the_web(query: str) -> str:
    """Search Wikipedia and return the text of the best matching page or search results."""
    import urllib.parse
    encoded_query = urllib.parse.quote_plus(query)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://en.wikipedia.org/w/index.php?search={encoded_query}", timeout=15000)
            
            if "search=" in page.url:
                results = []
                for item in page.locator(".mw-search-result").all()[:5]:
                    text = item.inner_text()
                    url_elem = item.locator(".mw-search-result-heading a").first
                    url = "https://en.wikipedia.org" + (url_elem.get_attribute("href") or "") if url_elem.count() > 0 else "unknown"
                    results.append(f"Result:\n{text}\nURL: {url}")
                text = "\n\n".join(results) or "No results found."
            else:
                text = f"Found Wikipedia Article: {page.url}\n\n"
                for p_tag in page.locator("#mw-content-text p").all()[:3]:
                    text += p_tag.inner_text() + "\n"
            browser.close()
        return text
    except Exception as e:
        return f"Error performing search: {e}"

def open_page(url: str) -> str:
    """Open a URL and return its visible text."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if url.startswith("//"):
                url = "https:" + url
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
        return text[:3000]
    except Exception as e:
        return f"Error opening page: {e}"

# --- MEMORY TOOLS ---

MEMORY_FILE = "memory.json"

def recall_list() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def remember(fact: str) -> str:
    """Save a fact about the user so it is not forgotten between sessions."""
    memory = recall_list()
    memory.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)
    return f"Saved fact: {fact}"

def recall() -> str:
    """Return everything the agent remembers about the user."""
    facts = recall_list()
    return "\n".join(facts) if facts else "I don't remember anything yet."

# --- CUSTOM TOOLS (Project Manager Persona) ---

def current_time() -> str:
    """Return the exact current date and time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_deadline(days_from_now: int) -> str:
    """Calculate the exact date that is a specific number of days from now."""
    target_date = datetime.datetime.now() + datetime.timedelta(days=days_from_now)
    return target_date.strftime("%Y-%m-%d")

def generate_ticket_id() -> str:
    """Generate a random alphanumeric ticket ID (e.g. PROJ-9482)."""
    num = ''.join(random.choices(string.digits, k=4))
    return f"PROJ-{num}"

# --- GOAL TRACKING TOOLS ---

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
    return f"New quest/ticket logged: {goal}"

def list_goals() -> str:
    """Show the user's current goals and whether each is done."""
    goals = _load_goals()
    if not goals:
        return "No quests/tickets yet."
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
        return f"Ticket complete: {goals[number - 1]['goal']}"
    return "There is no ticket with that number."

# --- AGENT SETUP ---

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web for current information.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a specific URL to read the full page content.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a fact about the user so it is not forgotten between sessions.",
            "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Return everything remembered about the user.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "Return the exact current date and time.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_deadline",
            "description": "Calculate the exact date that is a specific number of days from now.",
            "parameters": {"type": "object", "properties": {"days_from_now": {"type": "integer"}}, "required": ["days_from_now"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_ticket_id",
            "description": "Generate a random alphanumeric ticket ID (e.g. PROJ-9482).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Log a new goal or task the user wants to pursue. Call generate_ticket_id first to assign it a formal tracking number in the description.",
            "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": "Show the user's current goals and whether each is done.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark the goal at the given list number as done. Always use list_goals first if you are unsure of the number.",
            "parameters": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]}
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page,
    "remember": remember,
    "recall": recall,
    "current_time": current_time,
    "calculate_deadline": calculate_deadline,
    "generate_ticket_id": generate_ticket_id,
    "add_goal": add_goal,
    "list_goals": list_goals,
    "complete_goal": complete_goal
}

BASE_SYSTEM = (
    "You are an elite, highly systematic assistant. Your communication style is concise, "
    "structured, and action-oriented. You prioritize clarity, tracking deadlines, and checking off tasks. "
    "You refer to conversations as 'syncs' or 'standups' and use bullet points whenever possible.\n\n"
    "RULES:\n"
    "- When the user shares something worth keeping (their name, project info), call `remember`.\n"
    "- When the user mentions a new task or goal they want to pursue, call `generate_ticket_id` to get a ticket number, then call `add_goal` with the ticket number included in the goal description.\n"
    "- When the user says they finished something, find it with `list_goals` and then call `complete_goal`.\n"
    "- Stay in character at all times, even after calling tools."
)

def get_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

def run_assistant():
    print("Welcome to your AI Assistant! (Type 'quit' or 'exit' to stop)")
    
    # Load memory and goals at startup
    known_facts = recall()
    current_goals = list_goals()
    
    system_prompt = BASE_SYSTEM + f"\n\nHere is what you already know about the user:\n{known_facts}\n\nThe user's current quest/ticket log:\n{current_goals}"
    messages = [{"role": "system", "content": system_prompt}]
    
    greeting = get_greeting()
    # Greet the user with open quests if any exist
    if "PROJ" in current_goals or "1. " in current_goals:
        print(f"\nAssistant: {greeting}. Here is our current board:\n{current_goals}\nWhat's our focus today?")
    else:
        print(f"\nAssistant: {greeting}. We have a clean board. How can I help you today?")
        
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"quit", "exit", "q", ""}:
            break
            
        messages.append({"role": "user", "content": user_input})
        
        while True:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools
            )
            
            msg = response.choices[0].message
            
            if msg.tool_calls:
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    function_name = tool_call.function.name
                    # Handle json parsing safely
                    try:
                        arguments = json.loads(tool_call.function.arguments) or {}
                    except Exception:
                        arguments = {}
                        
                    print(f"-> PM action: {function_name} {arguments}")
                    
                    tool_function = available_tools.get(function_name)
                    if tool_function:
                        result = tool_function(**arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": str(result)
                        })
            else:
                messages.append({"role": "assistant", "content": msg.content})
                print(f"Assistant: {msg.content}")
                break

if __name__ == "__main__":
    run_assistant()
