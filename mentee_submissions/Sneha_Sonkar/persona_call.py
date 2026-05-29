import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def main():
    client = genai.Client()
    
    # Define the ruleset/persona configuration
    config = types.GenerateContentConfig(
        system_instruction="You are a retro, green-screen 1980s computer terminal terminal running on MS-DOS. Use technical, robotic jargon, uppercase text where appropriate, and terminal-style syntax indicators like 'ERROR:' or 'SYSTEM:'."
    )
    
    prompt = "How is the weather today?"
    print(f"Prompt: {prompt}\n")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config
    )
    
    print("Persona Output:")
    print(response.text)

if __name__ == "__main__":
    main()