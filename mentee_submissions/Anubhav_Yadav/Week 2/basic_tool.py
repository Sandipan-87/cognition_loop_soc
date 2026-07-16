import json
import os

import requests
from dotenv import load_dotenv
from groq import Groq

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": (
                "Fetch the current USD price and 24-hour change for a cryptocurrency "
                "using live market data from CoinGecko."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": (
                            "CoinGecko coin id, e.g. bitcoin, ethereum, solana, dogecoin."
                        ),
                    }
                },
                "required": ["coin_id"],
            },
        },
    }
]


def get_crypto_price(coin_id: str) -> dict:
    """Call CoinGecko and return price data for one coin."""
    response = requests.get(
        COINGECKO_URL,
        params={
            "ids": coin_id.lower().strip(),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if coin_id.lower() not in data:
        return {"error": f"No market data found for '{coin_id}'."}

    coin = data[coin_id.lower()]
    return {
        "coin_id": coin_id.lower(),
        "price_usd": coin.get("usd"),
        "change_24h_percent": coin.get("usd_24h_change"),
    }


def run_tool(name: str, arguments: str) -> str:
    """Execute a tool by name and return a JSON string for the model."""
    if name != "get_crypto_price":
        return json.dumps({"error": f"Unknown tool: {name}"})

    args = json.loads(arguments)
    result = get_crypto_price(args["coin_id"])
    return json.dumps(result)


def ask_agent(client: Groq, question: str) -> str:
    """Send a question through the tool-calling loop and return the final answer."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Use get_crypto_price when the user asks "
                "about live cryptocurrency prices. Explain results clearly in plain language."
            ),
        },
        {"role": "user", "content": question},
    ]

    first = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    assistant_message = first.choices[0].message
    messages.append(assistant_message)

    if assistant_message.tool_calls:
        for tool_call in assistant_message.tool_calls:
            tool_result = run_tool(
                tool_call.function.name,
                tool_call.function.arguments,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

        second = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        return second.choices[0].message.content or ""

    return assistant_message.content or ""


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment or .env file.")

    client = Groq(api_key=api_key)

    print("Crypto price agent (powered by Groq + CoinGecko)")
    print("Ask about any coin, e.g. 'What is Bitcoin worth right now?'")
    print("Type 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        answer = ask_agent(client, question)
        print(f"\nAgent: {answer}\n")


if __name__ == "__main__":
    main()
