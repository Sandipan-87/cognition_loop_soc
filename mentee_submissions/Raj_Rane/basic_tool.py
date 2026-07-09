"""
Week 2 - Task 1: basic_tool.py
AI agent that calls a tool to fetch live crypto data via CoinGecko API.
Groq decides when to call the tool, runs the function, and explains the result.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

# Load API key from .env
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def get_crypto_price(coin_id: str) -> dict:
    """Fetch live price data for a cryptocurrency from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id.lower(),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if coin_id.lower() in data:
            info = data[coin_id.lower()]
            return {
                "coin": coin_id,
                "price_usd": info.get("usd"),
                "market_cap_usd": info.get("usd_market_cap"),
                "change_24h_percent": info.get("usd_24h_change"),
            }
        return {"error": f"Coin '{coin_id}' not found. Try 'bitcoin', 'ethereum', etc."}
    except requests.RequestException as e:
        return {"error": str(e)}


# Define the tool schema for Groq
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get the current USD price, market cap, and 24-hour change for a cryptocurrency. Use CoinGecko coin IDs like 'bitcoin', 'ethereum', 'solana', 'dogecoin'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": "The CoinGecko ID of the cryptocurrency (e.g. 'bitcoin', 'ethereum', 'solana').",
                    }
                },
                "required": ["coin_id"],
            },
        },
    }
]

# Map tool names to functions
available_tools = {"get_crypto_price": get_crypto_price}


def run_agent(user_question: str):
    """Run the agent loop: ask → tool call → final answer."""
    print(f"\n🧠 User: {user_question}")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful crypto assistant. When asked about cryptocurrency prices, "
                "use the get_crypto_price tool to fetch live data. Then explain the result clearly."
            ),
        },
        {"role": "user", "content": user_question},
    ]

    # Step 1: Send the question with tools
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    msg = response.choices[0].message

    # Step 2: Check if the model wants to call a tool
    if msg.tool_calls:
        # Append the assistant message with tool calls
        messages.append(msg)

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            print(f"🔧 Tool call: {fn_name}({fn_args})")

            # Execute the real function
            result = available_tools[fn_name](**fn_args)
            print(f"📊 Tool result: {json.dumps(result, indent=2)}")

            # Send the result back to the model
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

        # Step 3: Get the final answer
        final_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )
        print(f"\n🤖 Agent: {final_response.choices[0].message.content}")
    else:
        # No tool call needed
        print(f"\n🤖 Agent: {msg.content}")


if __name__ == "__main__":
    # Demo questions
    run_agent("What's the current price of Bitcoin?")
    print("\n" + "=" * 60)
    run_agent("How is Ethereum doing today compared to yesterday?")
