import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()

# Initialize client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# --- TOOL 1: Search the Web ---
def search_the_web(query: str) -> str:
    """Search the live web and return the top results as text."""
    print(f"\n[System: Booting browser to search for '{query}']...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Running headless for speed
        page = browser.new_page()
        try:
            page.goto("https://html.duckduckgo.com/html/")
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            page.wait_for_selector(".result__snippet", timeout=10000)

            results = []
            for row in page.locator(".result__body").all()[:5]: # Grab top 5
                title = row.locator(".result__title").inner_text()
                link = row.locator(".result__url").inner_text() # Added the URL so the AI knows where to click!
                snippet = row.locator(".result__snippet").inner_text()
                results.append(f"Title: {title.strip()}\nURL: https://{link.strip()}\nSnippet: {snippet.strip()}")
            
            browser.close()
            return "\n\n".join(results) or "No results found."
        except Exception as e:
            browser.close()
            return f"Search failed. Error: {str(e)}"

# --- TOOL 2: Open a Specific Page ---
def open_page(url: str) -> str:
    """Open a URL and return its visible text."""
    print(f"\n[System: Opening webpage to read '{url}']...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # Short timeout so the agent doesn't freeze on bloated websites
            page.goto(url, timeout=15000)
            
            # Grab the raw text from the body of the page
            text = page.locator("body").inner_text()
            browser.close()
            
            # CRITICAL: Trim the text so we don't blow up the LLM's context window
            return text[:3000] 
        except Exception as e:
            browser.close()
            return f"Failed to open page. Error: {str(e)}"

# --- Schema Definitions ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web for current information. Returns titles, snippets, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a specific URL to read the full text of the page. Use this to investigate a search result deeper.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full HTTP URL to open."},
                },
                "required": ["url"],
            },
        },
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page
}

SYSTEM = (
    "You are an advanced research assistant with access to a live web browser. "
    "If you need current information, call 'search_the_web'. "
    "If a search result snippet is not enough, you can call 'open_page' with the URL "
    "to read the actual website. Always base your answers on the retrieved context."
)

def main():
    print("--- Live Research Agent Initialized (Type 'quit' to exit) ---")
    
    # MEMORY: The messages list lives OUTSIDE the chat loop so it remembers previous turns!
    messages = [{"role": "system", "content": SYSTEM}]
    
    # OUTER LOOP: The Conversation
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
            
        messages.append({"role": "user", "content": user_input})

        # INNER LOOP: The ReAct (Reason + Act) Cycle
        while True:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            messages.append(msg)
            
            # Step 1: Did it use a tool?
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    if tool_name in available_tools:
                        function_to_call = available_tools[tool_name]
                        result = function_to_call(**tool_args)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": result,
                        })
                # The inner loop restarts here, letting the AI analyze the new tool data
                
            # Step 2: No tools called? It has its final answer.
            else:
                print(f"\nAgent: {msg.content}")
                break # Break the inner loop to ask the user for the next prompt

if __name__ == "__main__":
    main()