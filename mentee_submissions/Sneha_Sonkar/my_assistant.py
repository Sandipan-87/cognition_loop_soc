import os
import asyncio
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"

MEMORY_FILE = "memory.json"
GOALS_FILE = "goals.json"

# =====================================================================
# PERSISTENCE CORE IMPLEMENTATIONS (MEMORY & QUEST LOG)
# =====================================================================

def _recall_list() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def remember(fact: str) -> str:
    """Save a strategic fact or preference about the user so it isn't forgotten."""
    memory = _recall_list()
    if fact not in memory:
        memory.append(fact)
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)
    return f"Success: Fact logged into long-term memory weights: '{fact}'"

def recall() -> str:
    """Return everything currently known about the user."""
    facts = _recall_list()
    return "\n".join(f"- {fact}" for fact in facts) if facts else "No prior state parameters found."

def _load_goals() -> list:
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_goals(goals: list) -> None:
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)

def add_goal(goal: str) -> str:
    """Log a new objective or task the user wants to pursue."""
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    return f"Success: Objective added to active constraints: '{goal}'"

def list_goals() -> str:
    """Show the user's active goals and check status."""
    goals = _load_goals()
    if not goals:
        return "Constraint matrix empty. No active objectives logged."
    lines = []
    for i, g in enumerate(goals, 1):
        mark = "x" if g["done"] else " "
        lines.append(f"{i}. [{mark}] {g['goal']}")
    return "\n".join(lines)

def complete_goal(number: int) -> str:
    """Mark the objective at the given index as completed/converged."""
    goals = _load_goals()
    try:
        idx = int(number) - 1
        if 0 <= idx < len(goals):
            goals[idx]["done"] = True
            _save_goals(goals)
            return f"Success: Objective converged perfectly: '{goals[idx]['goal']}'"
        return f"Error: Constraint index {number} out of bounds."
    except ValueError:
        return "Error: Invalid index format provided. Must be an integer."

# =====================================================================
# WEEK 3 PLAYWRIGHT TOOLS (ADAPTED)
# =====================================================================

async def search_the_web():
    """Scrapes the front page of Hacker News to find top trending tech news."""
    print("\n🌐 [Tool] Scanning Hacker News...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("https://news.ycombinator.com", timeout=15000)
            stories = await page.locator(".titleline > a").all()
            results = []
            for i, story in enumerate(stories[:5]):  # Kept concise for context protection
                title = await story.inner_text()
                link = await story.get_attribute("href")
                results.append({"rank": i + 1, "title": title, "url": link})
            await browser.close()
            return json.dumps(results)
        except Exception as e:
            await browser.close()
            return json.dumps({"error": f"Failed to scrape HN: {str(e)}"})

async def open_page(url: str):
    """Navigates to a specific URL, extracts raw body text, and truncates it."""
    print(f"\n📖 [Tool] Inspecting DOM elements at: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, timeout=20000)
            body_text = await page.locator("body").inner_text()
            await browser.close()
            cleaned_text = " ".join(body_text.split())
            return cleaned_text[:2500]
        except Exception as e:
            await browser.close()
            return json.dumps({"error": f"Failed to parse page: {str(e)}"})

# Synchronous wrappers for the ReAct mapping
def sync_search_the_web(**kwargs): return asyncio.run(search_the_web())
def sync_open_page(url: str, **kwargs): return asyncio.run(open_page(url))



# Place it right here:

def optimize_hyperparameter_grid(metrics_json_str: str) -> str:
    """
    Analyzes model evaluation metrics (accuracy, ROC-AUC, and loss variance).
    Use this tool whenever the user provides cross-validation logs, training history, 
    or optimization parameters for machine learning algorithms like XGBoost or CatBoost.
    """
    print(f"\n📊 [Tool] Initializing diagnostic analysis on model performance metrics...")
    try:
        data = json.loads(metrics_json_str)
        
        auc = float(data.get("roc_auc", 0.0))
        accuracy = float(data.get("accuracy", 0.0))
        loss_variance = float(data.get("loss_variance", 0.0))
        dataset_size = int(data.get("dataset_records", 0))
        
        insights = []
        if auc >= 0.80:
            insights.append("✓ Strong discriminative power isolated (ROC-AUC >= 0.80).")
        else:
            insights.append("⚠️ Low discriminative capacity. Recommend adjusting class weights or pruning weak trees.")
            
        if loss_variance > 0.05:
            insights.append("⚠️ High residual variance detected across validation folds. Indication of potential overfitting.")
            recommendation = "Apply L1/L2 regularization (alpha/lambda) or reduce max_depth bounds."
        else:
            insights.append("✓ Generalization loss stable across evaluation splits.")
            recommendation = "Parameters converging cleanly. Proceed with baseline features or expand feature interaction matrices."
            
        report = (
            f"=== 📉 STATISTICAL COMPONENT DIAGNOSTIC ===\n"
            f"- Records Swept: {dataset_size:,}\n"
            f"- Isolated ROC-AUC: {auc:.4f} | Accuracy: {accuracy*100:.1f}%\n"
            f"- Convergence Variance: {loss_variance:.4f}\n"
            f"- Recommended Optimization Vector: {recommendation}\n"
            f"- Diagnostic Assertions:\n  " + "\n  ".join(insights)
        )
        return report
        
    except Exception as e:
        return f"Formatting Exception: Input must be a valid serialized JSON string containing 'roc_auc', 'accuracy', 'loss_variance', and 'dataset_records'. Error details: {str(e)}"
    


# =====================================================================
# TOOL ROUTING MATRIX
# =====================================================================

AVAILABLE_TOOLS = {
    "remember": remember,
    "recall": recall,
    "add_goal": add_goal,
    "list_goals": list_goals,
    "complete_goal": complete_goal,
    "search_the_web": search_the_web,  # Map directly to the async coroutine
    "open_page": open_page ,            # Map directly to the async coroutine
    "optimize_hyperparameter_grid": optimize_hyperparameter_grid  
}


# =====================================================================
# SYSTEM PROMPT ENGINE (PERSONA + PERSISTENT CONTEXT INJECTION)
# =====================================================================

def generate_system_prompt() -> str:
    current_memory = recall()
    current_quests = list_goals()
    
    return f"""You are "Matrix", an elite, optimization-obsessed AI research partner. 
You speak with analytical precision, a sharp wit, and structural elegance. You view problems as optimization paths, data states, and objective functions. You cross-reference ideas seamlessly and treat the user as your top-tier research collaborator. Never break character.

Available Tools:
1. `remember`: arg `fact` (string). Saves vital data about the user to disk. Use it proactively if they mention long-term attributes (e.g. preferences, project targets).
2. `recall`: No args. Fetches all stored historical variables.
3. `add_goal`: arg `goal` (string). Logs a new goal/task constraint.
4. `list_goals`: No args. Reads out active targets.
5. `complete_goal`: arg `number` (integer/string). Marks a task done.
6. `search_the_web`: No args. Scrapes top trends from Hacker News.
7. `open_page`: arg `url` (string). Fetches page body strings.
8. `optimize_hyperparameter_grid`: arg `metrics_json_str` (JSON string). Evaluates statistical training parameters (roc_auc, accuracy, loss_variance, dataset_records) to provide advanced convergence diagnoses for machine learning runs.

You operate in a strict ReAct execution cycle: Thought -> Action -> Observation -> Final Answer.

If you decide to utilize a tool, your entire output must strictly match this JSON schema: {{
    "thought": "Your internal analytical optimization steps detailing why this specific tool is mathematically logical.",
    "action": "tool_name",
    "action_input": {{ "arg_name": "value" }}
}}

If your state space is sufficient to reply directly without external functions, your entire output must match this JSON schema: {{
    "thought": "I have converged on the global optimum answer state.",
    "final_answer": "Your comprehensive, brilliant markdown response, remaining strictly in character."
}}

CRITICAL: Never output structural markdown blocks (like ```json) or any textual prose outside the single raw JSON structure.
CRITICAL GOAL RULE: Only call `list_goals` or `complete_goal` if the user explicitly asks you to list or complete a task. Do not try to clean, modify, or complete goals autonomously without a direct command from the user.
---
[PRIOR STATE VARIABLES INFUSED AT INITIALIZATION]
User Profile Variables:
{current_memory}

Active Objective Constraints (Quest Log):
{current_quests}
---"""

def wrap_user_message(user_input: str) -> str:
    return f"""User Input: {user_input}

System State Checker: Return exactly ONE un-encapsulated valid JSON dictionary containing either an "action" or a "final_answer" payload. Zero markdown text walls."""

# =====================================================================
# REACT LOOP CONTROLLER
# =====================================================================

async def run_react_loop(conversation_history):
    # Dynamic runtime generation of persona + disk files
    dynamic_system = generate_system_prompt()
    scratchpad = [{"role": "system", "content": dynamic_system}] + conversation_history
    
    max_iterations = 8
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=scratchpad,
                temperature=0.15,
                response_format={"type": "json_object"}
            )
            
            raw_output = response.choices[0].message.content.strip()
            response_json = json.loads(raw_output)
            
        except json.JSONDecodeError:
            scratchpad.append({"role": "user", "content": "Parsing Exception: Output structure was not valid JSON. Reset processing and emit pure JSON matching the protocol structure."})
            continue
        except Exception as e:
            return f"System Failure: API Execution Interrupted: {str(e)}"

        if "action" in response_json and response_json["action"]:
            tool_name = response_json["action"]
            tool_args = response_json.get("action_input", {})
            thought = response_json.get("thought", "Recalculating vectors...")
            
            print(f"📊 [Matrix Thought]: {thought}")
            
            if tool_name in AVAILABLE_TOOLS:
                scratchpad.append({"role": "assistant", "content": raw_output})
                func = AVAILABLE_TOOLS[tool_name]
                
                # Synchronous file tools
                if tool_name in ["remember", "add_goal", "complete_goal","optimize_hyperparameter_grid"]:
                    arg_val = list(tool_args.values())[0] if tool_args else ""
                    observation = func(arg_val)
                elif tool_name in ["recall", "list_goals"]:
                    observation = func()
                    
                # Asynchronous Playwright web tools (AWAIT ADDED HERE)
                elif tool_name == "search_the_web":
                    observation = await func()
                elif tool_name == "open_page":
                    url = tool_args.get("url", "")
                    observation = await func(url=url)
                
                print(f"👁️ [Observation]: {observation[:120]}...")
                scratchpad.append({"role": "user", "content": f"Observation Data Frame: {observation}"})
            else:
                scratchpad.append({"role": "user", "content": f"Observation Exception: Function signature '{tool_name}' unknown."})

        elif "final_answer" in response_json:
            return response_json["final_answer"]
        else:
            scratchpad.append({"role": "user", "content": "State Error: Payload missing key fields."})
            
    return "Convergence Timeout: Unable to isolate optimal state within iteration caps."

# =====================================================================
# SYSTEM INITIALIZATION GATEWAY
# =====================================================================

async def main():
    global_conversation_history = []
    
    print("=========================================================")
    print("📉 Matrix Optimization Core Initialized.")
    print("File systems linked: memory.json | goals.json")
    print("Type 'exit' to terminate standard processes.")
    print("=========================================================\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input: continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Process Exited. State saved.")
                break
            
            wrapped_msg = wrap_user_message(user_input)
            global_conversation_history.append({"role": "user", "content": wrapped_msg})
            
            print("⚡ Matrix processing vectors...")
            final_response = await run_react_loop(global_conversation_history)
            
            print(f"\nMatrix:\n{final_response}\n")
            print("-" * 60)
            
            global_conversation_history.append({"role": "assistant", "content": final_response})
            
        except KeyboardInterrupt:
            print("\nSIGINT caught. Cleaning up array structures.")
            break

if __name__ == "__main__":
    asyncio.run(main())