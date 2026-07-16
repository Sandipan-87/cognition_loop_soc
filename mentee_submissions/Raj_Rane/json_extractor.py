"""
Task 5: Strict Data Extraction
Extracts structured JSON from unstructured text and parses it natively in Python.
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# Unstructured input text
raw_text = (
    "We interviewed Alex Mercer today. He is 24 years old and works as a "
    "Junior Data Analyst. His technical toolkit consists of Python, SQL, and Tableau."
)

# Strict data parser system instruction
system_instruction = (
    "You are a strict data parser. You output ONLY raw JSON. "
    "No conversational text. No markdown formatting. No code fences. No explanation. "
    "Output must be a single valid JSON object and nothing else. "
    'The JSON schema is: {"name": "string", "age": integer, "role": "string", "skills": ["string"]}'
)

# Send the unstructured text for extraction
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Extract structured data from this text:\n\n{raw_text}",
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
    ),
)

# Parse the raw response directly into Python
raw_output = response.text.strip()
parsed_data = json.loads(raw_output)

# Print just the skills list to verify clean extraction
print(parsed_data["skills"])
