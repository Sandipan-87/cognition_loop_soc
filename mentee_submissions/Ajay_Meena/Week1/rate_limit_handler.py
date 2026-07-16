from google import genai
from dotenv import load_dotenv
import os
import time

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

for i in range(15):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Tell me one interesting fact about space."
        )

        print(f"Request {i + 1}:")
        print(response.text)

    except Exception:
        print(f"Request {i + 1} failed. Retrying...")
        time.sleep(10)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Tell me one interesting fact about space."
            )

            print(response.text)

        except Exception:
            print("Could not complete the request.")
            break