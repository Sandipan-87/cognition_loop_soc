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
MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")
GOALS_FILE = os.path.join(SCRIPT_DIR, "goals.json")

# Initialize JSON files if they don't exist
for file_path in [MEMORY_FILE, GOALS_FILE]:
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump([], f)

# Model configuration
MODEL = "llama-3.3-70b-versatile"

# Helper function to invoke Groq API with exponential backoff retry logic (Week 4 standard)
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
                print(f"    [Rate Limit] Groq API rate-limited. Backing off for {delay}s...")
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

# --- TOOL 3: Custom stock lookup tool (Yahoo Finance) ---
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

# --- TOOLS 4 & 5: Persistent Memory ---
def remember(fact: str) -> str:
    """Save a fact about the user or their research preferences so it persists between sessions."""
    try:
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
        if fact not in memory:
            memory.append(fact)
            with open(MEMORY_FILE, "w") as f:
                json.dump(memory, f, indent=2)
        return f"Saved fact to memory: '{fact}'"
    except Exception as e:
        return f"Error saving fact: {str(e)}"

def recall() -> str:
    """Retrieve all facts the assistant currently remembers about the user/preferences."""
    try:
        with open(MEMORY_FILE, "r") as f:
            facts = json.load(f)
        return "\n".join(facts) if facts else "No saved facts in memory yet."
    except Exception as e:
        return f"Error loading memory: {str(e)}"

# --- TOOLS 6, 7, & 8: Quest Log ---
def _load_goals() -> list:
    try:
        with open(GOALS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def _save_goals(goals: list) -> None:
    with open(GOALS_FILE, "w") as f:
        json.dump(goals, f, indent=2)

def add_goal(goal: str) -> str:
    """Add a new research target, task, or goal to the persistent quest list."""
    goals = _load_goals()
    goals.append({"goal": goal, "done": False})
    _save_goals(goals)
    return f"Goal added: '{goal}'"

def list_goals() -> str:
    """List all current tasks and goals and their completion status."""
    goals = _load_goals()
    if not goals:
        return "The quest log is currently empty."
    lines = []
    for idx, item in enumerate(goals, 1):
        status = "Completed" if item["done"] else "Pending"
        lines.append(f"{idx}. [{status}] {item['goal']}")
    return "\n".join(lines)

def complete_goal(number: int) -> str:
    """Mark a specific goal as completed using its number from list_goals()."""
    goals = _load_goals()
    if 1 <= number <= len(goals):
        goals[number - 1]["done"] = True
        _save_goals(goals)
        return f"Goal completed: '{goals[number - 1]['goal']}'"
    return f"Error: Goal number {number} is invalid. Use list_goals() to find correct numbers."

# --- Schemas ---
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
            "name": "remember",
            "description": "Save an important fact about the user or their research preferences so it's remembered across restarts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to commit to long-term memory."}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Load all saved facts and preferences from long-term memory.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Log a new target company to research, a research step, or user goal to track.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Description of the research task or goal."}
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_goals",
            "description": "Display the persistent goal list and their status (Pending or Completed).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark a goal or research task as completed by specifying its line number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "The line number of the goal to complete."}
                },
                "required": ["number"]
            }
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page,
    "get_stock_price": get_stock_price,
    "remember": remember,
    "recall": recall,
    "add_goal": add_goal,
    "list_goals": list_goals,
    "complete_goal": complete_goal
}

def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY is not configured in .env. Execution will fail.")
        
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Establish system instructions (the voice)
    system_instruction = (
        "You are Alpha, a professional, data-driven equity research analyst and market strategist. "
        "You address the user as Client and communicate in a highly structured, objective, and analytical tone. "
        "Utilize formatting, markdown tables, and bullet points to present findings clearly. "
        "\n\n"
        "Guidelines:\n"
        "1. Maintain long-term memory: Call remember(fact) whenever the Client shares critical details about "
        "themselves, their investment profile, or research preferences. Use recall() to retrieve details.\n"
        "2. Coordinate Research Tasks: Use add_goal, list_goals, and complete_goal to manage research queues. "
        "Always list_goals to check the task number before calling complete_goal.\n"
        "3. Live Tools: If a research topic needs stock stats, fetch it using get_stock_price. If it needs general "
        "market details, use search_the_web, followed by open_page on specific links to gather deeper text data.\n"
        "4. Remain in character at all times, relying on standard function calls to retrieve information."
    )
    
    # Load persistence contexts at boot
    saved_memory = recall()
    saved_goals = list_goals()
    
    boot_context = (
        f"{system_instruction}\n\n"
        f"--- Client Memory Facts ---\n{saved_memory}\n\n"
        f"--- Active Research Quests ---\n{saved_goals}"
    )
    
    messages = [{"role": "system", "content": boot_context}]
    
    print("=========================================================================")
    print(" Welcome to Alpha: The Persistent Market Analyst Agent (Week 4)")
    print(" Type 'quit', 'exit', or 'q' to end the session.")
    print("=========================================================================")
    
    while True:
        try:
            user_input = input("\nClient: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break
            
        if not user_input:
            continue
            
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
            
        messages.append({"role": "user", "content": user_input})
        
        max_turns = 10
        turn = 0
        
        print("\nAlpha thinking...")
        
        while turn < max_turns:
            turn += 1
            try:
                # completions using exponential backoff wrapper
                response = call_llm(client, messages, tools=tools_schemas)
                
                msg = response.choices[0].message
                messages.append(msg)
                
                # Check for text answer completion
                if not msg.tool_calls:
                    print(f"\nAlpha: {msg.content}")
                    break
                    
                # Execute tool calls
                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    
                    print(f"  [Turn {turn}] Alpha requests tool '{func_name}'")
                    
                    if func_name in available_tools:
                        # Extract arguments
                        observation = available_tools[func_name](**func_args)
                        print(f"  [Turn {turn}] Tool output: {len(observation)} characters.")
                        
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
                print(f"  [Error] {e}")
                messages.append({
                    "role": "assistant",
                    "content": f"I encountered an internal system error: {str(e)}"
                })
                print(f"\nAlpha: Apologies, Client. I encountered an error: {str(e)}")
                break
        else:
            print("\nAlpha reached maximum internal reasoning loops. Ending turn.")

if __name__ == "__main__":
    main()
