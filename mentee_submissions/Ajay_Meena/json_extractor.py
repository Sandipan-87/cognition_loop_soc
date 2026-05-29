from google import genai
from dotenv import load_dotenv
import os
import json

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

text = """
We interviewed Alex Mercer today.
He is 24 years old and works as a Junior Data Analyst.
His technical toolkit consists of Python, SQL, and Tableau.
"""

system_instruction = """
You are a strict data parser.

Return only valid JSON.

Do not include explanations.
Do not include markdown.
Do not include extra text.

Output format:

{
  "name": "string",
  "age": 0,
  "role": "string",
  "skills": ["string"]
}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=text,
    config={
        "system_instruction": system_instruction
    }
)

data = json.loads(response.text)

print(data["skills"])