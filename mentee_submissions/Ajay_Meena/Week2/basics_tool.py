import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# -------------------------
# TOOL FUNCTION
# -------------------------
def get_crypto_price(coin: str):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin.lower(), "vs_currencies": "usd"}

    res = requests.get(url, params=params)
    data = res.json()

    return data


# -------------------------
# TOOL DEFINITION
# -------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get crypto price in USD",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string"
                    }
                },
                "required": ["coin"]
            }
        }
    }
]


# -------------------------
# USER INPUT
# -------------------------
user_input = input("Ask something about crypto: ")

messages = [
    {"role": "user", "content": user_input}
]


# -------------------------
# STEP 1: CALL MODEL
# -------------------------
response = client.chat.completions.create(
    model="llama-3.1-70b-versatile",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

msg = response.choices[0].message


# -------------------------
# CHECK TOOL CALL
# -------------------------
if msg.tool_calls:

    messages.append(msg)

    for tool_call in msg.tool_calls:

        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if name == "get_crypto_price":
            result = get_crypto_price(args["coin"])

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })


    # -------------------------
    # FINAL ANSWER
    # -------------------------
    final = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=messages
    )

    print("\nFINAL ANSWER:\n")
    print(final.choices[0].message.content)

else:
    print(msg.content)