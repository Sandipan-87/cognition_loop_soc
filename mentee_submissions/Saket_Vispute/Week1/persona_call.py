import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

def main():
    # Initialize Gemini Client
    client = genai.Client()
    
    # Define a highly specific persona ruleset
    system_instruction = (
        "You are a formal, extremely polite 19th-century British butler named Jeeves. "
        "You address the user as 'My Lord', 'My Lady', or 'Master'. "
        "Use formal, elegant language of the Victorian era. "
        "Always remain in character, showing absolute dedication to etiquette and service."
    )
    
    prompt = "How is the weather today?"
    print(f"Sending prompt to Butler persona: '{prompt}'\n")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
        )
        print("Butler Response:")
        print(response.text)
    except Exception as e:
        print(f"Error generating content: {e}")

if __name__ == "__main__":
    main()
