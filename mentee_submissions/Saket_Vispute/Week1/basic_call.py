import os
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
load_dotenv()

def main():
    # Initialize the Gemini client
    # The client automatically picks up GEMINI_API_KEY from environment variables.
    client = genai.Client()

    prompt = "Explain Newton's 2nd law in one sentence."
    print(f"Sending prompt: {prompt}\n")

    try:
        # Generate content using gemini-2.5-flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        print("Response:")
        print(response.text)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")

if __name__ == "__main__":
    main()
