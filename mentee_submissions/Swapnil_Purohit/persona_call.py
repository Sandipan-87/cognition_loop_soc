import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="How is the weather today?",
    config=types.GenerateContentConfig(
        system_instruction="You are a highly formal 19th-century butler."
    )
)
print(response.text)
