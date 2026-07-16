import os
import json
import time
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

# Tool 1: Playwright Web Search Tool
def search_the_web(query: str) -> str:
    """
    Search the live web using DuckDuckGo HTML and return top 5 results (title, description, URL).
    """
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
            if not results:
                return "No search results were found for this query."
            return "\n\n".join(results)
            
    except Exception as e:
        return f"Error during search execution: {str(e)}"

# Tool 2: Playwright Page Reader Tool
def open_page(url: str) -> str:
    """
    Open a URL and extract its visible text (trimmed to 3000 characters).
    Handles timeouts and page-load errors gracefully.
    """
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            return "Error: Invalid URL. It must start with 'http://' or 'https://'."
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True
            )
            page = context.new_page()
            
            print(f"  [Tool: open_page] Navigating to: '{url}'...")
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            
            body_text = page.locator("body").inner_text()
            browser.close()
            
            trimmed_text = body_text.strip()
            if not trimmed_text:
                return "The web page loaded successfully, but it contained no visible body text."
                
            # Return first 3000 chars to avoid exceeding context window limits
            return trimmed_text[:3000]
            
    except Exception as e:
        return f"Error: Failed to open or read URL '{url}'. Details: {str(e)}"

def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY is not set in .env. Groq calls will fail.")
        
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Declarations of the two tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_the_web",
                "description": (
                    "Search the live web for recent or factual information. "
                    "Use this tool to discover URLs and basic snippets about the user request."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "open_page",
                "description": (
                    "Open a specific URL/webpage and extract its text content. "
                    "Use this tool to read a full webpage or article when you need deeper details "
                    "from a search result URL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The absolute URL to open (e.g. 'https://en.wikipedia.org/wiki/Main_Page')."
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    ]
    
    available_tools = {
        "search_the_web": search_the_web,
        "open_page": open_page
    }
    
    system_instruction = (
        "You are an interactive conversational AI research assistant equipped with web tools: "
        "search_the_web and open_page. You maintain conversation history memory.\n\n"
        "Instructions:\n"
        "1. For questions requiring recent or specific details, first use search_the_web to find candidate URLs.\n"
        "2. If you need deeper details from a specific page or article, call open_page with the URL.\n"
        "3. You can chain tools: search first, then open one or more links to verify details before answering.\n"
        "4. Always formulate a final response in markdown based on the retrieved facts, citing sources.\n"
        "5. If a tool call fails, analyze the error message, adapt your plan, and either retry or try an alternative."
    )
    
    # Persistent messages list (Memory lives outside the chat loop)
    messages = [{"role": "system", "content": system_instruction}]
    
    print("=========================================================================")
    print(" Welcome to the Autonomous Chat Agent with Memory and Chained Tools!")
    print(" Ask any question. Type 'quit', 'exit', or 'q' to end the session.")
    print("=========================================================================")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break
            
        if not user_input:
            continue
            
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
            
        # Append user message to memory
        messages.append({"role": "user", "content": user_input})
        
        max_turns = 10
        turn = 0
        
        print("\nAgent thinking...")
        
        while turn < max_turns:
            turn += 1
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                messages.append(msg)
                
                # Check if final text answer is provided
                if not msg.tool_calls:
                    print(f"\nAgent: {msg.content}")
                    break
                    
                # Process the tool calls
                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    
                    print(f"  [Turn {turn}] Agent calls tool '{func_name}'")
                    
                    if func_name in available_tools:
                        # Extract parameter
                        param = func_args.get("query") if func_name == "search_the_web" else func_args.get("url")
                        observation = available_tools[func_name](param)
                        
                        print(f"  [Turn {turn}] Tool observation length: {len(observation)} characters.")
                        
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
                error_msg = f"Error during loop processing: {str(e)}"
                print(f"  [Turn {turn} Error] {error_msg}")
                # Recovery response to avoid hanging/infinite looping
                messages.append({
                    "role": "assistant",
                    "content": f"I encountered an internal error: {str(e)}"
                })
                print(f"\nAgent: I encountered an error: {str(e)}")
                break
        else:
            print("\nAgent reached maximum internal reasoning loops. Breaking turn.")

if __name__ == "__main__":
    main()
