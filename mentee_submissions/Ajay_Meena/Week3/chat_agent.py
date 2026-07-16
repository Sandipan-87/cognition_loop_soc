import os
import json
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

client = Groq(api_key="GROQ_API_KEY")

def search_the_web(query: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(f"https://html.duckduckgo.com/html/?q={query}", timeout=10000)
            page.wait_for_timeout(2000)

            results = page.locator(".result__title a")
            snippets = page.locator(".result__snippet")

            count = min(results.count(), 5)

            output = ""
            for i in range(count):
                title = results.nth(i).inner_text()
                link = results.nth(i).get_attribute("href")
                try:
                    snippet = snippets.nth(i).inner_text()
                except:
                    snippet = ""
                output += f"{i+1}. {title}\n{snippet}\n{link}\n\n"

            browser.close()
            return output if output else "No results found."

        except Exception as e:
            browser.close()
            return f"Search failed: {str(e)}"

def open_page(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=10000)
            page.wait_for_timeout(2000)

            content = page.locator("body").inner_text()
            browser.close()
            return content[:3000]

        except Exception as e:
            browser.close()
            return f"Could not open page: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the web for live information using DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a URL and return the text content of the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

system_prompt = """You are a helpful research assistant with memory of the full conversation.
When you need current or live information, use search_the_web.
If you need more detail from a specific page, use open_page with its URL.
You can chain these tools together. Always answer based on what you find."""

messages = [
    {"role": "system", "content": system_prompt}
]

print("Chat Agent ready. Type 'quit' to exit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "quit":
        print("Goodbye!")
        break

    messages.append({"role": "user", "content": user_input})

    while True:
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                print(f"  [Tool: {name}({args})]")

                if name == "search_the_web":
                    result = search_the_web(args["query"])
                elif name == "open_page":
                    result = open_page(args["url"])
                else:
                    result = "Unknown tool."

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            print(f"\nAgent: {msg.content}\n")
            messages.append({"role": "assistant", "content": msg.content})
            break