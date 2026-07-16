import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = 'llama-3.1-8b-instant'

def search_the_web(query: str) -> str:
    """Search Wikipedia and return the text of the best matching page or search results."""
    import urllib.parse
    encoded_query = urllib.parse.quote_plus(query)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"https://en.wikipedia.org/w/index.php?search={encoded_query}", timeout=15000)
            
            if "search=" in page.url: # We are on the search results page
                results = []
                for item in page.locator(".mw-search-result").all()[:5]:
                    text = item.inner_text()
                    url_elem = item.locator(".mw-search-result-heading a").first
                    url = "https://en.wikipedia.org" + (url_elem.get_attribute("href") or "") if url_elem.count() > 0 else "unknown"
                    results.append(f"Result:\n{text}\nURL: {url}")
                text = "\n\n".join(results) or "No results found."
            else: # We were redirected to an article
                text = f"Found Wikipedia Article: {page.url}\n\n"
                for p_tag in page.locator("#mw-content-text p").all()[:3]:
                    text += p_tag.inner_text() + "\n"
            browser.close()
        return text
    except Exception as e:
        return f"Error performing search: {e}"

def open_page(url: str) -> str:
    """Open a URL and return its visible text."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # If the url is relative (duckduckgo redirect), handle it (though usually href is absolute)
            if url.startswith("//"):
                url = "https:" + url
                
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
        return text[:3000]   # keep it short to not blow the context window
    except Exception as e:
        return f"Error opening page: {e}"

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
            "description": "Open a specific URL to read the full page content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The absolute URL to open."},
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
    "You are a conversational research assistant with live web access. "
    "You have memory of this conversation. "
    "When asked a question needing facts, you can call search_the_web. "
    "If you need more details from a specific search result, you can call open_page with the URL. "
    "Always synthesize your final answer based on the tool results."
)

def run_chat_agent():
    print("Welcome to the AI Chat Agent! (Type 'quit' or 'exit' to stop)")
    messages = [{"role": "system", "content": SYSTEM}]
    
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit", "q", ""}:
            break
            
        messages.append({"role": "user", "content": user_input})
        
        while True:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools
            )
            
            msg = response.choices[0].message
            
            if msg.tool_calls:
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    print(f"-> Agent calling {function_name} {arguments}")
                    
                    tool_function = available_tools.get(function_name)
                    if tool_function:
                        result = tool_function(**arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": str(result)
                        })
            else:
                messages.append({"role": "assistant", "content": msg.content})
                print(f"Agent: {msg.content}")
                break

if __name__ == "__main__":
    run_chat_agent()
