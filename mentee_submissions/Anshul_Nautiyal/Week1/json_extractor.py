import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# Task 5 Unstructured Data
text_block = "We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. His technical toolkit consists of Python, SQL, and Tableau."

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=text_block,
    config=types.GenerateContentConfig(
        system_instruction="""
        You are a strict data parser. Output ONLY raw JSON with no conversational text and absolutely no markdown formatting wrappers (e.g., do not use ```json). 
        The target JSON schema must look like this: {"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}
        """,
        # Setting temperature to 0.0 makes the output more deterministic for data extraction tasks
        temperature=0.0 
    )
)

# Convert the raw text output to a native Python dictionary and print the skills list
data = json.loads(response.text)
print(data.get("skills"))
