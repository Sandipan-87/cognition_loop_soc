import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="Explain Newton's 2nd law in one sentence"
)
print(response.text)
