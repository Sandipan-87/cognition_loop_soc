import os
from dotenv import load_dotenv
from google import genai

# Load  API
load_dotenv()
#connection
client = genai.Client()
print("sending request to server")
response = client.models.generate_content(model='gemini-2.5-flash', contents ='who even was newton.')
print(response.text)