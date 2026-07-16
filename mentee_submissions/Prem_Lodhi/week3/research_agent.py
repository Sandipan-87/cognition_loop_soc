import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# 1. Setup Environment and Client
load_dotenv()
client = Groq() 
MODEL = "llama-3.3-70b-versatile"

# 2. The Tool Definition (The "Eyes")
def search_the_web(query: str) -> str:
    """Scrape the Hacker News front page for trending stories."""
    print(f"\n[Agent Action] 🕵️‍♂️ Scraping Hacker News front page...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://news.ycombinator.com/")
        page.wait_for_selector(".titleline", timeout=10000)

        results = []
        for row in page.locator(".titleline").all()[:5]:
            title = row.inner_text()
            results.append(f"Trending Story: {title.strip()}")
            
        browser.close()

    return "\n\n".join(results) or "No results found."

# 3. The Menu for the LLM
tools = [{
    "type": "function",
    "function": {
        "name": "search_the_web",
        "description": "Scrape Hacker News for current tech stories. Use it whenever asked about trending tech news.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query (can be empty for front page)."},
            },
            "required": ["query"],
        },
    },
}]

available_tools = {"search_the_web": search_the_web}

# 4. The System Prompt (The Rules of the Game)
SYSTEM = (
    "You are a tech research assistant. "
    "When asked about current tech news or Hacker News, ALWAYS call the search_the_web tool first. "
    "Read the results, and summarize them nicely for the user in a conversational tone."
)

# 5. The ReAct Loop (The Brain)
def ask_agent(user_question: str):
    print(f"\nUser: {user_question}")
    
    # Initialize the conversation memory
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_question}
    ]

    # The Loop: Keep generating until the model gives a final text answer
    while True:
        # Ask Groq what to do next
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto" 
        )
        
        msg = response.choices[0].message
        messages.append(msg) # Remember the thought process

        # Did Groq decide to use the tool?
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Execute our Python function
                function_to_call = available_tools[function_name]
                tool_result = function_to_call(**function_args)
                
                # Feed the scraped text back to Groq
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result,
                })
            # The loop repeats, and Groq reads the new tool data!
            
        else:
            # If no tools are called, Groq is giving us the final answer
            print(f"\nAgent: {msg.content}\n")
            break

# --- Run the Full Agent ---
if __name__ == "__main__":
    ask_agent("What are the top trending stories on Hacker News right now?")