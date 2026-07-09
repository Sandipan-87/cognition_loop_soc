import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

def main():
    # Initialize the client
    client = genai.Client()
    
    # Target unstructured text block
    unstructured_text = (
        "We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. "
        "His technical toolkit consists of Python, SQL, and Tableau."
    )
    
    # System instruction directing the model to act as a strict parser
    system_instruction = (
        "You are a strict data parser. You must extract information from the input text and format it "
        "into a valid JSON object. Do not include any explanation, conversational text, or markdown code block formatting. "
        "The output must match this exact schema shape:\n"
        '{"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}'
    )
    
    print(f"Input Unstructured Text:\n{unstructured_text}\n")
    
    try:
        # Generate the structured response
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=unstructured_text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",  # Force JSON output format
                temperature=0.0,
            ),
        )
        
        raw_output = response.text.strip()
        print("Raw Output from Model:")
        print(raw_output)
        
        # Load the raw string directly into native Python JSON
        data = json.loads(raw_output)
        
        # Extract and print just the skills list
        skills = data.get("skills", [])
        print("\nExtracted Skills List (Native Python List):")
        print(skills)
        print(f"Verification of data type: {type(skills)}")
        
    except json.JSONDecodeError as jde:
        print(f"\nFailed to parse JSON. Raw output was: {raw_output}")
        print(f"Error: {jde}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
