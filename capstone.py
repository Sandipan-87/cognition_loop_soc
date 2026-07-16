import json
import os
import time
from dotenv import load_dotenv
from groq import Groq, RateLimitError

# Load environment variables
load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

PLAN_FILE = "plan.json"

def save_plan(plan_data, filename=PLAN_FILE):
    """Flushes the current state to disk."""
    with open(filename, 'w') as f:
        json.dump(plan_data, f, indent=2)
    print(f"[*] State successfully saved to {filename}")

def load_plan(filename=PLAN_FILE):
    """Loads the state from disk."""
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as f:
        return json.load(f)

def make_plan(goal):
    """Calls Groq to break a goal into steps, forcing JSON output."""
    print(f"\n[*] Asking Groq to plan: '{goal}'...")
    
    prompt = f"""You are an autonomous planning agent. Break the following goal into a sequential list of 3 distinct, actionable steps.
    
    CRITICAL: Respond with ONLY a raw JSON array of objects. Do not include markdown formatting, backticks, or any conversational text.
    Each object must have exactly two keys: "id" (integer starting at 1) and "task" (string).
    
    Goal: {goal}"""
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    raw_text = response.choices[0].message.content.strip()
    
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:-3].strip()
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:-3].strip()
        
    try:
        tasks = json.loads(raw_text)
    except json.JSONDecodeError:
        print("[-] Error: Groq did not return valid JSON.")
        return
        
    plan_state = {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": []
    }
    
    for task in tasks:
        plan_state["steps"].append({
            "id": task["id"],
            "task": task["task"],
            "status": "pending",
            "result": None
        })
        
    save_plan(plan_state)
    print("[*] Planning complete. Initial state written to disk.")

def call_llm_with_backoff(messages, max_retries=5):
    """One Groq call, hardened against HTTP 429 with exponential backoff."""
    delay = 2
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.5
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            print(f"\n[-] Rate-limited (429). Backing off {delay}s...")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("Exhausted retries")

def build_step_context(plan, step):
    """Minimal prompt context — bounded token cost no matter how long the plan is."""
    messages = [
        {"role": "system", "content": "You are a focused execution agent. Complete the task given to you and return ONLY the result of your work. Be concise."},
        {"role": "user", "content": f"Overall goal: {plan['goal']}"},
    ]
    
    # Get previous step if it exists
    prev_step = next((s for s in plan['steps'] if s['id'] == step['id'] - 1), None)
    if prev_step and prev_step.get("result"):
        summary = prev_step["result"][:300]
        messages.append({"role": "user", "content": f"Result of the previous step: {summary}"})
        
    messages.append({"role": "user", "content": f"Now do exactly this step, nothing else:\n{step['task']}"})
    return messages

def run_agent():
    """The main execution loop."""
    print("--- Starting Agent Loop ---")
    plan = load_plan()
    
    # If no plan exists, prompt for one
    if not plan or plan.get("status") == "done":
        goal = input("\nEnter your big goal: ")
        make_plan(goal)
        plan = load_plan()
        
    while True:
        # Find first step whose status is not "done"
        current_step = next((s for s in plan['steps'] if s['status'] != "done"), None)
        
        if not current_step:
            print("\n[+] All steps completed! Goal achieved.")
            plan['status'] = "done"
            save_plan(plan)
            break
            
        print(f"\n---> Executing Step {current_step['id']}: {current_step['task']}")
        
        # Mark as in_progress and save BEFORE executing (so we know where we crashed if interrupted)
        current_step['status'] = "in_progress"
        save_plan(plan)
        
        # Execute the step
        messages = build_step_context(plan, current_step)
        result = call_llm_with_backoff(messages)
        
        print(f"Result: {result[:150]}... (truncated)")
        
        # Save result, mark done, advance current_step
        current_step['result'] = result
        current_step['status'] = "done"
        plan['current_step'] = current_step['id'] + 1
        
        save_plan(plan)
        
        # Small delay so you can easily hit Ctrl-C during testing
        time.sleep(3) 

if __name__ == "__main__":
    run_agent()