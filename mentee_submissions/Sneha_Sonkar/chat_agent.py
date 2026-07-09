import os
import asyncio
import json
from groq import Groq
from playwright.async_api import async_playwright

# Initialize Groq client (Make sure GROQ_API_KEY is in your environment variables)
client = Groq()
MODEL_NAME = "llama-3.3-70b-versatile"  # Or "llama3-70b-8192" based on your setup

# =====================================================================
# TOOL DEFINITIONS (PLAYWRIGHT)
# =====================================================================

async def search_the_web():
    """Scrapes the front page of Hacker News to find top trending tech news."""
    print("\n[Tool] Running search_the_web (Hacker News Scraper)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # CHANGED: .new_api_context() -> .new_context()
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("https://news.ycombinator.com", timeout=15000)
            stories = await page.locator(".titleline > a").all()
            results = []
            for i, story in enumerate(stories[:10]):
                title = await story.inner_text()
                link = await story.get_attribute("href")
                results.append({"rank": i + 1, "title": title, "url": link})
            await browser.close()
            return json.dumps(results)
        except Exception as e:
            await browser.close()
            return json.dumps({"error": f"Failed to scrape Hacker News: {str(e)}"})

async def open_page(url: str):
    """Navigates to a specific URL, extracts raw body text, and truncates it."""
    print(f"\n[Tool] Running open_page for URL: {url} ...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # CHANGED: .new_api_context() -> .new_context()
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, timeout=20000)
            body_text = await page.locator("body").inner_text()
            await browser.close()
            
            cleaned_text = " ".join(body_text.split())
            return cleaned_text[:3000]
        except Exception as e:
            await browser.close()
            return json.dumps({"error": f"Failed to open page {url}: {str(e)}"})
# Map string tool names to executable async functions
AVAILABLE_TOOLS = {
    "search_the_web": search_the_web,
    "open_page": open_page
}

# =====================================================================
# SYSTEM PROMPT & RECONSTRUCTED USER WRAPPER
# =====================================================================

SYSTEM_PROMPT = """You are an advanced AI Chat Agent equipped with web tools. 
You can converse naturally, or use tools to fetch up-to-date information if needed.

You operate in a strict ReAct loop: Thought -> Action -> Observation -> Final Answer.

Available Tools:
1. search_the_web: Takes no arguments. Scrapes top headlines/links from Hacker News.
2. open_page: Takes a 'url' string argument. Returns the core text content of that webpage.

If you need to use a tool, you MUST respond ONLY with a valid JSON object matching this schema:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": { "arg_name": "value" } // Use {} if no arguments
}

If you have all the information required to directly answer the user, respond ONLY with a valid JSON object matching this schema:
{
    "thought": "I have enough info to answer the user.",
    "final_answer": "Your comprehensive, helpful markdown response to the user."
}

CRITICAL: Do not output any XML tags like <function=...>. Do not output any markdown prose outside of the JSON block. Your entire response must be a single parsable JSON object."""

def wrap_user_message(user_input: str) -> str:
    """
    Appends strict structural constraints to the user input.
    This fixes the Llama 3.3 70b edge case where it drops out of JSON tracking.
    """
    return f"""User Input: {user_input}

Reminder: You must reply with exactly ONE valid JSON object containing either "action" or "final_answer". Do not output markdown code blocks wrapping the JSON, and do NOT use XML formatting."""

# =====================================================================
# CORE AGENT REACT LOOP
# =====================================================================

async def run_react_loop(conversation_history):
    """
    Handles the inner ReAct loop execution for a single chat turn.
    """
    # Clone history for the internal scratchpad so we don't pollute global memory with intermediate thoughts
    scratchpad = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
    
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        try:
            # Call Groq LLM
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=scratchpad,
                temperature=0.2, # Low temperature for more reliable structural JSON tracking
                response_format={"type": "json_object"} # Force Groq to return JSON mode
            )
            
            raw_output = response.choices[0].message.content.strip()
            response_json = json.loads(raw_output)
            
        except json.JSONDecodeError:
            print(f"⚠️ Failed to parse JSON. Raw Output: {raw_output}")
            # Inject error back into scratchpad to force self-correction
            scratchpad.append({"role": "user", "content": "Your previous response was not valid JSON. Please repeat your thought process as a strict JSON object."})
            continue
        except Exception as e:
            print(f"⚠️ Groq API Error: {str(e)}")
            return "Sorry, I encountered an internal error processing that request."

        # Case 1: LLM wants to execute an Action
        if "action" in response_json and response_json["action"]:
            tool_name = response_json["action"]
            tool_args = response_json.get("action_input", {})
            thought = response_json.get("thought", "Executing tool...")
            
            print(f"\n🤔 [Thought]: {thought}")
            
            if tool_name in AVAILABLE_TOOLS:
                # Append agent's thought/action to scratchpad
                scratchpad.append({"role": "assistant", "content": raw_output})
                
                # Execute tool dynamically
                if tool_name == "search_the_web":
                    observation = await AVAILABLE_TOOLS[tool_name]()
                else:  # open_page
                    url = tool_args.get("url")
                    if url:
                        observation = await AVAILABLE_TOOLS[tool_name](url)
                    else:
                        observation = "Error: Missing 'url' parameter in action_input."
                
                print(f"👁️ [Observation]: (Fetched {len(observation)} characters of data)")
                
                # Append tool observation to scratchpad for next loop cycle
                scratchpad.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                scratchpad.append({"role": "user", "content": f"Observation: Tool '{tool_name}' is not recognized."})

        # Case 2: LLM provides a Final Answer
        elif "final_answer" in response_json:
            print(f"\n🤔 [Thought]: {response_json.get('thought')}")
            return response_json["final_answer"]
        
        else:
            # Edge case mitigation
            scratchpad.append({"role": "user", "content": "Invalid response state. You must provide either an 'action' or a 'final_answer'."})
            
    return "I was unable to resolve your request within the maximum tool execution limits."

# =====================================================================
# GLOBAL INTERACTIVE CHAT INTERFACE
# =====================================================================

async def main():
    # This list acts as our persistent memory *outside* the ReAct scratchpad loop
    global_conversation_history = []
    
    print("=========================================================")
    print("🤖 Playwright + Groq ReAct Chat Agent Initialized!")
    print("Type 'exit' or 'quit' to terminate.")
    print("=========================================================\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            
            # 1. Wrap the message with constraints and store it in global memory
            wrapped_msg = wrap_user_message(user_input)
            global_conversation_history.append({"role": "user", "content": wrapped_msg})
            
            # 2. Kick off the ReAct execution block
            print("\n🔄 Agent is thinking...")
            final_response = await run_react_loop(global_conversation_history)
            
            # 3. Print the final parsed answer back to user
            print(f"\nAgent: {final_response}\n")
            print("-" * 50)
            
            # 4. Append clean conversation back into history so memory isn't polluted by ReAct logs
            global_conversation_history.append({"role": "assistant", "content": final_response})
            
        except KeyboardInterrupt:
            print("\nSession interrupted. Exiting.")
            break

if __name__ == "__main__":
    asyncio.run(main())