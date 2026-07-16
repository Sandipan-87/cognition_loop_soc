"""
Week 3 - Task 2: chat_agent.py
Continuous chat agent with memory and two chained tools:
  1. search_the_web — find results via DuckDuckGo
  2. open_page — open a URL and read its content
The agent can chain: search → pick a link → open it → answer.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# Load API key from .env
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def search_the_web(query: str) -> str:
    """Search DuckDuckGo HTML and return top results."""
    print(f"  🔍 Searching: '{query}'")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://html.duckduckgo.com/html/?q={query}"
            page.goto(url, timeout=15000)

            results = []
            result_elements = page.query_selector_all(".result")
            for elem in result_elements[:7]:
                title_el = elem.query_selector(".result__a")
                snippet_el = elem.query_selector(".result__snippet")
                link_el = elem.query_selector(".result__url")

                title = title_el.inner_text() if title_el else "No title"
                snippet = snippet_el.inner_text() if snippet_el else "No snippet"
                link = link_el.get_attribute("href") if link_el else ""

                results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")

            browser.close()
            return "\n\n---\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search failed: {str(e)}"


def open_page(url: str) -> str:
    """Open a URL and return its text content (truncated)."""
    print(f"  🌐 Opening page: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_load_state("domcontentloaded")

            # Get the main text content, truncated to avoid token limits
            text = page.inner_text("body")
            browser.close()

            # Truncate to ~3000 chars to stay within token limits
            if len(text) > 3000:
                text = text[:3000] + "\n\n... [truncated]"
            return text if text.strip() else "Page loaded but no readable text found."
    except Exception as e:
        return f"Failed to open page: {str(e)}"


# Tool schemas
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the web using DuckDuckGo for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a specific URL and read its text content. Use this after searching to get detailed information from a specific page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to open and read.",
                    }
                },
                "required": ["url"],
            },
        },
    },
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page,
}

SYSTEM_PROMPT = (
    "You are a research assistant that can search the web and open pages. "
    "Use search_the_web to find information, then use open_page to read specific "
    "pages for more detail. You remember the full conversation — use prior context "
    "to answer follow-ups. Be concise and helpful. Cite sources when possible."
)


import re

def get_model_response(messages, use_tools=True):
    """Call Groq API with robust self-healing for tool_use_failed errors."""
    try:
        if use_tools:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        else:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )
        return response.choices[0].message
    except Exception as e:
        error_msg = str(e)
        if "tool_use_failed" in error_msg and use_tools:
            # Attempt to self-heal
            failed_gen = ""
            if hasattr(e, 'body') and isinstance(e.body, dict) and 'error' in e.body:
                failed_gen = e.body['error'].get('failed_generation', '')
            if not failed_gen:
                match_err = re.search(r"'failed_generation':\s*'([^']+)'", error_msg)
                if match_err:
                    failed_gen = match_err.group(1)
            
            print(f"  [*] Attempting self-healing parse on: {failed_gen}")
            match_fn = re.search(r'<function=(\w+)(.*?)</function>', failed_gen)
            if match_fn:
                fn_name = match_fn.group(1)
                fn_args_str = match_fn.group(2).strip()
                
                print(f"  [Self-Heal] Extracted tool: {fn_name} with args: {fn_args_str}")
                try:
                    fn_args = json.loads(fn_args_str)
                except Exception:
                    if fn_args_str.startswith('"') and fn_args_str.endswith('"'):
                        fn_args_str = fn_args_str[1:-1]
                    fn_args = {"query": fn_args_str}
                
                # Execute the tool manually
                try:
                    result = available_tools[fn_name](**fn_args)
                except Exception as ex:
                    result = f"Tool execution failed: {str(ex)}"
                
                print(f"  [Result] Got {len(result)} chars of results\n")
                
                # Append tool call and response to history
                mock_tool_call_id = f"call_heal_{fn_name}"
                messages.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": mock_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": json.dumps(fn_args)
                            }
                        }
                    ]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": mock_tool_call_id,
                    "content": result,
                })
                
                # Call the model again recursively to generate next action/response
                return get_model_response(messages, use_tools=True)
            
            # If parsing failed, retry without tools
            print("  [*] Self-healing parse failed, retrying without tools...")
            return get_model_response(messages, use_tools=False)
        else:
            raise


def process_tool_calls(messages, msg):
    """Handle tool calls in a loop until the model gives a text response."""
    max_tool_rounds = 5

    for _ in range(max_tool_rounds):
        if not msg.tool_calls:
            return msg.content

        messages.append(msg)

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            print(f"  🔧 Tool: {fn_name}({fn_args})")

            try:
                result = available_tools[fn_name](**fn_args)
            except Exception as e:
                result = f"Tool error: {str(e)}"

            print(f"  📄 Got {len(result)} chars\n")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

        # Call the model again using get_model_response helper
        msg = get_model_response(messages)

    # Fallback: force a text answer
    messages.append({"role": "user", "content": "Please summarize what you found and answer now."})
    response = client.chat.completions.create(model=MODEL, messages=messages)
    return response.choices[0].message.content


def main():
    """Main chat loop with persistent memory."""
    print("=" * 60)
    print("🤖 Research Chat Agent")
    print("   I can search the web and read pages for you.")
    print("   Type 'quit' or 'exit' to end the conversation.")
    print("=" * 60)

    # Memory lives outside the loop — persists across turns
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\n💬 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("👋 Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # First model call using get_model_response helper
        msg = get_model_response(messages)

        # Process any tool calls
        answer = process_tool_calls(messages, msg)

        # Store the final answer in memory
        messages.append({"role": "assistant", "content": answer})

        print(f"\n🤖 Agent: {answer}")


if __name__ == "__main__":
    main()
