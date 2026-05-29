import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

unstructured_text = "We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. His technical toolkit consists of Python, SQL, and Tableau."

llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)

messages = [
    SystemMessage(content="""Act as a strict data parser. Output ONLY raw JSON. 
    Do not include markdown formatting, code blocks, or conversational text.
    Follow this schema: {"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}"""),
    HumanMessage(content=unstructured_text)
]

raw_output = llm.invoke(messages).text


try:
    data = json.loads(raw_output)
    print(f"Extracted Skills: {data['skills']}")
except json.JSONDecodeError as e:
    print(f"Failed to parse JSON. Raw output was: {raw_output}")