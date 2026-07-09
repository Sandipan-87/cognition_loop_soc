import json
import os

from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

MODEL = "llama-3.3-70b-versatile"

SYSTEM = (
    "You are a research assistant with live web tools. "
    "Use search_the_web when you need current or factual information. "
    "Use open_page to read a specific URL when search snippets are not enough. "
    "You can chain tools: search first, then open a promising link. "
    "Base answers on what you find, and say so if the results don't contain the answer."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": (
                "Search the live web for current information. "
                "Use it whenever the question needs recent or factual data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": (
                "Open a URL and read its visible text. "
                "Use after search_the_web when you need more detail from a specific page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to open.",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


def search_the_web(query: str) -> str:
    """Search the live web and return the top results as text."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://html.duckduckgo.com/html/", timeout=15000)
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            page.wait_for_selector(".result__body", timeout=10000)

            results = []
            for row in page.locator(".result__body").all()[:5]:
                title = row.locator(".result__title").inner_text().strip()
                snippet = row.locator(".result__snippet").inner_text().strip()
                link = row.locator(".result__a").first.get_attribute("href") or ""
                results.append(f"{title}\n{snippet}\nURL: {link}")

            browser.close()
    except PlaywrightTimeout:
        return "Search timed out. The page may be slow or the layout changed."
    except Exception as exc:
        return f"Search failed: {exc}"

    return "\n\n".join(results) or "No results found."


def open_page(url: str) -> str:
    """Open a URL and return its visible text (trimmed)."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            text = page.locator("body").inner_text()
            browser.close()
    except PlaywrightTimeout:
        return "Page load timed out. The site may be slow or blocking automated access."
    except Exception as exc:
        return f"Failed to open page: {exc}"

    return text[:3000]


AVAILABLE_TOOLS = {
    "search_the_web": search_the_web,
    "open_page": open_page,
}


def run_react_turn(client: Groq, messages: list) -> str:
    """Run one user turn through the ReAct loop until the model answers."""
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content or ""

        for call in msg.tool_calls:
            print(f"[tool] {call.function.name}({call.function.arguments})")
            tool_fn = AVAILABLE_TOOLS.get(call.function.name)
            if tool_fn is None:
                result = f"Unknown tool: {call.function.name}"
            else:
                args = json.loads(call.function.arguments)
                result = tool_fn(**args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(result),
                }
            )


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment or .env file.")

    client = Groq(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM}]

    print("Research chat agent (Groq + Playwright)")
    print("Ask anything. Follow-ups are remembered. Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})
        answer = run_react_turn(client, messages)
        print(f"Agent: {answer}\n")


if __name__ == "__main__":
    main()
