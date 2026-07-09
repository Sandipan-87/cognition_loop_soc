import os
import json
import time
import requests
from dotenv import load_dotenv
from groq import Groq
from groq import RateLimitError
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

# Setup paths relative to the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAN_FILE = os.path.join(SCRIPT_DIR, "plan.json")

# Model configuration
MODEL = "llama-3.3-70b-versatile"

# Senior Analyst Persona for step execution and report synthesis
PLANNER_PERSONA = (
    "You are a research assistant with access to tools: search_the_web, open_page, get_stock_price, and write_file. "
    "When a task needs real-world details or stock prices, call the appropriate tool. "
    "Always base your final answer on the retrieved facts."
)

# Helper function to invoke Groq API with exponential backoff retry logic (HTTP 429)
def call_llm(client, messages, tools=None, max_retries=5):
    """Call the Groq API with exponential backoff on RateLimitError (HTTP 429)."""
    delay = 2  # initial delay in seconds
    
    # Try the default model first, fall back to llama-3.1-8b-instant if TPD is exceeded
    models_to_try = [MODEL, "llama-3.1-8b-instant", "llama3-8b-8192"]
    
    for model_name in models_to_try:
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.0  # Crucial for stable, deterministic tool calling
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        for attempt in range(max_retries):
            try:
                return client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                # If daily token limit (TPD) is reached, try the next model
                err_msg = str(e)
                if "TPD" in err_msg or "daily" in err_msg.lower() or "limit reached" in err_msg.lower():
                    if model_name != models_to_try[-1]:
                        print(f"    [Rate Limit] Token limit reached for {model_name}. Trying fallback model...")
                        break  # Break inner loop, try next model in outer loop
                if attempt == max_retries - 1:
                    raise e
                print(f"    [Rate Limit] Groq API rate-limited (HTTP 429). Backing off for {delay}s...")
                time.sleep(delay)
                delay *= 2
    raise RuntimeError("Exhausted all Groq API model fallbacks.")

# --- TOOL 1: Search the Web ---
def search_the_web(query: str) -> str:
    """Search the live web using DuckDuckGo HTML and return top 5 results (title, description, URL)."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print(f"  [Tool: search_the_web] Querying DuckDuckGo for: '{query}'...")
            page.goto("https://html.duckduckgo.com/html/", timeout=15000)
            
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            
            try:
                page.wait_for_selector(".result__body", timeout=10000)
            except Exception:
                page_content = page.content()
                if "captcha" in page_content.lower() or "robot" in page_content.lower() or "blocked" in page_content.lower():
                    browser.close()
                    return "Error: DuckDuckGo triggered bot protection / captcha. Search failed."
                browser.close()
                return "Error: Search page timeout or selector mismatch."
                
            results = []
            rows = page.locator(".result__body").all()
            for row in rows[:5]:
                try:
                    title_node = row.locator(".result__title")
                    snippet_node = row.locator(".result__snippet")
                    link_node = row.locator(".result__a").first
                    
                    title = title_node.inner_text().strip()
                    snippet = snippet_node.inner_text().strip()
                    url = link_node.get_attribute("href")
                    
                    if url and url.startswith("//"):
                        url = "https:" + url
                    results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {url}")
                except Exception:
                    continue
            browser.close()
            return "\n\n".join(results) if results else "No search results found."
    except Exception as e:
        return f"Error during web search: {str(e)}"

# --- TOOL 2: Open/Scrape Webpage ---
def open_page(url: str) -> str:
    """Open a URL and extract its visible text (trimmed to 3000 characters to protect context budget)."""
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            return "Error: Invalid URL. It must start with 'http://' or 'https://'."
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ignore_https_errors=True
            )
            page = context.new_page()
            print(f"  [Tool: open_page] Scrapes text from URL: '{url}'...")
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            body_text = page.locator("body").inner_text()
            browser.close()
            
            trimmed_text = body_text.strip()
            if not trimmed_text:
                return "The web page loaded successfully, but it contained no visible body text."
            return trimmed_text[:3000]
    except Exception as e:
        return f"Error: Failed to open page '{url}'. Details: {str(e)}"

# --- TOOL 3: Yahoo Finance stock price lookup ---
def get_stock_price(ticker: str) -> str:
    """Fetch the current stock price and trading info for a ticker symbol (e.g. AAPL, TSLA, MSFT)."""
    try:
        ticker = ticker.upper().strip()
        print(f"  [Tool: get_stock_price] Fetching market data for: '{ticker}'...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return f"Error: Failed to fetch ticker '{ticker}' (HTTP {response.status_code})."
            
        data = response.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return f"Error: No market data found for ticker '{ticker}'."
            
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        currency = meta.get("currency", "USD")
        exchange = meta.get("exchangeName", "NMS")
        
        if price is None:
            return f"Error: Stock price not available for ticker '{ticker}'."
            
        return f"Ticker: {ticker}\nPrice: {price} {currency}\nExchange: {exchange}"
    except Exception as e:
        return f"Error fetching stock price: {str(e)}"

# --- TOOL 4: Write Research Report to File ---
def write_file(filename: str, content: str) -> str:
    """Save content to a local markdown or text file. Useful for saving compiled research reports."""
    try:
        if not filename.endswith(".md") and not filename.endswith(".txt"):
            filename = filename + ".md"
        filename = os.path.basename(filename)
        output_path = os.path.join(SCRIPT_DIR, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File saved successfully at: {output_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

# --- Tool Schemas for Groq ---
tools_schemas = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web for recent news, market reports, or business details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a specific URL to scrape and read deeper text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The HTTP or HTTPS URL to open."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Fetch real-time stock price and exchange info for a ticker symbol (e.g. TSLA, NVDA).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "The stock ticker symbol."}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Save research results, data tables, or completed reports as a local file (e.g., nvda_report.md).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the file (e.g. 'tsla_report.md')."},
                    "content": {"type": "string", "description": "The markdown or text content to save."}
                },
                "required": ["filename", "content"]
            }
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page,
    "get_stock_price": get_stock_price,
    "write_file": write_file
}

# --- State Persistence Helpers ---
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

# --- Token-Efficient Context Construction (Week 4 Spec) ---
def build_step_context(plan: dict, step: dict) -> list:
    """Build a minimal, token-efficient context prompt to prevent exceeding TPM budget limits."""
    user_content = [f"Overall research objective: {plan['goal']}"]
    
    # Send only the immediately previous step's result to save context tokens (and cap at 400 chars)
    prev_step = None
    for s in plan["steps"]:
        if s["id"] == step["id"] - 1:
            prev_step = s
            break
            
    if prev_step and prev_step["result"]:
        if "Error executing step" in prev_step["result"]:
            prev_result_summary = "Previous step failed to retrieve data."
        else:
            prev_result_summary = prev_step["result"][:400]
            # Sanitize to prevent model replicating raw XML tags
            for tag in ["<function", "</function>", "<tool_use", "</tool_use>"]:
                prev_result_summary = prev_result_summary.replace(tag, "")
        user_content.append(f"Brief summary of data retrieved in previous step:\n{prev_result_summary}")
        
    user_content.append(f"Now execute this specific research step. Use your tools if needed:\n{step['task']}")
    
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user", "content": "\n\n".join(user_content)}
    ]
    return messages

# --- Step Execution Loop (ReAct inside one Step) ---
def execute_step(client, plan: dict, step: dict) -> str:
    """Execute a single plan step using a local ReAct (Reasoning & Acting) loop."""
    messages = build_step_context(plan, step)
    
    max_react_turns = 6
    turn = 0
    
    while turn < max_react_turns:
        turn += 1
        try:
            response = call_llm(client, messages, tools=tools_schemas)
            msg = response.choices[0].message
            messages.append(msg)
            
            # If no tool calls, model provides final text answer for the step
            if not msg.tool_calls:
                return msg.content
                
            # Process tool calls
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(f"    [ReAct Turn {turn}] Agent calls tool '{func_name}'")
                
                if func_name in available_tools:
                    observation = available_tools[func_name](**func_args)
                    print(f"    [ReAct Turn {turn}] Tool observation length: {len(observation)} characters.")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": observation
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": f"Error: Tool '{func_name}' is not recognized."
                    })
        except Exception as e:
            print(f"    [ReAct Error] Failed during step execution turn: {e}")
            return f"Error executing step: {str(e)}"
            
    return "Error: Step execution reached maximum internal reasoning loops without finishing."

# --- Task Decomposition (make_plan) ---
def make_plan(client, goal: str) -> dict:
    """Decompose one overall market research goal into 4 structured, ordered standard sub-tasks."""
    print(f"\nDecomposing overall goal: '{goal}' into steps...")
    
    # Clean up the query to extract the main company/topic name
    target = goal
    # Remove common filler words and case variants
    for word in ["analyse", "analyze", "market", "status", "profile", "of", "the", "about", "india"]:
        target = target.replace(word, "").replace(word.capitalize(), "")
    target = target.strip()
    if not target:
        target = goal
        
    print(f"Target company identified for standard analysis: '{target}'")
    
    return {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": [
            {
                "id": 1,
                "task": f"Retrieve stock details, current market price, and trading metrics of {target} using the get_stock_price or search_the_web tools.",
                "status": "pending",
                "result": None
            },
            {
                "id": 2,
                "task": f"Gather general company profile and business operations details of {target} from official websites or directories using search_the_web and open_page tools.",
                "status": "pending",
                "result": None
            },
            {
                "id": 3,
                "task": f"Conduct competitor checks and search for recent news updates related to {target} and its key industry peers using search_the_web.",
                "status": "pending",
                "result": None
            },
            {
                "id": 4,
                "task": f"Synthesize all findings, compile a structured markdown report analyzing {target}'s market position, and save it using the write_file tool.",
                "status": "pending",
                "result": None
            }
        ]
    }

# --- Final Synthesis Report ---
def synthesize_final_report(client, plan: dict) -> None:
    """Make a final LLM call to compile and synthesize all saved steps results into a master report."""
    print("\n========================================================")
    print(" Compiling and Synthesizing Final Market Research Report")
    print("========================================================")
    
    context = []
    for step in plan["steps"]:
        context.append(f"### Step {step['id']}: {step['task']}\nResult:\n{step['result']}\n")
        
    compiled_results = "\n".join(context)
    
    prompt = (
        "You are Alpha, the Senior Equity Research Analyst. Synthesize the following step results "
        "into a formal, comprehensive Market Research Report. Organize it with clear headings (Executive Summary, "
        "Financial & Market Stats, Competitive Analysis, Recent Developments, and Analyst Verdict). "
        "Use markdown formatting, lists, and tables where appropriate. Present all data points gathered.\n\n"
        f"Data Gathered:\n{compiled_results}"
    )
    
    messages = [
        {
            "role": "system", 
            "content": (
                "You are Alpha, a professional senior equity research analyst. Your job is to compile and synthesize the "
                "gathered research results into a formal, structured markdown report. Organize it with clear headings "
                "(Executive Summary, Financial & Market Stats, Competitive Analysis, Recent Developments, and Analyst Verdict). "
                "Use only the provided data; do NOT mention tools (like search_the_web, write_file, get_stock_price, open_page) "
                "or write placeholder calls. Present the facts clearly in structured markdown tables and bullet points."
            )
        },
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = call_llm(client, messages)
        report_content = response.choices[0].message.content
    except Exception as e:
        print(f"\n[Warning] Failed to synthesize final report using LLM: {str(e)}")
        print("Compiling a fallback report from gathered step results...")
        fallback_lines = [
            f"# Market Research Report: {plan['goal']}",
            "\n## Executive Summary",
            "This report was compiled from autonomous agent research steps. Due to API limit or connection errors during final synthesis, this fallback report lists the raw data gathered in each step.",
        ]
        for step in plan["steps"]:
            fallback_lines.append(f"\n### Step {step['id']}: {step['task']}")
            fallback_lines.append(f"**Result:**\n{step['result']}")
        report_content = "\n".join(fallback_lines)
    
    print("\n=== Final Analyst Report ===")
    print(report_content)
    print("============================\n")
    
    # Save the synthesized report to disk
    report_filename = plan["goal"].replace(" ", "_").lower()
    for c in ["'", '"', ",", ".", "?", "!", "(", ")", "/"]:
        report_filename = report_filename.replace(c, "")
    report_filename = report_filename[:40] + "_report.md"
    
    save_msg = write_file(report_filename, report_content)
    print(save_msg)

# --- Main Orchestration Loop ---
def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY is not set in .env. Groq calls will fail.")
        
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Step 1: Load existing plan from disk
    plan = load_plan()
    
    # Step 2: Determine if we are starting fresh or resuming
    if not plan or plan.get("status") == "done":
        # Start a new research quest
        print("=================================================================")
        print(" Alpha Capstone: State-Driven Market Research Orchestrator")
        print("=================================================================")
        
        goal_input = input("Enter market research target (e.g. 'Analyze Tesla (TSLA) market status'): ").strip()
        if not goal_input:
            goal_input = "Analyze NVIDIA (NVDA) market status"
            print(f"Using default research goal: {goal_input}")
            
        plan = make_plan(client, goal_input)
        save_plan(plan)
        print("\nPlan checklist created and saved to plan.json:")
        for step in plan["steps"]:
            print(f"  [{step['id']}] {step['task']}")
    else:
        # Resume an existing quest
        print("=================================================================")
        print(" Resuming Persistent Plan in progress!")
        print(f" Goal: '{plan['goal']}'")
        print(f" Resuming from Step {plan['current_step']} of {len(plan['steps'])}")
        print("=================================================================")
        for s in plan["steps"]:
            status_char = "x" if s["status"] == "done" else ("/" if s["status"] == "in_progress" else " ")
            print(f"  [{status_char}] Step {s['id']}: {s['task']}")
            
    # Step 3: Run the orchestrator loop
    total_steps = len(plan["steps"])
    
    while True:
        # Find the next step to execute
        current_step_id = plan["current_step"]
        active_step = None
        for s in plan["steps"]:
            if s["id"] == current_step_id:
                active_step = s
                break
                
        # If no active step is found or all steps are marked done, finish up
        if not active_step:
            all_done = True
            for s in plan["steps"]:
                if s["status"] != "done":
                    all_done = False
                    plan["current_step"] = s["id"]
                    active_step = s
                    break
            if all_done:
                break
                
        # Update plan status to running
        active_step["status"] = "in_progress"
        save_plan(plan)
        
        print(f"\n>>> [Executing Step {active_step['id']}/{total_steps}]: {active_step['task']}")
        print("    [System: Press Ctrl-C now to test progress persistence!]")
        
        # Artificial brief sleep to let user hit Ctrl-C easily if demonstrating
        time.sleep(3)
        
        # Execute the step with the internal ReAct loop
        step_result = execute_step(client, plan, active_step)
        
        # Commit step result to disk immediately
        active_step["result"] = step_result
        active_step["status"] = "done"
        plan["current_step"] = active_step["id"] + 1
        save_plan(plan)
        
        print(f">>> [Step {active_step['id']} Complete!] Saved result to plan.json.")
        
    # Step 4: Finalize plan, compile report, and mark plan done
    plan["status"] = "done"
    save_plan(plan)
    
    # Synthesize results
    synthesize_final_report(client, plan)
    
    print("\nResearch complete! Process finished successfully.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Process Interrupted by User] Execution halted.")
        print("All completed step results are safely flushed to plan.json on disk.")
        print("Run the script again to resume exactly where you left off!")
