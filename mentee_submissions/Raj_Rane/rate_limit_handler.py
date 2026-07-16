"""
Task 3: Managing Rate Limits
Demonstrates graceful handling of API rate limits with retry logic.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError, ServerError

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# Attempt 15 rapid API calls, handling rate limits gracefully
for i in range(1, 16):
    while True:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Say 'Request {i} successful' and nothing else.",
            )
            print(f"Request {i}: {response.text.strip()}")
            break  # Success — move to the next request

        except (ClientError, ServerError) as e:
            wait_time = 10
            print(f"Request {i}: Rate limit / server error hit. Pausing for {wait_time} seconds...")
            time.sleep(wait_time)
            print(f"Request {i}: Retrying...")
