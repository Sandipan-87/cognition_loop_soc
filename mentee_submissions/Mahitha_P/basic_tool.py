import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def get_weather(city):
    cities = {
        "hyderabad": (17.3850, 78.4867),
        "mumbai": (19.0760, 72.8777),
        "delhi": (28.6139, 77.2090),
        "bangalore": (12.9716, 77.5946),
        "chennai": (13.0827, 80.2707)
    }

    city = city.lower()

    if city not in cities:
        return {"error": f"Weather unavailable for {city}"}

    lat, lon = cities[city]

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current_weather=true"
    )

    response = requests.get(url, timeout=10)

    return response.json()


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

question = input("Ask me something: ")

messages = [
    {
        "role": "user",
        "content": question
    }
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

    arguments = json.loads(
        tool_call.function.arguments
    )

    result = get_weather(
        arguments["city"]
    )

    messages.append(message)

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result)
        }
    )

    final_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    print("\nAssistant:")
    print(
        final_response
        .choices[0]
        .message
        .content
    )

else:
    print("\nAssistant:")
    print(message.content)