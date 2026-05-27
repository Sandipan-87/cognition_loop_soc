import os
import json
from dotenv import load_dotenv
from google import genai

# 1. Setup the client
load_dotenv()
client = genai.Client()

# 2. The Unstructured Input Data
raw_text = "We crossed paths with that rookie, Alex Mercer, on the Grand Line today. He is 24 years old and sails as a Junior Navigator. His combat arsenal consists of Observation Haki, a Flintlock Pistol, and the Clima-Tact."

# 3. The System Instruction (Strict Data Parser Rules)
parser_rules = """
You are a strict data parser. Your only job is to extract information from unstructured text and output it in a highly structured JSON format.
You must output ONLY raw, valid JSON. 
Do not include any conversational text before or after the JSON.
DO NOT wrap the output in markdown code blocks (do not use ```json or ```).
The target JSON schema must look exactly like this:
{"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}
"""

print("Sending unstructured text to the model...\n")

# 4. The API Call
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=raw_text,
    config={
        'system_instruction': parser_rules
    }
)

raw_output = response.text.strip()

print(" Raw String Received from API ")
print(raw_output)
print(f"Type: {type(raw_output)}\n")

# Deserialization
try:
    parsed_data = json.loads(raw_output)
    
    print("Successfully Converted to Python Dictionary")
    
    skills_list = parsed_data["skills"]
    print(f"Extracted Skills: {skills_list}")
    print(f"Type: {type(skills_list)}")
    
except json.JSONDecodeError as e:
    print(f"CRITICAL ERROR: The model failed to follow instructions and returned invalid JSON. Details: {e}")