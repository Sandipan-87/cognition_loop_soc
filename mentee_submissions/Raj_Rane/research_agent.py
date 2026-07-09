"""
Week 3 - Task 1: research_agent.py
ReAct agent: Groq reasons + Playwright acts. Searches the web to answer questions
a plain LLM cannot.
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
    """Search DuckDuckGo HTML and return top results as text."""
    print(f"  🔍 Searching the web for: '{query}'")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://html.duckduckgo.com/html/?q={query}"
            page.goto(url, timeout=15000)

            # Extract search results
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

            if results:
                return "\n\n---\n\n".join(results)
            return "No results found for that query."
    except Exception as e:
        return f"Search failed: {str(e)}"


# Tool schema for Groq
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the web using DuckDuckGo to find current information. Use this when you need live, up-to-date data that you don't have in your training data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]

available_tools = {"search_the_web": search_the_web}


import re

def run_research_agent(question: str):
    """Run the ReAct loop until the agent can answer."""
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful research assistant. Use the search_the_web tool to find "
                "current, live information to answer the user's question. Be concise and cite your sources."
            ),
        },
        {"role": "user", "content": question},
    ]

    max_iterations = 5

    for iteration in range(max_iterations):
        print(f"--- Iteration {iteration + 1} ---")
        msg = None

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message
        except Exception as e:
            error_msg = str(e)
            print(f"  [!] Groq API error: {error_msg[:150]}")
            
            # Self-healing parser for tool_use_failed
            if "tool_use_failed" in error_msg:
                # Try to extract the failed generation details
                failed_gen = ""
                if hasattr(e, 'body') and isinstance(e.body, dict) and 'error' in e.body:
                    failed_gen = e.body['error'].get('failed_generation', '')
                if not failed_gen:
                    # Fallback regex parse from string representation
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
                        # Fallback parsing for queries directly passed as string
                        if fn_args_str.startswith('"') and fn_args_str.endswith('"'):
                            fn_args_str = fn_args_str[1:-1]
                        fn_args = {"query": fn_args_str}
                    
                    # Execute the tool manually
                    try:
                        result = available_tools[fn_name](**fn_args)
                    except Exception as ex:
                        result = f"Tool execution failed: {str(ex)}"
                    
                    print(f"  [Result] Got {len(result)} chars of results\n")
                    
                    # Create a mock tool call object to append
                    mock_tool_call_id = f"call_{iteration}_{fn_name}"
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
                    continue # successfully recovered, proceed to next iteration
            
            # If not tool_use_failed or self-healing failed, fall back
            print("  [*] Falling back to simple call without tools...")
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                )
                msg = response.choices[0].message
            except Exception as ex:
                print(f"  [!] Fallback failed: {ex}")
                raise

        if not msg:
            continue

        if msg.tool_calls:
            messages.append(msg)

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"  [Tool] {fn_name}({fn_args})")

                # Execute the tool
                try:
                    result = available_tools[fn_name](**fn_args)
                except Exception as e:
                    result = f"Tool execution failed: {str(e)}"

                print(f"  [Result] Got {len(result)} chars of results\n")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
        else:
            # The model has enough info to answer
            print(f"\nAnswer:\n{msg.content}\n")
            return msg.content

    # If we exhausted iterations, get a final answer
    messages.append({"role": "user", "content": "Please give your best answer now based on what you've found."})
    final = client.chat.completions.create(model=MODEL, messages=messages)
    answer = final.choices[0].message.content
    print(f"\nAnswer:\n{answer}\n")
    return answer


if __name__ == "__main__":
    # Test with a question that requires live data
    run_research_agent("What are the top stories on Hacker News today?")

