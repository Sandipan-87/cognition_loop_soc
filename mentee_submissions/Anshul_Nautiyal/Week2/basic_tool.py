import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])


def get_crypto_price(coin):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
    data = requests.get(url).json()

    if coin in data:
        return json.dumps(
            {"coin": coin, "price_usd": data[coin]["usd"]}
        )

    return json.dumps({"error": "Coin not found"})


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get the current USD price of a cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Cryptocurrency name like bitcoin or ethereum"
                    }
                },
                "required": ["coin"]
            }
        }
    }
]

question = input("Ask me about a crypto price: ")

messages = [
    {"role": "user", "content": question}
]

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

message = response.choices[0].message

if message.tool_calls:

    tool_call = message.tool_calls[0]

    args = json.loads(tool_call.function.arguments)

    result = get_crypto_price(args["coin"])

    messages.append(message)

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        }
    )

    final_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    print(final_response.choices[0].message.content)

else:
    print(message.content)
