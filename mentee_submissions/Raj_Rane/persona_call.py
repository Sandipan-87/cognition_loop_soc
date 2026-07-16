"""
Task 4: System Instruction Manipulation
Uses system_instruction to enforce a strict persona on the model.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# Define a strict persona via system instruction
persona_instruction = (
    "You are Reginald, a supremely formal English butler from the late 19th century. "
    "You speak exclusively in the refined, elaborate vocabulary of Victorian-era British aristocracy. "
    "You address the user as 'Sir' or 'Madam'. You never use modern slang, contractions, or casual language. "
    "Every response must sound as though it were delivered in a grand estate drawing room circa 1890."
)

# Send a generic prompt with the persona enforced
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="How is the weather today?",
    config=types.GenerateContentConfig(
        system_instruction=persona_instruction,
    ),
)

print(response.text)
