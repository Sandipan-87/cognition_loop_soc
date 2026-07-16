import os
import json
import asyncio
from dotenv import load_dotenv
from groq import Groq
from playwright.async_api import async_playwright

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


# ----------------------------
# TOOL
# ----------------------------
async def search_the_web(query):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        try:
            await page.goto(
                f"https://html.duckduckgo.com/html/?q={query}",
                timeout=30000,
            )

            await page.wait_for_selector(".result", timeout=10000)

            items = await page.locator(".result").all()

            for item in items[:5]:
                title = await item.locator(".result__title").inner_text()
                link = await item.locator("a").get_attribute("href")

                try:
                    snippet = await item.locator(".result__snippet").inner_text()
                except:
                    snippet = ""

                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                })

        except Exception as e:
            results.append({"error": str(e)})

        await browser.close()

    return results


tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web using DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"],
            },
        },
    }
]

available_tools = {
    "search_the_web": lambda query: asyncio.run(search_the_web(query))
}


question = input("Ask something: ")

messages = [
    {
        "role": "system",
        "content": """You are a research assistant.

Use search_the_web whenever current or live information is needed.

Continue using tools until you have enough information to answer.""",
    },
    {
        "role": "user",
        "content": question,
    },
]


while True:

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    message = response.choices[0].message
    messages.append(message)

    if not message.tool_calls:
        print("\nAnswer:\n")
        print(message.content)
        break

    for tool_call in message.tool_calls:

        name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"\nTool Called -> {name}")
        print(arguments)

        try:
            result = available_tools[name](**arguments)
        except Exception as e:
            result = {"error": str(e)}

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            }
        )