import os
import json
import asyncio
from dotenv import load_dotenv
from groq import Groq
from playwright.async_api import async_playwright

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"


# ============================================================
# TOOL 1 : Search Web
# ============================================================

async def search_the_web(query):

    results = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        try:

            await page.goto(
                f"https://html.duckduckgo.com/html/?q={query}",
                timeout=30000
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

                results.append(
                    {
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    }
                )

        except Exception as e:

            results.append({"error": str(e)})

        await browser.close()

    return results


# ============================================================
# TOOL 2 : Open Page
# ============================================================

async def open_page(url):

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        try:

            await page.goto(
                url,
                timeout=30000
            )

            await page.wait_for_load_state("networkidle")

            text = await page.locator("body").inner_text()

            text = text[:5000]

        except Exception as e:

            text = str(e)

        await browser.close()

    return text


# ============================================================
# TOOLS
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {

            "name": "search_the_web",

            "description": "Search the live web.",

            "parameters": {

                "type": "object",

                "properties": {

                    "query": {

                        "type": "string",

                        "description": "Search query"

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

            "description": "Open a webpage and read its contents.",

            "parameters": {

                "type": "object",

                "properties": {

                    "url": {

                        "type": "string",

                        "description": "Webpage URL"

                    }

                },

                "required": ["url"]

            }

        }

    }

]


available_tools = {

    "search_the_web": lambda query:
        asyncio.run(search_the_web(query)),

    "open_page": lambda url:
        asyncio.run(open_page(url))

}


# ============================================================
# MEMORY
# ============================================================

messages = [

    {

        "role": "system",

        "content": """
You are an autonomous research assistant.

You have two tools.

1. search_the_web(query)
2. open_page(url)

When needed, first search.

Then open one of the returned pages.

Use the page contents to answer.

Remember the previous conversation.
"""

    }

]


# ============================================================
# CHAT LOOP
# ============================================================

while True:

    user = input("\nYou: ")

    if user.lower() == "quit":
        print("Goodbye!")
        break

    messages.append(

        {

            "role": "user",

            "content": user

        }

    )

    while True:

        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=TOOLS,

            tool_choice="auto"

        )

        message = response.choices[0].message

        messages.append(message)

        if not message.tool_calls:

            print("\nAssistant:\n")

            print(message.content)

            break

        for tool_call in message.tool_calls:

            name = tool_call.function.name

            args = json.loads(tool_call.function.arguments)

            print(f"\nTool Called -> {name}")

            print(args)

            try:

                result = available_tools[name](**args)

            except Exception as e:

                result = {

                    "error": str(e)

                }

            print("\nTool Output:")

            if isinstance(result, str):

                print(result[:1000])

            else:

                print(json.dumps(result, indent=2))

            messages.append(

                {

                    "role": "tool",

                    "tool_call_id": tool_call.id,

                    "name": name,

                    "content": json.dumps(result)

                }

            )