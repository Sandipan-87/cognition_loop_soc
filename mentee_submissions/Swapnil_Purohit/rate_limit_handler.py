import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

for i in range(15):
    try:
        print(f"Request {i+1}...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Say hi"
        )
        print("Success:", response.text.strip())
    except Exception as e:
        print(f"Exception caught: {e}")
        print("Rate limit likely hit, sleeping for 10 seconds...")
        time.sleep(10)
