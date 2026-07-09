"""
Task 2: Programmatic Execution
Connects to the Gemini API and prints a simple response.
"""

import os
from dotenv import load_dotenv
from google import genai

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# Send a basic prompt and print the response
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain Newton's 2nd law in one sentence.",
)

print(response.text)
