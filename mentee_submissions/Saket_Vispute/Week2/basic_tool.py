import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Real python function to fetch weather data using open-meteo (no API key required)
def get_current_weather(city: str) -> str:
    """
    Get the current weather for a given city by geocoding its name and calling Open-Meteo.
    """
    try:
        # Step 1: Geocode city name to lat/lon using Open-Meteo Geocoding API
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_res = requests.get(geocode_url, timeout=10)
        if geo_res.status_code != 200:
            return f"Error: Geocoding API returned status code {geo_res.status_code}"
            
        geo_data = geo_res.json()
        results = geo_data.get("results")
        if not results:
            return f"Error: City '{city}' could not be resolved to geographical coordinates."
            
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        name = results[0]["name"]
        country = results[0].get("country", "Unknown Country")
        
        # Step 2: Fetch current weather for the coordinates
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_res = requests.get(weather_url, timeout=10)
        if weather_res.status_code != 200:
            return f"Error: Weather API returned status code {weather_res.status_code}"
            
        weather_data = weather_res.json()
        current = weather_data.get("current_weather")
        if not current:
            return f"Error: No current weather data returned for {name}."
            
        temp = current.get("temperature")
        wind = current.get("windspeed")
        time_measured = current.get("time")
        
        return (
            f"Current weather in {name}, {country} (Lat: {lat}, Lon: {lon}): "
            f"Temperature is {temp}°C, Wind Speed is {wind} km/h (measured at {time_measured})."
        )
    except Exception as e:
        return f"Error occurred while retrieving weather: {str(e)}"

def main():
    # Verify API key
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY is not set in .env. The script will fail when calling Groq.")
    
    # Initialize Groq client
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Define tool schema for Groq
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Retrieve current weather details for a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city, e.g. London, Paris, Tokyo."
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    # Prompt the user for input or use a default question
    user_query = input("Ask a weather question (e.g., 'What's the weather in Tokyo?'): ").strip()
    if not user_query:
        user_query = "What is the weather in Paris right now?"
        print(f"Using default query: {user_query}")
        
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Use the tools provided to look up real-time information when needed."
        },
        {
            "role": "user",
            "content": user_query
        }
    ]
    
    print("\nCalling Groq to determine next action...")
    try:
        # First completion call
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # Check if the model decided to call a tool
        if response_message.tool_calls:
            print("Model decided to use a tool!")
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                
                print(f"  Tool Name: {func_name}")
                print(f"  Arguments: {func_args}")
                
                if func_name == "get_current_weather":
                    # Execute tool
                    city_param = func_args.get("city")
                    print(f"  Executing get_current_weather for '{city_param}'...")
                    tool_result = get_current_weather(city_param)
                    print(f"  Tool Result: {tool_result}")
                    
                    # Append result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": tool_result
                    })
            
            print("\nSending tool observation back to Groq for final answer...")
            # Second completion call with the tool results
            second_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages
            )
            
            print("\nFinal Answer:")
            print(second_response.choices[0].message.content)
            
        else:
            print("Model did not request any tool calls.")
            print("\nAnswer:")
            print(response_message.content)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
