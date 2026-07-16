import os
import json
import time
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

# Playwright Web Search Tool
def search_the_web(query: str) -> str:
    """
    Search the live web using DuckDuckGo HTML and return the top 5 results.
    Includes title, description, and link URL for each result.
    """
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            # Create a page context with a modern user-agent to reduce blocking risk
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print(f"  [Tool: search_the_web] Querying DuckDuckGo for: '{query}'...")
            page.goto("https://html.duckduckgo.com/html/", timeout=15000)
            
            # Fill query and submit
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            
            # Wait for result selector or check for robot detection
            try:
                page.wait_for_selector(".result__body", timeout=10000)
            except Exception:
                page_content = page.content()
                if "captcha" in page_content.lower() or "robot" in page_content.lower() or "blocked" in page_content.lower():
                    browser.close()
                    return "Error: DuckDuckGo triggered bot protection / captcha. Search failed."
                browser.close()
                return "Error: Search page timeout or selector mismatch."
                
            # Parse search results
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

def main():
    # Verify environment keys
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY is not set in .env. Groq calls will fail.")
        
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Tool declaration
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_the_web",
                "description": (
                    "Search the live web for recent or factual information. "
                    "Use this tool whenever the user's question requires live details "
                    "or real-time knowledge not available in your training data."
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
        }
    ]
    
    # Available tools mapper
    available_tools = {
        "search_the_web": search_the_web
    }
    
    # System prompt instructing the model on ReAct behavior
    system_instruction = (
        "You are an autonomous research assistant with a live web search tool. "
        "When asked a question that needs current real-world facts, call the search_the_web "
        "tool. You must analyze the results carefully, reason about them, and decide if "
        "another search is needed or if you have enough information to answer. "
        "Base your final answer on the facts you retrieve, citing details as appropriate. "
        "If you encounter search failures or no results, reason about why and explain it."
    )
    
    # Prompt user for query
    user_query = input("Ask the Research Agent (e.g. 'Who won the latest Formula 1 race?'): ").strip()
    if not user_query:
        user_query = "What is the latest major news about SpaceX Starship launch?"
        print(f"Using default query: {user_query}")
        
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_query}
    ]
    
    max_turns = 8
    turn = 0
    
    print(f"\nInitializing ReAct loop for query: '{user_query}'")
    
    while turn < max_turns:
        turn += 1
        print(f"\n--- [Turn {turn}] Agent Thinking... ---")
        
        try:
            # Query Groq model
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            messages.append(response_message)
            
            # If no tool calls, model provides final answer
            if not response_message.tool_calls:
                print("\n=== Agent's Final Answer ===")
                print(response_message.content)
                break
                
            # If tool calls are requested
            for tool_call in response_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(f">> Agent requests tool call: '{func_name}'")
                print(f"   Arguments: {func_args}")
                
                if func_name in available_tools:
                    # Run the tool
                    tool_func = available_tools[func_name]
                    observation = tool_func(func_args.get("query"))
                    
                    print(f">> Observation length: {len(observation)} characters.")
                    
                    # Feed tool observation back to the conversation
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
            print(f"An error occurred during loop execution: {e}")
            break
            
    else:
        print("\nAgent reached maximum turn limit without generating a final response.")

if __name__ == "__main__":
    main()
