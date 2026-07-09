import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# Load environment variables
load_dotenv()

def main():
    # Initialize the client
    client = genai.Client()
    prompt = "Write only the word 'Hello'."
    
    total_calls = 15
    successful_calls = 0
    attempts = 0
    
    print(f"Attempting to make {total_calls} rapid API requests to Gemini...")
    
    while successful_calls < total_calls:
        attempts += 1
        print(f"Making request #{successful_calls + 1} (Total attempts: {attempts})...")
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            print(f"  Response: {response.text.strip()}")
            successful_calls += 1
            # Sleep briefly to avoid immediately flooding unless testing rate limits
            time.sleep(0.2)
        except APIError as e:
            # Catching Gemini API Rate Limit (typically HTTP 429 / RESOURCE_EXHAUSTED)
            if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                print(f"  [Rate Limit Caught] Status Code: {e.code}. Error: {e.message}")
                print("  Sleeping for 10 seconds before retrying...")
                time.sleep(10)
            else:
                print(f"  [API Error] {e}. Retrying in 5 seconds...")
                time.sleep(5)
        except Exception as e:
            print(f"  [Unexpected Error] {e}. Retrying in 5 seconds...")
            time.sleep(5)
            
    print(f"\nCompleted all {total_calls} calls successfully in {attempts} attempts!")

if __name__ == "__main__":
    main()
