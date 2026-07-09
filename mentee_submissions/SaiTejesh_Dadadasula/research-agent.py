import os
import json
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from datetime import date

today = date.today().strftime("%B %d, %Y")

load_dotenv()

client= Groq(
    api_key=os.environ['GROQ_API_KEY']
)

MODEL='openai/gpt-oss-120b'

# Tool search_the_web
def search_the_web(search_string : str):

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        
        page=context.new_page()
        
        page.goto('https://html.duckduckgo.com/html/')

        page.locator('#search_form_input_homepage').fill(search_string)
        page.locator('#search_button_homepage').click()

        page.wait_for_timeout(1000)
        page.locator('.result:not(.result--ad) .result__a').nth(0).click()
        page.wait_for_timeout(1000)
        return page.locator('body').inner_text()[:4000]


tools=[
    {
        "type" : "function",
        "function" : {
            "name" : "search_the_web",
            "description" : "if data is not available , Search the web and take whole chucks of text in the entire body from the website " ,
            "parameters" : {
                "type" : "object",
                "properties":{
                    "search_string" : {
                        "type" : "string" ,
                        "description" : "string used for searching in web becuz u dont know data"
                    }
                },
                "required" : ["search_string"]
            }
        }
    }
]

available_func = {
    "search_the_web" : search_the_web
}

def run_agent():
    user_prompt= input("type ur question? :")

    messages = [
        {
            "role" : "system",
            "content" : f"You are a assistant working on date {today} which answers things if u know,  but if u dont have live data u will search in internet and scrapes the data using tool given and then answer "
        },
        {
            "role" : "user",
            "content" : user_prompt
        }
    ]

    steps=0
    max_steps=3

    while steps<max_steps:
        response = client.chat.completions.create(
            messages=messages,
            tools=tools,
            tool_choice="auto",
            model=MODEL
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        messages.append(response_message)

        if not tool_calls:
            print(response_message.content)    
            break  
        for tool_call in tool_calls:
            print("using tool")
            func_name= tool_call.function.name
            func_args= json.loads(tool_call.function.arguments)

            func_to_call = available_func[func_name]
            func_response = func_to_call(**func_args)


            messages.append(
                {
                    "role" : "tool" ,
                    "tool_call_id" : tool_call.id,
                    "name" : func_name ,
                    "content" : func_response
                }
            )
        steps+=1
        
    else:
        print("Max steps reached so forcing answer!")
        messages.append({
            "role": "user",
            "content": "Based only on what you've already found above, give me the final answer now. Do not search again."
        })
        final=client.chat.completions.create(
            messages=messages,
            model=MODEL
        )
        print(final.choices[0].message.content)



if __name__=="__main__":
    run_agent()

