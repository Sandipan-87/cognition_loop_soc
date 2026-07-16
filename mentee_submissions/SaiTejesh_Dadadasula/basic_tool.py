import os
import json
from groq import Groq
from dotenv import load_dotenv
import math

load_dotenv()

client = Groq(
    api_key=os.environ['GROQ_API_KEY']
)

MODEL='llama-3.3-70b-versatile'

def calctrig(theta: float,func: str) -> str:
    
    x= theta * (math.pi)/180
    if func=="sin":
        return str(math.sin(x))
    elif func=="cos":
        return str(math.cos(x))
    elif func=="tan":
        return str(math.tan(x))
    else:
        return "unknown function"
    

tools=[
    {
        "type" : "function",
        "function" : {
            "name" : "calctrig",
            "description" : "Calculate trignomentric value of a theta in degrees",
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "theta" : {
                        "type": "number" ,
                        "description" : "theta in degrees"
                    },
                    "func" : {
                        "type" : "string",
                        "enum" : ["sin" , "cos" ,"tan"],
                        "description" : "trignometric function name"
                    }
                },
                "required" : ["theta" , "func"]
            }
        }
    }
]

available_func = {
    "calctrig" : calctrig 
}


def run_agent():

    user_prompt = "What is tan of 90 degrees" 

    messages = [
        {
            "role" : "system",
            "content" : "You are helpful math assistant"
        },
        {
            "role" : "user",
            "content" : user_prompt
        }
    ]

    first_response = client.chat.completions.create(
        messages=messages,
        tools=tools,
        tool_choice="auto",
        model=MODEL
    )

    response_message = first_response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls :
        print("using tool")
        tool_call = tool_calls[0]
        func_name = tool_call.function.name
        func_args= json.loads(tool_call.function.arguments) # json string loads to python dict

        func_to_call = available_func[func_name]
        func_response = func_to_call(**func_args)

        messages.append(response_message)
        messages.append(
            {
                "role" : "tool" ,
                "tool_call_id" : tool_call.id ,
                "name" : func_name ,
                "content" : func_response
            }   
        )

        second_response = client.chat.completions.create(
            messages=messages,
            model=MODEL
        )

        print(second_response.choices[0].message.content)

    else:
        print("no tool required")
        print(response_message)
 
if __name__=="__main__":
    run_agent()