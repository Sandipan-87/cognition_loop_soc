import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()

# 1. Initialize the raw Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# 2. Define the Playwright tool
def search_the_web(query: str) -> str:
    """Search the live web and return the top results as text."""
    print(f"\n[System: Booting browser to search for '{query}']...")
    
    with sync_playwright() as p:
        # headless=False lets you watch the robot. DDG sometimes throws bot-blockers,
        # seeing the screen helps you know if you got blocked!
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://html.duckduckgo.com/html/")
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            
            # Wait for the results container to load
            page.wait_for_selector(".result__snippet", timeout=10000)

            results = []
            # Grab the top 3 results to keep the context window clean
            for row in page.locator(".result__body").all()[:3]:
                title = row.locator(".result__title").inner_text()
                snippet = row.locator(".result__snippet").inner_text()
                results.append(f"Title: {title.strip()}\nSnippet: {snippet.strip()}")
            
            browser.close()
            return "\n\n".join(results) or "No results found."
            
        except Exception as e:
            browser.close()
            return f"Search failed. Error: {str(e)}"

# 3. Define the Schema for Groq
tools = [{
    "type": "function",
    "function": {
        "name": "search_the_web",
        "description": "Search the live web for current information. Use it whenever the question needs recent or factual data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
}]

# A quick lookup dictionary to map the tool name to the actual Python function
available_tools = {"search_the_web": search_the_web}

SYSTEM = (
    "You are a research assistant with a live web search tool. "
    "When a question needs current or real-world facts, call search_the_web "
    "before answering. Base your answer on the results, and say so if they "
    "don't contain the answer."
)

def run_research_agent(user_query):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_query}
    ]

    print(f"User: {user_query}")
    
    # 4. The ReAct Loop (Reason + Act)
    while True:
        # Step A: Let the AI think and decide what to do
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto" 
        )
        
        msg = response.choices[0].message
        messages.append(msg) # Save the AI's response to history
        
        # Step B: Did the AI decide to use a tool?
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                
                # We must manually parse the JSON string from Groq into a Python dictionary
                tool_args = json.loads(tool_call.function.arguments)
                
                if tool_name in available_tools:
                    function_to_call = available_tools[tool_name]
                    # Execute the Playwright function with the AI's arguments
                    function_result = function_to_call(**tool_args)
                    
                    print(f"[System: Tool returned {len(function_result)} characters of data]")
                    
                    # Step C: Hand the scraped data back to the AI
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": function_result,
                    })
            # The loop restarts here, sending the new history (with tool data) back to Groq!
        
        # Step D: No tools called? That means the AI is ready to give the final answer.
        else:
            print(f"\nAgent: {msg.content}")
            break

if __name__ == "__main__":
    # Test it with a question that requires live data
    question = "What is currently trending on Hacker News today?"
    run_research_agent(question)