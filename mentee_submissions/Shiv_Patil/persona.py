from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
load_dotenv()

instruction="you are a vintage computer terminal from the 1980s"
message=[SystemMessage(content=instruction),
         HumanMessage(content="do you know youtube?")]
llm=ChatGoogleGenerativeAI(model="gemini-2.5-flash")

print(llm.invoke(message).content)