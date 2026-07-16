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

tools = [{
    "type": "function",
    "function": {
        "name": "search_the_web",
        "description": "Search the live web for current information. "
                       "Use it whenever the question needs recent or factual data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
}]

available_tools = {"search_the_web": search_the_web}

SYSTEM = (
    "You are a research assistant with a live web search tool. "
    "When a question needs current or real-world facts, call search_the_web "
    "before answering. Base your answer on the results, and say so if they "
    "don't contain the answer."
)

def run_agent():
    print("Welcome to the AI Research Agent!")
    user_input = input("Enter a question that requires a live web search: ")
    
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_input}
    ]
    
    print("\nThinking...")
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
                
                print(f"-> Agent decided to use tool: {function_name} with args {arguments}")
                
                tool_function = available_tools.get(function_name)
                if tool_function:
                    result = tool_function(**arguments)
                    print(f"-> Tool returned {len(result)} characters of data.")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": str(result)
                    })
        else:
            print(f"\nAgent Answer:\n{msg.content}\n")
            break

if __name__ == "__main__":
    run_agent()
