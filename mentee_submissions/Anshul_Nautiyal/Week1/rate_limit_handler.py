import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

for i in range(15):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Say hello {i}"
        )

        print(f"Request {i+1} Success")

    except Exception as e:
        print("Rate limit hit. Waiting...")
        time.sleep(10)
