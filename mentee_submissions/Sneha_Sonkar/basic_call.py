import os
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()

def main():
    # The client automatically picks up GEMINI_API_KEY from the environment
    client = genai.Client()
    
    prompt = "Explain Newton's 2nd law in one sentence."
    print(f"Sending prompt: '{prompt}'...\n")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    print("Response:")
    print(response.text)

if __name__ == "__main__":
    main()