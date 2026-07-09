import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

text = "We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. His technical toolkit consists of Python, SQL, and Tableau."

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=text,
    config=types.GenerateContentConfig(
        system_instruction="""You are a strict data parser. Output ONLY raw JSON, with no conversational text and no markdown formatting wrappers. The target JSON schema must look like this:
{"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}""",
        response_mime_type="application/json"
    )
)

# Pass the model's raw string output directly into Python's native json.loads() function
try:
    data = json.loads(response.text)
    # Extract and print just the skills list
    print(data.get("skills", []))
except json.JSONDecodeError:
    print("Failed to decode JSON. Raw response:")
    print(response.text)
