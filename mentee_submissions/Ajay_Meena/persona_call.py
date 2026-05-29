from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

system_instruction = """
You are a formal 19th-century English butler.

Always speak politely.
Use old-fashioned English.
Address the user respectfully.
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="How is the weather today?",
    config={
        "system_instruction": system_instruction
    }
)

print(response.text)