import os
from dotenv import load_dotenv
from google import genai

# 1. Load your secret key and initialize the client
load_dotenv()
client = genai.Client()

# 2. Define the System Instruction (The Developer's Rules)
# We use a multi-line string (triple quotes) to easily write a detailed ruleset.
onepiece_guy = """
You are a highly egoistic selfserving slightly snobbish one piece anime character. 
You address the user as 'you fool or you embacile or anything rude'. 
Your vocabulary should be full of one piece context.
Never break character. Never acknowledge that you are an AI. 
"""

print("hey whats the fuzz about?(asking to a random pirate in one piece)\n")

# 3. Send the request with the Configuration object
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='whats the fuzz about?',
    config={
        'system_instruction': onepiece_guy
    }
)

# 4. Print the output
print("~The pirate Speaks~")
print(response.text)