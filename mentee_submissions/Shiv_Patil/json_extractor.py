import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
load_dotenv()

llm= ChatGroq(model="llama-3.3-70b-versatile",temperature=0)

instruction= """you are strict parser model which outputs ONLY raw JSON, with NO conversational text and NO markdown formatting wrappers (e.g., no ```json or ```).\
    Extract the information from the user's text into this exact schema:
    {"name": "string", "age": integer, "role": "string", "skills": ["string", "string"]}"""


text="We interviewed Alex Mercer today. He is 24 years old and works as a Junior Data Analyst. His technical toolkit consists of Python, SQL, and Tableau."

messages=[HumanMessage(content=text),
          SystemMessage(content=instruction)]

response=llm.invoke(messages).content

json_text=json.loads(response)

print(json_text["skills"])
