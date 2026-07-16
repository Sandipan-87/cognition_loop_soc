import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")

    unstructured_text = (
        "We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. "
        "His technical toolkit consists of Python, SQL, and Tableau."
    )

    parser_rules = (
        "You are a strict data parser. Output ONLY valid raw JSON with no markdown, no code fences, "
        "and no extra commentary. Follow this exact schema and keys: "
        '{"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}.'
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=unstructured_text,
        config=types.GenerateContentConfig(system_instruction=parser_rules),
    )

    raw_output = response.text
    parsed = json.loads(raw_output)

    print(parsed["skills"])


if __name__ == "__main__":
    main()
