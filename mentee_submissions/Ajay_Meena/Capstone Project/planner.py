import os
import json
import time
import ast
import re
from groq import Groq
from groq import RateLimitError
from dotenv import load_dotenv
from tools import dispatch_tool, TOOLS_SCHEMA

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile" 
PLAN_FILE = "plan.json"


def call_llm(messages, tools=None, response_format=None, max_retries=5):
    """Call Groq API with automatic retries for rate limits."""
    delay = 2
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": MODEL, 
                "messages": messages,
                "max_tokens": 4000
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            if response_format:
                kwargs["response_format"] = response_format
                
            return client.chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            print(f"  [rate limited, backing off {delay}s...]")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("exhausted retries")


def load_plan():
    if not os.path.exists(PLAN_FILE):
        return {}
    try:
        with open(PLAN_FILE, "r") as f:
            data = json.load(f)
            return data if data else {}
    except:
        return {}


def save_plan(plan):
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)


def make_plan(goal: str):
    print("\n[Planning...]\n")
    
    messages = [
        {"role": "system", "content": "You are a planning assistant. You must respond in valid JSON format only. Do not include markdown."},
        {"role": "user", "content": f"""Break this goal into 4 to 6 ordered steps. Each step must be a single, self-contained task.

Goal: {goal}

Return exactly this format:
[
  {{"id": 1, "task": "...", "status": "pending", "result": null}},
  {{"id": 2, "task": "...", "status": "pending", "result": null}}
]"""}
    ]

    response = call_llm(messages)
    raw_original = response.choices[0].message.content.strip()

    raw = re.sub(r'<think>.*?</think>', '', raw_original, flags=re.DOTALL).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    if "[" in raw and "]" in raw:
        raw = raw[raw.find("[") : raw.rfind("]") + 1]

    try:
        steps = json.loads(raw)
    except json.JSONDecodeError:
        try:
            steps = ast.literal_eval(raw)
            if not isinstance(steps, list):
                steps = []
        except Exception:
            print("  [Failed to parse JSON. Falling back to empty plan.]")
            steps = []

    plan = {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": steps
    }

    save_plan(plan)
    print(f"[Plan created with {len(steps)} steps]\n")
    return plan


def build_step_context(plan, step, persona):
    # Removed the strict warning that was confusing the model
    messages = [{"role": "system", "content": persona}]
    messages.append({"role": "user", "content": f"Overall goal: {plan['goal']}"})

    prev_id = step["id"] - 1
    if prev_id >= 1:
        prev = next((s for s in plan["steps"] if s["id"] == prev_id), None)
        if prev and prev["result"]:
            summary = prev["result"][:300]
            messages.append({"role": "user", "content": f"Previous step result: {summary}"})

    messages.append({"role": "user", "content": f"Now execute this step and nothing else:\n{step['task']}"})
    return messages


def extract_leaked_query(text):
    """Regex to find a tool query even if the LLM hallucinates the formatting."""
    match = re.search(r'"query"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    return None


def execute_step(plan, step, persona):
    print(f"\n[Step {step['id']}] {step['task']}")

    step["status"] = "in_progress"
    save_plan(plan)

    messages = build_step_context(plan, step, persona)

    while True:
        try:
            response = call_llm(messages, tools=TOOLS_SCHEMA)
        except Exception as e:
            err_msg = str(e).replace("'", '"')
            
            # INTERCEPTOR 1: Catch 400 Errors (<function=...> syntax bugs)
            query = extract_leaked_query(err_msg)
            if query:
                print(f"  [Auto-Correcting API Error -> Running Tool: search_the_web]")
                result = dispatch_tool("search_the_web", {"query": query})
                messages.append({"role": "user", "content": f"Web search results for '{query}':\n{result}\nNow provide the final plain-text answer for this step."})
                continue
            
            print(f"  [API error: Retrying without tools...]")
            try:
                response = call_llm(messages)
            except Exception as fallback_e:
                step["result"] = f"Step failed: {str(fallback_e)}"
                step["status"] = "done"
                save_plan(plan)
                return

        msg = response.choices[0].message
        content = msg.content or ""

        if msg.tool_calls:
            messages.append(msg.model_dump(exclude_unset=True))

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                print(f"  [Tool: {name}]")
                result = dispatch_tool(name, args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # INTERCEPTOR 2: Catch LLM leaking the JSON into the text content
            if "search_the_web" in content or "query" in content:
                query = extract_leaked_query(content)
                if query:
                    print(f"  [Auto-Correcting LLM syntax -> Running Tool: search_the_web]")
                    result = dispatch_tool("search_the_web", {"query": query})
                    
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"Web search results for '{query}':\n{result}\nNow provide the final plain-text answer for this step."})
                    continue

            result_text = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            print(f"  [Result]: {result_text}")

            step["result"] = result_text
            step["status"] = "done"
            plan["current_step"] = step["id"] + 1
            save_plan(plan)
            return


def run_loop(plan, persona):
    while True:
        pending = [s for s in plan["steps"] if s["status"] != "done"]

        if not pending:
            plan["status"] = "done"
            save_plan(plan)
            print("\n" + "="*50)
            print("All steps complete.\n")
            break

        step = pending[0]
        execute_step(plan, step, persona)
        plan = load_plan()