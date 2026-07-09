import os
import json
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

client=Groq(
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

        # page.wait_for_timeout(1000)
        # page.locator('.result:not(.result--ad) .result__a').nth(0).click()
        # page.wait_for_timeout(1000)
        return page.locator('body').inner_text()

def open_page(url : str):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        page=context.new_page()
        try:
            page.goto(url,timeout=5000)
        except:
            print(f"Page load timed out after 5 seconds. Returning partial content...")
            return page.locator('body').inner_text()[:4000]
        return page.locator('body').inner_text()[:4000]

tools=[
    {
        "type" : "function",
        "function" : {
            "name" : "search_the_web",
            "description" :"searches in duckduckgo and returns search page results body text",
            "parameters" : {
                "type" : "object",
                "properties":{
                    "search_string" : {
                        "type" : "string" ,
                        "description" : "string used for searching in web "
                    }
                },
                "required" : ["search_string"]
            }
        }
    },
    {
        "type" : "function",
        "function" : {
            "name" : "open_page",
            "description" : "opens a url directly and returns body of the text",
            "parameters" : {
                "type" : "object",
                "properties":{
                    "url" : {
                        "type" : "string",
                        "description" : "string which is the direct link url for the site which we are opening "
                                        "Take the url from previous text u searched from the web "
                                        "if one url didnt work take another url from the text searched from the web.."
                    }
                },
                "required" : ["url"]
            }
        }
    }   
]

availale_func={
    "search_the_web" : search_the_web,
    "open_page" : open_page
}

def run_agent():
    messages=[
        {
            "role" : "system",
            "content" : "You are a chat agent  which answers questions and can also take followup questions and then answer"
                        "But if u dont have data u uses tools to search the web and open urls and take the test from it"
                        "and then answers the question"
                        "You must only use the exact tool names provided to you. Do not alter, modify, or append any text to the tool names under any circumstances."
        },

    ]

    max_steps=4
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            break
        messages.append({"role" : "user" , "content": user_input})
        steps=0
        while steps<max_steps:
            response = client.chat.completions.create(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                model=MODEL
            )

            response_message = response.choices[0].message
            tool_calls= response_message.tool_calls

            messages.append(response_message)

            if not tool_calls:
                print(response_message.content)
                break

            for tool_call in tool_calls:
                print(f"using tool {tool_call.function.name}")
                func_name= tool_call.function.name
                func_args= json.loads(tool_call.function.arguments)

                func_to_call= availale_func[func_name]
                func_response= func_to_call(**func_args)

                messages.append(
                    {
                        "role" : "tool",
                        "tool_call_id" : tool_call.id,
                        "name" : func_name,
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