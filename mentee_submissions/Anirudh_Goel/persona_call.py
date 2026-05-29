from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")

messages = [
    SystemMessage(content="You are a funny stand-up comedian."),
    HumanMessage(content="How is the weather today?")
]

response = llm.invoke(messages)
print(response.text)