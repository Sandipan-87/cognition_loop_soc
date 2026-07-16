import os
import json
import re
import random
import urllib.parse
from dotenv import load_dotenv
import groq
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()

if "GROQ_API_KEY" not in os.environ:
    raise ValueError("GROQ_API_KEY environment variable not found. Please check your .env file.")

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

MEMORY_FILE = "memory.json"
GOALS_FILE = "goals.json"

def recall_list() -> list:
    """Helper to load memory facts."""
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def remember(fact: str) -> str:
    """Save a fact about the user so it is not forgotten between sessions."""
    print(f"\n -> [Tool executing] remember: '{fact}'...")
    memory = recall_list()
    memory.append(fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)
    return f"Saved: {fact}"

def recall() -> str:
    """Return everything the agent remembers about the user."""
    print("\n -> [Tool executing] recall...")
    facts = recall_list()
    return "\n".join(f"- {f}" for f in facts) if facts else "I don't remember anything yet."


def _load_goals() -> list:
    """Helper to load user goals."""
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_goals(goals: list) -> None:
    """Helper to save user goals."""
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)

def add_goal(goal: str) -> str:
    """Log a new goal or task the user wants to pursue."""
    print(f"\n -> [Tool executing] add_goal: '{goal}'...")
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    return f"New quest logged: {goal}"

def list_goals() -> str:
    """Show the user's current goals and whether each is done."""
    print("\n -> [Tool executing] list_goals...")
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
    print(f"\n -> [Tool executing] complete_goal for quest #{number}...")
    goals = _load_goals()
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        return f"Quest complete: {goals[number - 1]['goal']}"
    return "There is no quest with that number."


def roll_dice(sides: int) -> str:
    """Roll an n-sided dice."""
    print(f"\n -> [Tool executing] roll_dice ({sides}-sided)...")
    if sides < 2:
        return "A dice needs at least 2 sides!"
    result = random.randint(1, sides)
    return f"Rolled a {sides}-sided dice and got: {result}"


def search_the_web(query: str) -> str:
    print(f"\n -> [Tool executing] search_the_web with query: '{query}'...")
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://search.yahoo.com/search?q={encoded_query}"
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            
            results = page.locator("#web ol > li")
            count = results.count()
            
            if count == 0:
                browser.close()
                return "No search results found. Try another query."
                
            formatted_results = []
            valid_count = 0
            for i in range(count):
                item = results.nth(i)
                link_el = item.locator("div.compTitle a")
                snippet_el = item.locator("div.compText")
                
                if link_el.count() > 0:
                    title = link_el.first.inner_text().strip()
                    href = link_el.first.get_attribute("href")
                    
                    h3_el = link_el.locator("h3")
                    if h3_el.count() > 0:
                        title = h3_el.first.inner_text().strip()
                        
                    snippet = snippet_el.first.inner_text().strip() if snippet_el.count() > 0 else "No description available."
                    
                    if title and href:
                        valid_count += 1
                        formatted_results.append(f"[{valid_count}] Title: {title}\nURL: {href}\nSnippet: {snippet}\n")
                        if valid_count >= 5:
                            break
            
            browser.close()
            if not formatted_results:
                return "No structured search results found."
            return "\n".join(formatted_results)
            
        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return f"Error executing search: {str(e)}"

def open_page(url: str) -> str:
    print(f"\n -> [Tool executing] open_page for URL: '{url}'...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            
            body_text = page.locator("body").inner_text()
            
            cleaned = re.sub(r'\n+', '\n', body_text)
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)
            cleaned = cleaned.strip()
            
            max_chars = 4000
            truncated = cleaned[:max_chars]
            if len(cleaned) > max_chars:
                truncated += "\n... [Webpage content truncated for length] ..."
                
            browser.close()
            return f"Page Content of {url}:\n\n{truncated}"
            
        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return f"Error opening page: {str(e)}"


tools = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a fact about the user so it is not forgotten between sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember"}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Return everything the agent remembers about the user.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Log a new goal or task the user wants to pursue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The description of the goal or task"}
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": "Show the user's current goals and whether each is done. Call this BEFORE completing a goal.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark the goal at the given list number as done. You MUST call list_goals first to find the correct number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "The number of the goal to mark as done"}
                },
                "required": ["number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll an n-sided dice. Useful for random decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sides": {"type": "integer", "description": "The number of sides on the dice"}
                },
                "required": ["sides"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Searches the web for a query using Yahoo Search and returns the top 5 titles, links, and page summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search terms or question to look up"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Opens a specific webpage URL and extracts its main text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The exact absolute HTTP/HTTPS URL of the page to open"}
                },
                "required": ["url"]
            }
        }
    }
]

available_tools = {
    "remember": remember,
    "recall": recall,
    "add_goal": add_goal,
    "list_goals": list_goals,
    "complete_goal": complete_goal,
    "roll_dice": roll_dice,
    "search_the_web": search_the_web,
    "open_page": open_page
}


def main():
    print("==================================================")
    print("      Captain's Quarters (Your AI Assistant)      ")
    print("   Type 'quit' or 'exit' to end the conversation ")
    print("==================================================")
    
    # Load state for the initial system prompt
    known_facts = "\n".join(f"- {f}" for f in recall_list()) or "I don't remember anything yet."
    quest_log = list_goals()
    
    system_prompt = (
        "You are Captain 'Rusty' Roberts, a retired pirate turned helpful research assistant. "
        "You speak in short, slightly gruff sentences, use nautical slang, and often call the user 'matey'. "
        "You never break character. "
        "\n\nYou have several tools at your disposal: "
        "\n1. Memory tools (remember / recall) to keep track of facts about the user. Whenever the user shares something worth keeping (like their name or preferences), call 'remember'. "
        "\n2. Quest log tools (add_goal / list_goals / complete_goal). When the user wants to pursue something, call 'add_goal'. When they finish a quest, FIRST call 'list_goals' to find its number, then call 'complete_goal'. "
        "\n3. roll_dice for chaotic random decisions if asked. "
        "\n4. search_the_web and open_page for answering factual queries. "
        "\n\nHere is what you already know about the user:\n"
        f"{known_facts}\n"
        "\n\nThe user's current quest log:\n"
        f"{quest_log}\n"
        "\n\nIf the user has unfinished quests or known facts, you can mention them naturally in character."
    )
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    while True:
        try:
            user_input = input("\nMatey: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Fair winds!")
            break
            
        if user_input.strip().lower() in ["quit", "exit"]:
            print("Exiting. Fair winds!")
            break
            
        if not user_input.strip():
            continue
            
        messages.append({"role": "user", "content": user_input})
        
        round_num = 1
        while True:
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                msg = response.choices[0].message
                messages.append(msg)
                
                if not msg.tool_calls:
                    print(f"\nCaptain: {msg.content}")
                    break
                    
                tool_calls_to_execute = msg.tool_calls
            except groq.BadRequestError as err:
                body = getattr(err, "body", None)
                parsed_calls = []
                if body and isinstance(body, dict) and "error" in body:
                    error_details = body["error"]
                    if error_details.get("code") == "tool_use_failed" and "failed_generation" in error_details:
                        failed_str = error_details["failed_generation"]
                        pattern = r"<function=(\w+).*?(\{.*?\})"
                        matches = re.findall(pattern, failed_str, re.DOTALL)
                        for name, args_str in matches:
                            try:
                                args = json.loads(args_str.strip())
                                parsed_calls.append((name, args))
                            except Exception:
                                pass
                
                if not parsed_calls:
                    raise err
                    
                print(f"\n[Fallback Parser] Caught Groq tool call format failure. Parsed {len(parsed_calls)} tool call(s).")
                
                mock_tool_calls = []
                for idx, (name, args) in enumerate(parsed_calls):
                    mock_tool_calls.append({
                        "id": f"mock_call_{round_num}_{idx}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args)
                        }
                    })
                
                mock_assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": mock_tool_calls
                }
                messages.append(mock_assistant_msg)
                
                class MockFunction:
                    def __init__(self, name, arguments):
                        self.name = name
                        self.arguments = arguments
                        
                class MockToolCall:
                    def __init__(self, id, function):
                        self.id = id
                        self.function = function
                
                tool_calls_to_execute = [
                    MockToolCall(mock_call["id"], MockFunction(mock_call["function"]["name"], mock_call["function"]["arguments"]))
                    for mock_call in mock_tool_calls
                ]
                
            for call in tool_calls_to_execute:
                tool_name = call.function.name
                tool_args = json.loads(call.function.arguments)
                
                print(f"\n[Tool Call] Captain calls: '{tool_name}' with args {json.dumps(tool_args)}")
                
                if tool_name in available_tools:
                    tool_func = available_tools[tool_name]
                    try:
                        result = tool_func(**tool_args)
                    except Exception as err:
                        result = f"Error executing tool: {str(err)}"
                else:
                    result = f"Error: Tool '{tool_name}' is not supported."
                    
                print(f"[Tool Response] Execution completed.")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": tool_name,
                    "content": result
                })
                
            round_num += 1

if __name__ == "__main__":
    main()
