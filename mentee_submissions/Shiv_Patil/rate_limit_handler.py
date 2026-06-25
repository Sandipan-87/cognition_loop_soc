from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
load_dotenv()
import time
from google.api_core.exceptions import ResourceExhausted

llm=ChatGoogleGenerativeAI(model="gemini-2.5-flash")
starttime=time.time()
queries=["how is the capital of india?"]*20
try:
    responses=llm.batch(queries)
    for i in range(1,4):
        print(responses[i].content)
except ResourceExhausted as e:
    print("limit reached")
except Exception as e:
    print("some random error occured")

endtime=time.time()
print(f"total time taken ={endtime-starttime:.2f}seconds")