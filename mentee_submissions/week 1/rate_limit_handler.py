import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import errors

#Load environment | initialize the client
load_dotenv()
client = genai.Client()

print("Starting the 15-request loop...\n")

#to successfully complete 15 tasks.
for attempt_number in range(1, 16):
    
    while True:
        try:
            print(f"Task {attempt_number}: Sending request...")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f'Reply with exactly one word: "{attempt_number}"'
            )
            
            print(f"Success! Model replied: {response.text.strip()}")
            
            break 
            
        except errors.APIError as e:
            # The Exception Handler
            if e.code == 429:
                print("--- RATE LIMIT HIT (429)! Bucket is empty. ---")
                print("Sleeping for 15 seconds to let the server reset...\n")
                
                time.sleep(15) 
                
            else:
                print(f"An unexpected API error occurred: {e}")
                break
                
print("\nAll 15 tasks completed successfully!")