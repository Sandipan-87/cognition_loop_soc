import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")

response = llm.invoke("Explain Newton's 2nd law in one sentence")
print(response.text)