import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

# Define the target JSON structure using Pydantic
class ProfileSchema(BaseModel):
    name: str
    age: int
    role: str
    skills: list[str]

def main():
    client = genai.Client()
    
    unstructured_text = (
        "We interviewed Alex Mercer today. He is 24 years old and "
        "works as a Junior Data Analyst. His technical toolkit consists "
        "of Python, SQL, and Tableau."
    )
    
    # Configure the client to enforce JSON output matching our Pydantic schema
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ProfileSchema,
        system_instruction="Extract the entities accurately from the text into the specified JSON format."
    )
    
    print("Sending text for structured parsing...")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=unstructured_text,
        config=config
    )
    
    raw_json_string = response.text
    
    try:
        # Parse the raw output string into a Python dictionary
        parsed_data = json.loads(raw_json_string)
        
        print("\n--- Extraction Success ---")
        print(f"Raw String Output: {raw_json_string.strip()}")
        print(f"Parsed Python Type: {type(parsed_data)}")
        print(f"Extracted Skills List: {parsed_data['skills']}")
        
    except json.JSONDecodeError as e:
        print(f"\n[-] Verification failed! Could not parse JSON: {e}")
        print(f"Raw Output was: {raw_json_string}")

if __name__ == "__main__":
    main()