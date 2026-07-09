"""
Capstone: The Planner Agent
State-driven orchestration agent. Decomposes a goal into sequential steps,
saves them to plan.json, and executes them with a self-healing ReAct loop.
"""

import sys
import io

# Force UTF-8 stdout encoding on Windows to prevent UnicodeEncodeError
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import time
import re
import requests
from dotenv import load_dotenv
from groq import Groq
from groq import RateLimitError

PLAN_FILE = "plan.json"
MODEL = "llama-3.3-70b-versatile"

PLANNER_PERSONA = (
    "You are Reginald, a direct, concise, and highly efficient project manager. "
    "You speak in short, professional sentences, focused strictly on the tasks at hand. "
    "You address the user formally. No fluff, conversational pleasantries, or unnecessary explanations."
)


def load_plan():
    """Loads the plan from plan.json. Returns empty dict if file is missing, empty, or invalid."""
    if not os.path.exists(PLAN_FILE):
        return {}
    try:
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception as e:
        print(f"[!] Warning: Failed to load plan: {e}")
        return {}


def save_plan(plan):
    """Atomically saves the plan to plan.json to prevent corruption on interrupt."""
    temp_file = PLAN_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
        # Replace the original file atomically
        if os.path.exists(PLAN_FILE):
            os.remove(PLAN_FILE)
        os.rename(temp_file, PLAN_FILE)
    except Exception as e:
        print(f"[!] Error saving plan: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


def call_llm(client, messages, tools=None, max_retries=5):
    """One Groq call, hardened against HTTP 429 with exponential backoff and Retry-After header parsing."""
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
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # give up after the last attempt
            
            # Stretch: Attempt to parse retry delay from header
            wait_time = None
            try:
                if hasattr(e, 'response') and e.response is not None:
                    headers = e.response.headers
                    for header_key in ['retry-after', 'Retry-After', 'x-ratelimit-reset']:
                        if header_key in headers:
                            val = headers[header_key]
                            if val.replace('.', '', 1).isdigit():
                                wait_time = float(val)
                                break
            except Exception:
                pass
            
            if wait_time is None:
                wait_time = delay
                delay *= 2
            
            print(f"    [!] Rate-limited (429). Backing off for {wait_time:.2f}s...")
            time.sleep(wait_time)
            
        except Exception:
            raise
    raise RuntimeError("Exhausted all retries for LLM call.")


def search_the_web(query: str) -> str:
    """Search DuckDuckGo using requests and return text summary of results."""
    print(f"  🔍 Searching web for: '{query}'")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # Try parsing using BeautifulSoup if available
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            results = []
            for item in soup.select('.result')[:5]:
                title_el = item.select_one('.result__a')
                snippet_el = item.select_one('.result__snippet')
                if title_el:
                    title = title_el.get_text(strip=True)
                    link = title_el.get('href', '')
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append(f"Title: {title}\nURL: {link}\nSnippet: {snippet}")
            if results:
                return "\n\n---\n\n".join(results)
        except Exception:
            pass
            
        # Fallback to regex parsing if bs4 is missing or failed
        titles = re.findall(r'<a class="result__a" href="([^"]+)">([^<]+)</a>', resp.text)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>([^<]+)</a>', resp.text)
        results = []
        for i, (link, title) in enumerate(titles[:5]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append(f"Title: {title.strip()}\nURL: {link}\nSnippet: {snippet.strip()}")
            
        if results:
            return "\n\n---\n\n".join(results)
        return "No results found (or page structure changed)."
    except Exception as e:
        print(f"    [!] Requests search failed: {e}. Trying Playwright fallback...")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=15000)
                
                results = []
                result_elements = page.query_selector_all(".result")
                for elem in result_elements[:5]:
                    title_el = elem.query_selector(".result__a")
                    snippet_el = elem.query_selector(".result__snippet")
                    
                    title = title_el.inner_text() if title_el else "No title"
                    link = title_el.get_attribute("href") if title_el else ""
                    snippet = snippet_el.inner_text() if snippet_el else "No snippet"
                    results.append(f"Title: {title}\nURL: {link}\nSnippet: {snippet}")
                browser.close()
                if results:
                    return "\n\n---\n\n".join(results)
        except Exception as pe:
            return f"Search failed under both requests and Playwright. Error: {pe}"
        return f"Search failed: {str(e)}"


def run_tool(name, args):
    """Dispatches a tool call to the actual implementation."""
    if name == "search_the_web":
        return search_the_web(args.get("query", ""))
    elif name == "write_file":
        filename = args.get("filename", "")
        content = args.get("content", "")
        # Safety: restrict writing to current directory only
        filename = os.path.basename(filename)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File '{filename}' successfully written."
        except Exception as e:
            return f"Failed to write file '{filename}': {str(e)}"
    elif name == "read_file":
        filename = os.path.basename(args.get("filename", ""))
        try:
            if not os.path.exists(filename):
                return f"File '{filename}' not found."
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Failed to read file '{filename}': {str(e)}"
    return f"Tool '{name}' is not recognized."


tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the web using DuckDuckGo. Use this to search for current data, schedules, or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with text content. Use this to save reports, timetables, logs, or results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename (e.g. 'schedule.txt')."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete text content to write to the file."
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename to read."
                    }
                },
                "required": ["filename"]
            }
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "write_file": lambda filename, content: run_tool("write_file", {"filename": filename, "content": content}),
    "read_file": lambda filename: run_tool("read_file", {"filename": filename})
}


def build_step_context(plan, step):
    """Minimal prompt context — bounded token cost no matter how long the plan is."""
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user", "content": f"Overall goal: {plan['goal']}"},
    ]
    # Fetch the previous step
    prev_step = None
    if step["id"] > 1:
        for s in plan["steps"]:
            if s["id"] == step["id"] - 1:
                prev_step = s
                break
                
    if prev_step and prev_step.get("result"):
        summary = prev_step["result"][:300]  # cap it — one step back, trimmed
        messages.append({
            "role": "user",
            "content": f"Result of the previous step: {summary}"
        })
        
    messages.append({
        "role": "user",
        "content": f"Now do exactly this step, nothing else:\n{step['task']}"
    })
    return messages


def execute_step_with_react(client, step_messages, max_iterations=5):
    """Executes a single step using a ReAct loop (Reason -> Act -> Observe)."""
    messages = list(step_messages)
    
    for iteration in range(max_iterations):
        print(f"    [Brain] Iteration {iteration + 1}/{max_iterations}")
        msg = None
        
        try:
            response = call_llm(client, messages, tools=tools)
            msg = response.choices[0].message
        except Exception as e:
            error_msg = str(e)
            print(f"    [!] Error during API call: {error_msg[:150]}")
            
            # Self-healing parser for tool_use_failed (Groq Llama 3 XML bug)
            if "tool_use_failed" in error_msg:
                failed_gen = ""
                if hasattr(e, 'body') and isinstance(e.body, dict) and 'error' in e.body:
                    failed_gen = e.body['error'].get('failed_generation', '')
                if not failed_gen:
                    match_err = re.search(r"'failed_generation':\s*'([^']+)'", error_msg)
                    if match_err:
                        failed_gen = match_err.group(1)
                
                print(f"    [*] Attempting self-healing parse on failed generation: {failed_gen}")
                match_fn = re.search(r'<function=(\w+)(.*?)</function>', failed_gen)
                if match_fn:
                    fn_name = match_fn.group(1)
                    fn_args_str = match_fn.group(2).strip()
                    
                    print(f"    [Self-Heal] Extracted tool: {fn_name} with args: {fn_args_str}")
                    try:
                        fn_args = json.loads(fn_args_str)
                    except Exception:
                        if fn_args_str.startswith('"') and fn_args_str.endswith('"'):
                            fn_args_str = fn_args_str[1:-1]
                        fn_args = {"query": fn_args_str}
                    
                    # Execute tool
                    result = run_tool(fn_name, fn_args)
                    
                    # Append mock tool call assistant message
                    mock_id = f"call_heal_{iteration}_{fn_name}"
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": mock_id,
                                "type": "function",
                                "function": {
                                    "name": fn_name,
                                    "arguments": json.dumps(fn_args)
                                }
                            }
                        ]
                    })
                    # Append tool response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": mock_id,
                        "content": result
                    })
                    continue  # recovered and advanced to next loop iteration
            
            # Fallback to direct prompt without tools
            print("    [*] Falling back to direct prompt without tools...")
            try:
                response = call_llm(client, messages, tools=None)
                msg = response.choices[0].message
            except Exception as ex:
                print(f"    [!] Fallback failed: {ex}")
                return f"Execution failed: {str(e)}"
                
        if not msg:
            continue
            
        # Process regular tool calls
        if msg.tool_calls:
            messages.append(msg)
            
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"    🔧 Tool: {fn_name}({fn_args})")
                
                result = run_tool(fn_name, fn_args)
                print(f"    📄 Got {len(result)} chars of results")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # Model returned direct text response (final answer of this step)
            print(f"    🤖 Output: {msg.content[:150]}...")
            return msg.content
            
    # Fallback summary if we ran out of iterations
    print("    [!] ReAct loop limit reached. Summarizing...")
    messages.append({"role": "user", "content": "Please summarize what you've found and present your final answer for this step now."})
    try:
        response = call_llm(client, messages, tools=None)
        return response.choices[0].message.content
    except Exception as e:
        return f"ReAct execution summary failed: {str(e)}"


def make_plan(client, goal):
    """Queries Groq to decompose the big goal into ordered sub-tasks."""
    print(f"📝 Decomposing goal: '{goal}'")
    system_instruction = (
        "You are a strict task planner. Your role is to decompose a large overall goal into a list of self-contained, ordered, sequential steps. "
        "Each step must be a single actionable task that can be completed using a web search, file writing, or text reasoning. "
        "Output ONLY a raw JSON array of strings, where each string is a task. "
        "No conversational text. No markdown fences. No explanation. "
        "Example output: [\"Find the current price of Bitcoin\", \"Convert that price to EUR\", \"Write a report to bitcoin_report.txt\"]"
    )
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Decompose this goal: '{goal}'"}
    ]
    
    response = call_llm(client, messages)
    content = response.choices[0].message.content.strip()
    
    # Strip markdown fences if present
    if content.startswith("```"):
        start_idx = content.find("[")
        end_idx = content.rfind("]")
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx+1]
            
    try:
        tasks = json.loads(content)
        if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
            return tasks
    except Exception as e:
        print(f"    [!] Failed to parse plan JSON: {e}. Raw content: {content}")
        # Manual fallback line parsing
        lines = content.split("\n")
        tasks = []
        for line in lines:
            line = line.strip()
            match = re.match(r"^(?:\d+[\.\)]|-|\*)\s*(.*)$", line)
            if match:
                task_text = match.group(1).strip()
                if (task_text.startswith('"') and task_text.endswith('"')) or (task_text.startswith("'") and task_text.endswith("'")):
                    task_text = task_text[1:-1]
                if task_text:
                    tasks.append(task_text)
            elif line:
                tasks.append(line)
        if tasks:
            return tasks
            
    # Emergency fallback plan
    return [
        f"Research and gather information related to '{goal}'",
        f"Synthesize the research and write a final report to '{goal.lower().replace(' ', '_')}_report.txt'"
    ]


def main():
    # Load API key
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ Error: GROQ_API_KEY environment variable is not set in .env")
        sys.exit(1)
        
    client = Groq(api_key=api_key)
    
    # 1. Load plan
    plan = load_plan()
    
    # 2. Check if a plan is already in progress
    if not plan or not plan.get("goal"):
        print("🤖 Welcome to the Planner Agent!")
        goal = input("👉 Enter your overall goal: ").strip()
        if not goal:
            print("❌ Error: Goal cannot be empty.")
            sys.exit(1)
            
        tasks = make_plan(client, goal)
        print(f"📋 Generated {len(tasks)} steps:")
        for idx, task in enumerate(tasks, 1):
            print(f"  {idx}. {task}")
            
        # Build initial plan.json
        plan = {
            "goal": goal,
            "status": "in_progress",
            "current_step": 1,
            "steps": [
                {
                    "id": idx,
                    "task": task,
                    "status": "pending",
                    "result": None
                }
                for idx, task in enumerate(tasks, 1)
            ]
        }
        save_plan(plan)
        print("💾 Plan saved to plan.json. Starting execution...\n")
    else:
        print(f"🔄 Resuming plan from plan.json!")
        print(f"🎯 Overall Goal: {plan['goal']}")
        print(f"📈 Resuming at Step {plan['current_step']}/{len(plan['steps'])}")
        print(f"📝 Next Task: {plan['steps'][plan['current_step'] - 1]['task']}")
        print("-" * 60 + "\n")

    # 3. Main execution loop
    while plan["status"] == "in_progress":
        curr_step_idx = plan["current_step"] - 1
        steps = plan["steps"]
        
        if curr_step_idx >= len(steps):
            plan["status"] = "done"
            save_plan(plan)
            break
            
        curr_step = steps[curr_step_idx]
        print(f"🚀 Working on Step {curr_step['id']}/{len(steps)}: {curr_step['task']}")
        
        # Update status to in_progress
        curr_step["status"] = "in_progress"
        save_plan(plan)
        
        # Build prompt context
        step_messages = build_step_context(plan, curr_step)
        
        # Execute the step
        result = execute_step_with_react(client, step_messages)
        
        # Update step details
        curr_step["result"] = result
        curr_step["status"] = "done"
        
        # Advance current step
        plan["current_step"] += 1
        
        # If all steps are done, mark the overall plan done
        if plan["current_step"] > len(steps):
            plan["status"] = "done"
            
        save_plan(plan)
        print(f"✅ Completed Step {curr_step['id']}! State flushed to plan.json.\n")
        print("=" * 60 + "\n")
        
        # Brief pause to avoid hammering API
        time.sleep(2)
        
    print("🎉 All tasks completed!")
    print("\nSummary of results:")
    for step in plan["steps"]:
        print(f"📌 Step {step['id']}: {step['task']}")
        res_summary = step['result'][:150] + "..." if step['result'] and len(step['result']) > 150 else step['result']
        print(f"   Result: {res_summary}\n")


if __name__ == "__main__":
    main()
