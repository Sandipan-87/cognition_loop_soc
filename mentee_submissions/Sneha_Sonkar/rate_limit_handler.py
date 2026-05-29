import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()

def main():
    client = genai.Client()
    prompt = "Give me one random word."
    
    print("Starting 15 rapid API calls...\n")
    
    for i in range(1, 16):
        while True:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                print(f"Request {i} Succeeded: {response.text.strip()}")
                break # Break the inner while loop to move to the next request
                
            except APIError as e:
                # Catch Resource Exhausted / Rate Limit (HTTP 429)
                if e.code == 429:
                    print(f"\n[!] Rate limit hit on request {i}. Pausing for 15 seconds...")
                    time.sleep(15)
                    print("Retrying request...\n")
                    # Does not break the while loop, so it retries the same request 'i'
                else:
                    print(f"An unexpected API error occurred: {e}")
                    raise e
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                raise e

if __name__ == "__main__":
    main()