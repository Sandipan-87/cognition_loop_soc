import os
import re
import json
import time
# import asyncio
from dotenv import load_dotenv
from groq import Groq, RateLimitError
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────
# 1. SETUP & CONFIGURATION
# ─────────────────────────────────────────────────────────────────
load_dotenv()
# MODEL = "llama-3.3-70b-versatile"
MODEL = "llama-3.1-8b-instant"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAN_FILE = os.path.join(BASE_DIR, "plan.json")
DATASET_FILE = os.path.join(BASE_DIR, "dataset_metadata.json")

_client = None

def get_client() -> Groq:
    """Return the singleton Groq client, initializing on demand."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("CRITICAL: GROQ_API_KEY missing from environment setup.")
        _client = Groq(api_key=api_key)
    return _client

# ─────────────────────────────────────────────────────────────────
# 2. STATE LAYER (Pure Disk I/O Transactional System)
# ─────────────────────────────────────────────────────────────────

def load_plan() -> dict:
    """Read plan.json from disk. Safely defaults on corruption/absence."""
    print("Current working directory:", os.getcwd())
    print("Looking for:", os.path.abspath(PLAN_FILE))
    if not os.path.exists(PLAN_FILE):
        return {}
    with open(PLAN_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"[WARN] {PLAN_FILE} was corrupt. Re-initializing environment matrix.")
            return {}

def save_plan(plan: dict) -> None:
    """Write plan to plan.json via atomic file replacement to avoid corruption."""
    tmp_path = PLAN_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(plan, f, indent=2)
    os.replace(tmp_path, PLAN_FILE)

def get_step(plan: dict, step_id: int):
    """Retrieve a step dictionary by its absolute numerical ID index."""
    for step in plan.get("steps", []):
        if step["id"] == step_id:
            return step
    return None

# ─────────────────────────────────────────────────────────────────
# 3. API RELIABILITY SHIELD (Exponential Backoff Loop)
# ─────────────────────────────────────────────────────────────────

def call_llm(messages, tools=None, max_retries=5):
    """Executes Groq calls protected against HTTP 429 rate limit exceptions."""
    delay = 2

    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": MODEL,
                "messages": messages,
                "temperature": 0.15
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            return get_client().chat.completions.create(**kwargs)

        except RateLimitError as e:
            error_text = str(e).lower()

            # DAILY TOKEN LIMIT
            if "tokens per day" in error_text or "tpd" in error_text:
                print("\n❌ DAILY TOKEN LIMIT EXHAUSTED")
                print("Resume execution tomorrow or upgrade your Groq tier.")
                return None

            # Retry-After header
            sleep_time = delay

            if hasattr(e, "response") and e.response is not None:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_time = float(retry_after)
                    except:
                        pass

            print(f"\n⚠️ Rate limited. Sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)
            delay *= 2

    raise RuntimeError("Maximum retries exceeded.")

# ─────────────────────────────────────────────────────────────────
# 4. HANDS ORGAN (Playwright Web Automation Framework)
# ─────────────────────────────────────────────────────────────────

def read_local_dataset_metadata(file_path: str = "dataset_metadata.json") -> str:
    """Reads structured local data science parameters, feature lists, and performance metrics from disk."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # FIX: Ensure we use the absolute path relative to the script directory
    full_path = os.path.join(BASE_DIR, os.path.basename(file_path))
    
    print(f"  📊 [Tool] Extracting optimization parameters from local storage node: '{full_path}'...")
    try:
        if not os.path.exists(full_path):
            return f"Error: Target data vector path '{full_path}' does not exist on local disk."
        
        with open(full_path, "r") as f:
            print("Dataset metadata loaded successfully.")
            data = json.load(f)
            return json.dumps(data, indent=2)
    except Exception as e:
        return f"File layer exception: {str(e)}"


def search_the_web(query: str) -> str:
    """Uses a headless browser context to fetch targeted documentation from DuckDuckGo."""
    print(f"  🌐 [Tool] Scanning external web nodes for: '{query}'...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}", timeout=15000)
            
            results = []
            rows = page.locator(".result__body").all()
            for row in rows[:5]:
                title = row.locator(".result__title").inner_text().strip()
                snippet = row.locator(".result__snippet").inner_text().strip()
                results.append(f"• Title: {title}\n  Snippet: {snippet}")
            
            browser.close()
            return "\n\n".join(results) if results else "No documentation vectors found."
    except Exception as e:
        return f"Web search tool exception: {str(e)}"

def open_page(url: str) -> str:
    print(f"  📖 Opening {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            response = page.goto(url, timeout=20000)

            if response is None:
                browser.close()
                return "No response received."

            if response.status != 200:
                browser.close()
                return f"HTTP Error {response.status}"

            body = page.inner_text("body")
            browser.close()
            return " ".join(body.split())[:2500]
    except Exception as e:
        return str(e)
    

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_local_dataset_metadata",
            "description": "Reads local structural parameters, sample record metadata counts, feature allocations, and validation score sets from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The exact location path of the parameters json file (defaults to 'dataset_metadata.json')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Scans the web for technical documentation, advanced ML methods, and framework specifications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The specific query string to search."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Fetches raw text content from a target URL link for technical summary processing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The exact target URL string."}
                },
                "required": ["url"]
            }
        }
    }
]

available_tools = {
    "read_local_dataset_metadata": read_local_dataset_metadata,
    "search_the_web": search_the_web,
    "open_page": open_page
}
tool_cache = {}

# ─────────────────────────────────────────────────────────────────
# 5. VOICE & PERSONA SCHEMA
# ─────────────────────────────────────────────────────────────────

MATRIX_PERSONA = """
You are MATRIX, an expert Machine Learning Engineer.
You analyze datasets and baseline metrics before making recommendations.

Rules:
1. Never explain what XGBoost, LightGBM or CatBoost are.
2. Never give textbook definitions.
3. Every recommendation MUST reference values from dataset_metadata.json.
4. If ROC-AUC > 0.80, recommend only advanced tuning.
5. If class balance is between 45% and 55%, never recommend oversampling or undersampling.
6. If dataset size > 50,000, prefer Bayesian Optimization or Optuna over GridSearch.
7. Give exact hyperparameter recommendations whenever possible.
8. Produce concise engineering recommendations.
9. Do not repeat information from previous steps.

End every final report with:
Current baseline
Issues detected
Recommended changes
Expected improvement
"""

DECOMPOSER_PROMPT = """
You are an ML project planner.
Break the user's goal into exactly five sequential engineering tasks.

The tasks should be:
1. Inspect dataset metadata.
2. Diagnose current model performance.
3. Gather only relevant information from official documentation.
4. Recommend concrete hyperparameter changes.
5. Produce a final optimization report.

Return ONLY a JSON array.
"""

def extract_json(text: str):
    """Cleans up raw textual outputs to ensure strict JSON array parsing."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    return json.loads(text)

# ─────────────────────────────────────────────────────────────────
# 6. PLANNER & CONTEXT BOUNDERS
# ─────────────────────────────────────────────────────────────────

def make_plan(goal: str) -> dict:
    """Generates the master plan map, allocating pending steps into plan.json."""
    resp = call_llm([
        {"role": "system", "content": DECOMPOSER_PROMPT},
        {"role": "user", "content": f"Master Pipeline Target: {goal}"}
    ])
    
    raw = resp.choices[0].message.content
    try:
        steps_raw = extract_json(raw)
    except Exception:
        steps_raw = [{"id": 1, "task": "Verify local dataset integrity and configuration vectors."}]
        
    if isinstance(steps_raw, dict):
        for val in steps_raw.values():
            if isinstance(val, list):
                steps_raw = val
                break
                
    clean_steps = []
    for i, s in enumerate(steps_raw, 1):
        task_text = s.get("task", str(s)) if isinstance(s, dict) else str(s)
        clean_steps.append({
            "id": i,
            "task": task_text,
            "status": "pending",
            "result": None
        })
        
    plan = {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": clean_steps
    }
    save_plan(plan)
    return plan

def build_step_context(plan: dict, step: dict) -> list:
    """Assembles a highly bounded short message history context window."""
    messages = [
        {"role": "system", "content": MATRIX_PERSONA},
        {
            "role": "user",
            "content": f"Master Goal:\n{plan['goal']}\n\nAvailable local files:\n- dataset_metadata.json\nNever request any other filenames."
        }
    ]
    
    # FIX: Feed all previous results in full instead of cutting off at 180 chars. 
    # This prevents the model from forgetting data found in early steps.
    for i in range(1, step["id"]):
        prev_step = get_step(plan, i)
        if prev_step and prev_step["result"]:
            messages.append({
                "role": "user", 
                "content": f"Result from Step {i} [{prev_step['task']}]:\n{prev_step['result']}"
            })
        
    messages.append({
        "role": "user",
        "content": f"Execute this target task exactly. Embody the MATRIX persona throughout the answer output:\n{step['task']}"
    })
    return messages

# ─────────────────────────────────────────────────────────────────
# 7. EXECUTOR (Inner ReAct Functional Call Loop)
# ─────────────────────────────────────────────────────────────────

def execute_step(plan: dict, step: dict) -> str:
    """Runs one planning step using a bounded ReAct loop with strict tool parsing protections."""
    step["status"] = "in_progress"
    save_plan(plan)

    messages = build_step_context(plan, step)
    MAX_TOOL_CALLS = 10
    tool_calls = 0
    executed_tools = set()

    while True:
        try:
            resp = call_llm(messages, tools=tools)
        except Exception as e:
            # Catch API-level tool errors out of the box and give the agent a graceful way to recover
            if "tool_use_failed" in str(e) or "Failed to call a function" in str(e):
                print("\n⚠️ API rejected tool call structure. Forcing model fallback to reason with current state...")
                messages.append({
                    "role": "user",
                    "content": "The tool call failed due to formatting constraints. Proceed immediately using only the information you already possess."
                })
                continue
            raise e

        if resp is None:
            return "__TOKEN_LIMIT_REACHED__"

        msg = resp.choices[0].message
        messages.append(msg)

        # LLM has finished reasoning or chosen not to invoke further tools
        if not msg.tool_calls:
            return msg.content

        for tc in msg.tool_calls:
            tool_calls += 1
            if tool_calls > MAX_TOOL_CALLS:
                print("\n⚠ Maximum tool calls reached.")
                messages.append({
                    "role": "user",
                    "content": "Maximum tool calls reached. Output your definitive engineering findings now."
                })
                continue

            fn_name = tc.function.name
            fn_args = {}

            if tc.function.arguments:
                try:
                    parsed = json.loads(tc.function.arguments)
                    if isinstance(parsed, dict):
                        fn_args = parsed
                except Exception:
                    pass

            cache_key = (fn_name, json.dumps(fn_args, sort_keys=True))

            if cache_key in executed_tools:
                print(f"  ⚡ Duplicate tool call skipped: {fn_name}")
                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": "This tool has already been executed in this step. Proceed with previous outputs."
                })
                continue

            executed_tools.add(cache_key)
            print(f"  📊 [MATRIX REACT ROUTER] Calling: {fn_name}({fn_args})")

            if cache_key in tool_cache:
                print("  ⚡ Using cached tool result.")
                result = tool_cache[cache_key]
            else:
                try:
                    result = available_tools[fn_name](**fn_args)
                    tool_cache[cache_key] = result
                except Exception as tool_ex:
                    result = f"Tool execution failed internally: {str(tool_ex)}"

            messages.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "name": fn_name,
                "content": str(result)
            })
            print(f"  ✅ Tool '{fn_name}' completed.")

        # Cleaned guidance instruction: safe string format that will not break tool execution state
        messages.append({
            "role": "user",
            "content": "Review the latest tool outputs. Synthesize your final answer if execution parameters are met."
        })


# ─────────────────────────────────────────────────────────────────
# 8. STATE MACHINE INTERFACE
# ─────────────────────────────────────────────────────────────────

def run():
    """Drives the programmatic outer state machine loop interface."""
    # Tip: Delete your old plan.json to force a clean re-execution with the fixes applied
    plan = load_plan()

    if not plan or "steps" not in plan:
        print("Fallback prompt set to MLOps Tuning Pipeline Scenario...")
        default_goal = (
            "Analyze local dataset metadata and baseline model metrics stored in dataset_metadata.json, "
            "Search official documentation and trusted technical sources for:"
            "- XGBoost hyperparameter tuning"
            "- LightGBM optimization"
            "- CatBoost optimization"
            "- ROC-AUC improvement"
            "adjust training configurations, and generate an optimization execution plan."
        )
        print(f"\nTarget Master Goal Vector: \n{default_goal}\n")
        
        print("[MATRIX CORE]: Constructing optimization matrices...")
        plan = make_plan(default_goal)
        print(f"[MATRIX CORE]: Plan logged cleanly — {len(plan['steps'])} parameters active:\n")
        for s in plan["steps"]:
            print(f"  [{s['id']}] {s['task']}")
        print()
    else:
        done_count = sum(1 for s in plan["steps"] if s["status"] == "done")
        in_prog = [s for s in plan["steps"] if s["status"] == "in_progress"]
        print(f"\n📉 [MATRIX RESUME NODE]: Active Pipeline Found: '{plan['goal'][:60]}...'")
        print(f"         Execution Progress State: {done_count}/{len(plan['steps'])} parameters completed.")
        if in_prog:
            print(f"         Restoring interrupted worker step: Node [{in_prog[0]['id']}]")
        print()
        
    while True:
        pending = [s for s in plan["steps"] if s["status"] != "done"]
        
        if not pending:
            plan["status"] = "done"
            save_plan(plan)
            print("\n📈 [MATRIX CORE]: Master convergence achieved. Verification logs:\n")
            print("=" * 65)
            for s in plan["steps"]:
                print(f"  [{s['id']}] {s['task']}")
                if s["result"]:
                    print("       ↳ Result:")
                    print(s["result"])
                    print("-" * 60)
            print("=" * 65)
            break
            
        step = pending[0]
        total = len(plan["steps"])
        print(f"\n📉 [MATRIX PIPELINE WORKER] Running Step {step['id']}/{total}:\n👉 {step['task']}")
        
        try:
            result = execute_step(plan, step)
        except Exception as e:
            save_plan(plan)
            print(f"\nExecution interrupted:\n{e}")
            break

        if result == "__TOKEN_LIMIT_REACHED__":
            print("\n🛑 Execution paused.")
            print("Current progress already saved in plan.json.")
            print("Run again after Groq quota resets.")
            break
                
        print("\n" + "=" * 70)
        print(f"📄 RESULT OF STEP {step['id']}")
        print("=" * 70)
        print(result)
        print("=" * 70 + "\n")

        step["result"] = result
        step["status"] = "done"
        plan["current_step"] = step["id"] + 1
        save_plan(plan)
        
        print(f"✓ [MATRIX CORE]: Step {step['id']} metrics verified and successfully saved to disk state.")

if __name__ == "__main__":
    run()