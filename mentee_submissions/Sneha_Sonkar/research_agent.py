import os
import json
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# --------------------------------------------------
# Load API Key
# --------------------------------------------------
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"

# --------------------------------------------------
# Tool
# --------------------------------------------------
def search_the_web(query: str) -> str:
    """
    Searches Hacker News for recent technology news.
    """

    print(f"\n[Tool] Searching for: {query}")

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            page.goto("https://news.ycombinator.com", timeout=20000)

            page.wait_for_selector(".titleline", timeout=10000)

            articles = page.locator(".titleline > a").all()

            stopwords = {
                "latest",
                "recent",
                "news",
                "today",
                "about",
                "the",
                "a",
                "an",
            }

            keywords = [
                word.lower()
                for word in query.split()
                if word.lower() not in stopwords
            ]

            results = []

            for article in articles[:30]:

                title = article.inner_text()

                url = article.get_attribute("href")

                if any(k in title.lower() for k in keywords):

                    results.append(
                        f"Headline: {title}\nURL: {url}"
                    )

            if not results:

                results.append("No exact matches found.\n")

                for article in articles[:5]:

                    results.append(
                        f"Headline: {article.inner_text()}\nURL: {article.get_attribute('href')}"
                    )

            browser.close()

            return (
                "SEARCH COMPLETE.\n\n"
                "Summarize ONLY these search results.\n"
                "Do NOT search again.\n"
                "Do NOT open URLs.\n\n"
                + "\n\n".join(results)
            )

    except Exception as e:
        return f"Tool Error: {e}"


available_tools = {
    "search_the_web": search_the_web
}

# --------------------------------------------------
# Tool Schema
# --------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search Hacker News for recent technology news.",
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


# --------------------------------------------------
# Agent
# --------------------------------------------------
def run_agent():

    user_question = input("Ask a question: ")

    messages = [
        {
            "role": "system",
            "content": """
You are a research assistant.

You have exactly ONE tool:

search_the_web(query)

Rules:
1. Use the tool if recent information is needed.
2. Call it at most once.
3. After receiving tool results, summarize them.
4. Never search again.
5. Never open URLs.
6. Never call any tool except search_the_web.
"""
        },
        {
            "role": "user",
            "content": user_question
        }
    ]

    # -------------------------------
    # First model call
    # -------------------------------
    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

    except Exception as e:

        print(e)

        return

    message = response.choices[0].message

    # -------------------------------
    # No tool needed
    # -------------------------------
    if not message.tool_calls:

        print("\nFinal Answer\n")

        print(message.content)

        return

    # -------------------------------
    # Execute tool
    # -------------------------------
    tool_call = message.tool_calls[0]

    arguments = json.loads(tool_call.function.arguments)

    result = search_the_web(**arguments)

    messages.append(message)

    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.function.name,
        "content": result
    })

    # -------------------------------
    # Second model call
    # IMPORTANT:
    # No tools are provided now.
    # -------------------------------
    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )

    except Exception as e:

        print(e)

        return

    print("\n" + "=" * 60)

    print("Final Answer\n")

    print(response.choices[0].message.content)

    print("=" * 60)


if __name__ == "__main__":
    run_agent()