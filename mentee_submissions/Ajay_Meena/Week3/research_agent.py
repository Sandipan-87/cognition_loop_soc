import os
import json
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

client = Groq(api_key="GROQ_API_KEY")

def search_the_web(query: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            encoded = query.replace(" ", "+")
            page.goto(f"https://lite.duckduckgo.com/lite/?q={encoded}", timeout=15000)
            page.wait_for_timeout(2000)

            links = page.locator("a.result-link")
            snippets = page.locator("td.result-snippet")

            count = min(links.count(), 5)
            output = ""

            for i in range(count):
                try:
                    title = links.nth(i).inner_text()
                    link = links.nth(i).get_attribute("href")
                    try:
                        snippet = snippets.nth(i).inner_text()
                    except:
                        snippet = ""
                    output += f"{i+1}. {title}\n{snippet}\n{link}\n\n"
                except:
                    continue

            browser.close()
            print(f"[Raw results:\n{output}\n]")
            return output if output else "No results found."

        except Exception as e:
            browser.close()
            return f"Search failed: {str(e)}"
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
    }
]

system_prompt = """You are a research assistant. 
When you need current information, use search_the_web.
IMPORTANT: Only answer based on what the search results actually say.
If the results don't clearly answer the question, say you couldn't find reliable information and try a different search query.
Never guess or make up names, facts, or figures."""

question = input("What do you want to research? ")

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": question}
]

while True:
    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
    except Exception as e:
        print(f"  [API error: {str(e)}, retrying without tools...]")
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages
        )

    msg = response.choices[0].message
    # rest stays the same

    if msg.tool_calls:
        messages.append(msg)

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"\n[Tool call: {name}({args})]")

            if name == "search_the_web":
                result = search_the_web(args["query"])
                print(f"[Got {len(result)} chars of results]")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
    else:
        print("\nAnswer:\n")
        print(msg.content)
        break