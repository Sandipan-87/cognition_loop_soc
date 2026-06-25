from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
load_dotenv()

llm=ChatGoogleGenerativeAI(model="gemini-2.5-flash",temperature=0.7)

response=llm.invoke("Explain Newton's 2nd law in one sentence")
print(response.content)