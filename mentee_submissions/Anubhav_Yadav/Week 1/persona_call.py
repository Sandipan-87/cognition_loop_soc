import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")

    client = genai.Client(api_key=api_key)

    persona_rules = (
        "You are Mr. Alderwick, a formal 19th-century English butler. "
        "Always remain polite, composed, and concise. "
        "Address the user as 'sir' or 'madam'. "
        "Never break character, never mention modern AI, and never use slang. "
        "If uncertain, state uncertainty in refined butler language."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="How is the weather today?",
        config=types.GenerateContentConfig(system_instruction=persona_rules),
    )

    print(response.text)


if __name__ == "__main__":
    main()
