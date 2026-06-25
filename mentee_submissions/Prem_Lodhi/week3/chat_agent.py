import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# 1. Setup
load_dotenv()
client = Groq()
MODEL = "llama-3.3-70b-versatile"

# 2. Tool 1: The Searcher (No query parameter needed now)
def search_the_web() -> str:
    """Scrape the Hacker News front page for trending stories and their URLs."""
    print(f"\n[Agent Action] 🕵️‍♂️ Scraping Hacker News...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://news.ycombinator.com/")
            page.wait_for_selector(".titleline > a", timeout=10000)

            results = []
            for row in page.locator(".titleline > a").all()[:5]:
                title = row.inner_text()
                url = row.get_attribute("href")
                results.append(f"Title: {title.strip()}\nURL: {url}")
                
            browser.close()
        return "\n\n".join(results) or "No results found."
    except Exception as e:
        return f"Error scraping Hacker News: {str(e)}"

# 3. Tool 2: The Reader
def open_page(url: str) -> str:
    """Open a URL and return its visible text."""
    print(f"\n[Agent Action] 📄 Reading page: {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
        return text[:3000] # Keep context window safe
    except Exception as e:
        return f"Failed to read page. Error: {str(e)}"

# 4. Updated Menu Schema (Clean parameters for tool 1)
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Scrape the front page of Hacker News to see currently trending tech stories and links.",
            "parameters": {
                "type": "object",
                "properties": {} # No arguments needed anymore!
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a specific URL to read the full article text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The exact URL string to open."},
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

# 5. Clear System Prompt instructions
SYSTEM = (
    "You are a tech research assistant. "
    "You have two tools: search_the_web and open_page. "
    "1. When asked about trending news, call search_the_web. "
    "2. After search_the_web returns its data, you MUST explicitly type out the list of headlines for the user to see. "
    "3. At the end of your list, ask the user if they want you to open and read any of those specific articles. "
    "4. IMPORTANT: Do NOT call open_page unless the user explicitly asks you to read or open a specific article."
)
# 6. The Chat Loop
# 6. The Chat Loop
def start_chat():
    print("Welcome to your Agentic Chat! (Type 'quit' to exit)\n")
    messages = [{"role": "system", "content": SYSTEM}]

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        if not user_input:
            continue
            
        messages.append({"role": "user", "content": user_input})

        while True:
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                messages.append(msg)

                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        function_name = tool_call.function.name
                        
                        # --- THE FIX: Bulletproof Argument Parsing ---
                        args_string = tool_call.function.arguments
                        function_args = {} # Default to empty dict
                        
                        if args_string:
                            parsed = json.loads(args_string)
                            # Only accept it if the LLM actually returned a dictionary
                            if isinstance(parsed, dict):
                                function_args = parsed
                        # ---------------------------------------------
                        
                        function_to_call = available_tools[function_name]
                        tool_result = function_to_call(**function_args)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_result,
                        })
                else:
                    print(f"\nAgent: {msg.content}\n")
                    break
                    
            except Exception as e:
                print(f"\n[System Error] Something went wrong: {e}")
                break

if __name__ == "__main__":
    start_chat()