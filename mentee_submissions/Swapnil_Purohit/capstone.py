import os
import json
import time
from dotenv import load_dotenv
from groq import Groq

# Attempt to import playwright for web search tools
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
# Using llama-3.1-8b-instant for stability with tool calling and json extraction,
# as the 70b model was problematic earlier with tool usage parsing.
MODEL = 'llama-3.1-8b-instant'

PLAN_FILE = "plan.json"
PLANNER_PERSONA = "You are an autonomous agent capable of solving complex tasks. You break down goals into logical, sequential steps, and then execute those steps one by one using tools when necessary. Keep your answers concise and focused."

# --- HARDENED LLM CALLER ---

def call_llm(messages, tools=None, max_retries=5, response_format=None):
    """One Groq call, hardened against HTTP 429 with exponential backoff."""
    delay = 2  # seconds
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": MODEL,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            if response_format:
                kwargs["response_format"] = response_format
                
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "429" in err_str:
                if attempt == max_retries - 1:
                    raise  # give up after the last attempt
                print(f"    rate-limited (429). backing off {delay}s...")
                time.sleep(delay)
                delay *= 2  # 2s -> 4s -> 8s -> 16s...
            else:
                raise e
    raise RuntimeError("exhausted retries")

# --- TOOLS ---

def search_the_web(query: str) -> str:
    """Search Wikipedia and return the text of the best matching page or search results."""
    if not sync_playwright:
        return "Error: Playwright not installed."
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
    if not sync_playwright:
        return "Error: Playwright not installed."
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

def current_time() -> str:
    """Return the exact current date and time."""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            "name": "current_time",
            "description": "Return the exact current date and time.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page,
    "current_time": current_time
}

# --- STATE MANAGEMENT ---

def load_plan() -> dict:
    if not os.path.exists(PLAN_FILE):
        return {}
    with open(PLAN_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_plan(plan: dict) -> None:
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)

def get_step(plan: dict, step_id: int):
    for step in plan.get("steps", []):
        if step["id"] == step_id:
            return step
    return None

# --- ORCHESTRATION ---

def make_plan(goal: str):
    """Call LLM to decompose the goal into an ordered JSON list of steps."""
    print(f"Creating plan for goal: {goal}")
    messages = [
        {"role": "system", "content": "You are an expert planner. Break down the user's goal into a logical, sequential list of actionable tasks. Output valid JSON in the exact structure requested, with no markdown code blocks."},
        {"role": "user", "content": f"Goal: {goal}\n\nReturn JSON with a single key 'steps' which is a list of objects. Each object must have an 'id' (integer starting from 1) and 'task' (string describing the action to take). Do not include any other text."}
    ]
    
    response = call_llm(messages, response_format={"type": "json_object"})
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        steps = data.get("steps", [])
    except json.JSONDecodeError:
        print("Error: Could not parse JSON plan.")
        steps = []
        
    plan = {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": []
    }
    
    for s in steps:
        plan["steps"].append({
            "id": s["id"],
            "task": s["task"],
            "status": "pending",
            "result": None
        })
        
    save_plan(plan)
    print(f"Plan saved to {PLAN_FILE} with {len(plan['steps'])} steps.")
    return plan

def build_step_context(plan, step):
    """Minimal prompt context - bounded token cost no matter how long the plan is."""
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user", "content": f"Overall goal: {plan['goal']}"},
    ]
    
    completed_results = []
    for s in plan["steps"]:
        if s["id"] < step["id"] and s["status"] == "done" and s.get("result"):
            res = str(s["result"])[:500] # Limit each result length slightly
            completed_results.append(f"Step {s['id']} Result: {res}")
            
    if completed_results:
        context_str = "\n".join(completed_results)
        messages.append({"role": "user", "content": f"Results of previously completed steps:\n{context_str}"})
        
    messages.append({"role": "user", "content": f"Now do exactly this step, nothing else:\n{step['task']}\n\nExecute any tools if necessary, then provide a final concise answer/result for this step."})
    return messages

def execute_step(plan, step):
    """The brain: execute a single step using tools and the ReAct loop."""
    print(f"\n--- Executing Step {step['id']}: {step['task']} ---")
    messages = build_step_context(plan, step)
    
    step["status"] = "in_progress"
    save_plan(plan)
    
    while True:
        try:
            response = call_llm(messages, tools=tools)
            msg = response.choices[0].message
            
            if msg.tool_calls:
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments) or {}
                    except Exception:
                        arguments = {}
                        
                    print(f"-> Tool Call: {function_name} {arguments}")
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
                # Reached a final answer for the step
                final_result = msg.content
                print(f"-> Step Result: {final_result}")
                return final_result
        except Exception as e:
            err_str = str(e)
            if "tool_use_failed" in err_str:
                print("-> LLM emitted malformed tool call. Instructing to retry...")
                messages.append({
                    "role": "user",
                    "content": "System Error: You emitted an invalid tool call format. Remember to output valid JSON arguments that match the exact schema. For tools with no parameters, use {}. Do not hallucinate tools."
                })
            else:
                raise e

def run_planner():
    plan = load_plan()
    
    # If the previous plan is completely finished, start fresh
    if plan and plan.get("status") == "done":
        plan = {}
        
    if not plan or not plan.get("goal"):
        goal = input("Enter the ultimate goal for the Agent: ").strip()
        if not goal:
            print("No goal provided. Exiting.")
            return
        plan = make_plan(goal)
        
    while True:
        # Find first step that is not "done"
        pending_step = None
        for step in plan["steps"]:
            if step["status"] != "done":
                pending_step = step
                break
                
        if not pending_step:
            print("\nAll steps completed! Goal achieved.")
            plan["status"] = "done"
            save_plan(plan)
            break
            
        # Execute the step
        result = execute_step(plan, pending_step)
        
        # Advance the state
        pending_step["result"] = result
        pending_step["status"] = "done"
        plan["current_step"] = pending_step["id"] + 1
        save_plan(plan)
        
        print("State saved. Moving to next step...")
        time.sleep(1) # brief pause before next step

if __name__ == "__main__":
    run_planner()
