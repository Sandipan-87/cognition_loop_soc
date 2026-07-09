import os
import json
import datetime
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

client = Groq(api_key="xyz")

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
    return f"Got it, I'll remember that."


def recall():
    facts = load_memory()
    if not facts:
        return "I don't have anything stored about you yet."
    return "Here's what I remember:\n" + "\n".join(f"- {f}" for f in facts)


def add_goal(goal: str):
    goals = load_goals()
    goals.append({"goal": goal, "done": False})
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)
    return f"Added to your quest log: {goal}"


def list_goals():
    goals = load_goals()
    if not goals:
        return "Your quest log is empty."
    result = "Your quests:\n"
    for i, g in enumerate(goals):
        status = "✓" if g["done"] else "○"
        result += f"{i+1}. [{status}] {g['goal']}\n"
    return result


def complete_goal(number: int):
    goals = load_goals()
    idx = number - 1
    if idx < 0 or idx >= len(goals):
        return "That quest number doesn't exist. Use list_goals to check."
    if goals[idx]["done"]:
        return f"Quest {number} is already completed."
    goals[idx]["done"] = True
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)
    return f"Quest {number} complete: {goals[idx]['goal']}"


def search_the_web(query: str):
    with sync_playwright() as p:
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
    return now.strftime("It's %A, %B %d %Y, %I:%M %p")


tools = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a fact about the user to memory so you can recall it later, even after restart. Call this whenever the user tells you something personal like their name, preferences, or anything worth remembering.",
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
            "description": "Read all saved facts about the user from memory. Call this when the user asks what you remember, or when you need context about them.",
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
            "description": "Add a new goal or task to the user's quest log. Call this when the user says they want to do something, finish something, or asks you to remind them of something.",
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
            "description": "List all goals in the user's quest log with their completion status. Call this when the user asks what's on their list, what's pending, or before completing a goal.",
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
            "description": "Mark a goal as completed by its number. Always call list_goals first to confirm the correct number before calling this.",
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
            "name": "search_the_web",
            "description": "Search the web for live or current information the user asks about. Use this for news, prices, current events, or anything that needs up to date data.",
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
            "name": "current_time",
            "description": "Get the current date and time. Use this when the user asks what time or date it is, or to give a proper greeting based on the time of day.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

memory_context = recall()
goals_context = list_goals()

system_prompt = f"""You are ARIA — Autonomous Research & Intelligence Assistant. You have a dry, witty personality. You're helpful but never boring. You speak casually, drop the occasional sarcasm, but always get the job done. You never break character, even while using tools.

You have persistent memory and a quest log. Here's what you currently know:

MEMORY:
{memory_context}

QUEST LOG:
{goals_context}

Rules you follow strictly:
- When someone tells you their name or anything personal, call remember() immediately.
- When someone asks what you remember, call recall().
- When someone mentions a task or goal, call add_goal() without being asked.
- When someone asks what's on their list, call list_goals().
- Always call list_goals() before complete_goal() to confirm the number.
- For current info like prices or news, use search_the_web().
- For time or date questions, use current_time().
- After using any tool, always respond in character as ARIA.
- Greet the user with their open quests if any exist."""

messages = [
    {"role": "system", "content": system_prompt}
]

print("ARIA online. Type 'quit' to exit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "quit":
        print("ARIA: Logging off. Your quests await.")
        break

    messages.append({"role": "user", "content": user_input})

    while True:
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
        except Exception as e:
            print(f"  [API error: {str(e)}, retrying without tools...]")
            response = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages
            )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                print(f"  [Tool: {name}({args})]")

                if name == "remember":
                    result = remember(args["fact"])
                elif name == "recall":
                    result = recall()
                elif name == "add_goal":
                    result = add_goal(args["goal"])
                elif name == "list_goals":
                    result = list_goals()
                elif name == "complete_goal":
                    result = complete_goal(args["number"])
                elif name == "search_the_web":
                    result = search_the_web(args["query"])
                elif name == "current_time":
                    result = current_time()
                else:
                    result = "Unknown tool."

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            print(f"\nARIA: {msg.content}\n")
            messages.append({"role": "assistant", "content": msg.content})
            break