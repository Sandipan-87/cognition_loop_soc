import os
import json
from urllib.request import urlopen
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = 'llama-3.1-8b-instant'

# 1. Define the actual Python function (the tool)
def get_crypto_price(coin_id: str) -> dict:
    """Fetch the live price of a cryptocurrency in USD using CoinGecko API."""
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    with urlopen(url) as response:
        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            if coin_id in data:
                return {"coin_id": coin_id, "price_usd": data[coin_id]["usd"]}
    return {"error": "Could not fetch price or coin not found."}

# 2. Describe the tool to Groq
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get the current live price of a cryptocurrency in USD.",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": "The ID of the cryptocurrency on CoinGecko (e.g., 'bitcoin', 'ethereum').",
                    }
                },
                "required": ["coin_id"],
            },
        },
    }
]

# 3. Setup the initial conversation
messages = [
    {"role": "system", "content": "You are a helpful crypto assistant. Use the get_crypto_price tool when asked about prices."},
    {"role": "user", "content": "What is the current price of Ethereum?"}
]

print("User: What is the current price of Ethereum?")
print("Sending initial request to Groq...")

# In the newer Groq library versions, the tool calls are accessible differently
response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    tools=tools,
    tool_choice="auto",
    max_tokens=4096
)

response_message = response.choices[0].message
messages.append(response_message)

# 4. Check if the model wants to call a tool
if response_message.tool_calls:
    for tool_call in response_message.tool_calls:
        if tool_call.function.name == "get_crypto_price":
            # Extract arguments
            function_args = json.loads(tool_call.function.arguments)
            coin_id = function_args.get("coin_id")
            print(f"-> Model decided to call get_crypto_price('{coin_id}')")
            
            # Execute the actual Python function
            function_response = get_crypto_price(coin_id)
            print(f"-> API Response: {function_response}")
            
            # Append the result back to the messages
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "get_crypto_price",
                    "content": json.dumps(function_response),
                }
            )
            
    # 5. Call the model again with the new information so it can answer naturally
    print("Sending tool result back to Groq for final answer...")
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    print("\nFinal Answer:")
    print(final_response.choices[0].message.content)
else:
    # If it didn't call a tool, just print the response
    print("\nFinal Answer:")
    print(response_message.content)
