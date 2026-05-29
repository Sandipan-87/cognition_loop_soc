import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from google.api_core import exceptions

load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

for i in range(15):
    try:
        response = llm.invoke(f"Request number {i+1}: Say 'Hello'")
        print(f"Success {i+1}: {response.content}")
    except exceptions.ResourceExhausted:
        print(f"Rate limit hit on request {i+1}. Sleeping for 10 seconds...")
        time.sleep(10)
        # Optional: Retry the logic here